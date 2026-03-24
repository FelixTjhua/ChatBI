"""上下文压缩按数据源类型的集成测试"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.chat.thinking.context_compressor import ContextCompressor


# ============================================================

def _make_large_schema(num_tables=20, fields_per_table=15):
    """构造一个足够大的数据库 Schema（模拟多表多字段场景）"""
    parts = []
    for i in range(num_tables):
        header = f"Table sales_data_{i:03d} (销售数据表{i})"
        fields = []
        for j in range(fields_per_table):
            fields.append(f"  - field_{j:02d} INT COMMENT '字段{j}的描述信息，用于存储业务数据'")
        parts.append(header + "\n" + "\n".join(fields))
    return "\n\n".join(parts)


def _make_small_schema(num_tables=2, fields_per_table=5):
    """构造一个较小的 Schema（模拟 Excel/CSV 单表或少表场景）"""
    parts = []
    for i in range(num_tables):
        header = f"Table sheet_{i} (工作表{i})"
        fields = []
        for j in range(fields_per_table):
            fields.append(f"  - col_{j} VARCHAR COMMENT '列{j}'")
        parts.append(header + "\n" + "\n".join(fields))
    return "\n\n".join(parts)


def _make_terminologies(count=10):
    """构造术语 XML"""
    terms = []
    words = ["销售额", "毛利率", "净利润", "客户数", "订单量", "库存周转率",
             "应收账款", "资产负债率", "现金流", "市场份额", "复购率", "客单价"]
    for i in range(min(count, len(words))):
        terms.append(
            f"<terminology>"
            f"<word>{words[i]}</word>"
            f"<description>{words[i]}是商业经营中的重要指标，用于衡量业务表现和财务健康状况，"
            f"通常按月度、季度、年度进行统计分析，支持同比环比对比</description>"
            f"<sql_mapping>SELECT {words[i]} FROM business_metrics WHERE period = '2024'</sql_mapping>"
            f"</terminology>"
        )
    return "\n".join(terms)


def _make_sql_examples(count=8):
    """构造 SQL 示例 XML"""
    examples = []
    questions = [
        "查询各产品销售额排名", "统计每月销售趋势", "对比各区域利润",
        "查询销售额前10的产品", "统计客户复购率", "分析库存周转情况",
        "查询应收账款明细", "统计各部门业绩",
    ]
    for i in range(min(count, len(questions))):
        examples.append(
            f"<example>"
            f"<question>{questions[i]}</question>"
            f"<sql>SELECT product_name, SUM(amount) as total_sales "
            f"FROM sales_data_{i:03d} "
            f"WHERE date >= '2024-01-01' "
            f"GROUP BY product_name "
            f"ORDER BY total_sales DESC "
            f"LIMIT 10</sql>"
            f"</example>"
        )
    return "<sql-examples>\n" + "\n".join(examples) + "\n</sql-examples>"


def _make_document_knowledge(count=5):
    """构造 PDF 文档知识块"""
    chunks = []
    for i in range(count):
        chunks.append(
            f"<chunk page='{i+1}' section='第{i+1}章 业务规范' similarity='0.{70+i}'>"
            f"本章节详细描述了商业在{['生产', '销售', '采购', '物流', '财务'][i % 5]}环节的操作规范和质量要求。"
            f"所有相关人员必须严格遵守本规范中的各项条款，确保业务流程的合规性和高效性。"
            f"违反本规范的行为将按照公司管理制度进行处理。具体要求如下：..."
            f"</chunk>"
        )
    return "<document-knowledge>\n" + "\n".join(chunks) + "\n</document-knowledge>"


# ============================================================

class TestDatabaseCompression:
    """数据库数据源：Schema(大) + 术语 + SQL示例 → 最容易触发压缩"""

    def test_large_schema_triggers_compression(self):
        """多表多字段的 Schema 应触发压缩"""
        schema = _make_large_schema(num_tables=20, fields_per_table=15)
        terminologies = _make_terminologies(10)
        sql_examples = _make_sql_examples(8)

        result = ContextCompressor.compress(
            schema=schema,
            terminologies=terminologies,
            sql_examples=sql_examples,
            question="查询各产品的销售额和毛利率",
            max_total_tokens=4000,
        )

        assert result['compression_applied'] is True, (
            f"Database large schema should trigger compression. "
            f"Original: {result['stats'].get('original_length')}, "
            f"Estimated tokens: {ContextCompressor._estimate_tokens(schema + terminologies + sql_examples)}"
        )
        assert result['stats']['compressed_length'] < result['stats']['original_length']
        # 压缩后的内容不应为空
        assert len(result['schema']) > 0
        assert len(result['terminologies']) > 0

    def test_small_schema_no_compression(self):
        """少量表字段不应触发压缩"""
        schema = _make_small_schema(num_tables=1, fields_per_table=3)
        terminologies = _make_terminologies(2)
        sql_examples = _make_sql_examples(2)

        result = ContextCompressor.compress(
            schema=schema,
            terminologies=terminologies,
            sql_examples=sql_examples,
            question="查询销售额",
            max_total_tokens=4000,
        )

        assert result['compression_applied'] is False, (
            f"Small database should not trigger compression. "
            f"Estimated tokens: {ContextCompressor._estimate_tokens(schema + terminologies + sql_examples)}"
        )

    def test_compress_with_reranking_database(self):
        """compress_with_reranking 在数据库场景下的效果"""
        schema = _make_large_schema(num_tables=15, fields_per_table=10)
        terminologies = _make_terminologies(8)
        sql_examples = _make_sql_examples(6)

        term_results = [
            {"word": "销售额", "rerank_score": 0.9, "similarity": 0.95},
            {"word": "毛利率", "rerank_score": 0.7, "similarity": 0.80},
        ]
        sql_results = [
            {"question": "查询销售额排名", "rerank_score": 0.8, "similarity": 0.85},
        ]

        result = ContextCompressor.compress_with_reranking(
            schema=schema,
            terminologies=terminologies,
            sql_examples=sql_examples,
            question="查询各产品的销售额排名",
            terminology_results=term_results,
            sql_example_results=sql_results,
            max_total_tokens=4000,
        )

        assert result['compression_applied'] is True
        assert result['stats']['compressed_length'] < result['stats']['original_length']


# ============================================================

class TestExcelCompression:
    """Excel 数据源：数据导入PG后有 Schema + 术语 + SQL示例"""

    def test_excel_large_data_triggers_compression(self):
        """Excel 多列多术语场景应触发压缩"""
        # Excel 导入PG后通常只有1-3张表，但字段可能很多
        schema = _make_small_schema(num_tables=3, fields_per_table=20)
        terminologies = _make_terminologies(10)
        sql_examples = _make_sql_examples(8)

        total = schema + terminologies + sql_examples
        estimated = ContextCompressor._estimate_tokens(total)

        result = ContextCompressor.compress(
            schema=schema,
            terminologies=terminologies,
            sql_examples=sql_examples,
            question="统计每月销售趋势",
            max_total_tokens=4000,
        )

        if estimated > 4000:
            assert result['compression_applied'] is True, (
                f"Excel with large content should compress. Estimated tokens: {estimated}"
            )
        else:
            # 内容不够大，不触发压缩也是正确的
            assert result['compression_applied'] is False

    def test_excel_typical_no_compression(self):
        """典型 Excel 场景（少量列、少量术语）不触发压缩"""
        schema = _make_small_schema(num_tables=1, fields_per_table=5)
        terminologies = _make_terminologies(3)
        sql_examples = _make_sql_examples(3)

        result = ContextCompressor.compress(
            schema=schema,
            terminologies=terminologies,
            sql_examples=sql_examples,
            question="查询销售额",
            max_total_tokens=4000,
        )

        estimated = ContextCompressor._estimate_tokens(schema + terminologies + sql_examples)
        if estimated <= 4000:
            assert result['compression_applied'] is False


# ============================================================

class TestCSVCompression:
    """CSV 数据源：与 Excel 一致，数据导入PG后走SQL路径"""

    def test_csv_same_as_excel(self):
        """CSV 和 Excel 走完全相同的压缩逻辑"""
        schema = _make_small_schema(num_tables=1, fields_per_table=10)
        terminologies = _make_terminologies(5)
        sql_examples = _make_sql_examples(5)

        result_csv = ContextCompressor.compress(
            schema=schema,
            terminologies=terminologies,
            sql_examples=sql_examples,
            question="统计各产品销售额",
            max_total_tokens=4000,
        )

        # 相同输入应产生相同输出（压缩是确定性的）
        result_excel = ContextCompressor.compress(
            schema=schema,
            terminologies=terminologies,
            sql_examples=sql_examples,
            question="统计各产品销售额",
            max_total_tokens=4000,
        )

        assert result_csv['compression_applied'] == result_excel['compression_applied']
        assert result_csv['stats'] == result_excel['stats']


# ============================================================

class TestPDFCompression:
    """PDF 数据源：无 Schema、无 SQL 示例、无术语，只有文档知识块"""

    def test_pdf_no_schema_no_sql(self):
        """PDF 场景：空 Schema + 空 SQL 示例 + 空术语 → 不触发压缩"""
        result = ContextCompressor.compress(
            schema="",
            terminologies="",
            sql_examples="",
            question="文档中关于清洁的说明是什么",
            max_total_tokens=4000,
        )

        assert result['compression_applied'] is False, (
            "PDF with no content should not compress."
        )

    def test_pdf_with_document_knowledge_block(self):
        """PDF 场景：文档知识块作为 sql_examples 传入时的压缩行为（无术语）"""
        doc_knowledge = _make_document_knowledge(10)

        # PDF 场景下 document-knowledge 块通过 sql_examples 参数传入
        result = ContextCompressor.compress(
            schema="",
            terminologies="",
            sql_examples=doc_knowledge,
            question="文档中关于生产规范的要求",
            max_total_tokens=4000,
        )

        estimated = ContextCompressor._estimate_tokens(doc_knowledge)

        if estimated > 4000:
            assert result['compression_applied'] is True
            # 文档知识块应被保留（不应被清空）
            assert '<document-knowledge>' in result['sql_examples'] or len(result['sql_examples']) > 0
        else:
            assert result['compression_applied'] is False

    def test_pdf_large_document_knowledge_triggers_compression(self):
        """PDF 大量文档知识块应触发压缩（无术语）"""
        # 构造足够大的文档知识块
        doc_knowledge = _make_document_knowledge(20)

        estimated = ContextCompressor._estimate_tokens(doc_knowledge)

        result = ContextCompressor.compress(
            schema="",
            terminologies="",
            sql_examples=doc_knowledge,
            question="文档中关于各环节的规范要求",
            max_total_tokens=2000,  # 降低阈值确保触发
        )

        if estimated > 2000:
            assert result['compression_applied'] is True
            assert result['stats']['compressed_length'] <= result['stats']['original_length']

    def test_pdf_compress_with_reranking_detects_doc_knowledge(self):
        """compress_with_reranking 应检测到 document-knowledge 并调整预算分配（无术语）"""
        doc_knowledge = _make_document_knowledge(15)

        result = ContextCompressor.compress_with_reranking(
            schema="",
            terminologies="",
            sql_examples=doc_knowledge,
            question="文档中的业务规范",
            terminology_results=[],
            sql_example_results=[],
            max_total_tokens=2000,  # 降低阈值确保触发
        )

        estimated = ContextCompressor._estimate_tokens(doc_knowledge)

        if estimated > 2000:
            assert result['compression_applied'] is True
            # 文档知识块应被保留
            assert len(result['sql_examples']) > 0


# ============================================================

class TestCrossDatasourceComparison:
    """跨数据源类型的压缩行为对比"""

    def test_database_compresses_more_than_pdf(self):
        """数据库场景的压缩量应大于 PDF 场景（因为内容更多）"""
        # Database: 大 Schema + 术语 + SQL示例
        db_schema = _make_large_schema(15, 10)
        db_terms = _make_terminologies(8)
        db_sql = _make_sql_examples(6)

        db_result = ContextCompressor.compress(
            schema=db_schema, terminologies=db_terms, sql_examples=db_sql,
            question="查询销售额", max_total_tokens=4000,
        )

        # PDF: 无 Schema + 无术语 + 文档知识块
        pdf_doc = _make_document_knowledge(5)

        pdf_result = ContextCompressor.compress(
            schema="", terminologies="", sql_examples=pdf_doc,
            question="文档中的说明", max_total_tokens=4000,
        )

        db_original = db_result['stats'].get('original_length', 0)
        pdf_original = pdf_result['stats'].get('original_length', 0)

        # 数据库场景的原始内容应该更大
        assert db_original > pdf_original, (
            f"Database original ({db_original}) should be larger than PDF ({pdf_original})"
        )

    def test_all_types_preserve_output_structure(self):
        """所有数据源类型压缩后都应返回完整的结果结构"""
        scenarios = {
            'database': {
                'schema': _make_large_schema(10, 10),
                'terminologies': _make_terminologies(5),
                'sql_examples': _make_sql_examples(5),
            },
            'excel': {
                'schema': _make_small_schema(2, 10),
                'terminologies': _make_terminologies(5),
                'sql_examples': _make_sql_examples(5),
            },
            'csv': {
                'schema': _make_small_schema(1, 8),
                'terminologies': _make_terminologies(3),
                'sql_examples': _make_sql_examples(3),
            },
            'pdf': {
                'schema': "",
                'terminologies': "",
                'sql_examples': _make_document_knowledge(5),
            },
        }

        required_keys = {'terminologies', 'sql_examples', 'schema', 'compression_applied', 'stats'}

        for ds_type, inputs in scenarios.items():
            result = ContextCompressor.compress(
                question="测试查询",
                max_total_tokens=4000,
                **inputs,
            )

            missing = required_keys - set(result.keys())
            assert not missing, (
                f"[{ds_type}] Missing keys in compression result: {missing}"
            )
            assert isinstance(result['compression_applied'], bool), (
                f"[{ds_type}] compression_applied should be bool"
            )
            assert isinstance(result['stats'], dict), (
                f"[{ds_type}] stats should be dict"
            )
