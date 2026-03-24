"""错误消息脱敏工具 — 过滤内部实现细节，防止敏感信息泄露到客户端。"""

import re
from typing import Optional


# 数据库连接字符串模式
_CONNECTION_STRING_PATTERN = re.compile(
    r'(postgresql|mysql|oracle|mssql|sqlite|mongodb|redis|amqp)'
    r'(\+\w+)?://'
    r'[^\s,\'"}\]]*',
    re.IGNORECASE
)

# 文件系统路径模式 (Unix + Windows)
_FILE_PATH_PATTERN = re.compile(
    r'(?:'
    r'/(?:home|app|usr|var|etc|tmp|opt|srv|root|proc|sys|mnt|media|Users|Library)'
    r'(?:/[^\s:,\'"}\]]+)+'
    r'|'
    r'[A-Za-z]:\\\\(?:[^\s:,\'"}\]]+\\\\?)+'
    r')',
    re.IGNORECASE
)

# Python traceback 行模式
_TRACEBACK_PATTERN = re.compile(
    r'(?:'
    r'Traceback \(most recent call last\):.*?(?=\n\S|\Z)'
    r'|'
    r'File "[^"]*", line \d+.*'
    r')',
    re.DOTALL
)

# 内部模块/类名模式 (如 apps.chat.task.llm.LLMService)
_INTERNAL_MODULE_PATTERN = re.compile(
    r'\b(?:apps|common|backend)\.'
    r'(?:[a-z_]+\.){1,6}'
    r'[A-Za-z_]+\b'
)

# API 密钥模式 (OpenAI sk-..., Bearer tokens, key=value 等)
_API_KEY_PATTERN = re.compile(
    r'(?:'
    r'sk-[A-Za-z0-9]{20,}'                          # OpenAI API keys
    r'|'
    r'Bearer\s+[A-Za-z0-9\-._~+/]+=*'              # Bearer tokens
    r'|'
    r'(?:api[_-]?key|apikey|secret[_-]?key|access[_-]?token)'
    r'\s*[=:]\s*["\']?[A-Za-z0-9\-._~+/]{8,}["\']?' # key=value patterns
    r')',
    re.IGNORECASE
)

_GENERIC_ERROR_MSG = "服务内部错误，请稍后重试"
_REDACTED = "[REDACTED]"


def sanitize_error_message(
    message: Optional[str],
    fallback: str = _GENERIC_ERROR_MSG,
) -> str:
    """对错误消息进行脱敏处理，移除敏感的内部实现细节。"""
    if not message:
        return fallback

    result = message

    # 1. 移除数据库连接字符串
    result = _CONNECTION_STRING_PATTERN.sub(_REDACTED, result)

    # 2. 移除文件系统路径
    result = _FILE_PATH_PATTERN.sub(_REDACTED, result)

    # 3. 移除 traceback 信息
    result = _TRACEBACK_PATTERN.sub(_REDACTED, result)

    # 4. 移除内部模块/类名引用
    result = _INTERNAL_MODULE_PATTERN.sub(_REDACTED, result)

    # 5. 移除 API 密钥
    result = _API_KEY_PATTERN.sub(_REDACTED, result)

    # 如果脱敏后只剩下 [REDACTED] 和空白，返回兜底消息
    stripped = result.replace(_REDACTED, "").strip()
    if not stripped or stripped in ("{}", "''", '""'):
        return fallback

    return result


# ============  统一LLM错误分类与处理 ============

class LLMErrorCategory:
    """LLM错误分类枚举"""
    AUTH = 'auth'              # 认证错误 (401/403)
    NOT_FOUND = 'not_found'    # 资源不存在 (404)
    RATE_LIMIT = 'rate_limit'  # 速率限制 (429)
    CONTEXT_OVERFLOW = 'context_overflow'  # 上下文超长
    INVALID_REQUEST = 'invalid_request'    # 无效请求
    SERVER_ERROR = 'server_error'          # 服务端错误 (500+)
    NETWORK = 'network'        # 网络错误
    TIMEOUT = 'timeout'        # 超时
    UNKNOWN = 'unknown'        # 未知错误


def classify_llm_error(error: Exception) -> dict:
    """统一分类LLM调用错误"""
    error_str = str(error).lower()
    
    # 认证错误
    if any(kw in error_str for kw in ['401', '403', 'unauthorized', 'forbidden', 'invalid api key']):
        return {
            'category': LLMErrorCategory.AUTH,
            'retryable': False,
            'user_message': 'AI模型认证失败，请检查API密钥配置',
            'log_message': f'LLM auth error: {error}'
        }
    
    # 资源不存在
    if any(kw in error_str for kw in ['404', 'not found', 'model not found']):
        return {
            'category': LLMErrorCategory.NOT_FOUND,
            'retryable': False,
            'user_message': 'AI模型不可用，请检查模型配置',
            'log_message': f'LLM not found: {error}'
        }
    
    # 速率限制
    if any(kw in error_str for kw in ['429', 'rate limit', 'too many requests', 'quota']):
        return {
            'category': LLMErrorCategory.RATE_LIMIT,
            'retryable': True,
            'user_message': '请求过于频繁，请稍后重试',
            'log_message': f'LLM rate limited: {error}'
        }
    
    # 上下文超长
    if any(kw in error_str for kw in ['context length', 'token limit', 'maximum context', 'too long']):
        return {
            'category': LLMErrorCategory.CONTEXT_OVERFLOW,
            'retryable': False,
            'user_message': '输入内容过长，请简化问题后重试',
            'log_message': f'LLM context overflow: {error}'
        }
    
    # 无效请求
    if any(kw in error_str for kw in ['400', 'invalid request', 'bad request', 'invalid_request']):
        return {
            'category': LLMErrorCategory.INVALID_REQUEST,
            'retryable': False,
            'user_message': '请求格式错误，请重试',
            'log_message': f'LLM invalid request: {error}'
        }
    
    # 超时
    if any(kw in error_str for kw in ['timeout', 'timed out', 'deadline']):
        return {
            'category': LLMErrorCategory.TIMEOUT,
            'retryable': True,
            'user_message': 'AI模型响应超时，请稍后重试',
            'log_message': f'LLM timeout: {error}'
        }
    
    # 网络错误
    if any(kw in error_str for kw in ['connection', 'network', 'dns', 'refused', 'reset']):
        return {
            'category': LLMErrorCategory.NETWORK,
            'retryable': True,
            'user_message': '网络连接异常，请检查网络后重试',
            'log_message': f'LLM network error: {error}'
        }
    
    # 服务端错误
    if any(kw in error_str for kw in ['500', '502', '503', '504', 'internal server', 'service unavailable']):
        return {
            'category': LLMErrorCategory.SERVER_ERROR,
            'retryable': True,
            'user_message': 'AI服务暂时不可用，请稍后重试',
            'log_message': f'LLM server error: {error}'
        }
    
    # 未知错误
    return {
        'category': LLMErrorCategory.UNKNOWN,
        'retryable': False,
        'user_message': sanitize_error_message(str(error)),
        'log_message': f'LLM unknown error: {error}'
    }
