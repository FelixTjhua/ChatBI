"""Property-based tests for error message sanitization."""
import sys
import os
import re

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Ensure the backend root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.utils.error_sanitizer import sanitize_error_message


# ---------------------------------------------------------------------------

_CONNECTION_SCHEMES = re.compile(
    r'(postgresql|mysql|oracle|mssql|sqlite|mongodb|redis|amqp)'
    r'(\+\w+)?://',
    re.IGNORECASE,
)

_UNIX_SENSITIVE_PATHS = re.compile(
    r'/(?:home|app|usr|var|etc|tmp|opt|srv|root|proc|sys|mnt|media|Users|Library)'
    r'/[^\s]+',
    re.IGNORECASE,
)

_WINDOWS_PATHS = re.compile(
    r'[A-Za-z]:\\\\(?:[^\s:,\'"}\]]+\\\\?)+',
)

_TRACEBACK_HEADER = re.compile(
    r'Traceback \(most recent call last\)',
)

_FILE_LINE_REF = re.compile(
    r'File "[^"]*", line \d+',
)

_INTERNAL_MODULE = re.compile(
    r'\b(?:apps|common|backend)\.'
    r'(?:[a-z_]+\.){1,6}'
    r'[A-Za-z_]+\b',
)

_API_KEY_PATTERN = re.compile(
    r'(?:'
    r'sk-[A-Za-z0-9]{20,}'
    r'|'
    r'Bearer\s+[A-Za-z0-9\-._~+/]+=*'
    r'|'
    r'(?:api[_-]?key|apikey|secret[_-]?key|access[_-]?token)'
    r'\s*[=:]\s*["\']?[A-Za-z0-9\-._~+/]{8,}["\']?'
    r')',
    re.IGNORECASE,
)


def _contains_sensitive(text: str) -> list[str]:
    """Return list of sensitive pattern names found in *text*."""
    found = []
    if _CONNECTION_SCHEMES.search(text):
        found.append("connection_string")
    if _UNIX_SENSITIVE_PATHS.search(text):
        found.append("unix_path")
    if _WINDOWS_PATHS.search(text):
        found.append("windows_path")
    if _TRACEBACK_HEADER.search(text):
        found.append("traceback_header")
    if _FILE_LINE_REF.search(text):
        found.append("file_line_ref")
    if _INTERNAL_MODULE.search(text):
        found.append("internal_module")
    if _API_KEY_PATTERN.search(text):
        found.append("api_key")
    return found


# ---------------------------------------------------------------------------

_db_schemes = st.sampled_from([
    "postgresql", "mysql", "oracle", "mssql", "sqlite",
    "mongodb", "redis", "amqp",
])

_db_drivers = st.one_of(
    st.just(""),
    st.sampled_from(["+pymysql", "+psycopg2", "+asyncpg", "+cx_oracle"]),
)

_db_users = st.sampled_from(["admin", "root", "user", "deploy", "chatbi"])
_db_passwords = st.sampled_from(["secret", "p@ss!", "123456", "hunter2"])
_db_hosts = st.sampled_from(["localhost", "db.internal", "10.0.0.5", "rds.aws.com"])
_db_ports = st.sampled_from(["5432", "3306", "1521", "6379", "27017"])
_db_names = st.sampled_from(["chatbi", "mydb", "production", "test_db"])


@st.composite
def connection_string(draw):
    """Generate a database connection string like postgresql://user:pass@host:port/db."""
    scheme = draw(_db_schemes)
    driver = draw(_db_drivers)
    user = draw(_db_users)
    pwd = draw(_db_passwords)
    host = draw(_db_hosts)
    port = draw(_db_ports)
    db = draw(_db_names)
    return f"{scheme}{driver}://{user}:{pwd}@{host}:{port}/{db}"


_unix_roots = st.sampled_from([
    "/home", "/app", "/usr", "/var", "/etc", "/tmp",
    "/opt", "/srv", "/root", "/Users", "/Library",
])

_path_segments = st.lists(
    st.from_regex(r"[a-z_][a-z0-9_]{1,12}", fullmatch=True),
    min_size=1,
    max_size=4,
)


@st.composite
def unix_file_path(draw):
    """Generate a Unix file path like /home/deploy/chatbi/config.py."""
    root = draw(_unix_roots)
    segments = draw(_path_segments)
    ext = draw(st.sampled_from([".py", ".log", ".conf", ".json", ".yaml", ""]))
    return root + "/" + "/".join(segments) + ext


_drive_letters = st.sampled_from(["C", "D", "E"])


@st.composite
def windows_file_path(draw):
    r"""Generate a Windows file path with double-backslash separators.

    The sanitizer regex matches escaped Windows paths like C:\\Users\\admin\\project
    (with literal double backslashes as they appear in JSON/log output).
    We need at least 2 path segments for the regex to match.
    """
    drive = draw(_drive_letters)
    segments = draw(st.lists(
        st.from_regex(r"[a-zA-Z_][a-zA-Z0-9_]{1,12}", fullmatch=True),
        min_size=2,
        max_size=4,
    ))
    return drive + "\\\\" + "\\\\".join(segments)


_traceback_files = st.sampled_from([
    "llm.py", "sql_generator.py", "main.py", "feedback.py",
    "analysis_service.py", "prediction_service.py",
])

_traceback_lines = st.integers(min_value=1, max_value=5000)

_traceback_funcs = st.sampled_from([
    "run_task", "generate_sql", "execute_sql", "save_error",
    "dispatch", "__init__", "process_request",
])


@st.composite
def traceback_text(draw):
    """Generate a Python traceback-like string."""
    filename = draw(_traceback_files)
    lineno = draw(_traceback_lines)
    func = draw(_traceback_funcs)
    error_type = draw(st.sampled_from([
        "ValueError", "TypeError", "KeyError", "RuntimeError",
        "ConnectionError", "TimeoutError",
    ]))
    error_msg = draw(st.sampled_from([
        "invalid literal", "unexpected type", "'key' not found",
        "connection refused", "operation timed out",
    ]))
    return (
        f'Traceback (most recent call last):\n'
        f'  File "{filename}", line {lineno}, in {func}\n'
        f'{error_type}: {error_msg}'
    )


_module_prefixes = st.sampled_from(["apps", "common", "backend"])

_module_segments = st.lists(
    st.from_regex(r"[a-z_]{2,10}", fullmatch=True),
    min_size=1,
    max_size=5,
)

_class_names = st.sampled_from([
    "LLMService", "SQLGeneratorMixin",
    "QueryRewriter", "ContextCompressor", "RAGEvaluator",
    "DialogueStateTracker", "FeedbackService",
])


@st.composite
def internal_module_ref(draw):
    """Generate an internal module reference like apps.chat.task.llm.LLMService."""
    prefix = draw(_module_prefixes)
    segments = draw(_module_segments)
    cls = draw(_class_names)
    return f"{prefix}.{'.'.join(segments)}.{cls}"


# API key strategies
_api_key_suffixes = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"),
    min_size=20,
    max_size=50,
)


@st.composite
def api_key_string(draw):
    """Generate an API key string like sk-..., Bearer ..., or api_key=..."""
    key_type = draw(st.sampled_from(["openai", "bearer", "key_value"]))
    suffix = draw(_api_key_suffixes)
    if key_type == "openai":
        return f"sk-{suffix}"
    elif key_type == "bearer":
        return f"Bearer {suffix}"
    else:
        key_name = draw(st.sampled_from(["api_key", "api-key", "apikey", "secret_key", "access_token"]))
        return f"{key_name}={suffix}"


_safe_messages = st.sampled_from([
    "数据查询超时，请缩小查询范围后重试",
    "请求参数不合法",
    "操作失败，请稍后重试",
    "连接超时",
    "数据格式错误",
    "权限不足",
    "",
])


@st.composite
def mixed_content(draw):
    """Generate a message mixing sensitive and safe text."""
    safe = draw(_safe_messages)
    sensitive = draw(st.one_of(
        connection_string(),
        unix_file_path(),
        windows_file_path(),
        traceback_text(),
        internal_module_ref(),
        api_key_string(),
    ))
    # Randomly place sensitive content before or after safe text
    if draw(st.booleans()):
        return f"{safe} {sensitive}"
    else:
        return f"{sensitive} {safe}"


# Composite strategy: any kind of sensitive input
sensitive_input = st.one_of(
    connection_string(),
    unix_file_path(),
    windows_file_path(),
    traceback_text(),
    internal_module_ref(),
    api_key_string(),
    mixed_content(),
)


# ---------------------------------------------------------------------------

class TestErrorHandlingProperty15:
    """
    **Validates: Requirements 9.6, 11.5**

    Property 15: 错误处理友好性
    验证 sanitize_error_message() 返回的错误消息不包含内部实现细节
    （连接字符串、文件路径、堆栈跟踪、内部模块名）
    """

    @given(conn_str=connection_string())
    @settings(max_examples=100)
    def test_connection_strings_are_redacted(self, conn_str):
        """Database connection strings must not appear in sanitized output."""
        result = sanitize_error_message(conn_str)
        violations = _contains_sensitive(result)
        assert "connection_string" not in violations, (
            f"Connection string leaked: input={conn_str!r}, output={result!r}"
        )

    @given(path=unix_file_path())
    @settings(max_examples=100)
    def test_unix_paths_are_redacted(self, path):
        """Unix file paths must not appear in sanitized output."""
        result = sanitize_error_message(path)
        violations = _contains_sensitive(result)
        assert "unix_path" not in violations, (
            f"Unix path leaked: input={path!r}, output={result!r}"
        )

    @given(path=windows_file_path())
    @settings(max_examples=100)
    def test_windows_paths_are_redacted(self, path):
        """Windows file paths must not appear in sanitized output."""
        result = sanitize_error_message(path)
        violations = _contains_sensitive(result)
        assert "windows_path" not in violations, (
            f"Windows path leaked: input={path!r}, output={result!r}"
        )

    @given(tb=traceback_text())
    @settings(max_examples=100)
    def test_tracebacks_are_redacted(self, tb):
        """Python traceback patterns must not appear in sanitized output."""
        result = sanitize_error_message(tb)
        violations = _contains_sensitive(result)
        assert "traceback_header" not in violations, (
            f"Traceback header leaked: input={tb!r}, output={result!r}"
        )
        assert "file_line_ref" not in violations, (
            f"File/line ref leaked: input={tb!r}, output={result!r}"
        )

    @given(module=internal_module_ref())
    @settings(max_examples=100)
    def test_internal_modules_are_redacted(self, module):
        """Internal module/class references must not appear in sanitized output."""
        result = sanitize_error_message(module)
        violations = _contains_sensitive(result)
        assert "internal_module" not in violations, (
            f"Internal module leaked: input={module!r}, output={result!r}"
        )

    @given(api_key=api_key_string())
    @settings(max_examples=100)
    def test_api_keys_are_redacted(self, api_key):
        """API keys (sk-..., Bearer tokens, key=value) must not appear in sanitized output."""
        result = sanitize_error_message(api_key)
        violations = _contains_sensitive(result)
        assert "api_key" not in violations, (
            f"API key leaked: input={api_key!r}, output={result!r}"
        )

    @given(msg=mixed_content())
    @settings(max_examples=100)
    def test_mixed_content_has_no_sensitive_patterns(self, msg):
        """Mixed content (sensitive + safe text) must have all sensitive parts removed."""
        result = sanitize_error_message(msg)
        violations = _contains_sensitive(result)
        assert len(violations) == 0, (
            f"Sensitive patterns found: {violations}, input={msg!r}, output={result!r}"
        )

    @given(msg=sensitive_input)
    @settings(max_examples=100)
    def test_output_is_always_a_non_empty_string(self, msg):
        """Sanitized output must always be a non-empty string."""
        result = sanitize_error_message(msg)
        assert isinstance(result, str)
        assert len(result) > 0, (
            f"Empty output for input={msg!r}"
        )

    @given(msg=st.one_of(st.none(), st.just("")))
    @settings(max_examples=10)
    def test_empty_or_none_returns_fallback(self, msg):
        """None or empty string input must return the fallback message."""
        result = sanitize_error_message(msg)
        assert result == "服务内部错误，请稍后重试"


class TestUserFriendlyErrorMessages:
    """
    **Validates: Requirements 9.6, 11.5**

    验证各种错误场景返回用户友好的消息，不泄露内部实现细节。
    """

    def test_db_connection_error_no_connection_string_leaked(self):
        """数据源连接失败 → 不泄露连接字符串"""
        # Simulate a DB connection error with connection string
        raw_error = "Could not connect to postgresql://admin:secret@db.internal:5432/chatbi"
        result = sanitize_error_message(raw_error)
        assert "postgresql://" not in result
        assert "admin" not in result or "secret" not in result
        assert "db.internal" not in result

    def test_sql_execution_error_no_sql_leaked(self):
        """SQL 执行错误 → 不泄露 SQL 语句（通过 sanitize 过滤内部模块引用）"""
        raw_error = (
            'Traceback (most recent call last):\n'
            '  File "sql_generator.py", line 320, in execute_sql\n'
            'psycopg2.errors.SyntaxError: syntax error at or near "SELEC"'
        )
        result = sanitize_error_message(raw_error)
        assert "Traceback" not in result
        assert 'File "' not in result

    def test_llm_api_error_no_api_key_leaked(self):
        """LLM API 调用失败 → 不泄露 API Key"""
        raw_error = "OpenAI API error: Invalid API key sk-abcdefghijklmnopqrstuvwxyz1234567890"
        result = sanitize_error_message(raw_error)
        assert "sk-" not in result

    def test_document_parse_error_no_file_path_leaked(self):
        """文档解析失败 → 不泄露文件路径"""
        raw_error = "Failed to parse document at /home/deploy/chatbi/uploads/report.pdf: invalid format"
        result = sanitize_error_message(raw_error)
        assert "/home/" not in result
        assert "deploy" not in result
        assert "uploads" not in result

    def test_bearer_token_not_leaked(self):
        """Bearer token 不泄露"""
        raw_error = "Authorization failed: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.signature"
        result = sanitize_error_message(raw_error)
        assert "Bearer eyJ" not in result

    def test_internal_module_not_leaked(self):
        """内部模块路径不泄露"""
        raw_error = "Error in apps.chat.task.llm.LLMService.run_task: connection timeout"
        result = sanitize_error_message(raw_error)
        assert "apps.chat.task" not in result
        assert "LLMService" not in result



# ---------------------------------------------------------------------------

from common.utils.sql_error_handler import classify_sql_error

# Strategies for SQL error messages
_syntax_errors = st.sampled_from([
    "syntax error at or near 'SELEC'",
    "You have an error in your SQL syntax",
    "SyntaxError: unexpected token",
    "ORA-00933: SQL command not properly ended",
])

_table_not_found_errors = st.sampled_from([
    "relation 'nonexistent_table' does not exist",
    "Table 'mydb.unknown_table' doesn't exist",
    "Invalid object name 'missing_table'",
    "ORA-00942: table or view does not exist",
])

_column_not_found_errors = st.sampled_from([
    "Unknown column 'bad_col' in 'field list'",
    "column 'missing_field' does not exist",
    "Invalid column name 'xyz'",
    "ORA-00904: invalid identifier",
])

_connection_errors = st.sampled_from([
    "Connection refused to host db.internal:5432",
    "Connection timeout after 30s",
    "Network error: connection reset by peer",
    "Could not connect to server: Connection timed out",
])

_permission_errors = st.sampled_from([
    "Permission denied for table users",
    "Access denied for user 'readonly'@'localhost'",
    "ORA-01031: insufficient privileges",
])

_generic_errors = st.sampled_from([
    "Something went wrong during execution",
    "Unexpected error occurred",
    "Internal processing failure",
    "",
])

# Errors with Python traceback (should be stripped)
@st.composite
def _error_with_traceback(draw):
    """Generate an error message containing Python traceback."""
    error_type = draw(st.sampled_from([
        "psycopg2.errors.SyntaxError",
        "mysql.connector.errors.ProgrammingError",
        "sqlalchemy.exc.OperationalError",
    ]))
    error_detail = draw(st.sampled_from([
        "syntax error at or near 'FROM'",
        "table not found",
        "connection refused",
    ]))
    return (
        f'Traceback (most recent call last):\n'
        f'  File "apps/db/db.py", line 340, in exec_sql\n'
        f'{error_type}: {error_detail}'
    )

# All SQL error types combined
_any_sql_error = st.one_of(
    _syntax_errors,
    _table_not_found_errors,
    _column_not_found_errors,
    _connection_errors,
    _permission_errors,
    _generic_errors,
    _error_with_traceback(),
)


class TestStructuredErrorResponseProperty23:
    """
    **Validates: Requirements 1.4**

    Property 23: 结构化错误响应
    For any SQL execution error, the error response should be structured
    (error_type + suggestion), no raw Python stack traces
    (no "Traceback" or "File" keywords).
    """

    @given(error_msg=_any_sql_error)
    @settings(max_examples=100)
    def test_structured_response_has_error_type_and_suggestion(self, error_msg):
        """Feature: chatbi-system-audit-optimization, Property 23: 结构化错误响应
        classify_sql_error must return both error_type and suggestion fields."""
        result = classify_sql_error(error_msg)
        assert isinstance(result, dict), f"Result must be a dict, got {type(result)}"
        assert 'error_type' in result, f"Result must contain 'error_type': {result}"
        assert 'suggestion' in result, f"Result must contain 'suggestion': {result}"
        assert isinstance(result['error_type'], str) and len(result['error_type']) > 0, (
            f"error_type must be a non-empty string: {result['error_type']}"
        )
        assert isinstance(result['suggestion'], str) and len(result['suggestion']) > 0, (
            f"suggestion must be a non-empty string: {result['suggestion']}"
        )

    @given(error_msg=_any_sql_error)
    @settings(max_examples=100)
    def test_no_traceback_in_response(self, error_msg):
        """Feature: chatbi-system-audit-optimization, Property 23: 结构化错误响应
        The structured response must not contain raw Python stack traces."""
        result = classify_sql_error(error_msg)
        suggestion = result['suggestion']
        assert 'Traceback' not in suggestion, (
            f"Suggestion contains 'Traceback': {suggestion!r}"
        )
        # Check for "File" pattern typical in Python tracebacks
        assert not re.search(r'File "[^"]*", line \d+', suggestion), (
            f"Suggestion contains File/line reference: {suggestion!r}"
        )

    @given(error_msg=_error_with_traceback())
    @settings(max_examples=100)
    def test_traceback_input_produces_clean_output(self, error_msg):
        """Feature: chatbi-system-audit-optimization, Property 23: 结构化错误响应
        Even when input contains full traceback, output must be clean."""
        result = classify_sql_error(error_msg)
        suggestion = result['suggestion']
        assert 'Traceback (most recent call last)' not in suggestion
        assert 'File "' not in suggestion
        assert result['error_type'] != ''

    @given(error_msg=_syntax_errors)
    @settings(max_examples=100)
    def test_syntax_errors_classified_correctly(self, error_msg):
        """Feature: chatbi-system-audit-optimization, Property 23: 结构化错误响应
        SQL syntax errors should be classified as syntax_error type."""
        result = classify_sql_error(error_msg)
        assert result['error_type'] == 'syntax_error', (
            f"Expected syntax_error, got {result['error_type']} for: {error_msg}"
        )

    @given(error_msg=_connection_errors)
    @settings(max_examples=100)
    def test_connection_errors_classified_correctly(self, error_msg):
        """Feature: chatbi-system-audit-optimization, Property 23: 结构化错误响应
        Connection errors should be classified as connection_error type."""
        result = classify_sql_error(error_msg)
        assert result['error_type'] == 'connection_error', (
            f"Expected connection_error, got {result['error_type']} for: {error_msg}"
        )

    def test_none_input_returns_unknown_error(self):
        """Feature: chatbi-system-audit-optimization, Property 23: 结构化错误响应
        None/empty input should return unknown_error type."""
        result = classify_sql_error(None)
        assert result['error_type'] == 'unknown_error'
        assert len(result['suggestion']) > 0

        result2 = classify_sql_error('')
        assert result2['error_type'] == 'unknown_error'
        assert len(result2['suggestion']) > 0
