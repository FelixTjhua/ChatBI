"""文档解析与向量化检索流程模块 (Document Parsing & Vectorization Pipeline)"""
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from common.utils.utils import ChatBILogUtil


@dataclass
class DocumentChunk:
    """文档分块结果"""
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    # 元数据包含：source_file, page_number, section_title, chunk_index, chunk_type

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "metadata": self.metadata,
        }


@dataclass
class ParseResult:
    """文档解析结果"""
    raw_text: str = ""
    sections: List[Dict[str, Any]] = field(default_factory=list)
    # section: {title, level, content, page}
    tables: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    # metadata: {filename, file_type, total_pages, parse_time}



class DocumentParser:
    """文档解析器

    从不同格式文件中提取纯文本与结构信息。
    """

    SUPPORTED_EXTENSIONS = {'.pdf', '.xlsx', '.xls', '.csv'}

    @staticmethod
    def parse(file_path: str) -> ParseResult:
        """解析文档，自动识别格式"""
        import time
        start = time.time()

        ext = os.path.splitext(file_path)[1].lower()
        filename = os.path.basename(file_path)

        if ext not in DocumentParser.SUPPORTED_EXTENSIONS:
            raise ValueError(f"不支持的文件格式: {ext}，支持: {DocumentParser.SUPPORTED_EXTENSIONS} / "
                             f"Unsupported file format: {ext}, supported: {DocumentParser.SUPPORTED_EXTENSIONS}")

        result = ParseResult(metadata={"filename": filename, "file_type": ext})

        try:
            if ext == '.pdf':
                result = DocumentParser._parse_pdf(file_path, result)
            elif ext in ('.xlsx', '.xls', '.csv'):
                result = DocumentParser._parse_excel(file_path, result)
            else:
                raise ValueError(f"不支持的文件格式: {ext} / Unsupported file format: {ext}")
        except Exception as e:
            ChatBILogUtil.error(f"文档解析失败 [{filename}]: {e}")
            raise

        result.metadata["parse_time"] = round(time.time() - start, 3)
        ChatBILogUtil.info(
            f"文档解析完成: {filename}, "
            f"段落数={len(result.sections)}, "
            f"表格数={len(result.tables)}, "
            f"耗时={result.metadata['parse_time']}s"
        )
        return result

    @staticmethod
    def _parse_pdf(file_path: str, result: ParseResult) -> ParseResult:
        """解析PDF文档，提取文本、标题层级和表格"""
        import pdfplumber

        all_text = []
        scanned_pages = []
        ocr_pages = []  # 记录通过 OCR 识别的页面

        # ── OCR 辅助函数 ──
        def _ocr_page_image(file_path: str, page_number: int) -> str:
            """对指定页面进行 OCR 文字识别
            
            使用 pdf2image 将 PDF 页面渲染为图片，再用 pytesseract 识别文字。
            支持中英文混合识别（chi_sim+eng）。
            """
            try:
                from pdf2image import convert_from_path
                import pytesseract
                # 只渲染指定页面，dpi=300 保证识别精度
                images = convert_from_path(
                    file_path,
                    first_page=page_number,
                    last_page=page_number,
                    dpi=300,
                )
                if not images:
                    return ""
                # 中英文混合识别
                ocr_text = pytesseract.image_to_string(
                    images[0],
                    lang='chi_sim+eng',
                    config='--psm 6'  # 假设为统一的文本块
                )
                return ocr_text.strip()
            except ImportError:
                ChatBILogUtil.warning(
                    f"OCR 依赖未安装（pytesseract/pdf2image），跳过第{page_number}页图片识别。"
                    f"安装方法: pip install pytesseract pdf2image && brew install tesseract poppler"
                )
                return ""
            except Exception as e:
                ChatBILogUtil.warning(f"OCR 识别第{page_number}页失败: {e}")
                return ""

        def _page_has_images(page) -> bool:
            """检测 pdfplumber 页面是否包含图片对象"""
            try:
                return len(page.images) > 0
            except Exception:
                return False

        # 跨页 section 连续性 —— 将标题/正文状态提升到页循环外部
        current_section_lines: list[str] = []
        current_title = ""
        current_page = 1  # 记录当前 section 起始页
        current_level = 2  # 当前标题层级

        def _detect_heading_level(text: str) -> int:
            """检测标题层级：1=章级, 2=节级, 3=小节级"""
            # 章级标题：第一章 / 第1部分 / CHAPTER
            if re.match(r'^第[一二三四五六七八九十\d]+[章部分篇]', text):
                return 1
            if text.isascii() and text.isupper() and len(text) >= 3:
                return 1
            # 节级标题：1. / 一、/ 1.1 等单层编号
            if re.match(r'^[\d一二三四五六七八九十]+[\.\s、）\)](?!\d)', text):
                return 2
            if re.match(r'^第[一二三四五六七八九十\d]+[节]', text):
                return 2
            # 小节级标题：1.1 / 1.1.1 等多层编号 或 短行标题
            if re.match(r'^\d+\.\d+', text):
                return 3
            return 3  # 默认短行标题为小节级

        with pdfplumber.open(file_path) as pdf:
            result.metadata["total_pages"] = len(pdf.pages)

            for page_num, page in enumerate(pdf.pages, start=1):
                # ── 全量提取页面文本（不排除任何区域，零丢失） ──
                page_text = page.extract_text() or ""

                # ── 独立提取表格结构 ──
                tables = page.extract_tables() or []
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    headers = [str(c or '') for c in table[0]]
                    rows = [[str(c or '') for c in row] for row in table[1:]]

                    # 生成表格文本指纹：所有单元格文本的集合（用于分块阶段去重）
                    cell_texts = set()
                    for cell in table[0]:
                        if cell and str(cell).strip():
                            cell_texts.add(str(cell).strip())
                    for row in table[1:]:
                        for cell in row:
                            if cell and str(cell).strip():
                                cell_texts.add(str(cell).strip())

                    result.tables.append({
                        "headers": headers,
                        "rows": rows[:500],
                        "page": page_num,
                        "text_fingerprint": cell_texts,  # 用于分块阶段去重
                    })

                if page_text.strip():
                    all_text.append(page_text)

                    # 混合页图片 OCR：页面有文字但也包含图片时，
                    # 图片中的文字不会被 extract_text() 提取，需要 OCR 补充
                    if _page_has_images(page):
                        ocr_text = _ocr_page_image(file_path, page_num)
                        if ocr_text.strip():
                            # 去除 OCR 结果中与已提取文字重复的部分
                            # 简单策略：如果 OCR 文本中有超过 50% 的内容已在 page_text 中，跳过
                            existing_chars = set(page_text.replace(' ', '').replace('\n', ''))
                            ocr_chars = set(ocr_text.replace(' ', '').replace('\n', ''))
                            overlap = len(existing_chars & ocr_chars) / max(len(ocr_chars), 1)
                            if overlap < 0.5:
                                # OCR 提取到了图片中的新内容
                                ocr_pages.append(page_num)
                                all_text.append(ocr_text)
                                result.sections.append({
                                    "title": f"[OCR图片] 第{page_num}页",
                                    "level": 3,
                                    "content": ocr_text,
                                    "page": page_num,
                                })
                                ChatBILogUtil.info(
                                    f"混合页第{page_num}页图片OCR成功，新增 {len(ocr_text)} 字符"
                                )

                    # 按行分析，识别标题和正文段落
                    lines = page_text.strip().split('\n')

                    for line in lines:
                        stripped = line.strip()
                        if not stripped:
                            continue
                        # 增强标题检测（收紧条件，减少误判）
                        is_heading = (
                            len(stripped) <= 50
                            and not stripped.endswith(('。', '，', '；', '、', '.', ',', ';', '：', ':', '）', ')'))
                            and not stripped.startswith(('（', '(', '●', '•', '-', '—', '※', '→', '▪'))
                            and not re.match(r'^[\d\s\.\-/,，]+$', stripped)  # 排除纯数字/日期行
                            and not re.match(r'^\d{4}[\-/年]\d{1,2}[\-/月]', stripped)  # 排除日期字符串
                            and not re.match(r'^第?\d+页', stripped)  # 排除页码行
                            and not re.match(r'^[省市区县镇乡村路街道号楼栋单元室]', stripped)  # 排除地址行
                            and (
                                # 明确的编号标题：1. / 一、/ 1) 等
                                bool(re.match(r'^[\d一二三四五六七八九十]+[\.\s、）\)]', stripped))
                                # 章节标题：第一章 / 第2节 等
                                or bool(re.match(r'^第[一二三四五六七八九十\d]+[章节部分篇]', stripped))
                                # 纯英文标题（全大写或首字母大写）
                                or (stripped.isascii() and len(stripped) >= 3 and (stripped.isupper() or stripped.istitle()))
                                # 短行标题：≤12字、无逗号、无句号、不含常见非标题短语
                                or (
                                    len(stripped) <= 12
                                    and '，' not in stripped and ',' not in stripped
                                    and '的' not in stripped and '了' not in stripped
                                    and '是' not in stripped and '在' not in stripped
                                    and '有' not in stripped and '为' not in stripped
                                    and not re.search(r'[详见参考注意备注来源说明]', stripped)
                                )
                            )
                        )
                        if is_heading and current_section_lines:
                            # 遇到新标题 → flush 上一个 section
                            content = '\n'.join(current_section_lines)
                            result.sections.append({
                                "title": current_title,
                                "level": current_level,
                                "content": content,
                                "page": current_page,
                            })
                            current_section_lines = []
                            current_title = stripped
                            current_level = _detect_heading_level(stripped)
                            current_page = page_num
                        elif is_heading and not current_section_lines:
                            current_title = stripped
                            current_level = _detect_heading_level(stripped)
                            current_page = page_num
                        else:
                            if not current_section_lines:
                                current_page = page_num  # 记录 section 起始页
                            current_section_lines.append(stripped)
                else:
                    # 扫描版/纯图片页：先 flush 跨页累积的 section，再尝试 OCR
                    if current_section_lines:
                        content = '\n'.join(current_section_lines)
                        result.sections.append({
                            "title": current_title,
                            "level": current_level,
                            "content": content,
                            "page": current_page,
                        })
                        current_section_lines = []
                        current_title = ""
                        current_level = 2

                    # OCR 识别：对扫描版/纯图片页进行文字识别
                    ocr_text = _ocr_page_image(file_path, page_num)
                    if ocr_text.strip():
                        ocr_pages.append(page_num)
                        all_text.append(ocr_text)
                        # OCR 文本作为独立 section
                        result.sections.append({
                            "title": f"[OCR] 第{page_num}页",
                            "level": 2,
                            "content": ocr_text,
                            "page": page_num,
                        })
                        ChatBILogUtil.info(f"OCR 识别第{page_num}页成功，提取 {len(ocr_text)} 字符")
                    else:
                        scanned_pages.append(page_num)

        # flush 最后一个跨页 section（PDF 结束时的残留内容）
        if current_section_lines:
            content = '\n'.join(current_section_lines)
            result.sections.append({
                "title": current_title,
                "level": current_level,
                "content": content,
                "page": current_page,
            })
        elif current_title:
            # 文档末尾的孤立标题也必须保留
            result.sections.append({
                "title": current_title,
                "level": current_level,
                "content": current_title,
                "page": current_page,
            })

        result.raw_text = "\n\n".join(all_text)

        # OCR 识别统计
        if ocr_pages:
            result.metadata["ocr_pages"] = ocr_pages
            result.metadata["ocr_page_count"] = len(ocr_pages)
            ChatBILogUtil.info(
                f"OCR 识别完成: 共{len(ocr_pages)}页通过OCR提取文字"
                f"(第{ocr_pages[:5]}页等)"
            )

        if scanned_pages:
            result.metadata["scanned_pages"] = scanned_pages
            result.metadata["scanned_page_count"] = len(scanned_pages)
            ChatBILogUtil.warning(
                f"PDF含{len(scanned_pages)}个页面OCR识别失败或无内容"
                f"(第{scanned_pages[:5]}页等)"
            )

        return result

    @staticmethod
    def _parse_excel(file_path: str, result: ParseResult) -> ParseResult:
        """解析Excel/CSV文档"""
        import pandas as pd

        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.csv':
            dfs = {"Sheet1": DocumentParser._read_csv_smart(file_path)}
        else:
            dfs = pd.read_excel(file_path, sheet_name=None)

        # 空 Excel 文件（0 个 sheet）防御
        if not dfs:
            ChatBILogUtil.warning(f"Excel/CSV file has no sheets: {file_path}")
            result.metadata["total_pages"] = 0
            return result

        all_text = []
        for sheet_name, df in dfs.items():
            # CSV批量清洗：去重、空行清理
            original_rows = len(df)
            df = DocumentParser._clean_dataframe(df)
            cleaned_rows = len(df)

            # 清洗后空 DataFrame 保护
            if cleaned_rows == 0:
                ChatBILogUtil.warning(
                    f"Excel sheet '{sheet_name}' is empty after cleaning "
                    f"(original {original_rows} rows all removed), skipping"
                )
                continue

            # 在 fillna 之前执行 _classify_columns
            dimension_cols, metric_cols = DocumentParser._classify_columns(df)

            df = df.fillna("")
            headers = [str(c) for c in df.columns.tolist()]
            rows = df.astype(str).values.tolist()

            result.tables.append({
                "headers": headers,
                "rows": rows[:500],
                "page": 1,
                "sheet": sheet_name,
                "total_rows": len(rows),  # 记录原始行数，便于溯源
            })

            # 当数据被截断时记录警告日志
            if len(rows) > 500:
                ChatBILogUtil.warning(
                    f"Excel sheet '{sheet_name}' 数据截断: {len(rows)} → 500 行 "
                    f"(丢失 {len(rows) - 500} 行，可能影响分析完整性)"
                )

            # 基础文本描述
            text_repr = f"工作表/Worksheet: {sheet_name}\n"
            text_repr += f"列/Columns: {', '.join(headers)}\n"
            # 区分总行数和实际可查询行数，避免 LLM 产生误导性回答
            # 当数据被截断时，明确标注截断信息，让 LLM 知道语义分块仅基于样本数据
            if len(rows) > 500:
                text_repr += f"总行数/Total rows: {len(rows)}（语义分块基于前500行样本/Semantic chunks based on first 500 rows sample，完整数据可通过SQL查询/Full data available via SQL）\n"
            else:
                text_repr += f"行数/Rows: {cleaned_rows}\n"
            if original_rows != cleaned_rows:
                text_repr += f"清洗/Cleaned: 原始/original {original_rows}行/rows，去重清洗后/after dedup {cleaned_rows}行/rows\n"
            if dimension_cols:
                text_repr += f"维度字段/Dimension fields: {', '.join(dimension_cols)}\n"
            if metric_cols:
                text_repr += f"指标字段/Metric fields: {', '.join(metric_cols)}\n"
            sample = df.head(5).to_string(index=False)
            text_repr += f"数据样本/Data sample:\n{sample}"

            all_text.append(text_repr)
            result.sections.append({
                "title": f"工作表/Worksheet: {sheet_name}",
                "level": 1,
                "content": text_repr,
                "page": 1,
            })

            # 使用分层抽样替代简单 head(500)，更好地保留数据模式
            if len(df) > 500:
                try:
                    if dimension_cols:
                        # 按第一个维度列分层抽样，每组按比例取样
                        group_col = dimension_cols[0]
                        group_counts = df[group_col].value_counts()
                        sampled_parts = []
                        for val, count in group_counts.items():
                            group_df = df[df[group_col] == val]
                            # 每组至少取 2 行，按比例分配 500 行配额
                            n_sample = max(2, int(500 * count / len(df)))
                            sampled_parts.append(group_df.head(n_sample))
                        df_for_chunks = pd.concat(sampled_parts).head(500)
                    else:
                        df_for_chunks = df.head(500)
                except Exception:
                    df_for_chunks = df.head(500)
            else:
                df_for_chunks = df
            semantic_chunks = DocumentParser._generate_semantic_chunks(
                df_for_chunks, sheet_name, dimension_cols, metric_cols
            )
            for chunk_text, chunk_title in semantic_chunks:
                result.sections.append({
                    "title": chunk_title,
                    "level": 2,
                    "content": chunk_text,
                    "page": 1,
                })

            # 为数值列生成分布统计描述
            df_for_stats = df
            if metric_cols:
                dist_parts = [f"工作表「{sheet_name}」数值分布统计/Worksheet '{sheet_name}' numeric distribution statistics："]
                for mc in metric_cols[:5]:
                    try:
                        col_data = pd.to_numeric(df_for_stats[mc], errors='coerce').dropna()
                        if len(col_data) > 0:
                            dist_parts.append(
                                f"  {mc}: mean/均值={col_data.mean():.2f}, "
                                f"median/中位数={col_data.median():.2f}, "
                                f"std/标准差={col_data.std():.2f}, "
                                f"min/最小={col_data.min():.2f}, "
                                f"max/最大={col_data.max():.2f}"
                            )
                    except Exception:
                        pass
                if len(dist_parts) > 1:
                    dist_text = "\n".join(dist_parts)
                    result.sections.append({
                        "title": f"分布统计/Distribution statistics: {sheet_name}",
                        "level": 2,
                        "content": dist_text,
                        "page": 1,
                    })

        result.raw_text = "\n\n".join(all_text)
        result.metadata["total_pages"] = len(dfs)
        return result

    @staticmethod
    def _read_csv_smart(file_path: str):
        """智能CSV读取：自动检测编码和分隔符"""
        import pandas as pd

        # 1. 编码检测
        encoding = 'utf-8'
        try:
            with open(file_path, 'rb') as f:
                raw = f.read(8192)
            # 检测 UTF-8 BOM（EF BB BF），使用 utf-8-sig 自动剥离
            if raw[:3] == b'\xef\xbb\xbf':
                encoding = 'utf-8-sig'
            else:
                # 尝试UTF-8解码
                try:
                    raw.decode('utf-8')
                except UnicodeDecodeError:
                    # 尝试GBK
                    try:
                        raw.decode('gbk')
                        encoding = 'gbk'
                    except UnicodeDecodeError:
                        encoding = 'latin-1'
        except Exception:
            pass

        # 2. 分隔符检测
        sep = ','
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                first_line = f.readline()
            tab_count = first_line.count('\t')
            comma_count = first_line.count(',')
            semicolon_count = first_line.count(';')
            if tab_count > comma_count and tab_count > semicolon_count:
                sep = '\t'
            elif semicolon_count > comma_count:
                sep = ';'
        except Exception:
            pass

        ChatBILogUtil.info(f"CSV smart read: encoding={encoding}, sep='{sep}'")

        # 3. 大文件分批次解析
        import os
        file_size = os.path.getsize(file_path)
        LARGE_FILE_THRESHOLD = 50 * 1024 * 1024  # 50MB

        if file_size > LARGE_FILE_THRESHOLD:
            ChatBILogUtil.info(f"CSV large file detected ({file_size / 1024 / 1024:.1f}MB), using chunked reading")
            # 大文件限制最大行数，避免 OOM
            MAX_ROWS_LARGE_FILE = 500_000
            chunks = []
            total_rows = 0
            for chunk in pd.read_csv(file_path, encoding=encoding, sep=sep,
                                     on_bad_lines='skip', chunksize=50000):
                chunks.append(chunk)
                total_rows += len(chunk)
                if total_rows >= MAX_ROWS_LARGE_FILE:
                    ChatBILogUtil.warning(
                        f"CSV large file truncated at {total_rows} rows "
                        f"(max={MAX_ROWS_LARGE_FILE}), remaining data skipped"
                    )
                    break
            df = pd.concat(chunks, ignore_index=True)
        else:
            df = pd.read_csv(file_path, encoding=encoding, sep=sep, on_bad_lines='skip')

        return df

    @staticmethod
    def _clean_dataframe(df):
        """批量数据清洗"""
        import pandas as pd

        original_len = len(df)

        # 去除全空行
        df = df.dropna(how='all')

        # 去除完全重复行
        df = df.drop_duplicates()

        cleaned_len = len(df)
        if original_len != cleaned_len:
            ChatBILogUtil.info(
                f"Data cleaning: {original_len} → {cleaned_len} rows "
                f"(removed {original_len - cleaned_len} duplicates/empty rows)"
            )

        return df.reset_index(drop=True)
    @staticmethod
    def _classify_columns(df) -> Tuple[List[str], List[str]]:
        """识别DataFrame中的维度列和指标列。

        维度列：时间、地区、产品等分类字段
        指标列：销售额、利润、数量等数值字段
        """
        import pandas as pd

        dimension_cols = []
        metric_cols = []

        time_patterns = re.compile(r'日期|时间|年|月|季度|date|time|year|month|quarter|week', re.IGNORECASE)
        region_patterns = re.compile(r'地区|区域|省|市|城市|国家|region|city|country|area', re.IGNORECASE)
        category_patterns = re.compile(r'类别|品类|产品|类型|分类|category|product|type|class', re.IGNORECASE)

        for col in df.columns:
            col_str = str(col)
            # 数值列 → 指标
            if pd.api.types.is_numeric_dtype(df[col]):
                metric_cols.append(col_str)
            # 时间/地区/品类 → 维度
            elif time_patterns.search(col_str) or region_patterns.search(col_str) or category_patterns.search(col_str):
                dimension_cols.append(col_str)
            else:
                # 非数值列根据唯一值比例区分维度和高基数文本列
                nunique = df[col].nunique()
                total = len(df)
                if total > 0 and nunique > 50 and (nunique / total) > 0.5:
                    # 高基数文本列，跳过（不归入维度）
                    pass
                else:
                    dimension_cols.append(col_str)

        return dimension_cols, metric_cols

    @staticmethod
    def _safe_float(x) -> float:
        """安全地将值转换为float，失败返回NaN"""
        try:
            return float(x)
        except (ValueError, TypeError):
            return float('nan')

    @staticmethod
    def _generate_semantic_chunks(
        df, sheet_name: str, dimension_cols: List[str], metric_cols: List[str]
    ) -> List[Tuple[str, str]]:
        """按"维度组合-指标"生成语义分块。"""
        chunks = []

        if not metric_cols or not dimension_cols or len(df) == 0:
            return chunks

        # 取第一个维度列做分组（避免组合爆炸）
        group_col = dimension_cols[0]
        try:
            grouped = df.groupby(group_col)
        except Exception:
            return chunks

        for group_val, group_df in grouped:
            if len(chunks) >= 20:  # 限制分块数量
                break
            group_val_str = str(group_val).strip()
            if not group_val_str or group_val_str in ("", "nan", "None"):
                continue

            # 为每个指标生成摘要
            summaries = []
            for mc in metric_cols[:5]:
                try:
                    col_data = group_df[mc].apply(lambda x: DocumentParser._safe_float(x)).dropna()
                    if len(col_data) > 0:
                        total = col_data.sum()
                        avg = col_data.mean()
                        summaries.append(f"{mc} total/合计={total:.2f}，avg/均值={avg:.2f}")
                except Exception:
                    pass

            if summaries:
                title = f"{sheet_name}-{group_col}={group_val_str}"
                text = (f"工作表「{sheet_name}」中/In worksheet '{sheet_name}'，"
                        f"{group_col}为「{group_val_str}」的数据/data where {group_col}='{group_val_str}'（共{len(group_df)}行/rows）：\n")
                text += "；".join(summaries)
                chunks.append((text, title))

        return chunks




class TextChunker:
    """文本分块器"""

    DEFAULT_CHUNK_SIZE = 512
    DEFAULT_OVERLAP = 64

    @staticmethod
    def chunk_by_sections(
        parse_result: ParseResult,
        max_chunk_size: int = 512,
        overlap: int = 64,
    ) -> List[DocumentChunk]:
        """按标题层级分块（零丢失 + 智能去重）"""
        chunks: List[DocumentChunk] = []
        filename = parse_result.metadata.get("filename", "")

        if not parse_result.sections:
            raw_chunks = TextChunker.chunk_by_sliding_window(
                parse_result.raw_text, max_chunk_size, overlap
            )
            for i, text in enumerate(raw_chunks):
                chunks.append(DocumentChunk(
                    text=text,
                    metadata={
                        "source_file": filename,
                        "chunk_index": i,
                        "chunk_type": "sliding_window",
                    }
                ))
            return chunks

        # 构建每页的表格文本指纹索引（用于去重比对）
        page_table_fingerprints: Dict[int, List[set]] = {}
        for table in parse_result.tables:
            page = table.get("page", 1)
            fp = table.get("text_fingerprint", set())
            if fp:
                page_table_fingerprints.setdefault(page, []).append(fp)

        chunk_index = 0
        for section in parse_result.sections:
            title = section.get("title", "")
            content = section.get("content", "").strip()
            level = section.get("level", 1)
            page = section.get("page", 1)

            if not content:
                continue

            full_text = f"{title}\n{content}" if title else content

            # ── 计算与同页表格的文本重叠度 ──
            table_overlap_ratio = 0.0
            page_fps = page_table_fingerprints.get(page, [])
            if page_fps:
                # 增强表格重叠检测，减少正文误删
                section_text_flat = content.replace('\n', '').replace(' ', '')

                if section_text_flat:
                    # 合并同页所有表格的指纹
                    all_table_words = set()
                    for fp in page_fps:
                        all_table_words.update(fp)

                    # 字符级子串匹配：统计表格单元格文本在 section 中出现的比例
                    matched_cells = 0
                    total_cells = 0
                    for cell_text in all_table_words:
                        cell_clean = cell_text.replace(' ', '')
                        if len(cell_clean) >= 2:  # 忽略单字符（太通用）
                            total_cells += 1
                            if cell_clean in section_text_flat:
                                matched_cells += 1

                    table_overlap_ratio = matched_cells / total_cells if total_cells > 0 else 0.0

            # 提高 table_overlap 判定门槛
            is_table_overlap = table_overlap_ratio >= 0.75 and len(content) <= 200
            chunk_type_base = "table_overlap" if is_table_overlap else "section"

            if len(full_text) <= max_chunk_size:
                chunks.append(DocumentChunk(
                    text=full_text,
                    metadata={
                        "source_file": filename,
                        "section_title": title,
                        "heading_level": level,
                        "page_number": page,
                        "chunk_index": chunk_index,
                        "chunk_type": chunk_type_base,
                        "table_overlap_ratio": round(table_overlap_ratio, 2),
                    }
                ))
                chunk_index += 1
            else:
                sub_chunks = TextChunker.chunk_by_sliding_window(
                    full_text, max_chunk_size, overlap
                )
                for sub_text in sub_chunks:
                    chunks.append(DocumentChunk(
                        text=sub_text,
                        metadata={
                            "source_file": filename,
                            "section_title": title,
                            "heading_level": level,
                            "page_number": page,
                            "chunk_index": chunk_index,
                            "chunk_type": f"{chunk_type_base}_split" if not is_table_overlap else "table_overlap",
                            "table_overlap_ratio": round(table_overlap_ratio, 2),
                        }
                    ))
                    chunk_index += 1

        # 表格独立生成结构化 chunk（高质量检索入口）
        for table in parse_result.tables:
            table_text = TextChunker._table_to_text(table, max_chunk_size=max_chunk_size)
            if table_text:
                table_page = table.get("page", 1)
                associated_section_title = ""
                for section in parse_result.sections:
                    if section.get("page") == table_page and section.get("title"):
                        associated_section_title = section["title"]
                        break

                chunks.append(DocumentChunk(
                    text=table_text,
                    metadata={
                        "source_file": filename,
                        "page_number": table_page,
                        "sheet_name": table.get("sheet", ""),
                        "chunk_index": chunk_index,
                        "chunk_type": "table",
                        "section_title": associated_section_title,  # 使用 section_title 而非 associated_section，与 CoreDocumentChunk 模型字段名一致
                    }
                ))
                chunk_index += 1

        return chunks

    @staticmethod
    def chunk_by_sliding_window(
        text: str,
        chunk_size: int = 512,
        overlap: int = 64,
    ) -> List[str]:
        """固定长度滑动窗口分块（句子边界感知）"""
        if not text or not text.strip():
            return []

        text = text.strip()
        if len(text) <= chunk_size:
            return [text]

        # overlap >= chunk_size 时滑动窗口无限循环
        if overlap >= chunk_size:
            ChatBILogUtil.warning(
                f"chunk_by_sliding_window: overlap({overlap}) >= chunk_size({chunk_size}), "
                f"clamping to {chunk_size // 2}"
            )
            overlap = chunk_size // 2

        # 按句子边界预分割（中英文句号、问号、感叹号、换行）
        sentence_ends = re.compile(r'(?<=[。！？.!?\n])\s*')
        sentences = sentence_ends.split(text)
        sentences = [s.strip() for s in sentences if s.strip()]

        chunks = []
        current_chunk: list[str] = []
        current_len = 0

        for sentence in sentences:
            sent_len = len(sentence)

            if current_len + sent_len + 1 <= chunk_size:
                current_chunk.append(sentence)
                current_len += sent_len + 1
            else:
                if current_chunk:
                    chunks.append('\n'.join(current_chunk))
                # 单个句子超过 chunk_size → 硬切
                if sent_len > chunk_size:
                    start = 0
                    step = max(chunk_size - overlap, 1)
                    while start < sent_len:
                        end = start + chunk_size
                        chunks.append(sentence[start:end].strip())
                        if end >= sent_len:
                            break
                        start += step
                    current_chunk = []
                    current_len = 0
                else:
                    # 重叠：从上一个 chunk 末尾取 overlap 字符的句子
                    overlap_sentences = []
                    overlap_len = 0
                    if current_chunk and overlap > 0:
                        for s in reversed(current_chunk):
                            if overlap_len + len(s) + 1 > overlap:
                                break
                            overlap_sentences.insert(0, s)
                            overlap_len += len(s) + 1
                    current_chunk = overlap_sentences + [sentence]
                    current_len = overlap_len + sent_len

        if current_chunk:
            chunks.append('\n'.join(current_chunk))

        return [c for c in chunks if c.strip()]

    @staticmethod
    def _table_to_text(table: Dict, max_chunk_size: int = 512) -> str:
        """将表格转为Markdown格式文本 + 自然语言摘要（用于向量化检索）"""
        headers = table.get("headers", [])
        rows = table.get("rows", [])
        page = table.get("page", "")
        sheet = table.get("sheet", "")
        if not headers:
            return ""

        # 0. 生成自然语言摘要（提升向量检索语义匹配）
        nl_summary_parts = []
        clean_headers = [h.strip() if h.strip() else f"列{i+1}" for i, h in enumerate(headers)]
        source_hint = ""
        if page:
            source_hint += f"第{page}页"
        if sheet:
            source_hint += f"工作表「{sheet}」"

        nl_summary_parts.append(
            f"该表格包含{'/'.join(clean_headers[:6])}等字段，共{len(rows)}行数据。"
        )

        # 提取每列的值域摘要（前几个唯一值或数值范围）
        if rows:
            for col_idx, h in enumerate(clean_headers[:4]):
                col_vals = []
                for row in rows[:50]:
                    v = str(row[col_idx]).strip() if col_idx < len(row) else ""
                    if v and v not in ("None", "nan", "", "-"):
                        col_vals.append(v)
                if not col_vals:
                    continue
                # 尝试判断是否为数值列
                numeric_vals = []
                for v in col_vals:
                    try:
                        numeric_vals.append(float(v.replace(',', '').replace('万', '').replace('亿', '')))
                    except (ValueError, TypeError):
                        pass
                if len(numeric_vals) > len(col_vals) * 0.5 and numeric_vals:
                    nl_summary_parts.append(
                        f"{h}范围：{min(numeric_vals):.4g}~{max(numeric_vals):.4g}。"
                    )
                else:
                    unique_vals = list(dict.fromkeys(col_vals))[:5]
                    nl_summary_parts.append(
                        f"{h}包括：{'、'.join(unique_vals)}{'等' if len(set(col_vals)) > 5 else ''}。"
                    )

        nl_summary = "".join(nl_summary_parts)

        # 1. 表格标题描述
        desc_parts = []
        if nl_summary:
            desc_parts.append(nl_summary)
            desc_parts.append("")

        desc_parts.append(f"### 表格（{source_hint}）- {len(headers)}列 × {len(rows)}行")
        desc_parts.append("")  # 空行

        # 2. Markdown表格格式
        header_line = "| " + " | ".join(clean_headers) + " |"
        separator = "| " + " | ".join(["---"] * len(headers)) + " |"
        desc_parts.append(header_line)
        desc_parts.append(separator)

        current_len = sum(len(p) + 1 for p in desc_parts)

        # 3. 数据行（自适应行数，不超过 max_chunk_size）
        max_data_rows = min(len(rows), 30)
        for i, row in enumerate(rows[:max_data_rows]):
            row_cells = []
            for j, h in enumerate(headers):
                v = str(row[j]).strip() if j < len(row) else ""
                if v in ("None", "nan", ""):
                    v = "-"
                row_cells.append(v)
            row_line = "| " + " | ".join(row_cells) + " |"
            if current_len + len(row_line) + 1 > max_chunk_size:
                empty_cells = " | ".join([""] * (len(headers) - 2)) if len(headers) > 2 else ""
                truncation_note = f"共{len(rows)}行，已截断"
                if empty_cells:
                    desc_parts.append(f"| ... | {truncation_note} | {empty_cells} |")
                else:
                    desc_parts.append(f"| ... | {truncation_note} |")
                break
            desc_parts.append(row_line)
            current_len += len(row_line) + 1

        if len(rows) > max_data_rows:
            desc_parts.append(f"\n_共 {len(rows)} 行数据_")

        return "\n".join(desc_parts)



class TextPreprocessor:
    """文本预处理器

    对解析后的文本进行清洗和标准化处理。
    """

    @staticmethod
    def preprocess(text: str) -> str:
        """文本预处理流水线

        1. 清洗：去除多余空白、乱码、特殊符号
        2. 标准化：统一标点、全半角转换
        3. 过滤：去除无意义短文本
        """
        if not text:
            return ""

        # 去除控制字符和乱码
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)

        # 合并多余空白
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)

        # 全角转半角（数字和字母）
        result = []
        for ch in text:
            code = ord(ch)
            if 0xFF01 <= code <= 0xFF5E:
                result.append(chr(code - 0xFEE0))
            elif code == 0x3000:  # 全角空格
                result.append(' ')
            else:
                result.append(ch)
        text = ''.join(result)

        # 去除水印常见模式
        text = re.sub(r'(?:仅供.{0,6}(?:参考|使用|阅读|内部)|(?:机密|confidential)\s*(?:文件|文档|document)|watermark).*?(?:\n|$)', '', text, flags=re.IGNORECASE)

        return text.strip()

    @staticmethod
    def is_meaningful(text: str, min_length: int = 10) -> bool:
        """判断文本是否有意义（过滤无意义短文本）"""
        if not text or len(text.strip()) < min_length:
            return False
        # 纯数字或纯标点
        if re.match(r'^[\d\s\W]+$', text):
            return False
        return True


class DocumentVectorizer:
    """文档向量化器

    将文本块转为向量嵌入，存入向量库。
    使用项目已有的 EmbeddingModelCache 进行向量化。
    """

    @staticmethod
    def vectorize_chunks(
        chunks: List[DocumentChunk],
        batch_size: int = 32,
    ) -> List[Dict[str, Any]]:
        """批量向量化文本块"""
        from apps.ai_model.embedding import EmbeddingModelCache

        model = EmbeddingModelCache.get_model()
        results = []

        # 预处理：过滤无意义chunk 和 table_overlap chunk（已被表格chunk更好地表达）
        valid_chunks = [
            c for c in chunks
            if TextPreprocessor.is_meaningful(c.text)
            and c.metadata.get("chunk_type") != "table_overlap"
        ]

        # 批量向量化
        for i in range(0, len(valid_chunks), batch_size):
            batch = valid_chunks[i:i + batch_size]
            texts = [TextPreprocessor.preprocess(c.text) for c in batch]

            try:
                embeddings = model.embed_documents(texts)
                for chunk, embedding in zip(batch, embeddings):
                    results.append({
                        "text": chunk.text,
                        "embedding": embedding,
                        "metadata": chunk.metadata,
                    })
            except Exception as e:
                ChatBILogUtil.error(f"向量化批次失败 (batch {i//batch_size}): {e}")
                # 降级：逐条处理
                for chunk in batch:
                    try:
                        emb_list = model.embed_documents([TextPreprocessor.preprocess(chunk.text)])
                        results.append({
                            "text": chunk.text,
                            "embedding": emb_list[0],
                            "metadata": chunk.metadata,
                        })
                    except Exception as inner_e:
                        ChatBILogUtil.error(f"单条向量化失败: {inner_e}")

        skipped_overlap = len([c for c in chunks if c.metadata.get("chunk_type") == "table_overlap"])
        ChatBILogUtil.info(
            f"向量化完成: {len(results)}/{len(chunks)} chunks, "
            f"过滤 {len(chunks) - len(valid_chunks)} 个无意义/重叠chunk"
            f"（其中 table_overlap={skipped_overlap}）"
        )
        return results


class DocumentPipeline:
    """文档处理流水线

    整合文档解析、预处理、分块、向量化的完整流程。

    流程：原始文档 → 解析 → 预处理 → 分块 → 向量化 → 返回结果
    """

    @staticmethod
    def process(
        file_path: str,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
    ) -> Dict[str, Any]:
        """执行完整的文档处理流水线"""
        import time
        start = time.time()

        # Step 1: 文档解析
        parse_result = DocumentParser.parse(file_path)

        # Step 2: 文本分块（内部已包含预处理）
        chunks = TextChunker.chunk_by_sections(
            parse_result,
            max_chunk_size=chunk_size,
            overlap=chunk_overlap,
        )

        # Step 3: 向量化
        vectorized = DocumentVectorizer.vectorize_chunks(chunks)

        total_time = round(time.time() - start, 3)

        # Step 4: 分块完整性校验（Chunk Coverage Verification）
        coverage_stats = DocumentPipeline._verify_chunk_coverage(
            parse_result.raw_text, chunks
        )

        stats = {
            "filename": parse_result.metadata.get("filename", ""),
            "file_type": parse_result.metadata.get("file_type", ""),
            "total_sections": len(parse_result.sections),
            "total_tables": len(parse_result.tables),
            "total_chunks": len(chunks),
            "vectorized_count": len(vectorized),
            "total_time": total_time,
            # 分块完整性校验结果
            "chunk_coverage": coverage_stats["coverage_percent"],
            "raw_text_chars": coverage_stats["raw_text_chars"],
            "covered_chars": coverage_stats["covered_chars"],
            "uncovered_chars": coverage_stats["uncovered_chars"],
        }

        ChatBILogUtil.info(
            f"文档流水线完成: {stats['filename']}, "
            f"chunks={stats['total_chunks']}, "
            f"vectorized={stats['vectorized_count']}, "
            f"分块覆盖率={stats['chunk_coverage']}%, "
            f"耗时={total_time}s"
        )

        # 分块覆盖率低于阈值时记录警告，提醒可能存在内容丢失
        _coverage_pct = stats.get("chunk_coverage", 100)
        if _coverage_pct < 80:
            ChatBILogUtil.warning(
                f"⚠️ 分块覆盖率过低: {stats['filename']} 覆盖率={_coverage_pct}% (<80%), "
                f"原始字符={stats['raw_text_chars']}, 已覆盖={stats['covered_chars']}, "
                f"未覆盖={stats['uncovered_chars']}。可能存在内容丢失，请检查文档格式。"
            )
        stats["coverage_warning"] = _coverage_pct < 80

        return {
            "parse_result": parse_result,
            "chunks": chunks,
            "vectorized": vectorized,
            "stats": stats,
        }

    @staticmethod
    def _verify_chunk_coverage(
        raw_text: str, chunks: List[DocumentChunk]
    ) -> Dict[str, Any]:
        """分块完整性校验：计算 chunks 对 raw_text 的字符级覆盖率"""
        if not raw_text or not raw_text.strip():
            return {
                "coverage_percent": 100.0,
                "raw_text_chars": 0,
                "covered_chars": 0,
                "uncovered_chars": 0,
            }

        # 提取原始文本的非空白字符序列
        raw_chars = [c for c in raw_text if not c.isspace()]
        raw_total = len(raw_chars)
        if raw_total == 0:
            return {
                "coverage_percent": 100.0,
                "raw_text_chars": 0,
                "covered_chars": 0,
                "uncovered_chars": 0,
            }

        # 使用字符频次计数替代顺序贪心匹配
        # 顺序贪心在 chunks 乱序时（table chunks 追加到末尾）会严重低估覆盖率
        from collections import Counter
        
        raw_counter = Counter(raw_chars)
        
        chunk_chars = []
        for chunk in chunks:
            for c in chunk.text:
                if not c.isspace():
                    chunk_chars.append(c)
        chunk_counter = Counter(chunk_chars)
        
        # 计算交集：每个字符取 min(raw_count, chunk_count)
        covered = 0
        for char, raw_count in raw_counter.items():
            covered += min(raw_count, chunk_counter.get(char, 0))

        coverage_pct = round(covered / raw_total * 100, 1)

        return {
            "coverage_percent": coverage_pct,
            "raw_text_chars": raw_total,
            "covered_chars": covered,
            "uncovered_chars": raw_total - covered,
        }
