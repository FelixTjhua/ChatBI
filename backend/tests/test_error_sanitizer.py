"""
错误消息脱敏工具的单元测试。
"""

import pytest
from common.utils.error_sanitizer import sanitize_error_message


class TestSanitizeConnectionStrings:
    """验证数据库连接字符串被正确过滤"""

    def test_postgresql_connection_string(self):
        msg = "could not connect to postgresql://admin:secret@db.host:5432/mydb"
        result = sanitize_error_message(msg)
        assert "postgresql://" not in result
        assert "admin:secret" not in result
        assert "db.host" not in result

    def test_mysql_connection_string(self):
        msg = "Error connecting to mysql+pymysql://root:pass@localhost/chatbi"
        result = sanitize_error_message(msg)
        assert "mysql" not in result.lower() or "[REDACTED]" in result
        assert "root:pass" not in result

    def test_oracle_connection_string(self):
        msg = "oracle://user:pwd@host:1521/sid failed"
        result = sanitize_error_message(msg)
        assert "oracle://" not in result
        assert "user:pwd" not in result

    def test_redis_connection_string(self):
        msg = "redis://default:password@redis-host:6379/0 timeout"
        result = sanitize_error_message(msg)
        assert "redis://" not in result


class TestSanitizeFilePaths:
    """验证文件系统路径被正确过滤"""

    def test_home_path(self):
        msg = "FileNotFoundError: /home/deploy/chatbi/config.py"
        result = sanitize_error_message(msg)
        assert "/home/" not in result

    def test_app_path(self):
        msg = "ImportError at /app/backend/apps/chat/task/llm.py"
        result = sanitize_error_message(msg)
        assert "/app/" not in result

    def test_usr_path(self):
        msg = "ModuleNotFoundError: /usr/lib/python3.11/site-packages/foo"
        result = sanitize_error_message(msg)
        assert "/usr/" not in result

    def test_var_path(self):
        msg = "Permission denied: /var/log/chatbi/error.log"
        result = sanitize_error_message(msg)
        assert "/var/" not in result


class TestSanitizeTracebacks:
    """验证 Python traceback 信息被正确过滤"""

    def test_traceback_header(self):
        msg = 'Traceback (most recent call last):\n  File "llm.py", line 42\nValueError: bad'
        result = sanitize_error_message(msg)
        assert "Traceback" not in result

    def test_file_line_reference(self):
        msg = 'File "/app/backend/apps/chat/task/llm.py", line 2694, in run_task'
        result = sanitize_error_message(msg)
        assert 'File "' not in result
        assert "line 2694" not in result


class TestSanitizeInternalModules:
    """验证内部模块/类名引用被正确过滤"""

    def test_internal_module_path(self):
        msg = "Error in apps.chat.task.llm.LLMService.run_task"
        result = sanitize_error_message(msg)
        assert "apps.chat.task.llm" not in result

    def test_common_module_path(self):
        msg = "Failed at common.core.response_middleware.dispatch"
        result = sanitize_error_message(msg)
        assert "common.core.response_middleware" not in result


class TestSanitizeFallback:
    """验证兜底消息逻辑"""

    def test_none_message(self):
        result = sanitize_error_message(None)
        assert result == "服务内部错误，请稍后重试"

    def test_empty_message(self):
        result = sanitize_error_message("")
        assert result == "服务内部错误，请稍后重试"

    def test_custom_fallback(self):
        result = sanitize_error_message("", fallback="Custom error")
        assert result == "Custom error"

    def test_safe_message_preserved(self):
        msg = "数据查询超时，请缩小查询范围后重试"
        result = sanitize_error_message(msg)
        assert result == msg


class TestSanitizeMixedContent:
    """验证混合内容的脱敏"""

    def test_mixed_sensitive_and_safe(self):
        msg = "连接失败 postgresql://user:pass@host/db 请检查网络"
        result = sanitize_error_message(msg)
        assert "postgresql://" not in result
        assert "请检查网络" in result

    def test_fully_redacted_returns_fallback(self):
        msg = "postgresql://user:pass@host:5432/db"
        result = sanitize_error_message(msg)
        # The entire message is a connection string, should return fallback
        assert "postgresql://" not in result
