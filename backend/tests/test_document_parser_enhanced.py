"""测试增强后的文档解析器"""
import pytest
from apps.datasource.document_parser import DocumentParser, TextChunker, ParseResult


class TestTableNaturalLanguageDescription:
    """测试表格自然语言描述生成"""

    def test_table_to_text_includes_description(self):
        """表格转文本应包含自然语言描述"""
        table = {
            "headers": ["区域", "营收", "利润"],
            "rows": [
                ["华东", "5000", "1200"],
                ["华北", "3800", "900"],
            ],
            "page": 12,
        }
        text = TextChunker._table_to_text(table)
        # 应包含字段描述
        assert "区域" in text
        assert "营收" in text
        # 应包含自然语言摘要
        assert "华东" in text
        assert "5000" in text
        # 应包含来源信息
        assert "第12页" in text

    def test_table_to_text_with_sheet(self):
        """Excel表格应包含工作表信息"""
        table = {
            "headers": ["产品", "销量"],
            "rows": [["A", "100"]],
            "page": 1,
            "sheet": "销售数据",
        }
        text = TextChunker._table_to_text(table)
        assert "销售数据" in text

    def test_table_to_text_empty_headers(self):
        """空表头应返回空字符串"""
        table = {"headers": [], "rows": []}
        text = TextChunker._table_to_text(table)
        assert text == ""

    def test_table_to_text_preserves_raw_data(self):
        """应保留原始数据行（Markdown格式）"""
        table = {
            "headers": ["A", "B"],
            "rows": [["1", "2"], ["3", "4"]],
            "page": 1,
        }
        text = TextChunker._table_to_text(table)
        # _table_to_text 输出 Markdown 表格格式
        assert "| A | B |" in text
        assert "| 1 | 2 |" in text
        assert "| 3 | 4 |" in text


class TestColumnClassification:
    """测试维度-指标列分类"""

    def test_numeric_columns_as_metrics(self):
        """数值列应被识别为指标"""
        import pandas as pd
        df = pd.DataFrame({
            "日期": ["2025-01", "2025-02"],
            "销售额": [1000, 1200],
            "利润": [200, 300],
        })
        dims, metrics = DocumentParser._classify_columns(df)
        assert "销售额" in metrics
        assert "利润" in metrics

    def test_time_columns_as_dimensions(self):
        """时间列应被识别为维度"""
        import pandas as pd
        df = pd.DataFrame({
            "日期": ["2025-01", "2025-02"],
            "金额": [1000, 1200],
        })
        dims, metrics = DocumentParser._classify_columns(df)
        assert "日期" in dims

    def test_category_columns_as_dimensions(self):
        """分类列应被识别为维度"""
        import pandas as pd
        df = pd.DataFrame({
            "产品类型": ["A", "B", "A"],
            "数量": [10, 20, 30],
        })
        dims, metrics = DocumentParser._classify_columns(df)
        assert "产品类型" in dims
        assert "数量" in metrics


class TestSemanticChunking:
    """测试语义分块生成"""

    def test_generates_chunks_by_dimension(self):
        """应按维度分组生成语义分块"""
        import pandas as pd
        df = pd.DataFrame({
            "区域": ["华东", "华东", "华北", "华北"],
            "销售额": [1000, 1200, 800, 900],
        })
        chunks = DocumentParser._generate_semantic_chunks(
            df, "Sheet1", ["区域"], ["销售额"]
        )
        assert len(chunks) >= 2
        # 应包含华东和华北的分块
        texts = [c[0] for c in chunks]
        assert any("华东" in t for t in texts)
        assert any("华北" in t for t in texts)

    def test_empty_data_returns_empty(self):
        """空数据应返回空列表"""
        import pandas as pd
        df = pd.DataFrame()
        chunks = DocumentParser._generate_semantic_chunks(df, "Sheet1", [], [])
        assert chunks == []

    def test_chunk_limit(self):
        """分块数量应有上限"""
        import pandas as pd
        df = pd.DataFrame({
            "category": [f"cat_{i}" for i in range(50)],
            "value": list(range(50)),
        })
        chunks = DocumentParser._generate_semantic_chunks(
            df, "Sheet1", ["category"], ["value"]
        )
        assert len(chunks) <= 20


class TestDocumentContextFormatting:
    """测试文档检索结果溯源标注"""

    def test_format_includes_source_tracing(self):
        """格式化结果应包含溯源标注"""
        from apps.datasource.document_retrieval import format_document_context
        chunks = [{
            "text": "2024年营收为8500万元",
            "source_name": "年度报告.pdf",
            "source_type": "file",
            "section_title": "财务概况",
            "page_number": 15,
            "chunk_type": "section",
            "similarity": 0.85,
        }]
        context = format_document_context(chunks)
        assert "年度报告.pdf" in context
        assert "第15页" in context
        assert "财务概况" in context
        assert "85%" in context

    def test_format_table_chunk_label(self):
        """表格类型分块应标注'表格数据'"""
        from apps.datasource.document_retrieval import format_document_context
        chunks = [{
            "text": "区域 | 营收\n华东 | 5000",
            "source_name": "report.pdf",
            "source_type": "file",
            "page_number": 3,
            "chunk_type": "table",
            "similarity": 0.7,
        }]
        context = format_document_context(chunks)
        assert "表格数据" in context

    def test_format_empty_chunks(self):
        """空分块列表应返回空字符串"""
        from apps.datasource.document_retrieval import format_document_context
        assert format_document_context([]) == ""
