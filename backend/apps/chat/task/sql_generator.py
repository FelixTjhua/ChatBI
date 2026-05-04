"""SQL生成服务 - 从llm.py中提取的SQL生成相关逻辑"""
import json
import time
import traceback
from datetime import datetime
from typing import Any, List, Optional, Union

import orjson
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from sqlmodel import Session

from apps.chat.crud.chat import (
    start_log, end_log, save_sql_answer, save_sql
)
from apps.chat.models.chat_model import OperationEnum
from apps.chat.thinking.rag_thinking import record_sql_generation
from apps.datasource.crud.permission import get_row_permission_filters
from apps.db.db import exec_sql
from apps.system.schemas.system_schema import AssistantOutDsSchema
from common.error import SingleMessageError, ChatBIDBError, ParseSQLResultError
from common.utils.utils import ChatBILogUtil, extract_nested_json, extract_json_robust
from common.utils.sql_error_handler import classify_sql_error

# 从 llm.py 模块级常量引用
dynamic_subsql_prefix = 'select * from chatbi_dynamic_temp_table_'


class SQLGeneratorMixin:
    """SQL生成相关方法的Mixin类

    通过多继承注入到LLMService中，将SQL生成逻辑从主类中分离。
    所有方法通过self访问LLMService的状态。
    """

    def generate_sql(self, _session: Session):
        # append current question
        self.sql_message.append(HumanMessage(
            self.chat_question.sql_user_question(current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))))

        self.current_logs[OperationEnum.GENERATE_SQL] = start_log(session=_session,
                                                                  ai_modal_id=self.chat_question.ai_modal_id,
                                                                  ai_modal_name=self.chat_question.ai_modal_name,
                                                                  operate=OperationEnum.GENERATE_SQL,
                                                                  record_id=self.record.id,
                                                                  full_message=[
                                                                      {'type': msg.type, 'content': msg.content} for msg
                                                                      in self.sql_message])
        
        # 使用普通LLM进行SQL生成（不使用JSON模式，以保留reasoning_content推理输出）
        
        full_thinking_text = ''
        full_sql_text = ''
        token_usage = {}
        
        # 记录LLM调用开始时间
        llm_start_time = time.time()
        
        # 先发送 loading 状态，让前端立即展示"生成中"
        yield {
            'type': 'thinking_stage', 'stage': 'sql_generation',
            'data': {
                'stage': 'sql_generation',
                'status': 'loading',
                'timestamp': datetime.now().isoformat(),
                'model_name': self.chat_question.ai_modal_name or '',
                'streaming_reasoning': '',
            }
        }
        
        # NOTE: process_stream and stream_with_retry are module-level functions in llm.py,
        # accessed via late import to avoid circular dependency
        from apps.chat.task.llm import process_stream, stream_with_retry
        
        # 用于控制流式推理内容的发送频率
        _reasoning_update_counter = 0
        _REASONING_UPDATE_INTERVAL = 3  # 每3个chunk发送一次推理进度
        
        # 空响应自动重试（最多重试2次，指数退避）
        _max_empty_retries = 2
        _original_sql_user_msg = self.sql_message[-1].content if self.sql_message else ''
        for _empty_attempt in range(_max_empty_retries + 1):
            full_thinking_text = ''  # 重试时需要重置
            full_sql_text = ''
            _reasoning_update_counter = 0
            
            res = process_stream(stream_with_retry(self.llm, self.sql_message), token_usage)
            for chunk in res:
                # 安全处理：确保content不为None
                content = chunk.get('content')
                if content:
                    full_sql_text += content
                reasoning_content = chunk.get('reasoning_content')
                if reasoning_content:
                    full_thinking_text += reasoning_content
                    _reasoning_update_counter += 1
                    # 定期发送推理进度更新，让前端实时展示思考过程
                    if _reasoning_update_counter % _REASONING_UPDATE_INTERVAL == 0:
                        yield {
                            'type': 'thinking_stage', 'stage': 'sql_generation',
                            'data': {
                                'stage': 'sql_generation',
                                'status': 'loading',
                                'timestamp': datetime.now().isoformat(),
                                'model_name': self.chat_question.ai_modal_name or '',
                                'streaming_reasoning': full_thinking_text,
                            }
                        }
                yield chunk
            
            # 如果有内容（包括仅有推理内容），跳出重试循环
            if (full_sql_text and full_sql_text.strip()) or (full_thinking_text and full_thinking_text.strip()):
                break
            
            # 空响应：判断是否需要重试
            if _empty_attempt < _max_empty_retries:
                _wait_time = 1.0 * (2 ** _empty_attempt)  # 指数退避：1s, 2s
                ChatBILogUtil.warning(
                    f"[generate_sql] LLM returned empty content (attempt {_empty_attempt + 1}/{_max_empty_retries + 1}), "
                    f"retrying in {_wait_time:.0f}s... Model: {self.chat_question.ai_modal_name}, "
                    f"Token usage: {token_usage}"
                )
                # 重试时修改 user message，追加重试提示打破空响应模式
                _is_en_retry_sql = (self.chat_question.lang or '').lower().startswith('en')
                _retry_hint_sql = (f"\n\n(Retry attempt {_empty_attempt + 2}: Please generate the SQL query now.)"
                                   if _is_en_retry_sql else
                                   f"\n\n（第{_empty_attempt + 2}次请求：请立即生成SQL查询语句。）")
                self.sql_message[-1] = HumanMessage(content=_original_sql_user_msg + _retry_hint_sql)
                time.sleep(_wait_time)
            # else: 最后一次尝试也失败，继续到下面的空响应检测逻辑

        self.sql_message.append(AIMessage(full_sql_text))

        self.current_logs[OperationEnum.GENERATE_SQL] = end_log(session=_session,
                                                                log=self.current_logs[OperationEnum.GENERATE_SQL],
                                                                full_message=[{'type': msg.type, 'content': msg.content}
                                                                              for msg in self.sql_message],
                                                                reasoning_content=full_thinking_text,
                                                                token_usage=token_usage)
        self.record = save_sql_answer(session=_session, record_id=self.record.id,
                                      answer=orjson.dumps({'content': full_sql_text, 'reasoning_content': full_thinking_text}).decode())
        
        # 某些模型（如Gemini 2.5 Pro）偶尔返回空响应，此时full_sql_text为空字符串
        # 提前检测并抛出友好错误，避免后续check_sql报"Cannot parse sql from answer"
        if not full_sql_text or not full_sql_text.strip():
            # 安全兜底：如果LLM只输出了推理内容但没有最终回答，尝试从推理中提取SQL
            if full_thinking_text and full_thinking_text.strip():
                ChatBILogUtil.warning(
                    f"[generate_sql] LLM returned only reasoning content (length={len(full_thinking_text)}), "
                    f"attempting to extract SQL from reasoning. Model: {self.chat_question.ai_modal_name}"
                )
                # 尝试从推理内容中提取JSON/SQL（某些模型会把结果放在thinking里）
                _extracted = extract_json_robust(full_thinking_text)
                if _extracted:
                    full_sql_text = _extracted
                    self.sql_message[-1] = AIMessage(full_sql_text)
                    ChatBILogUtil.info(f"[generate_sql] Successfully extracted SQL from reasoning content")
                else:
                    full_sql_text = full_thinking_text
                    self.sql_message[-1] = AIMessage(full_sql_text)
            else:
                _is_en = (self.chat_question.lang or '').lower().startswith('en')
                _empty_msg = ('The AI model returned an empty response. This may be due to the model being overloaded or '
                              'the question being too complex. Please try again.\n'
                              '💡 Tip: Try simplifying your question, or check if the datasource contains the relevant tables and fields.') if _is_en else \
                             ('AI模型返回了空响应，可能是模型负载过高或问题过于复杂，请稍后重试。\n'
                              '💡 建议：尝试简化您的问题，或检查数据源中是否包含相关的数据表和字段。')
                ChatBILogUtil.error(
                    f"[generate_sql] LLM returned empty content after {_max_empty_retries + 1} attempts. "
                    f"Model: {self.chat_question.ai_modal_name}, "
                    f"Token usage: {token_usage}, "
                    f"Thinking text length: {len(full_thinking_text)}"
                )
                raise SingleMessageError(_empty_msg)
        
        # 计算SQL生成耗时（使用实际的LLM调用时间）
        sql_generation_time = time.time() - llm_start_time
        
        # 记录SQL生成阶段到思考过程（LLM基于RAG上下文生成）
        try:
            sql, tables = self.check_sql(full_sql_text, lang=self.chat_question.lang if hasattr(self, 'chat_question') else '')
            
            # 构建RAG上下文信息
            rag_context = {
                "schema": self.chat_question.db_schema[:500] if self.chat_question.db_schema else "",
                "terminologies_used": bool(self.chat_question.terminologies),
                "sql_examples_used": bool(self.chat_question.data_training),
                "custom_prompt_used": bool(self.chat_question.custom_prompt)
            }
            
            record_sql_generation(
                self.thinking_process,
                sql=sql,
                tables=tables or [],
                reasoning=full_thinking_text,
                rag_context=rag_context,
                generation_time=sql_generation_time,
                token_usage=token_usage,
                model_name=self.chat_question.ai_modal_name
            )
            
            # 发送最终的 completed 状态
            sql_stage_data = self.thinking_process.get_stage('sql_generation')
            if sql_stage_data:
                yield {'type': 'thinking_stage', 'stage': 'sql_generation', 'data': sql_stage_data}
        except Exception as e:
            ChatBILogUtil.error(f"Failed to record SQL thinking stage: {e}")

    def generate_with_sub_sql(self, session: Session, sql, sub_mappings: list):
        sub_query = json.dumps(sub_mappings, ensure_ascii=False)
        self.chat_question.sql = sql
        self.chat_question.sub_query = sub_query
        dynamic_sql_msg: List[Union[BaseMessage, dict[str, Any]]] = []
        dynamic_sql_msg.append(SystemMessage(content=self.chat_question.dynamic_sys_question()))
        dynamic_sql_msg.append(HumanMessage(content=self.chat_question.dynamic_user_question()))

        self.current_logs[OperationEnum.GENERATE_DYNAMIC_SQL] = start_log(session=session,
                                                                          ai_modal_id=self.chat_question.ai_modal_id,
                                                                          ai_modal_name=self.chat_question.ai_modal_name,
                                                                          operate=OperationEnum.GENERATE_DYNAMIC_SQL,
                                                                          record_id=self.record.id,
                                                                          full_message=[{'type': msg.type,
                                                                                         'content': msg.content}
                                                                                        for
                                                                                        msg in dynamic_sql_msg])

        # 使用JSON模式LLM进行动态SQL生成（强制结构化输出）
        json_llm = self.get_json_mode_llm()
        
        full_thinking_text = ''
        full_dynamic_text = ''
        token_usage = {}

        # NOTE: process_stream is a module-level function in llm.py
        from apps.chat.task.llm import process_stream

        res = process_stream(json_llm.stream(dynamic_sql_msg), token_usage)
        for chunk in res:
            # 安全处理：确保content不为None
            content = chunk.get('content')
            if content:
                full_dynamic_text += content
            reasoning_content = chunk.get('reasoning_content')
            if reasoning_content:
                full_thinking_text += reasoning_content

        dynamic_sql_msg.append(AIMessage(full_dynamic_text))

        self.current_logs[OperationEnum.GENERATE_DYNAMIC_SQL] = end_log(session=session,
                                                                        log=self.current_logs[
                                                                            OperationEnum.GENERATE_DYNAMIC_SQL],
                                                                        full_message=[
                                                                            {'type': msg.type,
                                                                             'content': msg.content}
                                                                            for msg in dynamic_sql_msg],
                                                                        reasoning_content=full_thinking_text,
                                                                        token_usage=token_usage)

        ChatBILogUtil.info(full_dynamic_text)
        return full_dynamic_text

    def generate_assistant_dynamic_sql(self, _session: Session, sql, tables: List):
        ds: AssistantOutDsSchema = self.ds
        sub_query = []
        result_dict = {}
        for table in ds.tables:
            if table.name in tables and table.sql:
                result_dict[table.name] = table.sql
                sub_query.append({"table": table.name, "query": f'{dynamic_subsql_prefix}{table.name}'})
        if not sub_query:
            return None
        temp_sql_text = self.generate_with_sub_sql(session=_session, sql=sql, sub_mappings=sub_query)
        result_dict['chatbi_temp_sql_text'] = temp_sql_text
        return result_dict

    def build_table_filter(self, session: Session, sql: str, filters: list):
        filter = json.dumps(filters, ensure_ascii=False)
        self.chat_question.sql = sql
        self.chat_question.filter = filter
        permission_sql_msg: List[Union[BaseMessage, dict[str, Any]]] = []
        permission_sql_msg.append(SystemMessage(content=self.chat_question.filter_sys_question()))
        permission_sql_msg.append(HumanMessage(content=self.chat_question.filter_user_question()))

        self.current_logs[OperationEnum.GENERATE_SQL_WITH_PERMISSIONS] = start_log(session=session,
                                                                                   ai_modal_id=self.chat_question.ai_modal_id,
                                                                                   ai_modal_name=self.chat_question.ai_modal_name,
                                                                                   operate=OperationEnum.GENERATE_SQL_WITH_PERMISSIONS,
                                                                                   record_id=self.record.id,
                                                                                   full_message=[
                                                                                       {'type': msg.type,
                                                                                        'content': msg.content} for
                                                                                       msg
                                                                                       in permission_sql_msg])
        
        # 使用JSON模式LLM进行权限SQL生成（强制结构化输出）
        json_llm = self.get_json_mode_llm()
        
        full_thinking_text = ''
        full_filter_text = ''
        token_usage = {}

        # NOTE: process_stream is a module-level function in llm.py
        from apps.chat.task.llm import process_stream

        res = process_stream(json_llm.stream(permission_sql_msg), token_usage)
        for chunk in res:
            # 安全处理：确保content不为None
            content = chunk.get('content')
            if content:
                full_filter_text += content
            reasoning_content = chunk.get('reasoning_content')
            if reasoning_content:
                full_thinking_text += reasoning_content

        permission_sql_msg.append(AIMessage(full_filter_text))

        self.current_logs[OperationEnum.GENERATE_SQL_WITH_PERMISSIONS] = end_log(session=session,
                                                                                 log=self.current_logs[
                                                                                     OperationEnum.GENERATE_SQL_WITH_PERMISSIONS],
                                                                                 full_message=[
                                                                                     {'type': msg.type,
                                                                                      'content': msg.content}
                                                                                     for msg in permission_sql_msg],
                                                                                 reasoning_content=full_thinking_text,
                                                                                 token_usage=token_usage)

        ChatBILogUtil.info(full_filter_text)
        return full_filter_text

    def generate_filter(self, _session: Session, sql: str, tables: List):
        filters = get_row_permission_filters(session=_session, current_user=self.current_user, ds=self.ds,
                                             tables=tables)
        if not filters:
            return None
        return self.build_table_filter(session=_session, sql=sql, filters=filters)

    def generate_assistant_filter(self, _session: Session, sql, tables: List):
        ds: AssistantOutDsSchema = self.ds
        filters = []
        for table in ds.tables:
            if table.name in tables and table.rule:
                filters.append({"table": table.name, "filter": table.rule})
        if not filters:
            return None
        return self.build_table_filter(session=_session, sql=sql, filters=filters)

    @staticmethod
    def check_sql(res: str, lang: str = '') -> tuple[str, Optional[list]]:
        """
        检查并解析SQL生成结果
        """
        # 语言感知的错误消息
        _is_en_sql = lang.lower().startswith('en') if lang else True
        _parse_sql_err = ('Unable to parse SQL from the AI response, please try again'
                          if _is_en_sql else '无法从AI响应中解析SQL，请重新提问')
        # 优先使用 extract_json_robust 进行更健壮的 JSON 提取
        # 使用 prefer_type='object' 确保优先提取SQL结果对象而非数组
        from common.utils.utils import extract_json_robust
        json_str = extract_json_robust(res, prefer_type='object')
        if json_str is None:
            # 回退到 extract_nested_json 作为兜底
            json_str = extract_nested_json(res)
        if json_str is None:
            ChatBILogUtil.error(f"Cannot parse JSON from LLM response: {res[:200]}")
            raise SingleMessageError(orjson.dumps({'message': _parse_sql_err,
                                                   'traceback': "Cannot parse sql from answer:\n" + res}).decode())
        
        sql: str
        data: dict
        try:
            data = orjson.loads(json_str)

            if data.get('success'):
                sql = data.get('sql', '')
                if not sql or sql.strip() == '':
                    raise SingleMessageError("SQL query is empty")
                
                # SQL语法预校验（在发送到数据库之前）
                # 使用sqlparse进行基础语法检查，拦截明显的语法错误
                try:
                    import sqlparse
                    parsed = sqlparse.parse(sql)
                    if not parsed or not parsed[0].tokens:
                        ChatBILogUtil.warning(f"SQL syntax check: sqlparse returned empty parse result")
                    else:
                        first_token = parsed[0].tokens[0]
                        # 检查SQL是否以合法的DML关键词开头
                        first_keyword = str(first_token).strip().upper()
                        allowed_starts = ('SELECT', 'WITH', '(')
                        if not any(first_keyword.startswith(kw) for kw in allowed_starts):
                            ChatBILogUtil.warning(
                                f"SQL syntax check: SQL starts with '{first_keyword}', "
                                f"expected one of {allowed_starts}. Potential dangerous SQL blocked."
                            )
                            # 阻止非SELECT语句（防止INSERT/UPDATE/DELETE/DROP等）
                            dangerous_starts = ('INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'TRUNCATE', 'CREATE', 'GRANT', 'REVOKE')
                            if any(first_keyword.startswith(kw) for kw in dangerous_starts):
                                raise SingleMessageError(f"安全限制：不允许执行 {first_keyword} 类型的SQL语句")
                        
                        # 深度检查 WITH/CTE 中是否包含危险 DML 操作
                        sql_upper = sql.upper()
                        dangerous_keywords_in_body = ('INSERT ', 'UPDATE ', 'DELETE ', 'DROP ', 'ALTER ', 'TRUNCATE ', 'CREATE ', 'GRANT ', 'REVOKE ')
                        # 复用 db.py 的 _strip_sql_literals 进行完整的字符串剥离
                        from apps.db.db import _strip_sql_literals
                        _sql_no_strings = _strip_sql_literals(sql_upper)
                        for dk in dangerous_keywords_in_body:
                            if dk in _sql_no_strings:
                                raise SingleMessageError(f"安全限制：SQL语句中包含不允许的操作: {dk.strip()}")
                except SingleMessageError:
                    raise
                except Exception as syntax_e:
                    # 语法检查本身失败不应阻止SQL执行，只记录警告
                    ChatBILogUtil.warning(f"SQL syntax pre-check failed (non-blocking): {syntax_e}")
            else:
                message = data.get('message', 'Failed to generate SQL')
                raise SingleMessageError(message)
        except SingleMessageError as e:
            raise e
        except Exception as e:
            ChatBILogUtil.error(f"Failed to parse SQL result: {e}")
            ChatBILogUtil.exception()
            raise SingleMessageError(orjson.dumps({'message': _parse_sql_err,
                                                   'traceback': f"Cannot parse sql from answer:\n{res}\nError: {str(e)}"}).decode())
        
        return sql, data.get('tables')

    def check_save_sql(self, session: Session, res: str) -> str:
        sql, *_ = self.check_sql(res=res, lang=self.chat_question.lang if hasattr(self, 'chat_question') else '')
        save_sql(session=session, sql=sql, record_id=self.record.id)

        self.chat_question.sql = sql

        return sql

    def execute_sql(self, sql: str):
        """Execute SQL query"""
        ChatBILogUtil.info(f"Executing SQL on ds_id {self.ds.id}: {sql}")
        try:
            return exec_sql(ds=self.ds, sql=sql, origin_column=False)
        except Exception as e:
            if isinstance(e, ParseSQLResultError):
                raise e
            else:
                # 使用结构化错误信息替代原始堆栈跟踪
                error_info = classify_sql_error(str(e))
                structured_msg = f"[{error_info['error_type']}] {error_info['suggestion']}"
                raise ChatBIDBError(structured_msg)

    def apply_field_display_names(self, session: Session, result: dict) -> dict:
        """将SQL查询结果中的内部列名替换为用户可读的显示名（custom_comment）"""
        if not result or not result.get('fields'):
            return result

        try:
            from apps.datasource.models.datasource import CoreField
            ds_id = self.ds.id if hasattr(self.ds, 'id') else None
            if not ds_id:
                return result

            # 查询该数据源所有字段的 field_name → custom_comment 映射
            fields = session.query(CoreField.field_name, CoreField.custom_comment).filter(
                CoreField.ds_id == ds_id
            ).all()

            # 构建映射（小写 field_name → custom_comment），仅当 custom_comment 非空且与 field_name 不同
            name_map = {}
            for f in fields:
                fn = (f.field_name or '').strip().lower()
                cc = (f.custom_comment or '').strip()
                if fn and cc and fn != cc.lower():
                    name_map[fn] = cc

            if not name_map:
                return result

            from common.utils.utils import ChatBILogUtil
            ChatBILogUtil.info(f"[field-display] Applying {len(name_map)} field name mappings for ds_id={ds_id}")

            # 替换 fields 列表
            old_fields = result['fields']
            new_fields = [name_map.get(f.lower(), f) if isinstance(f, str) else f for f in old_fields]
            result['fields'] = new_fields

            # 构建旧列名→新列名的精确映射（保留原始大小写匹配）
            col_rename = {}
            for old_f, new_f in zip(old_fields, new_fields):
                if old_f != new_f:
                    col_rename[old_f] = new_f

            # 替换 data 中每行字典的键名
            if col_rename and result.get('data'):
                new_data = []
                for row in result['data']:
                    new_row = {}
                    for k, v in row.items():
                        new_key = col_rename.get(k, k)
                        new_row[new_key] = v
                    new_data.append(new_row)
                result['data'] = new_data

            ChatBILogUtil.info(f"[field-display] Renamed columns: {col_rename}")
        except Exception as e:
            from common.utils.utils import ChatBILogUtil
            ChatBILogUtil.error(f"[field-display] Failed to apply display names: {e}")

        return result


