"""数据分析服务 - 从llm.py中提取的数据分析相关逻辑"""
import re
import time
from datetime import datetime
from typing import Any, List, Union

import orjson
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from sqlmodel import Session

from apps.chat.crud.chat import (
    start_log, end_log, save_analysis_answer, get_chat_chart_data, get_chart_config
)
from apps.chat.models.chat_model import OperationEnum
from apps.chat.thinking.rag_thinking import record_data_analysis
from apps.chat.thinking.query_rewriter import QueryRewriter
from apps.chat.thinking.context_compressor import ContextCompressor  # noqa: F401 - 保留以兼容旧代码引用
from apps.datasource.models.datasource import CoreDatasource
from apps.chat.thinking.rag_evidence_filter import filter_rag_evidence  # noqa: F401
from common.chatbi.custom_prompt import find_custom_prompts, find_relevant_custom_prompts, count_custom_prompts, CustomPromptTypeEnum
from common.chatbi.license import ChatBILicenseUtil
from common.utils.utils import ChatBILogUtil


class AnalysisServiceMixin:
    """数据分析相关方法的Mixin类

    通过多继承注入到LLMService中，将数据分析逻辑从主类中分离。
    所有方法通过self访问LLMService的状态。
    """

    @staticmethod
    def _aggregate_chart_data(data_content: list, chart_config: dict) -> list:
        """图表数据聚合：对同一分类的多行数据进行求和合并。"""
        if not chart_config:
            return data_content
        chart_type = chart_config.get('type', '')
        # table 展示原始明细，不聚合
        if chart_type not in ('pie', 'column', 'bar', 'line', 'area'):
            return data_content
        if not data_content or not isinstance(data_content, list) or len(data_content) == 0:
            return data_content

        axis = chart_config.get('axis') or {}

        # 确定分组键：饼图用 series 或 x，其他图表用 x（主维度轴）
        if chart_type == 'pie':
            group_field = (axis.get('series') or {}).get('value') or (axis.get('x') or {}).get('value')
        else:
            group_field = (axis.get('x') or {}).get('value')

        y_field = (axis.get('y') or {}).get('value')
        series_field = (axis.get('series') or {}).get('value')

        if not group_field or not y_field:
            return data_content

        # 构建复合分组键：x + series（如果有 series 且不同于 group_field）
        use_series = series_field and series_field != group_field

        def _to_num(v) -> float:
            if isinstance(v, (int, float)):
                return float(v)
            if isinstance(v, str):
                stripped = v.strip().rstrip('%')
                try:
                    return float(stripped)
                except (ValueError, TypeError):
                    return 0.0
            return 0.0

        # 检测原始数据是否带 % 后缀
        first_val = next((r[y_field] for r in data_content if r.get(y_field) is not None), None)
        has_percent = isinstance(first_val, str) and first_val.strip().endswith('%')

        aggregated: dict[str, dict] = {}
        for row in data_content:
            key_parts = [str(row.get(group_field, ''))]
            if use_series:
                key_parts.append(str(row.get(series_field, '')))
            key = '||'.join(key_parts)

            if key in aggregated:
                existing_val = _to_num(aggregated[key][y_field])
                new_val = _to_num(row[y_field])
                total = round(existing_val + new_val, 2)
                aggregated[key][y_field] = f'{total}%' if has_percent else total
            else:
                aggregated[key] = dict(row)

        return list(aggregated.values())

    @staticmethod
    def _annotate_data_quality(data_content: list, fields: list, lang: str = '') -> str:
        """检测数据质量问题并生成标注信息。"""
        if not data_content or not isinstance(data_content, list):
            _is_en_dq = (lang or '').lower().startswith('en')
            _empty_msg = "⚠️ Data is empty, unable to perform effective analysis. Please check the datasource or adjust query conditions." if _is_en_dq else "⚠️ 数据为空，无法进行有效分析。请检查数据源或调整查询条件。"
            return f"<data-quality>\n{_empty_msg}\n</data-quality>"

        annotations: list[str] = []
        total_rows = len(data_content)
        _is_en_dq = (lang or '').lower().startswith('en')

        # --- 1. 空值/缺失值检测 ---
        null_stats: dict[str, int] = {}
        for row in data_content:
            if not isinstance(row, dict):
                continue
            for key, val in row.items():
                if val is None or val == '' or val == 'null' or val == 'None':
                    null_stats[key] = null_stats.get(key, 0) + 1

        if null_stats:
            if _is_en_dq:
                parts = [f'Column "{col}" has {cnt}/{total_rows} null rows' for col, cnt in null_stats.items()]
                annotations.append("Missing values: " + "; ".join(parts))
            else:
                parts = [f"「{col}」列有 {cnt}/{total_rows} 行为空" for col, cnt in null_stats.items()]
                annotations.append("缺失值: " + "；".join(parts))

        # --- 2. 数值列异常值检测（IQR 方法） ---
        numeric_cols: dict[str, list[float]] = {}
        for row in data_content:
            if not isinstance(row, dict):
                continue
            for key, val in row.items():
                if val is None or val == '' or val == 'null':
                    continue
                try:
                    numeric_cols.setdefault(key, []).append(float(val))
                except (ValueError, TypeError):
                    pass

        outlier_notes: list[str] = []
        for col, values in numeric_cols.items():
            # IQR方法在小样本下不可靠，提高最低样本量到20
            if len(values) < 20:
                continue
            sorted_vals = sorted(values)
            n = len(sorted_vals)
            q1 = sorted_vals[n // 4]
            q3 = sorted_vals[(3 * n) // 4]
            iqr = q3 - q1
            if iqr <= 0:
                continue
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            outliers = [v for v in values if v < lower_bound or v > upper_bound]
            if outliers:
                if _is_en_dq:
                    outlier_notes.append(
                        f'Column "{col}" has {len(outliers)} outliers'
                        f' (normal range [{lower_bound:.2f}, {upper_bound:.2f}])'
                    )
                else:
                    outlier_notes.append(
                        f"「{col}」列检测到 {len(outliers)} 个异常值"
                        f"（正常范围 [{lower_bound:.2f}, {upper_bound:.2f}]）"
                    )

        if outlier_notes:
            if _is_en_dq:
                annotations.append("Outliers: " + "; ".join(outlier_notes))
            else:
                annotations.append("异常值: " + "；".join(outlier_notes))

        if not annotations:
            return ""

        if _is_en_dq:
            header = f"⚠️ Data quality notice ({total_rows} rows):"
            body = "\n".join(f"  - {a}" for a in annotations)
            return f"<data-quality>\n{header}\n{body}\nPlease note the above data quality issues in the analysis report to alert users about data reliability.\n</data-quality>"
        else:
            header = f"⚠️ 数据质量提示（共 {total_rows} 行数据）："
            body = "\n".join(f"  - {a}" for a in annotations)
            return f"<data-quality>\n{header}\n{body}\n请在分析报告中标注上述数据质量问题，提醒用户注意数据可靠性。\n</data-quality>"

    def _build_brief_analysis_system_prompt(self):
        """ 性能优化：data_query 延迟分析使用的精简系统提示词。
        生成结构化的数据洞察报告，包含核心发现、趋势分析和业务建议。
        相比完整分析模板更精简，但仍提供有价值的分析内容。"""
        lang = self.chat_question.lang or '简体中文'
        return (
            f"你是专业的数据分析助手。根据用户的查询和数据，用{lang}生成结构化的数据分析报告。\n"
            f"规则：\n"
            f"- 用 markdown 格式组织内容，包含标题和分段\n"
            f"- 报告结构：\n"
            f"  1. 一个简短的总结标题\n"
            f"  2. **核心发现**：列出 2-3 个关键数据洞察，引用具体数值\n"
            f"  3. **数据分析**：对数据分布、趋势、对比进行分析（如最大值、最小值、占比、增长率等）\n"
            f"  4. **业务建议**：基于数据给出 1-2 条可操作的建议\n"
            f"- 引用关键数值时必须使用数据中的原始值，严禁编造数据\n"
            f"- 不要重复列出原始数据表格\n"
            f"- 不要输出<think>标签\n"
            f"- 专业、有洞察力，避免空泛描述\n"
        )

    def _build_brief_analysis_user_prompt(self):
        """ 性能优化：data_query 延迟分析使用的精简用户提示词。"""
        lang = self.chat_question.lang or '简体中文'
        return (
            f"问题：{self.chat_question.question}\n"
            f"字段：{self.chat_question.fields}\n"
            f"数据：{self.chat_question.data}\n"
            f"请用{lang}输出数据分析报告（包含核心发现、数据分析、业务建议）："
        )

    def generate_analysis(self, _session: Session, skip_rag: bool = False, brief_mode: bool = False, skip_custom_prompt: bool = False):
        # RAG增强的数据分析：检索术语库和文档库，增强LLM对业务的理解
        rag_enabled = not skip_rag
        
        # PDF数据源不支持数据分析，在入口处显式拦截
        _ds_type_guard = (self.ds.type or '').lower() if self.ds else ''
        if _ds_type_guard == 'pdf':
            ChatBILogUtil.info("[generate_analysis] PDF datasource does not support data analysis, returning early")
            _is_en_pdf_guard = (self.chat_question.lang or '').lower().startswith('en')
            pdf_msg = ("PDF documents do not support data analysis. PDF is an unstructured document type that only supports "
                       "document Q&A (content comprehension, knowledge Q&A, summarization). "
                       "Please use the chat function to ask questions about the document content.") if _is_en_pdf_guard else \
                      "PDF文档不支持数据分析功能。PDF属于非结构化文档类型，仅支持文档问答（内容理解、知识问答、内容总结）。" \
                      "请使用对话功能向文档内容提问。"
            yield {'content': pdf_msg, 'reasoning_content': ''}
            try:
                # 使用模块级别已导入的 save_analysis_answer（第22行），不再局部 import
                # 调用 save_analysis_answer 时抛出 UnboundLocalError
                save_analysis_answer(session=_session, record_id=self.record.id,
                                     answer=orjson.dumps({'content': pdf_msg, 'reasoning_content': ''}).decode())
            except Exception:
                pass
            return
        
        # 从原始记录（analysis_record_id）获取 chart 和 data
        base_record_id = self.record.analysis_record_id if self.record.analysis_record_id else self.record.id
        
        fields = self.get_fields_from_chart(_session, base_record_id)
        self.chat_question.fields = orjson.dumps(fields).decode()
        data = get_chat_chart_data(_session, base_record_id)
        # data.get('data')可能返回None，导致LLM收到<data>null</data>
        _data_content = data.get('data') if data.get('data') is not None else []
        
        # 图表数据聚合 - 对同一分类的多行数据求和合并后再传给LLM
        _chart_config = get_chart_config(_session, base_record_id)
        _data_content = self._aggregate_chart_data(_data_content, _chart_config)
        
        # 空数据或稀疏数据提前拦截
        # 当数据为空时，不调用LLM（浪费token且结果无意义），直接返回提示
        if not _data_content or (isinstance(_data_content, list) and len(_data_content) == 0):
            ChatBILogUtil.info("[generate_analysis] Empty data, skipping LLM call")
            _is_en_empty = (self.chat_question.lang or '').lower().startswith('en')
            empty_msg = ("The current query result is empty, unable to perform effective data analysis. "
                         "Please check the datasource or adjust query conditions and try again.") if _is_en_empty else \
                        "当前查询结果为空，无法进行有效的数据分析。请检查数据源或调整查询条件后重试。"
            yield {'content': empty_msg, 'reasoning_content': ''}
            try:
                save_analysis_answer(session=_session, record_id=self.record.id,
                                     answer=orjson.dumps({'content': empty_msg, 'reasoning_content': ''}).decode())
            except Exception:
                pass
            return
        
        # 限制注入LLM的数据行数，防止prompt过长导致模型返回空响应
        _MAX_DATA_ROWS_FOR_LLM = 200
        _data_for_llm = _data_content
        _data_truncated = False
        if isinstance(_data_content, list) and len(_data_content) > _MAX_DATA_ROWS_FOR_LLM:
            _data_for_llm = _data_content[:_MAX_DATA_ROWS_FOR_LLM]
            _data_truncated = True
            ChatBILogUtil.warning(
                f"[generate_analysis] Data truncated for LLM: {len(_data_content)} -> {_MAX_DATA_ROWS_FOR_LLM} rows "
                f"(original JSON ~{len(orjson.dumps(_data_content).decode())} chars)"
            )
        # 二次防护：即使行数在限制内，JSON字符数也不能超过模型安全阈值
        _MAX_DATA_CHARS_FOR_LLM = 40000  # ~20K tokens，为system prompt和模型输出留足空间
        _data_json = orjson.dumps(_data_for_llm).decode()
        if len(_data_json) > _MAX_DATA_CHARS_FOR_LLM:
            # 按比例缩减行数
            _ratio = _MAX_DATA_CHARS_FOR_LLM / len(_data_json)
            _reduced_rows = max(10, int(len(_data_for_llm) * _ratio * 0.9))  # 留10%余量
            _data_for_llm = _data_for_llm[:_reduced_rows]
            _data_json = orjson.dumps(_data_for_llm).decode()
            _data_truncated = True
            ChatBILogUtil.warning(
                f"[generate_analysis] Data further truncated by char limit: -> {_reduced_rows} rows, "
                f"{len(_data_json)} chars"
            )
        self.chat_question.data = _data_json
        analysis_msg: List[Union[BaseMessage, dict[str, Any]]] = []

        ds_id = self.ds.id if isinstance(self.ds, CoreDatasource) else None
        oid = self.current_user.oid if self.current_user.oid is not None else 1
        
        # 查询重写：优化用户查询以提升RAG检索质量
        # skip_rag=True 时复用 run_task 已缓存的重写结果，避免重复调用
        _ds_type_for_rewrite = self.ds.type if self.ds else 'database'
        if skip_rag and hasattr(self, '_rewrite_result') and self._rewrite_result:
            rewrite_result = self._rewrite_result
        else:
            rewrite_result = QueryRewriter.rewrite(self.chat_question.question, ds_type=_ds_type_for_rewrite)
        retrieval_question = rewrite_result['rewritten']
        if rewrite_result['rewrite_applied']:
            ChatBILogUtil.info(f"[generate_analysis] Query rewritten: '{self.chat_question.question}' -> '{retrieval_question}'")
        
        # 记录查询理解阶段到思考过程
        try:
            if 'query_understanding' not in self.thinking_process.stages:
                from apps.chat.thinking.thinking_integration import record_query_understanding_stage
                dialogue_turn = len(self.dialogue_tracker.turns) if hasattr(self, 'dialogue_tracker') and self.dialogue_tracker else 1
                context_refs = []
                if hasattr(self, 'dialogue_tracker') and self.dialogue_tracker:
                    state = self.dialogue_tracker.get_state_summary()
                    context_refs = state.get('context_references', [])
                record_query_understanding_stage(
                    self.thinking_process,
                    original_query=self.chat_question.question,
                    rewritten_query=retrieval_question,
                    intent=rewrite_result.get('intent', 'analysis'),
                    rewrite_applied=rewrite_result['rewrite_applied'],
                    extracted_keywords=rewrite_result.get('extracted_keywords', []),
                    dialogue_turn=dialogue_turn,
                    context_references=context_refs,
                    intent_keywords=rewrite_result.get('intent_keywords', []),
                )
                qu_stage_data = self.thinking_process.get_stage('query_understanding')
                if qu_stage_data:
                    yield {'type': 'thinking_stage', 'stage': 'query_understanding', 'data': qu_stage_data}
        except Exception as e:
            ChatBILogUtil.error(f"[generate_analysis] Failed to record query understanding stage: {e}")
        
        # RAG检索，让术语和文档知识增强数据分析
        rag_start_time = time.time()
        terminology_count = 0
        _analysis_terminology_details = []
        
        if rag_enabled:
            # 使用共享RAG流水线，消除与prediction_service的重复代码
            _rag_result = self._execute_rag_for_task(
                _session, retrieval_question, rewrite_result, oid, ds_id,
                scenario='analysis',
            )
            _analysis_terminology_details = _rag_result['terminology_details']
            terminology_count = _rag_result['terminology_count']
            retrieval_question = _rag_result['retrieval_question']
            rag_retrieval_time = _rag_result['rag_retrieval_time']
            # doc_chunks 已由 _execute_rag_for_task 缓存到 self._rag_doc_chunks
        else:
            rag_retrieval_time = 0.0
        
        if self.chat_question.terminologies:
            terminology_count = self.chat_question.terminologies.count('<terminology>')
        
        # 记录对话轮次到对话状态追踪器
        try:
            _current_record_id = self.record.id if self.record else None
            already_tracked = any(
                getattr(t, 'record_id', None) == _current_record_id
                for t in self.dialogue_tracker.turns
            ) if _current_record_id else any(
                t.question == self.chat_question.question for t in self.dialogue_tracker.turns
            )
            if not already_tracked:
                self.dialogue_tracker.track_turn(
                    question=self.chat_question.question,
                    record_id=_current_record_id
                )
        except Exception as e:
            ChatBILogUtil.error(f"[generate_analysis] Dialogue tracking failed: {e}")
        
        # 多路检索、质量过滤、模板构建、术语扩展已移至 _execute_rag_for_task()
        try:
            if 'rag_retrieval' not in self.thinking_process.stages:
                from apps.chat.thinking.rag_thinking import record_rag_retrieval
                _an_ds_type = (self.ds.type or 'database').lower() if self.ds else 'database'
                record_rag_retrieval(
                    self.thinking_process,
                    question=self.chat_question.question,
                    terminologies=_analysis_terminology_details,
                    retrieval_time=rag_retrieval_time,
                    ds_type=_an_ds_type,
                    intent='analysis',
                )
            rag_stage_data = self.thinking_process.get_stage('rag_retrieval')
            if rag_stage_data:
                yield {'type': 'thinking_stage', 'stage': 'rag_retrieval', 'data': rag_stage_data}
        except Exception as e:
            ChatBILogUtil.error(f"[generate_analysis] Failed to yield rag_retrieval stage: {e}")
        
        # 缺陷2修复：发送上下文压缩阶段到前端（_execute_rag_for_task 内部已记录，此处 yield）
        # 仅在独立执行时（rag_enabled=True）yield，内联执行时 run_task 已发送
        try:
            if rag_enabled:
                cc_stage_data = self.thinking_process.get_stage('context_compression')
                if cc_stage_data:
                    yield {'type': 'thinking_stage', 'stage': 'context_compression', 'data': cc_stage_data}
        except Exception as e:
            ChatBILogUtil.error(f"[generate_analysis] Failed to yield context_compression stage: {e}")
        
        # 获取自定义提示词（智能匹配）
        # 注入 ANALYSIS 提示词（分析场景）
        custom_prompt_content = ''
        custom_prompt_used = False
        custom_prompts_list = []
        _question = self.chat_question.question or ''
        if ChatBILicenseUtil.valid():
            if not skip_custom_prompt:
                # 常规分析场景：注入 ANALYSIS 类型提示词
                _total = count_custom_prompts(_session, CustomPromptTypeEnum.ANALYSIS, oid, ds_id)
                custom_prompt_content, _details = find_relevant_custom_prompts(
                    _session, CustomPromptTypeEnum.ANALYSIS, oid, _question, ds_id)
                self.chat_question.custom_prompt = custom_prompt_content
                _matched_count = len([d for d in _details if d.get('reason') != 'not_matched'])
                custom_prompt_used = _matched_count > 0

                _is_en_cp = (self.chat_question.lang or '').lower().startswith('en')
                custom_prompts_list.append({
                    'type': 'Data Analysis' if _is_en_cp else '数据分析',
                    'content': custom_prompt_content[:200] + '...' if custom_prompt_content and len(custom_prompt_content) > 200 else (custom_prompt_content or ''),
                    'used': custom_prompt_used,
                    'empty': _total == 0,
                    'count': _matched_count,
                    'total': _total,
                    'matched': _details
                })
            
        analysis_msg.append(SystemMessage(content=self.chat_question.analysis_sys_question(
            ds_type=self.ds.type if self.ds else 'database'
        ) if not brief_mode else self._build_brief_analysis_system_prompt()))
        
        # 审计[14.1]：注入数据质量标注（异常值、空数据），满足需求 3.4
        if not brief_mode:
            try:
                _fields_list = orjson.loads(self.chat_question.fields) if self.chat_question.fields else []
                quality_annotation = self._annotate_data_quality(_data_content, _fields_list, lang=self.chat_question.lang)
                if quality_annotation:
                    analysis_msg.append(SystemMessage(content=quality_annotation))
                    ChatBILogUtil.info(f"[generate_analysis] Data quality annotation injected")
            except Exception as e:
                ChatBILogUtil.error(f"[generate_analysis] Data quality annotation failed: {e}")
        
        # 注入多轮对话上下文到数据分析路径
        try:
            if not brief_mode and self.dialogue_tracker and self.dialogue_tracker.turns:
                dialogue_ctx = self.dialogue_tracker.get_dialogue_context(max_turns=3)
                if dialogue_ctx.get('total_turns', 0) > 0:
                    ctx_parts = []
                    _is_en_ctx = (self.chat_question.lang or '').lower().startswith('en')
                    if dialogue_ctx.get('current_topic'):
                        ctx_parts.append(f"{'Current topic' if _is_en_ctx else '当前话题'}: {dialogue_ctx['current_topic']}")
                    if dialogue_ctx.get('active_entities'):
                        ctx_parts.append(f"{'Active entities' if _is_en_ctx else '活跃实体'}: {', '.join(dialogue_ctx['active_entities'][:5])}")
                    recent_qs = dialogue_ctx.get('recent_questions', [])
                    if len(recent_qs) > 1:
                        ctx_parts.append(f"{'Recent questions' if _is_en_ctx else '近期问题'}: {'; '.join(recent_qs[-3:])}")
                    # 注入上下文引用解析结果
                    ctx_refs = dialogue_ctx.get('context_references', [])
                    if ctx_refs:
                        ref_hints = [f"{r['type']}: {r['resolved']}" for r in ctx_refs if r.get('resolved')]
                        if ref_hints:
                            ctx_parts.append(f"{'Context references' if _is_en_ctx else '上下文引用'}: {'; '.join(ref_hints)}")
                    if ctx_parts:
                        dialogue_hint = '\n'.join(ctx_parts)
                        analysis_msg.append(SystemMessage(
                            content=f"<dialogue-context>\n{dialogue_hint}\n</dialogue-context>"
                        ))
        except Exception as e:
            ChatBILogUtil.error(f"Failed to inject dialogue context into analysis: {e}")
        
        _user_content = self.chat_question.analysis_user_question() \
            if not brief_mode else self._build_brief_analysis_user_prompt()
        # 如果数据被截断，在user prompt中告知LLM，避免它对数据完整性做错误假设
        if _data_truncated:
            _is_en_trunc = (self.chat_question.lang or '').lower().startswith('en')
            _trunc_notice = (f"\n\n⚠️ Note: The data above shows only the first {len(_data_for_llm)} rows "
                             f"out of {len(_data_content)} total rows. "
                             f"Please base your analysis on the available data and note that it is a subset."
                             if _is_en_trunc else
                             f"\n\n⚠️ 注意：以上数据仅展示了全部{len(_data_content)}行中的前{len(_data_for_llm)}行。"
                             f"请基于已提供的数据进行分析，并注明这是部分数据的分析结果。")
            _user_content += _trunc_notice
        analysis_msg.append(HumanMessage(content=_user_content))

        # 记录提示词构建阶段（分析路径）— 通过 PromptBuilder 记录
        if not skip_rag:
            try:
                from apps.chat.thinking.prompt_builder import PromptBuilder
                analysis_builder = PromptBuilder(
                    prompt_type='analysis',
                    model_name=self.chat_question.ai_modal_name or ''
                )
                analysis_builder.set_rag_knowledge(
                    terminologies_xml=self.chat_question.terminologies,
                    sql_examples_xml=self.chat_question.data_training,
                    raw_terminology_count=getattr(self.chat_question, 'raw_terminology_count', 0),
                )
                analysis_builder.set_custom_prompts(
                    self.chat_question.custom_prompt,
                    custom_prompts_list,
                )
                analysis_builder.set_dialogue_context(
                    getattr(self, 'dialogue_tracker', None),
                    lang=self.chat_question.lang,
                )

                _sys_prompt_analysis = analysis_msg[0].content if analysis_msg else ''
                _user_prompt_analysis = analysis_msg[-1].content if analysis_msg else ''
                _analysis_metadata = analysis_builder._build_metadata(_sys_prompt_analysis, _user_prompt_analysis)
                _analysis_metadata.message_count = len(analysis_msg)
                _sys_total_analysis = sum(
                    len(m.content) for m in analysis_msg
                    if isinstance(m, SystemMessage))
                _analysis_metadata.system_prompt_length = _sys_total_analysis
                _analysis_metadata.total_prompt_length = _sys_total_analysis + len(_user_prompt_analysis)
                analysis_builder.record_to_thinking(self.thinking_process, _analysis_metadata)

                _pc_stage = self.thinking_process.get_stage('prompt_construction')
                if _pc_stage:
                    yield {'type': 'thinking_stage', 'stage': 'prompt_construction', 'data': _pc_stage}
            except Exception:
                pass

        self.current_logs[OperationEnum.ANALYSIS] = start_log(session=_session,
                                                              ai_modal_id=self.chat_question.ai_modal_id,
                                                              ai_modal_name=self.chat_question.ai_modal_name,
                                                              operate=OperationEnum.ANALYSIS,
                                                              record_id=self.record.id,
                                                              full_message=[
                                                                  {'type': msg.type,
                                                                   'content': msg.content,
                                                                   'custom_prompt_used': custom_prompt_used} for
                                                                  msg
                                                                  in analysis_msg])
        
        # 发送分析阶段的RAG检索结果到前端
        try:
            if skip_rag:
                # 内联执行：只发送自定义提示词匹配结果（前端需要展示）
                rag_results_data = {
                    'terminologies': [],
                    'sql_examples': [],
                    'custom_prompts': custom_prompts_list,
                    'rag_enabled': True,
                    'custom_prompt_checked': bool(custom_prompts_list),
                }
            else:
                from apps.chat.thinking.rag_thinking import RAGQualityMetrics
                terminology_results_analysis = []
                if _analysis_terminology_details:
                    for t in _analysis_terminology_details[:5]:
                        terminology_results_analysis.append({
                            'word': t.get('word', ''),
                            'description': t.get('description', ''),
                            'similarity': t.get('similarity', 0),
                            'match_type': t.get('match_type', 'vector'),
                            'used': True
                        })
                elif terminology_count > 0:
                    _is_en_term = (self.chat_question.lang or '').lower().startswith('en')
                    terminology_results_analysis.append({
                        'word': f'Terminology ({terminology_count} items)' if _is_en_term else f'术语库({terminology_count}条)',
                        'description': 'Injected into analysis prompt' if _is_en_term else '已注入到分析提示词中',
                        'similarity': 0.8,
                        'match_type': 'vector',
                        'used': True
                    })
                _cached_doc_chunks = getattr(self, '_rag_doc_chunks', None) or []
                _ds_type_for_impact = (self.ds.type or 'database').lower() if self.ds else 'database'
                rag_impact = RAGQualityMetrics.calculate_rag_impact(
                    True,
                    terminology_results_analysis,
                    [],
                    doc_chunks=_cached_doc_chunks,
                    ds_type=_ds_type_for_impact,
                    intent='analysis',
                )
                terminology_quality = RAGQualityMetrics.calculate_retrieval_quality(terminology_results_analysis) if terminology_results_analysis else {}
                rag_results_data = {
                    'terminologies': terminology_results_analysis,
                    'sql_examples': [],
                    'custom_prompts': custom_prompts_list,
                    'rag_enabled': True,
                    'custom_prompt_checked': bool(custom_prompts_list),
                    'rag_impact': rag_impact,
                    'terminology_quality': terminology_quality,
                    'example_quality': {},
                    'document_chunks': [
                        {
                            'text': dc.get('text', '')[:300],
                            'source_name': dc.get('source_name', ''),
                            'similarity': dc.get('similarity', 0),
                            'page_number': dc.get('page_number'),
                            'section_title': dc.get('section_title', ''),
                        }
                        for dc in (_cached_doc_chunks or [])[:5]
                    ],
                }
                # 持久化RAG结果到数据库
                try:
                    from apps.chat.crud.chat import save_rag_results
                    save_rag_results(
                        session=_session,
                        record_id=self.record.id,
                        rag_enabled=True,
                        rag_results=orjson.dumps(rag_results_data).decode()
                    )
                except Exception as e:
                    ChatBILogUtil.error(f"[generate_analysis] Failed to save RAG results: {e}")
            yield {'type': 'rag_results', 'data': rag_results_data}
        except Exception as e:
            ChatBILogUtil.error(f"[generate_analysis] Failed to send RAG results: {e}")
        
        full_thinking_text = ''
        full_analysis_text = ''
        token_usage = {}
        
        # 记录LLM调用开始时间
        llm_start_time = time.time()
        
        # 先发送 loading 状态，让前端立即展示"生成中"
        yield {
            'type': 'thinking_stage', 'stage': 'data_analysis',
            'data': {
                'stage': 'data_analysis',
                'status': 'loading',
                'timestamp': datetime.now().isoformat(),
                'streaming_reasoning': '',
            }
        }
        
        from apps.chat.task.llm import process_stream, stream_with_retry
        
        # 用于控制流式推理内容的发送频率
        _reasoning_update_counter = 0
        _REASONING_UPDATE_INTERVAL = 3
        
        # 空响应自动重试（最多重试2次）
        _max_empty_retries = 2
        _original_user_msg = analysis_msg[-1].content if analysis_msg else ''
        for _empty_attempt in range(_max_empty_retries + 1):
            full_thinking_text = ''
            full_analysis_text = ''
            _reasoning_update_counter = 0
            
            res = process_stream(stream_with_retry(self.llm, analysis_msg), token_usage)
            for chunk in res:
                # 安全处理：确保content不为None
                content = chunk.get('content')
                if content:
                    full_analysis_text += content
                reasoning_content = chunk.get('reasoning_content')
                if reasoning_content:
                    full_thinking_text += reasoning_content
                    _reasoning_update_counter += 1
                    if _reasoning_update_counter % _REASONING_UPDATE_INTERVAL == 0:
                        yield {
                            'type': 'thinking_stage', 'stage': 'data_analysis',
                            'data': {
                                'stage': 'data_analysis',
                                'status': 'loading',
                                'timestamp': datetime.now().isoformat(),
                                'streaming_reasoning': full_thinking_text,
                            }
                        }
                yield chunk
            
            # 如果有内容（包括仅有推理内容），跳出重试循环
            if (full_analysis_text and full_analysis_text.strip()) or (full_thinking_text and full_thinking_text.strip()):
                break
            
            # 完全空响应：判断是否需要重试
            if _empty_attempt < _max_empty_retries:
                _wait_time = 1.0 * (2 ** _empty_attempt)  # 指数退避：1s, 2s
                ChatBILogUtil.warning(
                    f"[generate_analysis] LLM returned empty content (attempt {_empty_attempt + 1}/{_max_empty_retries + 1}), "
                    f"retrying in {_wait_time:.0f}s... Model: {self.chat_question.ai_modal_name}, "
                    f"Token usage: {token_usage}"
                )
                # 重试时修改 user message，追加重试提示打破空响应模式
                _is_en_retry = (self.chat_question.lang or '').lower().startswith('en')
                _retry_hint = (f"\n\n(Retry attempt {_empty_attempt + 2}: Please generate the analysis report now.)"
                               if _is_en_retry else
                               f"\n\n（第{_empty_attempt + 2}次请求：请立即生成数据分析报告。）")
                analysis_msg[-1] = HumanMessage(content=_original_user_msg + _retry_hint)
                time.sleep(_wait_time)

        # 安全兜底：如果LLM只输出了推理内容但没有最终回答
        if not full_analysis_text.strip() and full_thinking_text.strip():
            ChatBILogUtil.info("[generate_analysis] LLM returned only reasoning content, using it as analysis")
            full_analysis_text = full_thinking_text
            yield {'content': full_analysis_text, 'reasoning_content': ''}
        elif not full_analysis_text.strip():
            ChatBILogUtil.error(
                f"[generate_analysis] LLM returned empty response after {_max_empty_retries + 1} attempts. "
                f"Model: {self.chat_question.ai_modal_name}, Token usage: {token_usage}"
            )
            _is_en_empty2 = (self.chat_question.lang or '').lower().startswith('en')
            full_analysis_text = ("Sorry, the system failed to generate valid data analysis results. "
                                  "Please try rephrasing your question.\n"
                                  "💡 Tip: Try simplifying your question, or check if the datasource contains the relevant tables and fields.") if _is_en_empty2 else \
                                 ("抱歉，系统未能生成有效的数据分析结果，请尝试重新提问或换一种表述方式。\n"
                                  "💡 建议：尝试简化您的问题，或检查数据源中是否包含相关的数据表和字段。")
            yield {'content': full_analysis_text, 'reasoning_content': ''}

        analysis_msg.append(AIMessage(full_analysis_text))

        self.current_logs[OperationEnum.ANALYSIS] = end_log(session=_session,
                                                            log=self.current_logs[
                                                                OperationEnum.ANALYSIS],
                                                            full_message=[
                                                                {'type': msg.type,
                                                                 'content': msg.content}
                                                                for msg in analysis_msg],
                                                            reasoning_content=full_thinking_text,
                                                            token_usage=token_usage)
        self.record = save_analysis_answer(session=_session, record_id=self.record.id,
                                           answer=orjson.dumps({'content': full_analysis_text, 'reasoning_content': full_thinking_text}).decode())
        
        # 计算分析生成耗时（使用实际的LLM调用时间）
        analysis_generation_time = time.time() - llm_start_time
        
        # 记录数据分析阶段到思考过程
        try:
            # 构建RAG上下文信息
            rag_context = {
                "terminologies_used": terminology_count,
                "custom_prompt_used": custom_prompt_used,
                "rag_retrieval_time": round(rag_retrieval_time, 3),
                "data_fields": len(fields),
                "data_rows": len(_data_content) if isinstance(_data_content, list) else 0
            }
            
            record_data_analysis(
                self.thinking_process,
                analysis=full_analysis_text[:1000],
                reasoning=full_thinking_text[:500],
                rag_context=rag_context,
                generation_time=analysis_generation_time,
                token_usage=token_usage
            )
            
            # 发送分析思考过程
            analysis_stage_data = self.thinking_process.get_stage('data_analysis')
            if analysis_stage_data:
                yield {'type': 'thinking_stage', 'stage': 'data_analysis', 'data': analysis_stage_data}
            
            # 记录溯源凭证（分析路径）
            try:
                _existing_prov = self.thinking_process.get_stage('provenance')
                if _existing_prov and _existing_prov.get('extra_data', {}).get('records'):
                    # 已有溯源凭证（来自SQL路径），合并分析元数据到第一条记录
                    _prov_stage_obj = self.thinking_process.stages.get('provenance')
                    if _prov_stage_obj and _prov_stage_obj.extra_data.get('records'):
                        _first_rec = _prov_stage_obj.extra_data['records'][0]
                        _first_rec.setdefault('data_fields', len(fields))
                        _first_rec.setdefault('data_rows', len(_data_content) if isinstance(_data_content, list) else 0)
                        _first_rec.setdefault('terminologies_used', terminology_count)
                        _first_rec.setdefault('custom_prompt_used', custom_prompt_used)
                else:
                    # 独立分析路径（无SQL前置），正常记录溯源凭证
                    from apps.chat.thinking.thinking_integration import record_provenance_stage
                    _an_provenance = []
                    _an_ds_type = (self.ds.type or '').lower() if self.ds else 'database'
                    _an_provenance.append({
                        'source_type': _an_ds_type if _an_ds_type in ('excel', 'csv', 'pdf') else 'database',
                        'source_name': self.ds.name if self.ds else '',
                        'data_fields': len(fields),
                        'data_rows': len(_data_content) if isinstance(_data_content, list) else 0,
                        'terminologies_used': terminology_count,
                        'custom_prompt_used': custom_prompt_used,
                        'update_time': str(self.ds.update_time) if self.ds and hasattr(self.ds, 'update_time') else '',
                    })
                    record_provenance_stage(self.thinking_process, _an_provenance)
                _an_prov_stage = self.thinking_process.get_stage('provenance')
                if _an_prov_stage:
                    yield {'type': 'thinking_stage', 'stage': 'provenance', 'data': _an_prov_stage}
            except Exception as prov_e:
                ChatBILogUtil.error(f"[generate_analysis] Failed to record provenance: {prov_e}")
        except Exception as e:
            ChatBILogUtil.error(f"Failed to record analysis thinking stage: {e}")
