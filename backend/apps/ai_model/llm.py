"""LLM（大语言模型）基类和通用接口定义"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Iterator, List, Optional, Union

from langchain.chat_models.base import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from common.utils.utils import ChatBILogUtil


class LLMResponse(BaseModel):
    """LLM响应模型"""
    content: str = Field(default="", description="响应内容")
    reasoning_content: Optional[str] = Field(default=None, description="推理过程内容")
    token_usage: Optional[Dict[str, int]] = Field(default=None, description="Token使用统计")
    model_name: Optional[str] = Field(default=None, description="模型名称")
    finish_reason: Optional[str] = Field(default=None, description="完成原因")


class LLMStreamChunk(BaseModel):
    """LLM流式响应块"""
    content: Optional[str] = Field(default=None, description="内容块")
    reasoning_content: Optional[str] = Field(default=None, description="推理内容块")
    is_final: bool = Field(default=False, description="是否为最后一块")
    token_usage: Optional[Dict[str, int]] = Field(default=None, description="Token使用统计")


class BaseLLMInterface(ABC):
    """LLM基础接口类"""
    
    @abstractmethod
    def invoke(self, messages: List[BaseMessage]) -> LLMResponse:
        """同步调用LLM"""
        pass
    
    @abstractmethod
    def stream(self, messages: List[BaseMessage]) -> Iterator[LLMStreamChunk]:
        """流式调用LLM"""
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """获取模型名称"""
        pass
    
    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        pass


class LLMWrapper(BaseLLMInterface):
    """
    LLM包装器
    
    将LangChain的BaseChatModel包装为统一的接口，
    提供额外的功能如日志记录、错误处理等。
    """
    
    def __init__(self, llm: BaseChatModel, model_name: str = "unknown"):
        """初始化LLM包装器"""
        self._llm = llm
        self._model_name = model_name
    
    @property
    def llm(self) -> BaseChatModel:
        """获取底层LLM实例"""
        return self._llm
    
    def invoke(self, messages: List[BaseMessage]) -> LLMResponse:
        """同步调用LLM"""
        try:
            response = self._llm.invoke(messages)
            
            # 提取响应内容
            content = response.content if hasattr(response, 'content') else str(response)
            
            # 提取token使用信息（如果有）
            token_usage = None
            if hasattr(response, 'response_metadata'):
                metadata = response.response_metadata
                if 'token_usage' in metadata:
                    token_usage = metadata['token_usage']
            
            return LLMResponse(
                content=content,
                token_usage=token_usage,
                model_name=self._model_name
            )
            
        except Exception as e:
            ChatBILogUtil.error(f"LLM invoke error: {e}")
            raise
    
    def stream(self, messages: List[BaseMessage]) -> Iterator[LLMStreamChunk]:
        """流式调用LLM"""
        try:
            for chunk in self._llm.stream(messages):
                content = None
                reasoning_content = None
                
                # 处理不同类型的chunk
                if hasattr(chunk, 'content') and chunk.content:
                    content = chunk.content
                
                # 处理推理内容（某些模型支持）
                if hasattr(chunk, 'additional_kwargs'):
                    reasoning = chunk.additional_kwargs.get('reasoning_content')
                    if reasoning:
                        reasoning_content = reasoning
                
                yield LLMStreamChunk(
                    content=content,
                    reasoning_content=reasoning_content,
                    is_final=False
                )
            
            # 发送最终块
            yield LLMStreamChunk(is_final=True)
            
        except Exception as e:
            ChatBILogUtil.error(f"LLM stream error: {e}")
            raise
    
    def get_model_name(self) -> str:
        """获取模型名称"""
        return self._model_name
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "model_name": self._model_name,
            "model_type": type(self._llm).__name__,
            "supports_streaming": True
        }


class MessageBuilder:
    """
    消息构建器
    
    提供便捷的方法来构建LLM消息列表
    """
    
    def __init__(self):
        self._messages: List[BaseMessage] = []
    
    def add_system(self, content: str) -> 'MessageBuilder':
        """添加系统消息"""
        self._messages.append(SystemMessage(content=content))
        return self
    
    def add_user(self, content: str) -> 'MessageBuilder':
        """添加用户消息"""
        self._messages.append(HumanMessage(content=content))
        return self
    
    def add_assistant(self, content: str) -> 'MessageBuilder':
        """添加助手消息"""
        self._messages.append(AIMessage(content=content))
        return self
    
    def add_message(self, message: BaseMessage) -> 'MessageBuilder':
        """添加任意消息"""
        self._messages.append(message)
        return self
    
    def build(self) -> List[BaseMessage]:
        """构建消息列表"""
        return self._messages.copy()
    
    def clear(self) -> 'MessageBuilder':
        """清空消息列表"""
        self._messages.clear()
        return self


class LLMUtils:
    """
    LLM工具类
    
    提供通用的LLM相关工具方法
    """
    
    @staticmethod
    def count_tokens_estimate(text: str) -> int:
        """估算文本的token数量"""
        # 简单估算：中文约1.5字符/token，英文约4字符/token
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        
        estimated_tokens = int(chinese_chars / 1.5 + other_chars / 4)
        return max(1, estimated_tokens)
    
    @staticmethod
    def truncate_messages(
        messages: List[BaseMessage],
        max_tokens: int = 4000,
        keep_system: bool = True
    ) -> List[BaseMessage]:
        """截断消息列表以适应token限制"""
        if not messages:
            return []
        
        result = []
        current_tokens = 0
        
        # 首先处理系统消息
        system_messages = [m for m in messages if isinstance(m, SystemMessage)]
        other_messages = [m for m in messages if not isinstance(m, SystemMessage)]
        
        if keep_system and system_messages:
            for msg in system_messages:
                tokens = LLMUtils.count_tokens_estimate(msg.content)
                if current_tokens + tokens <= max_tokens:
                    result.append(msg)
                    current_tokens += tokens
        
        # 从最新的消息开始添加
        for msg in reversed(other_messages):
            tokens = LLMUtils.count_tokens_estimate(msg.content)
            if current_tokens + tokens <= max_tokens:
                result.insert(len(system_messages) if keep_system else 0, msg)
                current_tokens += tokens
            else:
                break
        
        return result
    
    @staticmethod
    def format_error_message(error: Exception) -> str:
        """格式化错误消息"""
        error_type = type(error).__name__
        error_msg = str(error)
        
        # 处理常见错误类型
        if "rate limit" in error_msg.lower():
            return "请求频率过高，请稍后重试"
        elif "timeout" in error_msg.lower():
            return "请求超时，请检查网络连接"
        elif "api key" in error_msg.lower():
            return "API密钥无效或已过期"
        elif "connection" in error_msg.lower():
            return "无法连接到AI服务，请检查网络"
        else:
            return f"AI服务错误: {error_msg[:100]}"


# 导出的类和函数
__all__ = [
    'LLMResponse',
    'LLMStreamChunk',
    'BaseLLMInterface',
    'LLMWrapper',
    'MessageBuilder',
    'LLMUtils'
]
