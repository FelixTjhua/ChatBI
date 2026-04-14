import concurrent
import json
import os
import re
import time
import traceback
import urllib.parse
import warnings
from concurrent.futures import ThreadPoolExecutor, Future
from datetime import datetime
from typing import Any, List, Optional, Union, Dict, Iterator

import orjson
import pandas as pd
import requests
import sqlparse
from langchain.chat_models.base import BaseChatModel
from langchain_community.utilities import SQLDatabase
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage, BaseMessageChunk
from sqlalchemy import and_, select
from sqlalchemy.orm import sessionmaker, scoped_session
from common.chatbi.custom_prompt import find_custom_prompts, find_relevant_custom_prompts, count_custom_prompts, CustomPromptTypeEnum
from common.chatbi.license import ChatBILicenseUtil
from sqlmodel import Session

from apps.ai_model.model_factory import LLMConfig, LLMFactory, get_default_config
from apps.chat.crud.chat import save_question, \
    save_error_message, save_sql_exec_data, \
    finish_record, save_analysis_answer, save_predict_answer, save_predict_data, \
    save_select_datasource_answer, save_recommend_question_answer, \
    get_old_questions, save_analysis_predict_record, rename_chat, \
    list_generate_sql_logs, list_generate_chart_logs, start_log, end_log, \
    get_last_execute_sql_error, format_json_data, save_rag_results, \
    save_thinking_process, save_intent, merge_rag_custom_prompts
from apps.chat.models.chat_model import ChatQuestion, ChatRecord, Chat, RenameChat, ChatLog, OperationEnum, \
    ChatFinishStep, AxisObj
from apps.chat.thinking.rag_thinking import (
    RAGThinkingProcess, record_rag_retrieval
)
from apps.chat.thinking.thinking_integration import (
    record_execution_stage
)
from apps.chat.thinking.query_rewriter import QueryRewriter
from apps.chat.thinking.context_compressor import ContextCompressor
from apps.chat.thinking.rag_evidence_filter import filter_rag_evidence
from apps.chat.thinking.dialogue_state import DialogueStateTracker
from apps.chat.thinking.unified_rag_executor import (
    UnifiedRAGExecutor, PipelineContext, DesignIntent,
    get_available_components, get_execution_path, map_to_design_intent,
    format_pdf_context, get_pdf_source_summary,
)
from apps.data_training.crud.data_training import get_training_template
from apps.datasource.crud.datasource import get_table_schema, get_table_schema_with_details
from apps.datasource.crud.permission import is_normal_user
from apps.datasource.embedding.ds_embedding import get_ds_embedding
from common.utils.error_sanitizer import sanitize_error_message
from apps.datasource.models.datasource import CoreDatasource
from apps.db.db import exec_sql, get_version, check_connection
from apps.system.crud.assistant import AssistantOutDs, AssistantOutDsFactory, get_assistant_ds
from apps.system.schemas.system_schema import AssistantOutDsSchema
from apps.terminology.crud.terminology import get_terminology_template
from common.core.config import settings
from common.core.db import engine
from common.core.deps import CurrentAssistant, CurrentUser
from common.error import SingleMessageError, ChatBIDBError, ChatBIDBConnectionError
from common.utils.data_format import DataFormat
from common.utils.utils import ChatBILogUtil, extract_json_robust, prepare_for_orjson

from apps.chat.task.sql_generator import SQLGeneratorMixin
from apps.chat.task.chart_generator import ChartGeneratorMixin
from apps.chat.task.analysis_service import AnalysisServiceMixin
from apps.chat.task.prediction_service import PredictionServiceMixin
from apps.chat.task.rag_mixin import RAGMixin

warnings.filterwarnings("ignore")

base_message_count_limit = 6

executor = ThreadPoolExecutor(max_workers=50)

dynamic_ds_types = [1, 3]
dynamic_subsql_prefix = 'select * from chatbi_dynamic_temp_table_'

session_maker = scoped_session(sessionmaker(bind=engine, class_=Session))


def _extract_friendly_table_names(sql: str, strip_hash_suffix: bool = False) -> list:
    """从 SQL 中提取友好的表名列表，去除引号和子查询等非表名内容。"""
    if not sql:
        return []
    raw = re.findall(r'(?:FROM|JOIN)\s+(\S+)', sql, re.IGNORECASE)
    seen = set()
    result = []
    for name in raw:
        clean = name.strip('"').strip("'").strip('`')
        # 跳过子查询括号、SQL关键字等非表名
        if not clean or clean.startswith('(') or clean.upper() in ('SELECT', 'LATERAL', 'UNNEST'):
            continue
        # Excel/CSV: 去掉内部 hash 后缀
        if strip_hash_suffix:
            parts = clean.rsplit('_', 1)
            if len(parts) == 2 and len(parts[1]) == 10:
                clean = parts[0]
        if clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result


def _build_data_features(result: dict) -> dict:
    """从SQL执行结果中提取数据特征，用于中置推荐问题的数据源感知。"""
    features: dict = {}
    if not result:
        return features
    data = result.get('data', [])
    features['row_count'] = len(data)
    if not data or not isinstance(data, list) or not data[0]:
        return features
    first_row = data[0] if isinstance(data[0], dict) else {}
    for key, value in first_row.items():
        key_lower = str(key).lower()
        if any(kw in key_lower for kw in ['date', 'time', '日期', '时间', 'month', '月', 'year', '年']):
            features['has_time_column'] = True
        if isinstance(value, (int, float)):
            features['has_numeric_column'] = True
        elif isinstance(value, str):
            cleaned = value.replace('.', '', 1).replace('-', '', 1)
            if cleaned.isdigit():
                features['has_numeric_column'] = True
            else:
                features['has_categorical_column'] = True
        elif value is not None and not isinstance(value, (int, float)):
            features['has_categorical_column'] = True
    return features


def build_terminology_template_from_details(terminology_details: List[Dict], ds_type: str = '') -> str:
    """从过滤+重排序后的术语详情列表构建XML模板（避免重新查数据库绕过质量过滤）"""
    if not terminology_details:
        return ''
    from apps.terminology.crud.terminology import to_xml_string as term_to_xml, get_base_terminology_template
    _is_pdf = (ds_type or '').lower() == 'pdf'

    # 按 word 去重，同时聚合同义词关系
    # 同一父术语下的多条命中（主术语+同义词）合并为一个条目
    seen_words = set()
    merged = {}  # key: 主术语 word, value: {'words': [...], 'description': ..., 'sql_mapping': ...}
    for t in terminology_details:
        word = t.get('word', '')
        if not word or word in seen_words:
            continue
        seen_words.add(word)
        synonyms = t.get('synonyms', [])
        # 构建完整的 words 列表：主术语 + 同义词
        all_words = [word] + [s for s in synonyms if s and s != word]
        # 用第一个出现的 word 作为 key 做合并（同义词可能各自命中）
        # 检查是否已有同组术语被收录（通过同义词交集判断）
        merge_key = None
        for existing_key, existing_entry in merged.items():
            existing_words_set = set(existing_entry['words'])
            if word in existing_words_set or existing_words_set & set(all_words):
                merge_key = existing_key
                break
        if merge_key:
            # 合并到已有条目：补充新的同义词
            for w in all_words:
                if w not in merged[merge_key]['_words_set']:
                    merged[merge_key]['words'].append(w)
                    merged[merge_key]['_words_set'].add(w)
        else:
            merged[word] = {
                'words': all_words,
                '_words_set': set(all_words),
                'description': t.get('description', ''),
                'sql_mapping': '' if _is_pdf else t.get('sql_mapping', ''),
            }

    converted = []
    for entry in merged.values():
        converted.append({
            'words': entry['words'],
            'description': entry['description'],
            'sql_mapping': entry['sql_mapping'],
        })
    xml_str = term_to_xml(converted)
    return get_base_terminology_template().format(terminologies=xml_str)


def build_training_template_from_details(training_details: List[Dict]) -> str:
    """从过滤+重排序后的SQL示例详情列表构建XML模板（避免重新查数据库绕过质量过滤）

     原来调用 get_training_template 会重新执行数据库查询，
    返回未经质量过滤和重排序的结果，导致注入Prompt的SQL示例与RAG流水线处理结果不一致。
    """
    if not training_details:
        return ''
    from apps.data_training.crud.data_training import to_xml_string as train_to_xml, get_base_data_training_template
    # 转换为 to_xml_string 期望的格式: [{'question': '...', 'suggestion-answer': '...'}]
    converted = []
    for e in training_details:
        converted.append({
            'question': e.get('question', ''),
            'suggestion-answer': e.get('sql', '') or e.get('description', ''),
        })
    xml_str = train_to_xml(converted)
    return get_base_data_training_template().format(data_training=xml_str)


class LLMService(SQLGeneratorMixin, ChartGeneratorMixin, AnalysisServiceMixin, PredictionServiceMixin, RAGMixin):
    """LLM 服务主类"""
    ds: CoreDatasource
    chat_question: ChatQuestion
    record: ChatRecord
    config: LLMConfig
    llm: BaseChatModel
    # 类型注解声明（不使用可变默认值）
    # 可变对象（list/dict）在类级别声明会被所有实例共享，导致数据串扰
    sql_message: List[Union[BaseMessage, dict[str, Any]]]
    chart_message: List[Union[BaseMessage, dict[str, Any]]]

    # session: Session = db_session
    current_user: CurrentUser
    current_assistant: Optional[CurrentAssistant] = None
    out_ds_instance: Optional[AssistantOutDs] = None
    change_title: bool = False

    generate_sql_logs: List[ChatLog]
    generate_chart_logs: List[ChatLog]

    current_logs: dict[OperationEnum, ChatLog]

    chunk_list: List[str]
    future: Future

    last_execute_sql_error: str = None
    
    # RAG增强的思考过程记录器
    thinking_process: Optional[RAGThinkingProcess] = None
    # RAG检索结果缓存（供RAG评估使用）
    _rag_terminologies: Optional[list] = None
    _rag_sql_examples: Optional[list] = None
    # 对话状态追踪器
    dialogue_tracker: Optional[DialogueStateTracker] = None
    
    # _dialogue_history_cache 是类级别共享的可变 dict，
    import threading as _threading
    from collections import OrderedDict as _OrderedDict
    _dialogue_history_cache: _OrderedDict = _OrderedDict()
    _dialogue_history_cache_lock = _threading.Lock()
    _DIALOGUE_CACHE_TTL = 60  # 缓存有效期（秒）
    _DIALOGUE_CACHE_MAX_SIZE = 200  # 缓存最大条目数，防止无限增长

    def __init__(self, session: Session, current_user: CurrentUser, chat_question: ChatQuestion,
                 current_assistant: Optional[CurrentAssistant] = None, no_reasoning: bool = False,
                 embedding: bool = False, config: LLMConfig = None):
        # 在实例级别初始化可变属性，避免类级别共享
        self.sql_message = []
        self.chart_message = []
        self.generate_sql_logs = []
        self.generate_chart_logs = []
        self.current_logs = {}
        self.chunk_list = []
        self._table_match_details = {}  # 表检索详情（供思考过程展示）
        self.current_user = current_user
        self.current_assistant = current_assistant
        chat_id = chat_question.chat_id
        chat: Chat | None = session.get(Chat, chat_id)
        if not chat:
            raise SingleMessageError(f"Chat with id {chat_id} not found")
        ds: CoreDatasource | AssistantOutDsSchema | None = None
        if chat.datasource:
            # Get available datasource
            if current_assistant and current_assistant.type in dynamic_ds_types:
                self.out_ds_instance = AssistantOutDsFactory.get_instance(current_assistant)
                ds = self.out_ds_instance.get_ds(chat.datasource)
                if not ds:
                    raise SingleMessageError("No available datasource configuration found")
                chat_question.engine = ds.type + get_version(ds)
                chat_question.ds_type = ds.type
                chat_question.db_schema = self.out_ds_instance.get_db_schema(ds.id, chat_question.question)
            else:
                ds = session.get(CoreDatasource, chat.datasource)
                if not ds:
                    raise SingleMessageError("No available datasource configuration found")
                chat_question.engine = (ds.type_name if ds.type not in ('excel', 'csv', 'pdf') else 'PostgreSQL') + get_version(ds)
                chat_question.ds_type = ds.type
                _perf_schema_start = time.time()
                _schema_details = get_table_schema_with_details(session=session, current_user=current_user, ds=ds,
                                                               question=chat_question.question, embedding=embedding)
                chat_question.db_schema = _schema_details['schema']
                # 缓存表匹配详情，供思考过程展示
                self._table_match_details = _schema_details
                ChatBILogUtil.info(f"[PERF] __init__ get_table_schema: {time.time() - _perf_schema_start:.2f}s")

        self.generate_sql_logs = list_generate_sql_logs(session=session, chart_id=chat_id)
        self.generate_chart_logs = list_generate_chart_logs(session=session, chart_id=chat_id)

        self.change_title = len(self.generate_sql_logs) == 0

        chat_question.lang = get_lang_name(current_user.language)

        self.ds = (
            ds if isinstance(ds, AssistantOutDsSchema) else CoreDatasource(**ds.model_dump())) if ds else None
        self.chat_question = chat_question
        self.config = config
        if no_reasoning:
            # only work while using qwen
            if self.config.additional_params:
                if self.config.additional_params.get('extra_body'):
                    if self.config.additional_params.get('extra_body').get('enable_thinking'):
                        del self.config.additional_params['extra_body']['enable_thinking']

        self.chat_question.ai_modal_id = self.config.model_id
        self.chat_question.ai_modal_name = self.config.model_name

        # Create LLM instance through factory
        llm_instance = LLMFactory.create_llm(self.config)
        self.llm = llm_instance.llm

        # get last_execute_sql_error
        last_execute_sql_error = get_last_execute_sql_error(session, self.chat_question.chat_id)
        if last_execute_sql_error:
            self.chat_question.error_msg = f'''<error-msg>
{last_execute_sql_error}
</error-msg>'''
        else:
            self.chat_question.error_msg = ''
        
        # 初始化RAG增强的思考过程记录器
        self.thinking_process = RAGThinkingProcess()
        self.thinking_process.set_question(self.chat_question.question)
        # RAG 永远开启（对齐 SQLBot）
        self.thinking_process.set_rag_enabled(True)
        
        # 初始化对话状态追踪器
        self.dialogue_tracker = DialogueStateTracker()
        
        # 使用Chat级别缓存避免重复加载对话历史
        try:
            import time as _time
            _cache_key = (current_user.id, chat_id)
            _cached = None
            with self.__class__._dialogue_history_cache_lock:
                if _cache_key in self.__class__._dialogue_history_cache:
                    _ts, _records = self.__class__._dialogue_history_cache[_cache_key]
                    if _time.time() - _ts < self.__class__._DIALOGUE_CACHE_TTL:
                        _cached = _records
                        # 命中时移到末尾，维护 LRU 顺序
                        self.__class__._dialogue_history_cache.move_to_end(_cache_key)
                    else:
                        del self.__class__._dialogue_history_cache[_cache_key]
            
            if _cached is not None:
                if _cached:
                    self.dialogue_tracker.load_history(_cached)
            else:
                from apps.chat.crud.chat import list_chat_records_for_dialogue
                history_records = list_chat_records_for_dialogue(session, chat_id, max_turns=10)
                with self.__class__._dialogue_history_cache_lock:
                    # 使用 OrderedDict.popitem(last=False) 实现 O(1) LRU 淘汰
                    if len(self.__class__._dialogue_history_cache) >= self.__class__._DIALOGUE_CACHE_MAX_SIZE:
                        self.__class__._dialogue_history_cache.popitem(last=False)
                    self.__class__._dialogue_history_cache[_cache_key] = (_time.time(), history_records)
                if history_records:
                    self.dialogue_tracker.load_history(history_records)
        except ImportError:
            # list_chat_records_for_dialogue 可能尚未定义，使用已有的日志记录
            try:
                if self.generate_sql_logs:
                    history = []
                    for log in self.generate_sql_logs[-10:]:
                        msg_list = log.full_message if hasattr(log, 'full_message') and log.full_message else []
                        for msg in (msg_list if isinstance(msg_list, list) else []):
                            if isinstance(msg, dict) and msg.get('type') == 'human':
                                history.append({'question': msg.get('content', ''), 'sql': '', 'sql_success': True})
                    if history:
                        self.dialogue_tracker.load_history(history)
            except Exception as e:
                ChatBILogUtil.error(f"Failed to load dialogue history from logs: {e}")
        except Exception as e:
            ChatBILogUtil.error(f"Failed to load dialogue history: {e}")

    @classmethod
    async def create(cls, *args, **kwargs):
        config: LLMConfig = await get_default_config()
        instance = cls(*args, **kwargs, config=config)
        return instance
    
    def get_json_mode_llm(self) -> BaseChatModel:
        """创建一个强制JSON模式的LLM实例（用于SQL生成等需要结构化输出的场景）"""
        # 创建新的配置（避免修改原配置）
        json_config_dict = {
            'model_id': self.config.model_id,
            'model_type': self.config.model_type,
            'model_name': self.config.model_name,
            'api_key': self.config.api_key,
            'api_base_url': self.config.api_base_url,
            'additional_params': {
                **self.config.additional_params,
                'force_json_mode': True,
                'temperature': 0.1,  # 降低temperature提高确定性
                'top_p': 0.9
            }
        }
        
        json_config = LLMConfig(**json_config_dict)
        
        # 创建新的LLM实例
        llm_instance = LLMFactory.create_llm(json_config)
        
        ChatBILogUtil.info(f"Created JSON-mode LLM with temperature=0.1 for structured output")
        return llm_instance.llm

    def _build_table_match_items(self) -> list:
        """从 _table_match_details 构建表检索质量评估数据"""
        details = getattr(self, '_table_match_details', {})
        selected = details.get('selected_tables', [])
        sims = details.get('similarities', [])
        return [{'name': selected[i], 'similarity': sims[i] if i < len(sims) else 0.0}
                for i in range(len(selected))]

    def is_running(self, timeout=0.5):
        try:
            r = concurrent.futures.wait([self.future], timeout)
            if len(r.not_done) > 0:
                return True
            else:
                return False
        except Exception as e:
            return True

    def init_messages(self):
        """
        构建 SQL 生成和图表生成的消息列表。
        
        使用 PromptBuilder 模块完成 RAG 增强阶段的提示词组装：
        1. 将 RAG 检索结果（术语、SQL示例）注入模板占位符
        2. 注入数据库 Schema、自定义提示词、对话上下文
        3. 组装完整的 LLM 输入消息列表
        """
        from apps.chat.thinking.prompt_builder import PromptBuilder
        
        # 将系统检测到的意图注入到 chat_question，供 SQL 生成 prompt 使用
        _early = getattr(self, '_early_intent', '')
        if _early and not self.chat_question.detected_intent:
            self.chat_question.detected_intent = _early
        
        last_sql_messages: List[dict[str, Any]] = self.generate_sql_logs[-1].messages if len(
            self.generate_sql_logs) > 0 else []

        count_limit = 0 - base_message_count_limit

        # ========== SQL 消息列表构建（通过 PromptBuilder）==========
        self.sql_prompt_builder = PromptBuilder(
            prompt_type='sql_generation',
            model_name=self.chat_question.ai_modal_name or ''
        )
        
        # 设置 RAG 知识组件
        ChatBILogUtil.info(
            f"[init_messages] chat_question.terminologies len={len(self.chat_question.terminologies or '')}, "
            f"chat_question.data_training len={len(self.chat_question.data_training or '')}, "
            f"has_terminology_tag={'<terminology>' in (self.chat_question.terminologies or '')}, "
            f"has_sql_example_tag={'<sql-example>' in (self.chat_question.data_training or '')}"
        )
        self.sql_prompt_builder.set_rag_knowledge(
            terminologies_xml=self.chat_question.terminologies,
            sql_examples_xml=self.chat_question.data_training,
            raw_terminology_count=getattr(self.chat_question, 'raw_terminology_count', 0),
        )
        self.sql_prompt_builder.set_schema(self.chat_question.db_schema)
        self.sql_prompt_builder.set_custom_prompts(self.chat_question.custom_prompt)
        
        # 设置对话上下文
        self.sql_prompt_builder.set_dialogue_context(
            getattr(self, 'dialogue_tracker', None),
            lang=self.chat_question.lang,
        )
        
        # 设置查询分解
        try:
            decompose_result = getattr(self, '_decompose_result', None)
            if decompose_result is None:
                decompose_result = QueryRewriter.decompose_complex_query(self.chat_question.question)
            self.sql_prompt_builder.set_decomposition(decompose_result, lang=self.chat_question.lang)
        except Exception as e:
            ChatBILogUtil.error(f"Failed to decompose query: {e}")
        
        # 构建消息列表
        self.sql_message, self._sql_prompt_metadata = self.sql_prompt_builder.build_sql_messages(
            chat_question=self.chat_question,
            history_sql_messages=last_sql_messages,
            enable_query_limit=settings.GENERATE_SQL_QUERY_LIMIT_ENABLED,
            count_limit=count_limit,
        )

        # ========== 图表消息列表构建 ==========
        last_chart_messages: List[dict[str, Any]] = self.generate_chart_logs[-1].messages if len(
            self.generate_chart_logs) > 0 else []

        self.chart_message = []
        self.chart_message.append(SystemMessage(content=self.chat_question.chart_sys_question()))

        if last_chart_messages is not None and len(last_chart_messages) > 0:
            for last_chart_message in last_chart_messages:
                _msg: BaseMessage
                if last_chart_message.get('type') == 'human':
                    _msg = HumanMessage(content=last_chart_message.get('content'))
                    self.chart_message.append(_msg)
                elif last_chart_message.get('type') == 'ai':
                    _msg = AIMessage(content=last_chart_message.get('content'))
                    self.chart_message.append(_msg)

    def init_record(self, session: Session) -> ChatRecord:
        self.record = save_question(session=session, current_user=self.current_user, question=self.chat_question)
        return self.record

    def get_record(self):
        return self.record

    def set_record(self, record: ChatRecord):
        self.record = record

    def _apply_context_compression(
        self,
        rag_enabled: bool,
        terminology_results: List = None,
        sql_example_results: List = None,
        max_total_tokens: int = 800,
        tag: str = "",
    ) -> None:
        """共享的上下文压缩逻辑，消除 run_task 中 select_ds / existing_ds 两条路径的重复代码"""
        if not rag_enabled:
            return
        try:
            _sql_gen_config = ContextCompressor.get_config('sql_generation')

            # 应用RAG评估反馈闭环调整参数
            # 上一轮查询的 _save_thinking_process_with_eval 会将反馈存入 self._rag_feedback_adjustments
            _feedback = getattr(self, '_rag_feedback_adjustments', None)
            if _feedback and _feedback.get('feedback_applied'):
                _budget_ratio = _feedback.get('compression_budget_ratio', 1.0)
                if _budget_ratio != 1.0:
                    max_total_tokens = int(max_total_tokens * _budget_ratio)
                    ChatBILogUtil.info(
                        f"{tag} Feedback loop: adjusted max_total_tokens to {max_total_tokens} "
                        f"(ratio={_budget_ratio})"
                    )

            compression_result = ContextCompressor.compress_with_reranking(
                terminologies=self.chat_question.terminologies,
                sql_examples=self.chat_question.data_training,
                schema=self.chat_question.db_schema,
                question=self.chat_question.question,
                terminology_results=terminology_results or [],
                sql_example_results=sql_example_results or [],
                max_total_tokens=max_total_tokens,
                config=_sql_gen_config,
            )
            if compression_result.get('compression_applied'):
                self.chat_question.terminologies = compression_result['terminologies']
                self.chat_question.data_training = compression_result['sql_examples']
                self.chat_question.db_schema = compression_result['schema']
                ChatBILogUtil.info(
                    f"{tag} Context compressed (rerank-aware): "
                    f"ratio={compression_result['stats'].get('compression_ratio', 1.0)}, "
                    f"dynamic_budget={compression_result['stats'].get('dynamic_budget', False)}"
                )
                try:
                    from apps.chat.thinking.thinking_integration import record_context_compression_stage
                    record_context_compression_stage(self.thinking_process, {
                        **compression_result['stats'],
                        'token_budget': max_total_tokens,
                    })
                except Exception:
                    pass
            else:
                # 未触发压缩时也记录统计，让思考链可见
                stats = compression_result.get('stats', {})
                if stats:
                    ChatBILogUtil.info(
                        f"{tag} Context within budget, compression skipped "
                        f"(tokens≈{stats.get('estimated_tokens', '?')}, budget={max_total_tokens})"
                    )
                    try:
                        from apps.chat.thinking.thinking_integration import record_context_compression_stage
                        record_context_compression_stage(self.thinking_process, {
                            **stats,
                            'compression_skipped': True,
                            'reason': 'within_budget',
                            'token_budget': max_total_tokens,
                        })
                    except Exception:
                        pass
        except Exception as e:
            ChatBILogUtil.error(f"{tag} Context compression failed, using original context: {e}")

    def generate_recommend_questions_task(self, _session: Session):

        # get schema
        ds_type = self.ds.type if self.ds else 'database'
        if self.ds and not self.chat_question.db_schema:
            self.chat_question.db_schema = self.out_ds_instance.get_db_schema(
                self.ds.id, self.chat_question.question) if self.out_ds_instance else get_table_schema(
                session=_session,
                current_user=self.current_user, ds=self.ds,
                question=self.chat_question.question,
                embedding=False)

        # 使用统一的质量过滤流程注入RAG术语知识（与主查询流程一致）
        if self.ds and not self.chat_question.terminologies:
            try:
                oid = self.ds.oid if isinstance(self.ds, CoreDatasource) else 1
                ds_id = self.ds.id if isinstance(self.ds, CoreDatasource) else None
                from apps.terminology.crud.terminology import select_terminology_by_word_with_details
                terminology_details = select_terminology_by_word_with_details(
                    _session, self.chat_question.question or '', oid, ds_id
                )
                if terminology_details:
                    filtered, _ = filter_rag_evidence(
                        [{**t, 'source_type': 'terminology'} for t in terminology_details],
                        threshold=0.35
                    )
                    terminology_details = [e for e in filtered if e.get('source_type') == 'terminology']
                    self.chat_question.terminologies = build_terminology_template_from_details(terminology_details, ds_type=ds_type)
                else:
                    self.chat_question.terminologies = ''
            except Exception as e:
                ChatBILogUtil.error(f"Failed to load terminologies for recommend questions: {e}")
                self.chat_question.terminologies = ''

        # 注入PDF文档知识库内容（让推荐问题能参考文档中的业务知识）
        doc_knowledge = ''
        _pdf_section_titles = []  # PDF文档的章节标题列表，用于生成更精准的推荐问题
        try:
            oid = self.ds.oid if isinstance(self.ds, CoreDatasource) else 1
            from apps.datasource.document_retrieval import search_document_chunks, format_document_context
            # PDF数据源使用文档名称作为检索查询
            _doc_search_query = self.chat_question.question or ''
            if not _doc_search_query:
                _doc_search_query = self.ds.name if self.ds else 'document overview'
            doc_chunks = search_document_chunks(
                _session, _doc_search_query, oid=oid, top_k=5, similarity_threshold=0.25,
                ds_id=self.ds.id if isinstance(self.ds, CoreDatasource) else None,
            )
            if doc_chunks:
                doc_knowledge = format_document_context(doc_chunks, max_tokens=1500, lang=self.chat_question.lang)
                ChatBILogUtil.info(f"Recommend questions: injected {len(doc_chunks)} document chunks")
            
            # PDF数据源：提取文档章节标题，用于生成基于真实文档内容的推荐问题
            _ds_type_rq = (self.ds.type or '').lower() if self.ds else ''
            if _ds_type_rq == 'pdf':
                try:
                    from apps.datasource.models.document import CoreDocumentChunk, CoreDocument
                    # file_type 存储时带点号前缀（如 ".pdf"），查询时需匹配
                    _pdf_docs = _session.query(CoreDocument).filter(
                        CoreDocument.oid == oid,
                        CoreDocument.file_type.in_(['.pdf', 'pdf'])
                    ).order_by(CoreDocument.id.desc()).limit(3).all()
                    _seen_titles = set()
                    for _pdf_doc in _pdf_docs:
                        _pdf_chunks = _session.query(CoreDocumentChunk).filter(
                            CoreDocumentChunk.document_id == _pdf_doc.id,
                            CoreDocumentChunk.section_title.isnot(None),
                            CoreDocumentChunk.section_title != ''
                        ).distinct(CoreDocumentChunk.section_title).limit(20).all()
                        for _pc in _pdf_chunks:
                            _title = _pc.section_title.strip()
                            if _title and _title not in _seen_titles and len(_title) >= 2:
                                _pdf_section_titles.append(_title)
                                _seen_titles.add(_title)
                    if _pdf_section_titles:
                        ChatBILogUtil.info(f"PDF section titles for recommend questions: {_pdf_section_titles[:10]}")
                except Exception as e:
                    ChatBILogUtil.error(f"Failed to extract PDF section titles: {e}")
        except Exception as e:
            ChatBILogUtil.error(f"Failed to load document knowledge for recommend questions: {e}")

        guess_msg: List[Union[BaseMessage, dict[str, Any]]] = []
        
        # 构建数据源能力描述，明确告知LLM哪些类型的问题可以推荐
        data_capability = ''
        _is_en_cap = (self.chat_question.lang or '').lower().startswith('en')
        try:
            _ds_type_cap = (self.ds.type or '').lower() if self.ds else ''
            
            # PDF数据源：纯文档问答能力描述（PDF不支持SQL/图表/分析/预测）
            if _ds_type_cap == 'pdf':
                _pdf_cap_parts = []
                if _is_en_cap:
                    _pdf_cap_parts.append('📄 Current datasource type: PDF document')
                    _pdf_cap_parts.append('Supported: document comprehension, knowledge Q&A, content summarization, concept explanation, key point extraction')
                    _pdf_cap_parts.append('Not supported: SQL data queries, chart generation, numerical statistics, data prediction')
                    _pdf_cap_parts.append('⚠️ Recommended questions must be document content Q&A only. Do not recommend any questions requiring SQL queries, charts, or numerical calculations')
                else:
                    _pdf_cap_parts.append('📄 当前数据源类型：PDF文档')
                    _pdf_cap_parts.append('支持：文档内容理解、知识问答、内容总结、概念解释、要点提取')
                    _pdf_cap_parts.append('不支持：SQL数据查询、图表生成、数值统计、数据预测')
                    _pdf_cap_parts.append('⚠️ 推荐的问题必须是围绕文档内容的问答类问题，禁止推荐任何需要SQL查询、图表展示、数值计算的问题')
                
                if _pdf_section_titles:
                    _titles_str = '、'.join(_pdf_section_titles[:8])
                    if _is_en_cap:
                        _pdf_cap_parts.append(f'📑 Document contains the following sections/topics: {_titles_str}')
                        _pdf_cap_parts.append('💡 Recommended questions should focus on the above section topics to help users explore specific document content')
                    else:
                        _pdf_cap_parts.append(f'📑 文档包含以下章节/主题：{_titles_str}')
                        _pdf_cap_parts.append('💡 推荐问题应围绕上述章节主题展开，让用户能深入了解文档中的具体内容')
                data_capability = '\n'.join(_pdf_cap_parts)
            else:
                # 数据库/Excel/CSV等数据源：检查SQL表字段能力
                from apps.datasource.models.datasource import CoreTable as _CapTable, CoreField as _CapField
                _cap_ds_id = self.ds.id if isinstance(self.ds, CoreDatasource) else None
                has_prediction = self._check_prediction_capability(session=_session)
                capability_parts = []
                
                # 性能优化：用 JOIN 一次查出所有字段类型，替代 N+1 查询
                _cap_has_date = False
                _cap_has_numeric = False
                _cap_has_text = False
                if _cap_ds_id:
                    _cap_fields_all = _session.query(_CapField.field_type).join(
                        _CapTable, _CapField.table_id == _CapTable.id
                    ).filter(
                        _CapTable.ds_id == _cap_ds_id,
                        _CapTable.checked == True,
                        _CapField.checked == True
                    ).all()
                    for (_cft_raw,) in _cap_fields_all:
                        if _cft_raw:
                            _cft = _cft_raw.lower()
                            if any(t in _cft for t in ['date', 'time', 'timestamp']):
                                _cap_has_date = True
                            if any(t in _cft for t in ['int', 'float', 'decimal', 'numeric', 'double', 'money', 'number', 'real', 'serial']):
                                _cap_has_numeric = True
                            if any(t in _cft for t in ['varchar', 'text', 'char', 'string', 'clob', 'nclob']):
                                _cap_has_text = True
                
                if has_prediction:
                    if _is_en_cap:
                        capability_parts.append('This datasource has both time and numeric fields with sufficient data (≥10 rows), supporting prediction questions. When recommending prediction questions, you must reference actual field names from the schema — do not fabricate')
                    else:
                        capability_parts.append('该数据源同时具有时间字段和数值字段且数据量充足（≥10行），支持预测类问题。推荐预测问题时必须引用表结构中实际存在的字段名，不要编造')
                else:
                    if _is_en_cap:
                        capability_parts.append('This datasource does not meet prediction requirements (missing time fields, numeric fields, or insufficient data). Do not recommend any prediction questions (e.g., "predict", "forecast", "future")')
                    else:
                        capability_parts.append('该数据源不具备预测条件（缺少时间字段、数值字段或数据量不足），禁止推荐任何预测类问题（如"预测"、"预估"、"未来"等）')
                
                if not _cap_has_date:
                    if _is_en_cap:
                        capability_parts.append('This datasource has no time/date fields. Do not recommend trend analysis, year-over-year, or other time-dimension questions')
                    else:
                        capability_parts.append('该数据源没有时间/日期字段，禁止推荐趋势分析、同比环比等需要时间维度的问题')
                if not _cap_has_numeric:
                    if _is_en_cap:
                        capability_parts.append('This datasource has no numeric fields. Do not recommend sum, average, ranking, ratio, growth rate, or comparison questions, nor "analyze XX sales/profit/cost" type questions')
                    else:
                        capability_parts.append('该数据源没有数值字段，禁止推荐求和、平均、排名、占比、增长率、对比等需要数值计算的问题，也不要推荐"分析XX销售额/利润/成本"等涉及数值指标的分析问题')
                if not _cap_has_text:
                    if _is_en_cap:
                        capability_parts.append('⚠️ This datasource has no text/categorical fields. Do not recommend "group by XX" or "proportion of each XX" type questions')
                    else:
                        capability_parts.append('⚠️ 该数据源没有文本分类字段，推荐问题时不要涉及"按XX分类统计"、"各XX的占比"等需要分类维度的问题')
                
                data_capability = '\n'.join(capability_parts)
        except Exception:
            if _is_en_cap:
                data_capability = '⚠️ Unable to determine datasource capabilities. Please recommend conservatively — only data overview questions'
            else:
                data_capability = '⚠️ 无法确定数据源能力，请保守推荐，只推荐数据概览类问题'
        
        guess_msg.append(SystemMessage(content=self.chat_question.guess_sys_question(ds_type=ds_type, data_capability=data_capability)))

        old_questions = list(map(lambda q: q.strip(), get_old_questions(_session, self.record.datasource, user_id=self.current_user.id if self.current_user else None)))
        user_content = self.chat_question.guess_user_question(orjson.dumps(old_questions).decode())
        
        # 注入文档知识库内容到推荐问题的用户消息中
        if doc_knowledge:
            _is_en_rq = (self.chat_question.lang or '').lower().startswith('en')
            if _is_en_rq:
                user_content += f"\n\n### Document Knowledge Base (from uploaded PDF/Excel documents):\n{doc_knowledge}"
            else:
                user_content += f"\n\n### 文档知识库（来自已上传的PDF/Excel等文档）:\n{doc_knowledge}"
        
        # PDF数据源：注入文档章节标题，帮助LLM生成基于真实文档内容的推荐问题
        if _pdf_section_titles:
            _is_en_rq2 = (self.chat_question.lang or '').lower().startswith('en')
            _titles_list = '\n'.join([f'- {t}' for t in _pdf_section_titles[:10]])
            if _is_en_rq2:
                user_content += f"\n\n### Document Section Directory (actual section titles from the PDF):\n{_titles_list}\n\n⚠️ Please generate document Q&A recommended questions based on the above section titles. Questions should focus on specific section content in the document."
            else:
                user_content += f"\n\n### 文档章节目录（PDF文档的实际章节标题）:\n{_titles_list}\n\n⚠️ 请基于上述章节标题生成文档问答类推荐问题，问题应围绕文档中的具体章节内容展开。"
        
        guess_msg.append(HumanMessage(content=user_content))

        self.current_logs[OperationEnum.GENERATE_RECOMMENDED_QUESTIONS] = start_log(session=_session,
                                                                                    ai_modal_id=self.chat_question.ai_modal_id,
                                                                                    ai_modal_name=self.chat_question.ai_modal_name,
                                                                                    operate=OperationEnum.GENERATE_RECOMMENDED_QUESTIONS,
                                                                                    record_id=self.record.id,
                                                                                    full_message=[
                                                                                        {'type': msg.type,
                                                                                         'content': msg.content} for
                                                                                        msg
                                                                                        in guess_msg])
        
        # 使用JSON模式LLM进行推荐问题生成（强制结构化输出）
        json_llm = self.get_json_mode_llm()
        
        full_thinking_text = ''
        full_guess_text = ''
        token_usage = {}
        
        ChatBILogUtil.info(f"开始生成推荐问题，record_id={self.record.id}")
        
        try:
            res = process_stream(json_llm.stream(guess_msg), token_usage)
            chunk_count = 0
            for chunk in res:
                chunk_count += 1
                # 安全处理：确保content不为None
                content = chunk.get('content')
                if content:
                    full_guess_text += content
                reasoning_content = chunk.get('reasoning_content')
                if reasoning_content:
                    full_thinking_text += reasoning_content
                yield chunk
            
            ChatBILogUtil.info(f"推荐问题生成完成，共处理 {chunk_count} 个chunk，生成内容长度: {len(full_guess_text)}")
            
        except Exception as e:
            # 如果LLM流式处理失败，记录错误并抛出
            ChatBILogUtil.exception()
            raise Exception(f"Recommend questions generation failed / 推荐问题生成失败: {str(e)}")

        guess_msg.append(AIMessage(full_guess_text))

        self.current_logs[OperationEnum.GENERATE_RECOMMENDED_QUESTIONS] = end_log(session=_session,
                                                                                  log=self.current_logs[
                                                                                      OperationEnum.GENERATE_RECOMMENDED_QUESTIONS],
                                                                                  full_message=[
                                                                                      {'type': msg.type,
                                                                                       'content': msg.content}
                                                                                      for msg in guess_msg],
                                                                                  reasoning_content=full_thinking_text,
                                                                                  token_usage=token_usage)
        
        ChatBILogUtil.info(f"开始保存推荐问题答案，内容: {full_guess_text[:200]}...")
        
        # 后置过滤：根据数据源实际字段类型过滤不可用的推荐问题
        # 核心原则：不推荐数据源无法支持的问题，避免用户体验矛盾
        filtered_guess_text = full_guess_text
        try:
            filtered_guess_text = self._filter_recommend_questions(
                _session, full_guess_text, ds_type
            )
        except Exception as e:
            ChatBILogUtil.error(f"推荐问题过滤失败，使用安全兜底: {e}")
            # 过滤失败时不使用未过滤的LLM输出（可能包含不可回答的问题），改用安全兜底
            _is_en_fb = (self.chat_question.lang or '').lower().startswith('en')
            filtered_guess_text = '["What data does this datasource contain"]' if _is_en_fb else '["这个数据源有哪些数据"]'
        
        # 保存推荐问题答案，如果失败则使用空数组
        try:
            result = save_recommend_question_answer(session=_session, record_id=self.record.id,
                                                         answer={'content': filtered_guess_text})
            if result:
                self.record = result
                ChatBILogUtil.info(f"推荐问题保存成功，recommended_question: {self.record.recommended_question}")
            else:
                ChatBILogUtil.warning(f"推荐问题保存跳过（record可能已被删除）")
                return
        except Exception as e:
            ChatBILogUtil.exception()
            # 如果保存失败，使用空数组作为默认值
            try:
                result = save_recommend_question_answer(session=_session, record_id=self.record.id,
                                                             answer={'content': '[]'})
                if result:
                    self.record = result
            except Exception:
                pass
            ChatBILogUtil.warning(f"推荐问题保存失败，使用空数组作为默认值")

        yield {'recommended_question': getattr(self.record, 'recommended_question', '[]')}

        # 分层推荐问题引擎
        # 在LLM生成的推荐问题基础上，补充前置概览类推荐
        try:
            from apps.chat.thinking.recommendation_engine import RecommendationEngine
            _ds_type_rec = (self.ds.type or '').lower() if self.ds else 'database'
            _section_titles = _pdf_section_titles
            _table_names = []
            _field_names = []
            if self.chat_question.db_schema:
                import re as _re
                _table_matches = _re.findall(r'Table:\s*\S+\.(\S+)', self.chat_question.db_schema)
                _table_names = _table_matches[:5]
                _field_matches = _re.findall(r'\((\w+):', self.chat_question.db_schema)
                _field_names = _field_matches[:10]
            pre_recs = RecommendationEngine.generate_pre_recommendations(
                ds_type=_ds_type_rec,
                schema_summary=self.chat_question.db_schema[:500] if self.chat_question.db_schema else "",
                section_titles=_section_titles,
                table_names=_table_names,
                field_names=_field_names,
                has_prediction_capability=self._check_prediction_capability(session=_session) if hasattr(self, '_check_prediction_capability') else False,
                lang=self.chat_question.lang,
            )
            if pre_recs:
                yield {'layered_recommendations': {'pre': pre_recs}}
                try:
                    from apps.chat.thinking.thinking_integration import record_recommendation_stage
                    record_recommendation_stage(self.thinking_process, 'pre', pre_recs)
                except Exception:
                    pass
        except Exception as e:
            ChatBILogUtil.error(f"Layered recommendation generation failed: {e}")

    def _filter_recommend_questions(self, session: Session, guess_text: str, ds_type: str) -> str:
        """根据数据源实际能力过滤LLM生成的推荐问题"""
        # PDF数据源一律使用PDF专用过滤（文档问答，不走SQL）
        if ds_type and ds_type.lower() == 'pdf':
            return self._filter_recommend_questions_for_pdf(session, guess_text)
        
        # 语言感知：根据用户语言生成对应的兜底问题
        is_en = (self.chat_question.lang or '').lower().startswith('en')
        _fallback_default = '["What data does this datasource contain"]' if is_en else '["这个数据源有哪些数据"]'
        
        # 尝试解析JSON数组
        try:
            content = guess_text.strip()
            questions = None
            
            if content.startswith('['):
                questions = orjson.loads(content)
            else:
                extracted = extract_json_robust(content)
                if extracted:
                    questions = orjson.loads(extracted)
            
            if not isinstance(questions, list) or not questions:
                # 无法解析为问题列表时，返回安全兜底而非原始文本
                ChatBILogUtil.warning(f"推荐问题JSON解析结果无效，使用安全兜底")
                return _fallback_default
        except Exception:
            ChatBILogUtil.warning(f"推荐问题JSON解析失败，使用安全兜底")
            return _fallback_default
        
        # 检查数据源是否具备预测条件
        has_prediction_capability = self._check_prediction_capability(session)
        
        # 性能优化：用 JOIN 一次查出所有表和字段信息，替代 N+1 查询
        available_keywords = set()
        has_date_field = False
        has_numeric_field = False
        has_text_field = False
        try:
            from apps.datasource.models.datasource import CoreTable, CoreField
            ds_id = self.ds.id if isinstance(self.ds, CoreDatasource) else None
            if ds_id:
                # 先收集表名关键词
                tables = session.query(CoreTable).filter(
                    CoreTable.ds_id == ds_id,
                    CoreTable.checked == True
                ).all()
                for table in tables:
                    for name in [table.custom_comment, table.table_comment, table.table_name]:
                        if name:
                            available_keywords.add(name.lower())
                # 一次 JOIN 查出所有字段
                fields_with_table = session.query(CoreField).join(
                    CoreTable, CoreField.table_id == CoreTable.id
                ).filter(
                    CoreTable.ds_id == ds_id,
                    CoreTable.checked == True,
                    CoreField.checked == True
                ).all()
                for f in fields_with_table:
                    for name in [f.custom_comment, f.field_comment, f.field_name]:
                        if name:
                            available_keywords.add(name.lower())
                    if f.field_type:
                        ft = f.field_type.lower()
                        if any(t in ft for t in ['date', 'time', 'timestamp']):
                            has_date_field = True
                        if any(t in ft for t in ['int', 'float', 'decimal', 'numeric', 'double', 'money', 'number', 'real', 'serial']):
                            has_numeric_field = True
                        if any(t in ft for t in ['varchar', 'text', 'char', 'string', 'clob', 'nclob']):
                            has_text_field = True
        except Exception as e:
            ChatBILogUtil.error(f"收集数据源关键词失败: {e}")
        
        # 预测类关键词
        prediction_keywords = ['预测', '预估', '预计', '未来', '下个月', '明年', '下季度', '下一年',
                               '下周', '下半年', 'forecast', 'predict', 'prediction', 'future']
        
        # 趋势类关键词（需要时间字段才能回答）
        trend_keywords = ['趋势', '走势', '变化趋势', '增长趋势', '月度变化', '年度变化',
                          'trend', 'growth rate']
        
        # 同比/环比类关键词（需要同时有时间字段和数值字段）
        yoy_keywords = ['同比', '环比', '同期', '去年同期', 'year-over-year', 'yoy', 'mom']
        
        filtered = []
        removed_count = 0
        for q in questions:
            q_text = q if isinstance(q, str) else str(q)
            q_lower = q_text.lower()
            should_remove = False
            remove_reason = ''
            
            # 规则0：过滤纯知识/概念性问题（系统无法通过SQL回答）
            # 核心原则：推荐问题 = 系统承诺能回答，概念性问题不应推荐
            _concept_kws = ['应用场景', '使用场景', '技术方案', '技术架构', '技术原理',
                            '方法论', '最佳实践', '设计模式', '优缺点', '发展趋势',
                            '如何实现', '实现方式', '实现原理', '有哪些方法', '有哪些方式']
            _tech_kws = ['大模型', '模型', '算法', '深度学习', '机器学习', '人工智能',
                         'ai', 'llm', '知识图谱', 'nlp', '自然语言处理', '神经网络',
                         'rag', '检索增强', '微调', '架构', '框架', '微服务']
            _has_concept = any(kw in q_lower for kw in _concept_kws)
            _has_tech = any(kw in q_lower for kw in _tech_kws)
            if _has_concept and _has_tech:
                should_remove = True
                remove_reason = '纯知识/概念性问题，系统无法通过数据查询回答'
            
            # 规则0b：可回答性预检 — 用意图检测验证推荐问题是否会被系统正确处理
            if not should_remove:
                try:
                    _q_intent = QueryRewriter._detect_intent(q_text, ds_type=ds_type)
                    _q_route = QueryRewriter.map_to_route(_q_intent)
                    if _q_intent in ('irrelevant_query',):
                        should_remove = True
                        remove_reason = f'意图预检为{_q_intent}，系统无法有效回答此问题'
                except Exception:
                    pass
            
            # 规则1：根据预测能力决定是否过滤预测类问题
            if not has_prediction_capability and any(kw in q_lower for kw in prediction_keywords):
                should_remove = True
                remove_reason = '数据源不具备预测条件(缺少时间字段、数值字段或数据量不足)'
            
            # 规则2：无时间字段时过滤趋势类问题
            if not has_date_field and any(kw in q_lower for kw in trend_keywords):
                should_remove = True
                remove_reason = '数据源无时间字段，无法分析趋势'
            
            # 规则2b：同比/环比需要同时有时间字段和数值字段
            if not should_remove and any(kw in q_lower for kw in yoy_keywords):
                if not has_date_field or not has_numeric_field:
                    should_remove = True
                    remove_reason = '同比/环比分析需要同时有时间字段和数值字段'
            
            # 规则4：白名单验证——推荐问题中的业务名词必须在数据源中有对应
            if not should_remove and available_keywords:
                # 通用操作词（这些词不需要在数据源中存在，它们描述的是操作而非数据内容）
                generic_words = {
                    # 查询/操作动词
                    '查询', '查看', '查找', '搜索', '统计', '展示', '显示', '列出', '计算',
                    '分析', '对比', '比较', '排名', '排序', '筛选', '过滤', '汇总', '导出',
                    '帮我', '看看', '了解', '告诉', '给我', '看一下',
                    # 聚合/数值操作
                    '总计', '合计', '总共', '一共', '平均', '最大', '最小', '求和', '均值',
                    # 通用名词/代词
                    '数据', '概览', '所有', '全部', '信息', '内容', '结果', '详情', '明细',
                    '数据源', '这个', '有哪些', '包含', '哪些', '哪个', '多少', '什么',
                    # 数量/排名修饰
                    '前10', '前五', '前十', '前三', '前20',
                    # 图表类型
                    '使用', '柱状图', '折线图', '饼图', '条形图', '表格', '图表',
                    # 时间/维度修饰
                    '按', '各', '每个', '每月', '每年', '每天', '每周',
                    # 趋势/变化描述
                    '趋势', '变化', '增长', '下降', '占比', '百分比', '分布', '情况',
                    '走势', '波动', '对照',
                    # 预测相关（预测问题由规则1单独处理，这里不作为业务名词）
                    '预测', '预估', '预计', '未来',
                    # 时间词（不是业务名词）
                    '最近', '今年', '去年', '上个月', '这个月', '本月', '本年',
                    '季度', '年度', '月度',
                }
                
                # 从推荐问题中提取2-6字的中文短语
                import re as _re
                q_phrases = set(_re.findall(r'[\u4e00-\u9fff]{2,6}', q_text))
                # 去掉通用操作词，剩下的就是业务名词
                business_phrases = {p for p in q_phrases if p not in generic_words}
                
                if business_phrases:
                    # 过滤掉过短的关键词（单字符关键词容易误匹配）
                    valid_keywords = {ak for ak in available_keywords if len(ak) >= 2}
                    
                    # 检查这些业务名词是否在数据源关键词中有匹配
                    has_any_match = False
                    for phrase in business_phrases:
                        for ak in valid_keywords:
                            if phrase in ak or ak in phrase:
                                has_any_match = True
                                break
                        if has_any_match:
                            break
                    
                    if not has_any_match:
                        should_remove = True
                        remove_reason = f'问题中的业务名词({", ".join(list(business_phrases)[:3])})在数据源中找不到对应的表名或字段名'
            
            # 规则5：无数值字段时过滤需要数值计算的问题
            if not should_remove and not has_numeric_field:
                numeric_action_keywords = ['总计', '合计', '平均', '最大', '最小', '排名', '占比',
                                           '百分比', '增长率', '下降率', '变化率', '增长', '下降',
                                           '分布', 'sum', 'avg', 'max', 'min', 'total', 'growth']
                if any(kw in q_lower for kw in numeric_action_keywords):
                    should_remove = True
                    remove_reason = '数据源无数值字段，无法进行数值计算'
            
            # 规则5b：分析类问题如果明确引用了数值操作，也需要数值字段
            if not should_remove and not has_numeric_field:
                if '分析' in q_lower:
                    # "分析" + 数值相关词 → 需要数值字段
                    analysis_numeric_hints = ['销售额', '收入', '利润', '成本', '金额', '数量',
                                              '订单量', '营收', '毛利', '净利', '客单价', '坪效',
                                              '人效', '增长', '下降', '占比', '排名', '对比']
                    if any(kw in q_lower for kw in analysis_numeric_hints):
                        should_remove = True
                        remove_reason = '分析类问题涉及数值指标，但数据源无数值字段'
            
            # 规则5c：对比/比较类问题需要有数值字段进行比较
            if not should_remove:
                compare_keywords = ['对比', '比较', '对照', '相比', 'compare', 'vs']
                if any(kw in q_lower for kw in compare_keywords):
                    if not has_numeric_field:
                        should_remove = True
                        remove_reason = '对比类问题需要数值字段进行比较'
            
            # 规则6：图表类问题需要对应的字段支撑
            if not should_remove:
                # 折线图需要时间字段+数值字段
                if any(kw in q_lower for kw in ['折线图', 'line chart']):
                    if not has_date_field or not has_numeric_field:
                        should_remove = True
                        remove_reason = '折线图需要时间字段和数值字段'
                # 柱状图/条形图/饼图至少需要数值字段
                if any(kw in q_lower for kw in ['饼图', '柱状图', '条形图', 'pie', 'bar', 'column']):
                    if not has_numeric_field:
                        should_remove = True
                        remove_reason = '图表展示需要数值字段'
            
            # 规则7：分类统计类问题需要文本分类字段
            if not should_remove and not has_text_field:
                classify_keywords = ['按.*分类', '各.*类', '分类统计', '按类别', '按类型',
                                     '各类', '各种', 'by category', 'group by']
                import re as _cls_re
                if any(_cls_re.search(kw, q_lower) if '.*' in kw else kw in q_lower for kw in classify_keywords):
                    should_remove = True
                    remove_reason = '分类统计需要文本分类字段'
            
            if should_remove:
                removed_count += 1
                ChatBILogUtil.info(f"过滤不可用的推荐问题: '{q_text}' (原因: {remove_reason})")
            else:
                filtered.append(q)
        
        if removed_count > 0:
            ChatBILogUtil.info(f"推荐问题过滤完成: 移除{removed_count}个不可用问题, 剩余{len(filtered)}个")
        
        # 如果过滤后不足4个，用安全的兜底问题补足到4个
        # 核心原则：推荐问题始终展示4个，保证用户体验一致性
        target_count = 4
        if len(filtered) < target_count and questions:
            ChatBILogUtil.info(f"推荐问题不足{target_count}个(当前{len(filtered)}个)，补充兜底问题")
            try:
                from apps.datasource.models.datasource import CoreTable as _FallbackTable
                _fb_ds_id = self.ds.id if isinstance(self.ds, CoreDatasource) else None
                
                # 准备候选补充问题池（不与已有问题重复）
                existing_texts = {(q if isinstance(q, str) else str(q)) for q in filtered}
                supplement_pool = []
                
                if _fb_ds_id:
                    _fb_tables = session.query(_FallbackTable).filter(
                        _FallbackTable.ds_id == _fb_ds_id,
                        _FallbackTable.checked == True
                    ).limit(3).all()
                    if _fb_tables:
                        # 优先使用自定义备注或表备注，如果都没有且表名像自动生成的（含下划线+hash），用数据源名称
                        _fb_raw_name = _fb_tables[0].table_name or ''
                        _fb_table_name = _fb_tables[0].custom_comment or _fb_tables[0].table_comment
                        if not _fb_table_name or _fb_table_name == _fb_raw_name:
                            # 表名像自动生成的（如 sheet1_0798352c...），用数据源名称
                            import re as _fb_re
                            if _fb_re.search(r'[0-9a-f]{6,}', _fb_raw_name):
                                _fb_table_name = self.ds.name if self.ds else _fb_raw_name
                            else:
                                _fb_table_name = _fb_raw_name
                        # 兜底问题池覆盖多种问题类型（数据查询 + 分析 + 总结），保持多样性
                        supplement_pool = [
                            f'Query all data of {_fb_table_name}' if is_en else f'查询{_fb_table_name}的所有数据',
                            f'Summarize the overall data of {_fb_table_name}' if is_en else f'总结一下{_fb_table_name}的整体数据情况',
                            f'Data overview of {_fb_table_name}' if is_en else f'{_fb_table_name}的数据概览',
                            'What data does this datasource contain' if is_en else '这个数据源有哪些数据',
                            f'How many records does {_fb_table_name} have' if is_en else f'{_fb_table_name}有多少条记录',
                        ]
                        # 如果有数值字段，加入分析类兜底问题
                        if has_numeric_field:
                            supplement_pool.insert(1,
                                f'Analyze the data distribution of {_fb_table_name}' if is_en else f'分析{_fb_table_name}的数据分布情况')
                        # 如果有多个表，加入第二个表的问题
                        if len(_fb_tables) > 1:
                            _fb_table_name2 = _fb_tables[1].custom_comment or _fb_tables[1].table_comment
                            if not _fb_table_name2:
                                _fb_table_name2 = self.ds.name if self.ds else _fb_tables[1].table_name
                            supplement_pool.append(
                                f'Data overview of {_fb_table_name2}' if is_en else f'{_fb_table_name2}的数据概览')
                    else:
                        supplement_pool = ['What data does this datasource contain' if is_en else '这个数据源有哪些数据']
                else:
                    supplement_pool = ['What data does this datasource contain' if is_en else '这个数据源有哪些数据']
                
                # 从候选池中补充不重复的问题
                for sp in supplement_pool:
                    if len(filtered) >= target_count:
                        break
                    if sp not in existing_texts:
                        filtered.append(sp)
                        existing_texts.add(sp)
                
            except Exception:
                # 补充失败时，至少确保有1个问题
                if not filtered:
                    filtered = ['What data does this datasource contain' if is_en else '这个数据源有哪些数据']
        
        return orjson.dumps(filtered).decode()
    
    def _filter_recommend_questions_for_pdf(self, session: Session, guess_text: str) -> str:
        """PDF数据源推荐问题过滤

        架构设计PDF是非结构化文档，只能做RAG文档问答。
        PDF中的表格已在解析阶段转为Markdown文本并向量化，不导入PostgreSQL，
        因此PDF永远不走SQL路径，永远过滤掉所有数据查询/统计/图表/预测类问题。
        has_table概念对PDF无意义。
        """
        is_en = (self.chat_question.lang or '').lower().startswith('en')
        try:
            content = guess_text.strip()
            questions = None
            if content.startswith('['):
                questions = orjson.loads(content)
            else:
                extracted = extract_json_robust(content)
                if extracted:
                    questions = orjson.loads(extracted)
            if not isinstance(questions, list) or not questions:
                questions = []
        except Exception:
            questions = []

        # PDF = 纯文档问答，过滤掉所有SQL/图表/分析/预测类问题
        sql_keywords = ['查询', '统计', '计算', '列出', '排名', '排序',
                        '筛选', '过滤', '合计', '平均', '求和', '最大', '最小',
                        '柱状图', '折线图', '饼图', '图表', '可视化',
                        '同比', '环比', '增长率', '占比', '百分比',
                        '预测', '预估', '预计', '未来',
                        'top', 'count', 'sum', 'avg', 'chart', 'graph',
                        'predict', 'forecast', 'future', 'next year']
        filtered = []
        for q in questions:
            q_text = q if isinstance(q, str) else str(q)
            q_lower = q_text.lower()
            if not any(kw in q_lower for kw in sql_keywords):
                filtered.append(q)
        
        # 基于文档章节标题生成兜底问题
        doc_name = self.ds.name if self.ds else ('document' if is_en else '文档')
        fallback_questions = []
        try:
            oid = self.ds.oid if isinstance(self.ds, CoreDatasource) else 1
            from apps.datasource.models.document import CoreDocumentChunk, CoreDocument
            _pdf_docs = session.query(CoreDocument).filter(
                CoreDocument.oid == oid,
                CoreDocument.file_type.in_(['.pdf', 'pdf'])  # 兼容带点和不带点的格式
            ).order_by(CoreDocument.id.desc()).limit(3).all()
            _section_titles = []
            _seen = set()
            for _doc in _pdf_docs:
                _chunks = session.query(CoreDocumentChunk).filter(
                    CoreDocumentChunk.document_id == _doc.id,
                    CoreDocumentChunk.section_title.isnot(None),
                    CoreDocumentChunk.section_title != ''
                ).distinct(CoreDocumentChunk.section_title).limit(15).all()
                for _c in _chunks:
                    _t = _c.section_title.strip()
                    if _t and _t not in _seen and len(_t) >= 2:
                        _section_titles.append(_t)
                        _seen.add(_t)
            
            if _section_titles:
                # 基于真实章节标题生成问题
                fallback_questions.append(
                    f'Summarize the main content of {doc_name}' if is_en else f'总结一下{doc_name}的主要内容')
                for _st in _section_titles[:3]:
                    fallback_questions.append(
                        f'What does {doc_name} say about "{_st}"?' if is_en else f'{doc_name}中关于"{_st}"的内容是什么')
                ChatBILogUtil.info(f"PDF fallback questions based on sections: {_section_titles[:5]}")
            else:
                # 无章节标题时使用通用兜底
                if is_en:
                    fallback_questions = [
                        f'Summarize the main content of {doc_name}',
                        f'What are the key points of {doc_name}',
                        f'What are the core viewpoints of {doc_name}',
                        f'What important concepts are mentioned in {doc_name}',
                    ]
                else:
                    fallback_questions = [
                        f'总结一下{doc_name}的主要内容',
                        f'{doc_name}讲了哪些关键要点',
                        f'概括{doc_name}的核心观点',
                        f'{doc_name}中提到了哪些重要概念',
                    ]
        except Exception as e:
            ChatBILogUtil.error(f"Failed to generate PDF fallback questions from sections: {e}")
            if is_en:
                fallback_questions = [
                    f'Summarize the main content of {doc_name}',
                    f'What are the key points of {doc_name}',
                    f'What are the core viewpoints of {doc_name}',
                    f'What important concepts are mentioned in {doc_name}',
                ]
            else:
                fallback_questions = [
                    f'总结一下{doc_name}的主要内容',
                    f'{doc_name}讲了哪些关键要点',
                    f'概括{doc_name}的核心观点',
                    f'{doc_name}中提到了哪些重要概念',
                ]
        
        existing = {(q if isinstance(q, str) else str(q)) for q in filtered}
        for fq in fallback_questions:
            if len(filtered) >= 4:
                break
            if fq not in existing:
                filtered.append(fq)
                existing.add(fq)
        
        return orjson.dumps(filtered[:4]).decode()

    def _check_prediction_capability(self, session: Session) -> bool:
        """检查当前数据源是否具备预测条件"""
        if hasattr(self, '_prediction_capability_cache'):
            return self._prediction_capability_cache
        result = self._do_check_prediction_capability(session)
        self._prediction_capability_cache = result
        return result

    def _do_check_prediction_capability(self, session: Session) -> bool:
        """_check_prediction_capability 的实际实现"""
        try:
            from apps.datasource.models.datasource import CoreTable, CoreField
            from sqlalchemy import text as sa_text

            _ds_type = self.ds.type.lower() if self.ds and self.ds.type else ''
            if _ds_type == 'pdf':
                return False

            ds_id = self.ds.id if isinstance(self.ds, CoreDatasource) else None
            if not ds_id:
                return False

            # 性能优化：用 JOIN 一次查出所有表和字段，替代 N+1 查询
            results = session.query(CoreTable, CoreField).join(
                CoreField, CoreField.table_id == CoreTable.id
            ).filter(
                CoreTable.ds_id == ds_id,
                CoreTable.checked == True,
                CoreField.checked == True
            ).all()

            if not results:
                return False

            # 按表分组分析字段类型
            table_fields = {}
            for table, field in results:
                if table.id not in table_fields:
                    table_fields[table.id] = {'table': table, 'has_date': False, 'has_numeric': False}
                if not field.field_type:
                    continue
                ft = field.field_type.lower()
                fn = (field.field_name or '').lower()

                if any(t in ft for t in ['date', 'time', 'timestamp']):
                    table_fields[table.id]['has_date'] = True
                elif any(t in fn for t in ['date', 'time', '日期', '时间', '年', '月']):
                    table_fields[table.id]['has_date'] = True

                if any(t in ft for t in ['int', 'float', 'decimal', 'numeric', 'double', 'money', 'number', 'real', 'serial']):
                    table_fields[table.id]['has_numeric'] = True

            has_date_field = any(v['has_date'] for v in table_fields.values())
            has_numeric_field = any(v['has_numeric'] for v in table_fields.values())
            has_enough_data = False

            # 只对同时有时间+数值字段的表检查数据量
            for info in table_fields.values():
                if info['has_date'] and info['has_numeric'] and not has_enough_data:
                    try:
                        import re as _re_tbl
                        _tbl_name = info['table'].table_name
                        # 放宽表名正则，支持中文等Unicode字符
                        if _tbl_name and not _re_tbl.search(r'[;\'"\\]', _tbl_name):
                            _ds_type_lower = self.ds.type.lower() if self.ds and self.ds.type else ''
                            if _ds_type_lower in ('excel', 'csv', 'pdf'):
                                from apps.db.engine import get_engine_conn as _get_engine
                                _engine = _get_engine()
                                with _engine.connect() as _conn:
                                    row_count = _conn.execute(
                                        sa_text(f'SELECT COUNT(*) FROM "{_tbl_name}"')
                                    ).scalar()
                            else:
                                # Database 数据源也需要检查数据量
                                try:
                                    from apps.db.db import exec_sql as _pred_exec_sql
                                    _safe_name = '"' + _tbl_name.replace('"', '""') + '"'
                                    _count_result = _pred_exec_sql(ds=self.ds, sql=f'SELECT COUNT(*) as cnt FROM {_safe_name}', origin_column=False)
                                    row_count = 0
                                    if _count_result and _count_result.get('data'):
                                        row_count = _count_result['data'][0].get('cnt', 0) if _count_result['data'] else 0
                                except Exception:
                                    # 数据库查询失败时保守处理，假设数据量足够
                                    has_enough_data = True
                                    continue
                            if row_count and row_count >= 10:
                                has_enough_data = True
                    except Exception:
                        pass

            return has_date_field and has_numeric_field and has_enough_data
        except Exception as e:
            ChatBILogUtil.error(f"检查预测能力失败: {e}")
            return False

    def _execute_query_understanding(self, session, ds_type: str, path_label: str = '') -> Dict:
        """修复 QU-5：统一的查询理解流程，select_datasource 和 existing_ds 共用"""
        from apps.chat.thinking.query_rewriter import QueryRewriter
        from apps.chat.thinking.llm_query_rewriter import llm_enhanced_rewrite

        # 构建对话历史（供 LLM 重写使用）
        dialogue_history = None
        if hasattr(self, 'dialogue_tracker') and self.dialogue_tracker and self.dialogue_tracker.turns:
            dialogue_history = [
                {'question': t.question, 'answer': getattr(t, 'answer', '')}
                for t in self.dialogue_tracker.turns[-5:]
            ]

        # 混合查询重写：规则层 + LLM层（自动判断是否需要 LLM）
        rewrite_result = llm_enhanced_rewrite(
            question=self.chat_question.question,
            ds_type=ds_type,
            dialogue_history=dialogue_history,
            llm=self.llm if hasattr(self, 'llm') else None,
        )
        self._rewrite_result = rewrite_result
        retrieval_question = rewrite_result['rewritten']
        if rewrite_result['rewrite_applied']:
            ChatBILogUtil.info(
                f"Query rewritten ({path_label}): '{self.chat_question.question}' -> '{retrieval_question}'"
            )

        # Step 3: 更新早期意图
        if rewrite_result.get('intent'):
            _old_early = self._early_intent
            self._early_intent = rewrite_result['intent']
            if _old_early != self._early_intent:
                ChatBILogUtil.info(
                    f"[{path_label}] Early intent updated by rewriter: '{_old_early}' -> '{self._early_intent}'"
                )

        # Step 4: PDF 意图调整（PDF 始终走文档问答）
        _ds_lower = (ds_type or '').lower()
        if _ds_lower == 'pdf':
            # PDF场景下 ambiguous_query 也应走 document_qa
            if self._early_intent not in ('irrelevant_query', 'document_qa'):
                ChatBILogUtil.info(
                    f"[{path_label}][PDF route] Re-adjusting intent from '{self._early_intent}' to 'document_qa'"
                )
                self._early_intent = 'document_qa'

        # Step 5: 记录查询理解阶段到思考过程
        try:
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
                intent=self._early_intent or rewrite_result.get('intent', 'data_query'),
                rewrite_applied=rewrite_result['rewrite_applied'],
                extracted_keywords=rewrite_result.get('extracted_keywords', []),
                dialogue_turn=dialogue_turn,
                context_references=context_refs,
                ds_type=(self.ds.type or '').lower() if hasattr(self, 'ds') and self.ds else '',
                ds_name=(self.ds.name or '') if hasattr(self, 'ds') and self.ds else '',
                intent_keywords=rewrite_result.get('intent_keywords', []),
            )
        except Exception as e:
            ChatBILogUtil.error(f"Failed to record query understanding stage ({path_label}): {e}")

        # Step 7: 查询分解
        decompose_result = {}
        try:
            decompose_result = QueryRewriter.decompose_complex_query(self.chat_question.question)
            self._decompose_result = decompose_result
            if decompose_result.get('is_complex') and len(decompose_result.get('sub_tasks', [])) >= 2:
                from apps.chat.thinking.thinking_integration import record_query_decomposition_stage
                record_query_decomposition_stage(
                    self.thinking_process,
                    is_complex=decompose_result['is_complex'],
                    sub_tasks=decompose_result['sub_tasks'],
                    task_type=decompose_result['task_type'],
                )
                ChatBILogUtil.info(
                    f"Query decomposition ({path_label}): {len(decompose_result['sub_tasks'])} sub-tasks"
                )
        except Exception as e:
            ChatBILogUtil.error(f"Query decomposition failed ({path_label}): {e}")

        return {
            'rewrite_result': rewrite_result,
            'retrieval_question': retrieval_question,
            'decompose_result': decompose_result,
        }

    def _execute_unified_rag_pipeline(
        self,
        _session: Session,
        retrieval_question: str,
        oid: int,
        ds_id: Optional[int],
        rewrite_result: dict,
    ) -> dict:
        """统一三阶段 RAG 流水线桥接方法"""
        from apps.chat.thinking.rag_reranker import RAGReranker, RAGQualityEnhancer

        ds_type = (self.ds.type or 'database').lower() if self.ds else 'database'
        ds_name = self.ds.name if self.ds else ''
        has_table = not (ds_type == 'pdf')  # PDF固定为False

        # ========== 阶段1：检索 Retrieve ==========
        ctx = PipelineContext(
            question=self.chat_question.question,
            ds_type=ds_type,
            ds_name=ds_name,
            has_table=has_table,
            oid=oid,
            ds_id=ds_id,
            available_components=get_available_components(ds_type, has_table),
            # 传入外部查询分解结果，让 retrieve 合并到 sub_intents
            decompose_result=getattr(self, '_decompose_result', None),
            lang=self.chat_question.lang or "zh",
        )

        # 将外部重写结果直接传入 retrieve，避免双重查询重写
        _perf_retrieve_start = time.time()
        retrieve = UnifiedRAGExecutor.retrieve(
            ctx, _session, rewrite_result=rewrite_result
        )
        ChatBILogUtil.info(f"[PERF] RAG retrieve phase: {time.time() - _perf_retrieve_start:.2f}s")

        # 跨数据源提示注入 LLM prompt，让用户看到引导信息
        if retrieve.cross_datasource_hint and retrieve.cross_datasource_hint.get("is_cross_datasource"):
            hint_text = retrieve.cross_datasource_hint.get("hint", "")
            if hint_text:
                _is_en_hint = (self.chat_question.lang or '').lower().startswith('en')
                _hint_prefix = "[System Notice]" if _is_en_hint else "【系统提示】"
                existing_custom = self.chat_question.custom_prompt or ""
                self.chat_question.custom_prompt = (
                    existing_custom + f"\n\n{_hint_prefix}{hint_text}" if existing_custom
                    else f"{_hint_prefix}{hint_text}"
                )

        ChatBILogUtil.info(
            f"[UnifiedRAG] Retrieve done: design_intent={retrieve.intent} "
            f"fine_intent={retrieve.fine_intent} terms={len(retrieve.terminology_results)} "
            f"sql_ex={len(retrieve.sql_example_results)} doc_chunks={len(retrieve.doc_chunk_results)}"
        )

        # ========== 阶段2：增强 Augment ==========
        _perf_augment_start = time.time()
        augment = UnifiedRAGExecutor.augment(
            ctx, retrieve,
            db_schema=self.chat_question.db_schema,
            custom_prompt=self.chat_question.custom_prompt,
            dialogue_tracker=self.dialogue_tracker,
        )

        ChatBILogUtil.info(
            f"[UnifiedRAG] Augment done: viz={augment.visualization_detected} "
            f"compression={augment.compression_applied} "
            f"components={[k for k, v in augment.components_used.items() if v]}"
        )

        # 记录可视化意图判定阶段到思考过程
        if augment.visualization_detected or augment.visualization_reason:
            try:
                from apps.chat.thinking.thinking_integration import record_visualization_intent_stage
                record_visualization_intent_stage(self.thinking_process, {
                    'needs_visualization': augment.visualization_detected,
                    'chart_type': augment.visualization_chart_type,
                    'reason': augment.visualization_reason,
                    'dimensions': {},
                    'confidence': 0.8 if augment.visualization_detected else 0.0,
                })
            except Exception as e:
                ChatBILogUtil.error(f"[UnifiedRAG] Failed to record visualization_intent stage: {e}")

        # 记录上下文压缩阶段到思考过程（统一执行器路径）
        try:
            from apps.chat.thinking.thinking_integration import record_context_compression_stage
            if augment.compression_applied:
                record_context_compression_stage(self.thinking_process, {
                    'original_length': augment.original_token_count,
                    'compressed_length': augment.compressed_token_count,
                    'compression_ratio': round(augment.compressed_token_count / max(augment.original_token_count, 1), 3),
                    'compression_applied': True,
                })
            else:
                # 未压缩时也记录（让前端显示"在预算内"状态）
                _est_tokens = augment.original_token_count
                record_context_compression_stage(self.thinking_process, {
                    'original_length': _est_tokens,
                    'compressed_length': _est_tokens,
                    'compression_ratio': 1.0,
                    'compression_applied': False,
                    'compression_skipped': True,
                    'estimated_tokens': _est_tokens,
                    'reason': 'within_budget',
                })
        except Exception as e:
            ChatBILogUtil.error(f"[UnifiedRAG] Failed to record context_compression stage: {e}")

        # ========== 阶段3：生成配置 Generate ==========
        ChatBILogUtil.info(f"[PERF] RAG augment phase: {time.time() - _perf_augment_start:.2f}s")
        _perf_generate_start = time.time()
        generate = UnifiedRAGExecutor.generate_config(ctx, retrieve, augment)
        ChatBILogUtil.info(f"[PERF] RAG generate_config phase: {time.time() - _perf_generate_start:.2f}s")

        # ========== 映射回 self.chat_question 字段（兼容层）==========
        ChatBILogUtil.info(
            f"[UnifiedRAG] augment output: "
            f"terminologies_xml_len={len(augment.terminologies_xml or '')}, "
            f"sql_examples_xml_len={len(augment.sql_examples_xml or '')}, "
            f"has_terminology_tag={'<terminology>' in (augment.terminologies_xml or '')}, "
            f"has_sql_example_tag={'<sql-example>' in (augment.sql_examples_xml or '')}, "
            f"compression_applied={augment.compression_applied}"
        )
        # 术语 XML
        if augment.terminologies_xml:
            self.chat_question.terminologies = augment.terminologies_xml
            self.chat_question.raw_terminology_count = len(retrieve.terminology_results)
        else:
            self.chat_question.terminologies = ''
            self.chat_question.raw_terminology_count = 0
            if retrieve.terminology_results:
                ChatBILogUtil.warning(
                    f"[UnifiedRAG] ⚠️ terminologies_xml is EMPTY despite retrieve having "
                    f"{len(retrieve.terminology_results)} results! "
                    f"Check build_terminology_template_from_details"
                )

        # SQL 示例 XML（Database/Excel/CSV 数据源统一启用）
        components = ctx.available_components
        if components.get('sql_examples') and augment.sql_examples_xml:
            self.chat_question.data_training = augment.sql_examples_xml
        else:
            self.chat_question.data_training = ''
            if retrieve.sql_example_results:
                ChatBILogUtil.warning(
                    f"[UnifiedRAG] ⚠️ sql_examples_xml is EMPTY despite retrieve having "
                    f"{len(retrieve.sql_example_results)} results! "
                    f"component_enabled={components.get('sql_examples')}, "
                    f"xml_len={len(augment.sql_examples_xml or '')}"
                )

        # 文档片段注入 data_training（扩展到所有文档类数据源）
        if ds_type == 'pdf' and retrieve.doc_chunk_results:
            # 计算已有上下文占用的字符数
            _existing_context_len = len(self.chat_question.data_training or '') + \
                                    len(self.chat_question.terminologies or '') + \
                                    len(self.chat_question.db_schema or '')
            # LLM上下文窗口预算（保守估计，为system prompt和回答留空间）
            _max_context_chars = 8000
            _doc_budget = max(1000, _max_context_chars - _existing_context_len)
            _doc_budget = min(_doc_budget, 4000)  # 文档片段最多4000字符
            doc_context = format_pdf_context(
                retrieve.doc_chunk_results,
                max_chars=_doc_budget,
                lang=self.chat_question.lang or "zh"
            )
            if doc_context:
                doc_prefix = "\n\n<document-knowledge>\n"
                doc_suffix = "\n</document-knowledge>"
                self.chat_question.data_training = (
                    (self.chat_question.data_training or '') + doc_prefix + doc_context + doc_suffix
                )

        # Schema（压缩后）
        if augment.compression_applied and augment.schema_xml:
            self.chat_question.db_schema = augment.schema_xml

        # 缓存 RAG 结果供评估和溯源使用
        self._rag_terminologies = []
        self._rag_sql_examples = []
        self._rag_doc_chunks = retrieve.doc_chunk_results

        # 构建前端展示用的增强结果
        for term in retrieve.terminology_results[:5]:
            try:
                enhanced = RAGQualityEnhancer.enhance_terminology(term, lang=self.chat_question.lang)
                self._rag_terminologies.append({
                    'word': enhanced['word'],
                    'description': enhanced['description'],
                    'similarity': enhanced['similarity'] / 100.0 if enhanced['similarity'] > 1 else enhanced['similarity'],
                    'match_type': enhanced['match_type'],
                    'used': True,
                    'rerank_score': enhanced.get('rerank_score', 0),
                    'usage_hint': enhanced.get('usage_hint', ''),
                })
            except Exception:
                self._rag_terminologies.append(term)

        for ex in retrieve.sql_example_results[:3]:
            try:
                enhanced = RAGQualityEnhancer.enhance_sql_example(ex, lang=self.chat_question.lang)
                self._rag_sql_examples.append({
                    'question': enhanced['question'],
                    'sql': enhanced['sql'],
                    'similarity': enhanced['similarity'] / 100.0 if enhanced['similarity'] > 1 else enhanced['similarity'],
                    'match_type': enhanced['match_type'],
                    'used': True,
                    'rerank_score': enhanced.get('rerank_score', 0),
                    'sql_features': enhanced.get('sql_features', []),
                    'applicable_scenarios': enhanced.get('applicable_scenarios', '')
                })
            except Exception:
                self._rag_sql_examples.append(ex)

        # 保存执行器结果供后续阶段使用
        self._unified_rag_result = {
            'retrieve': retrieve,
            'augment': augment,
            'generate': generate,
            'context': ctx,
        }

        return {
            'retrieve': retrieve,
            'augment': augment,
            'generate': generate,
            'terminology_results': self._rag_terminologies,
            'sql_example_results': self._rag_sql_examples,
            'doc_chunk_results': retrieve.doc_chunk_results,
            'custom_prompts_used': [],
            'design_intent': retrieve.intent,
            'fine_intent': retrieve.fine_intent,
        }

    def generate_direct_answer(self, _session: Session, intent: str):
        """生成直接文本回答（不经过SQL生成流程）"""
        ChatBILogUtil.info(f"Generating direct answer for intent: {intent}, question: {self.chat_question.question}")
        
        # 记录RAG检索阶段到思考过程（仅当尚未记录时）
        terminology_count = 0
        if self.chat_question.terminologies:
            terminology_count = self.chat_question.terminologies.count('<terminology>')
        
        if 'rag_retrieval' not in self.thinking_process.stages:
            try:
                # 使用 run_task 中缓存的实际 RAG 检索耗时
                _actual_rag_time = 0.0
                _da_terminologies = []
                _da_sql_examples = []
                _da_doc_chunks = []
                if hasattr(self, '_unified_rag_result') and self._unified_rag_result:
                    _ret = self._unified_rag_result.get('retrieve')
                    if _ret:
                        if hasattr(_ret, 'retrieval_time_ms'):
                            _actual_rag_time = _ret.retrieval_time_ms / 1000.0
                        _da_terminologies = getattr(_ret, 'terminology_results', []) or []
                        _da_sql_examples = getattr(_ret, 'sql_example_results', []) or []
                        _da_doc_chunks = getattr(_ret, 'doc_chunk_results', []) or []
                _da_ds_type = (self.ds.type or 'database').lower() if self.ds else 'database'
                record_rag_retrieval(
                    self.thinking_process,
                    question=self.chat_question.question,
                    table_candidates=getattr(self, '_table_match_details', {}).get('table_candidates', []),
                    selected_tables=getattr(self, '_table_match_details', {}).get('selected_tables', []),
                    similarities=getattr(self, '_table_match_details', {}).get('similarities', []),
                    terminologies=_da_terminologies,
                    sql_examples=_da_sql_examples,
                    doc_chunks=_da_doc_chunks,
                    retrieval_time=_actual_rag_time,
                    ds_type=_da_ds_type,
                )
            except Exception as e:
                ChatBILogUtil.error(f"[generate_direct_answer] Failed to record rag_retrieval stage: {e}")
        
        direct_msg: List[Union[BaseMessage, dict[str, Any]]] = []
        
        # 优先使用 UnifiedRAGExecutor 的增强系统提示词（PDF 文档问答场景）
        _use_executor_prompt = False
        if hasattr(self, '_unified_rag_result') and self._unified_rag_result:
            _aug = self._unified_rag_result.get('augment')
            if _aug and _aug.augmented_system_prompt:
                direct_msg.append(SystemMessage(content=_aug.augmented_system_prompt))
                _use_executor_prompt = True
                ChatBILogUtil.info("[generate_direct_answer] Using UnifiedRAGExecutor augmented system prompt")
        
        if not _use_executor_prompt:
            direct_msg.append(SystemMessage(content=self.chat_question.direct_answer_sys_question(intent=intent)))
        
        # 注入多轮对话上下文到直接回答路径
        try:
            if self.dialogue_tracker and self.dialogue_tracker.turns:
                dialogue_ctx = self.dialogue_tracker.get_dialogue_context(max_turns=3)
                if dialogue_ctx.get('total_turns', 0) > 0:
                    _is_en_dlg = (self.chat_question.lang or '').lower().startswith('en')
                    ctx_parts = []
                    if _is_en_dlg:
                        ctx_parts.append(f"Dialogue turns: {dialogue_ctx['total_turns']}")
                        if dialogue_ctx.get('current_topic'):
                            ctx_parts.append(f"Current topic: {dialogue_ctx['current_topic']}")
                        if dialogue_ctx.get('active_entities'):
                            ctx_parts.append(f"Active entities: {', '.join(dialogue_ctx['active_entities'][:5])}")
                        recent_qs = dialogue_ctx.get('recent_questions', [])
                        if len(recent_qs) > 1:
                            ctx_parts.append(f"Recent questions: {'; '.join(recent_qs[-3:])}")
                        ctx_refs = dialogue_ctx.get('context_references', [])
                        if ctx_refs:
                            ref_hints = [f"{r['type']}: {r['resolved']}" for r in ctx_refs if r.get('resolved')]
                            if ref_hints:
                                ctx_parts.append(f"Context references: {'; '.join(ref_hints)}")
                    else:
                        ctx_parts.append(f"当前对话轮次: {dialogue_ctx['total_turns']}")
                        if dialogue_ctx.get('current_topic'):
                            ctx_parts.append(f"当前话题: {dialogue_ctx['current_topic']}")
                        if dialogue_ctx.get('active_entities'):
                            ctx_parts.append(f"活跃实体: {', '.join(dialogue_ctx['active_entities'][:5])}")
                        recent_qs = dialogue_ctx.get('recent_questions', [])
                        if len(recent_qs) > 1:
                            ctx_parts.append(f"近期问题: {'; '.join(recent_qs[-3:])}")
                        # 注入上下文引用解析结果
                        ctx_refs = dialogue_ctx.get('context_references', [])
                        if ctx_refs:
                            ref_hints = [f"{r['type']}: {r['resolved']}" for r in ctx_refs if r.get('resolved')]
                            if ref_hints:
                                ctx_parts.append(f"上下文引用: {'; '.join(ref_hints)}")
                    dialogue_hint = '\n'.join(ctx_parts)
                    direct_msg.append(SystemMessage(
                        content=f"<dialogue-context>\n{dialogue_hint}\n</dialogue-context>"
                    ))
        except Exception as e:
            ChatBILogUtil.error(f"Failed to inject dialogue context into direct answer: {e}")
        
        # 用户提示词：优先使用执行器的增强用户提示词
        if _use_executor_prompt and self._unified_rag_result:
            _aug = self._unified_rag_result.get('augment')
            if _aug and _aug.augmented_user_prompt:
                direct_msg.append(HumanMessage(content=_aug.augmented_user_prompt))
            else:
                direct_msg.append(HumanMessage(content=self.chat_question.direct_answer_user_question()))
        else:
            direct_msg.append(HumanMessage(content=self.chat_question.direct_answer_user_question()))
        
        # 记录提示词构建阶段（直接回答路径）— 通过 PromptBuilder 记录
        try:
            from apps.chat.thinking.prompt_builder import PromptBuilder
            da_builder = PromptBuilder(
                prompt_type='direct_answer',
                model_name=self.chat_question.ai_modal_name or ''
            )
            da_builder.set_rag_knowledge(
                terminologies_xml=self.chat_question.terminologies,
                sql_examples_xml=self.chat_question.data_training,
                raw_terminology_count=getattr(self.chat_question, 'raw_terminology_count', 0),
            )
            # 设置文档片段（PDF 数据源独立追踪，使提示词结构组成中显示"文档片段"组件）
            _cached_doc_chunks = getattr(self, '_rag_doc_chunks', []) or []
            if _cached_doc_chunks:
                # 从实际发送给 LLM 的系统提示词中提取 <document-knowledge> 的真实长度
                _sys_for_doc = direct_msg[0].content if direct_msg else ''
                # 将 import re 提升到 if 块外部，
                import re as _re_da
                _doc_xml = ''
                if '<document-knowledge>' in _sys_for_doc:
                    _dm = _re_da.search(r'<document-knowledge>.*?</document-knowledge>', _sys_for_doc, _re_da.DOTALL)
                    if _dm:
                        _doc_xml = _dm.group(0)
                # 如果系统提示词中没找到（fallback 路径），从 data_training 中提取
                if not _doc_xml:
                    _dt = self.chat_question.data_training or ''
                    if '<document-knowledge>' in _dt:
                        _dm2 = _re_da.search(r'<document-knowledge>.*?</document-knowledge>', _dt, _re_da.DOTALL)
                        if _dm2:
                            _doc_xml = _dm2.group(0)
                da_builder.set_document_chunks(_cached_doc_chunks, _doc_xml)
            da_builder.set_schema(self.chat_question.db_schema)
            # PDF 数据源不注入自定义提示词到思考过程展示
            _ds_type_da = (self.ds.type or '').lower() if hasattr(self, 'ds') and self.ds else ''
            if _ds_type_da == 'pdf':
                da_builder.set_custom_prompts('', [])
            else:
                da_builder.set_custom_prompts(
                    self.chat_question.custom_prompt,
                    getattr(self, '_custom_prompts_used', []),
                )
            da_builder.set_dialogue_context(getattr(self, 'dialogue_tracker', None), lang=self.chat_question.lang)

            _sys_prompt_da = direct_msg[0].content if direct_msg else ''
            _user_prompt_da = direct_msg[-1].content if direct_msg else ''
            _da_metadata = da_builder._build_metadata(_sys_prompt_da, _user_prompt_da)
            _da_metadata.message_count = len(direct_msg)
            # system_prompt_length 应包含所有 SystemMessage（含 dialogue-context）
            _sys_total_da = sum(
                len(m.content) for m in direct_msg
                if isinstance(m, SystemMessage))
            _da_metadata.system_prompt_length = _sys_total_da
            _da_metadata.total_prompt_length = _sys_total_da + len(_user_prompt_da)
            da_builder.record_to_thinking(self.thinking_process, _da_metadata)

            _pc_stage_da = self.thinking_process.get_stage('prompt_construction')
            
            # 发送上下文压缩阶段数据（如果有）— 压缩在提示词构建之前执行
            _cc_stage_da = self.thinking_process.get_stage('context_compression')
            if _cc_stage_da:
                yield {'type': 'thinking_stage', 'stage': 'context_compression', 'data': _cc_stage_da}
            
            if _pc_stage_da:
                yield {'type': 'thinking_stage', 'stage': 'prompt_construction', 'data': _pc_stage_da}
        except Exception as e:
            ChatBILogUtil.error(f"Failed to record prompt_construction stage (direct_answer): {e}")
        
        self.current_logs[OperationEnum.DIRECT_ANSWER] = start_log(
            session=_session,
            ai_modal_id=self.chat_question.ai_modal_id,
            ai_modal_name=self.chat_question.ai_modal_name,
            operate=OperationEnum.DIRECT_ANSWER,
            record_id=self.record.id,
            full_message=[{'type': msg.type, 'content': msg.content} for msg in direct_msg]
        )
        
        full_text = ''
        full_thinking_text = ''
        token_usage = {}
        
        # 记录LLM调用开始时间
        llm_start_time = time.time()
        
        # Gemini 2.5 Pro 偶尔返回 0 output tokens（HTTP 200 但无内容），需要在此层重试
        _max_empty_retries = 2
        for _empty_attempt in range(_max_empty_retries + 1):
            full_text = ''  # 重试时重置
            full_thinking_text = ''
            
            try:
                res = process_stream(stream_with_retry(self.llm, direct_msg), token_usage)
                for chunk in res:
                    content = chunk.get('content')
                    if content:
                        full_text += content
                    reasoning_content = chunk.get('reasoning_content')
                    if reasoning_content:
                        full_thinking_text += reasoning_content
                    yield chunk
            except Exception as e:
                ChatBILogUtil.exception()
                raise Exception(f"Direct answer generation failed / 直接回答生成失败: {str(e)}")
            
            # 如果有内容（content 或 reasoning），跳出重试循环
            if full_text.strip() or full_thinking_text.strip():
                break
            
            # 空响应：判断是否需要重试
            if _empty_attempt < _max_empty_retries:
                ChatBILogUtil.warning(
                    f"[generate_direct_answer] LLM returned empty content (attempt {_empty_attempt + 1}/{_max_empty_retries + 1}), "
                    f"retrying in 1s... Token usage: {token_usage}"
                )
                time.sleep(1)
        
        # 安全兜底：如果LLM只输出了推理内容但没有最终回答
        # 将推理内容作为回答内容发送给前端，避免"第一次空白"问题
        if not full_text.strip() and full_thinking_text.strip():
            ChatBILogUtil.info("[generate_direct_answer] LLM returned only reasoning content, using it as answer")
            full_text = full_thinking_text
            yield {'content': full_text, 'reasoning_content': ''}
        elif not full_text.strip():
            ChatBILogUtil.info("[generate_direct_answer] LLM returned empty response after all retries")
            _is_en_fb = (self.chat_question.lang or '').lower().startswith('en')
            full_text = (
                "Sorry, the system was unable to generate a valid answer. Please try rephrasing your question."
                if _is_en_fb else
                "抱歉，系统未能生成有效回答，请尝试重新提问或换一种表述方式。"
            )
            yield {'content': full_text, 'reasoning_content': ''}
        
        direct_msg.append(AIMessage(full_text))
        
        # 计算LLM生成耗时
        llm_generation_time = time.time() - llm_start_time
        
        self.current_logs[OperationEnum.DIRECT_ANSWER] = end_log(
            session=_session,
            log=self.current_logs[OperationEnum.DIRECT_ANSWER],
            full_message=[{'type': msg.type, 'content': msg.content} for msg in direct_msg],
            reasoning_content=full_thinking_text,
            token_usage=token_usage
        )
        
        # 记录直接回答生成阶段到思考过程（关键修复：之前缺失）
        # 这使得思考过程面板能显示LLM生成阶段的耗时和Token消耗
        try:
            stage_name = 'direct_answer'
            
            self.thinking_process.record_stage(
                name=stage_name,
                status='completed',
                duration=int(llm_generation_time * 1000),
                extra_data={
                    'intent': intent,
                    'answer_length': len(full_text),
                    'has_reasoning': bool(full_thinking_text),
                    'chunks': [],
                    'rag_context': {
                        'terminologies_used': terminology_count,
                        'schema_used': bool(self.chat_question.db_schema),
                    }
                },
                llm_generation={
                    'generation_time': round(llm_generation_time, 3),
                    'token_usage': token_usage,
                    'model': self.chat_question.ai_modal_name,
                }
            )
            
            # 发送思考过程阶段到前端
            stage_data = self.thinking_process.get_stage(stage_name)
            if stage_data:
                yield {'type': 'thinking_stage', 'stage': stage_name, 'data': stage_data}
            
            # 记录溯源凭证（直接回答路径 - 使用统一 RAG 执行器的溯源凭证）
            try:
                from apps.chat.thinking.thinking_integration import record_provenance_stage
                _da_provenance = []
                _da_ds_type = (self.ds.type or '').lower() if self.ds else ''

                # 优先使用 UnifiedRAGExecutor 的溯源凭证
                if hasattr(self, '_unified_rag_result') and self._unified_rag_result:
                    _gen = self._unified_rag_result.get('generate')
                    if _gen and _gen.provenance:
                        _da_provenance = _gen.provenance
                        ChatBILogUtil.info(f"[generate_direct_answer] Using executor provenance: {len(_da_provenance)} records")

                # 兜底：执行器未运行时使用内联构建
                _is_en_prov = (self.chat_question.lang or '').lower().startswith('en')
                if not _da_provenance:
                    if _da_ds_type == 'pdf':
                        if hasattr(self, '_rag_doc_chunks') and self._rag_doc_chunks:
                            for dc in self._rag_doc_chunks[:5]:
                                _prov_pdf = {
                                    'source_type': 'pdf',
                                    'source_name': dc.get('filename', dc.get('source_file', self.ds.name if self.ds else '')),
                                    'page_number': dc.get('page_number'),
                                    'section_title': dc.get('section_title', ''),
                                    'chunk_type': dc.get('chunk_type', 'text'),
                                    'similarity': dc.get('similarity', 0),
                                }
                                if dc.get('table_index') is not None:
                                    _prov_pdf['table_index'] = dc['table_index']
                                _da_provenance.append(_prov_pdf)
                        elif self.chat_question.data_training and '<document-knowledge>' in (self.chat_question.data_training or ''):
                            _da_provenance.append({
                                'source_type': 'pdf',
                                'source_name': self.ds.name if self.ds else '',
                                'description': (
                                    'Answer generated based on document knowledge base RAG retrieval results'
                                    if _is_en_prov else '基于文档知识库RAG检索结果生成回答'
                                ),
                            })
                    elif _da_ds_type in ('excel', 'csv'):
                        # 增强 Excel/CSV 溯源信息，添加表名和数据导入方式
                        _excel_csv_prov = {
                            'source_type': _da_ds_type,
                            'source_name': self.ds.name if self.ds else '',
                            'data_storage': 'PostgreSQL (imported)',
                            'description': (
                                f'Data imported from {_da_ds_type.upper()} file into PostgreSQL, answer generated based on terminology knowledge base'
                                if _is_en_prov else f'数据已从{_da_ds_type.upper()}文件导入PostgreSQL，基于术语知识库生成回答'
                            ),
                        }
                        # 尝试获取表名信息
                        try:
                            if self.ds and isinstance(self.ds, CoreDatasource):
                                from apps.datasource.models.datasource import CoreTable
                                _prov_tables = _session.query(CoreTable).filter(
                                    CoreTable.ds_id == self.ds.id,
                                    CoreTable.checked == True
                                ).limit(5).all()
                                if _prov_tables:
                                    _excel_csv_prov['table_names'] = [
                                        t.custom_comment or t.table_comment or t.table_name
                                        for t in _prov_tables
                                    ]
                        except Exception:
                            pass
                        _da_provenance.append(_excel_csv_prov)
                    else:
                        # 增强 Database 溯源信息，记录具体使用的术语和 SQL 示例
                        _db_prov = {
                            'source_type': 'database',
                            'source_name': self.ds.name if self.ds else ('General Knowledge' if _is_en_prov else '通用知识'),
                            'description': (
                                'Answer generated based on RAG retrieval knowledge'
                                if _is_en_prov else '基于RAG检索知识生成回答'
                            ),
                            'terminologies_used': terminology_count,
                        }
                        # 附加具体术语词条（供前端溯源面板展示）
                        if hasattr(self, '_rag_terminologies') and self._rag_terminologies:
                            _db_prov['terminology_words'] = [
                                t.get('word', '') for t in self._rag_terminologies[:5] if t.get('word')
                            ]
                        # 附加 SQL 示例信息
                        if hasattr(self, '_rag_sql_examples') and self._rag_sql_examples:
                            _db_prov['sql_examples_used'] = len(self._rag_sql_examples)
                            _db_prov['sql_example_questions'] = [
                                e.get('question', '') for e in self._rag_sql_examples[:3] if e.get('question')
                            ]
                        _da_provenance.append(_db_prov)

                if _da_provenance:
                    record_provenance_stage(self.thinking_process, _da_provenance)
                    _da_prov_stage = self.thinking_process.get_stage('provenance')
                    if _da_prov_stage:
                        yield {'type': 'thinking_stage', 'stage': 'provenance', 'data': _da_prov_stage}
            except Exception as prov_e:
                ChatBILogUtil.error(f"[generate_direct_answer] Failed to record provenance: {prov_e}")
        except Exception as e:
            ChatBILogUtil.error(f"[generate_direct_answer] Failed to record {stage_name} stage: {e}")
        
        # 执行后置验证（抗幻觉）
        # validate_generation_result 已定义但之前从未被调用
        try:
            if hasattr(self, '_unified_rag_result') and self._unified_rag_result:
                _gen_val = self._unified_rag_result.get('generate')
                if _gen_val and _gen_val.validation_rules:
                    from apps.chat.thinking.unified_rag_executor import validate_generation_result
                    validation = validate_generation_result(
                        answer=full_text,
                        sql="",
                        validation_rules=_gen_val.validation_rules,
                    )
                    if validation.get("warnings"):
                        ChatBILogUtil.warning(
                            f"[generate_direct_answer] Validation warnings: {validation['warnings']}, "
                            f"confidence={validation.get('confidence', 'unknown')}"
                        )
                    # 将验证结果存入思考过程，供前端展示
                    self.thinking_process.record_stage(
                        name='post_validation',
                        status='completed',
                        extra_data=validation,
                    )
        except Exception as val_e:
            ChatBILogUtil.error(f"[generate_direct_answer] Post-validation failed: {val_e}")

        # 保存回答到record
        try:
            save_analysis_answer(session=_session, record_id=self.record.id,
                                 answer=orjson.dumps({'content': full_text, 'reasoning_content': full_thinking_text}).decode())
        except Exception as e:
            ChatBILogUtil.error(f"Failed to save direct answer: {e}")

        # 后置推荐问题（直接回答路径 — 优先使用执行器结果）
        try:
            post_recs = []
            mid_recs = []
            pre_recs = []

            # 优先使用 UnifiedRAGExecutor 的推荐问题
            if hasattr(self, '_unified_rag_result') and self._unified_rag_result:
                _gen = self._unified_rag_result.get('generate')
                _aug = self._unified_rag_result.get('augment')
                _ret = self._unified_rag_result.get('retrieve')
                if _gen and _gen.post_recommendations:
                    post_recs = _gen.post_recommendations
                if _aug and _aug.mid_recommendations:
                    mid_recs = _aug.mid_recommendations
                if _ret and _ret.pre_recommendations:
                    pre_recs = _ret.pre_recommendations

            # 兜底：执行器未运行时使用 RecommendationEngine
            if not post_recs and not mid_recs:
                from apps.chat.thinking.recommendation_engine import RecommendationEngine
                _ds_type_rec_da = (self.ds.type or '').lower() if self.ds else 'database'
                post_recs = RecommendationEngine.generate_post_recommendations(
                    question=self.chat_question.question,
                    chart_type='table',
                    intent=intent,
                    ds_type=_ds_type_rec_da,
                    lang=self.chat_question.lang,
                )
                mid_recs = RecommendationEngine.generate_mid_recommendations(
                    question=self.chat_question.question,
                    intent=intent,
                    ds_type=_ds_type_rec_da,
                    retrieval_results={'doc_chunks': getattr(self, '_rag_doc_chunks', [])},
                    lang=self.chat_question.lang,
                )

            if post_recs or mid_recs or pre_recs:
                yield {'type': 'layered_recommendations', 'data': {'pre': pre_recs, 'mid': mid_recs, 'post': post_recs}}
        except Exception as e:
            ChatBILogUtil.error(f"[generate_direct_answer] Recommendation generation failed: {e}")

    def select_datasource(self, _session: Session):
        datasource_msg: List[Union[BaseMessage, dict[str, Any]]] = []
        datasource_msg.append(SystemMessage(self.chat_question.datasource_sys_question()))
        if self.current_assistant and self.current_assistant.type != 4:
            _ds_list = get_assistant_ds(session=_session, llm_service=self)
        else:
            stmt = select(CoreDatasource.id, CoreDatasource.name, CoreDatasource.description).where(
                and_(CoreDatasource.oid == self.current_user.oid))
            _ds_list = [
                {
                    "id": ds.id,
                    "name": ds.name,
                    "description": ds.description
                }
                for ds in _session.exec(stmt)
            ]
        if not _ds_list:
            raise SingleMessageError('No available datasource configuration found')
        ignore_auto_select = _ds_list and len(_ds_list) == 1
        # ignore auto select ds

        full_thinking_text = ''
        full_text = ''
        if not ignore_auto_select:
            if settings.TABLE_EMBEDDING_ENABLED and (
                    not self.current_assistant or (self.current_assistant and self.current_assistant.type != 1)):
                _ds_list = get_ds_embedding(_session, self.current_user, _ds_list, self.out_ds_instance,
                                            self.chat_question.question, self.current_assistant)
                # yield {'content': '{"id":' + str(ds.get('id')) + '}'}

            _ds_list_dict = []
            for _ds in _ds_list:
                _ds_list_dict.append(_ds)
            datasource_msg.append(
                HumanMessage(self.chat_question.datasource_user_question(orjson.dumps(_ds_list_dict).decode())))

            self.current_logs[OperationEnum.CHOOSE_DATASOURCE] = start_log(session=_session,
                                                                           ai_modal_id=self.chat_question.ai_modal_id,
                                                                           ai_modal_name=self.chat_question.ai_modal_name,
                                                                           operate=OperationEnum.CHOOSE_DATASOURCE,
                                                                           record_id=self.record.id,
                                                                           full_message=[{'type': msg.type,
                                                                                          'content': msg.content}
                                                                                         for
                                                                                         msg in datasource_msg])

            # 使用JSON模式LLM进行数据源选择（强制结构化输出）
            json_llm = self.get_json_mode_llm()
            
            token_usage = {}
            res = process_stream(json_llm.stream(datasource_msg), token_usage)
            for chunk in res:
                # 安全处理：确保content不为None
                content = chunk.get('content')
                if content:
                    full_text += content
                reasoning_content = chunk.get('reasoning_content')
                if reasoning_content:
                    full_thinking_text += reasoning_content
                yield chunk
            datasource_msg.append(AIMessage(full_text))

            self.current_logs[OperationEnum.CHOOSE_DATASOURCE] = end_log(session=_session,
                                                                         log=self.current_logs[
                                                                             OperationEnum.CHOOSE_DATASOURCE],
                                                                         full_message=[
                                                                             {'type': msg.type,
                                                                              'content': msg.content}
                                                                             for msg in datasource_msg],
                                                                         reasoning_content=full_thinking_text,
                                                                         token_usage=token_usage)

            json_str = extract_json_robust(full_text)
            if json_str is None:
                raise SingleMessageError(f'Cannot parse datasource from answer: {full_text}')
            ds = orjson.loads(json_str)

        _error: Exception | None = None
        _datasource: int | None = None
        _engine_type: str | None = None
        try:
            data: dict = _ds_list[0] if ignore_auto_select else ds

            if data.get('id') and data.get('id') != 0:
                _datasource = data['id']
                _chat = _session.get(Chat, self.record.chat_id)
                _chat.datasource = _datasource
                if self.current_assistant and self.current_assistant.type in dynamic_ds_types:
                    _ds = self.out_ds_instance.get_ds(data['id'])
                    self.ds = _ds
                    self.chat_question.engine = _ds.type + get_version(self.ds)
                    self.chat_question.ds_type = _ds.type
                    self.chat_question.db_schema = self.out_ds_instance.get_db_schema(self.ds.id,
                                                                                      self.chat_question.question)
                    _engine_type = self.chat_question.engine
                    _chat.engine_type = _ds.type
                else:
                    _ds = _session.get(CoreDatasource, _datasource)
                    if not _ds:
                        _datasource = None
                        raise SingleMessageError(f"Datasource configuration with id {_datasource} not found")
                    self.ds = CoreDatasource(**_ds.model_dump())
                    self.chat_question.engine = (_ds.type_name if _ds.type not in ('excel', 'csv', 'pdf') else 'PostgreSQL') + get_version(
                        self.ds)
                    self.chat_question.ds_type = _ds.type
                    self.chat_question.db_schema = get_table_schema(session=_session,
                                                                        current_user=self.current_user, ds=self.ds,
                                                                        question=self.chat_question.question)
                    _engine_type = self.chat_question.engine
                    _chat.engine_type = _ds.type_name
                # save chat
                with _session.begin_nested():
                    # 为了能继续记日志，先单独处理下事务
                    try:
                        _session.add(_chat)
                        _session.flush()
                        _session.refresh(_chat)
                        _session.commit()
                    except Exception as e:
                        _session.rollback()
                        raise e

            elif data.get('fail'):
                # 使用data.get('fail')避免KeyError
                raise SingleMessageError(data['fail'])
            else:
                raise SingleMessageError('No available datasource configuration found')

        except Exception as e:
            _error = e

        if not ignore_auto_select and not settings.TABLE_EMBEDDING_ENABLED:
            self.record = save_select_datasource_answer(session=_session, record_id=self.record.id,
                                                        answer=orjson.dumps({'content': full_text}).decode(),
                                                        datasource=_datasource,
                                                        engine_type=_engine_type)
        if self.ds:
            oid = self.ds.oid if isinstance(self.ds, CoreDatasource) else 1
            ds_id = self.ds.id if isinstance(self.ds, CoreDatasource) else None

            # RAG 永远开启（对齐 SQLBot）
            rag_enabled = True
            
            # 早期意图检测（select_datasource路径）
            self._early_intent = QueryRewriter._detect_intent(self.chat_question.question, ds_type=self.ds.type if self.ds else 'database')
            ChatBILogUtil.info(f"[select_datasource] Early intent: {self._early_intent}")
            
            # ========== follow_up意图继承（select_datasource路径） ==========
            if self._early_intent == 'follow_up':
                try:
                    from apps.chat.crud.chat import list_chat_records_for_dialogue
                    _chat_id = self.chat_question.chat_id if hasattr(self.chat_question, 'chat_id') else None
                    _inherited = None
                    if _chat_id:
                        _prev_recs = list_chat_records_for_dialogue(_session, _chat_id, max_turns=5)
                        for _pr in reversed(_prev_recs):
                            if _pr.get('intent') and _pr['intent'] not in ('follow_up', 'irrelevant_query', 'ambiguous_query'):
                                _inherited = _pr['intent']
                                break
                    if _inherited:
                        # D2 话题切换检测：检查当前问题是否包含与上轮不同的强意图信号
                        _q_lower = self.chat_question.question.lower()
                        _topic_switch = False
                        # 预测信号 vs 非预测继承
                        if _inherited != 'prediction' and any(kw in _q_lower for kw in ['预测', '预估', '预计', 'forecast', 'predict']):
                            _topic_switch = True
                        # 对比信号 vs 非对比继承
                        if _inherited != 'comparison_analysis' and any(kw in _q_lower for kw in ['对比', '比较', '同比', '环比', 'compare', 'vs']):
                            _topic_switch = True
                        # 趋势信号 vs 非趋势继承
                        if _inherited != 'trend_analysis' and any(kw in _q_lower for kw in ['趋势', '走势', '变化', 'trend']):
                            _topic_switch = True
                        if _topic_switch:
                            ChatBILogUtil.info(f"[select_datasource][follow_up] Topic switch detected, re-detecting intent instead of inheriting '{_inherited}'")
                            # 重新检测意图（去掉追问指代词后）
                            import re as _re
                            _cleaned_q = _re.sub(r'(上面|上述|刚才|之前|继续|接着|进一步|那么)', '', _q_lower).strip()
                            self._early_intent = QueryRewriter._detect_intent(_cleaned_q, ds_type=self.ds.type if self.ds else 'database')
                        else:
                            ChatBILogUtil.info(f"[select_datasource][follow_up] Inherited intent: {_inherited}")
                            self._early_intent = _inherited
                    else:
                        self._early_intent = 'fact_query'
                except Exception as e:
                    ChatBILogUtil.error(f"[select_datasource][follow_up] Inheritance failed: {e}")
                    self._early_intent = 'fact_query'
            
            # PDF数据源一律走直接回答路径（RAG+LLM文档问答）
            self._pdf_has_tables = None
            _ds_type_early_sd = self.ds.type.lower() if self.ds and self.ds.type else ''
            if _ds_type_early_sd == 'pdf':
                self._pdf_has_tables = False
                ChatBILogUtil.info(f"[select_datasource][PDF route] PDF datasource always uses direct answer path (RAG+LLM)")
                # 保留 comparison_analysis 意图（与 _execute_query_understanding 一致）
                if self._early_intent not in ('irrelevant_query', 'document_qa', 'comparison_analysis'):
                    ChatBILogUtil.info(f"[select_datasource][PDF route] Adjusting early intent from '{self._early_intent}' to 'document_qa'")
                    self._early_intent = 'document_qa'
            
            # 纯寒暄快速路径（与existing ds路径一致）
            _skip_rag_select = self._early_intent == 'irrelevant_query' and QueryRewriter._is_trivial_chat(self.chat_question.question)
            if _skip_rag_select:
                rag_enabled = False
                self.chat_question.terminologies = ''
                self.chat_question.data_training = ''
                self.chat_question.db_schema = ''  #  纯寒暄不需要表结构
                ChatBILogUtil.info(f"[select_datasource][trivial_chat] Fast path: skipping all RAG processing")
                
                # 纯寒暄也需要发送查询理解阶段（步骤1），让前端展示完整的思考链
                try:
                    from apps.chat.thinking.thinking_integration import record_query_understanding_stage
                    record_query_understanding_stage(
                        self.thinking_process,
                        original_query=self.chat_question.question,
                        rewritten_query=self.chat_question.question,
                        intent='irrelevant_query',
                        rewrite_applied=False,
                        extracted_keywords=[],
                        dialogue_turn=1,
                        context_references=[],
                        ds_type=(self.ds.type or '').lower() if hasattr(self, 'ds') and self.ds else '',
                        ds_name=(self.ds.name or '') if hasattr(self, 'ds') and self.ds else '',
                        intent_keywords=['纯寒暄/帮助类'],
                    )
                    qu_stage = self.thinking_process.get_stage('query_understanding')
                    if qu_stage:
                        yield {'type': 'thinking_stage', 'stage': 'query_understanding', 'data': qu_stage}
                except Exception as e:
                    ChatBILogUtil.error(f"[select_datasource] Failed to record query_understanding for trivial chat: {e}")
            
            # 记录RAG检索开始时间
            rag_start_time = time.time()
            
            if not _skip_rag_select:
                # 使用统一的查询理解方法（消除与 existing_ds 路径的代码重复）
                _ds_type_for_rewrite = self.ds.type if self.ds else 'database'
                _qu_result = self._execute_query_understanding(_session, _ds_type_for_rewrite, path_label='select_ds')
                rewrite_result = _qu_result['rewrite_result']
                retrieval_question = _qu_result['retrieval_question']
            else:
                # 纯寒暄路径：设置默认值供后续代码使用
                rewrite_result = {'rewritten': self.chat_question.question, 'rewrite_applied': False, 'intent': 'irrelevant_query', 'extracted_keywords': []}
                self._rewrite_result = rewrite_result
                retrieval_question = self.chat_question.question
            
            # 对话状态追踪（所有路径都需要）
            try:
                _record_id = self.record.id if hasattr(self, 'record') and self.record else None
                self.dialogue_tracker.track_turn(question=self.chat_question.question, record_id=_record_id)
                # 记录对话上下文注入信息到思考过程（让用户看到LLM收到了什么上下文）
                if self.dialogue_tracker.turns:
                    _dlg_ctx = self.dialogue_tracker.get_dialogue_context(max_turns=3)
                    if _dlg_ctx.get('total_turns', 0) > 0:
                        self.thinking_process.dialogue_context_injected = {
                            'total_turns': _dlg_ctx.get('total_turns', 0),
                            'current_intent': _dlg_ctx.get('current_intent', ''),
                            'current_topic': _dlg_ctx.get('current_topic', ''),
                            'active_entities': _dlg_ctx.get('active_entities', [])[:5],
                            'recent_questions': _dlg_ctx.get('recent_questions', [])[-3:],
                            'context_references': _dlg_ctx.get('context_references', []),
                            'injected': True
                        }
            except Exception as e:
                ChatBILogUtil.error(f"Dialogue state tracking failed: {e}")
            
            # 存储RAG检索结果用于前端展示
            terminology_results = []
            sql_example_results = []
            custom_prompts_used = []
            doc_chunk_results = []
            self._custom_prompts_used = custom_prompts_used  # 存储为实例属性，供其他方法访问
            
            if rag_enabled:
                # 导入术语和训练数据的详细检索函数
                from apps.terminology.crud.terminology import select_terminology_by_word_with_details
                from apps.data_training.crud.data_training import select_training_by_question_with_details
                from apps.chat.thinking.rag_reranker import RAGReranker, RAGQualityEnhancer
                
                # 根据数据源类型+意图判断是否检索SQL示例库
                from apps.chat.thinking.ds_component_router import should_skip_sql_examples as _should_skip_sql_sd
                _early_route_sd = QueryRewriter.map_to_route(getattr(self, '_early_intent', ''))
                _ds_type_for_routing_sd = self.ds.type if self.ds and self.ds.type else 'database'
                _skip_sql_examples_sd = _should_skip_sql_sd(_ds_type_for_routing_sd, _early_route_sd)
                if _skip_sql_examples_sd:
                    from apps.chat.thinking.ds_component_router import get_routing_reason
                    _skip_reason_sd = get_routing_reason(_ds_type_for_routing_sd, 'sql_examples')
                    ChatBILogUtil.info(f"[select_datasource][RAG routing] Skipping SQL examples: {_skip_reason_sd} (intent='{self._early_intent}', route={_early_route_sd}, ds_type={_ds_type_for_routing_sd})")
                
                # 获取详细检索结果（用于质量过滤、重排序和前端展示）
                try:
                    # 术语检索结果（包含相似度）- 使用重写后的查询保持一致性
                    terminology_details = select_terminology_by_word_with_details(
                        _session, retrieval_question, oid, ds_id
                    )
                    
                    # 仅在需要SQL的路由下检索SQL示例库
                    if _skip_sql_examples_sd:
                        training_details = []
                    elif self.current_assistant and self.current_assistant.type == 1:
                        training_details = select_training_by_question_with_details(
                            _session, retrieval_question, oid, None, self.current_assistant.id
                        )
                    else:
                        training_details = select_training_by_question_with_details(
                            _session, retrieval_question, oid, ds_id
                        )
                    
                    # 🔥 多路检索合并：使用扩展查询补充检索结果
                    expanded_queries = rewrite_result.get('expanded_queries', [])
                    for eq in expanded_queries:
                        try:
                            extra_terms = select_terminology_by_word_with_details(
                                _session, eq, oid, ds_id
                            )
                            existing_words = {t.get('word', '') for t in terminology_details}
                            for et in extra_terms:
                                if et.get('word', '') not in existing_words:
                                    terminology_details.append(et)
                                    existing_words.add(et.get('word', ''))
                            
                            if not _skip_sql_examples_sd:
                                if self.current_assistant and self.current_assistant.type == 1:
                                    extra_examples = select_training_by_question_with_details(
                                        _session, eq, oid, None, self.current_assistant.id
                                    )
                                else:
                                    extra_examples = select_training_by_question_with_details(
                                        _session, eq, oid, ds_id
                                    )
                                existing_questions = {e.get('question', '') for e in training_details}
                                for ee in extra_examples:
                                    if ee.get('question', '') not in existing_questions:
                                        training_details.append(ee)
                                        existing_questions.add(ee.get('question', ''))
                        except Exception as e:
                            ChatBILogUtil.error(f"Expanded query retrieval failed for '{eq}': {e}")
                    
                    # Step A: 质量过滤（与existing ds路径一致：先过滤再预压缩再重排序）
                    try:
                        all_evidence = []
                        for t in terminology_details:
                            all_evidence.append({**t, 'source_type': 'terminology'})
                        for e in training_details:
                            all_evidence.append({**e, 'source_type': 'sql_example'})
                        
                        if all_evidence:
                            filtered, removed = filter_rag_evidence(all_evidence, threshold=0.35)
                            terminology_details = [e for e in filtered if e.get('source_type') == 'terminology']
                            training_details = [e for e in filtered if e.get('source_type') == 'sql_example']
                            if removed:
                                ChatBILogUtil.info(f"Quality filter (select_ds): {len(removed)} low-quality items removed")
                    except Exception as e:
                        ChatBILogUtil.error(f"Quality filter failed (select_ds): {e}")
                    
                    # Step B: 预过滤（相似度阈值+去重+截断）
                    try:
                        _sql_gen_config = ContextCompressor.get_config('sql_generation')
                        compressed_terms, compressed_examples, compress_stats = ContextCompressor.compress_retrieval_results(
                            terminology_results=terminology_details,
                            sql_example_results=training_details,
                            config=_sql_gen_config,
                        )
                        if compress_stats.get('terms_removed', 0) > 0 or compress_stats.get('examples_removed', 0) > 0:
                            ChatBILogUtil.info(f"Pre-rerank compression: terms {compress_stats['original_terms']}->{compress_stats['compressed_terms']}, examples {compress_stats['original_examples']}->{compress_stats['compressed_examples']}")
                            terminology_details = compressed_terms
                            training_details = compressed_examples
                    except Exception as e:
                        ChatBILogUtil.error(f"Pre-rerank compression failed: {e}")
                    
                    # 📚 文档知识库语义检索（RAG核心：向量检索文档分块）
                    doc_chunk_results = []
                    _ds_type_for_doc_sd = (self.ds.type or '').lower() if self.ds else ''
                    if _ds_type_for_doc_sd == 'pdf':
                        try:
                            from apps.datasource.document_retrieval import search_document_chunks, format_document_context
                            # 使用savepoint隔离文档检索
                            _doc_savepoint = _session.begin_nested()
                            try:
                                doc_chunk_results = search_document_chunks(
                                    _session, retrieval_question, oid=oid, top_k=5, similarity_threshold=0.3,
                                    ds_id=ds_id,
                                )
                                _doc_savepoint.commit()
                            except Exception as e:
                                _doc_savepoint.rollback()
                                ChatBILogUtil.error(f"Document chunk retrieval failed: {e}")
                                ChatBILogUtil.info("Savepoint rolled back after document retrieval failure (select_ds)")
                        except Exception as e:
                            ChatBILogUtil.error(f"Document retrieval setup failed: {e}")
                    
                    # Step C: 智能重排序（ChatBI核心优势）
                    reranked_results = RAGReranker.rerank_combined_results(
                        terminologies=terminology_details,
                        sql_examples=training_details,
                        custom_prompts=[],
                        question=self.chat_question.question,
                        datasource_id=ds_id
                    )
                    
                    # 使用重排序后的结果
                    terminology_details = reranked_results['terminologies']
                    training_details = reranked_results['sql_examples']
                    
                    # Step D: 基于过滤+重排序后的结果生成XML模板（确保模板与结构化数据一致）
                    self.chat_question.terminologies = build_terminology_template_from_details(terminology_details, ds_type=self.ds.type if self.ds else '')
                    self.chat_question.data_training = build_training_template_from_details(training_details)
                    
                    # 注入文档知识库检索结果到上下文
                    if doc_chunk_results:
                        try:
                            from apps.datasource.document_retrieval import format_document_context
                            doc_context = format_document_context(doc_chunk_results, lang=self.chat_question.lang)
                            if doc_context:
                                doc_prefix = "\n\n<document-knowledge>\n"
                                doc_suffix = "\n</document-knowledge>"
                                self.chat_question.data_training = (self.chat_question.data_training or '') + doc_prefix + doc_context + doc_suffix
                                ChatBILogUtil.info(f"Document retrieval: {len(doc_chunk_results)} chunks injected into context")
                        except Exception as e:
                            ChatBILogUtil.error(f"Document context formatting failed: {e}")
                    
                    # 增强结果信息
                    for term in terminology_details[:5]:  # 只取前5个
                        enhanced_term = RAGQualityEnhancer.enhance_terminology(term, lang=self.chat_question.lang)
                        terminology_results.append({
                            'word': enhanced_term['word'],
                            'description': enhanced_term['description'],
                            'similarity': enhanced_term['similarity'] / 100.0 if enhanced_term['similarity'] > 1 else enhanced_term['similarity'],
                            'match_type': enhanced_term['match_type'],
                            'used': True,
                            'rerank_score': enhanced_term.get('rerank_score', 0),
                            'usage_hint': enhanced_term.get('usage_hint', ''),
                        })
                    
                    for example in training_details[:3]:  # 只取前3个
                        enhanced_example = RAGQualityEnhancer.enhance_sql_example(example, lang=self.chat_question.lang)
                        sql_example_results.append({
                            'question': enhanced_example['question'],
                            'sql': enhanced_example['sql'],
                            'similarity': enhanced_example['similarity'] / 100.0 if enhanced_example['similarity'] > 1 else enhanced_example['similarity'],
                            'match_type': enhanced_example['match_type'],
                            'used': True,
                            'rerank_score': enhanced_example.get('rerank_score', 0),
                            'sql_features': enhanced_example.get('sql_features', []),
                            'applicable_scenarios': enhanced_example.get('applicable_scenarios', '')
                        })
                except Exception as e:
                    ChatBILogUtil.error(f"Failed to get RAG retrieval details in select_datasource: {e}")
                    ChatBILogUtil.exception()
                
                # 后置术语扩展（select_datasource路径）
                if terminology_results and rag_enabled:
                    try:
                        expanded_query = QueryRewriter.post_expand_with_terminologies(
                            retrieval_question, terminology_results
                        )
                        if expanded_query != retrieval_question:
                            ChatBILogUtil.info(f"Post-expand with terminologies (select_ds): '{retrieval_question}' -> '{expanded_query}'")
                            retrieval_question = expanded_query
                    except Exception as e:
                        ChatBILogUtil.error(f"Post-expand with terminologies failed (select_ds): {e}")
            else:
                # 纯LLM模式：不使用RAG检索
                self.chat_question.terminologies = ''
                self.chat_question.data_training = ''
            
            # 上下文压缩：使用重排序感知的高级压缩策略
            # compress_with_reranking根据重排序质量评分动态调整Token预算分配
            self._apply_context_compression(
                rag_enabled=rag_enabled,
                terminology_results=terminology_results,
                sql_example_results=sql_example_results,
                max_total_tokens=800,
                tag="[select_ds]",
            )
            
            # 获取自定义提示词（智能匹配）
            # 仅SQL路由下检索SQL生成提示词
            custom_prompt_checked = False
            _question = self.chat_question.question or ''
            if ChatBILicenseUtil.valid() and not _skip_sql_examples_sd:
                _total_sql = count_custom_prompts(_session, CustomPromptTypeEnum.GENERATE_SQL, oid, ds_id)
                custom_prompt_content, _sql_details = find_relevant_custom_prompts(
                    _session, CustomPromptTypeEnum.GENERATE_SQL, oid, _question, ds_id)
                self.chat_question.custom_prompt = custom_prompt_content
                custom_prompt_checked = True
                
                # 记录提示词使用情况
                _sql_matched_count = len([d for d in _sql_details if d.get('reason') != 'not_matched'])
                _is_en_cp_sql = (self.chat_question.lang or '').lower().startswith('en')
                custom_prompts_used.append({
                    'type': 'SQL Generation' if _is_en_cp_sql else 'SQL生成',
                    'content': custom_prompt_content[:200] + '...' if custom_prompt_content and len(custom_prompt_content) > 200 else (custom_prompt_content or ''),
                    'used': _sql_matched_count > 0,
                    'empty': _total_sql == 0,
                    'count': _sql_matched_count,
                    'total': _total_sql,
                    'matched': _sql_details
                })
                
                # 场景感知提示词：SQL路径只加载SQL生成提示词
            elif _skip_sql_examples_sd:
                ChatBILogUtil.info(f"[select_datasource][RAG optimization] Skipping SQL custom prompt retrieval for intent '{self._early_intent}'")
                
            # 仅SQL路径时初始化SQL消息
            # general_chat 路由走 generate_direct_answer，不需要 sql_message
            _early_route_for_init_sd = QueryRewriter.map_to_route(getattr(self, '_early_intent', 'data_query'))
            if not _skip_sql_examples_sd and _early_route_for_init_sd != 'general_chat':
                # 初始化SQL消息
                self.init_messages()
            
            # 计算RAG检索耗时
            rag_retrieval_time = time.time() - rag_start_time
            
            # 缓存RAG结果供评估使用（质量过滤已在检索阶段完成）
            self._rag_terminologies = terminology_results
            self._rag_sql_examples = sql_example_results
            self._rag_doc_chunks = doc_chunk_results
            
            # ========== 检索结果有效性校验 ==========
            retrieval_validation = {
                'first_retrieval_count': len(terminology_results) + len(sql_example_results),
                'second_retrieval_triggered': False,
                'second_retrieval_reason': None,
                'final_count': 0,
            }
            try:
                first_total = len(terminology_results) + len(sql_example_results)
                # 计算首次检索的平均相似度
                all_scores = [t.get('similarity', 0) for t in terminology_results] + \
                             [e.get('similarity', 0) for e in sql_example_results]
                avg_similarity = sum(all_scores) / len(all_scores) if all_scores else 0
                
                # 触发二次检索的条件：检索结果为空 或 平均相似度过低
                need_second = False
                reason = ''
                if first_total == 0 and rag_enabled:
                    need_second = True
                    reason = 'no_results'
                elif avg_similarity < 0.3 and first_total < 3 and rag_enabled:
                    need_second = True
                    reason = 'low_quality'
                
                if need_second and hasattr(self, '_rewrite_result') and self._rewrite_result:
                    retrieval_validation['second_retrieval_triggered'] = True
                    retrieval_validation['second_retrieval_reason'] = reason
                    ChatBILogUtil.info(f"Triggering second retrieval: reason={reason}, first_count={first_total}, avg_sim={avg_similarity:.3f}")
                    
                    # 二次检索策略：使用扩展查询 + 降低相似度阈值
                    expanded_queries = self._rewrite_result.get('expanded_queries', [])
                    retry_query = expanded_queries[0] if expanded_queries else self._rewrite_result.get('rewritten', self.chat_question.question)
                    
                    # 二次检索使用带详情的检索函数（返回列表而非XML字符串）
                    from apps.terminology.crud.terminology import select_terminology_by_word_with_details
                    from apps.data_training.crud.data_training import select_training_by_question_with_details
                    
                    try:
                        retry_term_results = select_terminology_by_word_with_details(
                            _session, retry_query, oid, ds_id
                        )
                    except Exception as e:
                        ChatBILogUtil.error(f"Second retrieval (terminology) failed: {e}")
                        retry_term_results = []
                    
                    try:
                        retry_sql_results = select_training_by_question_with_details(
                            _session, retry_query, oid, ds_id
                        )
                    except Exception as e:
                        ChatBILogUtil.error(f"Second retrieval (sql examples) failed: {e}")
                        retry_sql_results = []
                    
                    # 合并去重：保留首次检索结果 + 新增的二次检索结果
                    existing_term_words = {t.get('word', '') for t in terminology_results}
                    for rt in (retry_term_results or []):
                        if rt.get('word', '') not in existing_term_words:
                            terminology_results.append(rt)
                    
                    existing_sql_questions = {e.get('question', '') for e in sql_example_results}
                    for rs in (retry_sql_results or []):
                        if rs.get('question', '') not in existing_sql_questions:
                            sql_example_results.append(rs)
                    
                    # 重建术语和SQL示例模板（使用标准模板构建函数）
                    if terminology_results:
                        self.chat_question.terminologies = build_terminology_template_from_details(terminology_results)
                    
                    if sql_example_results:
                        self.chat_question.data_training = build_training_template_from_details(sql_example_results)
                    
                    ChatBILogUtil.info(f"Second retrieval completed: {first_total} -> {len(terminology_results) + len(sql_example_results)}")
                
                retrieval_validation['final_count'] = len(terminology_results) + len(sql_example_results)
            except Exception as e:
                ChatBILogUtil.error(f"Retrieval validation failed: {e}")
            
            # 记录检索校验阶段到思考过程
            try:
                self.thinking_process.record_stage(
                    name='retrieval_validation',
                    status='completed',
                    duration=0,
                    extra_data=retrieval_validation
                )
            except Exception:
                pass
            
            # 计算RAG质量指标（新增 - 专业评估）
            from apps.chat.thinking.rag_thinking import RAGQualityMetrics
            
            terminology_quality = RAGQualityMetrics.calculate_retrieval_quality(
                terminology_results, threshold=0.7
            ) if terminology_results else {}
            
            example_quality = RAGQualityMetrics.calculate_retrieval_quality(
                sql_example_results, threshold=0.7
            ) if sql_example_results else {}
            
            # rag_impact计算 - 正确传递各维度知识列表（包含文档片段）
            _ds_type_for_impact = (self.ds.type or 'database').lower() if self.ds else 'database'
            _intent_for_impact = 'sql'
            if hasattr(self, '_unified_rag_result') and self._unified_rag_result:
                _ret_imp = self._unified_rag_result.get('retrieve')
                if _ret_imp:
                    _intent_for_impact = _ret_imp.intent or 'sql'
            rag_impact = RAGQualityMetrics.calculate_rag_impact(
                rag_enabled,
                terminology_results,
                sql_example_results,
                doc_chunks=doc_chunk_results,
                table_matches=self._build_table_match_items(),
                ds_type=_ds_type_for_impact,
                intent=_intent_for_impact,
            )
            
            # 保存RAG检索结果和提示词使用情况（在select_datasource阶段）
            # 无论RAG是否开启，都要保存完整的知识使用情况
            try:
                rag_results_data = {
                    'terminologies': terminology_results,
                    'sql_examples': sql_example_results,
                    'custom_prompts': custom_prompts_used,
                    'rag_enabled': rag_enabled,
                    'custom_prompt_checked': custom_prompt_checked,
                    # 新增：质量评估指标
                    'terminology_quality': terminology_quality,
                    'example_quality': example_quality,
                    'rag_impact': rag_impact,
                    # 新增：文档知识库检索结果
                    'document_chunks': [
                        {
                            'text': dc.get('text', '')[:300],
                            'source_type': dc.get('source_type', 'file'),
                            'source_name': dc.get('source_name', dc.get('filename', '')),
                            'source_file': dc.get('filename', dc.get('source_file', '')),
                            'section_title': dc.get('section_title', ''),
                            'page_number': dc.get('page_number'),
                            'similarity': dc.get('similarity', 0),
                            'chunk_type': dc.get('chunk_type', 'text'),
                        }
                        for dc in doc_chunk_results[:5]
                    ] if doc_chunk_results else [],
                }

                # select_datasource路径也需要附加PDF元数据（与existing ds路径一致）
                _ds_type_sel = (self.ds.type or '').lower() if self.ds else ''
                if _ds_type_sel == 'pdf' and doc_chunk_results:
                    rag_results_data['pdf_source_summary'] = get_pdf_source_summary(doc_chunk_results)
                if hasattr(self, '_unified_rag_result') and self._unified_rag_result:
                    _ret_sel = self._unified_rag_result.get('retrieve')
                    _aug_sel = self._unified_rag_result.get('augment')
                    if _ret_sel:
                        rag_results_data['design_intent'] = _ret_sel.intent
                        rag_results_data['fine_intent'] = _ret_sel.fine_intent
                    if _aug_sel:
                        rag_results_data['components_used'] = _aug_sel.components_used
                        rag_results_data['visualization_detected'] = _aug_sel.visualization_detected

                save_rag_results(
                    session=_session,
                    record_id=self.record.id,
                    rag_enabled=rag_enabled,
                    rag_results=orjson.dumps(rag_results_data).decode()
                )
                
                # 发送RAG检索结果到前端（SSE事件）
                # select_datasource路径也需通过SSE发送给前端
                yield {'type': 'rag_results', 'data': rag_results_data}
                
                # 记录RAG检索阶段到思考过程（统一函数）
                _ds_type_for_schema = (self.ds.type or 'database').lower() if self.ds else 'database'
                _intent_for_schema = 'sql'
                if hasattr(self, '_unified_rag_result') and self._unified_rag_result:
                    _ret = self._unified_rag_result.get('retrieve')
                    if _ret:
                        _intent_for_schema = _ret.intent or 'sql'
                record_rag_retrieval(
                    self.thinking_process,
                    question=self.chat_question.question,
                    table_candidates=getattr(self, '_table_match_details', {}).get('table_candidates', []),
                    selected_tables=getattr(self, '_table_match_details', {}).get('selected_tables', []),
                    similarities=getattr(self, '_table_match_details', {}).get('similarities', []),
                    terminologies=terminology_results,
                    sql_examples=sql_example_results,
                    custom_prompts=custom_prompts_used,
                    retrieval_time=rag_retrieval_time,
                    rag_enabled=rag_enabled,
                    doc_chunks=doc_chunk_results,
                    ds_type=_ds_type_for_schema,
                    intent=_intent_for_schema,
                )
                
                # 精简后的6阶段流程：查询理解 → 知识检索 → 提示词构建 → SQL生成 → SQL执行 → 输出决策
                
                # 1. 查询理解阶段（合并了查询重写+对话上下文）
                # 注：纯寒暄路径已在_skip_rag_select块中提前发送，此处仅为正常路径发送
                if not _skip_rag_select:
                    qu_stage_data = self.thinking_process.get_stage('query_understanding')
                    if qu_stage_data:
                        yield {'type': 'thinking_stage', 'stage': 'query_understanding', 'data': qu_stage_data}
                
                # 2. RAG知识检索阶段
                rag_stage_data = self.thinking_process.get_stage('rag_retrieval')
                if rag_stage_data:
                    yield {'type': 'thinking_stage', 'stage': 'rag_retrieval', 'data': rag_stage_data}
                
                # 2.5 子问题分解阶段
                _qd_stage = self.thinking_process.get_stage('query_decomposition')
                if _qd_stage:
                    yield {'type': 'thinking_stage', 'stage': 'query_decomposition', 'data': _qd_stage}
                
                # 2.6 检索结果校验阶段（二次检索）
                rv_stage_data = self.thinking_process.get_stage('retrieval_validation')
                if rv_stage_data:
                    yield {'type': 'thinking_stage', 'stage': 'retrieval_validation', 'data': rv_stage_data}
                
                # 2.7 上下文压缩阶段
                cc_stage_data = self.thinking_process.get_stage('context_compression')
                if cc_stage_data:
                    yield {'type': 'thinking_stage', 'stage': 'context_compression', 'data': cc_stage_data}
                
                # 注：提示词构建、SQL生成、SQL执行、输出决策阶段在后续流程中发送
                
            except Exception as e:
                ChatBILogUtil.error(f"Failed to save RAG results in select_datasource: {e}")
                ChatBILogUtil.exception()

        if _error:
            raise _error

    def save_error(self, session: Session, message: str):
        sanitized = sanitize_error_message(message)
        return save_error_message(session=session, record_id=self.record.id, message=sanitized)

    def save_sql_data(self, session: Session, data_obj: Dict[str, Any]):
        try:
            data_result = data_obj.get('data')
            limit = 1000
            if data_result:
                data_result = prepare_for_orjson(data_result)
                if data_result and len(data_result) > limit and settings.GENERATE_SQL_QUERY_LIMIT_ENABLED:
                    data_obj['data'] = data_result[:limit]
                    data_obj['limit'] = limit
                else:
                    data_obj['data'] = data_result
            return save_sql_exec_data(session=session, record_id=self.record.id,
                                      data=orjson.dumps(data_obj).decode())
        except Exception as e:
            raise e

    def finish(self, session: Session):
        # 完成对话后失效缓存
        # 新记录已写入DB，缓存中的历史记录已过时，下次请求需重新加载
        try:
            _cache_key = (self.current_user.id, self.chat_question.chat_id)
            with self.__class__._dialogue_history_cache_lock:
                self.__class__._dialogue_history_cache.pop(_cache_key, None)
        except Exception:
            pass  # 缓存失效失败不影响主流程
        return finish_record(session=session, record_id=self.record.id)

    def pop_chunk(self):
        try:
            chunk = self.chunk_list.pop(0)
            return chunk
        except IndexError as e:
            return None

    def await_result(self):
        while self.is_running():
            while True:
                chunk = self.pop_chunk()
                if chunk is not None:
                    yield chunk
                else:
                    break
        while True:
            chunk = self.pop_chunk()
            if chunk is None:
                break
            yield chunk

    def run_task_async(self, in_chat: bool = True, stream: bool = True,
                       finish_step: ChatFinishStep = ChatFinishStep.GENERATE_CHART):
        if in_chat:
            stream = True
        self.future = executor.submit(self.run_task_cache, in_chat, stream, finish_step)

    def run_task_cache(self, in_chat: bool = True, stream: bool = True,
                       finish_step: ChatFinishStep = ChatFinishStep.GENERATE_CHART):
        for chunk in self.run_task(in_chat, stream, finish_step):
            self.chunk_list.append(chunk)

    def run_task(self, in_chat: bool = True, stream: bool = True,
                 finish_step: ChatFinishStep = ChatFinishStep.GENERATE_CHART):
        """主任务执行入口"""
        json_result: Dict[str, Any] = {'success': True}
        _session = None
        try:
            _session = session_maker()
            _task_start_time = time.time()
            ChatBILogUtil.info(f"[PERF] ========== run_task START, record_id={self.get_record().id}, question='{self.chat_question.question[:50]}' ==========")
            
            # return id
            if in_chat:
                yield 'data:' + orjson.dumps({'type': 'id', 'id': self.get_record().id}).decode() + '\n\n'
            if not stream:
                json_result['record_id'] = self.get_record().id

            # return title
            if self.change_title:
                if self.chat_question.question and self.chat_question.question.strip() != '':
                    brief = rename_chat(session=_session,
                                        rename_object=RenameChat(id=self.get_record().chat_id,
                                                                 brief=self.chat_question.question.strip()[:20]))
                    if in_chat:
                        yield 'data:' + orjson.dumps({'type': 'brief', 'brief': brief}).decode() + '\n\n'
                    if not stream:
                        json_result['title'] = brief

                # select datasource if datasource is none
            if not self.ds:
                _perf_ds_start = time.time()
                ds_res = self.select_datasource(_session)

                for chunk in ds_res:
                    ChatBILogUtil.info(chunk)
                    if in_chat:
                        # 区分不同类型的chunk：RAG结果、思考过程、数据源选择结果
                        if isinstance(chunk, dict) and chunk.get('type') == 'rag_results':
                            yield 'data:' + orjson.dumps({
                                'type': 'rag_results',
                                'data': chunk.get('data')
                            }).decode() + '\n\n'
                        elif isinstance(chunk, dict) and chunk.get('type') == 'thinking_stage':
                            yield 'data:' + orjson.dumps({
                                'type': 'thinking_stage',
                                'stage': chunk.get('stage'),
                                'data': chunk.get('data')
                            }).decode() + '\n\n'
                        else:
                            yield 'data:' + orjson.dumps(
                                {'content': chunk.get('content'), 'reasoning_content': chunk.get('reasoning_content'),
                                 'type': 'datasource-result'}).decode() + '\n\n'
                if in_chat:
                    yield 'data:' + orjson.dumps({'id': self.ds.id, 'datasource_name': self.ds.name,
                                                  'engine_type': self.ds.type_name or self.ds.type,
                                                  'ds_type': self.ds.type,
                                                  'type': 'datasource'}).decode() + '\n\n'

                # 性能优化：select_datasource 内部已经设置了 db_schema，
                # 仅在 select_datasource 未设置时才重新获取（避免重复调用 get_table_schema）
                if not self.chat_question.db_schema:
                    self.chat_question.db_schema = self.out_ds_instance.get_db_schema(
                        self.ds.id, self.chat_question.question) if self.out_ds_instance else get_table_schema(
                        session=_session,
                        current_user=self.current_user,
                        ds=self.ds,
                        question=self.chat_question.question)
                
                # RAG结果已在select_datasource中保存和发送，这里不需要重复
                ChatBILogUtil.info(f"[PERF] select_datasource path completed in {time.time() - _perf_ds_start:.2f}s")
            else:
                _perf_existing_ds_start = time.time()
                self.validate_history_ds(_session)
                
                # 确保ds_type已设置（兼容旧数据）
                if self.ds and not self.chat_question.ds_type:
                    self.chat_question.ds_type = self.ds.type or 'database'
                
                # 数据源已存在的情况：需要执行RAG检索并发送结果
                oid = self.ds.oid if isinstance(self.ds, CoreDatasource) else 1
                ds_id = self.ds.id if isinstance(self.ds, CoreDatasource) else None
                rag_enabled = getattr(self.chat_question, 'rag_enabled', True)
                
                # 早期意图检测：决定是否需要RAG检索
                # 这是整个智能对话系统的核心路由决策点
                _perf_intent_start = time.time()
                early_intent = QueryRewriter._detect_intent(self.chat_question.question, ds_type=self.ds.type if self.ds else 'database')
                ChatBILogUtil.info(f"[PERF] early intent detection: {time.time() - _perf_intent_start:.3f}s, intent={early_intent}")
                self._early_intent = early_intent  # 保存供后续意图路由使用，避免重复检测
                
                # ========== follow_up意图继承（existing ds路径） ==========
                if early_intent == 'follow_up':
                    try:
                        from apps.chat.crud.chat import list_chat_records_for_dialogue
                        _chat_id = self.chat_question.chat_id if hasattr(self.chat_question, 'chat_id') else None
                        _inherited = None
                        if _chat_id:
                            _prev_recs = list_chat_records_for_dialogue(_session, _chat_id, max_turns=5)
                            for _pr in reversed(_prev_recs):
                                if _pr.get('intent') and _pr['intent'] not in ('follow_up', 'irrelevant_query', 'ambiguous_query'):
                                    _inherited = _pr['intent']
                                    break
                        if _inherited:
                            # D2 话题切换检测
                            _q_lower = self.chat_question.question.lower()
                            _topic_switch = False
                            if _inherited != 'prediction' and any(kw in _q_lower for kw in ['预测', '预估', '预计', 'forecast', 'predict']):
                                _topic_switch = True
                            if _inherited != 'comparison_analysis' and any(kw in _q_lower for kw in ['对比', '比较', '同比', '环比', 'compare', 'vs']):
                                _topic_switch = True
                            if _inherited != 'trend_analysis' and any(kw in _q_lower for kw in ['趋势', '走势', '变化', 'trend']):
                                _topic_switch = True
                            if _topic_switch:
                                ChatBILogUtil.info(f"[existing_ds][follow_up] Topic switch detected, re-detecting intent instead of inheriting '{_inherited}'")
                                import re as _re
                                _cleaned_q = _re.sub(r'(上面|上述|刚才|之前|继续|接着|进一步|那么)', '', _q_lower).strip()
                                early_intent = QueryRewriter._detect_intent(_cleaned_q, ds_type=self.ds.type if self.ds else 'database')
                                self._early_intent = early_intent
                            else:
                                ChatBILogUtil.info(f"[existing_ds][follow_up] Inherited intent: {_inherited}")
                                early_intent = _inherited
                                self._early_intent = _inherited
                        else:
                            early_intent = 'fact_query'
                            self._early_intent = 'fact_query'
                    except Exception as e:
                        ChatBILogUtil.error(f"[existing_ds][follow_up] Inheritance failed: {e}")
                        early_intent = 'fact_query'
                        self._early_intent = 'fact_query'
                
                # 区分"纯寒暄"和"需要RAG的非数据查询"
                is_trivial_chat = early_intent == 'irrelevant_query' and QueryRewriter._is_trivial_chat(self.chat_question.question)
                
                if is_trivial_chat:
                    # ========== 纯寒暄快速路径 ==========
                    rag_enabled = False
                    self.chat_question.terminologies = ''
                    self.chat_question.data_training = ''
                    self.chat_question.db_schema = ''  #  纯寒暄不需要表结构
                    ChatBILogUtil.info(f"[trivial_chat] Fast path: skipping all RAG/rewrite processing")
                    
                    # 纯寒暄也需要发送查询理解阶段（步骤1），让前端展示完整的思考链
                    try:
                        from apps.chat.thinking.thinking_integration import record_query_understanding_stage
                        record_query_understanding_stage(
                            self.thinking_process,
                            original_query=self.chat_question.question,
                            rewritten_query=self.chat_question.question,
                            intent='irrelevant_query',
                            rewrite_applied=False,
                            extracted_keywords=[],
                            dialogue_turn=1,
                            context_references=[],
                            ds_type=(self.ds.type or '').lower() if hasattr(self, 'ds') and self.ds else '',
                            ds_name=(self.ds.name or '') if hasattr(self, 'ds') and self.ds else '',
                            intent_keywords=['纯寒暄/帮助类'],
                        )
                        if in_chat:
                            qu_stage = self.thinking_process.get_stage('query_understanding')
                            if qu_stage:
                                yield 'data:' + orjson.dumps({
                                    'type': 'thinking_stage',
                                    'stage': 'query_understanding',
                                    'data': qu_stage
                                }).decode() + '\n\n'
                    except Exception as e:
                        ChatBILogUtil.error(f"Failed to record query_understanding for trivial chat: {e}")
                    
                    # 纯寒暄也需要记录对话轮次，否则多轮对话上下文丢失
                    # 例如用户先说"你好"再问"查询销售数据"，"你好"这轮不应丢失
                    try:
                        self.dialogue_tracker.track_turn(
                            question=self.chat_question.question,
                            record_id=self.record.id if hasattr(self, 'record') and self.record else None
                        )
                    except Exception as e:
                        ChatBILogUtil.error(f"Dialogue tracking failed for trivial chat: {e}")
                    
                    # 发送空RAG结果（告知前端此次不使用RAG）
                    if in_chat:
                        yield 'data:' + orjson.dumps({
                            'type': 'rag_results',
                            'data': {
                                'terminologies': [], 'sql_examples': [],
                                'custom_prompts': [], 'rag_enabled': False,
                                'custom_prompt_checked': False
                            }
                        }).decode() + '\n\n'
                    
                    # 跳转到意图路由（不执行后续的RAG检索代码）
                    _skip_rag_processing = True
                    
                else:
                    # ========== 正常RAG路径 ==========
                    _skip_rag_processing = False
                
                # PDF始终走直接回答路径（RAG+LLM文档问答）
                self._pdf_has_tables = None
                _ds_type_early = self.ds.type.lower() if self.ds and self.ds.type else ''
                if _ds_type_early == 'pdf' and not _skip_rag_processing:
                    self._pdf_has_tables = False  # PDF不走SQL路径
                    # PDF意图统一调整为 document_qa
                    if self._early_intent not in ('irrelevant_query', 'ambiguous_query'):
                        ChatBILogUtil.info(f"[PDF route] Adjusting early intent from '{self._early_intent}' to 'document_qa' (PDF always direct answer)")
                        self._early_intent = 'document_qa'
                
                if not _skip_rag_processing:
                    rag_start_time = time.time()
                    
                    # 使用统一的查询理解方法（消除与 select_datasource 路径的代码重复）
                    _perf_qu_start = time.time()
                    _ds_type_for_rewrite = self.ds.type if self.ds else 'database'
                    _qu_result2 = self._execute_query_understanding(_session, _ds_type_for_rewrite, path_label='existing_ds')
                    ChatBILogUtil.info(f"[PERF] query understanding: {time.time() - _perf_qu_start:.2f}s")
                    rewrite_result = _qu_result2['rewrite_result']
                    retrieval_question = _qu_result2['retrieval_question']
                
                    # 对话状态追踪（existing ds路径）
                    try:
                        self.dialogue_tracker.track_turn(
                            question=self.chat_question.question,
                            record_id=self.record.id if hasattr(self, 'record') and self.record else None
                        )
                        if self.dialogue_tracker.turns:
                            _dlg_ctx = self.dialogue_tracker.get_dialogue_context(max_turns=3)
                            if _dlg_ctx.get('total_turns', 0) > 0:
                                self.thinking_process.dialogue_context_injected = {
                                    'total_turns': _dlg_ctx.get('total_turns', 0),
                                    'current_intent': _dlg_ctx.get('current_intent', ''),
                                    'current_topic': _dlg_ctx.get('current_topic', ''),
                                    'active_entities': _dlg_ctx.get('active_entities', [])[:5],
                                    'recent_questions': _dlg_ctx.get('recent_questions', [])[-3:],
                                    'context_references': _dlg_ctx.get('context_references', []),
                                    'injected': True
                                }
                    except Exception as e:
                        ChatBILogUtil.error(f"Dialogue state tracking failed (existing ds): {e}")
                
                terminology_results = []
                sql_example_results = []
                custom_prompts_used = []
                doc_chunk_results = []
                self._custom_prompts_used = custom_prompts_used  # 存储为实例属性，供generate_direct_answer访问
                
                # ========== 统一三阶段 RAG 执行器（所有数据源统一使用）==========
                _use_unified_executor = (
                    rag_enabled
                    and not _skip_rag_processing
                )
                
                if _use_unified_executor:
                    try:
                        _perf_rag_pipeline_start = time.time()
                        ChatBILogUtil.info(f"[UnifiedRAG] Using UnifiedRAGExecutor for ds_type={_ds_type_early}")
                        _rag_pipeline_result = self._execute_unified_rag_pipeline(
                            _session, retrieval_question, oid, ds_id, rewrite_result
                        )
                        ChatBILogUtil.info(f"[PERF] unified RAG pipeline: {time.time() - _perf_rag_pipeline_start:.2f}s")
                        terminology_results = _rag_pipeline_result['terminology_results']
                        sql_example_results = _rag_pipeline_result['sql_example_results']
                        doc_chunk_results = _rag_pipeline_result['doc_chunk_results']
                        
                        # 组件矩阵强制执行：根据 COMPONENT_MATRIX 决定是否跳过 SQL 组件
                        # 所有数据源统一启用 SQL 组件（Excel/CSV 数据已导入 PG，SQL 路径统一）
                        _components = get_available_components(_ds_type_early or 'database')
                        _skip_sql_examples = not _components.get('sql_examples', False)
                        
                        # 移除重复的 post_expand_with_terminologies 调用
                        
                        ChatBILogUtil.info(
                            f"[UnifiedRAG] Pipeline complete: ds_type={_ds_type_early} "
                            f"intent={_rag_pipeline_result['design_intent']} "
                            f"terms={len(terminology_results)} "
                            f"sql_ex={len(sql_example_results)} "
                            f"doc_chunks={len(doc_chunk_results)} "
                            f"skip_sql={_skip_sql_examples}"
                        )
                        
                        # 统一执行器路径：计算 RAG 质量指标（与内联路径一致）
                        from apps.chat.thinking.rag_thinking import RAGQualityMetrics
                        terminology_quality = RAGQualityMetrics.calculate_retrieval_quality(
                            terminology_results, threshold=0.7
                        ) if terminology_results else {}
                        example_quality = RAGQualityMetrics.calculate_retrieval_quality(
                            sql_example_results, threshold=0.7
                        ) if sql_example_results else {}
                        rag_impact = RAGQualityMetrics.calculate_rag_impact(
                            rag_enabled, terminology_results, sql_example_results,
                            doc_chunks=doc_chunk_results,
                            table_matches=self._build_table_match_items(),
                            ds_type=_ds_type_early,
                            intent=_rag_pipeline_result.get('design_intent', 'sql') if _rag_pipeline_result else 'sql',
                        )
                        
                        # 缓存 RAG 结果供评估使用
                        self._rag_terminologies = terminology_results
                        self._rag_sql_examples = sql_example_results
                        self._rag_doc_chunks = doc_chunk_results
                        
                        # 仅在需要 SQL 的数据源且意图路由可能走 SQL 路径时初始化 SQL 消息
                        _early_route_for_init = QueryRewriter.map_to_route(getattr(self, '_early_intent', 'data_query'))
                        if not _skip_sql_examples and _early_route_for_init != 'general_chat':
                            _perf_init_msg_start = time.time()
                            self.init_messages()
                            ChatBILogUtil.info(f"[PERF] init_messages (unified executor path): {time.time() - _perf_init_msg_start:.2f}s")
                        
                        # 自定义提示词检索（仅非 general_chat 路由需要 SQL 生成提示词）
                        # term_explanation/irrelevant_query/ambiguous_query 等 general_chat 路由不需要 SQL 生成提示词
                        custom_prompt_checked = False
                        if ChatBILicenseUtil.valid() and not _skip_sql_examples and _early_route_for_init != 'general_chat':
                            _question = self.chat_question.question or ''
                            _total_sql = count_custom_prompts(_session, CustomPromptTypeEnum.GENERATE_SQL, oid, ds_id)
                            custom_prompt_content, _sql_details = find_relevant_custom_prompts(
                                _session, CustomPromptTypeEnum.GENERATE_SQL, oid, _question, ds_id)
                            self.chat_question.custom_prompt = custom_prompt_content
                            custom_prompt_checked = True
                            _sql_matched_count = len([d for d in _sql_details if d.get('reason') != 'not_matched'])
                            _is_en_cp_sql2 = (self.chat_question.lang or '').lower().startswith('en')
                            custom_prompts_used.append({
                                'type': 'SQL Generation' if _is_en_cp_sql2 else 'SQL生成',
                                'content': custom_prompt_content[:200] + '...' if custom_prompt_content and len(custom_prompt_content) > 200 else (custom_prompt_content or ''),
                                'used': _sql_matched_count > 0,
                                'empty': _total_sql == 0,
                                'count': _sql_matched_count,
                                'total': _total_sql,
                                'matched': _sql_details
                            })
                        
                    except Exception as e:
                        ChatBILogUtil.error(f"[UnifiedRAG] Pipeline failed for ds_type={_ds_type_early}, falling back to empty RAG: {e}")
                        ChatBILogUtil.exception()
                        # 移除冗余的内联 RAG 降级路径（原 ~200 行重复代码）
                        _use_unified_executor = True  # 标记为已处理，跳过内联路径
                        self.chat_question.terminologies = ''
                        self.chat_question.data_training = ''
                        _skip_sql_examples = True
                        # 初始化空的质量指标
                        from apps.chat.thinking.rag_thinking import RAGQualityMetrics
                        terminology_quality = {}
                        example_quality = {}
                        rag_impact = RAGQualityMetrics.calculate_rag_impact(
                            rag_enabled, [], [],
                            doc_chunks=[],
                            table_matches=self._build_table_match_items(),
                            ds_type=_ds_type_early,
                            intent='sql',
                        )
                        self._rag_terminologies = []
                        self._rag_sql_examples = []
                        self._rag_doc_chunks = []
                        custom_prompt_checked = False
                
                if not _use_unified_executor and not rag_enabled:
                    # 仅在 RAG 禁用时清空（unified executor 成功时不清空，已在 pipeline 中设置）
                    self.chat_question.terminologies = ''
                    self.chat_question.data_training = ''
                    _skip_sql_examples = False  # RAG禁用时不跳过（保持默认行为）
                
                if not _skip_rag_processing:
                    # 上下文压缩：使用重排序感知的高级压缩策略
                    if not _use_unified_executor:
                        self._apply_context_compression(
                            rag_enabled=rag_enabled,
                            terminology_results=terminology_results,
                            sql_example_results=sql_example_results,
                            max_total_tokens=800,
                            tag="[existing_ds]",
                        )
                    
                    # 获取自定义提示词（智能匹配）
                    if not _use_unified_executor:
                        custom_prompt_checked = False
                        _question = self.chat_question.question or ''
                        _early_route_for_cp = QueryRewriter.map_to_route(getattr(self, '_early_intent', 'data_query'))
                        if ChatBILicenseUtil.valid() and not _skip_sql_examples and _early_route_for_cp != 'general_chat':
                            _total_sql = count_custom_prompts(_session, CustomPromptTypeEnum.GENERATE_SQL, oid, ds_id)
                            custom_prompt_content, _sql_details = find_relevant_custom_prompts(
                                _session, CustomPromptTypeEnum.GENERATE_SQL, oid, _question, ds_id)
                            self.chat_question.custom_prompt = custom_prompt_content
                            custom_prompt_checked = True
                            
                            _sql_matched_count = len([d for d in _sql_details if d.get('reason') != 'not_matched'])
                            _is_en_cp_sql3 = (self.chat_question.lang or '').lower().startswith('en')
                            custom_prompts_used.append({
                                'type': 'SQL Generation' if _is_en_cp_sql3 else 'SQL生成',
                                'content': custom_prompt_content[:200] + '...' if custom_prompt_content and len(custom_prompt_content) > 200 else (custom_prompt_content or ''),
                                'used': _sql_matched_count > 0,
                                'empty': _total_sql == 0,
                                'count': _sql_matched_count,
                                'total': _total_sql,
                                'matched': _sql_details
                            })
                            
                            # 场景感知提示词：SQL路径只加载SQL生成提示词
                        elif _skip_sql_examples:
                            ChatBILogUtil.info(f"[RAG routing] Skipping SQL custom prompt: ds_type={_ds_type_for_routing}, intent='{self._early_intent}'")
                    
                    # 仅SQL路径时初始化SQL消息
                    if not _use_unified_executor:
                        _early_route_for_init2 = QueryRewriter.map_to_route(getattr(self, '_early_intent', 'data_query'))
                        if not _skip_sql_examples and _early_route_for_init2 != 'general_chat':
                            # 初始化SQL消息
                            self.init_messages()
                
                    # 缓存RAG结果供评估使用
                    self._rag_terminologies = terminology_results
                    self._rag_sql_examples = sql_example_results
                    self._rag_doc_chunks = doc_chunk_results
                    
                    # 计算RAG质量指标（新增 - 专业评估）
                    from apps.chat.thinking.rag_thinking import RAGQualityMetrics
                    
                    terminology_quality = RAGQualityMetrics.calculate_retrieval_quality(
                        terminology_results, threshold=0.7
                    ) if terminology_results else {}
                    
                    example_quality = RAGQualityMetrics.calculate_retrieval_quality(
                        sql_example_results, threshold=0.7
                    ) if sql_example_results else {}
                    
                    # rag_impact计算 - 正确传递各维度知识列表（包含文档片段）
                    # calculate_rag_impact签名: (rag_enabled, terminologies, sql_examples, analysis_examples, predict_examples, doc_chunks, ds_type, intent)
                    _ds_type_for_impact3 = (self.ds.type or 'database').lower() if self.ds else 'database'
                    _intent_for_impact3 = 'sql'
                    if hasattr(self, '_unified_rag_result') and self._unified_rag_result:
                        _ret3 = self._unified_rag_result.get('retrieve')
                        if _ret3:
                            _intent_for_impact3 = _ret3.intent or 'sql'
                    rag_impact = RAGQualityMetrics.calculate_rag_impact(
                        rag_enabled,
                        terminology_results,
                        sql_example_results,
                        doc_chunks=doc_chunk_results,
                        table_matches=self._build_table_match_items(),
                        ds_type=_ds_type_for_impact3,
                        intent=_intent_for_impact3,
                    )
                    
                    # 发送RAG检索结果到前端
                    if in_chat:
                        rag_results_data = {
                            'terminologies': terminology_results,
                            'sql_examples': sql_example_results,
                            'custom_prompts': custom_prompts_used,
                            'rag_enabled': rag_enabled,
                            'custom_prompt_checked': custom_prompt_checked,
                            'terminology_quality': terminology_quality,
                            'example_quality': example_quality,
                            'rag_impact': rag_impact,
                            'document_chunks': [
                                {
                                    'text': dc.get('text', '')[:300],
                                    'source_type': dc.get('source_type', 'file'),
                                    'source_name': dc.get('source_name', dc.get('filename', '')),
                                    'source_file': dc.get('filename', dc.get('source_file', '')),
                                    'section_title': dc.get('section_title', ''),
                                    'page_number': dc.get('page_number'),
                                    'similarity': dc.get('similarity', 0),
                                    'chunk_type': dc.get('chunk_type', 'text'),
                                }
                                for dc in doc_chunk_results[:5]
                            ] if doc_chunk_results else [],
                        }
                        
                        # PDF 数据源：附加来源摘要（页码、章节、相似度统计）
                        if _ds_type_early == 'pdf' and doc_chunk_results:
                            rag_results_data['pdf_source_summary'] = get_pdf_source_summary(doc_chunk_results)
                        
                        # 统一执行器元数据（组件矩阵、设计意图）
                        if hasattr(self, '_unified_rag_result') and self._unified_rag_result:
                            _ret = self._unified_rag_result.get('retrieve')
                            _aug = self._unified_rag_result.get('augment')
                            if _ret:
                                rag_results_data['design_intent'] = _ret.intent
                                rag_results_data['fine_intent'] = _ret.fine_intent
                            if _aug:
                                rag_results_data['components_used'] = _aug.components_used
                                rag_results_data['visualization_detected'] = _aug.visualization_detected
                        
                        # RAG检索结果兜底策略
                        _is_en_rag_fb = (self.chat_question.lang or '').lower().startswith('en')
                        if rag_enabled and not terminology_results and not sql_example_results and not doc_chunk_results:
                            rag_results_data['fallback_message'] = (
                                'No relevant information found in knowledge base. Consider adding terminologies or SQL examples to improve answer quality.'
                                if _is_en_rag_fb else
                                '知识库中未找到相关信息，建议补充术语或SQL示例以提升回答质量'
                            )
                        elif rag_impact.get('confidence') == 'very_low' or rag_impact.get('quality_score', 0) < 0.3:
                            rag_results_data['quality_warning'] = (
                                'Retrieval result quality is low. Answer accuracy may be affected.'
                                if _is_en_rag_fb else
                                '检索结果质量较低，回答准确性可能受影响'
                            )
                        
                        yield 'data:' + orjson.dumps({
                            'type': 'rag_results',
                            'data': rag_results_data
                        }).decode() + '\n\n'
                        
                        try:
                            save_rag_results(
                                session=_session,
                                record_id=self.get_record().id,
                                rag_enabled=rag_enabled,
                                rag_results=orjson.dumps(rag_results_data).decode()
                            )
                        except Exception as e:
                            ChatBILogUtil.error(f"Failed to save RAG results for existing ds: {e}")
                            ChatBILogUtil.exception()
                    
                    # 记录Schema检索阶段到思考过程（existing ds路径）
                    try:
                        _rag_time = time.time() - rag_start_time if 'rag_start_time' in locals() else 0
                        _ds_type_for_schema2 = (self.ds.type or 'database').lower() if self.ds else 'database'
                        _intent_for_schema2 = 'sql'
                        if hasattr(self, '_unified_rag_result') and self._unified_rag_result:
                            _ret2 = self._unified_rag_result.get('retrieve')
                            if _ret2:
                                _intent_for_schema2 = _ret2.intent or 'sql'
                        record_rag_retrieval(
                            self.thinking_process,
                            question=self.chat_question.question,
                            table_candidates=getattr(self, '_table_match_details', {}).get('table_candidates', []),
                            selected_tables=getattr(self, '_table_match_details', {}).get('selected_tables', []),
                            similarities=getattr(self, '_table_match_details', {}).get('similarities', []),
                            terminologies=terminology_results,
                            sql_examples=sql_example_results,
                            custom_prompts=custom_prompts_used,
                            retrieval_time=_rag_time,
                            rag_enabled=rag_enabled,
                            doc_chunks=doc_chunk_results,
                            ds_type=_ds_type_for_schema2,
                            intent=_intent_for_schema2,
                        )
                        # 精简后的6阶段流程：查询理解 → 知识检索 → 提示词构建 → SQL生成 → SQL执行 → 输出决策
                        
                        # 1. 查询理解阶段（合并了查询重写+对话上下文）
                        qu_stage_data = self.thinking_process.get_stage('query_understanding')
                        if qu_stage_data:
                            yield 'data:' + orjson.dumps({
                                'type': 'thinking_stage',
                                'stage': 'query_understanding',
                                'data': qu_stage_data
                            }).decode() + '\n\n'
                        
                        # 2. RAG知识检索阶段
                        rag_stage_data = self.thinking_process.get_stage('rag_retrieval')
                        if rag_stage_data:
                            yield 'data:' + orjson.dumps({
                                'type': 'thinking_stage',
                                'stage': 'rag_retrieval',
                                'data': rag_stage_data
                            }).decode() + '\n\n'
                        
                        # 2.5a 子问题分解阶段（步骤9）
                        _qd_stage = self.thinking_process.get_stage('query_decomposition')
                        if _qd_stage:
                            yield 'data:' + orjson.dumps({
                                'type': 'thinking_stage',
                                'stage': 'query_decomposition',
                                'data': _qd_stage
                            }).decode() + '\n\n'
                        
                        # 2.5b 检索结果校验阶段（existing ds路径 — 已做质量过滤，记录结果）
                        try:
                            _rv_data = {
                                'first_retrieval_count': len(terminology_results) + len(sql_example_results),
                                'second_retrieval_triggered': False,
                                'second_retrieval_reason': None,
                                'final_count': len(terminology_results) + len(sql_example_results),
                            }
                            self.thinking_process.record_stage(
                                name='retrieval_validation', status='completed', duration=0, extra_data=_rv_data
                            )
                            yield 'data:' + orjson.dumps({
                                'type': 'thinking_stage',
                                'stage': 'retrieval_validation',
                                'data': self.thinking_process.get_stage('retrieval_validation')
                            }).decode() + '\n\n'
                        except Exception:
                            pass
                        
                        # 2.7 上下文压缩阶段
                        cc_stage_data2 = self.thinking_process.get_stage('context_compression')
                        if cc_stage_data2:
                            yield 'data:' + orjson.dumps({
                                'type': 'thinking_stage',
                                'stage': 'context_compression',
                                'data': cc_stage_data2
                            }).decode() + '\n\n'
                        
                        # 注：提示词构建、SQL生成、SQL执行、输出决策阶段在后续流程中发送
                        
                    except Exception as e:
                        ChatBILogUtil.error(f"Failed to record schema_retrieval for existing ds: {e}")
                
                ChatBILogUtil.info(f"[PERF] existing_ds path (RAG+schema) completed in {time.time() - _perf_existing_ds_start:.2f}s")

            _perf_intent_route_start = time.time()
            ChatBILogUtil.info(f"[PERF] pre-intent-routing total elapsed: {time.time() - _task_start_time:.2f}s")
            # 确保oid/ds_id/custom_prompts_used在意图路由阶段可用
            try:
                oid
            except NameError:
                oid = self.ds.oid if self.ds and isinstance(self.ds, CoreDatasource) else (self.current_user.oid if self.current_user.oid is not None else 1)
            try:
                ds_id
            except NameError:
                ds_id = self.ds.id if self.ds and isinstance(self.ds, CoreDatasource) else None
            try:
                custom_prompts_used
            except NameError:
                custom_prompts_used = []
            
            # 使用早期检测的意图（已在existing ds路径中完成follow_up继承）
            # 不再重复执行follow_up意图继承查询，避免多余的数据库访问
            if hasattr(self, '_early_intent'):
                detected_intent = self._early_intent
            else:
                detected_intent = QueryRewriter._detect_intent(self.chat_question.question, ds_type=self.ds.type if self.ds else 'database')
            ChatBILogUtil.info(f"Intent routing: {detected_intent} for question: {self.chat_question.question}")
            
            # 判断是否需要走直接回答路径（不生成SQL）
            # 使用 map_to_route 将9种细粒度意图映射到4种处理路由
            detected_route = QueryRewriter.map_to_route(detected_intent)
            use_direct_answer = False
            if detected_route == 'general_chat':
                use_direct_answer = True
            ChatBILogUtil.info(f"Intent routing decision: intent={detected_intent}, route={detected_route}, use_direct_answer={use_direct_answer}")
            
            # PDF数据源路由策略（PDF始终走直接回答路径）
            # PDF是非结构化文档，不支持SQL/图表/分析/预测
            _ds_type = self.ds.type.lower() if self.ds and self.ds.type else ''
            if _ds_type == 'pdf':
                use_direct_answer = True
                # PDF 数据源统一使用 document_qa 意图（与 rag_results.design_intent 一致）
                if detected_intent not in ('irrelevant_query', 'ambiguous_query'):
                    detected_intent = 'document_qa'
                ChatBILogUtil.info(f"[PDF route] PDF always uses direct answer path (RAG+LLM document QA)")
            
            # save_intent 必须在 PDF 意图覆盖之后调用
            try:
                save_intent(_session, self.get_record().id, detected_intent)
            except Exception as e:
                ChatBILogUtil.error(f"Failed to save intent: {e}")
            
            # 同步更新 thinking_process 中的意图
            try:
                _qu_stage = self.thinking_process.get_stage('query_understanding')
                if _qu_stage and isinstance(_qu_stage, dict):
                    _recorded_intent = _qu_stage.get('intent') or _qu_stage.get('extra_data', {}).get('intent')
                    if _recorded_intent and _recorded_intent != detected_intent:
                        if 'extra_data' in _qu_stage and isinstance(_qu_stage['extra_data'], dict):
                            _qu_stage['extra_data']['intent'] = detected_intent
                            _qu_stage['extra_data']['original_intent'] = _recorded_intent
                        elif 'intent' in _qu_stage:
                            _qu_stage['original_intent'] = _recorded_intent
                            _qu_stage['intent'] = detected_intent
            except Exception:
                pass
            
            if use_direct_answer:
                # ========== 直接回答路径：不生成SQL，直接用LLM生成文本回答 ==========
                ChatBILogUtil.info(f"Using direct answer path for intent: {detected_intent}")
                
                # 直接回答路径不需要SQL示例
                if self.chat_question.data_training:
                    # 保留文档知识库检索结果（<document-knowledge>），仅清除SQL示例
                    _doc_marker = '<document-knowledge>'
                    _doc_idx = (self.chat_question.data_training or '').find(_doc_marker)
                    if _doc_idx >= 0:
                        # 有文档知识库结果，只保留文档部分
                        self.chat_question.data_training = self.chat_question.data_training[_doc_idx:]
                        ChatBILogUtil.info("[direct_answer] Cleared SQL examples from data_training, kept document chunks")
                    else:
                        # 纯SQL示例，全部清除
                        self.chat_question.data_training = ''
                        ChatBILogUtil.info("[direct_answer] Cleared SQL examples from data_training")
                
                # 语义意图直接使用检测到的意图
                user_semantic_intent = detected_intent
                
                if in_chat:
                    yield 'data:' + orjson.dumps({
                        'type': 'intent',
                        'intent': detected_intent
                    }).decode() + '\n\n'
                
                # 为直接回答路径检索自定义提示词
                try:
                    if ChatBILicenseUtil.valid():
                        _prompt_type = None  # 默认不检索
                        _prompt_type_label = None
                        _is_en_ptl = (self.chat_question.lang or '').lower().startswith('en')
                        if user_semantic_intent in ('analysis', 'statistical_analysis'):
                            _prompt_type = CustomPromptTypeEnum.ANALYSIS
                            _prompt_type_label = 'Data Analysis' if _is_en_ptl else '数据分析'
                        elif user_semantic_intent in ('prediction',):
                            _prompt_type = CustomPromptTypeEnum.PREDICT_DATA
                            _prompt_type_label = 'Data Prediction' if _is_en_ptl else '数据预测'
                        elif user_semantic_intent in ('fact_query', 'comparison_analysis', 'trend_analysis'):
                            # 这些意图到达直接回答路径的原因：PDF无表格 或 general_chat兜底
                            # 此时LLM是在分析/回答问题，应使用分析提示词而非SQL提示词
                            _prompt_type = CustomPromptTypeEnum.ANALYSIS
                            _prompt_type_label = 'Data Analysis' if _is_en_ptl else '数据分析'
                        
                        if _prompt_type is not None:
                            _question = self.chat_question.question or ''
                            _total_direct = count_custom_prompts(_session, _prompt_type, oid, ds_id)
                            _direct_custom_prompt, _direct_details = find_relevant_custom_prompts(
                                _session, _prompt_type, oid, _question, ds_id
                            )
                            _direct_matched_count = len([d for d in _direct_details if d.get('reason') != 'not_matched'])
                            if _direct_matched_count > 0:
                                self.chat_question.custom_prompt = _direct_custom_prompt
                            custom_prompts_used.append({
                                'type': _prompt_type_label,
                                'content': _direct_custom_prompt[:200] + '...' if _direct_custom_prompt and len(_direct_custom_prompt) > 200 else (_direct_custom_prompt or ''),
                                'used': _direct_matched_count > 0,
                                'empty': _total_direct == 0,
                                'count': _direct_matched_count,
                                'total': _total_direct,
                                'matched': _direct_details
                            })
                        else:
                            ChatBILogUtil.info(f"[direct_answer] Skipping custom prompt retrieval for intent: {user_semantic_intent}")
                except Exception as e:
                    ChatBILogUtil.error(f"Failed to retrieve custom prompts for direct answer: {e}")
                
                _perf_direct_answer_start = time.time()
                direct_res = self.generate_direct_answer(_session, user_semantic_intent)
                full_direct_text = ''
                for chunk in direct_res:
                    # 处理思考过程阶段数据（与SQL路径一致）
                    if chunk.get('type') == 'thinking_stage':
                        if in_chat:
                            yield 'data:' + orjson.dumps({
                                'type': 'thinking_stage',
                                'stage': chunk.get('stage'),
                                'data': chunk.get('data')
                            }).decode() + '\n\n'
                        continue
                    if chunk.get('type') == 'rag_results':
                        if in_chat:
                            yield 'data:' + orjson.dumps(chunk).decode() + '\n\n'
                        continue
                    # 处理分层推荐问题（generate_direct_answer 的后置推荐）
                    if chunk.get('type') == 'layered_recommendations':
                        if in_chat:
                            yield 'data:' + orjson.dumps({
                                'type': 'layered_recommendations',
                                'data': chunk.get('data')
                            }).decode() + '\n\n'
                        continue
                    content = chunk.get('content')
                    if content:
                        full_direct_text += content
                    if in_chat:
                        yield 'data:' + orjson.dumps({
                            'content': chunk.get('content'),
                            'reasoning_content': chunk.get('reasoning_content'),
                            'type': 'direct-answer'
                        }).decode() + '\n\n'
                    else:
                        if stream:
                            content = chunk.get('content')
                            if content:
                                yield content
                
                if in_chat:
                    # 保存思考过程到数据库（直接回答路径）
                    try:
                        thinking_data = self.thinking_process.to_dict()
                        if self.dialogue_tracker:
                            thinking_data['dialogue_state'] = self.dialogue_tracker.get_state_summary()
                        
                        # RAG评估：直接回答路径
                        try:
                            from apps.chat.thinking.rag_evaluator import RAGEvaluator
                            _eval_retrieval_items = []
                            try:
                                for t in (self._rag_terminologies or []):
                                    _eval_retrieval_items.append({
                                        'similarity': t.get('similarity', 0),
                                        'source_type': 'terminology'
                                    })
                                for e_item in (self._rag_sql_examples or []):
                                    _eval_retrieval_items.append({
                                        'similarity': e_item.get('similarity', 0),
                                        'source_type': 'sql_example'
                                    })
                                # PDF数据源的主要检索源是文档片段(doc_chunks)，
                                for dc in (getattr(self, '_rag_doc_chunks', None) or []):
                                    _eval_retrieval_items.append({
                                        'similarity': dc.get('similarity', 0),
                                        'source_type': 'doc_chunk'
                                    })
                            except Exception:
                                pass
                            
                            if _eval_retrieval_items:
                                retrieval_eval = RAGEvaluator.evaluate_retrieval(_eval_retrieval_items)
                                thinking_data['rag_evaluation'] = {
                                    'retrieval': {
                                        'precision_at_k': retrieval_eval.precision_at_k,
                                        'mrr': retrieval_eval.mrr,
                                        'ndcg': retrieval_eval.ndcg,
                                        'avg_similarity': retrieval_eval.avg_similarity,
                                        'high_quality_ratio': retrieval_eval.high_quality_ratio,
                                        'total_retrieved': retrieval_eval.total_retrieved,
                                        'relevant_count': retrieval_eval.relevant_count
                                    }
                                }
                        except Exception as eval_e:
                            ChatBILogUtil.error(f"RAG evaluation failed for direct answer: {eval_e}")
                        
                        if thinking_data and thinking_data.get('stages'):
                            import json as _json
                            thinking_json = _json.dumps(thinking_data, ensure_ascii=False)
                            save_thinking_process(
                                session=_session,
                                record_id=self.record.id,
                                thinking_process=thinking_json
                            )
                            # 标记已保存，防止 finally 块重复保存
                            self._thinking_process_saved = True
                    except Exception as e:
                        ChatBILogUtil.error(f"[run_task] Failed to save thinking process for direct answer: {e}")
                    
                    yield 'data:' + orjson.dumps({'type': 'finish'}).decode() + '\n\n'
                if not stream:
                    json_result['direct_answer'] = full_direct_text
                    yield json_result
                ChatBILogUtil.info(f"[PERF] direct_answer path completed in {time.time() - _perf_direct_answer_start:.2f}s, total elapsed: {time.time() - _task_start_time:.2f}s")
                return
            
            # ========== 数据查询路径：生成SQL → 执行 → 图表 ==========
            try:
                _rag_term_count = len(getattr(self, '_rag_terminologies', []) or [])
                _rag_example_count = len(getattr(self, '_rag_sql_examples', []) or [])
                _has_schema = bool(self.chat_question.db_schema and len(self.chat_question.db_schema.strip()) > 10)
                _has_any_knowledge = _rag_term_count > 0 or _rag_example_count > 0 or _has_schema
                
                if not _has_any_knowledge and detected_route in ('data_query', 'analysis', 'prediction'):
                    ChatBILogUtil.info(f"[validity_check] No RAG knowledge and no schema for SQL-path intent={detected_intent}, switching to honest response")
                    _is_en_nd = (self.chat_question.lang or '').lower().startswith('en')
                    if _is_en_nd:
                        _no_data_msg = (
                            "Sorry, no relevant data tables or field information were found in the current datasource for your question.\n\n"
                            "💡 Suggestions:\n"
                            "1. Check if the datasource is properly configured and contains relevant data\n"
                            "2. Try asking with more specific business terms\n"
                            "3. Add relevant business terms in the Terminology Library to improve retrieval"
                        )
                    else:
                        _no_data_msg = "抱歉，当前数据源中暂未找到与您问题相关的数据表或字段信息。\n\n💡 建议：\n1. 检查数据源是否已正确配置并包含相关数据\n2. 尝试使用更具体的业务术语提问\n3. 在「术语库」中添加相关业务术语以提升检索效果"
                    
                    try:
                        save_intent(_session, self.get_record().id, 'ambiguous_query')
                        save_analysis_answer(
                            session=_session, record_id=self.record.id,
                            answer=orjson.dumps({'content': _no_data_msg, 'reasoning_content': ''}).decode()
                        )
                    except Exception:
                        pass
                    
                    if in_chat:
                        yield 'data:' + orjson.dumps({'type': 'intent', 'intent': 'ambiguous_query'}).decode() + '\n\n'
                        yield 'data:' + orjson.dumps({'content': _no_data_msg, 'reasoning_content': '', 'type': 'direct-answer'}).decode() + '\n\n'
                        yield 'data:' + orjson.dumps({'type': 'finish'}).decode() + '\n\n'
                    else:
                        if stream:
                            yield _no_data_msg
                        else:
                            json_result['direct_answer'] = _no_data_msg
                            yield json_result
                    return
            except Exception as e:
                ChatBILogUtil.error(f"[validity_check] Failed: {e}")
            
            # ========== 步骤10b：数据源能力验证 ==========
            try:
                _capability_mismatch = False
                _capability_reason = ''
                
                if detected_intent == 'prediction':
                    # 预测需要时间字段+数值字段+足够数据量
                    if not self._check_prediction_capability(_session):
                        _capability_mismatch = True
                        _is_en_cap2 = (self.chat_question.lang or '').lower().startswith('en')
                        _capability_reason = (
                            'The current datasource does not meet prediction requirements (needs time fields, numeric fields, and ≥10 rows of data)'
                            if _is_en_cap2 else
                            '当前数据源不具备预测条件（需要同时有时间字段、数值字段且数据量≥10行）'
                        )
                
                elif detected_intent == 'trend_analysis':
                    # 趋势分析需要时间字段
                    _has_date_for_cap = False
                    try:
                        from apps.datasource.models.datasource import CoreTable as _CapT, CoreField as _CapF
                        _cap_ds = self.ds.id if isinstance(self.ds, CoreDatasource) else None
                        if _cap_ds:
                            # 使用 JOIN 替代 N+1 查询（与 _check_prediction_capability 对齐）
                            _cap_fields = _session.query(_CapF.field_type).join(
                                _CapT, _CapF.table_id == _CapT.id
                            ).filter(
                                _CapT.ds_id == _cap_ds,
                                _CapT.checked == True,
                                _CapF.checked == True,
                            ).all()
                            for (_ft,) in _cap_fields:
                                if _ft and any(t in _ft.lower() for t in ['date', 'time', 'timestamp']):
                                    _has_date_for_cap = True
                                    break
                    except Exception:
                        _has_date_for_cap = True  # 检查失败时保守处理，不阻断
                    if not _has_date_for_cap:
                        _capability_mismatch = True
                        _is_en_cap3 = (self.chat_question.lang or '').lower().startswith('en')
                        _capability_reason = (
                            'The current datasource has no time/date fields and cannot perform trend analysis'
                            if _is_en_cap3 else
                            '当前数据源没有时间/日期字段，无法进行趋势分析'
                        )
                
                if _capability_mismatch:
                    ChatBILogUtil.info(f"[capability_check] Intent '{detected_intent}' not supported: {_capability_reason}")
                    _is_en_cap4 = (self.chat_question.lang or '').lower().startswith('en')
                    if _is_en_cap4:
                        _cap_msg = f"Sorry, {_capability_reason}.\n\n💡 You can try asking questions that match the current datasource fields, such as data queries or statistical analysis."
                    else:
                        _cap_msg = f"抱歉，{_capability_reason}。\n\n💡 您可以尝试提出与当前数据源字段匹配的问题，例如数据查询、统计分析等。"
                    
                    try:
                        save_intent(_session, self.get_record().id, 'ambiguous_query')
                        save_analysis_answer(
                            session=_session, record_id=self.record.id,
                            answer=orjson.dumps({'content': _cap_msg, 'reasoning_content': ''}).decode()
                        )
                    except Exception:
                        pass
                    
                    if in_chat:
                        yield 'data:' + orjson.dumps({'type': 'intent', 'intent': 'ambiguous_query'}).decode() + '\n\n'
                        yield 'data:' + orjson.dumps({'content': _cap_msg, 'reasoning_content': '', 'type': 'direct-answer'}).decode() + '\n\n'
                        yield 'data:' + orjson.dumps({'type': 'finish'}).decode() + '\n\n'
                    else:
                        if stream:
                            yield _cap_msg
                        else:
                            json_result['direct_answer'] = _cap_msg
                            yield json_result
                    return
            except Exception as e:
                ChatBILogUtil.error(f"[capability_check] Failed: {e}")
            
            if in_chat:
                yield 'data:' + orjson.dumps({
                    'type': 'intent',
                    'intent': detected_intent
                }).decode() + '\n\n'

            # check connection
            connected = check_connection(ds=self.ds, trans=None)
            if not connected:
                raise ChatBIDBConnectionError('Connect DB failed')

            # 预测意图问题改写：将"预测未来X"改写为"查询历史数据"
            _original_question_for_predict = None
            if detected_intent == 'prediction':
                _original_question_for_predict = self.chat_question.question
                # 从原始问题中提取要预测的指标（如"销售额"、"订单量"等）
                import re as _pred_re
                _pred_question = self.chat_question.question
                # 移除预测相关的修饰词，保留核心指标
                _is_en_pred = (self.chat_question.lang or '').lower().startswith('en')
                if _is_en_pred:
                    # English: remove prediction modifiers
                    _pred_question = _pred_re.sub(
                        r'(?i)(predict|forecast|estimate|project|future|next\s+(month|year|quarter|week|half\s*year))\s*\d*\s*(days?|weeks?|months?|years?|quarters?)?\s*',
                        '', _pred_question
                    ).strip()
                    _pred_question = _pred_re.sub(r'^(please|can you|help me|the)\s*', '', _pred_question).strip()
                else:
                    # Chinese: remove prediction modifiers
                    _pred_question = _pred_re.sub(
                        r'(预测|预估|预计|未来|下个月|明年|下季度|下一年|下周|下半年|接下来|今后)\s*\d*\s*(天|周|月|年|个月|季度)?的?',
                        '', _pred_question
                    ).strip()
                # 清理残留的无意义词（如"一下"、"看看"等）
                _pred_question = _pred_re.sub(r'^(一下|看看|帮我|请|吧|呢|吗|的)$', '', _pred_question).strip()
                # 清理残留的纯标点或空白
                _pred_question = _pred_re.sub(r'^[\s\W]+$', '', _pred_question).strip()
                if _pred_question and len(_pred_question) >= 2:
                    # 改写为查询历史数据的问题
                    if _is_en_pred:
                        self.chat_question.question = f'Query recent {_pred_question} data, sorted by time'
                    else:
                        self.chat_question.question = f'查询最近的{_pred_question}数据，按时间排序'
                    ChatBILogUtil.info(f"[prediction] Question rewritten for SQL: '{_original_question_for_predict}' -> '{self.chat_question.question}'")
                else:
                    # 如果提取不到有意义的指标，查询所有数值数据
                    if _is_en_pred:
                        self.chat_question.question = 'Query recent data, sorted by time'
                    else:
                        self.chat_question.question = '查询最近的数据，按时间排序'
                    ChatBILogUtil.info(f"[prediction] Fallback question for SQL: '{self.chat_question.question}'")

            # 预匹配分析/预测提示词（不注入，仅为 Step 3 展示匹配结果）
            try:
                _pre_match_question = _original_question_for_predict or self.chat_question.question or ''
                _pre_match_route = detected_route  # 使用路由而非原始意图判断
                _is_en_pm = (self.chat_question.lang or '').lower().startswith('en')
                ChatBILogUtil.info(f"[run_task] Pre-match check: detected_intent={detected_intent}, detected_route={_pre_match_route}, question='{_pre_match_question[:50]}'")
                if _pre_match_route in ('data_query', 'analysis'):
                    # data_query 和 analysis 路由都会触发内联分析，预匹配分析提示词
                    _total_analysis = count_custom_prompts(_session, CustomPromptTypeEnum.ANALYSIS, oid, ds_id)
                    _, _analysis_details = find_relevant_custom_prompts(
                        _session, CustomPromptTypeEnum.ANALYSIS, oid, _pre_match_question, ds_id)
                    _analysis_matched = len([d for d in _analysis_details if d.get('reason') != 'not_matched'])
                    custom_prompts_used.append({
                        'type': 'Data Analysis' if _is_en_pm else '数据分析',
                        'content': '',
                        'used': _analysis_matched > 0,
                        'empty': _total_analysis == 0,
                        'count': _analysis_matched,
                        'total': _total_analysis,
                        'matched': _analysis_details
                    })
                if _pre_match_route == 'prediction':
                    # prediction 路由触发内联预测，预匹配预测提示词
                    _total_predict = count_custom_prompts(_session, CustomPromptTypeEnum.PREDICT_DATA, oid, ds_id)
                    _, _predict_details = find_relevant_custom_prompts(
                        _session, CustomPromptTypeEnum.PREDICT_DATA, oid, _pre_match_question, ds_id)
                    _predict_matched = len([d for d in _predict_details if d.get('reason') != 'not_matched'])
                    custom_prompts_used.append({
                        'type': 'Data Prediction' if _is_en_pm else '数据预测',
                        'content': '',
                        'used': _predict_matched > 0,
                        'empty': _total_predict == 0,
                        'count': _predict_matched,
                        'total': _total_predict,
                        'matched': _predict_details
                    })
            except Exception as e:
                ChatBILogUtil.error(f"[run_task] Pre-match analysis/predict prompts failed: {e}")

            # 保障：SQL路径必须完成完整RAG流程（init_messages → prompt_construction → generate_sql）
            _perf_sql_gen_start = time.time()
            ChatBILogUtil.info(f"[PERF] entering SQL generation, total elapsed: {time.time() - _task_start_time:.2f}s")
            if not self.sql_message:
                ChatBILogUtil.info("[safety_guard] init_messages() was skipped but SQL path reached, calling init_messages() now")
                self.init_messages()

            # 记录提示词构建阶段（SQL路径）— 通过 PromptBuilder 记录
            # 此处 sql_prompt_builder 和 _sql_prompt_metadata 一定存在（init_messages 已保证）
            try:
                if hasattr(self, 'sql_prompt_builder'):
                    self.sql_prompt_builder.set_custom_prompts(
                        self.chat_question.custom_prompt,
                        custom_prompts_used
                    )
                    _user_prompt = self.chat_question.sql_user_question(
                        current_time=__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                    if hasattr(self, '_sql_prompt_metadata'):
                        self._sql_prompt_metadata.user_prompt_preview = _user_prompt
                        self._sql_prompt_metadata.user_prompt_length = len(_user_prompt)
                        _sys_total = sum(
                            len(m.content) for m in self.sql_message
                            if isinstance(m, SystemMessage))
                        self._sql_prompt_metadata.system_prompt_length = _sys_total
                        self._sql_prompt_metadata.message_count = len(self.sql_message) + 1
                        self._sql_prompt_metadata.total_prompt_length = _sys_total + len(_user_prompt)
                        self._sql_prompt_metadata.custom_prompts = custom_prompts_used or []
                        for comp in self._sql_prompt_metadata.components:
                            if comp.name == 'custom_prompt':
                                comp.injected = bool(self.chat_question.custom_prompt)
                                comp.char_length = len(self.chat_question.custom_prompt or '')
                                break
                    self.sql_prompt_builder.record_to_thinking(
                        self.thinking_process, self._sql_prompt_metadata)
                
                # 发送上下文压缩阶段数据（如果有）— 压缩在提示词构建之前执行
                _cc_stage = self.thinking_process.get_stage('context_compression')
                if _cc_stage and in_chat:
                    yield 'data:' + orjson.dumps({
                        'type': 'thinking_stage',
                        'stage': 'context_compression',
                        'data': _cc_stage
                    }).decode() + '\n\n'
                
                _pc_stage = self.thinking_process.get_stage('prompt_construction')
                if _pc_stage and in_chat:
                    yield 'data:' + orjson.dumps({
                        'type': 'thinking_stage',
                        'stage': 'prompt_construction',
                        'data': _pc_stage
                    }).decode() + '\n\n'
            except Exception as e:
                ChatBILogUtil.error(f"Failed to record prompt_construction stage (SQL): {e}")

            sql_res = self.generate_sql(_session)
            full_sql_text = ''
            
            # 使得generate_sql中抛出的SingleMessageError（如空响应）
            # 能被下方的except SingleMessageError捕获并转为友好回答
            try:
                for chunk in sql_res:
                    # 处理思考过程阶段数据
                    if chunk.get('type') == 'thinking_stage':
                        if in_chat:
                            yield 'data:' + orjson.dumps({
                                'type': 'thinking_stage',
                                'stage': chunk.get('stage'),
                                'data': chunk.get('data')
                            }).decode() + '\n\n'
                        continue
                    # 安全处理：确保content不为None
                    content = chunk.get('content')
                    if content:
                        full_sql_text += content
                    if in_chat:
                        yield 'data:' + orjson.dumps(
                            {'content': chunk.get('content'), 'reasoning_content': chunk.get('reasoning_content'),
                             'type': 'sql-result'}).decode() + '\n\n'
                if in_chat:
                    yield 'data:' + orjson.dumps({'type': 'info', 'msg': 'sql generated'}).decode() + '\n\n'
                # filter sql
                ChatBILogUtil.info(full_sql_text)
                
                # 恢复预测意图的原始问题（SQL生成已完成，后续流程需要原始问题）
                if _original_question_for_predict:
                    self.chat_question.question = _original_question_for_predict
                    ChatBILogUtil.info(f"[prediction] Restored original question: '{_original_question_for_predict}'")

                chart_type = self.get_chart_type_from_sql_answer(full_sql_text)

                # check_sql抛出SingleMessageError，之前被外层except捕获显示为红色错误框。
                use_dynamic_ds: bool = self.current_assistant and self.current_assistant.type in dynamic_ds_types
                is_page_embedded: bool = self.current_assistant and self.current_assistant.type == 4
                dynamic_sql_result = None
                chatbi_temp_sql_text = None
                assistant_dynamic_sql = None
                # row permission
                if ((not self.current_assistant or is_page_embedded) and is_normal_user(
                        self.current_user)) or use_dynamic_ds:
                    sql, tables = self.check_sql(res=full_sql_text, lang=self.chat_question.lang if hasattr(self, 'chat_question') else '')
                    sql_result = None

                    if use_dynamic_ds:
                        dynamic_sql_result = self.generate_assistant_dynamic_sql(_session, sql, tables)
                        chatbi_temp_sql_text = dynamic_sql_result.get(
                            'chatbi_temp_sql_text') if dynamic_sql_result else None
                        # sql_result = self.generate_assistant_filter(sql, tables)
                    else:
                        sql_result = self.generate_filter(_session, sql, tables)  # maybe no sql and tables

                    if sql_result:
                        ChatBILogUtil.info(sql_result)
                        sql = self.check_save_sql(session=_session, res=sql_result)
                    elif dynamic_sql_result and chatbi_temp_sql_text:
                        assistant_dynamic_sql = self.check_save_sql(session=_session, res=chatbi_temp_sql_text)
                    else:
                        sql = self.check_save_sql(session=_session, res=full_sql_text)
                else:
                    sql = self.check_save_sql(session=_session, res=full_sql_text)
            except SingleMessageError as sql_refuse_err:
                # LLM明确表示无法生成SQL（success:false），转为友好的文本回答
                refuse_msg = str(sql_refuse_err)
                ChatBILogUtil.info(f"[SQL-Refuse] LLM refused to generate SQL: {refuse_msg}")
                
                # 尝试从JSON格式中提取友好消息
                friendly_msg = refuse_msg
                try:
                    _parsed = orjson.loads(refuse_msg)
                    if isinstance(_parsed, dict) and _parsed.get('message'):
                        friendly_msg = _parsed['message']
                except Exception:
                    pass
                
                # 构建友好回答：包含LLM的拒绝原因 + 建议
                _is_en_refuse = (self.chat_question.lang or '').lower().startswith('en')
                if _is_en_refuse:
                    fallback_answer = f"{friendly_msg}\n\n💡 You can try rephrasing your question, or check if the datasource contains the relevant tables and fields."
                else:
                    fallback_answer = f"{friendly_msg}\n\n💡 您可以尝试换一种提问方式，或者检查数据源中是否包含相关的数据表和字段。"
                
                # 更新intent为irrelevant_query，使前端历史记录加载时正确映射为direct_answer
                try:
                    save_intent(_session, self.get_record().id, 'irrelevant_query')
                except Exception:
                    pass
                
                # 保存为正常回答（不是错误）
                try:
                    save_analysis_answer(
                        session=_session, record_id=self.record.id,
                        answer=orjson.dumps({'content': fallback_answer, 'reasoning_content': ''}).decode()
                    )
                except Exception as save_e:
                    ChatBILogUtil.error(f"[SQL-Refuse] Failed to save fallback answer: {save_e}")
                
                if in_chat:
                    yield 'data:' + orjson.dumps({
                        'content': fallback_answer,
                        'reasoning_content': '',
                        'type': 'direct-answer'
                    }).decode() + '\n\n'
                    
                    try:
                        from apps.chat.thinking.thinking_integration import record_provenance_stage
                        _refuse_provenance = []
                        _refuse_ds_type = (self.ds.type or '').lower() if self.ds else ''
                        _is_en_prov_refuse = (self.chat_question.lang or '').lower().startswith('en')
                        
                        if _refuse_ds_type == 'pdf':
                            if hasattr(self, '_rag_doc_chunks') and self._rag_doc_chunks:
                                for dc in self._rag_doc_chunks[:5]:
                                    _prov_pdf = {
                                        'source_type': 'pdf',
                                        'source_name': dc.get('source_name') or dc.get('source_file') or (self.ds.name if self.ds else ''),
                                        'page_number': dc.get('page_number'),
                                        'section_title': dc.get('section_title'),
                                        'chunk_type': dc.get('chunk_type', 'text'),
                                        'similarity': dc.get('similarity', 0),
                                        'text': (dc.get('text', '') or '')[:200],
                                    }
                                    if dc.get('table_index') is not None:
                                        _prov_pdf['table_index'] = dc['table_index']
                                    _refuse_provenance.append(_prov_pdf)
                            else:
                                _refuse_provenance.append({
                                    'source_type': 'pdf',
                                    'source_name': self.ds.name if self.ds else '',
                                })
                        elif _refuse_ds_type in ('excel', 'csv'):
                            # 增强 Excel/CSV 溯源信息
                            _refuse_excel_prov = {
                                'source_type': _refuse_ds_type,
                                'source_name': self.ds.name if self.ds else '',
                                'data_storage': 'PostgreSQL (imported)',
                                'description': f'SQL generation refused for {_refuse_ds_type.upper()} data source' if _is_en_prov_refuse else f'{_refuse_ds_type.upper()} 数据源 SQL 生成被拒绝',
                            }
                            try:
                                if self.ds and isinstance(self.ds, CoreDatasource):
                                    from apps.datasource.models.datasource import CoreTable as _RefuseTable
                                    _refuse_tables = _session.query(_RefuseTable).filter(
                                        _RefuseTable.ds_id == self.ds.id,
                                        _RefuseTable.checked == True
                                    ).limit(5).all()
                                    if _refuse_tables:
                                        _refuse_excel_prov['table_names'] = [
                                            t.custom_comment or t.table_comment or t.table_name
                                            for t in _refuse_tables
                                        ]
                            except Exception:
                                pass
                            _refuse_provenance.append(_refuse_excel_prov)
                        else:
                            _refuse_provenance.append({
                                'source_type': 'database',
                                'source_name': self.ds.name if self.ds else ('General Knowledge' if _is_en_prov_refuse else '通用知识'),
                                'table_names': [t.name for t in self.ds.tables][:5] if self.ds and hasattr(self.ds, 'tables') and self.ds.tables else [],
                            })
                        
                        if _refuse_provenance:
                            record_provenance_stage(self.thinking_process, _refuse_provenance)
                            _refuse_prov_stage = self.thinking_process.get_stage('provenance')
                            if _refuse_prov_stage:
                                yield 'data:' + orjson.dumps({'type': 'thinking_stage', 'stage': 'provenance', 'data': _refuse_prov_stage}).decode() + '\n\n'
                    except Exception as _refuse_prov_e:
                        ChatBILogUtil.error(f"[SQL-Refuse] Failed to record provenance: {_refuse_prov_e}")
                    
                    yield 'data:' + orjson.dumps({'type': 'finish'}).decode() + '\n\n'
                else:
                    if stream:
                        yield fallback_answer
                    else:
                        json_result['direct_answer'] = fallback_answer
                        yield json_result
                return

            ChatBILogUtil.info('sql: ' + sql)
            ChatBILogUtil.info(f"[PERF] SQL generation completed in {time.time() - _perf_sql_gen_start:.2f}s, total elapsed: {time.time() - _task_start_time:.2f}s")

            if not stream:
                json_result['sql'] = sql

            format_sql = sqlparse.format(sql, reindent=True)
            if in_chat:
                yield 'data:' + orjson.dumps({'content': format_sql, 'type': 'sql'}).decode() + '\n\n'
            else:
                if stream:
                    yield f'```sql\n{format_sql}\n```\n\n'

            # execute sql
            real_execute_sql = sql
            if chatbi_temp_sql_text and assistant_dynamic_sql:
                dynamic_sql_result.pop('chatbi_temp_sql_text')
                for origin_table, subsql in dynamic_sql_result.items():
                    assistant_dynamic_sql = assistant_dynamic_sql.replace(f'{dynamic_subsql_prefix}{origin_table}',
                                                                          subsql)
                real_execute_sql = assistant_dynamic_sql

            if finish_step.value <= ChatFinishStep.GENERATE_SQL.value:
                if in_chat:
                    yield 'data:' + orjson.dumps({'type': 'finish'}).decode() + '\n\n'
                if not stream:
                    yield json_result
                return

            _perf_sql_exec_start = time.time()
            result = self.execute_sql(sql=real_execute_sql)
            ChatBILogUtil.info(f"[PERF] SQL execution: {time.time() - _perf_sql_exec_start:.2f}s")

            _data = DataFormat.convert_large_numbers_in_object_array(result.get('data'))
            result["data"] = _data

            # Excel/CSV数据源的列名可能是拼音，替换为中文显示名
            try:
                result = self.apply_field_display_names(session=_session, result=result)
            except Exception as _field_map_e:
                ChatBILogUtil.error(f"[field-display] apply_field_display_names failed: {_field_map_e}")

            # SQL 路径也执行后置验证（抗幻觉）
            try:
                if hasattr(self, '_unified_rag_result') and self._unified_rag_result:
                    _gen_sql_val = self._unified_rag_result.get('generate')
                    if _gen_sql_val and _gen_sql_val.validation_rules:
                        from apps.chat.thinking.unified_rag_executor import validate_generation_result
                        sql_validation = validate_generation_result(
                            answer="", sql=sql,
                            validation_rules=_gen_sql_val.validation_rules,
                        )
                        if sql_validation.get("warnings"):
                            ChatBILogUtil.warning(
                                f"[run_task] SQL validation warnings: {sql_validation['warnings']}"
                            )
            except Exception as _sql_val_e:
                ChatBILogUtil.error(f"[run_task] SQL post-validation failed: {_sql_val_e}")

            self.save_sql_data(session=_session, data_obj=result)
            
            # 记录SQL执行阶段到思考过程
            try:
                # 传入已执行的 SQL 语句，避免信息丢失
                record_execution_stage(
                    self.thinking_process,
                    row_count=len(result.get('data', [])),
                    execution_time=result.get('execution_time', 0),
                    sql=sql
                )
                
                # 发送SQL执行思考过程
                if in_chat:
                    exec_stage_data = self.thinking_process.get_stage('sql_execution')
                    if exec_stage_data:
                        yield 'data:' + orjson.dumps({'type': 'thinking_stage', 'stage': 'sql_execution', 'data': exec_stage_data}).decode() + '\n\n'
            except Exception as e:
                ChatBILogUtil.error(f"Failed to record SQL execution thinking stage: {e}")
            
            if in_chat:
                _sql_data_payload = {'content': 'execute-success', 'type': 'sql-data'}
                # 缓存降级时附带用户提示
                if result and result.get('cache_warning'):
                    _sql_data_payload['cache_warning'] = result['cache_warning']
                yield 'data:' + orjson.dumps(_sql_data_payload).decode() + '\n\n'
            if not stream:
                json_result['data'] = result.get('data')

            if finish_step.value <= ChatFinishStep.QUERY_DATA.value:
                if stream:
                    if in_chat:
                        yield 'data:' + orjson.dumps({'type': 'finish'}).decode() + '\n\n'
                    else:
                        _column_list = []
                        for field in result.get('fields'):
                            _column_list.append(AxisObj(name=field, value=field))

                        md_data, _fields_list = DataFormat.convert_object_array_for_pandas(_column_list, result.get('data'))


                        if not md_data or not _fields_list:
                            yield 'The SQL execution result is empty.\n\n'
                        else:
                            df = pd.DataFrame(md_data, columns=_fields_list)
                            df_safe = DataFormat.safe_convert_to_string(df)
                            markdown_table = df_safe.to_markdown(index=False)
                            yield markdown_table + '\n\n'
                else:
                    yield json_result
                return

            _smart_output_decision = None
            try:
                from apps.chat.task.smart_output import analyze_output_format
                _smart_output_decision = analyze_output_format(
                    question=_original_question_for_predict or self.chat_question.question,
                    sql=real_execute_sql,
                    result=result,
                    chart_type_hint=chart_type or '',
                    intent=getattr(self, '_early_intent', '')
                )
                ChatBILogUtil.info(f"[smart-output] Decision: {_smart_output_decision.format_type}, reason: {_smart_output_decision.reason}")
                
                # 记录输出格式决策到思考过程
                try:
                    from apps.chat.thinking.thinking_integration import record_smart_output_stage
                    record_smart_output_stage(
                        self.thinking_process,
                        decision=_smart_output_decision.to_dict(),
                        row_count=len(result.get('data', [])),
                        field_count=len(result.get('fields', []))
                    )
                    stage_data = self.thinking_process.get_stage('smart_output')
                    if stage_data and in_chat:
                        yield 'data:' + orjson.dumps({
                            'type': 'thinking_stage',
                            'stage': 'smart_output',
                            'data': stage_data
                        }).decode() + '\n\n'
                except Exception as e:
                    ChatBILogUtil.error(f"Failed to record smart_output stage: {e}")
            except Exception as e:
                ChatBILogUtil.error(f"[smart-output] Decision failed, falling back to chart: {e}")
            
            # 单行结果 → 自然语言直接回答，跳过图表生成
            if _smart_output_decision and _smart_output_decision.should_skip_chart():
                nl_answer = _smart_output_decision.natural_language_answer
                ChatBILogUtil.info(f"[smart-output] Skipping chart generation, natural language answer: {nl_answer}")
                
                # 构建一个最小化的table类型chart配置（保存到DB，前端历史加载需要）
                _fields = result.get('fields', [])
                _minimal_columns = [{'name': f, 'value': f} for f in _fields]
                _minimal_chart = {
                    'type': 'table',
                    'title': nl_answer,
                    'columns': _minimal_columns,
                    'smart_output': True
                }
                from apps.chat.crud.chat import save_chart
                save_chart(session=_session, chart=orjson.dumps(_minimal_chart).decode(), record_id=self.record.id)
                
                if in_chat:
                    # 发送smart-answer事件（前端渲染为自然语言卡片）
                    yield 'data:' + orjson.dumps({
                        'type': 'smart-answer',
                        'content': nl_answer,
                        'chart': orjson.dumps(_minimal_chart).decode()
                    }).decode() + '\n\n'
                    
                    # 跳过图表生成，直接进入内联分析/预测（如果需要）
                    # 获取SQL执行结果的行数
                    _result_row_count = len(result.get('data', [])) if result else 0
                    
                    if detected_route == 'analysis' and _result_row_count > 0:
                        try:
                            yield 'data:' + orjson.dumps({'type': 'inline_analysis_start'}).decode() + '\n\n'
                            analysis_res = self.generate_analysis(_session, skip_rag=True)
                            _inline_analysis_custom_prompts = []
                            for chunk in analysis_res:
                                if chunk.get('type') == 'rag_results':
                                    _inline_analysis_custom_prompts = chunk.get('data', {}).get('custom_prompts', [])
                                    yield 'data:' + orjson.dumps(chunk).decode() + '\n\n'
                                elif chunk.get('type') == 'thinking_stage':
                                    yield 'data:' + orjson.dumps(chunk).decode() + '\n\n'
                                else:
                                    yield 'data:' + orjson.dumps({
                                        'content': chunk.get('content'),
                                        'reasoning_content': chunk.get('reasoning_content'),
                                        'type': 'inline-analysis-result'
                                    }).decode() + '\n\n'
                            yield 'data:' + orjson.dumps({'type': 'inline_analysis_finish'}).decode() + '\n\n'
                            if _inline_analysis_custom_prompts:
                                try:
                                    merge_rag_custom_prompts(_session, self.record.id, _inline_analysis_custom_prompts)
                                except Exception as _e:
                                    ChatBILogUtil.error(f"[inline-analysis] Failed to merge custom prompts: {_e}")
                        except Exception as e:
                            ChatBILogUtil.error(f"[smart-output] Inline analysis failed: {e}")
                    
                    elif detected_route == 'prediction' and _result_row_count > 0:
                        # smart_output跳过图表路径中缺少prediction内联执行
                        try:
                            ChatBILogUtil.info(f"[smart-output] Inline prediction for single-row result")
                            yield 'data:' + orjson.dumps({'type': 'inline_predict_start'}).decode() + '\n\n'
                            
                            # 单行结果大概率不满足时间序列预测条件，直接走文本预测降级
                            original_question = self.chat_question.question
                            _is_en_sp = (self.chat_question.lang or '').lower().startswith('en')
                            if _is_en_sp:
                                self.chat_question.question = f"Perform predictive analysis based on the following data (Note: only 1 row of data, cannot generate precise time-series prediction charts, please provide text-based predictive analysis and trend judgment based on available data): {original_question}"
                            else:
                                self.chat_question.question = f"基于以下数据进行预测性分析（注意：数据仅有1行，无法生成精确的时间序列预测图表，请基于现有数据给出文字预测分析和趋势判断）：{original_question}"
                            try:
                                analysis_res = self.generate_analysis(_session, skip_rag=True)
                                for chunk in analysis_res:
                                    if chunk.get('type') == 'rag_results':
                                        yield 'data:' + orjson.dumps({'type': 'rag_results', 'data': chunk.get('data')}).decode() + '\n\n'
                                    elif chunk.get('type') == 'thinking_stage':
                                        yield 'data:' + orjson.dumps({'type': 'thinking_stage', 'stage': chunk.get('stage'), 'data': chunk.get('data')}).decode() + '\n\n'
                                    else:
                                        yield 'data:' + orjson.dumps({
                                            'content': chunk.get('content'),
                                            'reasoning_content': chunk.get('reasoning_content'),
                                            'type': 'inline-predict-result'
                                        }).decode() + '\n\n'
                            finally:
                                self.chat_question.question = original_question
                            
                            yield 'data:' + orjson.dumps({'type': 'inline_predict_finish', 'predict_success': False}).decode() + '\n\n'
                        except Exception as e:
                            ChatBILogUtil.error(f"[smart-output] Inline prediction failed: {e}")
                    
                    # ========== Output 阶段：溯源凭证（smart_output 跳过图表路径） ==========
                    try:
                        from apps.chat.thinking.thinking_integration import record_provenance_stage
                        _prov_records_so = []
                        _ds_type_so = (self.ds.type or '').lower() if self.ds else 'database'
                        if _ds_type_so in ('excel', 'csv'):
                            _so_prov_entry = {
                                'source_type': _ds_type_so,
                                'source_name': self.ds.name if self.ds else '',
                                'sql': locals().get('real_execute_sql', ''),
                                'table_names': _extract_friendly_table_names(real_execute_sql, strip_hash_suffix=True) if locals().get('real_execute_sql') else [],
                                'row_count': len(result.get('data', [])) if result else 0,
                                'execution_time': result.get('execution_time', 0) if result else 0,
                                'cache_status': result.get('cache_status', '') if result else '',
                                'update_time': str(self.ds.update_time) if self.ds and hasattr(self.ds, 'update_time') else '',
                            }
                            _prov_records_so.append(_so_prov_entry)
                        else:
                            _prov_records_so.append({
                                'source_type': 'database',
                                'source_name': self.ds.name if self.ds else '',
                                'sql': locals().get('real_execute_sql', ''),
                                'table_names': _extract_friendly_table_names(real_execute_sql) if locals().get('real_execute_sql') else [],
                                'row_count': len(result.get('data', [])) if result else 0,
                                'execution_time': result.get('execution_time', 0) if result else 0,
                                'cache_status': result.get('cache_status', '') if result else '',
                                'update_time': str(self.ds.update_time) if self.ds and hasattr(self.ds, 'update_time') else '',
                            })
                        if _prov_records_so:
                            record_provenance_stage(self.thinking_process, _prov_records_so)
                            _prov_stage_so = self.thinking_process.get_stage('provenance')
                            if _prov_stage_so:
                                yield 'data:' + orjson.dumps({'type': 'thinking_stage', 'stage': 'provenance', 'data': _prov_stage_so}).decode() + '\n\n'
                    except Exception as e:
                        ChatBILogUtil.error(f"[smart-output] Failed to record provenance: {e}")
                    
                    yield 'data:' + orjson.dumps({'type': 'finish'}).decode() + '\n\n'
                else:
                    if stream:
                        yield nl_answer + '\n\n'
                    else:
                        json_result['smart_answer'] = nl_answer
                        json_result['chart'] = _minimal_chart
                        yield json_result
                
                # 保存思考过程
                try:
                    if self.thinking_process and _session:
                        thinking_data = self.thinking_process.to_dict()
                        if self.dialogue_tracker:
                            thinking_data['dialogue_state'] = self.dialogue_tracker.get_state_summary()
                        import json as _json
                        thinking_json = _json.dumps(thinking_data, ensure_ascii=False)
                        save_thinking_process(session=_session, record_id=self.record.id, thinking_process=thinking_json)
                        self._thinking_process_saved = True
                except Exception as e:
                    ChatBILogUtil.error(f"[smart-output] Failed to save thinking process: {e}")
                
                return

            # 图表类型覆盖：当智能决策建议不同的图表类型时，覆盖LLM的推荐
            if _smart_output_decision and _smart_output_decision.override_chart_type:
                _original_chart_type = chart_type
                chart_type = _smart_output_decision.override_chart_type
                ChatBILogUtil.info(f"[smart-output] Overriding chart type: {_original_chart_type} -> {chart_type}")

            # 可视化意图判定
            # 基于数据特征+用户问题意图，精准判定图表类型和维度映射
            try:
                from apps.chat.thinking.visualization_intent import VisualizationIntentDetector
                _viz_fields = result.get('fields', []) if result else []
                _viz_data = result.get('data', []) if result else []
                _viz_features = VisualizationIntentDetector.extract_data_features(_viz_fields, _viz_data)
                _viz_intent = VisualizationIntentDetector.detect(
                    question=self.chat_question.question,
                    data_features=_viz_features,
                    ds_type=self.ds.type if self.ds else 'database',
                    lang=self.chat_question.lang,
                )
                if _viz_intent.needs_visualization and _viz_intent.confidence > 0.7:
                    if not chart_type or chart_type == 'table':
                        chart_type = _viz_intent.chart_type
                        ChatBILogUtil.info(f"[viz-intent] Auto-detected chart type: {chart_type} (confidence={_viz_intent.confidence:.2f})")
                # 记录可视化意图到思考过程
                from apps.chat.thinking.thinking_integration import record_visualization_intent_stage
                record_visualization_intent_stage(self.thinking_process, _viz_intent.to_dict())
                _viz_stage = self.thinking_process.get_stage('visualization_intent')
                if _viz_stage and in_chat:
                    yield 'data:' + orjson.dumps({
                        'type': 'thinking_stage',
                        'stage': 'visualization_intent',
                        'data': _viz_stage
                    }).decode() + '\n\n'
            except Exception as e:
                ChatBILogUtil.error(f"[viz-intent] Detection failed: {e}")

            # KPI 快速路径：跳过 LLM 图表生成，直接构建 KPI 配置
            # KPI 只需要 title + value，不需要 LLM 推断 axis/columns
            if chart_type == 'kpi' and result and result.get('data'):
                from decimal import Decimal as _Decimal
                _kpi_row = result['data'][0]
                _kpi_fields = result.get('fields', [])
                _kpi_title = ''
                _kpi_value = 0

                # 单字段：字段名作为标题，值作为 KPI 值
                _numeric_fields = [f for f in _kpi_fields if isinstance(_kpi_row.get(f), (int, float, _Decimal))]
                _text_fields = [f for f in _kpi_fields if f not in _numeric_fields]

                if len(_kpi_fields) == 1 and len(_numeric_fields) == 1:
                    _kpi_title = _numeric_fields[0]
                    _kpi_value = _kpi_row[_numeric_fields[0]]
                elif len(_numeric_fields) >= 1:
                    # 有文本字段时用作标题，否则用数值字段名
                    if _text_fields:
                        _kpi_title = str(_kpi_row.get(_text_fields[0], _text_fields[0]))
                    else:
                        _kpi_title = _numeric_fields[0]
                    _kpi_value = _kpi_row[_numeric_fields[0]]
                else:
                    # 无数值字段，兜底
                    _kpi_title = _kpi_fields[0] if _kpi_fields else 'KPI'
                    _kpi_value = _kpi_row.get(_kpi_fields[0], 0) if _kpi_fields else 0

                # Decimal → float（JSON 序列化兼容）
                if isinstance(_kpi_value, _Decimal):
                    _kpi_value = float(_kpi_value)

                # 尝试翻译字段名为中文显示名
                try:
                    from apps.chat.task.smart_output import _translate_field_name
                    _kpi_title = _translate_field_name(_kpi_title, self.chat_question.question)
                except Exception:
                    pass

                _kpi_columns = [{'name': f, 'value': f} for f in _kpi_fields]
                _kpi_chart = {
                    'type': 'kpi',
                    'title': _kpi_title,
                    'data': {'title': _kpi_title, 'value': _kpi_value},
                    'columns': _kpi_columns,
                }
                ChatBILogUtil.info(f"[kpi-fast-path] Built KPI config: title={_kpi_title}, value={_kpi_value}")

                from apps.chat.crud.chat import save_chart
                save_chart(session=_session, chart=orjson.dumps(_kpi_chart).decode(), record_id=self.record.id)

                if in_chat:
                    yield 'data:' + orjson.dumps(
                        {'content': orjson.dumps(_kpi_chart).decode(), 'type': 'chart'}).decode() + '\n\n'
                else:
                    if not stream:
                        json_result['chart'] = _kpi_chart

                # 跳过 LLM 图表生成，直接进入后续流程（内联分析/预测等）
                chart = _kpi_chart
                # 使用 goto-like 标记跳过 generate_chart + check_save_chart
                _skip_chart_generation = True
            else:
                _skip_chart_generation = False

            # ==========  性能优化：规则引擎图表配置（替代 LLM 调用，~150s → <1ms） ==========
            if not _skip_chart_generation:
                try:
                    from apps.chat.task.chart_rule_engine import build_chart_config
                    _rule_chart = build_chart_config(
                        chart_type=chart_type or '',
                        fields=result.get('fields', []) if result else [],
                        data=result.get('data', []) if result else [],
                        question=self.chat_question.question,
                        sql=real_execute_sql if locals().get('real_execute_sql') else '',
                        terminologies=self.chat_question.terminologies or '',
                    )
                    if _rule_chart:
                        _perf_chart_start = time.time()
                        chart = _rule_chart
                        from apps.chat.crud.chat import save_chart
                        save_chart(session=_session, chart=orjson.dumps(chart).decode(), record_id=self.record.id)
                        ChatBILogUtil.info(f"[chart-rule-engine] Generated chart config in <1ms: type={chart.get('type')}, title={chart.get('title')}")
                        ChatBILogUtil.info(f"[PERF] chart generation (rule engine) completed in {time.time() - _perf_chart_start:.4f}s, total elapsed: {time.time() - _task_start_time:.2f}s")
                        
                        # 记录图表生成阶段到思考过程
                        try:
                            from apps.chat.thinking.thinking_integration import record_chart_stage as _rule_record_chart_stage
                            _rule_record_chart_stage(
                                self.thinking_process,
                                chart_type=chart.get('type', 'unknown'),
                                reasoning='Rule-based chart config generation (no LLM call)',
                                generation_time=time.time() - _perf_chart_start,
                                token_usage={}
                            )
                            chart_stage_data = self.thinking_process.get_stage('chart_generation')
                            if chart_stage_data and in_chat:
                                yield 'data:' + orjson.dumps({'type': 'thinking_stage', 'stage': 'chart_generation', 'data': chart_stage_data}).decode() + '\n\n'
                        except Exception as _cse:
                            ChatBILogUtil.error(f"[chart-rule-engine] Failed to record thinking stage: {_cse}")
                        
                        if not stream:
                            json_result['chart'] = chart
                        if in_chat:
                            yield 'data:' + orjson.dumps({'content': orjson.dumps(chart).decode(), 'type': 'chart'}).decode() + '\n\n'
                        
                        _skip_chart_generation = True
                except Exception as _rule_e:
                    ChatBILogUtil.warning(f"[chart-rule-engine] Rule engine failed, falling back to LLM: {_rule_e}")

            if not _skip_chart_generation:
              # generate chart
              _perf_chart_start = time.time()
              chart_res = self.generate_chart(_session, chart_type)
              full_chart_text = ''
              for chunk in chart_res:
                # 处理思考过程阶段数据
                if chunk.get('type') == 'thinking_stage':
                    if in_chat:
                        yield 'data:' + orjson.dumps({
                            'type': 'thinking_stage',
                            'stage': chunk.get('stage'),
                            'data': chunk.get('data')
                        }).decode() + '\n\n'
                    continue
                # 安全处理：确保content不为None
                content = chunk.get('content')
                if content:
                    full_chart_text += content
                if in_chat:
                    yield 'data:' + orjson.dumps(
                        {'content': chunk.get('content'), 'reasoning_content': chunk.get('reasoning_content'),
                         'type': 'chart-result'}).decode() + '\n\n'
              if in_chat:
                yield 'data:' + orjson.dumps({'type': 'info', 'msg': 'chart generated'}).decode() + '\n\n'

              # 检测图表生成LLM返回空内容（0 output tokens）
              # 提前检测并抛出友好错误，避免check_save_chart报"Cannot parse chart config from answer"
              if not full_chart_text or not full_chart_text.strip():
                _is_en_chart = (self.chat_question.lang or '').lower().startswith('en')
                _empty_chart_msg = ('The AI model returned an empty response during chart generation. '
                                    'Please try again.') if _is_en_chart else \
                                   'AI模型在生成图表配置时返回了空响应，请稍后重试。'
                ChatBILogUtil.error(
                    f"[run_task] Chart generation LLM returned empty content. "
                    f"Model: {self.chat_question.ai_modal_name}"
                )
                raise SingleMessageError(_empty_chart_msg)

              # filter chart
              ChatBILogUtil.info(full_chart_text)
              chart = self.check_save_chart(session=_session, res=full_chart_text)
              ChatBILogUtil.info(chart)
              ChatBILogUtil.info(f"[PERF] chart generation completed in {time.time() - _perf_chart_start:.2f}s, total elapsed: {time.time() - _task_start_time:.2f}s")

              if not stream:
                json_result['chart'] = chart

              if in_chat:
                yield 'data:' + orjson.dumps(
                    {'content': orjson.dumps(chart).decode(), 'type': 'chart'}).decode() + '\n\n'
              else:
                if stream:
                    _fields = {}
                    if chart.get('columns'):
                        for _column in chart.get('columns'):
                            if _column:
                                _fields[_column.get('value')] = _column.get('name')
                    if chart.get('axis'):
                        if chart.get('axis').get('x'):
                            _fields[chart.get('axis').get('x').get('value')] = chart.get('axis').get('x').get('name')
                        if chart.get('axis').get('y'):
                            _fields[chart.get('axis').get('y').get('value')] = chart.get('axis').get('y').get('name')
                        if chart.get('axis').get('series'):
                            _fields[chart.get('axis').get('series').get('value')] = chart.get('axis').get('series').get(
                                'name')
                    _column_list = []
                    for field in result.get('fields'):
                        _column_list.append(
                            AxisObj(name=field if not _fields.get(field) else _fields.get(field), value=field))

                    md_data, _fields_list = DataFormat.convert_object_array_for_pandas(_column_list, result.get('data'))

                    # data, _fields_list, col_formats = self.format_pd_data(_column_list, result.get('data'))

                    if not md_data or not _fields_list:
                        yield 'The SQL execution result is empty.\n\n'
                    else:
                        df = pd.DataFrame(md_data, columns=_fields_list)
                        df_safe = DataFormat.safe_convert_to_string(df)
                        markdown_table = df_safe.to_markdown(index=False)
                        yield markdown_table + '\n\n'

            if in_chat:
                _result_row_count = len(result.get('data', [])) if result else 0
                _deferred_inline_analysis = False  #  性能优化：data_query 延迟分析标记
                _deferred_inline_prediction = False  #  UX优化：prediction 延迟预测标记
                
                if detected_route == 'analysis' and _result_row_count == 0:
                    # ========== 分析意图但SQL返回0行：生成"无数据"分析说明 ==========
                    try:
                        ChatBILogUtil.info(f"[inline-analysis] SQL returned 0 rows, generating no-data analysis")
                        yield 'data:' + orjson.dumps({
                            'type': 'inline_analysis_start'
                        }).decode() + '\n\n'
                        
                        _is_en_nda = (self.chat_question.lang or '').lower().startswith('en')
                        if _is_en_nda:
                            no_data_msg = (
                                "## Data Analysis Result\n\n"
                                "The current query returned no data, so data analysis cannot be performed.\n\n"
                                "### Possible Reasons\n"
                                "- Query conditions are too strict, no matching records\n"
                                "- No relevant data in the data table\n"
                                "- Time range or filter conditions need adjustment\n\n"
                                "### Suggestions\n"
                                "- Try relaxing query conditions, e.g., expand the time range\n"
                                "- Check if the datasource contains relevant data\n"
                                "- Rephrase with more specific business metrics"
                            )
                        else:
                            no_data_msg = (
                                "## 数据分析结果\n\n"
                                "当前查询未返回任何数据，无法进行数据分析。\n\n"
                                "### 可能的原因\n"
                                "- 查询条件过于严格，没有匹配的数据记录\n"
                                "- 数据表中暂无相关数据\n"
                                "- 时间范围或筛选条件需要调整\n\n"
                                "### 建议\n"
                                "- 尝试放宽查询条件，例如扩大时间范围\n"
                                "- 检查数据源中是否存在相关数据\n"
                                "- 使用更具体的业务指标重新提问，例如「查询本月销售额」"
                            )
                        
                        yield 'data:' + orjson.dumps({
                            'content': no_data_msg,
                            'reasoning_content': '',
                            'type': 'inline-analysis-result'
                        }).decode() + '\n\n'
                        
                        # 保存到record
                        save_analysis_answer(
                            session=_session, record_id=self.record.id,
                            answer=orjson.dumps({'content': no_data_msg, 'reasoning_content': ''}).decode()
                        )
                        
                        yield 'data:' + orjson.dumps({
                            'type': 'inline_analysis_finish'
                        }).decode() + '\n\n'
                    except Exception as e:
                        ChatBILogUtil.error(f"[inline-analysis] No-data analysis failed: {e}")
                
                elif detected_route == 'analysis' and _result_row_count > 0:
                    # ========== 分析意图：延迟到 finish 后执行，先展示图表 ==========
                    _deferred_inline_analysis = True
                
                elif detected_route == 'prediction' and _result_row_count == 0:
                    # ========== 预测意图但SQL返回0行：生成"无数据"预测说明 ==========
                    try:
                        ChatBILogUtil.info(f"[inline-predict] SQL returned 0 rows, generating no-data prediction")
                        yield 'data:' + orjson.dumps({
                            'type': 'inline_predict_start'
                        }).decode() + '\n\n'
                        
                        _is_en_ndp = (self.chat_question.lang or '').lower().startswith('en')
                        if _is_en_ndp:
                            no_data_msg = (
                                "## Prediction Analysis Result\n\n"
                                "The current query returned no historical data, so trend prediction cannot be performed.\n\n"
                                "### Possible Reasons\n"
                                "- Query conditions are too strict, no matching historical data records\n"
                                "- No relevant time series data in the data table\n"
                                "- Time range or filter conditions need adjustment\n\n"
                                "### Suggestions\n"
                                "- Try relaxing query conditions, e.g., expand the time range\n"
                                "- Ensure the data contains time fields and numeric fields\n"
                                '- Rephrase with more specific business metrics, e.g., "Predict future sales trends"'
                            )
                        else:
                            no_data_msg = (
                                "## 预测分析结果\n\n"
                                "当前查询未返回任何历史数据，无法进行趋势预测。\n\n"
                                "### 可能的原因\n"
                                "- 查询条件过于严格，没有匹配的历史数据记录\n"
                                "- 数据表中暂无相关时间序列数据\n"
                                "- 时间范围或筛选条件需要调整\n\n"
                                "### 建议\n"
                                "- 尝试放宽查询条件，例如扩大时间范围\n"
                                "- 确保数据中包含时间字段和数值字段\n"
                                '- 使用更具体的业务指标重新提问，例如「预测未来销售额趋势」'
                            )
                        
                        yield 'data:' + orjson.dumps({
                            'content': no_data_msg,
                            'reasoning_content': '',
                            'type': 'inline-predict-result'
                        }).decode() + '\n\n'
                        
                        # 保存到record
                        save_predict_answer(
                            session=_session, record_id=self.record.id,
                            answer=orjson.dumps({'content': no_data_msg, 'reasoning_content': ''}).decode()
                        )
                        
                        yield 'data:' + orjson.dumps({
                            'type': 'inline_predict_finish',
                            'predict_success': False
                        }).decode() + '\n\n'
                    except Exception as e:
                        ChatBILogUtil.error(f"[inline-predict] No-data prediction failed: {e}")
                
                elif detected_route == 'prediction' and _result_row_count > 0:
                    # ========== 预测意图：延迟到 finish 后执行，先展示图表 ==========
                    _deferred_inline_prediction = True
                
                elif detected_route == 'data_query' and _result_row_count > 0:
                    # ========== 数据查询意图：标记需要延迟执行内联分析 ==========
                    _deferred_inline_analysis = True
                
                # ========== Output 阶段：术语规范化 + 溯源凭证 ==========
                try:
                    from apps.chat.thinking.thinking_integration import record_provenance_stage
                    _provenance_records = []
                    _ds_type_prov = (self.ds.type or '').lower() if self.ds else 'database'
                    if _ds_type_prov == 'pdf':
                        # PDF溯源：页码、章节、检索相似度、片段类型
                        if hasattr(self, '_rag_doc_chunks') and self._rag_doc_chunks:
                            for dc in self._rag_doc_chunks[:5]:
                                _prov_pdf = {
                                    'source_type': 'pdf',
                                    'source_name': dc.get('filename', dc.get('source_file', '')),
                                    'page_number': dc.get('page_number'),
                                    'section_title': dc.get('section_title', ''),
                                    'chunk_type': dc.get('chunk_type', 'text'),
                                    'similarity': dc.get('similarity', 0),
                                    'update_time': dc.get('update_time', ''),
                                }
                                if dc.get('table_index') is not None:
                                    _prov_pdf['table_index'] = dc['table_index']
                                _provenance_records.append(_prov_pdf)
                    elif _ds_type_prov in ('excel', 'csv'):
                        # Excel/CSV溯源：文件名、表名、行号、执行时间
                        _prov_entry = {
                            'source_type': _ds_type_prov,
                            'source_name': self.ds.name if self.ds else '',
                            'sql': locals().get('real_execute_sql', ''),
                            'table_names': _extract_friendly_table_names(real_execute_sql, strip_hash_suffix=True) if locals().get('real_execute_sql') else [],
                            'row_count': len(result.get('data', [])) if result else 0,
                            'execution_time': result.get('execution_time', 0) if result else 0,
                            'cache_status': result.get('cache_status', '') if result else '',
                            'update_time': str(self.ds.update_time) if self.ds and hasattr(self.ds, 'update_time') else '',
                        }
                        _provenance_records.append(_prov_entry)
                    else:
                        # Database溯源：SQL语句、执行时间、缓存状态
                        _provenance_records.append({
                            'source_type': 'database',
                            'source_name': self.ds.name if self.ds else '',
                            'sql': locals().get('real_execute_sql', ''),
                            'table_names': _extract_friendly_table_names(real_execute_sql) if locals().get('real_execute_sql') else [],
                            'row_count': len(result.get('data', [])) if result else 0,
                            'execution_time': result.get('execution_time', 0) if result else 0,
                            'cache_status': result.get('cache_status', '') if result else '',
                            'update_time': str(self.ds.update_time) if self.ds and hasattr(self.ds, 'update_time') else '',
                        })
                    if _provenance_records:
                        record_provenance_stage(self.thinking_process, _provenance_records)
                        prov_stage_data = self.thinking_process.get_stage('provenance')
                        if prov_stage_data:
                            yield 'data:' + orjson.dumps({'type': 'thinking_stage', 'stage': 'provenance', 'data': prov_stage_data}).decode() + '\n\n'
                except Exception as e:
                    ChatBILogUtil.error(f"Failed to record provenance stage: {e}")
                
                # 后置推荐问题
                try:
                    from apps.chat.thinking.recommendation_engine import RecommendationEngine
                    _chart_type_for_rec = chart_type or 'table'
                    _ds_type_for_rec = (self.ds.type or '').lower() if self.ds else 'database'
                    _detected_intent_for_rec = locals().get('detected_intent', '')
                    post_recs = RecommendationEngine.generate_post_recommendations(
                        question=self.chat_question.question,
                        chart_type=_chart_type_for_rec,
                        intent=_detected_intent_for_rec,
                        ds_type=_ds_type_for_rec,
                        lang=self.chat_question.lang,
                    )
                    mid_recs = RecommendationEngine.generate_mid_recommendations(
                        question=self.chat_question.question,
                        intent=_detected_intent_for_rec,
                        ds_type=_ds_type_for_rec,
                        has_visualization=_chart_type_for_rec != 'table',
                        data_features=_build_data_features(result),
                        lang=self.chat_question.lang,
                    )
                    if post_recs or mid_recs:
                        yield 'data:' + orjson.dumps({
                            'type': 'layered_recommendations',
                            'data': {'mid': mid_recs, 'post': post_recs}
                        }).decode() + '\n\n'
                        # 记录推荐问题生成阶段到思考过程
                        try:
                            from apps.chat.thinking.thinking_integration import record_recommendation_stage
                            if post_recs:
                                record_recommendation_stage(self.thinking_process, 'post', post_recs)
                            if mid_recs:
                                record_recommendation_stage(self.thinking_process, 'mid', mid_recs)
                        except Exception as rec_e:
                            ChatBILogUtil.error(f"[post-recommendations] Failed to record stage: {rec_e}")
                except Exception as e:
                    ChatBILogUtil.error(f"[post-recommendations] Generation failed: {e}")

                ChatBILogUtil.info(f"[PERF] >>>>>> finish event sent, user-visible elapsed: {time.time() - _task_start_time:.2f}s <<<<<<")
                yield 'data:' + orjson.dumps({'type': 'finish'}).decode() + '\n\n'
                
                # ==========  参考 SQLBot：finish 后异步生成图表静态图片 ==========
                if chart and chart.get('type') != 'table' and result:
                    try:
                        image_url = request_picture(self.record.chat_id, self.record.id, chart,
                                                    format_json_data(result))
                        if image_url and _session:
                            from sqlmodel import select
                            stmt = select(ChatRecord).where(ChatRecord.id == self.record.id)
                            db_record = _session.exec(stmt).first()
                            if db_record:
                                db_record.chart_image = image_url
                                _session.add(db_record)
                                _session.commit()
                            ChatBILogUtil.info(f"[chart-image] Saved chart image: {image_url}")
                            yield 'data:' + orjson.dumps({
                                'type': 'chart_image',
                                'url': image_url
                            }).decode() + '\n\n'
                    except Exception:
                        pass  # G2 SSR截图服务未启动时静默跳过，不影响核心功能
                
                # ==========  UX优化：延迟执行内联分析/预测（finish后执行） ==========
                if _deferred_inline_analysis:
                    # 分析意图使用完整分析，data_query使用简要分析
                    _use_brief_mode = (detected_route == 'data_query')
                    _route_label = detected_route or 'data_query'
                    try:
                        ChatBILogUtil.info(f"[PERF] [inline-analysis] Starting deferred inline analysis for {_route_label}, record {self.record.id}, brief_mode={_use_brief_mode}")
                        yield 'data:' + orjson.dumps({'type': 'inline_analysis_start'}).decode() + '\n\n'
                        
                        _skip_analysis_cp = False
                        analysis_res = self.generate_analysis(_session, skip_rag=True, brief_mode=_use_brief_mode, skip_custom_prompt=_skip_analysis_cp)
                        _inline_analysis_custom_prompts_dq = []
                        for chunk in analysis_res:
                            if chunk.get('type') == 'rag_results':
                                _inline_analysis_custom_prompts_dq = chunk.get('data', {}).get('custom_prompts', [])
                                yield 'data:' + orjson.dumps({
                                    'type': 'rag_results',
                                    'data': chunk.get('data')
                                }).decode() + '\n\n'
                            elif chunk.get('type') == 'thinking_stage':
                                yield 'data:' + orjson.dumps({
                                    'type': 'thinking_stage',
                                    'stage': chunk.get('stage'),
                                    'data': chunk.get('data')
                                }).decode() + '\n\n'
                            else:
                                yield 'data:' + orjson.dumps({
                                    'content': chunk.get('content'),
                                    'reasoning_content': chunk.get('reasoning_content'),
                                    'type': 'inline-analysis-result'
                                }).decode() + '\n\n'
                        yield 'data:' + orjson.dumps({'type': 'inline_analysis_finish'}).decode() + '\n\n'
                        if _inline_analysis_custom_prompts_dq:
                            try:
                                merge_rag_custom_prompts(_session, self.record.id, _inline_analysis_custom_prompts_dq)
                            except Exception as _e:
                                ChatBILogUtil.error(f"[inline-analysis] Failed to merge custom prompts: {_e}")
                        ChatBILogUtil.info(f"[PERF] [inline-analysis] Deferred inline analysis for {_route_label} completed")
                    except Exception as e:
                        ChatBILogUtil.error(f"[inline-analysis] Deferred inline analysis for {_route_label} failed: {e}")
                        yield 'data:' + orjson.dumps({
                            'type': 'inline_analysis_error',
                            'message': str(e)
                        }).decode() + '\n\n'
                
                if _deferred_inline_prediction:
                    try:
                        ChatBILogUtil.info(f"[PERF] [inline-predict] Starting deferred inline prediction for record {self.record.id}")
                        
                        # 验证数据是否支持预测（需要时间字段+数值字段+足够行数）
                        data_array = result.get('data', [])
                        has_time_field = False
                        has_numeric_field = False
                        
                        if data_array and len(data_array) >= 3:
                            from datetime import datetime as _dt, date as _date
                            sample_rows = data_array[:min(3, len(data_array))]
                            for row in sample_rows:
                                for key, value in row.items():
                                    if isinstance(value, (_dt, _date)):
                                        has_time_field = True
                                    elif isinstance(value, str):
                                        if re.match(r'^\d{4}[-/]\d{1,2}([-/]\d{1,2})?', value) or \
                                           re.match(r'^\d{4}年\d{1,2}月(\d{1,2}日)?', value) or \
                                           re.match(r'^\d{1,2}[-/]\d{1,2}[-/]\d{4}', value):
                                            has_time_field = True
                                    if isinstance(value, (int, float)):
                                        has_numeric_field = True
                                    elif isinstance(value, str):
                                        try:
                                            float(value)
                                            has_numeric_field = True
                                        except (ValueError, TypeError):
                                            pass
                                if has_time_field and has_numeric_field:
                                    break
                        
                        can_predict = has_time_field and has_numeric_field and len(data_array) >= 3
                        
                        if can_predict:
                            yield 'data:' + orjson.dumps({'type': 'inline_predict_start'}).decode() + '\n\n'
                            
                            predict_res = self.generate_predict(_session, skip_rag=True)
                            full_predict_text = ''
                            _inline_predict_custom_prompts = []
                            for chunk in predict_res:
                                if chunk.get('type') == 'rag_results':
                                    _inline_predict_custom_prompts = chunk.get('data', {}).get('custom_prompts', [])
                                    yield 'data:' + orjson.dumps({
                                        'type': 'rag_results',
                                        'data': chunk.get('data')
                                    }).decode() + '\n\n'
                                elif chunk.get('type') == 'thinking_stage':
                                    yield 'data:' + orjson.dumps({
                                        'type': 'thinking_stage',
                                        'stage': chunk.get('stage'),
                                        'data': chunk.get('data')
                                    }).decode() + '\n\n'
                                elif chunk.get('type') == 'prediction_confidence':
                                    yield 'data:' + orjson.dumps({
                                        'type': 'prediction_confidence',
                                        'data': chunk.get('data')
                                    }).decode() + '\n\n'
                                else:
                                    content = chunk.get('content')
                                    if content:
                                        full_predict_text += content
                                    if content or chunk.get('reasoning_content'):
                                        yield 'data:' + orjson.dumps({
                                            'content': content,
                                            'reasoning_content': chunk.get('reasoning_content'),
                                            'type': 'inline-predict-result'
                                        }).decode() + '\n\n'
                            
                            _predict_data_saved = self.check_save_predict_data(session=_session, res=full_predict_text)
                            if _inline_predict_custom_prompts:
                                try:
                                    merge_rag_custom_prompts(_session, self.record.id, _inline_predict_custom_prompts)
                                except Exception as _e:
                                    ChatBILogUtil.error(f"[inline-predict] Failed to merge custom prompts: {_e}")
                            yield 'data:' + orjson.dumps({
                                'type': 'inline_predict_finish',
                                'predict_success': _predict_data_saved
                            }).decode() + '\n\n'
                            ChatBILogUtil.info(f"[PERF] [inline-predict] Deferred inline prediction completed, data_saved={_predict_data_saved}")
                        else:
                            # 数据不满足时间序列预测条件 → 降级为文本预测
                            reasons = []
                            _is_en_pred_fb = (self.chat_question.lang or '').lower().startswith('en')
                            if not has_time_field:
                                reasons.append('missing time/date fields' if _is_en_pred_fb else '缺少时间/日期字段')
                            if not has_numeric_field:
                                reasons.append('missing numeric fields' if _is_en_pred_fb else '缺少数值字段')
                            if len(data_array) < 3:
                                reasons.append(f'insufficient data rows (current {len(data_array)} rows, at least 3 required)' if _is_en_pred_fb else f'数据行数不足（当前{len(data_array)}行，至少需要3行）')
                            reason_text = ', '.join(reasons) if _is_en_pred_fb else '、'.join(reasons)
                            
                            ChatBILogUtil.info(f"[inline-predict] Time-series prediction unavailable ({reason_text}), falling back to text-based prediction")
                            
                            yield 'data:' + orjson.dumps({'type': 'inline_predict_start'}).decode() + '\n\n'
                            
                            try:
                                original_question = self.chat_question.question
                                if _is_en_pred_fb:
                                    self.chat_question.question = f"Perform predictive analysis based on the following data (Note: data {reason_text}, cannot generate precise time-series prediction charts, please provide text-based predictive analysis and trend judgment based on available data): {original_question}"
                                else:
                                    self.chat_question.question = f"基于以下数据进行预测性分析（注意：数据{reason_text}，无法生成精确的时间序列预测图表，请基于现有数据给出文字预测分析和趋势判断）：{original_question}"
                                
                                try:
                                    analysis_res = self.generate_analysis(_session, skip_rag=True)
                                    for chunk in analysis_res:
                                        if chunk.get('type') == 'rag_results':
                                            yield 'data:' + orjson.dumps({
                                                'type': 'rag_results',
                                                'data': chunk.get('data')
                                            }).decode() + '\n\n'
                                        elif chunk.get('type') == 'thinking_stage':
                                            yield 'data:' + orjson.dumps({
                                                'type': 'thinking_stage',
                                                'stage': chunk.get('stage'),
                                                'data': chunk.get('data')
                                            }).decode() + '\n\n'
                                        else:
                                            yield 'data:' + orjson.dumps({
                                                'content': chunk.get('content'),
                                                'reasoning_content': chunk.get('reasoning_content'),
                                                'type': 'inline-predict-result'
                                            }).decode() + '\n\n'
                                finally:
                                    self.chat_question.question = original_question
                                
                                yield 'data:' + orjson.dumps({
                                    'type': 'inline_predict_finish',
                                    'predict_success': False
                                }).decode() + '\n\n'
                                ChatBILogUtil.info(f"[inline-predict] Text-based prediction fallback completed")
                            except Exception as fallback_e:
                                ChatBILogUtil.error(f"[inline-predict] Text-based prediction fallback failed: {fallback_e}")
                                yield 'data:' + orjson.dumps({
                                    'type': 'inline_predict_unavailable',
                                    'reason': reason_text
                                }).decode() + '\n\n'
                    except Exception as e:
                        ChatBILogUtil.error(f"[inline-predict] Deferred inline prediction failed: {e}")
                        yield 'data:' + orjson.dumps({
                            'type': 'inline_predict_error',
                            'message': str(e)
                        }).decode() + '\n\n'
            else:
                # 生成图表图片（用于MCP/导出场景）
                try:
                    if chart['type'] != 'table':
                        yield '### generated chart picture\n\n'
                        image_url = request_picture(self.record.chat_id, self.record.id, chart,
                                                    format_json_data(result))
                        ChatBILogUtil.info(image_url)
                        if stream:
                            yield f'![{chart["type"]}]({image_url})'
                        else:
                            json_result['image_url'] = image_url
                except Exception as e:
                    if stream:
                        raise e

            if not stream:
                yield json_result

        except Exception as e:
            ChatBILogUtil.exception()
            error_msg: str
            if isinstance(e, SingleMessageError):
                # SingleMessageError 也需要脱敏，防止 check_save_sql/check_save_chart
                # 中的 traceback 字段泄露 LLM 原始响应和内部错误细节
                raw_msg = str(e)
                try:
                    parsed = orjson.loads(raw_msg)
                    if isinstance(parsed, dict):
                        if 'traceback' in parsed:
                            parsed['traceback'] = sanitize_error_message(parsed['traceback'])
                        if 'message' in parsed:
                            parsed['message'] = sanitize_error_message(parsed['message'])
                        error_msg = orjson.dumps(parsed).decode()
                    else:
                        error_msg = sanitize_error_message(raw_msg)
                except Exception:
                    error_msg = sanitize_error_message(raw_msg)
            elif isinstance(e, ChatBIDBConnectionError):
                _is_en_err = (self.chat_question.lang or '').lower().startswith('en')
                _conn_err_msg = 'Datasource connection error, please check connection configuration' if _is_en_err else '数据源连接异常，请检查连接配置'
                error_msg = orjson.dumps(
                    {'message': _conn_err_msg, 'type': 'db-connection-err'}).decode()
            elif isinstance(e, ChatBIDBError):
                # 返回结构化错误信息（error_type + suggestion），不暴露原始堆栈
                from common.utils.sql_error_handler import classify_sql_error
                error_info = classify_sql_error(str(e))
                error_msg = orjson.dumps({
                    'message': error_info['suggestion'],
                    'error_type': error_info['error_type'],
                    'suggestion': error_info['suggestion'],
                    'type': 'exec-sql-err'
                }).decode()
            else:
                error_msg = orjson.dumps({'message': sanitize_error_message(str(e))}).decode()
            if _session:
                self.save_error(session=_session, message=error_msg)
            if in_chat:
                try:
                    # 检查是否已经发送过provenance（正常流程中已发送则跳过）
                    _err_prov_stage = self.thinking_process.get_stage('provenance') if self.thinking_process else None
                    if not _err_prov_stage and self.ds:
                        from apps.chat.thinking.thinking_integration import record_provenance_stage
                        _err_provenance = []
                        _err_ds_type = (self.ds.type or '').lower()
                        if _err_ds_type == 'pdf':
                            if hasattr(self, '_rag_doc_chunks') and self._rag_doc_chunks:
                                for dc in self._rag_doc_chunks[:5]:
                                    _err_provenance.append({
                                        'source_type': 'pdf',
                                        'source_name': dc.get('source_name') or dc.get('source_file') or self.ds.name,
                                        'page_number': dc.get('page_number'),
                                        'section_title': dc.get('section_title'),
                                        'similarity': dc.get('similarity', 0),
                                        'text': (dc.get('text', '') or '')[:200],
                                    })
                            else:
                                _err_provenance.append({'source_type': 'pdf', 'source_name': self.ds.name})
                        elif _err_ds_type in ('excel', 'csv'):
                            _err_provenance.append({'source_type': _err_ds_type, 'source_name': self.ds.name})
                        else:
                            _err_provenance.append({
                                'source_type': 'database',
                                'source_name': self.ds.name,
                                'table_names': [t.name for t in self.ds.tables][:5] if hasattr(self.ds, 'tables') and self.ds.tables else [],
                            })
                        if _err_provenance:
                            record_provenance_stage(self.thinking_process, _err_provenance)
                            _err_prov_data = self.thinking_process.get_stage('provenance')
                            if _err_prov_data:
                                yield 'data:' + orjson.dumps({'type': 'thinking_stage', 'stage': 'provenance', 'data': _err_prov_data}).decode() + '\n\n'
                except Exception as _err_prov_e:
                    ChatBILogUtil.error(f"[error-handler] Failed to record provenance: {_err_prov_e}")
                
                yield 'data:' + orjson.dumps({'content': error_msg, 'type': 'error'}).decode() + '\n\n'
            else:
                if stream:
                    yield f'> &#x274c; **ERROR**\n\n> \n\n> {error_msg}。'
                else:
                    json_result['success'] = False
                    json_result['message'] = error_msg
                    yield json_result
        finally:
            # 保存思考过程逻辑提取到 _save_thinking_process_with_eval()
            try:
                if self.thinking_process and _session and not getattr(self, '_thinking_process_saved', False):
                    self._save_thinking_process_with_eval(_session)
            except Exception as e:
                ChatBILogUtil.error(f"Failed to save thinking process: {e}")
            
            # session_maker.remove() 移到 if _session 外部
            if _session:
                ChatBILogUtil.info(f"[PERF] ========== run_task FINISH, total elapsed: {time.time() - _task_start_time:.2f}s ==========")
                self.finish(_session)
            session_maker.remove()



    def _save_thinking_process_with_eval(self, _session: Session) -> None:
        """ 从run_task提取的思考过程保存+RAG评估逻辑

         性能优化：先快速保存思考过程（关键路径），再做 RAG 评估（非关键路径）。
        RAG 评估结果通过二次更新写入，避免阻塞用户响应。
        """
        thinking_data = self.thinking_process.to_dict()
        if self.dialogue_tracker:
            thinking_data['dialogue_state'] = self.dialogue_tracker.get_state_summary()

        # 性能优化：先保存思考过程（不含评估），让 finish 事件尽快发出
        import json as _json
        thinking_json = _json.dumps(thinking_data, ensure_ascii=False)
        save_thinking_process(
            session=_session,
            record_id=self.record.id,
            thinking_process=thinking_json
        )

        # RAG评估（非关键路径，失败不影响用户体验）
        try:
            from apps.chat.thinking.rag_evaluator import RAGEvaluator

            _eval_retrieval_items = []
            for t in (self._rag_terminologies or []):
                _eval_retrieval_items.append({
                    'similarity': t.get('similarity', 0),
                    'source_type': 'terminology'
                })
            for e in (self._rag_sql_examples or []):
                _eval_retrieval_items.append({
                    'similarity': e.get('similarity', 0),
                    'source_type': 'sql_example'
                })
            for dc in (getattr(self, '_rag_doc_chunks', None) or []):
                _eval_retrieval_items.append({
                    'similarity': dc.get('similarity', 0),
                    'source_type': 'doc_chunk'
                })

            if _eval_retrieval_items:
                retrieval_eval = RAGEvaluator.evaluate_retrieval(_eval_retrieval_items)
                thinking_data['rag_evaluation'] = {
                    'retrieval': {
                        'precision_at_k': retrieval_eval.precision_at_k,
                        'mrr': retrieval_eval.mrr,
                        'ndcg': retrieval_eval.ndcg,
                        'avg_similarity': retrieval_eval.avg_similarity,
                        'high_quality_ratio': retrieval_eval.high_quality_ratio,
                        'total_retrieved': retrieval_eval.total_retrieved,
                        'relevant_count': retrieval_eval.relevant_count
                    }
                }

                try:
                    from apps.chat.thinking.rag_evaluator import EvaluationReport
                    _report = EvaluationReport()
                    _report.retrieval = retrieval_eval
                    feedback = RAGEvaluator.generate_feedback_adjustments(_report)
                    if feedback.get('feedback_applied'):
                        self._rag_feedback_adjustments = feedback
                        thinking_data['rag_evaluation']['feedback_adjustments'] = {
                            'similarity_threshold': feedback.get('similarity_threshold'),
                            'max_terminologies': feedback.get('max_terminologies'),
                            'max_sql_examples': feedback.get('max_sql_examples'),
                            'rerank_weight_boost': feedback.get('rerank_weight_boost'),
                            'compression_budget_ratio': feedback.get('compression_budget_ratio'),
                            'reasons': feedback.get('feedback_reasons', []),
                        }
                except Exception as _fb_e:
                    ChatBILogUtil.error(f"RAG feedback generation failed: {_fb_e}")

                # 二次更新：将评估结果追加写入
                thinking_json_with_eval = _json.dumps(thinking_data, ensure_ascii=False)
                save_thinking_process(
                    session=_session,
                    record_id=self.record.id,
                    thinking_process=thinking_json_with_eval
                )
        except Exception as eval_e:
            ChatBILogUtil.error(f"RAG evaluation failed: {eval_e}")

    def run_recommend_questions_task_async(self):
        self.future = executor.submit(self.run_recommend_questions_task_cache)

    def run_recommend_questions_task_cache(self):
        for chunk in self.run_recommend_questions_task():
            self.chunk_list.append(chunk)

    def run_recommend_questions_task(self):
        _session = None
        try:
            ChatBILogUtil.info(f"开始执行推荐问题任务，record_id={self.record.id if self.record else 'None'}")
            _session = session_maker()
            res = self.generate_recommend_questions_task(_session)

            chunk_count = 0
            for chunk in res:
                chunk_count += 1
                if chunk.get('recommended_question'):
                    ChatBILogUtil.info(f"发送最终推荐问题: {chunk.get('recommended_question')[:100]}...")
                    yield 'data:' + orjson.dumps(
                        {'content': chunk.get('recommended_question'),
                         'type': 'recommended_question'}).decode() + '\n\n'
                elif chunk.get('layered_recommendations'):
                    # 前置推荐问题（三层推荐系统的pre层）
                    yield 'data:' + orjson.dumps(
                        {'type': 'layered_recommendations',
                         'data': chunk.get('layered_recommendations')}).decode() + '\n\n'
                else:
                    yield 'data:' + orjson.dumps(
                        {'content': chunk.get('content'), 'reasoning_content': chunk.get('reasoning_content'),
                         'type': 'recommended_question_result'}).decode() + '\n\n'
            
            ChatBILogUtil.info(f"推荐问题任务完成，共发送 {chunk_count} 个chunk，准备发送完成信号")
            
            # 发送完成信号，告知前端推荐问题生成已完成
            yield 'data:' + orjson.dumps({'type': 'recommend_questions_finish'}).decode() + '\n\n'
            
            ChatBILogUtil.info("推荐问题完成信号已发送")
            
        except Exception as e:
            ChatBILogUtil.exception()
            # 返回错误信息给前端
            error_msg = str(e)
            ChatBILogUtil.error(f"推荐问题生成错误: {error_msg}")
            # 保存错误状态到数据库，使用特殊格式标记为错误
            if _session and self.record and self.record.id:
                try:
                    error_data = orjson.dumps({'error': True, 'message': error_msg}).decode()
                    save_recommend_question_answer(_session, self.record.id, {'content': error_data})
                except Exception:
                    pass
            yield 'data:' + orjson.dumps({
                'code': 500,
                'msg': error_msg,
                'type': 'error'
            }).decode() + '\n\n'
        finally:
            session_maker.remove()

    def run_analysis_or_predict_task_async(self, session: Session, action_type: str, base_record: ChatRecord, rag_enabled: bool = True):
        self.set_record(save_analysis_predict_record(session, base_record, action_type))
        self.future = executor.submit(self.run_analysis_or_predict_task_cache, action_type, rag_enabled)

    def run_analysis_or_predict_task_cache(self, action_type: str, rag_enabled: bool = True):
        for chunk in self.run_analysis_or_predict_task(action_type, rag_enabled):
            self.chunk_list.append(chunk)

    def run_analysis_or_predict_task(self, action_type: str, rag_enabled: bool = True):
        _session = None
        try:
            _session = session_maker()
            yield 'data:' + orjson.dumps({'type': 'id', 'id': self.get_record().id}).decode() + '\n\n'

            # PDF数据源防护：PDF不支持数据分析和数据预测
            # 这是defense-in-depth层，generate_analysis/generate_predict内部也有PDF guard
            _ds_type_guard = (self.ds.type or '').lower() if self.ds else ''
            if _ds_type_guard == 'pdf':
                _action_label = '数据分析' if action_type == 'analysis' else '数据预测'
                _is_en_guard = (self.chat_question.lang or '').lower().startswith('en')
                if _is_en_guard:
                    _guard_msg = f"PDF documents do not support {action_type}. PDF is an unstructured document type that only supports document Q&A."
                else:
                    _guard_msg = f"PDF文档不支持{_action_label}功能。PDF属于非结构化文档类型，仅支持文档问答。"
                ChatBILogUtil.info(f"[run_analysis_or_predict_task] PDF guard: blocking {action_type} for PDF datasource")
                yield 'data:' + orjson.dumps({'content': _guard_msg, 'reasoning_content': '', 'type': f'{action_type}-result'}).decode() + '\n\n'
                yield 'data:' + orjson.dumps({'type': 'finish'}).decode() + '\n\n'
                return

            # 独立分析/预测记录需要保存intent字段
            try:
                intent_value = 'analysis' if action_type == 'analysis' else 'prediction'
                save_intent(_session, self.get_record().id, intent_value)
            except Exception as e:
                ChatBILogUtil.error(f"Failed to save intent for {action_type}: {e}")

            # 修复 T8 + QU-3：独立分析/预测路径也执行查询重写
            # 现在执行完整的查询重写，提取关键词和时间规范化，但保持用户明确选择的意图
            try:
                from apps.chat.thinking.thinking_integration import record_query_understanding_stage
                from apps.chat.thinking.query_rewriter import QueryRewriter
                _ds_type_ap = self.ds.type if self.ds else 'database'
                _rewrite_ap = QueryRewriter.rewrite(self.chat_question.question, ds_type=_ds_type_ap)
                record_query_understanding_stage(
                    self.thinking_process,
                    original_query=self.chat_question.question,
                    rewritten_query=_rewrite_ap['rewritten'],
                    intent=intent_value,  # 保持 analysis/prediction（用户明确选择的）
                    rewrite_applied=_rewrite_ap['rewrite_applied'],
                    extracted_keywords=_rewrite_ap.get('extracted_keywords', []),
                    dialogue_turn=1,
                    context_references=[],
                    ds_type=(self.ds.type or '').lower() if hasattr(self, 'ds') and self.ds else '',
                    ds_name=(self.ds.name or '') if hasattr(self, 'ds') and self.ds else '',
                    intent_keywords=_rewrite_ap.get('intent_keywords', []),
                )
                qu_stage = self.thinking_process.get_stage('query_understanding')
                if qu_stage:
                    yield 'data:' + orjson.dumps({
                        'type': 'thinking_stage',
                        'stage': 'query_understanding',
                        'data': qu_stage
                    }).decode() + '\n\n'
            except Exception as e:
                ChatBILogUtil.error(f"Failed to record query_understanding for {action_type}: {e}")

            if action_type == 'analysis':
                # generate analysis
                analysis_res = self.generate_analysis(_session)
                for chunk in analysis_res:
                    # 处理 RAG 检索结果
                    if chunk.get('type') == 'rag_results':
                        yield 'data:' + orjson.dumps({
                            'type': 'rag_results',
                            'data': chunk.get('data')
                        }).decode() + '\n\n'
                    # 处理思考过程阶段
                    elif chunk.get('type') == 'thinking_stage':
                        yield 'data:' + orjson.dumps({
                            'type': 'thinking_stage',
                            'stage': chunk.get('stage'),
                            'data': chunk.get('data')
                        }).decode() + '\n\n'
                    else:
                        # 处理分析结果
                        yield 'data:' + orjson.dumps(
                            {'content': chunk.get('content'), 'reasoning_content': chunk.get('reasoning_content'),
                             'type': 'analysis-result'}).decode() + '\n\n'
                yield 'data:' + orjson.dumps({'type': 'info', 'msg': 'analysis generated'}).decode() + '\n\n'

                # 后置推荐问题（独立分析路径）
                try:
                    from apps.chat.thinking.recommendation_engine import RecommendationEngine
                    _ds_type_rec = (self.ds.type or '').lower() if self.ds else 'database'
                    post_recs = RecommendationEngine.generate_post_recommendations(
                        question=self.chat_question.question,
                        chart_type='table',
                        intent='statistical_analysis',
                        ds_type=_ds_type_rec,
                        lang=self.chat_question.lang,
                    )
                    mid_recs = RecommendationEngine.generate_mid_recommendations(
                        question=self.chat_question.question,
                        intent='statistical_analysis',
                        ds_type=_ds_type_rec,
                        lang=self.chat_question.lang,
                    )
                    if post_recs or mid_recs:
                        yield 'data:' + orjson.dumps({
                            'type': 'layered_recommendations',
                            'data': {'mid': mid_recs, 'post': post_recs}
                        }).decode() + '\n\n'
                except Exception as e:
                    ChatBILogUtil.error(f"[standalone-analysis] Recommendation generation failed: {e}")

                yield 'data:' + orjson.dumps({'type': 'analysis_finish'}).decode() + '\n\n'

            elif action_type == 'predict':
                # generate predict
                analysis_res = self.generate_predict(_session)
                full_text = ''
                for chunk in analysis_res:
                    # 处理 RAG 检索结果
                    if chunk.get('type') == 'rag_results':
                        yield 'data:' + orjson.dumps({
                            'type': 'rag_results',
                            'data': chunk.get('data')
                        }).decode() + '\n\n'
                    # 处理思考过程阶段
                    elif chunk.get('type') == 'thinking_stage':
                        yield 'data:' + orjson.dumps({
                            'type': 'thinking_stage',
                            'stage': chunk.get('stage'),
                            'data': chunk.get('data')
                        }).decode() + '\n\n'
                    # 转发预测置信度事件到前端（之前被else分支吞掉）
                    elif chunk.get('type') == 'prediction_confidence':
                        yield 'data:' + orjson.dumps({
                            'type': 'prediction_confidence',
                            'data': chunk.get('data')
                        }).decode() + '\n\n'
                    else:
                        # 处理预测结果
                        content = chunk.get('content')
                        yield 'data:' + orjson.dumps(
                            {'content': content, 'reasoning_content': chunk.get('reasoning_content'),
                             'type': 'predict-result'}).decode() + '\n\n'
                        # 安全累积content，避免None值
                        if content:
                            full_text += content
                yield 'data:' + orjson.dumps({'type': 'info', 'msg': 'predict generated'}).decode() + '\n\n'

                _data = self.check_save_predict_data(session=_session, res=full_text)
                if _data:
                    yield 'data:' + orjson.dumps({'type': 'predict-success'}).decode() + '\n\n'
                else:
                    yield 'data:' + orjson.dumps({'type': 'predict-failed'}).decode() + '\n\n'

                # 后置推荐问题（独立预测路径）
                try:
                    from apps.chat.thinking.recommendation_engine import RecommendationEngine
                    _ds_type_rec = (self.ds.type or '').lower() if self.ds else 'database'
                    post_recs = RecommendationEngine.generate_post_recommendations(
                        question=self.chat_question.question,
                        chart_type='line',
                        intent='prediction',
                        ds_type=_ds_type_rec,
                        lang=self.chat_question.lang,
                    )
                    mid_recs = RecommendationEngine.generate_mid_recommendations(
                        question=self.chat_question.question,
                        intent='prediction',
                        ds_type=_ds_type_rec,
                        lang=self.chat_question.lang,
                    )
                    if post_recs or mid_recs:
                        yield 'data:' + orjson.dumps({
                            'type': 'layered_recommendations',
                            'data': {'mid': mid_recs, 'post': post_recs}
                        }).decode() + '\n\n'
                except Exception as e:
                    ChatBILogUtil.error(f"[standalone-predict] Recommendation generation failed: {e}")

                yield 'data:' + orjson.dumps({'type': 'predict_finish'}).decode() + '\n\n'

        except Exception as e:
            error_msg: str
            if isinstance(e, SingleMessageError):
                # SingleMessageError 也需要脱敏处理
                raw_msg = str(e)
                try:
                    parsed = orjson.loads(raw_msg)
                    if isinstance(parsed, dict):
                        if 'traceback' in parsed:
                            parsed['traceback'] = sanitize_error_message(parsed['traceback'])
                        if 'message' in parsed:
                            parsed['message'] = sanitize_error_message(parsed['message'])
                        error_msg = orjson.dumps(parsed).decode()
                    else:
                        error_msg = sanitize_error_message(raw_msg)
                except Exception:
                    error_msg = sanitize_error_message(raw_msg)
            else:
                error_msg = orjson.dumps({'message': sanitize_error_message(str(e))}).decode()
            if _session:
                self.save_error(session=_session, message=error_msg)
            yield 'data:' + orjson.dumps({'content': error_msg, 'type': 'error'}).decode() + '\n\n'
        finally:
            # 保存完整的思考过程（包含RAG评估）
            try:
                if self.thinking_process and _session and not getattr(self, '_thinking_process_saved', False):
                    thinking_data = self.thinking_process.to_dict()
                    if self.dialogue_tracker:
                        thinking_data['dialogue_state'] = self.dialogue_tracker.get_state_summary()
                    
                    # RAG评估：分析/预测路径
                    try:
                        from apps.chat.thinking.rag_evaluator import RAGEvaluator
                        _eval_retrieval_items = []
                        try:
                            for t in (self._rag_terminologies or []):
                                _eval_retrieval_items.append({
                                    'similarity': t.get('similarity', 0),
                                    'source_type': 'terminology'
                                })
                            for e in (self._rag_sql_examples or []):
                                _eval_retrieval_items.append({
                                    'similarity': e.get('similarity', 0),
                                    'source_type': 'sql_example'
                                })
                            # PDF数据源的主要检索源是文档片段(doc_chunks)，
                            for dc in (getattr(self, '_rag_doc_chunks', None) or []):
                                _eval_retrieval_items.append({
                                    'similarity': dc.get('similarity', 0),
                                    'source_type': 'doc_chunk'
                                })
                        except Exception:
                            pass
                        
                        if _eval_retrieval_items:
                            retrieval_eval = RAGEvaluator.evaluate_retrieval(_eval_retrieval_items)
                            thinking_data['rag_evaluation'] = {
                                'retrieval': {
                                    'precision_at_k': retrieval_eval.precision_at_k,
                                    'mrr': retrieval_eval.mrr,
                                    'ndcg': retrieval_eval.ndcg,
                                    'avg_similarity': retrieval_eval.avg_similarity,
                                    'high_quality_ratio': retrieval_eval.high_quality_ratio,
                                    'total_retrieved': retrieval_eval.total_retrieved,
                                    'relevant_count': retrieval_eval.relevant_count
                                }
                            }
                    except Exception as eval_e:
                        ChatBILogUtil.error(f"RAG evaluation failed for analysis/predict: {eval_e}")
                    
                    import json as _json
                    thinking_json = _json.dumps(thinking_data, ensure_ascii=False)
                    save_thinking_process(
                        session=_session,
                        record_id=self.record.id,
                        thinking_process=thinking_json
                    )
                    ChatBILogUtil.info(f"Saved thinking process for analysis/predict record {self.record.id}")
            except Exception as e:
                ChatBILogUtil.error(f"Failed to save thinking process for analysis/predict: {e}")
            
            # end
            if _session:
                self.finish(_session)
            session_maker.remove()

    def validate_history_ds(self, session: Session):
        _ds = self.ds
        if not self.current_assistant or self.current_assistant.type == 4:
            try:
                current_ds = session.get(CoreDatasource, _ds.id)
                if not current_ds:
                    raise SingleMessageError('chat.ds_is_invalid')
            except Exception as e:
                raise SingleMessageError("chat.ds_is_invalid")
        else:
            try:
                _ds_list: list[dict] = get_assistant_ds(session=session, llm_service=self)
                match_ds = any(item.get("id") == _ds.id for item in _ds_list)
                if not match_ds:
                    type = self.current_assistant.type
                    msg = f"[please check ds list and public ds list]" if type == 0 else f"[please check ds api]"
                    raise SingleMessageError(msg)
            except Exception as e:
                raise SingleMessageError(f"ds is invalid [{str(e)}]")


def execute_sql_with_db(db: SQLDatabase, sql: str) -> str:
    """Execute SQL query using SQLDatabase"""
    try:
        # Execute query
        result = db.run(sql)

        if not result:
            return "Query executed successfully but returned no results."

        # Format results
        return str(result)

    except Exception as e:
        error_msg = f"SQL execution failed: {str(e)}"
        ChatBILogUtil.exception(error_msg)
        raise RuntimeError(error_msg)


def request_picture(chat_id: int, record_id: int, chart: dict, data: dict):
    file_name = f'c_{chat_id}_r_{record_id}'

    columns = chart.get('columns') if chart.get('columns') else []
    x = None
    y = None
    series = None
    if chart.get('axis'):
        x = chart.get('axis').get('x')
        y = chart.get('axis').get('y')
        series = chart.get('axis').get('series')

    axis = []
    for v in columns:
        axis.append({'name': v.get('name'), 'value': v.get('value')})
    if x:
        axis.append({'name': x.get('name'), 'value': x.get('value'), 'type': 'x'})
    if y:
        axis.append({'name': y.get('name'), 'value': y.get('value'), 'type': 'y'})
    if series:
        axis.append({'name': series.get('name'), 'value': series.get('value'), 'type': 'series'})

    request_obj = {
        "path": os.path.join(settings.MCP_IMAGE_PATH, file_name),
        "type": chart['type'],
        "data": orjson.dumps(data.get('data') if data.get('data') else []).decode(),
        "axis": orjson.dumps(axis).decode(),
    }

    requests.post(url=settings.MCP_IMAGE_HOST, json=request_obj)

    request_path = urllib.parse.urljoin(settings.SERVER_IMAGE_HOST, f"{file_name}.png")

    return request_path


def get_token_usage(chunk: BaseMessageChunk, token_usage: dict = None):
    try:
        if chunk.usage_metadata:
            if token_usage is None:
                token_usage = {}
            token_usage['input_tokens'] = chunk.usage_metadata.get('input_tokens')
            token_usage['output_tokens'] = chunk.usage_metadata.get('output_tokens')
            token_usage['total_tokens'] = chunk.usage_metadata.get('total_tokens')
    except Exception:
        pass


def stream_with_retry(llm, messages, max_retries: int = 2, retry_delay: float = 1.0):
    """带重试机制的LLM流式调用"""
    # 可重试的异常关键词（瞬态错误）
    _retryable_keywords = ['timeout', 'rate limit', 'too many requests', '429', '503', '502',
                           'connection', 'reset', 'refused', 'temporarily']
    # 不可重试的错误关键词（永久性错误，重试无意义）
    _non_retryable_keywords = ['401', 'unauthorized', 'authentication', 'invalid api key',
                               '404', 'not found', 'model not found', 'does not exist',
                               '403', 'forbidden', 'permission denied',
                               'invalid request', 'bad request', '400',
                               'context length exceeded', 'maximum context length',
                               'content filter', 'content policy']
    
    ChatBILogUtil.info(
        f"[stream_with_retry] Starting LLM stream call "
        f"(max_retries={max_retries}, retry_delay={retry_delay}s, backoff=exponential)"
    )
    
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            # 追踪是否已产出chunk，已产出则不可重试
            has_yielded = False
            for chunk in llm.stream(messages):
                has_yielded = True
                yield chunk
            # 成功完成流式调用
            if attempt > 0:
                ChatBILogUtil.info(
                    f"[stream_with_retry] LLM stream succeeded on retry attempt {attempt + 1}/{max_retries + 1} "
                    f"(recovered after {attempt} failed attempt(s))"
                )
            return
        except Exception as e:
            last_error = e
            
            # 关键修复：如果已经yield了部分chunk，绝不能重试
            # 重试会导致前端收到 "部分旧响应 + 完整新响应" 的拼接乱码
            if has_yielded:
                ChatBILogUtil.error(
                    f"[stream_with_retry] LLM stream failed after yielding chunks "
                    f"(attempt {attempt + 1}/{max_retries + 1}), "
                    f"cannot retry to avoid garbled output: {e}"
                )
                raise
            
            error_str = str(e).lower()
            is_retryable = any(kw in error_str for kw in _retryable_keywords)
            
            # 显式检查不可重试错误（优先于retryable判断）
            is_non_retryable = any(kw in error_str for kw in _non_retryable_keywords)
            if is_non_retryable:
                ChatBILogUtil.error(
                    f"[stream_with_retry] Non-retryable permanent error on attempt {attempt + 1}/{max_retries + 1}, "
                    f"aborting immediately (no retry for auth/model/permission errors): {e}"
                )
                raise
            
            if not is_retryable:
                ChatBILogUtil.error(
                    f"[stream_with_retry] Non-retryable error on attempt {attempt + 1}/{max_retries + 1}, "
                    f"aborting: {e}"
                )
                raise
            
            if attempt >= max_retries:
                ChatBILogUtil.error(
                    f"[stream_with_retry] Max retries ({max_retries}) exhausted, "
                    f"all {max_retries + 1} attempts failed. Last error: {e}"
                )
                raise
            
            wait_time = retry_delay * (2 ** attempt)
            ChatBILogUtil.warning(
                f"[stream_with_retry] Retryable error on attempt {attempt + 1}/{max_retries + 1}, "
                f"retrying in {wait_time:.1f}s (exponential backoff): {e}"
            )
            time.sleep(wait_time)
    
    raise last_error


def process_stream(res: Iterator[BaseMessageChunk],
                   token_usage: Dict[str, Any] = None,
                   enable_tag_parsing: bool = settings.PARSE_REASONING_BLOCK_ENABLED,
                   start_tag: str = settings.DEFAULT_REASONING_CONTENT_START,
                   end_tag: str = settings.DEFAULT_REASONING_CONTENT_END
                   ):
    if token_usage is None:
        token_usage = {}
    in_thinking_block = False  # 标记是否在思考过程块中
    current_thinking = ''  # 当前收集的思考过程内容
    pending_start_tag = ''  # 用于缓存可能被截断的开始标签部分
    pending_end_tag = ''  # 用于缓存可能被截断的结束标签部分

    for chunk in res:
        # 性能优化：移除逐chunk日志（每个LLM chunk都写日志严重拖慢流式输出）
        reasoning_content_chunk = ''
        content = chunk.content
        output_content = ''  # 实际要输出的内容

        # 检查additional_kwargs中的reasoning_content
        if 'reasoning_content' in chunk.additional_kwargs:
            reasoning_content = chunk.additional_kwargs.get('reasoning_content', '')
            if reasoning_content is None:
                reasoning_content = ''

            # 累积additional_kwargs中的思考内容到current_thinking
            current_thinking += reasoning_content
            reasoning_content_chunk = reasoning_content

        # 只有当current_thinking不是空字符串时才跳过标签解析
        if not in_thinking_block and current_thinking.strip() != '':
            output_content = content  # 正常输出content
            yield {
                'content': output_content,
                'reasoning_content': reasoning_content_chunk
            }
            get_token_usage(chunk, token_usage)
            continue  # 跳过后续的标签解析逻辑

        # 如果没有有效的思考内容，并且启用了标签解析，才执行标签解析逻辑
        # 如果有缓存的开始标签部分，先拼接当前内容
        if pending_start_tag:
            content = pending_start_tag + content
            pending_start_tag = ''

        # 检查是否开始思考过程块（处理可能被截断的开始标签）
        if enable_tag_parsing and not in_thinking_block and start_tag:
            if start_tag in content:
                start_idx = content.index(start_tag)
                # 输出开始标签之前的文本内容（如果有）
                output_content += content[:start_idx]
                content = content[start_idx + len(start_tag):]  # 移除开始标签
                in_thinking_block = True
            else:
                # 检查是否可能有部分开始标签
                for i in range(1, len(start_tag)):
                    if content.endswith(start_tag[:i]):
                        pending_start_tag = start_tag[:i]
                        output_content += content[:-i]  # 输出部分标签之前的内容
                        content = ''
                        break

        # 处理思考块内容
        if enable_tag_parsing and in_thinking_block and end_tag:
            # 如果有缓存的部分结束标签，先拼接
            if pending_end_tag:
                content = pending_end_tag + content
                pending_end_tag = ''

            if end_tag in content:
                # 找到结束标签
                end_idx = content.index(end_tag)
                # 只将本chunk新增的思考内容加入reasoning_content_chunk
                # 思考内容再次输出，导致消费端拼接后出现重复文本
                reasoning_content_chunk += content[:end_idx]
                current_thinking += content[:end_idx]  # 收集思考内容（仅用于内部追踪）
                content = content[end_idx + len(end_tag):]  # 移除结束标签后的内容
                current_thinking = ''  # 重置当前思考内容
                in_thinking_block = False
                output_content += content  # 输出结束标签之后的内容
            else:
                # 检查末尾是否有部分结束标签被截断（如 "</thi" 在当前chunk末尾）
                found_partial = False
                for i in range(min(len(end_tag) - 1, len(content)), 0, -1):
                    if content.endswith(end_tag[:i]):
                        # 末尾匹配到部分结束标签，缓存起来等下个chunk拼接
                        pending_end_tag = content[-i:]
                        current_thinking += content[:-i]
                        reasoning_content_chunk += content[:-i]
                        found_partial = True
                        content = ''
                        break
                if not found_partial:
                    # 在遇到结束标签前，持续收集思考内容
                    current_thinking += content
                    reasoning_content_chunk += content
                    content = ''

        else:
            # 不在思考块中或标签解析未启用，正常输出
            output_content += content

        yield {
            'content': output_content,
            'reasoning_content': reasoning_content_chunk
        }
        get_token_usage(chunk, token_usage)


def get_lang_name(lang: str):
    """
    Convert language code to language name for LLM prompts.
    Supported languages: zh-CN (简体中文), en (English)
    """
    if not lang:
        return '简体中文'
    normalized = lang.lower().replace('_', '-')
    if normalized.startswith('en'):
        return 'English'
    # Default to Chinese for zh-CN and any other cases
    return '简体中文'
