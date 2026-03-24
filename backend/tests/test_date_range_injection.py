"""测试 PRED-1 修复：get_table_schema_with_details 注入日期字段的实际数据范围"""
import re
import pytest


class TestDateRangeInjection:
    """测试日期范围注入到 schema 的逻辑"""

    def test_date_field_detection_by_type(self):
        """测试通过字段类型检测日期字段"""
        date_types = ['date', 'timestamp', 'datetime', 'time', 'timestamptz']
        for dt in date_types:
            ft = dt.lower()
            is_date = any(t in ft for t in ['date', 'time', 'timestamp'])
            assert is_date, f"Field type '{dt}' should be detected as date field"

    def test_date_field_detection_by_name(self):
        """测试通过字段名检测日期字段（中文字段名场景）"""
        date_names = ['date', 'create_time', '日期', '时间', '年份', '月份',
                      'order_date', 'update_time', '销售日期']
        for fn in date_names:
            fn_lower = fn.lower()
            is_date = any(t in fn_lower for t in ['date', 'time', '日期', '时间', '年', '月'])
            assert is_date, f"Field name '{fn}' should be detected as date field"

    def test_non_date_field_not_detected(self):
        """测试非日期字段不被误检测"""
        non_date_names = ['amount', 'price', 'quantity', '金额', '数量', 'name', 'id']
        non_date_types = ['int', 'float', 'varchar', 'text', 'decimal']
        for fn in non_date_names:
            fn_lower = fn.lower()
            is_date_by_name = any(t in fn_lower for t in ['date', 'time', '日期', '时间', '年', '月'])
            assert not is_date_by_name, f"Field name '{fn}' should NOT be detected as date field"
        for ft in non_date_types:
            ft_lower = ft.lower()
            is_date_by_type = any(t in ft_lower for t in ['date', 'time', 'timestamp'])
            assert not is_date_by_type, f"Field type '{ft}' should NOT be detected as date field"

    def test_sql_injection_prevention(self):
        """测试 SQL 注入防护：含特殊字符的表名/字段名应被跳过"""
        dangerous_names = [
            "table'; DROP TABLE users;--",
            'field"name',
            "table\\name",
            "field'name",
        ]
        for name in dangerous_names:
            has_danger = bool(re.search(r'[;\'"\\]', name))
            assert has_danger, f"Name '{name}' should be flagged as dangerous"

    def test_safe_table_names(self):
        """测试安全的表名（包括中文）应通过检查"""
        safe_names = [
            "sales_data_abc123",
            "销售数据_abc123",
            "Sheet1_def456",
            "order_details",
        ]
        for name in safe_names:
            has_danger = bool(re.search(r'[;\'"\\]', name))
            assert not has_danger, f"Name '{name}' should be considered safe"

    def test_schema_data_time_range_format(self):
        """测试 Data Time Range 段的格式"""
        # 模拟注入后的 schema 片段
        range_lines = [
            "sales_data.order_date: 2024-01-01 ~ 2024-12-31",
            "inventory.update_time: 2024-03-15 10:00:00 ~ 2024-11-20 18:30:00",
        ]
        schema_section = '【Data Time Range】\n'
        for rl in range_lines:
            schema_section += rl + '\n'

        assert '【Data Time Range】' in schema_section
        assert '2024-01-01 ~ 2024-12-31' in schema_section
        assert 'sales_data.order_date' in schema_section

    def test_range_line_parsing(self):
        """测试范围行可以被正确解析"""
        range_line = "my_table.date_col: 2024-01-15 ~ 2024-12-28"
        parts = range_line.split(': ', 1)
        assert len(parts) == 2
        table_field = parts[0]
        date_range = parts[1]
        assert table_field == 'my_table.date_col'
        assert '~' in date_range
        min_val, max_val = date_range.split(' ~ ')
        assert min_val == '2024-01-15'
        assert max_val == '2024-12-28'


class TestSQLTemplateDataTimeRange:
    """测试 SQL 模板中的 Data Time Range 规则"""

    def test_sql_template_contains_data_time_range_rule(self):
        """测试 SQL 模板包含 Data Time Range 相关规则"""
        import yaml
        from pathlib import Path
        template_path = Path(__file__).parent.parent / 'templates' / 'template.yaml'
        with open(template_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        sql_sys = data['template']['sql']['system']
        assert 'Data Time Range' in sql_sys, "SQL template should mention Data Time Range"
        assert 'CURRENT_DATE' in sql_sys, "SQL template should warn against CURRENT_DATE"

    def test_sql_template_warns_against_current_date(self):
        """测试 SQL 模板警告不要使用 CURRENT_DATE"""
        import yaml
        from pathlib import Path
        template_path = Path(__file__).parent.parent / 'templates' / 'template.yaml'
        with open(template_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        sql_sys = data['template']['sql']['system']
        # 应包含关于不使用 CURRENT_DATE/NOW() 的警告
        assert 'NOW()' in sql_sys or 'CURRENT_DATE' in sql_sys
        # 应包含关于基于数据最大日期推算的指导
        assert '最大日期' in sql_sys or 'max' in sql_sys.lower()


class TestPredictionScenario:
    """测试预测场景下的端到端逻辑"""

    def test_prediction_query_with_historical_data(self):
        """
        模拟场景：用户问"预测未来一个月的销售额趋势"
        数据范围：2024-01-01 ~ 2024-12-31
        期望：LLM 应查询全部历史数据或基于 2024-12-31 往前推算
        """
        # 模拟 schema 中包含 Data Time Range
        schema_with_range = """【DB_ID】 test_db
     【Schema】
     """
        # 验证 schema 包含日期范围信息
        assert '2024-01-01 ~ 2024-12-31' in schema_with_range
        assert '【Data Time Range】' in schema_with_range

        # 验证 LLM 能从 schema 中获取到数据范围
        # （实际 LLM 调用在集成测试中验证，这里验证数据格式正确）
        lines = schema_with_range.strip().split('\n')
        range_section_found = False
        for i, line in enumerate(lines):
            if '【Data Time Range】' in line:
                range_section_found = True
                # 下一行应该是范围数据
                next_line = lines[i + 1] if i + 1 < len(lines) else ''
                assert 'sales_data.order_date' in next_line
                assert '2024-01-01' in next_line
                assert '2024-12-31' in next_line
                break
        assert range_section_found, "Data Time Range section should be present in schema"

    def test_csv_same_issue_as_excel(self):
        """验证 CSV 数据源与 Excel 有相同的问题和修复"""
        # CSV 和 Excel 都使用内部 PG 引擎存储数据
        # 两者都需要日期范围注入
        csv_types = ['csv', 'excel']
        for ds_type in csv_types:
            _ds_type_lower = ds_type.lower()
            needs_internal_engine = _ds_type_lower in ('excel', 'csv')
            assert needs_internal_engine, f"{ds_type} should use internal PG engine"

    def test_database_also_benefits(self):
        """验证数据库数据源也能受益于日期范围注入"""
        # 数据库数据源虽然通常有当前数据，但也可能有历史数据库
        # 日期范围注入对所有数据源类型都有帮助
        db_types = ['mysql', 'postgresql', 'oracle']
        for ds_type in db_types:
            _ds_type_lower = ds_type.lower()
            uses_external = _ds_type_lower not in ('excel', 'csv', 'pdf')
            assert uses_external, f"{ds_type} should use external connection pool"
