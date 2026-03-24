"""Property-based tests for PredictionServiceMixin._calculate_prediction_confidence()"""
import sys
import os
import types
import statistics
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Ensure the backend root is on sys.path so that app modules can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


_MODULES_TO_STUB = [
    # DB layer
    "common.core.db",
    # CRUD — prediction_service.py imports from apps.chat.crud.chat
    "apps.chat.crud.chat",
    # Models (must mock before import to avoid pydantic/Python 3.14 forward-ref crash)
    "apps.chat.models.chat_model",
    "apps.datasource.models.datasource",
    "apps.datasource.models",
    # Terminology (needs dicttoxml)
    "apps.terminology.crud.terminology",
    # common.chatbi package (needs Crypto)
    "common.chatbi",
    "common.chatbi.crypto",
    "common.chatbi.custom_prompt",
    "common.chatbi.license",
]

for _mod_name in _MODULES_TO_STUB:
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = MagicMock()

# Provide specific names that prediction_service.py imports directly
for _name in ("start_log", "end_log", "save_predict_answer",
              "save_predict_data", "get_chat_chart_data"):
    setattr(sys.modules["apps.chat.crud.chat"], _name, MagicMock())

setattr(sys.modules["apps.chat.models.chat_model"], "OperationEnum", MagicMock())
setattr(sys.modules["apps.terminology.crud.terminology"], "get_terminology_template", MagicMock())
setattr(sys.modules["common.chatbi.custom_prompt"], "find_custom_prompts", MagicMock())
setattr(sys.modules["common.chatbi.custom_prompt"], "CustomPromptTypeEnum", MagicMock())
setattr(sys.modules["common.chatbi.license"], "ChatBILicenseUtil", MagicMock())

# Now safe to import the module under test
from apps.chat.task.prediction_service import PredictionServiceMixin


# ---------------------------------------------------------------------------

VALID_LEVELS = {"高", "中", "低"}

RESULT_REQUIRED_KEYS = {"score", "level", "factors", "prediction_interval"}

FACTORS_REQUIRED_KEYS = {
    "data_volume", "time_span", "trend_stability", "data_completeness",
}

INTERVAL_REQUIRED_KEYS = {"lower", "upper"}


# ---------------------------------------------------------------------------

_data_rows_strategy = st.integers(min_value=1, max_value=10000)

_time_span_strategy = st.floats(
    min_value=1.0, max_value=60.0, allow_nan=False, allow_infinity=False,
)

_values_strategy = st.lists(
    st.floats(min_value=-1000.0, max_value=1000.0,
              allow_nan=False, allow_infinity=False),
    min_size=2, max_size=100,
)

_missing_rate_strategy = st.floats(
    min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False,
)


# ---------------------------------------------------------------------------

class TestPredictionConfidenceRangeProperty20:
    """
    **Validates: Requirements 13.4**

    Property 24: 预测置信度评分范围
    验证 _calculate_prediction_confidence() 返回的 prediction_confidence 始终在 [0, 1]，
    score 始终在 [0, 100]，level 为 "高"/"中"/"低" 之一，且返回结构包含所有必要字段。
    """

    @given(
        data_rows=_data_rows_strategy,
        time_span_months=_time_span_strategy,
        values=_values_strategy,
        missing_rate=_missing_rate_strategy,
    )
    @settings(max_examples=100)
    def test_prediction_confidence_within_zero_one(
        self, data_rows, time_span_months, values, missing_rate,
    ):
        """prediction_confidence must always be in [0, 1] (Property 24)."""
        result = PredictionServiceMixin._calculate_prediction_confidence(
            data_rows=data_rows,
            time_span_months=time_span_months,
            values=values,
            missing_rate=missing_rate,
        )
        assert "prediction_confidence" in result, "Missing prediction_confidence field"
        pc = result["prediction_confidence"]
        assert 0 <= pc <= 1, (
            f"prediction_confidence {pc} is out of [0, 1] range"
        )

    @given(
        data_rows=_data_rows_strategy,
        time_span_months=_time_span_strategy,
        values=_values_strategy,
        missing_rate=_missing_rate_strategy,
    )
    @settings(max_examples=100)
    def test_prediction_confidence_consistent_with_score(
        self, data_rows, time_span_months, values, missing_rate,
    ):
        """prediction_confidence should equal score / 100."""
        result = PredictionServiceMixin._calculate_prediction_confidence(
            data_rows=data_rows,
            time_span_months=time_span_months,
            values=values,
            missing_rate=missing_rate,
        )
        expected = round(result["score"] / 100.0, 4)
        assert result["prediction_confidence"] == expected, (
            f"prediction_confidence {result['prediction_confidence']} != score/100 {expected}"
        )

    @given(
        data_rows=_data_rows_strategy,
        time_span_months=_time_span_strategy,
        values=_values_strategy,
        missing_rate=_missing_rate_strategy,
    )
    @settings(max_examples=100)
    def test_score_within_range(
        self, data_rows, time_span_months, values, missing_rate,
    ):
        """score must always be in [0, 100]."""
        result = PredictionServiceMixin._calculate_prediction_confidence(
            data_rows=data_rows,
            time_span_months=time_span_months,
            values=values,
            missing_rate=missing_rate,
        )
        assert 0 <= result["score"] <= 100, (
            f"score {result['score']} is out of [0, 100] range"
        )

    @given(
        data_rows=_data_rows_strategy,
        time_span_months=_time_span_strategy,
        values=_values_strategy,
        missing_rate=_missing_rate_strategy,
    )
    @settings(max_examples=100)
    def test_level_is_valid(
        self, data_rows, time_span_months, values, missing_rate,
    ):
        """level must be one of '高', '中', '低'."""
        result = PredictionServiceMixin._calculate_prediction_confidence(
            data_rows=data_rows,
            time_span_months=time_span_months,
            values=values,
            missing_rate=missing_rate,
        )
        assert result["level"] in VALID_LEVELS, (
            f"level '{result['level']}' is not in {VALID_LEVELS}"
        )

    @given(
        data_rows=_data_rows_strategy,
        time_span_months=_time_span_strategy,
        values=_values_strategy,
        missing_rate=_missing_rate_strategy,
    )
    @settings(max_examples=100)
    def test_level_consistent_with_score(
        self, data_rows, time_span_months, values, missing_rate,
    ):
        """level must match score thresholds: >=80 高, >=50 中, <50 低."""
        result = PredictionServiceMixin._calculate_prediction_confidence(
            data_rows=data_rows,
            time_span_months=time_span_months,
            values=values,
            missing_rate=missing_rate,
        )
        score = result["score"]
        level = result["level"]

        if score >= 80:
            assert level == "高", f"score={score} → expected '高', got '{level}'"
        elif score >= 50:
            assert level == "中", f"score={score} → expected '中', got '{level}'"
        else:
            assert level == "低", f"score={score} → expected '低', got '{level}'"

    @given(
        data_rows=_data_rows_strategy,
        time_span_months=_time_span_strategy,
        values=_values_strategy,
        missing_rate=_missing_rate_strategy,
    )
    @settings(max_examples=100)
    def test_result_contains_required_keys(
        self, data_rows, time_span_months, values, missing_rate,
    ):
        """Result dict must contain all required keys with correct structure."""
        result = PredictionServiceMixin._calculate_prediction_confidence(
            data_rows=data_rows,
            time_span_months=time_span_months,
            values=values,
            missing_rate=missing_rate,
        )

        assert isinstance(result, dict), "Result must be a dict"
        assert RESULT_REQUIRED_KEYS.issubset(result.keys()), (
            f"Missing keys: {RESULT_REQUIRED_KEYS - result.keys()}"
        )

        factors = result["factors"]
        assert isinstance(factors, dict), "factors must be a dict"
        assert FACTORS_REQUIRED_KEYS.issubset(factors.keys()), (
            f"Missing factor keys: {FACTORS_REQUIRED_KEYS - factors.keys()}"
        )
        for key in FACTORS_REQUIRED_KEYS:
            assert 0 <= factors[key] <= 100, (
                f"Factor '{key}' = {factors[key]} out of [0, 100]"
            )

        interval = result["prediction_interval"]
        assert isinstance(interval, dict), "prediction_interval must be a dict"
        assert INTERVAL_REQUIRED_KEYS.issubset(interval.keys()), (
            f"Missing interval keys: {INTERVAL_REQUIRED_KEYS - interval.keys()}"
        )

    @given(
        data_rows=_data_rows_strategy,
        time_span_months=_time_span_strategy,
        values=_values_strategy,
        missing_rate=_missing_rate_strategy,
    )
    @settings(max_examples=100)
    def test_prediction_interval_ordering(
        self, data_rows, time_span_months, values, missing_rate,
    ):
        """When prediction interval is provided, lower <= upper."""
        result = PredictionServiceMixin._calculate_prediction_confidence(
            data_rows=data_rows,
            time_span_months=time_span_months,
            values=values,
            missing_rate=missing_rate,
        )
        interval = result["prediction_interval"]
        if interval["lower"] is not None and interval["upper"] is not None:
            assert interval["lower"] <= interval["upper"], (
                f"lower ({interval['lower']}) > upper ({interval['upper']})"
            )


# ---------------------------------------------------------------------------

class TestPredictionConfidenceMonotonicityProperty21:
    """
    **Validates: Requirements 9.4**

    Property 21: 置信度单调性
    验证在其他因子固定时：
    - 数据量增加 → 置信度不降低
    - 缺失率增加 → 置信度不升高
    """

    @given(
        data_rows_low=st.integers(min_value=1, max_value=5000),
        data_rows_delta=st.integers(min_value=1, max_value=5000),
        time_span_months=_time_span_strategy,
        values=_values_strategy,
        missing_rate=_missing_rate_strategy,
    )
    @settings(max_examples=100)
    def test_more_data_rows_no_decrease(
        self, data_rows_low, data_rows_delta, time_span_months,
        values, missing_rate,
    ):
        """Increasing data_rows (other factors fixed) must not decrease score."""
        data_rows_high = data_rows_low + data_rows_delta

        score_low = PredictionServiceMixin._calculate_prediction_confidence(
            data_rows=data_rows_low,
            time_span_months=time_span_months,
            values=values,
            missing_rate=missing_rate,
        )["score"]

        score_high = PredictionServiceMixin._calculate_prediction_confidence(
            data_rows=data_rows_high,
            time_span_months=time_span_months,
            values=values,
            missing_rate=missing_rate,
        )["score"]

        assert score_high >= score_low, (
            f"Monotonicity violated: rows {data_rows_low} → {score_low}, "
            f"rows {data_rows_high} → {score_high}"
        )

    @given(
        data_rows=_data_rows_strategy,
        time_span_months=_time_span_strategy,
        values=_values_strategy,
        missing_rate_low=st.floats(
            min_value=0.0, max_value=0.5,
            allow_nan=False, allow_infinity=False,
        ),
        missing_rate_delta=st.floats(
            min_value=0.01, max_value=0.5,
            allow_nan=False, allow_infinity=False,
        ),
    )
    @settings(max_examples=100)
    def test_higher_missing_rate_no_increase(
        self, data_rows, time_span_months, values,
        missing_rate_low, missing_rate_delta,
    ):
        """Increasing missing_rate (other factors fixed) must not increase score."""
        missing_rate_high = min(1.0, missing_rate_low + missing_rate_delta)
        assume(missing_rate_high > missing_rate_low)

        score_low_mr = PredictionServiceMixin._calculate_prediction_confidence(
            data_rows=data_rows,
            time_span_months=time_span_months,
            values=values,
            missing_rate=missing_rate_low,
        )["score"]

        score_high_mr = PredictionServiceMixin._calculate_prediction_confidence(
            data_rows=data_rows,
            time_span_months=time_span_months,
            values=values,
            missing_rate=missing_rate_high,
        )["score"]

        assert score_high_mr <= score_low_mr, (
            f"Monotonicity violated: missing_rate {missing_rate_low} → {score_low_mr}, "
            f"missing_rate {missing_rate_high} → {score_high_mr}"
        )
