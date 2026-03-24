"""数据预测服务 - 从llm.py中提取的数据预测相关逻辑"""
import math
import re
import statistics
import time
from datetime import datetime
from typing import Any, Dict, List, Union

import orjson
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from sqlmodel import Session

from apps.chat.crud.chat import (
    start_log, end_log, save_predict_answer, save_predict_data, get_chat_chart_data
)
from apps.chat.models.chat_model import OperationEnum
from apps.chat.thinking.rag_thinking import record_data_prediction
from apps.chat.thinking.query_rewriter import QueryRewriter
from apps.chat.thinking.context_compressor import ContextCompressor  # noqa: F401 - 保留以兼容旧代码引用
from apps.datasource.models.datasource import CoreDatasource
from apps.chat.thinking.rag_evidence_filter import filter_rag_evidence  # noqa: F401
from common.chatbi.custom_prompt import find_custom_prompts, find_relevant_custom_prompts, count_custom_prompts, CustomPromptTypeEnum
from common.chatbi.license import ChatBILicenseUtil
from common.utils.utils import ChatBILogUtil, extract_json_robust


class PredictionServiceMixin:
    """数据预测相关方法的Mixin类

    通过多继承注入到LLMService中，将数据预测逻辑从主类中分离。
    所有方法通过self访问LLMService的状态。
    """

    def generate_predict(self, _session: Session, skip_rag: bool = False):
        # RAG增强的数据预测：检索术语库和文档库，增强LLM对业务的理解
        # skip_rag=True: 内联执行时，RAG上下文已在run_task中设置，跳过重复检索
        rag_enabled = not skip_rag
        
        # PDF数据源不支持数据预测，在入口处显式拦截
        _ds_type_guard = (self.ds.type or '').lower() if self.ds else ''
        if _ds_type_guard == 'pdf':
            ChatBILogUtil.info("[generate_predict] PDF datasource does not support data prediction, returning early")
            _is_en_pdf_guard = (self.chat_question.lang or '').lower().startswith('en')
            pdf_msg = ("PDF documents do not support data prediction. PDF is an unstructured document type that only supports "
                       "document Q&A (content comprehension, knowledge Q&A, summarization). "
                       "Please use the chat function to ask questions about the document content.") if _is_en_pdf_guard else \
                      "PDF文档不支持数据预测功能。PDF属于非结构化文档类型，仅支持文档问答（内容理解、知识问答、内容总结）。" \
                      "请使用对话功能向文档内容提问。"
            yield {'content': pdf_msg, 'reasoning_content': ''}
            try:
                save_predict_answer(session=_session, record_id=self.record.id,
                                    answer=orjson.dumps({'content': pdf_msg, 'reasoning_content': ''}).decode())
            except Exception:
                pass
            return
        
        # 从原始记录（predict_record_id）获取 chart 和 data
        base_record_id = self.record.predict_record_id if self.record.predict_record_id else self.record.id
        
        fields = self.get_fields_from_chart(_session, base_record_id)
        self.chat_question.fields = orjson.dumps(fields).decode()
        data = get_chat_chart_data(_session, base_record_id)
        # data.get('data')可能返回None，导致LLM收到<data>null</data>
        _data_content = data.get('data') if data.get('data') is not None else []
        
        if not _data_content or (isinstance(_data_content, list) and len(_data_content) == 0):
            ChatBILogUtil.info("[generate_predict] Empty data, skipping LLM call")
            _is_en_empty_p = (self.chat_question.lang or '').lower().startswith('en')
            empty_msg = ("The current query result is empty, unable to perform effective data prediction. "
                         "Please check the datasource or adjust query conditions and try again.") if _is_en_empty_p else \
                        "当前查询结果为空，无法进行有效的数据预测。请检查数据源或调整查询条件后重试。"
            yield {'content': empty_msg, 'reasoning_content': ''}
            try:
                save_predict_answer(session=_session, record_id=self.record.id,
                                    answer=orjson.dumps({'content': empty_msg, 'reasoning_content': ''}).decode())
            except Exception:
                pass
            return
        
        # 限制注入LLM的数据行数，防止prompt过长导致模型返回空响应
        # 预测场景需要足够的历史数据点，但不需要上千行
        _MAX_DATA_ROWS_FOR_LLM = 200
        _data_for_llm = _data_content
        _data_truncated = False
        if isinstance(_data_content, list) and len(_data_content) > _MAX_DATA_ROWS_FOR_LLM:
            _data_for_llm = _data_content[:_MAX_DATA_ROWS_FOR_LLM]
            _data_truncated = True
            ChatBILogUtil.warning(
                f"[generate_predict] Data truncated for LLM: {len(_data_content)} -> {_MAX_DATA_ROWS_FOR_LLM} rows"
            )
        _MAX_DATA_CHARS_FOR_LLM = 40000
        _data_json = orjson.dumps(_data_for_llm).decode()
        if len(_data_json) > _MAX_DATA_CHARS_FOR_LLM:
            _ratio = _MAX_DATA_CHARS_FOR_LLM / len(_data_json)
            _reduced_rows = max(10, int(len(_data_for_llm) * _ratio * 0.9))
            _data_for_llm = _data_for_llm[:_reduced_rows]
            _data_json = orjson.dumps(_data_for_llm).decode()
            _data_truncated = True
            ChatBILogUtil.warning(
                f"[generate_predict] Data further truncated by char limit: -> {_reduced_rows} rows, "
                f"{len(_data_json)} chars"
            )
        self.chat_question.data = _data_json

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
            ChatBILogUtil.info(f"[generate_predict] Query rewritten: '{self.chat_question.question}' -> '{retrieval_question}'")
        
        # 记录查询理解阶段到思考过程（对齐run_task路径，确保思考面板Step 1显示）
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
                    intent=rewrite_result.get('intent', 'prediction'),
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
            ChatBILogUtil.error(f"[generate_predict] Failed to record query understanding stage: {e}")
        
        # RAG检索，让术语和文档知识增强数据预测
        rag_start_time = time.time()
        terminology_count = 0
        _predict_terminology_details = []
        
        if rag_enabled:
            # 使用共享RAG流水线，消除与analysis_service的重复代码
            _rag_result = self._execute_rag_for_task(
                _session, retrieval_question, rewrite_result, oid, ds_id,
                scenario='prediction',
            )
            _predict_terminology_details = _rag_result['terminology_details']
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
            ChatBILogUtil.error(f"[generate_predict] Dialogue tracking failed: {e}")
        
        # 多路检索、质量过滤、模板构建、术语扩展已移至 _execute_rag_for_task()
        try:
            if 'rag_retrieval' not in self.thinking_process.stages:
                from apps.chat.thinking.rag_thinking import record_rag_retrieval
                _pd_ds_type = (self.ds.type or 'database').lower() if self.ds else 'database'
                record_rag_retrieval(
                    self.thinking_process,
                    question=self.chat_question.question,
                    terminologies=_predict_terminology_details,
                    retrieval_time=rag_retrieval_time,
                    ds_type=_pd_ds_type,
                    intent='prediction',
                )
            rag_stage_data = self.thinking_process.get_stage('rag_retrieval')
            if rag_stage_data:
                yield {'type': 'thinking_stage', 'stage': 'rag_retrieval', 'data': rag_stage_data}
        except Exception as e:
            ChatBILogUtil.error(f"[generate_predict] Failed to yield rag_retrieval stage: {e}")
        
        # 缺陷2修复：发送上下文压缩阶段到前端（_execute_rag_for_task 内部已记录，此处 yield）
        # 仅在独立执行时（rag_enabled=True）yield，内联执行时 run_task 已发送
        try:
            if rag_enabled:
                cc_stage_data = self.thinking_process.get_stage('context_compression')
                if cc_stage_data:
                    yield {'type': 'thinking_stage', 'stage': 'context_compression', 'data': cc_stage_data}
        except Exception as e:
            ChatBILogUtil.error(f"[generate_predict] Failed to yield context_compression stage: {e}")
        
        # 获取自定义提示词（智能匹配）
        custom_prompt_content = ''
        custom_prompt_used = False
        custom_prompts_list = []
        _question = self.chat_question.question or ''
        if ChatBILicenseUtil.valid():
            # 查询当前场景（数据预测）的自定义提示词
            _total = count_custom_prompts(_session, CustomPromptTypeEnum.PREDICT_DATA, oid, ds_id)
            custom_prompt_content, _details = find_relevant_custom_prompts(
                _session, CustomPromptTypeEnum.PREDICT_DATA, oid, _question, ds_id)
            self.chat_question.custom_prompt = custom_prompt_content
            _matched_count = len([d for d in _details if d.get('reason') != 'not_matched'])
            custom_prompt_used = _matched_count > 0
            
            _is_en_cp = (self.chat_question.lang or '').lower().startswith('en')
            custom_prompts_list.append({
                'type': 'Data Prediction' if _is_en_cp else '数据预测',
                'content': custom_prompt_content[:200] + '...' if custom_prompt_content and len(custom_prompt_content) > 200 else (custom_prompt_content or ''),
                'used': custom_prompt_used,
                'empty': _total == 0,
                'count': _matched_count,
                'total': _total,
                'matched': _details
            })
            
        predict_msg: List[Union[BaseMessage, dict[str, Any]]] = []
        predict_msg.append(SystemMessage(content=self.chat_question.predict_sys_question(
            ds_type=self.ds.type if self.ds else 'database'
        )))
        
        # 注入多轮对话上下文到数据预测路径
        # 使预测能理解上下文引用，如"预测上面提到的指标"、"用同样的数据预测下个月"
        try:
            if self.dialogue_tracker and self.dialogue_tracker.turns:
                dialogue_ctx = self.dialogue_tracker.get_dialogue_context(max_turns=3)
                if dialogue_ctx.get('total_turns', 0) > 0:
                    ctx_parts = []
                    _is_en_ctx_p = (self.chat_question.lang or '').lower().startswith('en')
                    if dialogue_ctx.get('current_topic'):
                        ctx_parts.append(f"{'Current topic' if _is_en_ctx_p else '当前话题'}: {dialogue_ctx['current_topic']}")
                    if dialogue_ctx.get('active_entities'):
                        ctx_parts.append(f"{'Active entities' if _is_en_ctx_p else '活跃实体'}: {', '.join(dialogue_ctx['active_entities'][:5])}")
                    recent_qs = dialogue_ctx.get('recent_questions', [])
                    if len(recent_qs) > 1:
                        ctx_parts.append(f"{'Recent questions' if _is_en_ctx_p else '近期问题'}: {'; '.join(recent_qs[-3:])}")
                    # 注入上下文引用解析结果
                    ctx_refs = dialogue_ctx.get('context_references', [])
                    if ctx_refs:
                        ref_hints = [f"{r['type']}: {r['resolved']}" for r in ctx_refs if r.get('resolved')]
                        if ref_hints:
                            ctx_parts.append(f"{'Context references' if _is_en_ctx_p else '上下文引用'}: {'; '.join(ref_hints)}")
                    if ctx_parts:
                        dialogue_hint = '\n'.join(ctx_parts)
                        predict_msg.append(SystemMessage(
                            content=f"<dialogue-context>\n{dialogue_hint}\n</dialogue-context>"
                        ))
        except Exception as e:
            ChatBILogUtil.error(f"Failed to inject dialogue context into predict: {e}")
        
        _predict_user_content = self.chat_question.predict_user_question()
        # 如果数据被截断，在user prompt中告知LLM，避免它对数据完整性做错误假设
        if _data_truncated:
            _is_en_trunc_p = (self.chat_question.lang or '').lower().startswith('en')
            _trunc_notice_p = (f"\n\n⚠️ Note: The data above shows only the first {len(_data_for_llm)} rows "
                               f"out of {len(_data_content)} total rows. "
                               f"Please base your prediction on the available data and note that it is a subset."
                               if _is_en_trunc_p else
                               f"\n\n⚠️ 注意：以上数据仅展示了全部{len(_data_content)}行中的前{len(_data_for_llm)}行。"
                               f"请基于已提供的数据进行预测，并注明这是部分数据的预测结果。")
            _predict_user_content += _trunc_notice_p
        predict_msg.append(HumanMessage(content=_predict_user_content))

        # 记录提示词构建阶段（预测路径）— 通过 PromptBuilder 记录
        if not skip_rag:
            try:
                from apps.chat.thinking.prompt_builder import PromptBuilder
                predict_builder = PromptBuilder(
                    prompt_type='prediction',
                    model_name=self.chat_question.ai_modal_name or ''
                )
                predict_builder.set_rag_knowledge(
                    terminologies_xml=self.chat_question.terminologies,
                    sql_examples_xml=self.chat_question.data_training,
                    raw_terminology_count=getattr(self.chat_question, 'raw_terminology_count', 0),
                )
                predict_builder.set_custom_prompts(
                    self.chat_question.custom_prompt,
                    custom_prompts_list,
                )
                predict_builder.set_dialogue_context(
                    getattr(self, 'dialogue_tracker', None),
                    lang=self.chat_question.lang,
                )

                _sys_prompt_predict = predict_msg[0].content if predict_msg else ''
                _user_prompt_predict = predict_msg[-1].content if predict_msg else ''
                _predict_metadata = predict_builder._build_metadata(_sys_prompt_predict, _user_prompt_predict)
                _predict_metadata.message_count = len(predict_msg)
                # system_prompt_length 应包含所有 SystemMessage（含 dialogue-context）
                # 否则 total_prompt_length ≠ system_prompt_length + user_prompt_length，前端占比条不准确
                _sys_total_predict = sum(
                    len(m.content) for m in predict_msg
                    if isinstance(m, SystemMessage))
                _predict_metadata.system_prompt_length = _sys_total_predict
                _predict_metadata.total_prompt_length = _sys_total_predict + len(_user_prompt_predict)
                predict_builder.record_to_thinking(self.thinking_process, _predict_metadata)

                # 发送合并后的 prompt_construction 阶段到前端
                _pc_stage = self.thinking_process.get_stage('prompt_construction')
                if _pc_stage:
                    yield {'type': 'thinking_stage', 'stage': 'prompt_construction', 'data': _pc_stage}
            except Exception:
                pass

        self.current_logs[OperationEnum.PREDICT_DATA] = start_log(session=_session,
                                                                  ai_modal_id=self.chat_question.ai_modal_id,
                                                                  ai_modal_name=self.chat_question.ai_modal_name,
                                                                  operate=OperationEnum.PREDICT_DATA,
                                                                  record_id=self.record.id,
                                                                  full_message=[
                                                                      {'type': msg.type,
                                                                       'content': msg.content,
                                                                       'custom_prompt_used': custom_prompt_used} for
                                                                      msg
                                                                      in predict_msg])
        
        # 发送预测阶段的RAG检索结果到前端
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
                terminology_results_predict = []
                if _predict_terminology_details:
                    for t in _predict_terminology_details[:5]:
                        terminology_results_predict.append({
                            'word': t.get('word', ''),
                            'description': t.get('description', ''),
                            'similarity': t.get('similarity', 0),
                            'match_type': t.get('match_type', 'vector'),
                            'used': True
                        })
                elif terminology_count > 0:
                    _is_en_term_p = (self.chat_question.lang or '').lower().startswith('en')
                    terminology_results_predict.append({
                        'word': f'Terminology ({terminology_count} items)' if _is_en_term_p else f'术语库({terminology_count}条)',
                        'description': 'Injected into prediction prompt' if _is_en_term_p else '已注入到预测提示词中',
                        'similarity': 0.8,
                        'match_type': 'vector',
                        'used': True
                    })
                # 计算RAG影响指标（对齐run_task主路径）
                from apps.chat.thinking.rag_thinking import RAGQualityMetrics
                _cached_doc_chunks = getattr(self, '_rag_doc_chunks', None) or []
                _ds_type_for_impact = (self.ds.type or 'database').lower() if self.ds else 'database'
                rag_impact = RAGQualityMetrics.calculate_rag_impact(
                    True,
                    terminology_results_predict,
                    [],
                    doc_chunks=_cached_doc_chunks,
                    ds_type=_ds_type_for_impact,
                    intent='prediction',
                )
                terminology_quality = RAGQualityMetrics.calculate_retrieval_quality(terminology_results_predict) if terminology_results_predict else {}
                rag_results_data = {
                    'terminologies': terminology_results_predict,
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
                    ChatBILogUtil.error(f"[generate_predict] Failed to save RAG results: {e}")
            yield {'type': 'rag_results', 'data': rag_results_data}
        except Exception as e:
            ChatBILogUtil.error(f"[generate_predict] Failed to send RAG results: {e}")
        
        full_thinking_text = ''
        full_predict_text = ''
        token_usage = {}
        
        # 记录LLM调用开始时间
        llm_start_time = time.time()
        
        # 先发送 loading 状态，让前端立即展示"生成中"
        yield {
            'type': 'thinking_stage', 'stage': 'data_prediction',
            'data': {
                'stage': 'data_prediction',
                'status': 'loading',
                'timestamp': datetime.now().isoformat(),
                'streaming_reasoning': '',
            }
        }
        
        # NOTE: process_stream and stream_with_retry are module-level functions in llm.py,
        # accessed via late import to avoid circular dependency
        from apps.chat.task.llm import process_stream, stream_with_retry
        
        # 新增：分离预测数据和预测报告
        first_line = ''  # 第一行应该是JSON数组格式的预测数据
        report_lines = []  # 后续行是预测报告
        is_first_line = True
        
        # 用于控制流式推理内容的发送频率
        _reasoning_update_counter = 0
        _REASONING_UPDATE_INTERVAL = 3
        
        ChatBILogUtil.info(f"[generate_predict] Starting to process predict stream")
        
        # Gemini 2.5 Pro 偶尔返回 0 output tokens，需要在此层重试
        # 重试时在 user message 末尾追加提示，打破模型的空响应模式
        _max_empty_retries = 2
        _original_predict_user_msg = predict_msg[-1].content if predict_msg else ''
        for _empty_attempt in range(_max_empty_retries + 1):
            full_thinking_text = ''
            full_predict_text = ''
            first_line = ''
            report_lines = []
            is_first_line = True
            _reasoning_update_counter = 0
            
            res = process_stream(stream_with_retry(self.llm, predict_msg), token_usage)
            
            for chunk in res:
                # 安全处理：确保content不为None
                content = chunk.get('content')
                if content:
                    full_predict_text += content
                    
                    # 分离第一行（预测数据）和后续行（预测报告）
                    if is_first_line and '\n' in full_predict_text:
                        lines = full_predict_text.split('\n', 1)
                        first_line = lines[0].strip()
                        if len(lines) > 1:
                            report_lines.append(lines[1])
                        is_first_line = False
                        ChatBILogUtil.info(f"[generate_predict] Separated first line (length: {len(first_line)})")
                    elif not is_first_line:
                        report_lines.append(content)
                        
                reasoning_content = chunk.get('reasoning_content')
                if reasoning_content:
                    full_thinking_text += reasoning_content
                    _reasoning_update_counter += 1
                    if _reasoning_update_counter % _REASONING_UPDATE_INTERVAL == 0:
                        yield {
                            'type': 'thinking_stage', 'stage': 'data_prediction',
                            'data': {
                                'stage': 'data_prediction',
                                'status': 'loading',
                                'timestamp': datetime.now().isoformat(),
                                'streaming_reasoning': full_thinking_text,
                            }
                        }
                yield chunk
            
            # 如果有内容（包括仅有推理内容），跳出重试循环
            if (full_predict_text and full_predict_text.strip()) or (full_thinking_text and full_thinking_text.strip()):
                break
            
            # 完全空响应：判断是否需要重试
            if _empty_attempt < _max_empty_retries:
                _wait_time = 1.0 * (2 ** _empty_attempt)  # 指数退避：1s, 2s
                ChatBILogUtil.warning(
                    f"[generate_predict] LLM returned empty content (attempt {_empty_attempt + 1}/{_max_empty_retries + 1}), "
                    f"retrying in {_wait_time:.0f}s... Model: {self.chat_question.ai_modal_name}, "
                    f"Token usage: {token_usage}"
                )
                # 重试时修改 user message，追加重试提示打破空响应模式
                _is_en_retry_p = (self.chat_question.lang or '').lower().startswith('en')
                _retry_hint_p = (f"\n\n(Retry attempt {_empty_attempt + 2}: Please generate the prediction report now.)"
                                 if _is_en_retry_p else
                                 f"\n\n（第{_empty_attempt + 2}次请求：请立即生成数据预测报告。）")
                predict_msg[-1] = HumanMessage(content=_original_predict_user_msg + _retry_hint_p)
                time.sleep(_wait_time)
        
        # 安全兜底：如果LLM只输出了推理内容但没有最终回答
        if not full_predict_text.strip() and full_thinking_text.strip():
            ChatBILogUtil.info("[generate_predict] LLM returned only reasoning content, using it as prediction")
            full_predict_text = full_thinking_text
            yield {'content': full_predict_text, 'reasoning_content': ''}
        elif not full_predict_text.strip():
            ChatBILogUtil.error(
                f"[generate_predict] LLM returned empty response after {_max_empty_retries + 1} attempts. "
                f"Model: {self.chat_question.ai_modal_name}, Token usage: {token_usage}"
            )
            _is_en_empty_p2 = (self.chat_question.lang or '').lower().startswith('en')
            full_predict_text = ("Sorry, the system failed to generate valid prediction results. "
                                 "Please try rephrasing your question.\n"
                                 "💡 Tip: Try simplifying your question, or check if the datasource contains the relevant tables and fields.") if _is_en_empty_p2 else \
                                ("抱歉，系统未能生成有效的预测结果，请尝试重新提问或换一种表述方式。\n"
                                 "💡 建议：尝试简化您的问题，或检查数据源中是否包含相关的数据表和字段。")
            yield {'content': full_predict_text, 'reasoning_content': ''}
        
        # 重新从完整文本中分离JSON数据行和报告文本
        _clean_text = full_predict_text.strip()
        if _clean_text:
            _clean_lines = _clean_text.split('\n', 1)
            _candidate_first = _clean_lines[0].strip()
            if _candidate_first.startswith('[') or _candidate_first.startswith('{'):
                first_line = _candidate_first
                predict_report_text = _clean_lines[1].strip() if len(_clean_lines) > 1 else ''
            else:
                # 非JSON开头，整个内容可能是纯文本报告或错误信息
                first_line = _clean_text
                predict_report_text = ''
            ChatBILogUtil.info(f"[generate_predict] Re-separated: first_line length={len(first_line)}, report length={len(predict_report_text)}")
        else:
            first_line = ''
            predict_report_text = ''

        predict_msg.append(AIMessage(full_predict_text))
        
        # 构建最终的预测结果
        predict_report = predict_report_text
        
        ChatBILogUtil.info(f"[generate_predict] Final result - first_line length: {len(first_line)}, report length: {len(predict_report)}, thinking length: {len(full_thinking_text)}")
        
        # 合并预测数据和预测报告到同一次数据库写入，避免两次独立 commit
        # 第二次 commit 失败时 predict 已保存但 predict_content 丢失
        from sqlalchemy import update as sa_update
        from apps.chat.models.chat_model import ChatRecord
        
        update_values = {
            'predict': orjson.dumps({
                'content': first_line,
                'reasoning_content': full_thinking_text
            }).decode()
        }
        if predict_report:
            update_values['predict_content'] = predict_report
            ChatBILogUtil.info(f"[generate_predict] Saving predict_content: {len(predict_report)} chars")
        if full_thinking_text:
            update_values['predict_reasoning_content'] = full_thinking_text
            ChatBILogUtil.info(f"[generate_predict] Saving predict_reasoning_content: {len(full_thinking_text)} chars")
        
        stmt = sa_update(ChatRecord).where(ChatRecord.id == self.record.id).values(**update_values)
        _session.execute(stmt)
        _session.commit()
        
        from apps.chat.crud.chat import get_chat_record_by_id
        self.record = get_chat_record_by_id(_session, self.record.id)
        ChatBILogUtil.info(f"[generate_predict] Successfully saved all predict data in single commit")
            
        # 将 end_log 包裹在 try/except 中，防止日志记录失败阻塞
        # record_data_prediction 的 yield（即 data_prediction completed 阶段发送到前端）
        try:
            self.current_logs[OperationEnum.PREDICT_DATA] = end_log(session=_session,
                                                                    log=self.current_logs[
                                                                        OperationEnum.PREDICT_DATA],
                                                                    full_message=[
                                                                        {'type': msg.type,
                                                                         'content': msg.content}
                                                                        for msg in predict_msg],
                                                                    reasoning_content=full_thinking_text,
                                                                    token_usage=token_usage)
        except Exception as _end_log_err:
            ChatBILogUtil.error(f"[generate_predict] end_log failed (non-fatal): {_end_log_err}")
        
        # 计算预测生成耗时（使用实际的LLM调用时间）
        predict_generation_time = time.time() - llm_start_time
        
        # 记录数据预测阶段到思考过程
        try:
            # 构建RAG上下文信息
            rag_context = {
                "terminologies_used": terminology_count,
                "custom_prompt_used": custom_prompt_used,
                "rag_retrieval_time": round(rag_retrieval_time, 3),
                "data_fields": len(fields),
                "data_rows": len(_data_content) if isinstance(_data_content, list) else 0
            }
            
            # 使用新的record_data_prediction函数（区分预测和分析）
            record_data_prediction(
                self.thinking_process,
                prediction=full_predict_text[:1000],
                reasoning=full_thinking_text[:500],
                rag_context=rag_context,
                generation_time=predict_generation_time,
                token_usage=token_usage
            )
            
            # 发送预测思考过程
            predict_stage_data = self.thinking_process.get_stage('data_prediction')
            if predict_stage_data:
                yield {'type': 'thinking_stage', 'stage': 'data_prediction', 'data': predict_stage_data}
            
            # 记录溯源凭证（预测路径）
            try:
                _existing_prov = self.thinking_process.get_stage('provenance')
                if _existing_prov and _existing_prov.get('extra_data', {}).get('records'):
                    _prov_stage_obj = self.thinking_process.stages.get('provenance')
                    if _prov_stage_obj and _prov_stage_obj.extra_data.get('records'):
                        _first_rec = _prov_stage_obj.extra_data['records'][0]
                        _first_rec.setdefault('data_fields', len(fields))
                        _first_rec.setdefault('data_rows', len(_data_content) if isinstance(_data_content, list) else 0)
                        _first_rec.setdefault('terminologies_used', terminology_count)
                        _first_rec.setdefault('custom_prompt_used', custom_prompt_used)
                else:
                    from apps.chat.thinking.thinking_integration import record_provenance_stage
                    _pred_provenance = []
                    _pred_ds_type = (self.ds.type or '').lower() if self.ds else 'database'
                    _pred_provenance.append({
                        'source_type': _pred_ds_type if _pred_ds_type in ('excel', 'csv', 'pdf') else 'database',
                        'source_name': self.ds.name if self.ds else '',
                        'data_fields': len(fields),
                        'data_rows': len(_data_content) if isinstance(_data_content, list) else 0,
                        'terminologies_used': terminology_count,
                        'custom_prompt_used': custom_prompt_used,
                        'update_time': str(self.ds.update_time) if self.ds and hasattr(self.ds, 'update_time') else '',
                    })
                    record_provenance_stage(self.thinking_process, _pred_provenance)
                _pred_prov_stage = self.thinking_process.get_stage('provenance')
                if _pred_prov_stage:
                    yield {'type': 'thinking_stage', 'stage': 'provenance', 'data': _pred_prov_stage}
            except Exception as prov_e:
                ChatBILogUtil.error(f"[generate_predict] Failed to record provenance: {prov_e}")
        except Exception as e:
            ChatBILogUtil.error(f"Failed to record predict thinking stage: {e}")

        # 新增：计算并发送预测置信度评分
        try:
            # 从 _data_content 提取数值列用于趋势稳定性计算
            _confidence_values: List[float] = []
            _time_span_months = 0.0
            _missing_count = 0
            _total_cells = 0

            if isinstance(_data_content, list) and _data_content:
                for row in _data_content:
                    if isinstance(row, dict):
                        for v in row.values():
                            _total_cells += 1
                            if v is None or v == '' or v == 'null':
                                _missing_count += 1
                            else:
                                try:
                                    _confidence_values.append(float(v))
                                except (ValueError, TypeError):
                                    pass

                # 估算时间跨度：尝试从数据中提取日期字段
                _date_values: List[str] = []
                if _data_content:
                    first_row = _data_content[0] if isinstance(_data_content[0], dict) else {}
                    for key in first_row:
                        # 检测可能的日期字段
                        key_lower = str(key).lower()
                        if any(kw in key_lower for kw in ['date', 'time', '日期', '时间', 'month', '月', 'year', '年']):
                            for row in _data_content:
                                if isinstance(row, dict) and row.get(key):
                                    _date_values.append(str(row[key]))
                            break

                if _date_values and len(_date_values) >= 2:
                    # 粗略估算时间跨度（月）
                    try:
                        _parsed_dates = []
                        for dv in _date_values:
                            for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y-%m', '%Y%m', '%Y年%m月', '%Y年%m月%d日'):
                                try:
                                    _parsed_dates.append(datetime.strptime(dv.strip(), fmt))
                                    break
                                except ValueError:
                                    continue
                        if len(_parsed_dates) >= 2:
                            _parsed_dates.sort()
                            delta = _parsed_dates[-1] - _parsed_dates[0]
                            _time_span_months = delta.days / 30.0
                    except Exception:
                        pass

                # 如果无法从数据推断时间跨度，根据数据行数粗略估算
                if _time_span_months <= 0 and len(_data_content) > 0:
                    _time_span_months = len(_data_content) * 0.25  # 假设每行约 1 周

            _missing_rate = (_missing_count / _total_cells) if _total_cells > 0 else 0.0
            _data_row_count = len(_data_content) if isinstance(_data_content, list) else 0

            confidence_result = self._calculate_prediction_confidence(
                data_rows=_data_row_count,
                time_span_months=_time_span_months,
                values=_confidence_values,
                missing_rate=_missing_rate,
            )

            ChatBILogUtil.info(
                f"[generate_predict] Prediction confidence: score={confidence_result['score']}, "
                f"level={confidence_result['level']}, factors={confidence_result['factors']}"
            )

            # 通过 SSE 发送置信度数据到前端
            yield {'type': 'prediction_confidence', 'data': confidence_result}
            
            # 持久化预测置信度到 thinking_process
            try:
                predict_stage = self.thinking_process.get_stage('data_prediction')
                if predict_stage:
                    if isinstance(predict_stage, dict):
                        predict_stage['prediction_confidence'] = confidence_result
                    elif hasattr(predict_stage, 'extra_data'):
                        if predict_stage.extra_data is None:
                            predict_stage.extra_data = {}
                        predict_stage.extra_data['prediction_confidence'] = confidence_result
            except Exception:
                pass
        except Exception as e:
            ChatBILogUtil.error(f"[generate_predict] Failed to calculate prediction confidence: {e}")

    @staticmethod
    def _calculate_prediction_confidence(
        data_rows: int,
        time_span_months: float,
        values: List[float],
        missing_rate: float,
    ) -> Dict[str, Any]:
        """计算预测置信度评分。"""

        # --- 辅助：线性插值到 [0, 100] ---
        def _linear_score(value: float, low: float, high: float) -> float:
            if value >= high:
                return 100.0
            if value <= low:
                return 0.0
            return (value - low) / (high - low) * 100.0

        # 1) 数据量充足性 (30%)
        data_volume_score = _linear_score(float(data_rows), 20.0, 100.0)

        # 2) 时间跨度合理性 (25%)
        time_span_score = _linear_score(float(time_span_months), 3.0, 12.0)

        # 3) 趋势稳定性 (25%) — 基于变异系数 (CV = std / |mean|)
        if values and len(values) >= 2:
            # 审计[14.2]：过滤 NaN/Inf 值，防止数据库脏数据导致计算异常
            clean_values = [v for v in values if math.isfinite(v)]
            if len(clean_values) >= 2:
                mean_val = statistics.mean(clean_values)
                std_val = statistics.stdev(clean_values)
                if abs(mean_val) > 1e-9:
                    cv = std_val / abs(mean_val)
                else:
                    # mean ≈ 0 时，若 std 也很小则稳定
                    cv = 0.0 if std_val < 1e-9 else 2.0
                # CV ≤ 0.1 → 满分，CV ≥ 1.0 → 0 分
                trend_stability_score = _linear_score(1.0 - cv, 0.0, 0.9)
            elif len(clean_values) == 1:
                trend_stability_score = 50.0
            else:
                trend_stability_score = 0.0
        elif values and len(values) == 1:
            # 只有一个数据点，无法评估趋势
            trend_stability_score = 50.0
        else:
            trend_stability_score = 0.0

        # 4) 数据完整性 (20%)
        clamped_missing = max(0.0, min(1.0, float(missing_rate)))
        data_completeness_score = (1.0 - clamped_missing) * 100.0

        # 加权总分
        score = (
            data_volume_score * 0.30
            + time_span_score * 0.25
            + trend_stability_score * 0.25
            + data_completeness_score * 0.20
        )
        score = round(max(0.0, min(100.0, score)), 1)

        # level 映射
        if score >= 80:
            level = "高"
        elif score >= 50:
            level = "中"
        else:
            level = "低"

        # 预测区间：基于标准差和置信度
        if values and len(values) >= 2:
            # 审计[14.2]：使用过滤后的干净数值计算预测区间
            clean_values = [v for v in values if math.isfinite(v)]
            if len(clean_values) >= 2:
                std_val = statistics.stdev(clean_values)
                mean_val = statistics.mean(clean_values)
                # 置信度越高，区间越窄
                interval_factor = 1.96 * (1.0 - score / 200.0)  # score 高 → 因子小
                lower = round(mean_val - interval_factor * std_val, 2)
                upper = round(mean_val + interval_factor * std_val, 2)
            else:
                lower = None
                upper = None
        else:
            lower = None
            upper = None

        # 添加归一化到[0,1]的prediction_confidence字段
        prediction_confidence = round(score / 100.0, 4)

        return {
            "score": score,
            "prediction_confidence": prediction_confidence,
            "level": level,
            "factors": {
                "data_volume": round(data_volume_score, 1),
                "time_span": round(time_span_score, 1),
                "trend_stability": round(trend_stability_score, 1),
                "data_completeness": round(data_completeness_score, 1),
            },
            "prediction_interval": {
                "lower": lower,
                "upper": upper,
            },
        }

    def check_save_predict_data(self, session: Session, res: str) -> bool:
        """从预测结果中提取预测数据（JSON数组）
            预测结果格式：
            """
        # 优先提取第一行的JSON数组
        lines = res.strip().split('\n')
        first_line = lines[0].strip() if lines else ''
        
        ChatBILogUtil.info(f"[check_save_predict_data] Processing predict result, total lines: {len(lines)}")
        ChatBILogUtil.info(f"[check_save_predict_data] First line: {first_line[:200] if first_line else 'empty'}")
        
        json_str = ''
        
        # 策略1：尝试直接解析第一行
        if first_line:
            try:
                parsed = orjson.loads(first_line)
                if isinstance(parsed, list):
                    json_str = first_line
                    ChatBILogUtil.info(f"[check_save_predict_data] Successfully extracted predict data from first line: {len(parsed)} items")
            except Exception as e:
                ChatBILogUtil.warning(f"[check_save_predict_data] First line is not valid JSON array: {e}")
        
        # 策略2：正则提取 — 匹配 ```json ... ``` 代码块中的JSON数组
        if not json_str:
            code_block_match = re.search(r'```(?:json)?\s*(\[[\s\S]*?\])\s*```', res)
            if code_block_match:
                candidate = code_block_match.group(1).strip()
                try:
                    parsed = orjson.loads(candidate)
                    if isinstance(parsed, list):
                        json_str = candidate
                        ChatBILogUtil.info(f"[check_save_predict_data] Extracted from code block: {len(parsed)} items")
                except Exception:
                    pass
        
        # 策略3：正则提取 — 匹配文本中最长的 JSON 数组 [...]
        if not json_str:
            # 贪婪匹配最外层的 [ ... ]
            array_match = re.search(r'(\[\s*\{[\s\S]*?\}\s*\])', res)
            if array_match:
                candidate = array_match.group(1).strip()
                try:
                    parsed = orjson.loads(candidate)
                    if isinstance(parsed, list):
                        json_str = candidate
                        ChatBILogUtil.info(f"[check_save_predict_data] Extracted via regex: {len(parsed)} items")
                except Exception:
                    pass
        
        # 策略4：使用 extract_json_robust 提取（原有兜底）
        if not json_str:
            json_str = extract_json_robust(res)
            if json_str:
                ChatBILogUtil.info(f"[check_save_predict_data] Extracted predict data using extract_json_robust")
        
        if not json_str:
            json_str = ''
            ChatBILogUtil.warning(f"[check_save_predict_data] No valid JSON array found in predict result")

        save_predict_data(session=session, record_id=self.record.id, data=json_str)
        
        ChatBILogUtil.info(f"[check_save_predict_data] Saved predict data to record {self.record.id}, has_data: {json_str != ''}")

        if json_str == '':
            return False

        return True
