import datetime
import re
from typing import Dict, List, Optional

import orjson
import sqlparse
from sqlalchemy import and_, select, update
from sqlalchemy.orm import aliased

from apps.chat.models.chat_model import Chat, ChatRecord, CreateChat, ChatInfo, RenameChat, ChatQuestion, ChatLog, \
    TypeEnum, OperationEnum, ChatRecordResult
from apps.datasource.models.datasource import CoreDatasource
from apps.system.crud.assistant import AssistantOutDsFactory
from common.core.deps import CurrentAssistant, SessionDep, CurrentUser
from common.utils.utils import extract_nested_json, extract_json_robust, ChatBILogUtil

logger = ChatBILogUtil


def get_chat_record_by_id(session: SessionDep, record_id: int) -> Optional[ChatRecord]:
    record: ChatRecord | None = None

    stmt = select(ChatRecord.id, ChatRecord.question, ChatRecord.chat_id, ChatRecord.datasource, ChatRecord.engine_type,
                  ChatRecord.ai_modal_id, ChatRecord.create_by).where(
        and_(ChatRecord.id == record_id))
    result = session.execute(stmt)
    for r in result:
        record = ChatRecord(id=r.id, question=r.question, chat_id=r.chat_id, datasource=r.datasource,
                            engine_type=r.engine_type, ai_modal_id=r.ai_modal_id, create_by=r.create_by)
    return record


def list_chats(session: SessionDep, current_user: CurrentUser) -> List[Chat]:
    oid = current_user.oid if current_user.oid is not None else 1
    chart_list = session.query(Chat).filter(and_(Chat.create_by == current_user.id, Chat.oid == oid)).order_by(
        Chat.create_time.desc()).all()
    return chart_list


def rename_chat(session: SessionDep, rename_object: RenameChat, current_user: CurrentUser = None) -> str:
    chat = session.get(Chat, rename_object.id)
    if not chat:
        raise Exception(f"Chat with id {rename_object.id} not found")

    # 验证用户权限（如果提供了current_user）
    if current_user and chat.create_by != current_user.id:
        raise Exception(f"Permission denied: cannot rename chat {rename_object.id}")

    chat.brief = rename_object.brief.strip()[:20]
    session.add(chat)
    session.flush()
    session.refresh(chat)

    brief = chat.brief
    session.commit()
    return brief


def delete_chat(session, chart_id, current_user: CurrentUser) -> str:
    chat = session.query(Chat).filter(
        and_(Chat.id == chart_id, Chat.create_by == current_user.id)
    ).first()
    if not chat:
        return f'Chat with id {chart_id} not found or already deleted'

    # ChatLog.pid 关联的是 ChatRecord.id（不是 Chat.id）
    # 必须先获取所有 record_id，再删除对应的 ChatLog
    record_ids = [r.id for r in session.query(ChatRecord.id).filter(ChatRecord.chat_id == chart_id).all()]
    if record_ids:
        session.query(ChatLog).filter(ChatLog.pid.in_(record_ids)).delete(synchronize_session=False)
    # 级联删除关联的聊天记录，防止孤儿记录
    session.query(ChatRecord).filter(ChatRecord.chat_id == chart_id).delete()
    session.delete(chat)
    session.commit()

    return f'Chat with id {chart_id} has been deleted'


def delete_chat_record(session: SessionDep, record_id: int, current_user: CurrentUser) -> str:
    record = session.query(ChatRecord).filter(
        and_(ChatRecord.id == record_id, ChatRecord.create_by == current_user.id)
    ).first()

    if not record:
        return f'Chat record with id {record_id} not found or already deleted'

    # 级联删除关联的聊天日志，防止孤儿记录
    session.query(ChatLog).filter(ChatLog.pid == record_id).delete()
    session.delete(record)
    session.commit()

    return f'Chat record with id {record_id} has been deleted'


def get_chart_config(session: SessionDep, chart_record_id: int) -> dict:
    stmt = select(ChatRecord.chart).where(and_(ChatRecord.id == chart_record_id))
    res = session.execute(stmt)
    for row in res:
        try:
            return orjson.loads(row.chart)
        except Exception as e:
            logger.warning(f"Failed to parse chart config for record {chart_record_id}: {e}")
    return {}

def format_chart_fields(chart_info: dict) -> List[str]:
    fields = []
    if chart_info.get('columns') and len(chart_info.get('columns')) > 0:
        for column in chart_info.get('columns'):
            column_str = column.get('value')
            if column.get('value') != column.get('name'):
                column_str = column_str + '(' + column.get('name') + ')'
            fields.append(column_str)
    if chart_info.get('axis'):
        for _type in ['x', 'y', 'series']:
            if chart_info.get('axis').get(_type):
                column = chart_info.get('axis').get(_type)
                column_str = column.get('value')
                if column.get('value') != column.get('name'):
                    column_str = column_str + '(' + column.get('name') + ')'
                fields.append(column_str)
    return fields

def get_last_execute_sql_error(session: SessionDep, chart_id: int) -> Optional[str]:
    stmt = select(ChatRecord.error).where(and_(ChatRecord.chat_id == chart_id)).order_by(
        ChatRecord.create_time.desc()).limit(1)
    res = session.execute(stmt).scalar()
    if res:
        try:
            obj = orjson.loads(res)
            if obj.get('type') and obj.get('type') == 'exec-sql-err':
                return obj.get('traceback')
        except Exception as e:
            logger.warning(f"Failed to parse error JSON for chat {chart_id}: {e}")

    return None


def format_json_data(origin_data: dict) -> dict:
    result = {'fields': origin_data.get('fields') if origin_data.get('fields') else []}
    _list = origin_data.get('data') if origin_data.get('data') else []
    data = format_json_list_data(_list)
    result['data'] = data

    return result


def format_json_list_data(origin_data: list[dict]) -> list[dict]:
    data = []
    for _data in origin_data if origin_data else []:
        _row = {}
        for key, value in _data.items():
            if value is not None:
                # 检查是否为数字且需要特殊处理
                if isinstance(value, (int, float)):
                    # 整数且超过15位 → 转字符串并标记为文本列
                    if isinstance(value, int) and len(str(abs(value))) > 15:
                        value = str(value)
                    # 小数且超过15位有效数字 → 转字符串并标记为文本列
                    elif isinstance(value, float):
                        decimal_str = format(value, '.16f').rstrip('0').rstrip('.')
                        if len(decimal_str) > 15:
                            value = str(value)
            _row[key] = value
        data.append(_row)

    return data


def get_chat_chart_data(session: SessionDep, chat_record_id: int) -> dict:
    stmt = select(ChatRecord.data).where(and_(ChatRecord.id == chat_record_id))
    res = session.execute(stmt)
    for row in res:
        try:
            # row.data 为 None 时 orjson.loads(None) 会抛 TypeError
            if not row.data:
                return {}
            return orjson.loads(row.data)
        except Exception as e:
            logger.warning(f"Failed to parse chart data for record {chat_record_id}: {e}")
    return {}


def get_chat_predict_data(session: SessionDep, chat_record_id: int) -> list:
    stmt = select(ChatRecord.predict_data).where(and_(ChatRecord.id == chat_record_id))
    res = session.execute(stmt)
    for row in res:
        try:
            # row.predict_data 为 None 时 orjson.loads(None) 会抛 TypeError
            if not row.predict_data:
                return []
            parsed_data = orjson.loads(row.predict_data)
            # 确保返回列表类型
            if isinstance(parsed_data, list):
                return parsed_data
            elif isinstance(parsed_data, dict):
                # 如果是字典且不为空，包装成列表
                return [parsed_data] if parsed_data else []
            else:
                # 其他类型返回空列表
                return []
        except Exception as e:
            logger.warning(f"Failed to parse predict data for record {chat_record_id}: {e}")
    return []


def get_chat_with_records_with_data(session: SessionDep, chart_id: int, current_user: CurrentUser,
                                    current_assistant: CurrentAssistant) -> ChatInfo:
    return get_chat_with_records(session, chart_id, current_user, current_assistant, True)


dynamic_ds_types = [1, 3]


def get_chat_with_records(session: SessionDep, chart_id: int, current_user: CurrentUser,
                          current_assistant: CurrentAssistant, with_data: bool = False) -> ChatInfo:
    chat = session.get(Chat, chart_id)
    if not chat:
        raise Exception(f"Chat with id {chart_id} not found")

    # 验证会话归属当前用户，防止 IDOR 越权访问
    if chat.create_by != current_user.id:
        raise Exception(f"Chat with id {chart_id} not found")

    chat_info = ChatInfo(**chat.model_dump())

    if current_assistant and current_assistant.type in dynamic_ds_types:
        out_ds_instance = AssistantOutDsFactory.get_instance(current_assistant)
        ds = out_ds_instance.get_ds(chat.datasource)
    else:
        ds = session.get(CoreDatasource, chat.datasource) if chat.datasource else None

    if not ds:
        chat_info.datasource_exists = False
        chat_info.datasource_name = 'Datasource not exist'
    else:
        chat_info.datasource_exists = True
        chat_info.datasource_name = ds.name
        chat_info.ds_type = ds.type

    sql_alias_log = aliased(ChatLog)
    chart_alias_log = aliased(ChatLog)
    analysis_alias_log = aliased(ChatLog)
    predict_alias_log = aliased(ChatLog)

    stmt = (select(ChatRecord.id, ChatRecord.chat_id, ChatRecord.create_time, ChatRecord.finish_time,
                   ChatRecord.question, ChatRecord.sql_answer, ChatRecord.sql,
                   ChatRecord.chart_answer, ChatRecord.chart, ChatRecord.analysis, ChatRecord.predict,
                   ChatRecord.predict_content,  #  新增：预测报告内容
                   ChatRecord.datasource_select_answer, ChatRecord.analysis_record_id, ChatRecord.predict_record_id,
                   ChatRecord.recommended_question, ChatRecord.first_chat,
                   ChatRecord.finish, ChatRecord.error,
                   ChatRecord.rag_enabled, ChatRecord.rag_results, ChatRecord.thinking_process,
                   ChatRecord.intent, ChatRecord.input_type,
                   sql_alias_log.reasoning_content.label('sql_reasoning_content'),
                   chart_alias_log.reasoning_content.label('chart_reasoning_content'),
                   analysis_alias_log.reasoning_content.label('analysis_reasoning_content'),
                   predict_alias_log.reasoning_content.label('predict_reasoning_content')
                   )
    .outerjoin(sql_alias_log, and_(sql_alias_log.pid == ChatRecord.id,
                                   sql_alias_log.type == TypeEnum.CHAT,
                                   sql_alias_log.operate == OperationEnum.GENERATE_SQL))
    .outerjoin(chart_alias_log, and_(chart_alias_log.pid == ChatRecord.id,
                                     chart_alias_log.type == TypeEnum.CHAT,
                                     chart_alias_log.operate == OperationEnum.GENERATE_CHART))
    .outerjoin(analysis_alias_log, and_(analysis_alias_log.pid == ChatRecord.id,
                                        analysis_alias_log.type == TypeEnum.CHAT,
                                        analysis_alias_log.operate == OperationEnum.ANALYSIS))
    .outerjoin(predict_alias_log, and_(predict_alias_log.pid == ChatRecord.id,
                                       predict_alias_log.type == TypeEnum.CHAT,
                                       predict_alias_log.operate == OperationEnum.PREDICT_DATA))
    .where(and_(ChatRecord.create_by == current_user.id, ChatRecord.chat_id == chart_id)).order_by(
        ChatRecord.create_time))
    if with_data:
        # with_data 分支也需要 JOIN chat_log 获取 reasoning_content
        stmt = (select(ChatRecord.id, ChatRecord.chat_id, ChatRecord.create_time, ChatRecord.finish_time,
                      ChatRecord.question, ChatRecord.sql_answer, ChatRecord.sql,
                      ChatRecord.chart_answer, ChatRecord.chart, ChatRecord.analysis, ChatRecord.predict,
                      ChatRecord.predict_content,
                      ChatRecord.datasource_select_answer, ChatRecord.analysis_record_id, ChatRecord.predict_record_id,
                      ChatRecord.recommended_question, ChatRecord.first_chat,
                      ChatRecord.finish, ChatRecord.error, ChatRecord.data, ChatRecord.predict_data,
                      ChatRecord.rag_enabled, ChatRecord.rag_results, ChatRecord.thinking_process,
                      ChatRecord.intent, ChatRecord.input_type,
                      sql_alias_log.reasoning_content.label('sql_reasoning_content'),
                      chart_alias_log.reasoning_content.label('chart_reasoning_content'),
                      analysis_alias_log.reasoning_content.label('analysis_reasoning_content'),
                      predict_alias_log.reasoning_content.label('predict_reasoning_content')
                      )
        .outerjoin(sql_alias_log, and_(sql_alias_log.pid == ChatRecord.id,
                                       sql_alias_log.type == TypeEnum.CHAT,
                                       sql_alias_log.operate == OperationEnum.GENERATE_SQL))
        .outerjoin(chart_alias_log, and_(chart_alias_log.pid == ChatRecord.id,
                                         chart_alias_log.type == TypeEnum.CHAT,
                                         chart_alias_log.operate == OperationEnum.GENERATE_CHART))
        .outerjoin(analysis_alias_log, and_(analysis_alias_log.pid == ChatRecord.id,
                                            analysis_alias_log.type == TypeEnum.CHAT,
                                            analysis_alias_log.operate == OperationEnum.ANALYSIS))
        .outerjoin(predict_alias_log, and_(predict_alias_log.pid == ChatRecord.id,
                                           predict_alias_log.type == TypeEnum.CHAT,
                                           predict_alias_log.operate == OperationEnum.PREDICT_DATA))
        .where(and_(ChatRecord.create_by == current_user.id, ChatRecord.chat_id == chart_id)).order_by(
            ChatRecord.create_time))

    result = session.execute(stmt).all()
    record_list: list[ChatRecordResult] = []
    for row in result:
        if not with_data:
            record_list.append(
                ChatRecordResult(id=row.id, chat_id=row.chat_id, create_time=row.create_time,
                                 finish_time=row.finish_time,
                                 question=row.question, sql_answer=row.sql_answer, sql=row.sql,
                                 chart_answer=row.chart_answer, chart=row.chart,
                                 analysis=row.analysis, predict=row.predict,
                                 predict_content=row.predict_content,  #  新增：预测报告内容
                                 datasource_select_answer=row.datasource_select_answer,
                                 analysis_record_id=row.analysis_record_id, predict_record_id=row.predict_record_id,
                                 recommended_question=row.recommended_question, first_chat=row.first_chat,
                                 finish=row.finish, error=row.error,
                                 rag_enabled=row.rag_enabled, rag_results=row.rag_results, thinking_process=row.thinking_process,
                                 intent=row.intent, input_type=row.input_type,
                                 sql_reasoning_content=row.sql_reasoning_content,
                                 chart_reasoning_content=row.chart_reasoning_content,
                                 analysis_reasoning_content=row.analysis_reasoning_content,
                                 predict_reasoning_content=row.predict_reasoning_content,
                                 ))
        else:
            record_list.append(
                ChatRecordResult(id=row.id, chat_id=row.chat_id, create_time=row.create_time,
                                 finish_time=row.finish_time,
                                 question=row.question, sql_answer=row.sql_answer, sql=row.sql,
                                 chart_answer=row.chart_answer, chart=row.chart,
                                 analysis=row.analysis, predict=row.predict,
                                 predict_content=row.predict_content,
                                 datasource_select_answer=row.datasource_select_answer,
                                 analysis_record_id=row.analysis_record_id, predict_record_id=row.predict_record_id,
                                 recommended_question=row.recommended_question, first_chat=row.first_chat,
                                 finish=row.finish, error=row.error, data=row.data, predict_data=row.predict_data,
                                 rag_enabled=row.rag_enabled, rag_results=row.rag_results, thinking_process=row.thinking_process,
                                 intent=row.intent, input_type=row.input_type,
                                 sql_reasoning_content=row.sql_reasoning_content,
                                 chart_reasoning_content=row.chart_reasoning_content,
                                 analysis_reasoning_content=row.analysis_reasoning_content,
                                 predict_reasoning_content=row.predict_reasoning_content,
                                 ))

    result = list(map(format_record, record_list))

    for row in result:
        try:
            data_value = row.get('data')
            if data_value is not None:
                row['data'] = format_json_data(data_value)
        except Exception as e:
            logger.warning(f"Failed to format JSON data for record: {e}")
        # predict_data 也需要格式化处理大数字，防止前端 JS 精度丢失
        try:
            predict_data_value = row.get('predict_data')
            if predict_data_value is not None and isinstance(predict_data_value, list):
                row['predict_data'] = format_json_list_data(predict_data_value)
        except Exception as e:
            logger.warning(f"Failed to format predict_data for record: {e}")

    chat_info.records = result

    return chat_info


def format_record(record: ChatRecordResult) -> dict:
    _dict = record.model_dump()

    # 计算 run_time（数据库列已在migration 024中移除，需要从时间戳计算）
    # 前端 ChatRecord 依赖此字段展示响应耗时
    if record.create_time and record.finish_time:
        try:
            _delta = (record.finish_time - record.create_time).total_seconds()
            _dict['run_time'] = round(_delta, 2) if _delta > 0 else 0
        except Exception:
            _dict['run_time'] = 0
    else:
        _dict['run_time'] = 0

    if record.sql_answer and record.sql_answer.strip() != '' and record.sql_answer.strip()[0] == '{' and \
            record.sql_answer.strip()[-1] == '}':
        try:
            _obj = orjson.loads(record.sql_answer)
            # 优先使用reasoning_content（DeepSeek R1、OpenAI o1/o3等推理模型）
            _reasoning = _obj.get('reasoning_content')
            if _reasoning and _reasoning.strip():
                _dict['sql_answer'] = _reasoning
            else:
                # 模型不支持reasoning_content时（如Gemini），从content中提取可读文本
                _content = _obj.get('content')
                if _content and _content.strip():
                    # content是LLM的原始输出，可能是SQL JSON（含markdown代码块包裹）。尝试提取message字段作为可读文本
                    _content_stripped = _content.strip()
                    # 去除可能的markdown代码块包裹
                    _json_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', _content_stripped)
                    if _json_block_match:
                        _content_stripped = _json_block_match.group(1).strip()
                    try:
                        _sql_obj = orjson.loads(_content_stripped)
                        if isinstance(_sql_obj, dict):
                            _msg = _sql_obj.get('message', '')
                            _sql = _sql_obj.get('sql', '')
                            # 构建可读的生成过程文本
                            parts = []
                            if _msg:
                                parts.append(_msg)
                            if _sql:
                                parts.append(f"```sql\n{_sql}\n```")
                            _dict['sql_answer'] = '\n\n'.join(parts) if parts else _content
                        else:
                            _dict['sql_answer'] = _content
                    except Exception:
                        # content不是JSON，直接使用原始文本
                        _dict['sql_answer'] = _content
        except Exception as e:
            logger.warning(f"Failed to parse sql_answer JSON: {e}")
    if record.sql_reasoning_content and record.sql_reasoning_content.strip() != '':
        _dict['sql_answer'] = record.sql_reasoning_content
    if record.chart_answer and record.chart_answer.strip() != '' and record.chart_answer.strip()[0] == '{' and \
            record.chart_answer.strip()[-1] == '}':
        try:
            _obj = orjson.loads(record.chart_answer)
            # reasoning_content可能为None，此时保留原始chart_answer而非覆盖为None
            _reasoning = _obj.get('reasoning_content')
            if _reasoning is not None:
                _dict['chart_answer'] = _reasoning
        except Exception as e:
            logger.warning(f"Failed to parse chart_answer JSON: {e}")
    if record.chart_reasoning_content and record.chart_reasoning_content.strip() != '':
        _dict['chart_answer'] = record.chart_reasoning_content
    if record.analysis and record.analysis.strip() != '' and record.analysis.strip()[0] == '{' and \
            record.analysis.strip()[-1] == '}':
        try:
            _obj = orjson.loads(record.analysis)
            # 验证解析后的对象确实包含 content 键
            if isinstance(_obj, dict) and 'content' in _obj:
                _dict['analysis_thinking'] = _obj.get('reasoning_content')
                _dict['analysis'] = _obj.get('content')
            # else: 不是预期格式，保留原始 analysis 文本
        except Exception as e:
            logger.warning(f"Failed to parse analysis JSON: {e}")
    if record.analysis_reasoning_content and record.analysis_reasoning_content.strip() != '':
        _dict['analysis_thinking'] = record.analysis_reasoning_content
    if record.predict and record.predict.strip() != '' and record.predict.strip()[0] == '{' and record.predict.strip()[
        -1] == '}':
        try:
            _obj = orjson.loads(record.predict)
            if isinstance(_obj, dict) and ('reasoning_content' in _obj or 'content' in _obj):
                # predict字段应存储预测报告文本（与analysis字段对齐）
                _dict['predict_thinking'] = _obj.get('reasoning_content')
                # 优先使用独立的predict_content字段（由generate_predict单独保存）
                # 如果predict_content为空，则从predict JSON的content中提取
                if record.predict_content and record.predict_content.strip() != '':
                    _dict['predict'] = record.predict_content
                elif _obj.get('content'):
                    # content可能是预测数据JSON数组（如[{"date":"2025-01","value":100}]）
                    # 而非可读的预测报告文本。JSON数组不应作为predict展示内容
                    _content = _obj.get('content', '').strip()
                    if _content.startswith('['):
                        # 预测数据JSON数组，不适合展示，清空predict让前端只显示图表
                        _dict['predict'] = ''
                    else:
                        _dict['predict'] = _content
            # else: 不是预期格式，保留原始 predict 文本
        except Exception as e:
            logger.warning(f"Failed to parse predict JSON: {e}")
    if record.predict_reasoning_content and record.predict_reasoning_content.strip() != '':
        _dict['predict_thinking'] = record.predict_reasoning_content
    # predict_content独立字段优先级最高
    if record.predict_content and record.predict_content.strip() != '':
        _dict['predict'] = record.predict_content
    if record.data and record.data.strip() != '':
        try:
            _obj = orjson.loads(record.data)
            _dict['data'] = _obj
        except Exception as e:
            logger.warning(f"Failed to parse record data JSON: {e}")
    if record.predict_data and record.predict_data.strip() != '':
        try:
            _obj = orjson.loads(record.predict_data)
            _dict['predict_data'] = _obj
        except Exception as e:
            logger.warning(f"Failed to parse predict_data JSON: {e}")
    if record.sql and record.sql.strip() != '':
        try:
            _dict['sql'] = sqlparse.format(record.sql, reindent=True)
        except Exception as e:
            logger.warning(f"Failed to format SQL: {e}")
    # 解析 rag_results 和 thinking_process JSON 字符串为对象
    # 让前端统一接收对象格式，不需要再判断 string/object 两种情况
    if record.rag_results and isinstance(record.rag_results, str) and record.rag_results.strip() != '':
        try:
            _dict['rag_results'] = orjson.loads(record.rag_results)
        except Exception as e:
            logger.warning(f"Failed to parse rag_results JSON: {e}")
    if record.thinking_process and isinstance(record.thinking_process, str) and record.thinking_process.strip() != '':
        try:
            _dict['thinking_process'] = orjson.loads(record.thinking_process)
        except Exception as e:
            logger.warning(f"Failed to parse thinking_process JSON: {e}")

    # 提取 direct_answer 字段（直接回答路径的回答内容）
    _direct_answer_intents = {'summarization', 'general_chat', 'irrelevant_query',
                              'term_explanation', 'ambiguous_query', 'document_qa'}
    _intent = record.intent or ''
    # 条件1：intent 是直接回答类型
    # 条件2：有 analysis 内容但没有 sql（兜底：intent 保存失败时仍能识别直接回答）
    _is_direct = _intent in _direct_answer_intents or (
        _dict.get('analysis') and not record.sql and not record.chart
    )
    if _is_direct and _dict.get('analysis'):
        _dict['direct_answer'] = _dict['analysis']

    # 提取 smart_answer 字段（智能输出：单行极值结果的自然语言回答）
    if record.chart and record.chart.strip():
        try:
            _chart_obj = orjson.loads(record.chart) if isinstance(record.chart, str) else record.chart
            if isinstance(_chart_obj, dict) and _chart_obj.get('smart_output') and _chart_obj.get('title'):
                _dict['smart_answer'] = _chart_obj['title']
        except Exception:
            pass

    # 从 thinking_process 恢复 layered_recommendations
    _tp = _dict.get('thinking_process')
    if _tp and isinstance(_tp, dict):
        _stages = _tp.get('stages', {})
        if isinstance(_stages, dict):
            _lr = {}
            for _layer in ('pre', 'mid', 'post'):
                _rec_stage = _stages.get(f'recommendation_{_layer}')
                if _rec_stage and isinstance(_rec_stage, dict):
                    _extra = _rec_stage.get('extra_data', _rec_stage)
                    _questions = _extra.get('questions', [])
                    _types = _extra.get('types', [])
                    if _questions:
                        _lr[_layer] = [
                            {'question': q, 'type': _types[i] if i < len(_types) else '', 'layer': _layer}
                            for i, q in enumerate(_questions)
                        ]
            if _lr:
                _dict['layered_recommendations'] = _lr

    # 从 thinking_process 恢复 prediction_confidence
    if _tp and isinstance(_tp, dict):
        _stages = _tp.get('stages', {})
        if isinstance(_stages, dict):
            _pred_stage = _stages.get('data_prediction')
            if _pred_stage and isinstance(_pred_stage, dict):
                _pc = _pred_stage.get('prediction_confidence')
                if not _pc:
                    _extra = _pred_stage.get('extra_data', {})
                    if isinstance(_extra, dict):
                        _pc = _extra.get('prediction_confidence')
                if _pc:
                    _dict['prediction_confidence'] = _pc

    return _dict


def list_generate_sql_logs(session: SessionDep, chart_id: int) -> List[ChatLog]:
    stmt = select(ChatLog).where(
        and_(ChatLog.pid.in_(select(ChatRecord.id).where(and_(ChatRecord.chat_id == chart_id))),
             ChatLog.type == TypeEnum.CHAT, ChatLog.operate == OperationEnum.GENERATE_SQL)).order_by(
        ChatLog.start_time)
    result = session.execute(stmt).all()
    _list = []
    for row in result:
        for r in row:
            _list.append(ChatLog(**r.model_dump()))
    return _list


def list_generate_chart_logs(session: SessionDep, chart_id: int) -> List[ChatLog]:
    stmt = select(ChatLog).where(
        and_(ChatLog.pid.in_(select(ChatRecord.id).where(and_(ChatRecord.chat_id == chart_id))),
             ChatLog.type == TypeEnum.CHAT, ChatLog.operate == OperationEnum.GENERATE_CHART)).order_by(
        ChatLog.start_time)
    result = session.execute(stmt).all()
    _list = []
    for row in result:
        for r in row:
            _list.append(ChatLog(**r.model_dump()))
    return _list


def create_chat(session: SessionDep, current_user: CurrentUser, create_chat_obj: CreateChat,
                require_datasource: bool = True) -> ChatInfo:
    if not create_chat_obj.datasource and require_datasource:
        raise Exception("Datasource cannot be None")

    if not create_chat_obj.question or create_chat_obj.question.strip() == '':
        create_chat_obj.question = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    chat = Chat(create_time=datetime.datetime.now(),
                create_by=current_user.id,
                oid=current_user.oid if current_user.oid is not None else 1,
                brief=create_chat_obj.question.strip()[:20],
                origin=create_chat_obj.origin if create_chat_obj.origin is not None else 0)
    ds: CoreDatasource | None = None
    if create_chat_obj.datasource:
        chat.datasource = create_chat_obj.datasource
        ds = session.get(CoreDatasource, create_chat_obj.datasource)

        if not ds:
            raise Exception(f"Datasource with id {create_chat_obj.datasource} not found")

        chat.engine_type = ds.type_name
    else:
        chat.engine_type = ''

    chat_info = ChatInfo(**chat.model_dump())

    session.add(chat)
    session.flush()
    session.refresh(chat)
    chat_info.id = chat.id
    session.commit()

    if ds:
        chat_info.datasource_exists = True
        chat_info.datasource_name = ds.name
        chat_info.ds_type = ds.type

    if require_datasource and ds:
        # generate first empty record
        record = ChatRecord()
        record.chat_id = chat.id
        record.datasource = ds.id
        record.engine_type = ds.type_name
        record.first_chat = True
        record.finish = True
        record.create_time = datetime.datetime.now()
        record.create_by = current_user.id

        _record = ChatRecord(**record.model_dump())

        session.add(record)
        session.flush()
        session.refresh(record)
        _record.id = record.id
        session.commit()

        chat_info.records.append(_record)

    return chat_info


def save_question(session: SessionDep, current_user: CurrentUser, question: ChatQuestion) -> ChatRecord:
    if not question.chat_id:
        raise Exception("ChatId cannot be None")
    if not question.question or question.question.strip() == '':
        raise Exception("Question cannot be Empty")

    # chat = session.query(Chat).filter(Chat.id == question.chat_id).first()
    chat: Chat = session.get(Chat, question.chat_id)
    if not chat:
        raise Exception(f"Chat with id {question.chat_id} not found")

    record = ChatRecord()
    record.question = question.question
    record.chat_id = chat.id
    record.create_time = datetime.datetime.now()
    record.create_by = current_user.id
    record.datasource = chat.datasource
    record.engine_type = chat.engine_type
    record.ai_modal_id = question.ai_modal_id
    record.input_type = getattr(question, 'input_type', 'manual') or 'manual'

    result = ChatRecord(**record.model_dump())

    session.add(record)
    session.flush()
    session.refresh(record)
    result.id = record.id
    session.commit()

    return result


def save_analysis_predict_record(session: SessionDep, base_record: ChatRecord, action_type: str) -> ChatRecord:
    record = ChatRecord()
    record.question = base_record.question
    record.chat_id = base_record.chat_id
    record.datasource = base_record.datasource
    record.engine_type = base_record.engine_type
    record.ai_modal_id = base_record.ai_modal_id
    record.create_time = datetime.datetime.now()
    record.create_by = base_record.create_by
    record.chart = base_record.chart
    record.data = base_record.data
    record.input_type = base_record.input_type or 'manual'

    if action_type == 'analysis':
        record.analysis_record_id = base_record.id
    elif action_type == 'predict':
        record.predict_record_id = base_record.id

    result = ChatRecord(**record.model_dump())

    session.add(record)
    session.flush()
    session.refresh(record)
    result.id = record.id
    session.commit()

    return result


def start_log(session: SessionDep, ai_modal_id: int, ai_modal_name: str, operate: OperationEnum, record_id: int,
              full_message: list[dict]) -> ChatLog:
    log = ChatLog(type=TypeEnum.CHAT, operate=operate, pid=record_id, ai_modal_id=ai_modal_id, base_modal=ai_modal_name,
                  messages=full_message, start_time=datetime.datetime.now())

    result = ChatLog(**log.model_dump())

    session.add(log)
    session.flush()
    session.refresh(log)
    result.id = log.id
    session.commit()

    return result


def end_log(session: SessionDep, log: ChatLog, full_message: list[dict], reasoning_content: str = None,
            token_usage=None) -> ChatLog:
    if token_usage is None:
        token_usage = {}
    log.messages = full_message
    log.token_usage = token_usage
    log.finish_time = datetime.datetime.now()
    log.reasoning_content = reasoning_content if reasoning_content and len(reasoning_content.strip()) > 0 else None

    stmt = update(ChatLog).where(and_(ChatLog.id == log.id)).values(
        messages=log.messages,
        token_usage=log.token_usage,
        finish_time=log.finish_time,
        reasoning_content=log.reasoning_content
    )
    session.execute(stmt)
    session.commit()

    return log


def save_sql_answer(session: SessionDep, record_id: int, answer: str) -> ChatRecord:
    if not record_id:
        raise Exception("Record id cannot be None")

    stmt = update(ChatRecord).where(and_(ChatRecord.id == record_id)).values(
        sql_answer=answer,
    )

    session.execute(stmt)

    session.commit()

    record = get_chat_record_by_id(session, record_id)

    return record


def save_analysis_answer(session: SessionDep, record_id: int, answer: str = '') -> ChatRecord:
    if not record_id:
        raise Exception("Record id cannot be None")

    stmt = update(ChatRecord).where(and_(ChatRecord.id == record_id)).values(
        analysis=answer,
    )

    session.execute(stmt)

    session.commit()

    record = get_chat_record_by_id(session, record_id)

    return record


def save_predict_answer(session: SessionDep, record_id: int, answer: str) -> ChatRecord:
    if not record_id:
        raise Exception("Record id cannot be None")

    stmt = update(ChatRecord).where(and_(ChatRecord.id == record_id)).values(
        predict=answer,
    )

    session.execute(stmt)

    session.commit()

    record = get_chat_record_by_id(session, record_id)

    return record


def save_select_datasource_answer(session: SessionDep, record_id: int, answer: str,
                                  datasource: int = None, engine_type: str = None) -> ChatRecord:
    if not record_id:
        raise Exception("Record id cannot be None")
    record = get_chat_record_by_id(session, record_id)

    record.datasource_select_answer = answer

    if datasource:
        record.datasource = datasource
        record.engine_type = engine_type

    result = ChatRecord(**record.model_dump())

    if datasource:
        stmt = update(ChatRecord).where(and_(ChatRecord.id == record.id)).values(
            datasource_select_answer=record.datasource_select_answer,
            datasource=record.datasource,
            engine_type=record.engine_type,
        )
    else:
        stmt = update(ChatRecord).where(and_(ChatRecord.id == record.id)).values(
            datasource_select_answer=record.datasource_select_answer,
        )

    session.execute(stmt)

    session.commit()

    return result


def save_recommend_question_answer(session: SessionDep, record_id: int,
                                   answer: dict = None) -> ChatRecord:
    if not record_id:
        raise Exception("Record id cannot be None")

    recommended_question_answer = orjson.dumps(answer).decode()

    json_str = '[]'
    if answer and answer.get('content') and answer.get('content') != '':
        try:
            content = answer.get('content').strip()
            
            # 增强的JSON数组解析策略
            # 策略1: 直接尝试解析（如果已经是有效JSON）
            if content.startswith('[') and content.endswith(']'):
                try:
                    orjson.loads(content)
                    json_str = content
                    ChatBILogUtil.info(f"直接解析推荐问题成功: {json_str[:100]}")
                except (ValueError, Exception):
                    pass
            
            # 策略2: 使用extract_json_robust提取
            if json_str == '[]':
                extracted = extract_json_robust(content)
                if extracted:
                    # 验证是否是数组
                    try:
                        data = orjson.loads(extracted)
                        if isinstance(data, list):
                            json_str = extracted
                            ChatBILogUtil.info(f"使用extract_json_robust提取推荐问题成功: {json_str[:100]}")
                        else:
                            ChatBILogUtil.warning(f"提取的JSON不是数组格式: {extracted[:100]}")
                    except (ValueError, Exception):
                        pass
            
            # 策略3: 从代码块中提取
            if json_str == '[]':
                # 匹配 ```json [...] ``` 或 ``` [...] ```
                code_block_pattern = r'```(?:json)?\s*(\[[\s\S]*?\])\s*```'
                match = re.search(code_block_pattern, content)
                if match:
                    candidate = match.group(1).strip()
                    try:
                        orjson.loads(candidate)
                        json_str = candidate
                        ChatBILogUtil.info(f"从代码块提取推荐问题成功: {json_str[:100]}")
                    except (ValueError, Exception):
                        pass
            
            # 策略4: 直接查找JSON数组（最后的尝试）
            if json_str == '[]':
                array_pattern = r'\[(?:[^\[\]]|\[[^\[\]]*\])*\]'
                matches = list(re.finditer(array_pattern, content))
                if matches:
                    # 从最后一个开始尝试（通常最后一个是完整的）
                    for match in reversed(matches):
                        try:
                            candidate = match.group(0)
                            data = orjson.loads(candidate)
                            if isinstance(data, list) and len(data) > 0:
                                json_str = candidate
                                ChatBILogUtil.info(f"通过正则提取推荐问题成功: {json_str[:100]}")
                                break
                        except (ValueError, Exception):
                            continue
            
            if json_str == '[]':
                ChatBILogUtil.warning(f"无法从内容中提取有效的JSON数组，使用空数组。原始内容: {content[:200]}")
                
        except Exception as e:
            ChatBILogUtil.error(f"解析推荐问题时出错: {e}")
            ChatBILogUtil.exception()
            
    recommended_question = json_str

    stmt = update(ChatRecord).where(and_(ChatRecord.id == record_id)).values(
        recommended_question_answer=recommended_question_answer,
        recommended_question=recommended_question,
    )

    session.execute(stmt)

    session.commit()

    # get_chat_record_by_id 只查询部分列并手动构造新对象，
    record = session.get(ChatRecord, record_id)
    if record is None:
        raise Exception(f"Record {record_id} not found after update")
    # session.get 在 commit 后会返回最新数据，无需手动覆盖

    return record


def save_sql(session: SessionDep, record_id: int, sql: str) -> ChatRecord:
    if not record_id:
        raise Exception("Record id cannot be None")

    record = get_chat_record_by_id(session, record_id)

    record.sql = sql

    result = ChatRecord(**record.model_dump())

    stmt = update(ChatRecord).where(and_(ChatRecord.id == record.id)).values(
        sql=record.sql
    )

    session.execute(stmt)

    session.commit()

    return result


def save_chart_answer(session: SessionDep, record_id: int, answer: str) -> ChatRecord:
    if not record_id:
        raise Exception("Record id cannot be None")

    stmt = update(ChatRecord).where(and_(ChatRecord.id == record_id)).values(
        chart_answer=answer,
    )

    session.execute(stmt)

    session.commit()

    record = get_chat_record_by_id(session, record_id)

    return record


def save_chart(session: SessionDep, record_id: int, chart: str) -> ChatRecord:
    if not record_id:
        raise Exception("Record id cannot be None")
    record = get_chat_record_by_id(session, record_id)

    record.chart = chart

    result = ChatRecord(**record.model_dump())

    stmt = update(ChatRecord).where(and_(ChatRecord.id == record.id)).values(
        chart=record.chart
    )

    session.execute(stmt)

    session.commit()

    return result


def save_predict_data(session: SessionDep, record_id: int, data: str = '') -> ChatRecord:
    if not record_id:
        raise Exception("Record id cannot be None")
    record = get_chat_record_by_id(session, record_id)

    record.predict_data = data

    result = ChatRecord(**record.model_dump())

    stmt = update(ChatRecord).where(and_(ChatRecord.id == record.id)).values(
        predict_data=record.predict_data
    )

    session.execute(stmt)

    session.commit()

    return result


def save_error_message(session: SessionDep, record_id: int, message: str) -> ChatRecord:
    if not record_id:
        raise Exception("Record id cannot be None")
    record = get_chat_record_by_id(session, record_id)

    record.error = message
    record.finish = True
    record.finish_time = datetime.datetime.now()

    result = ChatRecord(**record.model_dump())

    stmt = update(ChatRecord).where(and_(ChatRecord.id == record.id)).values(
        error=record.error,
        finish=record.finish,
        finish_time=record.finish_time
    )

    session.execute(stmt)

    session.commit()

    return result


def save_sql_exec_data(session: SessionDep, record_id: int, data: str) -> ChatRecord:
    if not record_id:
        raise Exception("Record id cannot be None")
    record = get_chat_record_by_id(session, record_id)

    record.data = data

    result = ChatRecord(**record.model_dump())

    stmt = update(ChatRecord).where(and_(ChatRecord.id == record.id)).values(
        data=record.data,
    )

    session.execute(stmt)

    session.commit()

    return result


def finish_record(session: SessionDep, record_id: int) -> ChatRecord:
    if not record_id:
        raise Exception("Record id cannot be None")
    record = get_chat_record_by_id(session, record_id)

    record.finish = True
    record.finish_time = datetime.datetime.now()

    result = ChatRecord(**record.model_dump())

    stmt = update(ChatRecord).where(and_(ChatRecord.id == record.id)).values(
        finish=record.finish,
        finish_time=record.finish_time
    )

    session.execute(stmt)

    session.commit()

    return result


def get_old_questions(session: SessionDep, datasource: int, user_id: int = None) -> List[str]:
    records = []
    if not datasource:
        return records
    # 添加 create_by 过滤，防止多用户共享数据源时跨用户信息泄露
    conditions = [
        ChatRecord.datasource == datasource,
        ChatRecord.question.isnot(None),
        ChatRecord.error.is_(None),
    ]
    if user_id:
        conditions.append(ChatRecord.create_by == user_id)
    stmt = select(ChatRecord.question).where(
        and_(*conditions)).order_by(
        ChatRecord.create_time.desc()).limit(20)
    result = session.execute(stmt)
    for r in result:
        records.append(r.question)
    return records


def save_rag_results(session: SessionDep, record_id: int, rag_enabled: bool = True, rag_results=None) -> ChatRecord:
    """Save RAG retrieval results to chat record"""
    if not record_id:
        raise Exception("Record id cannot be None")
    
    # JSONB 字段：接受 dict 或 JSON 字符串，统一转为 dict 存储
    rag_data = rag_results
    if isinstance(rag_data, str):
        try:
            rag_data = orjson.loads(rag_data)
        except Exception:
            rag_data = None
    
    stmt = update(ChatRecord).where(and_(ChatRecord.id == record_id)).values(
        rag_enabled=rag_enabled,
        rag_results=rag_data
    )
    
    session.execute(stmt)
    session.commit()
    
    record = get_chat_record_by_id(session, record_id)
    return record


def merge_rag_custom_prompts(session: SessionDep, record_id: int, new_custom_prompts: list) -> None:
    """将内联分析/预测的自定义提示词合并到已有的rag_results中
    
    内联执行时（skip_rag=True），分析/预测路径不会覆盖DB中的rag_results，
    但其自定义提示词信息需要追加到已有结果中，以便历史记录加载时能完整展示。
    """
    if not record_id or not new_custom_prompts:
        return
    try:
        # JSONB 字段：直接读取为 dict，无需手动反序列化
        stmt = select(ChatRecord.rag_results).where(and_(ChatRecord.id == record_id))
        result = session.execute(stmt).first()
        if not result or not result.rag_results:
            return
        existing = result.rag_results
        if isinstance(existing, str):
            existing = orjson.loads(existing)
        if not isinstance(existing, dict):
            return
        existing_prompts = existing.get('custom_prompts', [])
        existing_types = {p.get('type') for p in existing_prompts}
        for np in new_custom_prompts:
            if np.get('type') not in existing_types:
                existing_prompts.append(np)
        existing['custom_prompts'] = existing_prompts
        existing['custom_prompt_checked'] = True
        update_stmt = update(ChatRecord).where(and_(ChatRecord.id == record_id)).values(
            rag_results=existing
        )
        session.execute(update_stmt)
        session.commit()
    except Exception as e:
        logger.warning(f"Failed to merge RAG custom prompts for record {record_id}: {e}")


def save_thinking_process(session: SessionDep, record_id: int, thinking_process=None) -> ChatRecord:
    """Save thinking process to chat record and think_process table"""
    if not record_id:
        raise Exception("Record id cannot be None")
    
    # JSONB 字段：接受 dict 或 JSON 字符串，统一转为 dict 存储
    thinking_data = thinking_process
    if isinstance(thinking_data, str):
        try:
            import json as _json
            thinking_data = _json.loads(thinking_data)
        except Exception:
            thinking_data = None
    
    stmt = update(ChatRecord).where(and_(ChatRecord.id == record_id)).values(
        thinking_process=thinking_data
    )
    
    session.execute(stmt)
    session.commit()
    
    # 同步持久化到 think_process 表
    if thinking_process:
        try:
            import json as _json
            from apps.datasource.models.document import ThinkProcess
            from datetime import datetime
            
            thinking_data = _json.loads(thinking_process) if isinstance(thinking_process, str) else thinking_process
            
            # 获取 chat_id 和 user_id
            record = get_chat_record_by_id(session, record_id)
            chat_id = record.chat_id if record else None
            # ChatRecord 没有 user_id 字段，应使用 create_by
            user_id = record.create_by if record else None
            
            # 计算总耗时
            total_time_ms = None
            stages = thinking_data.get('stages', {})
            if isinstance(stages, dict):
                total_time_ms = sum(s.get('duration', 0) for s in stages.values() if isinstance(s, dict))
            elif isinstance(stages, list):
                total_time_ms = sum(s.get('duration', 0) for s in stages if isinstance(s, dict))
            
            # 先查询是否已存在该record_id的记录，存在则更新，避免重复插入
            existing_tp = session.query(ThinkProcess).filter(
                ThinkProcess.record_id == record_id
            ).first()
            
            if existing_tp:
                existing_tp.stages = thinking_data.get('stages') if isinstance(thinking_data, dict) else thinking_data
                existing_tp.summary = thinking_data.get('summary', '')
                existing_tp.total_time_ms = total_time_ms
            else:
                tp = ThinkProcess(
                    record_id=record_id,
                    chat_id=chat_id,
                    user_id=user_id,
                    stages=thinking_data.get('stages') if isinstance(thinking_data, dict) else thinking_data,
                    summary=thinking_data.get('summary', ''),
                    total_time_ms=total_time_ms,
                    create_time=datetime.now(),
                )
                session.add(tp)
            session.commit()
        except Exception as e:
            from common.utils.utils import ChatBILogUtil
            ChatBILogUtil.warning(f"持久化思考过程到think_process表失败: {e}")
    
    record = get_chat_record_by_id(session, record_id)
    return record


def save_intent(session: SessionDep, record_id: int, intent: str) -> None:
    """Save detected intent to chat record"""
    if not record_id:
        return
    stmt = update(ChatRecord).where(and_(ChatRecord.id == record_id)).values(intent=intent)
    session.execute(stmt)
    session.commit()


def list_chat_records_for_dialogue(session: SessionDep, chat_id: int, max_turns: int = 10) -> List[dict]:
    """获取对话历史记录用于对话状态追踪器初始化"""
    if not chat_id:
        return []
    
    try:
        stmt = select(
            ChatRecord.question,
            ChatRecord.sql,
            ChatRecord.error,
            ChatRecord.intent
        ).where(
            and_(
                ChatRecord.chat_id == chat_id,
                ChatRecord.question.isnot(None),
                ChatRecord.question != ''
            )
        ).order_by(ChatRecord.create_time.desc()).limit(max_turns)
        
        results = session.execute(stmt).fetchall()
        
        # 反转顺序（从旧到新）
        records = []
        for r in reversed(results):
            records.append({
                'question': r.question or '',
                'sql': r.sql or '',
                'sql_success': r.error is None,
                'intent': r.intent or ''
            })
        
        return records
    except Exception as e:
        ChatBILogUtil.error(f"Failed to list chat records for dialogue: {e}")
        return []
