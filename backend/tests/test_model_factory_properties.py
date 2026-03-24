"""Property-based tests for LLMFactory unified interface."""
import sys
import os
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Ensure the backend root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ---------------------------------------------------------------------------
_heavy_modules = [
    "langchain", "langchain.chat_models", "langchain.chat_models.base",
    "langchain_community", "langchain_community.llms",
    "langchain_core", "langchain_core.messages", "langchain_core.embeddings",
    "langchain_openai",
    "langchain_huggingface",
    "sqlmodel",
    "apps.ai_model.openai", "apps.ai_model.openai.llm",
    "apps.system.models", "apps.system.models.system_model",
    "common.core.db",
    "common.utils.crypto",
    "common.utils.utils",
    "common.core.config",
]

# Create mock modules with proper class stubs
for mod_name in _heavy_modules:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

# Set up BaseChatModel as a proper class for isinstance checks
class _MockBaseChatModel:
    pass

sys.modules["langchain.chat_models.base"].BaseChatModel = _MockBaseChatModel
sys.modules["langchain_openai"].AzureChatOpenAI = type("AzureChatOpenAI", (_MockBaseChatModel,), {
    "__init__": lambda self, **kwargs: None
})
sys.modules["langchain_community.llms"].VLLMOpenAI = type("VLLMOpenAI", (_MockBaseChatModel,), {
    "__init__": lambda self, **kwargs: None
})

# Mock BaseChatOpenAI to return a _MockBaseChatModel-compatible instance
_mock_base_chat_openai_cls = type("BaseChatOpenAI", (_MockBaseChatModel,), {
    "__init__": lambda self, **kwargs: None,
})
sys.modules["apps.ai_model.openai.llm"].BaseChatOpenAI = _mock_base_chat_openai_cls

# Mock pydantic BaseModel for LLMConfig
from pydantic import BaseModel

# Mock ChatBILogUtil
mock_log_util = MagicMock()
sys.modules["common.utils.utils"].ChatBILogUtil = mock_log_util
sys.modules["common.utils.utils"].prepare_model_arg = lambda x: x

# Now import the module under test
from apps.ai_model.model_factory import LLMFactory, LLMConfig, BaseLLM


REGISTERED_MODEL_TYPES = ["openai", "tongyi", "vllm", "azure", "chatglm"]

_model_type = st.sampled_from(REGISTERED_MODEL_TYPES)

_model_name = st.sampled_from([
    "gpt-4o", "gpt-4o-mini", "deepseek-chat",
    "qwen-plus", "qwen-max", "glm-4", "glm-3-turbo",
    "llama3", "mistral",
])

_api_key = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N')),
    min_size=8, max_size=32
)

_api_base_url = st.sampled_from([
    "https://api.openai.com/v1",
    "https://api.deepseek.com",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "https://open.bigmodel.cn/api/paas/v4",
    "http://localhost:11434/v1",
    "https://my-azure.openai.azure.com",
])

# For azure, we need api_version and deployment_name
_azure_params = st.fixed_dictionaries({
    "api_version": st.just("2024-02-01"),
    "deployment_name": st.just("my-deployment"),
})


# ---------------------------------------------------------------------------

class TestModelFactoryProperty20:
    """
    **Validates: Requirements 8.2**

    Property 20: 模型工厂统一接口
    For any registered model type (openai, tongyi, vllm, azure, chatglm),
    LLMFactory.create_llm() should return a BaseLLM instance with an llm
    property returning BaseChatModel.
    """

    def setup_method(self):
        """Clear LLM cache before each test method to avoid stale entries."""
        LLMFactory.clear_cache()

    @given(
        model_type=_model_type,
        model_name=_model_name,
        api_key=_api_key,
        api_base_url=_api_base_url,
    )
    @settings(max_examples=100)
    def test_factory_returns_base_llm_instance(self, model_type, model_name, api_key, api_base_url):
        """LLMFactory.create_llm() should return a BaseLLM instance for any registered type."""
        LLMFactory.clear_cache()

        additional_params = {}
        if model_type == "azure":
            additional_params = {"api_version": "2024-02-01", "deployment_name": "test-deploy"}

        config = LLMConfig(
            model_type=model_type,
            model_name=model_name,
            api_key=api_key,
            api_base_url=api_base_url,
            additional_params=additional_params,
        )

        result = LLMFactory.create_llm(config)

        assert isinstance(result, BaseLLM), (
            f"create_llm({model_type}) should return BaseLLM instance, "
            f"got {type(result).__name__}"
        )

    @given(
        model_type=_model_type,
        model_name=_model_name,
        api_key=_api_key,
        api_base_url=_api_base_url,
    )
    @settings(max_examples=100)
    def test_factory_instance_has_llm_property(self, model_type, model_name, api_key, api_base_url):
        """The returned BaseLLM instance should have an llm property."""
        LLMFactory.clear_cache()

        additional_params = {}
        if model_type == "azure":
            additional_params = {"api_version": "2024-02-01", "deployment_name": "test-deploy"}

        config = LLMConfig(
            model_type=model_type,
            model_name=model_name,
            api_key=api_key,
            api_base_url=api_base_url,
            additional_params=additional_params,
        )

        result = LLMFactory.create_llm(config)

        assert hasattr(result, 'llm'), (
            f"BaseLLM instance for type '{model_type}' should have 'llm' property"
        )
        # The llm property should return a BaseChatModel-compatible instance
        llm_instance = result.llm
        assert llm_instance is not None, (
            f"llm property for type '{model_type}' should not be None"
        )

    @given(
        model_type=st.text(min_size=1, max_size=20).filter(
            lambda t: t not in REGISTERED_MODEL_TYPES
        ),
    )
    @settings(max_examples=100)
    def test_factory_rejects_unregistered_type(self, model_type):
        """LLMFactory.create_llm() should raise ValueError for unregistered model types."""
        LLMFactory.clear_cache()

        config = LLMConfig(
            model_type=model_type,
            model_name="test-model",
            api_key="test-key",
            api_base_url="https://api.example.com/v1",
        )

        with pytest.raises(ValueError, match="Unsupported LLM type"):
            LLMFactory.create_llm(config)

    def test_all_registered_types_have_adapters(self):
        """Every type in _llm_types should map to a valid BaseLLM subclass."""
        for model_type, llm_class in LLMFactory._llm_types.items():
            assert issubclass(llm_class, BaseLLM), (
                f"Adapter for '{model_type}' ({llm_class.__name__}) "
                f"should be a subclass of BaseLLM"
            )

    def test_registered_types_match_requirements(self):
        """The factory should support all 5 required model types."""
        required_types = {"openai", "tongyi", "vllm", "azure", "chatglm"}
        registered_types = set(LLMFactory._llm_types.keys())

        missing = required_types - registered_types
        assert not missing, (
            f"Missing required model types: {missing}"
        )

    @given(model_type=_model_type)
    @settings(max_examples=100)
    def test_factory_config_preserved(self, model_type):
        """The created LLM instance should preserve the original config."""
        LLMFactory.clear_cache()

        additional_params = {}
        if model_type == "azure":
            additional_params = {"api_version": "2024-02-01", "deployment_name": "test-deploy"}

        config = LLMConfig(
            model_type=model_type,
            model_name="test-model",
            api_key="test-key-12345",
            api_base_url="https://api.example.com/v1",
            additional_params=additional_params,
        )

        result = LLMFactory.create_llm(config)

        assert result.config.model_type == model_type, (
            f"Config model_type should be preserved: expected '{model_type}', "
            f"got '{result.config.model_type}'"
        )
        assert result.config.model_name == "test-model", (
            "Config model_name should be preserved"
        )
