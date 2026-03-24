"""Property-based tests for SQLGeneratorMixin.check_sql()"""
import json
import sys
import os
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Ensure the backend root is on sys.path so that app modules can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Mock heavy dependencies that require database connections before importing
# the module under test. We only need the static check_sql() method.
_mods_to_mock = [
    "apps.chat.crud.chat",
    "apps.chat.thinking.rag_thinking",
    "apps.datasource.crud.permission",
    "apps.datasource.models.datasource",
    "apps.datasource.models",
    "apps.db.db",
    "apps.system.schemas.system_schema",
]
for _mod_name in _mods_to_mock:
    sys.modules.setdefault(_mod_name, MagicMock())

from apps.chat.task.sql_generator import SQLGeneratorMixin
from common.error import SingleMessageError


_sql_table_names = st.sampled_from([
    "users", "orders", "products", "sales", "customers",
    "inventory", "transactions", "employees", "departments", "accounts",
])

_sql_columns = st.sampled_from([
    "*", "id", "name", "COUNT(*)", "SUM(amount)", "AVG(price)",
    "id, name", "date, total", "category, COUNT(*)",
])

_sql_where_clause = st.one_of(
    st.just(""),
    st.just(" WHERE id > 0"),
    st.just(" WHERE name IS NOT NULL"),
    st.just(" WHERE amount >= 100"),
)


@st.composite
def valid_select_sql(draw):
    """Generate a syntactically valid SELECT statement."""
    col = draw(_sql_columns)
    table = draw(_sql_table_names)
    where = draw(_sql_where_clause)
    return f"SELECT {col} FROM {table}{where}"


@st.composite
def valid_check_sql_input(draw):
    """Generate a JSON string that check_sql() should accept.

    Format: {"success": true, "sql": "<SELECT ...>", "tables": [<table>]}
    The JSON may optionally be surrounded by extra text (simulating LLM output).
    """
    sql = draw(valid_select_sql())
    table = draw(_sql_table_names)
    tables = [table]
    payload = json.dumps({"success": True, "sql": sql, "tables": tables})

    # Optionally wrap with surrounding text to simulate LLM response
    prefix = draw(st.sampled_from(["", "Here is the result:\n", "```json\n"]))
    suffix = draw(st.sampled_from(["", "\n```", "\nDone."]))
    return prefix + payload + suffix, sql, tables


# Strategy: plain text with no JSON structure at all
_plain_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "Z"),  # letters, numbers, spaces
        blacklist_characters="{}[]",
    ),
    min_size=1,
    max_size=200,
).filter(lambda t: "{" not in t and "[" not in t)


# ---------------------------------------------------------------------------

class TestCheckSqlProperty13:
    """
    **Validates: Requirements 9.1**

    Property 13: SQL 语法检查
    验证 check_sql() 对合法 SELECT 语句返回非空结果，对纯文本返回空结果
    """

    @given(data=valid_check_sql_input())
    @settings(max_examples=100)
    def test_valid_select_returns_non_empty_result(self, data):
        """check_sql() should return a non-empty SQL string for valid JSON
        with success=true and a SELECT statement."""
        input_str, expected_sql, expected_tables = data

        sql, tables = SQLGeneratorMixin.check_sql(input_str)

        # SQL should be non-empty and match what we put in
        assert sql is not None
        assert len(sql.strip()) > 0
        assert sql == expected_sql
        # Tables should be returned
        assert tables == expected_tables

    @given(text=_plain_text)
    @settings(max_examples=100)
    def test_plain_text_raises_error(self, text):
        """check_sql() should raise SingleMessageError for plain text
        that contains no JSON structure."""
        with pytest.raises(SingleMessageError):
            SQLGeneratorMixin.check_sql(text)
