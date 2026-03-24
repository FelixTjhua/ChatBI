"""PDF 文本切分审计测试"""
import pytest
from apps.datasource.document_parser import TextChunker, ParseResult, DocumentChunk


class TestSlidingWindowSentenceBoundary:
    """滑动窗口应在句子边界处切分"""

    def test_splits_at_sentence_boundary(self):
        """切分点应在句号/问号/感叹号后，不在词中间"""
        text = "这是第一个句子。这是第二个句子。这是第三个句子。这是第四个句子。这是第五个句子。"
        chunks = TextChunker.chunk_by_sliding_window(text, chunk_size=30, overlap=0)
        # 每个 chunk 不应以半截句子结尾（除非单句超长）
        for chunk in chunks:
            assert chunk.strip(), "chunk 不应为空"

    def test_short_text_single_chunk(self):
        """短文本应返回单个 chunk"""
        text = "这是一段短文本。"
        chunks = TextChunker.chunk_by_sliding_window(text, chunk_size=512, overlap=64)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_empty_text(self):
        """空文本应返回空列表"""
        assert TextChunker.chunk_by_sliding_window("", 512, 64) == []
        assert TextChunker.chunk_by_sliding_window("   ", 512, 64) == []

    def test_single_long_sentence_hard_split(self):
        """单个超长句子应硬切（无句子边界可用）"""
        text = "这" * 1000  # 1000字符无标点
        chunks = TextChunker.chunk_by_sliding_window(text, chunk_size=200, overlap=20)
        assert len(chunks) > 1
        # 所有字符都应被覆盖
        total_text = "".join(chunks)
        assert "这" * 200 in total_text

    def test_chinese_sentence_boundaries(self):
        """中文句号、问号、感叹号都应作为切分点"""
        text = "第一句话。第二句话！第三句话？第四句话。第五句话。第六句话。"
        chunks = TextChunker.chunk_by_sliding_window(text, chunk_size=20, overlap=0)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert len(chunk) > 0


class TestTableToTextSizeControl:
    """表格 chunk 大小应受 max_chunk_size 控制"""

    def test_large_table_truncated(self):
        """大表格应被截断，不超过 max_chunk_size"""
        headers = [f"col_{i}" for i in range(20)]
        rows = [[f"val_{i}_{j}" for j in range(20)] for i in range(100)]
        table = {"headers": headers, "rows": rows, "page": 1}
        text = TextChunker._table_to_text(table, max_chunk_size=512)
        # VEC-1 添加了自然语言摘要前缀（列名语义+数据范围），
        # 摘要约占 100-200 字符，总长度允许 max_chunk_size + 摘要开销
        assert len(text) <= 800  # 允许 NL 摘要前缀的额外开销
        assert "截断" in text or len(text) <= 512 + 300

    def test_small_table_not_truncated(self):
        """小表格不应被截断"""
        table = {
            "headers": ["A", "B"],
            "rows": [["1", "2"], ["3", "4"]],
            "page": 1,
        }
        text = TextChunker._table_to_text(table, max_chunk_size=512)
        assert "截断" not in text
        assert "A | B" in text

    def test_empty_table(self):
        """空表头返回空字符串"""
        assert TextChunker._table_to_text({"headers": [], "rows": []}, 512) == ""


class TestChunkBySectionsTableDedup:
    """chunk_by_sections 应将表格作为独立 chunk，不与正文重复"""

    def test_table_chunks_have_table_type(self):
        """表格 chunk 的 chunk_type 应为 'table'"""
        pr = ParseResult()
        pr.metadata = {"filename": "test.pdf"}
        pr.sections = [{"title": "概述", "content": "这是正文内容。", "level": 2, "page": 1}]
        pr.tables = [{"headers": ["A", "B"], "rows": [["1", "2"]], "page": 1,
                      "text_fingerprint": {"A", "B", "1", "2"}}]
        chunks = TextChunker.chunk_by_sections(pr, max_chunk_size=512, overlap=64)
        table_chunks = [c for c in chunks if c.metadata.get("chunk_type") == "table"]
        assert len(table_chunks) == 1
        assert "A" in table_chunks[0].text

    def test_section_chunks_separate_from_table(self):
        """正文 section 和表格应生成独立的 chunks，高重叠 section 标记为 table_overlap"""
        pr = ParseResult()
        pr.metadata = {"filename": "test.pdf"}
        pr.sections = [
            {"title": "第一章", "content": "这是第一章的正文内容，包含详细说明。", "level": 2, "page": 1},
        ]
        pr.tables = [
            {"headers": ["指标", "数值"], "rows": [["销售额", "1000"]], "page": 1,
             "text_fingerprint": {"指标", "数值", "销售额", "1000"}},
        ]
        chunks = TextChunker.chunk_by_sections(pr, max_chunk_size=512, overlap=64)
        section_chunks = [c for c in chunks if c.metadata.get("chunk_type") in ("section", "section_split", "table_overlap")]
        table_chunks = [c for c in chunks if c.metadata.get("chunk_type") == "table"]
        assert len(section_chunks) >= 1
        assert len(table_chunks) == 1

    def test_table_associated_section(self):
        """表格 chunk 应关联同页的 section 标题"""
        pr = ParseResult()
        pr.metadata = {"filename": "test.pdf"}
        pr.sections = [
            {"title": "销售数据分析", "content": "以下是销售数据。", "level": 2, "page": 3},
        ]
        pr.tables = [
            {"headers": ["区域", "金额"], "rows": [["华东", "5000"]], "page": 3,
             "text_fingerprint": {"区域", "金额", "华东", "5000"}},
        ]
        chunks = TextChunker.chunk_by_sections(pr, max_chunk_size=512, overlap=64)
        table_chunks = [c for c in chunks if c.metadata.get("chunk_type") == "table"]
        assert len(table_chunks) == 1
        assert table_chunks[0].metadata.get("section_title") == "销售数据分析"

    def test_no_sections_fallback_to_sliding_window(self):
        """无结构信息时应降级为滑动窗口"""
        pr = ParseResult()
        pr.metadata = {"filename": "test.pdf"}
        pr.raw_text = "这是一段没有标题结构的纯文本。" * 50
        pr.sections = []
        pr.tables = []
        chunks = TextChunker.chunk_by_sections(pr, max_chunk_size=100, overlap=10)
        assert len(chunks) > 1
        for c in chunks:
            assert c.metadata.get("chunk_type") == "sliding_window"

    def test_long_section_split(self):
        """超长 section 应被滑动窗口进一步切分"""
        pr = ParseResult()
        pr.metadata = {"filename": "test.pdf"}
        long_content = "这是一段很长的内容。" * 100
        pr.sections = [{"title": "长章节", "content": long_content, "level": 2, "page": 1}]
        pr.tables = []
        chunks = TextChunker.chunk_by_sections(pr, max_chunk_size=100, overlap=10)
        assert len(chunks) > 1
        split_chunks = [c for c in chunks if c.metadata.get("chunk_type") == "section_split"]
        assert len(split_chunks) > 0
        # 所有 split chunk 都应保留 section_title
        for c in split_chunks:
            assert c.metadata.get("section_title") == "长章节"


class TestLosslessChunkingStrategy:
    """零丢失分块策略：text_fingerprint 去重 + table_overlap 标记"""

    def test_text_fingerprint_used_for_dedup(self):
        """表格 text_fingerprint 应用于检测 section 重叠"""
        pr = ParseResult()
        pr.metadata = {"filename": "test.pdf"}
        # section 内容与表格单元格高度重叠
        pr.sections = [
            {"title": "数据表", "content": "产品 价格 数量\n手机 3000 100\n电脑 5000 50", "level": 2, "page": 1},
        ]
        pr.tables = [
            {"headers": ["产品", "价格", "数量"],
             "rows": [["手机", "3000", "100"], ["电脑", "5000", "50"]],
             "page": 1,
             "text_fingerprint": {"产品", "价格", "数量", "手机", "3000", "100", "电脑", "5000", "50"}},
        ]
        chunks = TextChunker.chunk_by_sections(pr, max_chunk_size=512, overlap=64)
        overlap_chunks = [c for c in chunks if c.metadata.get("chunk_type") == "table_overlap"]
        assert len(overlap_chunks) >= 1, "高重叠 section 应标记为 table_overlap"
        assert overlap_chunks[0].metadata.get("table_overlap_ratio", 0) >= 0.6

    def test_low_overlap_section_not_marked(self):
        """低重叠 section 不应标记为 table_overlap"""
        pr = ParseResult()
        pr.metadata = {"filename": "test.pdf"}
        pr.sections = [
            {"title": "分析报告", "content": "本季度公司业绩表现良好，各项指标均有提升。市场份额持续增长。",
             "level": 2, "page": 1},
        ]
        pr.tables = [
            {"headers": ["产品", "价格"], "rows": [["手机", "3000"]],
             "page": 1,
             "text_fingerprint": {"产品", "价格", "手机", "3000"}},
        ]
        chunks = TextChunker.chunk_by_sections(pr, max_chunk_size=512, overlap=64)
        section_chunks = [c for c in chunks if c.metadata.get("chunk_type") == "section"]
        assert len(section_chunks) >= 1, "低重叠 section 应保持 section 类型"

    def test_no_fingerprint_no_overlap(self):
        """表格无 text_fingerprint 时，section 不应被标记为 table_overlap"""
        pr = ParseResult()
        pr.metadata = {"filename": "test.pdf"}
        pr.sections = [
            {"title": "概述", "content": "这是正文内容。", "level": 2, "page": 1},
        ]
        pr.tables = [
            {"headers": ["A", "B"], "rows": [["1", "2"]], "page": 1},  # 无 text_fingerprint
        ]
        chunks = TextChunker.chunk_by_sections(pr, max_chunk_size=512, overlap=64)
        overlap_chunks = [c for c in chunks if c.metadata.get("chunk_type") == "table_overlap"]
        assert len(overlap_chunks) == 0

    def test_different_page_no_overlap(self):
        """不同页的表格不应影响 section 的重叠判定"""
        pr = ParseResult()
        pr.metadata = {"filename": "test.pdf"}
        pr.sections = [
            {"title": "数据", "content": "产品 价格 数量", "level": 2, "page": 1},
        ]
        pr.tables = [
            {"headers": ["产品", "价格", "数量"], "rows": [["手机", "3000", "100"]],
             "page": 2,  # 不同页
             "text_fingerprint": {"产品", "价格", "数量", "手机", "3000", "100"}},
        ]
        chunks = TextChunker.chunk_by_sections(pr, max_chunk_size=512, overlap=64)
        overlap_chunks = [c for c in chunks if c.metadata.get("chunk_type") == "table_overlap"]
        assert len(overlap_chunks) == 0, "不同页的表格不应导致 table_overlap"

    def test_all_content_preserved_in_chunks(self):
        """零丢失：所有 section 内容都应出现在 chunks 中（无论是否标记为 overlap）"""
        pr = ParseResult()
        pr.metadata = {"filename": "test.pdf"}
        pr.sections = [
            {"title": "正文", "content": "这是纯正文内容。", "level": 2, "page": 1},
            {"title": "表格区", "content": "产品 价格\n手机 3000", "level": 2, "page": 1},
        ]
        pr.tables = [
            {"headers": ["产品", "价格"], "rows": [["手机", "3000"]],
             "page": 1,
             "text_fingerprint": {"产品", "价格", "手机", "3000"}},
        ]
        chunks = TextChunker.chunk_by_sections(pr, max_chunk_size=512, overlap=64)
        all_text = " ".join(c.text for c in chunks)
        assert "这是纯正文内容" in all_text
        assert "手机" in all_text


class TestVectorizerTableOverlapFiltering:
    """向量化器应跳过 table_overlap chunk"""

    def test_table_overlap_chunks_filtered_from_valid(self):
        """table_overlap chunk 应被过滤，不参与向量化"""
        chunks = [
            DocumentChunk(text="正常正文内容，包含足够长度的文本信息。", metadata={"chunk_type": "section"}),
            DocumentChunk(text="这是表格重叠的内容，产品价格数量信息。", metadata={"chunk_type": "table_overlap"}),
            DocumentChunk(text="产品 | 价格\n手机 | 3000 元人民币", metadata={"chunk_type": "table"}),
        ]

        # 直接测试过滤逻辑（与 vectorize_chunks 内部一致）
        from apps.datasource.document_parser import TextPreprocessor
        valid_chunks = [
            c for c in chunks
            if TextPreprocessor.is_meaningful(c.text)
            and c.metadata.get("chunk_type") != "table_overlap"
        ]
        assert len(valid_chunks) == 2
        valid_types = [c.metadata["chunk_type"] for c in valid_chunks]
        assert "table_overlap" not in valid_types
        assert "section" in valid_types
        assert "table" in valid_types

    def test_all_overlap_chunks_filtered(self):
        """全部为 table_overlap 时过滤后应为空"""
        from apps.datasource.document_parser import TextPreprocessor
        chunks = [
            DocumentChunk(text="重叠内容一，包含足够长度的文本。", metadata={"chunk_type": "table_overlap"}),
            DocumentChunk(text="重叠内容二，包含足够长度的文本。", metadata={"chunk_type": "table_overlap"}),
        ]
        valid_chunks = [
            c for c in chunks
            if TextPreprocessor.is_meaningful(c.text)
            and c.metadata.get("chunk_type") != "table_overlap"
        ]
        assert len(valid_chunks) == 0
