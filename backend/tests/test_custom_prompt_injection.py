"""测试自定义提示词注入链路（v4 全量注入版）："""
import pytest
from unittest.mock import MagicMock
from common.chatbi.custom_prompt import (
    find_relevant_custom_prompts,
    CustomPromptTypeEnum,
    PromptSQL,
    PromptAnalysis,
    PromptForecast,
)


def _make_mock_session(prompts):
    """创建mock session，模拟 session.exec(stmt).all() 返回"""
    session = MagicMock()
    mock_result = MagicMock()
    mock_result.all.return_value = prompts
    session.exec.return_value = mock_result
    return session


class TestFullInjection:
    """测试全量注入行为：所有提示词均应注入"""

    def test_all_prompts_injected(self):
        """所有提示词全量注入，不做关键词筛选"""
        prompts = [
            PromptAnalysis(id=1, oid=1, name="全局分析规则", prompt="请使用标准分析格式"),
            PromptAnalysis(id=2, oid=1, name="不相关规则", prompt="无关内容也应注入"),
        ]
        session = _make_mock_session(prompts)

        content, details = find_relevant_custom_prompts(
            session, CustomPromptTypeEnum.ANALYSIS, 1, "随便问个问题"
        )

        injected = [d for d in details if d['reason'] == 'intent_inject']
        assert len(injected) == 2, f"全量注入应注入所有提示词，实际: {len(injected)}"
        assert "标准分析格式" in content
        assert "无关内容也应注入" in content

    def test_all_reasons_are_intent_inject(self):
        """所有注入的提示词 reason 均为 intent_inject"""
        prompts = [
            PromptSQL(id=1, oid=1, name="规则A", prompt="内容A"),
            PromptSQL(id=2, oid=1, name="规则B", prompt="内容B"),
            PromptSQL(id=3, oid=1, name="规则C", prompt="内容C"),
        ]
        session = _make_mock_session(prompts)

        content, details = find_relevant_custom_prompts(
            session, CustomPromptTypeEnum.GENERATE_SQL, 1, "任意问题"
        )

        for d in details:
            assert d['reason'] == 'intent_inject'
            assert d['score'] == 1.0

    def test_empty_prompts(self):
        """无提示词时应返回空"""
        session = _make_mock_session([])
        content, details = find_relevant_custom_prompts(
            session, CustomPromptTypeEnum.GENERATE_SQL, 1, "查询数据"
        )
        assert content == ""
        assert details == []


class TestDatasourceFilter:
    """测试数据源过滤逻辑"""

    def test_specific_ds_not_matched(self):
        """specific_ds=True 且 ds_id 不匹配时应跳过"""
        prompts = [
            PromptSQL(id=1, oid=1, name="特定数据源规则", prompt="仅限数据源1",
                      specific_ds=True, datasource_ids=[1]),
        ]
        session = _make_mock_session(prompts)

        content, details = find_relevant_custom_prompts(
            session, CustomPromptTypeEnum.GENERATE_SQL, 1, "查询销售额", ds_id=999
        )

        not_matched = [d for d in details if d['reason'] == 'not_matched']
        assert len(not_matched) == 1
        assert "数据源不匹配" in not_matched[0]['detail']

    def test_specific_ds_matched(self):
        """specific_ds=True 且 ds_id 匹配时应注入"""
        prompts = [
            PromptSQL(id=1, oid=1, name="特定数据源规则", prompt="仅限数据源1",
                      specific_ds=True, datasource_ids=[1]),
        ]
        session = _make_mock_session(prompts)

        content, details = find_relevant_custom_prompts(
            session, CustomPromptTypeEnum.GENERATE_SQL, 1, "查询销售额", ds_id=1
        )

        injected = [d for d in details if d['reason'] == 'intent_inject']
        assert len(injected) == 1
        assert "仅限数据源1" in content

    def test_specific_ds_no_context(self):
        """specific_ds=True 但无 ds_id 上下文时应跳过"""
        prompts = [
            PromptSQL(id=1, oid=1, name="限定数据源", prompt="限定内容",
                      specific_ds=True, datasource_ids=[1]),
        ]
        session = _make_mock_session(prompts)

        content, details = find_relevant_custom_prompts(
            session, CustomPromptTypeEnum.GENERATE_SQL, 1, "查询数据"
        )

        not_matched = [d for d in details if d['reason'] == 'not_matched']
        assert len(not_matched) == 1
        assert "无数据源上下文" in not_matched[0]['detail']

    def test_non_specific_ds_always_injected(self):
        """specific_ds=False 的提示词无论 ds_id 如何都应注入"""
        prompts = [
            PromptSQL(id=1, oid=1, name="通用规则", prompt="通用内容", specific_ds=False),
        ]
        session = _make_mock_session(prompts)

        content, details = find_relevant_custom_prompts(
            session, CustomPromptTypeEnum.GENERATE_SQL, 1, "查询数据", ds_id=999
        )

        injected = [d for d in details if d['reason'] == 'intent_inject']
        assert len(injected) == 1


class TestSQLPromptInjection:
    """测试 SQL生成 提示词全量注入"""

    def test_sql_prompts_all_injected(self):
        prompts = [
            PromptSQL(id=1, oid=1, name="GMV mapping", prompt="GMV表示商品交易总额"),
            PromptSQL(id=2, oid=1, name="JOIN rules", prompt="关联查询时使用LEFT JOIN"),
        ]
        session = _make_mock_session(prompts)

        content, details = find_relevant_custom_prompts(
            session, CustomPromptTypeEnum.GENERATE_SQL, 1, "查询GMV数据的关联表"
        )

        injected = [d for d in details if d['reason'] == 'intent_inject']
        assert len(injected) == 2
        assert "GMV表示商品交易总额" in content
        assert "关联查询时使用LEFT JOIN" in content


class TestPredictPromptInjection:
    """测试数据预测提示词全量注入"""

    def test_predict_prompts_all_injected(self):
        prompts = [
            PromptForecast(id=1, oid=1, name="预测 method", prompt="根据数据特征选择合适的预测方法"),
            PromptForecast(id=2, oid=1, name="销售额 forecast", prompt="预测结果需标注置信度"),
        ]
        session = _make_mock_session(prompts)

        content, details = find_relevant_custom_prompts(
            session, CustomPromptTypeEnum.PREDICT_DATA, 1, "预测下个月的销售额趋势"
        )

        injected = [d for d in details if d['reason'] == 'intent_inject']
        assert len(injected) == 2
        assert "预测方法" in content
        assert "置信度" in content

    def test_predict_content_wrapped(self):
        """验证预测提示词可以被正确包裹"""
        prompts = [
            PromptForecast(id=1, oid=1, name="预测方法", prompt="根据数据特征选择预测方法"),
        ]
        session = _make_mock_session(prompts)

        content, details = find_relevant_custom_prompts(
            session, CustomPromptTypeEnum.PREDICT_DATA, 1, "预测销售额"
        )

        assert content.strip() != ""

        # 模拟 _wrap_custom_prompt 逻辑
        def _wrap_custom_prompt(custom_prompt: str, tag: str = 'Custom-Prompt') -> str:
            if custom_prompt and custom_prompt.strip():
                lines = custom_prompt.strip().split('\n')
                wrapped_lines = '\n'.join(f'<content>{line}</content>' for line in lines if line.strip())
                return f'<{tag}>\n{wrapped_lines}\n</{tag}>'
            return ''

        wrapped = _wrap_custom_prompt(content, 'Data-Prediction-Prompt')
        assert "<Data-Prediction-Prompt>" in wrapped
        assert "预测方法" in wrapped
