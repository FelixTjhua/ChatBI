"""RAG检索共享逻辑 - 从analysis_service和prediction_service中提取的公共RAG流水线"""
import time
from typing import Dict, List, Optional, Tuple

from sqlmodel import Session

from apps.chat.thinking.query_rewriter import QueryRewriter
from apps.chat.thinking.context_compressor import ContextCompressor
from apps.terminology.crud.terminology import select_terminology_by_word_with_details
from apps.chat.thinking.rag_evidence_filter import filter_rag_evidence
from common.utils.utils import ChatBILogUtil


class RAGMixin:
    """分析/预测共享的RAG检索逻辑"""

    def _execute_rag_for_task(
        self,
        _session: Session,
        retrieval_question: str,
        rewrite_result: dict,
        oid: int,
        ds_id: Optional[int],
        scenario: str = 'analysis',
    ) -> Dict:
        """执行分析/预测共享的RAG检索流水线"""
        tag = f"[{scenario}]"
        rag_start_time = time.time()
        terminology_details: List[Dict] = []

        # --- 1. 术语检索 ---
        try:
            terminology_details = select_terminology_by_word_with_details(
                _session, retrieval_question, oid, ds_id
            )
        except Exception as e:
            ChatBILogUtil.error(f"{tag} Failed to get terminology details: {e}")

        # --- 2. 多路检索：利用扩展查询提升召回率 ---
        expanded_queries = rewrite_result.get('expanded_queries', [])
        if expanded_queries:
            ChatBILogUtil.info(f"{tag} Multi-path retrieval with {len(expanded_queries)} expanded queries")
            existing_words = {t.get('word', '') for t in terminology_details}
            for eq in expanded_queries:
                try:
                    extra_terms = select_terminology_by_word_with_details(
                        _session, eq, oid, ds_id
                    )
                    for et in extra_terms:
                        if et.get('word', '') not in existing_words:
                            terminology_details.append(et)
                            existing_words.add(et.get('word', ''))
                except Exception as e:
                    ChatBILogUtil.error(f"{tag} Expanded query retrieval failed for '{eq}': {e}")

        # --- 3. 质量过滤 ---
        if terminology_details:
            try:
                all_evidence = [{**t, 'source_type': 'terminology'} for t in terminology_details]
                filtered, removed = filter_rag_evidence(all_evidence, threshold=0.35)
                terminology_details = [e for e in filtered if e.get('source_type') == 'terminology']
                if removed:
                    ChatBILogUtil.info(f"{tag} Quality filter: {len(removed)} low-quality items removed")
            except Exception as e:
                ChatBILogUtil.error(f"{tag} Quality filter failed: {e}")

        # --- 4. 构建XML模板 ---
        from apps.chat.task.llm import build_terminology_template_from_details
        _ds_type_for_template = (self.ds.type or '').lower() if hasattr(self, 'ds') and self.ds else ''
        self.chat_question.terminologies = build_terminology_template_from_details(terminology_details, ds_type=_ds_type_for_template)

        # --- 4b. 文档片段检索（仅PDF文档知识库）---
        doc_chunks: List[Dict] = []
        _ds_type = (self.ds.type or '').lower() if hasattr(self, 'ds') and self.ds else ''
        if _ds_type == 'pdf':
            try:
                from apps.datasource.document_retrieval import search_document_chunks
                _doc_top_k = 5
                _doc_threshold = 0.35
                doc_chunks = search_document_chunks(
                    _session, retrieval_question, oid,
                    top_k=_doc_top_k, similarity_threshold=_doc_threshold,
                    ds_id=ds_id,
                ) or []

                # 扩展查询补充检索
                expanded_queries = rewrite_result.get('expanded_queries', [])
                if expanded_queries and doc_chunks is not None:
                    seen_ids = {c.get('id') for c in doc_chunks if c.get('id')}
                    for eq in expanded_queries[:2]:
                        try:
                            extra = search_document_chunks(
                                _session, eq, oid, top_k=3,
                                similarity_threshold=0.30, ds_id=ds_id,
                            ) or []
                            for ec in extra:
                                if ec.get('id') not in seen_ids:
                                    doc_chunks.append(ec)
                                    seen_ids.add(ec.get('id'))
                        except Exception:
                            pass

                # 按相似度排序截取
                doc_chunks.sort(key=lambda c: c.get('similarity', 0), reverse=True)
                _max_chunks = 8
                doc_chunks = doc_chunks[:_max_chunks]

                if doc_chunks:
                    ChatBILogUtil.info(
                        f"{tag} Document chunk retrieval: {len(doc_chunks)} chunks, "
                        f"top_sim={doc_chunks[0].get('similarity', 0)}"
                    )

                    # 将文档片段注入 data_training（与 _execute_unified_rag_pipeline 保持一致）
                    from apps.chat.thinking.unified_rag_executor import format_pdf_context
                    # PDF文档片段受动态预算控制，防止超出LLM上下文窗口
                    _existing_len = len(getattr(self.chat_question, 'data_training', '') or '') + \
                                    len(getattr(self.chat_question, 'terminologies', '') or '')
                    _max_ctx = 8000
                    _doc_budget = max(1000, min(3000, _max_ctx - _existing_len))
                    doc_context = format_pdf_context(doc_chunks, max_chars=_doc_budget, lang=getattr(self.chat_question, 'lang', 'zh') or 'zh')
                    if doc_context:
                        doc_prefix = "\n\n<document-knowledge>\n"
                        doc_suffix = "\n</document-knowledge>"
                        existing_training = getattr(self.chat_question, 'data_training', '') or ''
                        self.chat_question.data_training = (
                            existing_training + doc_prefix + doc_context + doc_suffix
                        )
            except Exception as e:
                ChatBILogUtil.error(f"{tag} Document chunk retrieval failed: {e}")

        # 将 rag_retrieval_time 的计算移到文档片段检索之后，
        # 确保 PDF 数据源的文档检索耗时也被计入 RAG 检索总耗时
        rag_retrieval_time = time.time() - rag_start_time

        # 缓存文档片段供 RAG 影响评估使用
        self._rag_doc_chunks = doc_chunks

        # --- 5. 后置术语扩展 ---
        if terminology_details:
            try:
                _term_results = [
                    {'word': t.get('word', ''), 'description': t.get('description', '')}
                    for t in terminology_details
                    if t.get('word') and t.get('description')
                ]
                if _term_results:
                    expanded_query = QueryRewriter.post_expand_with_terminologies(retrieval_question, _term_results)
                    if expanded_query != retrieval_question:
                        ChatBILogUtil.info(f"{tag} Post-expand with terminologies: '{retrieval_question}' -> '{expanded_query}'")
                        retrieval_question = expanded_query
            except Exception as e:
                ChatBILogUtil.error(f"{tag} Post-expand with terminologies failed: {e}")

        # --- 6. 上下文压缩 ---
        try:
            _config = ContextCompressor.get_config(scenario)
            # 计算有效的 max_total_tokens：纯术语场景使用更小的预算
            _schema = getattr(self.chat_question, 'db_schema', '') or ''
            _sql_examples = getattr(self.chat_question, 'data_training', '') or ''
            # 排除 <document-knowledge> 标签内容，仅检查真正的 SQL 示例
            _has_real_sql_examples = _sql_examples.strip() and '<document-knowledge>' not in _sql_examples
            _effective_max_tokens = 800
            if not _schema.strip() and not _has_real_sql_examples:
                # 纯术语场景：预算缩小到术语实际需要的量
                _effective_max_tokens = 400  # 纯术语场景使用更小的预算
            compression_result = ContextCompressor.compress(
                terminologies=self.chat_question.terminologies,
                sql_examples=_sql_examples,
                schema=_schema,
                question=self.chat_question.question,
                max_total_tokens=_effective_max_tokens,
                config=_config,
            )
            if compression_result['compression_applied']:
                self.chat_question.terminologies = compression_result['terminologies']
                ChatBILogUtil.info(f"{tag} Context compressed: ratio={compression_result['stats'].get('compression_ratio', 1.0)}")
                try:
                    from apps.chat.thinking.thinking_integration import record_context_compression_stage
                    record_context_compression_stage(self.thinking_process, {
                        **compression_result['stats'],
                        'token_budget': _effective_max_tokens,
                    })
                except Exception:
                    pass
        except Exception as e:
            ChatBILogUtil.error(f"{tag} Context compression failed: {e}")

        # 在压缩之后计算 terminology_count，确保与实际注入 prompt 的数量一致
        terminology_count = self.chat_question.terminologies.count('<terminology>')

        return {
            'terminology_details': terminology_details,
            'terminology_count': terminology_count,
            'retrieval_question': retrieval_question,
            'rag_retrieval_time': rag_retrieval_time,
            'doc_chunks': doc_chunks,
        }
