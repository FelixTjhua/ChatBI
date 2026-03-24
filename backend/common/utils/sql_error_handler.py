"""SQL 执行错误结构化处理工具。"""

import re
from typing import Dict


def classify_sql_error(error_message: str) -> Dict[str, str]:
    """将 SQL 执行错误分类为结构化错误信息。"""
    if not error_message:
        return {
            "error_type": "unknown_error",
            "suggestion": "执行过程中发生未知错误，请稍后重试"
        }

    msg_lower = error_message.lower()

    # 语法错误
    if any(kw in msg_lower for kw in [
        'syntax error', 'syntaxerror', '语法错误', 'sql syntax',
        'ora-00933', 'ora-01756', 'command not properly ended',
        'not properly ended', 'unexpected end',
    ]):
        return {
            "error_type": "syntax_error",
            "suggestion": "SQL语法错误，请尝试用更简洁的方式描述您的问题"
        }

    # 表或列不存在
    if any(kw in msg_lower for kw in [
        'no such table', 'table not found', 'unknown table',
        'relation', 'does not exist', 'doesn\'t exist',
        'invalid object name', 'ora-00942',
    ]):
        return {
            "error_type": "table_not_found",
            "suggestion": "查询引用了不存在的表，请检查数据源中的表结构或换一种方式提问"
        }

    if any(kw in msg_lower for kw in [
        'unknown column', 'column not found', 'no such column',
        'invalid column', 'ora-00904', 'undefined column',
    ]):
        return {
            "error_type": "column_not_found",
            "suggestion": "查询引用了不存在的字段，请检查字段名称或换一种方式提问"
        }

    # 权限错误
    if any(kw in msg_lower for kw in [
        'permission denied', 'access denied', 'insufficient privileges',
        'ora-01031', 'ora-00942',
    ]):
        return {
            "error_type": "permission_error",
            "suggestion": "数据库权限不足，请联系管理员检查数据源配置"
        }

    # 连接错误
    if any(kw in msg_lower for kw in [
        'connection', 'timeout', 'timed out', 'refused',
        'reset', 'broken pipe', 'network',
    ]):
        return {
            "error_type": "connection_error",
            "suggestion": "数据库连接异常，请检查数据源连接状态后重试"
        }

    # 数据类型错误
    if any(kw in msg_lower for kw in [
        'type mismatch', 'data type', 'cannot cast',
        'invalid input syntax', 'conversion failed',
    ]):
        return {
            "error_type": "type_error",
            "suggestion": "数据类型不匹配，请尝试调整问题描述"
        }

    # 除零错误
    if any(kw in msg_lower for kw in ['division by zero', 'divide by zero']):
        return {
            "error_type": "division_by_zero",
            "suggestion": "计算过程中出现除零错误，请检查数据是否包含零值"
        }

    # 多语句注入
    if '仅允许' in error_message or '不允许的操作' in error_message:
        return {
            "error_type": "forbidden_operation",
            "suggestion": error_message
        }

    # 结果解析错误
    if any(kw in msg_lower for kw in ['parse', 'decode', 'encoding']):
        return {
            "error_type": "parse_error",
            "suggestion": "查询结果解析失败，请尝试简化查询条件"
        }

    # 默认：通用错误
    # 清理可能的堆栈信息
    clean_msg = _strip_stack_trace(error_message)
    return {
        "error_type": "execution_error",
        "suggestion": f"查询执行失败：{clean_msg}" if clean_msg else "查询执行失败，请尝试简化您的问题"
    }


def _strip_stack_trace(message: str) -> str:
    """移除消息中的 Python 堆栈跟踪信息。"""
    # 移除 Traceback 块
    message = re.sub(
        r'Traceback \(most recent call last\):.*?(?=\n[A-Z]|\Z)',
        '', message, flags=re.DOTALL
    )
    # 移除 File "..." 行
    message = re.sub(r'File "[^"]*", line \d+.*?\n?', '', message)
    # 移除内部模块引用
    message = re.sub(
        r'\b(?:apps|common|backend)\.'
        r'(?:[a-z_]+\.){1,6}'
        r'[A-Za-z_]+\b',
        '', message
    )
    result = message.strip()
    # 如果清理后太短或为空，返回空字符串
    if len(result) < 3:
        return ""
    return result[:200]  # 限制长度
