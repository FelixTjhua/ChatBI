import copy
import json
import threading
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Type

from langchain.chat_models.base import BaseChatModel
from pydantic import BaseModel
from sqlmodel import Session, select

from apps.ai_model.openai.llm import BaseChatOpenAI
from apps.system.models.system_model import AiModelDetail
from common.core.db import engine
from common.utils.crypto import chatbi_decrypt
from common.utils.utils import prepare_model_arg, ChatBILogUtil
from langchain_community.llms import VLLMOpenAI
from langchain_openai import AzureChatOpenAI


class LLMConfig(BaseModel):
    """Base configuration class for large language models"""
    model_id: Optional[int] = None
    model_type: str  # Model type: openai/tongyi/vllm etc.
    model_name: str  # Specific model name
    api_key: Optional[str] = None
    api_base_url: Optional[str] = None
    additional_params: Dict[str, Any] = {}

    def _stable_cache_key(self) -> str:
        """生成稳定的缓存键字符串，避免 hash() 碰撞和嵌套 dict 不可哈希问题。
        
                 1. 使用 json.dumps 序列化 additional_params，安全处理任意嵌套结构
        2. 返回字符串而非 int，消除 hash() 碰撞导致缓存返回错误 LLM 实例的风险
        """
        try:
            params_str = json.dumps(self.additional_params, sort_keys=True, default=str)
        except (TypeError, ValueError):
            params_str = str(self.additional_params)
        return f"{self.model_id}|{self.model_type}|{self.model_name}|{self.api_key}|{self.api_base_url}|{params_str}"

    def __hash__(self):
        return hash(self._stable_cache_key())

    def __eq__(self, other):
        if not isinstance(other, LLMConfig):
            return False
        return (self.model_id == other.model_id
                and self.model_type == other.model_type
                and self.model_name == other.model_name
                and self.api_key == other.api_key
                and self.api_base_url == other.api_base_url
                and self.additional_params == other.additional_params)


class BaseLLM(ABC):
    """Abstract base class for large language models"""

    def __init__(self, config: LLMConfig):
        self.config = config
        # deep copy additional_params，防止 _init_llm 中的 pop/修改
        # 影响到 lru_cache 缓存的原始 config 对象
        self._params = copy.deepcopy(config.additional_params)
        self._llm = self._init_llm()

    @abstractmethod
    def _init_llm(self) -> BaseChatModel:
        """Initialize specific large language model instance"""
        pass

    @property
    def llm(self) -> BaseChatModel:
        """Return the langchain LLM instance"""
        return self._llm


class OpenAIvLLM(BaseLLM):
    def _init_llm(self) -> VLLMOpenAI:
        params = self._params  # 使用 deep copy 的副本
        return VLLMOpenAI(
            openai_api_key=self.config.api_key or 'Empty',
            openai_api_base=self.config.api_base_url,
            model_name=self.config.model_name,
            streaming=True,
            **params,
        )


class OpenAIAzureLLM(BaseLLM):
    def _init_llm(self) -> AzureChatOpenAI:
        params = self._params  # 使用 deep copy 的副本
        # 使用 pop 的默认值处理空字符串，避免空字符串传给 API
        api_version = params.pop("api_version", None) or None
        deployment_name = params.pop("deployment_name", None) or None
        return AzureChatOpenAI(
            azure_endpoint=self.config.api_base_url,
            api_key=self.config.api_key or 'Empty',
            model_name=self.config.model_name,
            api_version=api_version,
            deployment_name=deployment_name,
            streaming=True,
            **params,
        )


class OpenAILLM(BaseLLM):
    def _init_llm(self) -> BaseChatModel:
        params = self._params  # 使用 deep copy 的副本
        # 检查是否需要强制JSON模式
        force_json = params.pop('force_json_mode', False)

        # 如果强制JSON模式，添加response_format参数
        if force_json:
            # 确保temperature不要太高（避免创造性输出）
            if 'temperature' not in params:
                params['temperature'] = 0.1
            else:
                # 转换temperature为float（可能是字符串）
                try:
                    temp_value = float(params['temperature'])
                    if temp_value > 0.3:
                        ChatBILogUtil.warning(f"Temperature {temp_value} is too high for JSON mode, setting to 0.3")
                        params['temperature'] = 0.3
                except (ValueError, TypeError):
                    ChatBILogUtil.warning(f"Invalid temperature value, setting to 0.1 for JSON mode")
                    params['temperature'] = 0.1

            # 添加JSON模式配置（OpenAI API支持）
            params['response_format'] = {"type": "json_object"}
            ChatBILogUtil.info("JSON mode enabled for SQL generation")

        llm = BaseChatOpenAI(
            model=self.config.model_name,
            api_key=self.config.api_key or 'Empty',
            base_url=self.config.api_base_url,
            stream_usage=True,
            **params,
        )

        llm.force_json_mode = force_json
        return llm

    def generate(self, prompt: str) -> str:
        return self.llm.invoke(prompt)


class ChatGLMLLM(BaseLLM):
    def _init_llm(self) -> BaseChatModel:
        params = self._params  # 使用 deep copy 的副本
        api_base = self.config.api_base_url or 'https://open.bigmodel.cn/api/paas/v4'
        llm = BaseChatOpenAI(
            model=self.config.model_name,
            api_key=self.config.api_key or 'Empty',
            base_url=api_base,
            stream_usage=True,
            **params,
        )
        return llm


class LLMFactory:
    """Large Language Model Factory Class"""

    _llm_types: Dict[str, Type[BaseLLM]] = {
        "openai": OpenAILLM,
        "tongyi": OpenAILLM,
        "vllm": OpenAIvLLM,
        "azure": OpenAIAzureLLM,
        "chatglm": ChatGLMLLM,
    }

    # 使用 OrderedDict 实现真正的 LRU 缓存
    # 原 dict + next(iter()) 只是 FIFO，不会将命中的条目移到末尾
    from collections import OrderedDict as _LLMOrderedDict
    _cache: _LLMOrderedDict = _LLMOrderedDict()
    _cache_lock = threading.Lock()
    _CACHE_MAX_SIZE = 32

    @classmethod
    def create_llm(cls, config: LLMConfig) -> BaseLLM:
        cache_key = config._stable_cache_key()
        with cls._cache_lock:
            if cache_key in cls._cache:
                # 命中时移到末尾，维护 LRU 顺序
                cls._cache.move_to_end(cache_key)
                return cls._cache[cache_key]

        # 在锁外创建实例（避免阻塞其他线程）
        llm_class = cls._llm_types.get(config.model_type)
        if not llm_class:
            raise ValueError(f"Unsupported LLM type: {config.model_type}")
        instance = llm_class(config)

        with cls._cache_lock:
            # double-check
            if cache_key in cls._cache:
                return cls._cache[cache_key]
            # LRU 淘汰
            if len(cls._cache) >= cls._CACHE_MAX_SIZE:
                cls._cache.popitem(last=False)  # O(1) 淘汰最旧项
            cls._cache[cache_key] = instance
        return instance

    @classmethod
    def register_llm(cls, model_type: str, llm_class: Type[BaseLLM]):
        """Register new model type"""
        cls._llm_types[model_type] = llm_class

    @classmethod
    def clear_cache(cls):
        """清空 LLM 缓存（模型配置变更时调用）"""
        with cls._cache_lock:
            cls._cache.clear()


async def get_default_config() -> LLMConfig:
    # async 函数中使用 asyncio.to_thread 包装同步 DB 操作，
    import asyncio

    def _load_config_sync() -> LLMConfig:
        with Session(engine) as session:
            db_model = session.exec(
                select(AiModelDetail).where(AiModelDetail.default_model == True)
            ).first()
            if not db_model:
                raise Exception("The system default model has not been set")

            additional_params = {}
            if db_model.config:
                try:
                    config_raw = json.loads(db_model.config)
                    additional_params = {item["key"]: prepare_model_arg(item.get('val')) for item in config_raw if "key" in item and "val" in item}
                except Exception as e:
                    # 记录配置解析错误而非静默忽略
                    ChatBILogUtil.warning(f"Failed to parse model config JSON: {e}")

            return db_model, additional_params

    db_model, additional_params = await asyncio.to_thread(_load_config_sync)

    # 更可靠的加密检测与解密逻辑
    _raw_domain = db_model.api_domain
    _raw_key = db_model.api_key
    if _raw_domain and not _raw_domain.startswith("http://") and not _raw_domain.startswith("https://"):
        db_model.api_domain = await chatbi_decrypt(_raw_domain)
    if _raw_key and not _raw_key.startswith("sk-") and len(_raw_key) > 20:
        try:
            decrypted_key = await chatbi_decrypt(_raw_key)
            if decrypted_key and decrypted_key != _raw_key:
                db_model.api_key = decrypted_key
        except Exception as e:
            # 记录解密失败而非静默忽略
            ChatBILogUtil.warning(f"API key decryption failed, using raw key: {e}")
    if db_model.api_domain and not db_model.api_domain.startswith("http"):
        raise Exception(f"Invalid API domain after decryption: {db_model.api_domain[:20]}...")

    return LLMConfig(
        model_id=db_model.id,
        model_type="openai" if db_model.protocol == 1 else "vllm",
        model_name=db_model.base_model,
        api_key=db_model.api_key,
        api_base_url=db_model.api_domain,
        additional_params=additional_params,
    )
