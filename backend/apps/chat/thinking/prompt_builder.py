"""ChatBI Prompt Builder — 提示词构建模块"""

import logging
import re
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage

logger = logging.getLogger('chatbi')


@dataclass
class PromptComponent:
    """单个提示词组件的注入状态"""
    name: str           # 组件名称
    injected: bool      # 是否已注入
    source: str         # 来源方式：'rag_vector' | 'intent_inject' | 'direct' | 'context'
    count: int = 0      # 注入的条目数量
    char_length: int = 0  # 注入的字符长度


@dataclass
class PromptMetadata:
    """提示词构建的元数据 — 用于思考过程展示"""
    prompt_type: str                          # 场景类型
    model_name: str = ''                      # 使用的模型
    system_prompt_preview: str = ''           # System Prompt 预览
    user_prompt_preview: str = ''             # User Prompt 预览
    system_prompt_length: int = 0             # System Prompt 字符数
    user_prompt_length: int = 0               # User Prompt 字符数
    total_prompt_length: int = 0              # 提示词总字符数
    message_count: int = 0                    # 消息列表总条数
    components: List[PromptComponent] = field(default_factory=list)
    custom_prompts: List[Dict] = field(default_factory=list)  # 自定义提示词详情
    build_duration_ms: int = 0                # 构建耗时（毫秒）
    injected_terminologies: List[str] = field(default_factory=list)  # 注入的术语名称列表
    injected_sql_examples: List[str] = field(default_factory=list)   # 注入的SQL示例问题列表
    dialogue_context_text: str = ''  # 对话上下文实际内容（供前端展示）

    def to_rag_components(self) -> Dict[str, bool]:
        """转换为 rag_components 格式（兼容旧接口）"""
        result = {}
        for comp in self.components:
            key = comp.name
            result[key] = comp.injected
        return result

    def to_component_counts(self) -> Dict[str, Any]:
        """转换为 component_counts 格式（兼容旧接口）"""
        result = {}
        for comp in self.components:
            if comp.name == 'terminologies':
                result['terminology_count'] = comp.count
                # 导出实际字符长度，前端不再需要 count*80 的粗略估算
                result['terminology_char_length'] = comp.char_length
            elif comp.name == 'sql_examples':
                result['sql_example_count'] = comp.count
                # 导出实际字符长度，前端不再需要 count*200 的粗略估算
                result['sql_example_char_length'] = comp.char_length
            elif comp.name == 'document_chunks':
                result['doc_chunk_count'] = comp.count
                result['doc_chunk_length'] = comp.char_length
            elif comp.name == 'data_sample':
                result['data_sample_count'] = comp.count
                result['data_sample_length'] = comp.char_length
            elif comp.name == 'schema':
                result['schema_length'] = comp.char_length
            elif comp.name == 'custom_prompt':
                result['custom_prompt_length'] = comp.char_length
        # 注入的术语和SQL示例名称列表（供前端PromptConstructionDisplay展示）
        result['injected_terminologies'] = self.injected_terminologies
        result['injected_sql_examples'] = self.injected_sql_examples
        # 对话上下文实际内容（供前端展示）
        result['dialogue_context_text'] = self.dialogue_context_text
        return result


class PromptBuilder:
    """提示词构建器 — RAG 增强阶段的核心模块"""

    def __init__(self, prompt_type: str, model_name: str = ''):
        self.prompt_type = prompt_type
        self.model_name = model_name

        # 知识组件（RAG 向量检索结果）
        self._terminologies_xml: str = ''
        self._sql_examples_xml: str = ''
        self._terminology_count: int = 0
        self._sql_example_count: int = 0
        self._injected_terminologies: List[str] = []
        self._injected_sql_examples: List[str] = []

        # 文档片段（PDF 文档知识库检索结果）
        self._doc_chunk_count: int = 0
        self._doc_context_xml: str = ''

        # 数据样本
        self._data_sample_count: int = 0
        self._data_sample_xml: str = ''

        # Schema（直接注入）
        self._schema: str = ''

        # 自定义提示词（关键词匹配）
        self._custom_prompt_content: str = ''
        self._custom_prompt_details: List[Dict] = []

        # 对话上下文
        self._dialogue_context_parts: List[str] = []
        self._has_dialogue_context: bool = False

        # 查询分解
        self._decomposition_hint: str = ''

        # 构建计时
        self._build_start: float = 0

    # ========== 设置输入 ==========

    def set_rag_knowledge(self, terminologies_xml: str, sql_examples_xml: str = '',
                         raw_terminology_count: int = 0):
        """设置 RAG 向量检索结果（术语库 + SQL 示例库）"""
        self._raw_terminology_count = raw_terminology_count
        self._terminologies_xml = terminologies_xml or ''
        self._sql_examples_xml = sql_examples_xml or ''

        # 自动检测并分离 <document-knowledge> 内容
        # PDF 路径中 doc chunks 被注入到 data_training，会作为 sql_examples_xml 传入
        if self._sql_examples_xml and '<document-knowledge>' in self._sql_examples_xml:
            import re as _re
            _doc_match = _re.search(
                r'<document-knowledge>.*?</document-knowledge>',
                self._sql_examples_xml, _re.DOTALL
            )
            if _doc_match:
                _doc_xml = _doc_match.group(0)
                # 如果尚未通过 set_document_chunks 设置，自动提取
                if self._doc_chunk_count == 0:
                    self._doc_context_xml = _doc_xml
                    # 统计文档片段数量（每个 <chunk> 或 <p> 或段落）
                    _chunk_count = _doc_xml.count('【片段') + _doc_xml.count('[Chunk')
                    if _chunk_count == 0:
                        # 备用：按段落分隔符估算
                        _chunk_count = len([s for s in _doc_xml.split('\n\n') if s.strip() and not s.strip().startswith('<')])
                    self._doc_chunk_count = max(_chunk_count, 1)
                # 从 sql_examples_xml 中移除 document-knowledge 部分，仅保留真正的 SQL 示例
                self._sql_examples_xml = self._sql_examples_xml.replace(_doc_xml, '').strip()

        # 自动检测并分离 <data-sample> 内容
        # 样本数据被注入到 data_training，会作为 sql_examples_xml 传入
        if self._sql_examples_xml and '<data-sample>' in self._sql_examples_xml:
            import re as _re_ds
            _ds_match = _re_ds.search(
                r'<data-sample>.*?</data-sample>',
                self._sql_examples_xml, _re_ds.DOTALL
            )
            if _ds_match:
                _ds_xml = _ds_match.group(0)
                if self._data_sample_count == 0:
                    self._data_sample_xml = _ds_xml
                    # 统计样本数据涉及的表数量（每个 "表名:" 标记）
                    self._data_sample_count = max(_ds_xml.count('表名:') + _ds_xml.count('Table:'), 1)
                # 从 sql_examples_xml 中移除 data-sample 部分
                self._sql_examples_xml = self._sql_examples_xml.replace(_ds_xml, '').strip()

        self._terminology_count = self._raw_terminology_count or (self._terminologies_xml.count('<terminology>') if self._terminologies_xml else 0)
        # SQL示例 XML 使用 <sql-example>（连字符），不是 <sql_example>（下划线）
        self._sql_example_count = self._sql_examples_xml.count('<sql-example>') if self._sql_examples_xml else 0
        # 调试日志：确认 RAG 知识是否正确到达 PromptBuilder
        logger.info(
            f"[PromptBuilder.set_rag_knowledge] "
            f"terminologies_xml_len={len(self._terminologies_xml)}, "
            f"sql_examples_xml_len={len(self._sql_examples_xml)}, "
            f"terminology_count={self._terminology_count}, "
            f"sql_example_count={self._sql_example_count}"
        )
        # 提取术语名称列表（供前端展示）
        self._injected_terminologies = []
        if self._terminologies_xml:
            # 按 <terminology>...</terminology> 分组提取
            term_blocks = re.findall(r'<terminology>(.*?)</terminology>', self._terminologies_xml, re.DOTALL)
            for block in term_blocks:
                words = re.findall(r'<word>\s*(?:<!\[CDATA\[)?\s*(.+?)\s*(?:\]\]>)?\s*</word>', block)
                words = [w.strip() for w in words if w.strip()]
                if words:
                    self._injected_terminologies.append({
                        'word': words[0],
                        'synonyms': words[1:] if len(words) > 1 else [],
                    })
            self._injected_terminologies = self._injected_terminologies[:10]
        # 提取SQL示例问题列表（供前端展示）
        self._injected_sql_examples = []
        if self._sql_examples_xml:
            # 匹配 <question> 子标签（在 <sql-example> 内部）
            sql_matches = re.findall(r'<question>\s*<!\[CDATA\[\s*(.+?)\s*\]\]>\s*</question>', self._sql_examples_xml)
            if not sql_matches:
                # 备用：无 CDATA 包裹的情况
                sql_matches = re.findall(r'<question>\s*(.+?)\s*</question>', self._sql_examples_xml, re.DOTALL)
            self._injected_sql_examples = [q.strip()[:60] for q in sql_matches[:5]]

    def set_document_chunks(self, doc_chunks: list = None, doc_context_xml: str = ''):
        """设置 PDF 文档片段检索结果（仅 PDF 数据源）"""
        self._doc_chunk_count = len(doc_chunks) if doc_chunks else 0
        self._doc_context_xml = doc_context_xml or ''

    def set_data_sample(self, table_count: int = 0, data_sample_xml: str = ''):
        """设置数据样本"""
        self._data_sample_count = table_count
        self._data_sample_xml = data_sample_xml or ''

    def set_schema(self, schema: str):
        """设置数据库 Schema（直接注入）"""
        self._schema = schema or ''

    def set_custom_prompts(self, content: str, details: List[Dict] = None):
        """设置自定义提示词（关键词匹配结果）"""
        self._custom_prompt_content = content or ''
        self._custom_prompt_details = details or []

    def set_dialogue_context(self, dialogue_tracker, lang: str = 'zh'):
        """从 DialogueStateTracker 提取对话上下文"""
        try:
            _en = lang.lower().startswith('en') if lang else False
            if dialogue_tracker and dialogue_tracker.turns:
                ctx = dialogue_tracker.get_dialogue_context(max_turns=3)
                if ctx.get('total_turns', 0) > 0:
                    parts = []
                    parts.append(f"{'Turn' if _en else '当前对话轮次'}: {ctx['total_turns']}")
                    parts.append(f"{'Intent' if _en else '当前意图'}: {ctx['current_intent']}")
                    if ctx.get('current_topic'):
                        parts.append(f"{'Topic' if _en else '当前话题'}: {ctx['current_topic']}")
                    if ctx.get('active_entities'):
                        parts.append(f"{'Entities' if _en else '活跃实体'}: {', '.join(ctx['active_entities'][:5])}")
                    recent_qs = ctx.get('recent_questions', [])
                    if len(recent_qs) > 1:
                        parts.append(f"{'Recent questions' if _en else '近期问题'}: {'; '.join(recent_qs[-3:])}")
                    ctx_refs = ctx.get('context_references', [])
                    if ctx_refs:
                        ref_hints = [f"{r['type']}: {r['resolved']}" for r in ctx_refs if r.get('resolved')]
                        if ref_hints:
                            parts.append(f"{'Context refs' if _en else '上下文引用'}: {'; '.join(ref_hints)}")
                    self._dialogue_context_parts = parts
                    self._has_dialogue_context = True
        except Exception as e:
            logger.error(f"PromptBuilder: Failed to extract dialogue context: {e}")

    def set_decomposition(self, decompose_result: Dict, lang: str = 'zh'):
        """设置查询分解结果（复杂查询的子任务提示）"""
        try:
            _en = lang.lower().startswith('en') if lang else False
            if decompose_result.get('is_complex') and len(decompose_result.get('sub_tasks', [])) >= 2:
                task_type = decompose_result['task_type']
                sub_tasks = decompose_result['sub_tasks']
                parts = [f"{'Query type' if _en else '查询类型'}: {task_type}"]
                parts.append(f"{'Sub-tasks' if _en else '子任务分解'}: {'; '.join(sub_tasks[:4])}")
                if task_type == 'comparison':
                    parts.append("Hint: Use CASE WHEN or JOIN to compare in a single SQL" if _en else
                                 "提示: 请在一条SQL中完成对比查询，使用CASE WHEN或JOIN实现")
                elif task_type == 'multi_step':
                    parts.append("Hint: Use subquery or CTE to combine multiple steps into one SQL" if _en else
                                 "提示: 请使用子查询或CTE将多个步骤合并为一条SQL")
                self._decomposition_hint = '\n'.join(parts)
        except Exception as e:
            logger.error(f"PromptBuilder: Failed to set decomposition: {e}")

    # ========== 构建消息列表 ==========

    def build_sql_messages(
        self,
        chat_question,
        history_sql_messages: List[Dict] = None,
        enable_query_limit: bool = True,
        count_limit: int = -10,
    ) -> tuple:
        """
        构建 SQL 生成场景的消息列表

        输入：chat_question（含模板参数）、历史消息
        输出：(messages: List[BaseMessage], metadata: PromptMetadata)
        """
        self._build_start = time.time()
        messages = []

        # 1. System Prompt — 模板填充（RAG 知识注入的核心）
        sys_content = chat_question.sql_sys_question(
            chat_question.ds_type if hasattr(chat_question, 'ds_type') else chat_question.engine,
            enable_query_limit
        )
        messages.append(SystemMessage(content=sys_content))

        # 2. 对话上下文注入（多轮对话支持）
        if self._has_dialogue_context and self._dialogue_context_parts:
            dialogue_hint = '\n'.join(self._dialogue_context_parts)
            messages.append(SystemMessage(
                content=f"<dialogue-context>\n{dialogue_hint}\n</dialogue-context>"
            ))

        # 3. 查询分解提示注入（复杂查询支持）
        if self._decomposition_hint:
            messages.append(SystemMessage(
                content=f"<query-decomposition>\n{self._decomposition_hint}\n</query-decomposition>"
            ))

        # 4. 历史消息注入（多轮对话的上下文窗口）
        if history_sql_messages:
            for msg in history_sql_messages[count_limit:]:
                if msg.get('type') == 'human':
                    messages.append(HumanMessage(content=msg['content']))
                elif msg.get('type') == 'ai':
                    messages.append(AIMessage(content=msg['content']))

        # 构建元数据
        metadata = self._build_metadata(sys_content, '', actual_message_count=len(messages))
        return messages, metadata

    def build_analysis_messages(self, chat_question) -> tuple:
        """
        构建数据分析场景的消息列表

        输入：chat_question（含分析数据）
        输出：(messages: List[BaseMessage], metadata: PromptMetadata)
        """
        self._build_start = time.time()
        messages = []

        # 1. System Prompt（含术语 + 自定义提示词）
        sys_content = chat_question.analysis_sys_question(ds_type=chat_question.ds_type)
        messages.append(SystemMessage(content=sys_content))

        # 2. 对话上下文
        if self._has_dialogue_context and self._dialogue_context_parts:
            dialogue_hint = '\n'.join(self._dialogue_context_parts)
            messages.append(SystemMessage(
                content=f"<dialogue-context>\n{dialogue_hint}\n</dialogue-context>"
            ))

        # 3. User Prompt（含数据和字段）
        user_content = chat_question.analysis_user_question()
        messages.append(HumanMessage(content=user_content))

        metadata = self._build_metadata(sys_content, user_content, actual_message_count=len(messages))
        return messages, metadata

    def build_prediction_messages(self, chat_question) -> tuple:
        """
        构建数据预测场景的消息列表

        输入：chat_question（含预测数据）
        输出：(messages: List[BaseMessage], metadata: PromptMetadata)
        """
        self._build_start = time.time()
        messages = []

        # 1. System Prompt（含术语 + 自定义提示词）
        sys_content = chat_question.predict_sys_question(ds_type=chat_question.ds_type)
        messages.append(SystemMessage(content=sys_content))

        # 2. 对话上下文
        if self._has_dialogue_context and self._dialogue_context_parts:
            dialogue_hint = '\n'.join(self._dialogue_context_parts)
            messages.append(SystemMessage(
                content=f"<dialogue-context>\n{dialogue_hint}\n</dialogue-context>"
            ))

        # 3. User Prompt
        user_content = chat_question.predict_user_question()
        messages.append(HumanMessage(content=user_content))

        metadata = self._build_metadata(sys_content, user_content, actual_message_count=len(messages))
        return messages, metadata

    def build_direct_answer_messages(self, chat_question, intent: str = 'general_chat') -> tuple:
        """
        构建直接回答场景的消息列表（general_chat / term_explanation 等）

        输入：chat_question + 意图类型
        输出：(messages: List[BaseMessage], metadata: PromptMetadata)
        """
        self._build_start = time.time()
        messages = []

        # 1. System Prompt
        sys_content = chat_question.direct_answer_sys_question(intent=intent)
        messages.append(SystemMessage(content=sys_content))

        # 2. User Prompt
        user_content = chat_question.direct_answer_user_question()
        messages.append(HumanMessage(content=user_content))

        metadata = self._build_metadata(sys_content, user_content, actual_message_count=len(messages))
        return messages, metadata

    def build_chart_messages(self, chat_question, chart_type: str = None) -> tuple:
        """
        构建图表生成场景的消息列表

        输入：chat_question（含 SQL）+ 推荐图表类型
        输出：(messages: List[BaseMessage], metadata: PromptMetadata)
        """
        self._build_start = time.time()
        messages = []

        sys_content = chat_question.chart_sys_question()
        messages.append(SystemMessage(content=sys_content))

        user_content = chat_question.chart_user_question(chart_type=chart_type)
        messages.append(HumanMessage(content=user_content))

        metadata = self._build_metadata(sys_content, user_content, actual_message_count=len(messages))
        metadata.prompt_type = 'chart_generation'
        return messages, metadata

    # ========== 记录到思考过程 ==========

    def record_to_thinking(self, thinking_process, metadata: PromptMetadata = None):
        """将构建结果记录到思考过程（供前端展示）"""
        if not thinking_process or not metadata:
            return
        try:
            from apps.chat.thinking.thinking_integration import record_prompt_construction_stage
            record_prompt_construction_stage(
                thinking=thinking_process,
                prompt_type=metadata.prompt_type,
                system_prompt_preview=metadata.system_prompt_preview,
                user_prompt_preview=metadata.user_prompt_preview,
                model_name=metadata.model_name,
                rag_components=metadata.to_rag_components(),
                message_count=metadata.message_count,
                total_prompt_length=metadata.total_prompt_length,
                component_counts=metadata.to_component_counts(),
                custom_prompts=metadata.custom_prompts,
                system_prompt_length=metadata.system_prompt_length,
                user_prompt_length=metadata.user_prompt_length,
            )
        except Exception as e:
            logger.error(f"PromptBuilder: Failed to record thinking: {e}")

    # ========== 内部方法 ==========

    def _build_metadata(self, sys_content: str, user_content: str, actual_message_count: int = 0) -> PromptMetadata:
        """构建元数据"""
        build_ms = int((time.time() - self._build_start) * 1000) if self._build_start else 0

        components = [
            PromptComponent(
                name='terminologies',
                injected=bool(self._terminologies_xml),
                source='rag_vector',
                count=self._terminology_count,
                char_length=len(self._terminologies_xml),
            ),
            PromptComponent(
                name='sql_examples',
                injected=bool(self._sql_example_count > 0),
                source='rag_vector',
                count=self._sql_example_count,
                char_length=len(self._sql_examples_xml),
            ),
            PromptComponent(
                name='document_chunks',
                injected=bool(self._doc_chunk_count > 0),
                source='rag_vector',
                count=self._doc_chunk_count,
                char_length=len(self._doc_context_xml),
            ),
            PromptComponent(
                name='data_sample',
                injected=bool(self._data_sample_count > 0),
                source='direct',
                count=self._data_sample_count,
                char_length=len(self._data_sample_xml),
            ),
            PromptComponent(
                name='schema',
                injected=bool(self._schema),
                source='direct',
                char_length=len(self._schema),
            ),
            PromptComponent(
                name='custom_prompt',
                injected=bool(self._custom_prompt_content),
                source='intent_inject',
                char_length=len(self._custom_prompt_content),
            ),
            PromptComponent(
                name='dialogue_context',
                injected=self._has_dialogue_context,
                source='context',
            ),
        ]

        sys_len = len(sys_content)
        user_len = len(user_content)
        total_len = sys_len + user_len

        # 调试日志：确认 metadata 中的组件状态
        logger.info(
            f"[PromptBuilder._build_metadata] "
            f"terminologies: injected={bool(self._terminologies_xml)}, count={self._terminology_count}, len={len(self._terminologies_xml)}; "
            f"sql_examples: injected={bool(self._sql_example_count > 0)}, count={self._sql_example_count}, len={len(self._sql_examples_xml)}; "
            f"schema: injected={bool(self._schema)}, len={len(self._schema)}; "
            f"sys_content_len={len(sys_content)}, has_terminology_tag={'<terminology>' in sys_content}"
        )

        # 使用实际消息数量而非硬编码 2
        # 对话上下文、查询分解、历史消息等都会增加消息数
        msg_count = actual_message_count if actual_message_count > 0 else 2

        return PromptMetadata(
            prompt_type=self.prompt_type,
            model_name=self.model_name,
            system_prompt_preview=sys_content,
            user_prompt_preview=user_content,
            system_prompt_length=sys_len,
            user_prompt_length=user_len,
            total_prompt_length=total_len,
            message_count=msg_count,
            components=components,
            custom_prompts=self._custom_prompt_details,
            build_duration_ms=build_ms,
            injected_terminologies=getattr(self, '_injected_terminologies', []),
            injected_sql_examples=getattr(self, '_injected_sql_examples', []),
            dialogue_context_text=f"<dialogue-context>\n{chr(10).join(self._dialogue_context_parts)}\n</dialogue-context>" if self._dialogue_context_parts else '',
        )
