import base64
import hashlib
import inspect
import json
import logging
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Request
from common.core.config import settings
from typing import Optional

import jwt
import orjson
from jwt.exceptions import InvalidTokenError

from common.core import security


def generate_password_reset_token(email: str) -> str:
    delta = timedelta(hours=24)  # 密码重置token有效期24小时
    now = datetime.now(timezone.utc)
    expires = now + delta
    exp = expires.timestamp()
    encoded_jwt = jwt.encode(
        {"exp": exp, "nbf": now, "sub": email},
        settings.SECRET_KEY,
        algorithm=security.ALGORITHM,
    )
    return encoded_jwt


def verify_password_reset_token(token: str) -> str | None:
    try:
        decoded_token = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        return str(decoded_token["sub"])
    except InvalidTokenError:
        return None


def deepcopy_ignore_extra(src, dest):
    import copy
    for attr in vars(src):
        if hasattr(dest, attr):
            src_value = getattr(src, attr)
            dest_value = copy.deepcopy(src_value)  # deep copy
            setattr(dest, attr, dest_value)
    return dest


def extract_nested_json(text):
    stack = []
    start_index = -1
    results = []

    for i, char in enumerate(text):
        if char in '{[':
            if not stack:  # 记录起始位置
                start_index = i
            stack.append(char)
        elif char in '}]':
            if stack and ((char == '}' and stack[-1] == '{') or (char == ']' and stack[-1] == '[')):
                stack.pop()
                if not stack:  # 栈空时截取完整JSON
                    json_str = text[start_index:i + 1]
                    try:
                        orjson.loads(json_str)  # 验证有效性
                        results.append(json_str)
                    except (ValueError, Exception):
                        pass
            else:
                stack = []  # 括号不匹配则重置
    if len(results) > 0 and results[0]:
        return results[0]
    return None


def extract_json_robust(text: str, prefer_type: str = 'auto') -> Optional[str]:
    """强大的 JSON 提取函数，支持多种格式
        1. 提取 ```json 代码块中的 JSON（优先，支持对象和数组）
        """
    import re
    
    # 方法1: 提取 ```json 代码块（优先，支持对象和数组）
    # 先尝试提取数组
    json_array_block_pattern = r'```(?:json)?\s*(\[[\s\S]*?\])\s*```'
    match = re.search(json_array_block_pattern, text)
    if match:
        candidate = match.group(1).strip()
        try:
            orjson.loads(candidate)
            return candidate
        except (ValueError, Exception):
            pass
    
    # 再尝试提取对象
    json_object_block_pattern = r'```(?:json)?\s*(\{[\s\S]*?\})\s*```'
    match = re.search(json_object_block_pattern, text)
    if match:
        candidate = match.group(1).strip()
        try:
            orjson.loads(candidate)
            return candidate
        except (ValueError, Exception):
            pass
    
    # 方法2: 使用栈匹配完整的 JSON（支持任意深度嵌套）
    def find_complete_json_structures(text: str):
        """使用栈找到所有完整的 JSON 结构（对象和数组）"""
        results = []
        i = 0
        while i < len(text):
            if text[i] in '{[':
                stack = []
                start = i
                in_string = False
                escape = False
                start_char = text[i]
                
                for j in range(i, len(text)):
                    char = text[j]
                    
                    # 处理字符串中的引号
                    if char == '"' and not escape:
                        in_string = not in_string
                    elif char == '\\' and in_string:
                        escape = not escape
                        continue
                    
                    escape = False
                    
                    # 只在非字符串中处理括号
                    if not in_string:
                        if char in '{[':
                            stack.append(char)
                        elif char in '}]':
                            if stack:
                                last = stack[-1]
                                # 检查括号匹配
                                if (char == '}' and last == '{') or (char == ']' and last == '['):
                                    stack.pop()
                                    if not stack:  # 找到完整的 JSON
                                        candidate = text[start:j+1]
                                        try:
                                            orjson.loads(candidate)
                                            # 标记是数组还是对象
                                            is_array = start_char == '['
                                            results.append((start, candidate, is_array))
                                            i = j
                                            break
                                        except (ValueError, Exception):
                                            pass
            i += 1
        return results
    
    json_structures = find_complete_json_structures(text)
    if json_structures:
        # 根据 prefer_type 决定优先返回类型
        if prefer_type == 'object':
            # 优先返回包含 success/type 字段的对象（SQL结果等场景）
            for _, candidate, is_array in json_structures:
                if not is_array:
                    try:
                        data = orjson.loads(candidate)
                        if 'type' in data or 'success' in data:
                            return candidate
                    except (ValueError, Exception):
                        continue
            # 退而求其次：任意对象
            for _, candidate, is_array in json_structures:
                if not is_array:
                    return candidate
        elif prefer_type == 'array':
            # 优先返回数组（预测数据等场景）
            for _, candidate, is_array in json_structures:
                if is_array:
                    return candidate
        else:
            # auto模式：优先返回数组（兼容旧行为）
            for _, candidate, is_array in json_structures:
                if is_array:
                    return candidate
        
            # 如果没有数组，优先返回包含 type 或 success 字段的对象
            for _, candidate, is_array in reversed(json_structures):
                if not is_array:
                    try:
                        data = orjson.loads(candidate)
                        if 'type' in data or 'success' in data:
                            return candidate
                    except (ValueError, Exception):
                        continue
        
        # 如果都没有匹配，返回第一个有效的结构
        if json_structures:
            return json_structures[0][1]
    
    # 方法3: 使用原有的 extract_nested_json（支持数组和对象）
    json_str = extract_nested_json(text)
    if json_str:
        return json_str
    
    return None

def string_to_numeric_hash(text: str, bits: Optional[int] = 64) -> int:
    hash_bytes = hashlib.sha256(text.encode()).digest()
    hash_num = int.from_bytes(hash_bytes, byteorder='big')
    max_bigint = 2**63 - 1
    return hash_num % max_bigint


def setup_logging():
    # 确保日志目录存在
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 日志格式
    formatter = logging.Formatter(
        f'{settings.LOG_FORMAT}'
    )
    
    # 控制台日志
    console_handler = logging.StreamHandler()
    console_handler.setLevel(settings.LOG_LEVEL)
    console_handler.setFormatter(formatter)
    
    # 文件日志处理器
    file_handlers = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warn': logging.WARNING,
        'error': logging.ERROR
    }
    
    # 主日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # 设置最低级别
    
    # 添加控制台处理器
    root_logger.addHandler(console_handler)
    
    # 为每个级别创建文件处理器
    for level_name, level in file_handlers.items():
        file_path = log_dir / f"{level_name}.log"
        handler = RotatingFileHandler(
            file_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        handler.setLevel(level)
        handler.setFormatter(formatter)
        
        # 添加过滤器只处理特定级别日志
        if level_name == 'debug':
            handler.addFilter(lambda record: record.levelno == logging.DEBUG)
        elif level_name == 'info':
            handler.addFilter(lambda record: record.levelno == logging.INFO)
        elif level_name == 'warn':
            handler.addFilter(lambda record: record.levelno == logging.WARNING)
        elif level_name == 'error':
            handler.addFilter(lambda record: record.levelno >= logging.ERROR)
        
        root_logger.addHandler(handler)
    
    # SQL日志特殊处理
    if settings.LOG_LEVEL == "DEBUG" and settings.SQL_DEBUG:
        sql_logger = logging.getLogger('sqlalchemy.engine')
        sql_logger.setLevel(logging.DEBUG)
        
        sql_handler = RotatingFileHandler(
            log_dir / "sql.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=2,
            encoding='utf-8'
        )
        sql_handler.setFormatter(formatter)
        sql_logger.addHandler(sql_handler)
        
setup_logging()


class CallerLogger(logging.Logger):
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        super().__init__(logger.name, logger.level)

    def _log(self, level, msg, args, exc_info=None, extra=None, stacklevel=3):
        if self.logger.isEnabledFor(level):
            self.logger._log(level, msg, args, exc_info=exc_info, extra=extra, stacklevel=stacklevel)

class ChatBILogUtil:
    
    @staticmethod
    def _get_logger() -> logging.Logger:
        frame = inspect.currentframe()
        try:
            caller_frame = frame.f_back.f_back
            module_name = caller_frame.f_globals.get('__name__', '__main__')
            return CallerLogger(logging.getLogger(module_name))
        finally:
            del frame
        

    @staticmethod
    def debug(msg: str, *args, **kwargs):
        logger = ChatBILogUtil._get_logger()
        if logger.isEnabledFor(logging.DEBUG):
            logger._log(logging.DEBUG, msg, args, **kwargs)

    @staticmethod
    def info(msg: str, *args, **kwargs):
        logger = ChatBILogUtil._get_logger()
        if logger.isEnabledFor(logging.INFO):
            logger._log(logging.INFO, msg, args, **kwargs)

    @staticmethod
    def warning(msg: str, *args, **kwargs):
        logger = ChatBILogUtil._get_logger()
        if logger.isEnabledFor(logging.WARNING):
            logger._log(logging.WARNING, msg, args, **kwargs)

    @staticmethod
    def error(msg: str, *args, exc_info: Optional[bool] = None, **kwargs):
        logger = ChatBILogUtil._get_logger()
        if logger.isEnabledFor(logging.ERROR):
            logger._log(
                logging.ERROR, 
                msg, 
                args, 
                exc_info=exc_info if exc_info is not None else True,
                **kwargs
            )

    @staticmethod
    def exception(msg: str = "Exception occurred", *args, **kwargs):
        logger = ChatBILogUtil._get_logger()
        if logger.isEnabledFor(logging.ERROR):
            logger._log(logging.ERROR, msg, args, exc_info=True, **kwargs)

    @staticmethod
    def critical(msg: str, *args, **kwargs):
        logger = ChatBILogUtil._get_logger()
        if logger.isEnabledFor(logging.CRITICAL):
            logger._log(logging.CRITICAL, msg, args, **kwargs)


            
def prepare_for_orjson(data):
    """将数据转换为 orjson 可序列化的类型（第二道防线，exec_sql 层已做主要转换）"""
    from datetime import datetime, date, time, timedelta
    from decimal import Decimal
    
    if data is None:
        return data
    if isinstance(data, bytes):
        try:
            return data.decode('utf-8')
        except UnicodeDecodeError:
            return base64.b64encode(data).decode('utf-8')
    elif isinstance(data, bytearray):
        return prepare_for_orjson(bytes(data))
    elif isinstance(data, Decimal):
        return float(str(data))
    elif isinstance(data, float):
        import math
        if not (math.isinf(data) or math.isnan(data)):
            data = round(data, 10)
        return data
    elif isinstance(data, timedelta):
        return str(data)
    elif isinstance(data, datetime):
        return data.strftime('%Y-%m-%d %H:%M:%S')
    elif isinstance(data, date):
        return data.isoformat()
    elif isinstance(data, time):
        return str(data)
    elif isinstance(data, dict):
        return {k: prepare_for_orjson(v) for k, v in data.items()}
    elif isinstance(data, (list, tuple)):
        return [prepare_for_orjson(item) for item in data]
    else:
        return data
        
    
def prepare_model_arg(origin_arg: str):
    if not isinstance(origin_arg, str):
        return origin_arg
    if not origin_arg.strip()[0] in {'{', '['}:
        return origin_arg
    try:
        return json.loads(origin_arg)
    except (ValueError, json.JSONDecodeError):
        return origin_arg
    
def get_origin_from_referer(request: Request):
    referer = request.headers.get("referer")
    if not referer:
        return None
    
    try:
        parsed = urlparse(referer)
        if not parsed.scheme or not parsed.hostname:
            return None
        port = parsed.port
        if port:
            if (parsed.scheme == "http" and port != 80) or \
               (parsed.scheme == "https" and port != 443):
                return f"{parsed.scheme}://{parsed.hostname}:{port}"
        
        return f"{parsed.scheme}://{parsed.hostname}"
    except Exception as e:
        ChatBILogUtil.error(f"解析 Referer 出错: {e}")
        return referer


def equals_ignore_case(str1: str, *args: str) -> bool:
    if str1 is None:
        return None in args
    for arg in args:
        if arg is None:
            continue
        if str1.casefold() == arg.casefold():
            return True
    return False