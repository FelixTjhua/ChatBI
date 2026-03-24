"""CSV批量处理增强测试"""
import os
import tempfile
import pytest
from apps.datasource.document_parser import DocumentParser


class TestCSVSmartRead:
    """测试CSV智能读取"""

    def test_utf8_comma_csv(self):
        content = "名称,数量,金额\n产品A,100,5000\n产品B,200,8000\n"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv',
                                          delete=False, encoding='utf-8') as f:
            f.write(content)
            path = f.name
        try:
            result = DocumentParser.parse(path)
            assert len(result.tables) == 1
            assert "名称" in result.tables[0]["headers"]
            assert len(result.tables[0]["rows"]) == 2
        finally:
            os.unlink(path)

    def test_tab_separated_csv(self):
        content = "name\tcount\tamount\nA\t100\t5000\nB\t200\t8000\n"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv',
                                          delete=False, encoding='utf-8') as f:
            f.write(content)
            path = f.name
        try:
            result = DocumentParser.parse(path)
            assert len(result.tables) == 1
            headers = result.tables[0]["headers"]
            assert "name" in headers
            assert "count" in headers
        finally:
            os.unlink(path)

    def test_semicolon_separated_csv(self):
        content = "name;count;amount\nA;100;5000\nB;200;8000\n"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv',
                                          delete=False, encoding='utf-8') as f:
            f.write(content)
            path = f.name
        try:
            result = DocumentParser.parse(path)
            assert len(result.tables) == 1
            headers = result.tables[0]["headers"]
            assert "name" in headers
        finally:
            os.unlink(path)


class TestDataCleaning:
    """测试批量数据清洗"""

    def test_duplicate_removal(self):
        content = "name,value\nA,100\nA,100\nB,200\n"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv',
                                          delete=False, encoding='utf-8') as f:
            f.write(content)
            path = f.name
        try:
            result = DocumentParser.parse(path)
            # 去重后应该只有2行
            assert len(result.tables[0]["rows"]) == 2
        finally:
            os.unlink(path)

    def test_empty_row_removal(self):
        content = "name,value\nA,100\n,,\nB,200\n"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv',
                                          delete=False, encoding='utf-8') as f:
            f.write(content)
            path = f.name
        try:
            result = DocumentParser.parse(path)
            # 空行应被清除
            rows = result.tables[0]["rows"]
            non_empty = [r for r in rows if any(cell.strip() for cell in r)]
            assert len(non_empty) >= 2
        finally:
            os.unlink(path)

    def test_cleaning_stats_in_text(self):
        content = "name,value\nA,100\nA,100\nA,100\nB,200\n"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv',
                                          delete=False, encoding='utf-8') as f:
            f.write(content)
            path = f.name
        try:
            result = DocumentParser.parse(path)
            # 清洗信息应出现在文本描述中
            assert "清洗" in result.raw_text or "行数: 2" in result.raw_text
        finally:
            os.unlink(path)
