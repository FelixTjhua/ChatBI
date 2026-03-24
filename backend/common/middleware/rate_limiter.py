"""简单的API请求频率限制中间件"""
import time
from collections import defaultdict
from typing import Dict, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from common.utils.utils import ChatBILogUtil


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    基于IP+用户的请求频率限制
    
    配置：
    - LLM相关端点（/chat/question, /chat/recommend_questions）: 10次/分钟
    - 普通API端点: 60次/分钟
    """
    
    # LLM密集型端点（消耗API配额的）
    LLM_ENDPOINTS = {
        '/chat/question',
        '/chat/recommend_questions',
    }
    
    def __init__(self, app, llm_rate: int = 10, api_rate: int = 60, window: int = 60):
        super().__init__(app)
        self.llm_rate = llm_rate      # LLM端点每窗口最大请求数
        self.api_rate = api_rate      # 普通端点每窗口最大请求数
        self.window = window          # 时间窗口（秒）
        # {client_key: (request_count, window_start_time)}
        self._llm_counters: Dict[str, Tuple[int, float]] = defaultdict(lambda: (0, 0.0))
        self._api_counters: Dict[str, Tuple[int, float]] = defaultdict(lambda: (0, 0.0))
        # 请求计数器，每 100 次请求触发一次清理
        self._request_count = 0
        self._cleanup_interval = 100

    def _get_client_key(self, request: Request) -> str:
        """获取客户端标识（真实 IP）"""
        # 优先使用 X-Real-IP（Nginx 通常设置此头为真实客户端 IP）
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip.strip()
        # 其次使用 X-Forwarded-For 的第一个 IP（最左侧为原始客户端）
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        # 兜底使用直连 IP
        client_ip = request.client.host if request.client else 'unknown'
        return client_ip
    
    def _is_rate_limited(self, key: str, is_llm: bool) -> bool:
        """检查是否超过频率限制"""
        now = time.time()
        counters = self._llm_counters if is_llm else self._api_counters
        max_rate = self.llm_rate if is_llm else self.api_rate
        
        count, window_start = counters[key]
        
        # 窗口过期，重置计数器
        if now - window_start > self.window:
            counters[key] = (1, now)
            return False
        
        # 检查是否超限
        if count >= max_rate:
            return True
        
        # 递增计数器
        counters[key] = (count + 1, window_start)
        return False
    
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        
        # 只对POST请求做频率限制（GET请求通常是读取操作）
        if request.method != 'POST':
            return await call_next(request)
        
        # 定期清理过期计数器，防止内存泄漏
        self._request_count += 1
        if self._request_count >= self._cleanup_interval:
            self._request_count = 0
            self.cleanup()
        
        # 判断是否为LLM密集型端点
        is_llm = any(path.endswith(ep) or ep in path for ep in self.LLM_ENDPOINTS)
        
        client_key = self._get_client_key(request)
        
        if self._is_rate_limited(client_key, is_llm):
            rate_type = "LLM API" if is_llm else "API"
            max_rate = self.llm_rate if is_llm else self.api_rate
            ChatBILogUtil.warning(
                f"Rate limit exceeded for {client_key} on {path} "
                f"({rate_type}: {max_rate}/{self.window}s)"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"请求过于频繁，请稍后再试（限制：{max_rate}次/{self.window}秒）",
                    "type": "rate_limit_exceeded"
                }
            )
        
        return await call_next(request)
    
    def cleanup(self):
        """清理过期的计数器（可定期调用）"""
        now = time.time()
        for counters in [self._llm_counters, self._api_counters]:
            expired = [k for k, (_, t) in counters.items() if now - t > self.window * 2]
            for k in expired:
                del counters[k]
