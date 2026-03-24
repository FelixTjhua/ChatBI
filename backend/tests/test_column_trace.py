"""列名追踪测试 — 验证 Excel/CSV 导入链路中列名是否被修改"""
import os
import sys
import pandas as pd
import pytest


# ============================================================

def _create_test_excel(path: str):
    """创建一个带中文列名的测试 Excel 文件"""
    df = pd.DataFrame({
        '学生姓名': ['张三', '李四', '王五'],
        '序号': [1, 2, 3],
        '主/辅修': ['主修', '主修', '辅修'],
        '性别': ['男', '女', '男'],
        '院系名称': ['计算机学院', '数学学院', '物理学院'],
    })
    df.to_excel(path, index=False, engine='openpyxl')
    return df.columns.tolist()


def test_openpyxl_preserves_chinese_columns(tmp_path):
    """openpyxl 引擎应保留中文列名"""
    path = str(tmp_path / 'test.xlsx')
    original_cols = _create_test_excel(path)
    df = pd.read_excel(path, engine='openpyxl')
    assert list(df.columns) == original_cols, \
        f"openpyxl 修改了列名: {list(df.columns)} != {original_cols}"


def test_calamine_preserves_chinese_columns(tmp_path):
    """calamine 引擎应保留中文列名"""
    try:
        import python_calamine  # noqa: F401
    except ImportError:
        pytest.skip("python-calamine 未安装")

    path = str(tmp_path / 'test.xlsx')
    original_cols = _create_test_excel(path)
    df = pd.read_excel(path, engine='calamine')
    assert list(df.columns) == original_cols, \
        f"calamine 修改了列名: {list(df.columns)} != {original_cols}"


def test_sanitize_column_names_preserves_chinese():
    """_sanitize_column_names 不应修改中文列名（除非是PG保留字）"""
    try:
        from apps.datasource.api.datasource import _sanitize_column_names
    except ImportError:
        pytest.skip("无法导入 apps 模块（缺少依赖）")

    df = pd.DataFrame({
        '学生姓名': ['张三'],
        '序号': [1],
        '主/辅修': ['主修'],
        '性别': ['男'],
        '院系名称': ['计算机学院'],
    })
    original_cols = list(df.columns)
    df = _sanitize_column_names(df)
    assert list(df.columns) == original_cols, \
        f"_sanitize_column_names 修改了中文列名: {list(df.columns)} != {original_cols}"


def test_clean_dataframe_preserves_chinese_columns():
    """_clean_dataframe 不应修改中文列名"""
    try:
        from apps.datasource.api.datasource import _clean_dataframe
    except ImportError:
        pytest.skip("无法导入 apps 模块（缺少依赖）")

    df = pd.DataFrame({
        '学生姓名': ['张三', '李四'],
        '序号': [1, 2],
    })
    original_cols = list(df.columns)
    df, _ = _clean_dataframe(df)
    assert list(df.columns) == original_cols, \
        f"_clean_dataframe 修改了中文列名: {list(df.columns)} != {original_cols}"


# ============================================================

def trace_excel_columns(filepath: str):
    """对指定 Excel 文件进行完整的列名追踪"""
    print(f"\n{'='*60}")
    print(f"列名追踪诊断: {filepath}")
    print(f"{'='*60}\n")

    if not os.path.exists(filepath):
        print(f"文件不存在: {filepath}")
        return

    ext = os.path.splitext(filepath)[1].lower()

    # Step 1: 用默认引擎读取
    print("📋 Step 1: pd.read_excel (默认引擎 openpyxl)")
    try:
        df_default = pd.read_excel(filepath)
        print(f"   列名: {list(df_default.columns)}")
        print(f"   列名类型: {[type(c).__name__ for c in df_default.columns]}")
        print(f"   列名编码: {[repr(c) for c in df_default.columns]}")
    except Exception as e:
        print(f"   读取失败: {e}")

    # Step 2: 用 calamine 引擎读取
    print("\n📋 Step 2: pd.read_excel (calamine 引擎)")
    try:
        df_calamine = pd.read_excel(filepath, engine='calamine')
        print(f"   列名: {list(df_calamine.columns)}")
        print(f"   列名类型: {[type(c).__name__ for c in df_calamine.columns]}")
        print(f"   列名编码: {[repr(c) for c in df_calamine.columns]}")

        # 对比两个引擎
        if list(df_default.columns) != list(df_calamine.columns):
            print(f"\n   ⚠️  两个引擎读出的列名不同!")
            print(f"   openpyxl:  {list(df_default.columns)}")
            print(f"   calamine:  {list(df_calamine.columns)}")
        else:
            print(f"\n   两个引擎读出的列名一致")
    except ImportError:
        print(f"   ⚠️  python-calamine 未安装，跳过")
    except Exception as e:
        print(f"   读取失败: {e}")

    # Step 3: 检查是否包含拼音特征
    print("\n📋 Step 3: 拼音特征检测")
    import re
    for col in df_default.columns:
        col_str = str(col)
        # 拼音特征：全小写英文字母+空格，无大写，无数字
        if re.fullmatch(r'[a-z /-]+', col_str):
            print(f"   ⚠️  疑似拼音列名: '{col_str}'")
        else:
            has_chinese = bool(re.search(r'[\u4e00-\u9fff]', col_str))
            print(f"   {'中文' if has_chinese else '📝 其他'}: '{col_str}'")

    # Step 4: 检查 Excel XML 内部的 sharedStrings
    print("\n📋 Step 4: 检查 Excel 内部 sharedStrings.xml")
    if ext in ('.xlsx', '.xlsm'):
        try:
            import zipfile
            with zipfile.ZipFile(filepath) as zf:
                if 'xl/sharedStrings.xml' in zf.namelist():
                    xml_content = zf.read('xl/sharedStrings.xml').decode('utf-8')
                    # 检查是否有 rPh 标签（phonetic data）
                    if '<rPh' in xml_content:
                        print(f"   ⚠️  发现 <rPh> 标签（拼音/注音数据）!")
                        # 提取 rPh 内容
                        import xml.etree.ElementTree as ET
                        root = ET.fromstring(xml_content)
                        ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                        rph_count = 0
                        for si in root.findall('.//s:si', ns):
                            rph_elements = si.findall('.//s:rPh', ns)
                            if rph_elements:
                                main_text = si.find('s:t', ns)
                                main_val = main_text.text if main_text is not None else '(无主文本)'
                                phonetic_texts = [rph.find('s:t', ns).text for rph in rph_elements if rph.find('s:t', ns) is not None]
                                print(f"   原文: '{main_val}' → 注音: {phonetic_texts}")
                                rph_count += 1
                                if rph_count >= 10:
                                    print(f"   ... (共 {len(root.findall('.//s:rPh', ns))} 个 rPh 标签)")
                                    break
                    else:
                        print(f"   未发现 <rPh> 标签")

                    # 打印前几个 shared string
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(xml_content)
                    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                    print(f"\n   前10个 shared strings:")
                    for i, si in enumerate(root.findall('s:si', ns)[:10]):
                        t_elem = si.find('s:t', ns)
                        r_elems = si.findall('s:r', ns)
                        if t_elem is not None and t_elem.text:
                            print(f"   [{i}] '{t_elem.text}'")
                        elif r_elems:
                            parts = []
                            for r in r_elems:
                                rt = r.find('s:t', ns)
                                if rt is not None and rt.text:
                                    parts.append(rt.text)
                            print(f"   [{i}] (rich text) '{''.join(parts)}'")
                        else:
                            print(f"   [{i}] (empty)")
                else:
                    print(f"   ℹ️  无 sharedStrings.xml（可能使用 inline strings）")
        except Exception as e:
            print(f"   解析失败: {e}")
    else:
        print(f"   ℹ️  非 xlsx 格式，跳过 XML 检查")

    # Step 5: _clean_dataframe + _sanitize_column_names 模拟
    print("\n📋 Step 5: 模拟导入流程")
    try:
        from apps.datasource.api.datasource import _clean_dataframe, _sanitize_column_names
        df_test = df_default.copy() if 'df_default' in dir() else pd.read_excel(filepath)
        print(f"   原始列名:          {list(df_test.columns)}")
        df_test, _ = _clean_dataframe(df_test)
        print(f"   _clean_dataframe后: {list(df_test.columns)}")
        df_test = _sanitize_column_names(df_test)
        print(f"   _sanitize后:        {list(df_test.columns)}")
    except ImportError:
        print(f"   ⚠️  无法导入 apps 模块（需要在 backend 目录下运行）")
    except Exception as e:
        print(f"   模拟失败: {e}")

    print(f"\n{'='*60}")
    print("诊断完成。请将以上输出发给开发者分析。")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        trace_excel_columns(sys.argv[1])
    else:
        print("用法: python3 tests/test_column_trace.py <excel文件路径>")
        print("示例: python3 tests/test_column_trace.py /tmp/test_upload.xlsx")
