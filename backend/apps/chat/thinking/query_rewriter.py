"""查询重写模块 (Query Rewriting)"""
import re
from typing import List, Dict, Optional, Tuple

from common.utils.utils import ChatBILogUtil


# 集中定义 PDF 表格操作关键词
PDF_TABLE_OP_KEYWORDS = [
    '查询', '统计', '计算', '列出', '显示', '对比',
    '排名', '排序', '筛选', '过滤', '求和', '平均',
    '预测', '预估', '趋势', 'top', 'count', 'sum',
    '柱状图', '折线图', '饼图', '图表', '可视化',
    '画图', '画个', '生成图', '做个图', '绘制',
    # 英文关键词
    'query', 'statistics', 'calculate', 'list', 'show', 'compare',
    'rank', 'sort', 'filter', 'average', 'total',
    'predict', 'forecast', 'trend',
    'bar chart', 'line chart', 'pie chart', 'chart', 'visualize',
    'plot', 'graph', 'generate chart', 'draw',
]


class QueryRewriter:
    """查询重写器 - 优化用户查询以提升RAG检索质量"""

    # 常见的中文停用词和口语化表达
    STOP_WORDS = {
        '请', '帮我', '我想', '能不能', '可以', '麻烦', '一下',
        '看看', '查一下', '告诉我', '给我',
        '的话', '吧', '呢', '啊', '哦', '嗯', '了', '吗', '呗',
        # 英文停用词（口语化表达）
        'please', 'could you', 'can you', 'i want to', 'i need to',
        'help me', 'tell me', 'let me', 'i would like to',
    }

    # PDF 文档问答场景的额外停用短语（仅 ds_type='pdf' 时使用）
    PDF_STOP_PHRASES = [
        '这个里面的', '这个里面', '这里面的', '这里面',
        '这份文档', '这份文件', '这份报告', '这篇文章',
        '这个文档', '这个文件', '这个报告', '这篇论文',
        '讲了什么', '说了什么', '写了什么', '描述了什么',
        '讲的是什么', '说的是什么', '写的是什么',
        '讲了哪些', '说了哪些', '包含哪些', '涉及哪些',
        '主要讲了', '主要说了', '主要写了', '主要描述了',
        '主要讲的', '主要说的', '主要内容是',
        '大概讲了', '大概说了', '大致讲了', '大致说了',
    ]

    # 时间表达规范化映射
    TIME_PATTERNS = {
        r'最近(\d+)天': r'最近\1天',
        # 添加负向后行断言 (?<!最)，避免"最近3个月"被替换为"最最近3个月"
        # 原正则 r'近(\d+)个月' 会匹配"最近3个月"中的"近3个月"，导致重复前缀
        r'(?<!最)近(\d+)个月': r'最近\1个月',
    }

    # 聚合意图关键词
    AGG_KEYWORDS = {
        '总': 'SUM', '总计': 'SUM', '合计': 'SUM', '总共': 'SUM',
        '平均': 'AVG', '均值': 'AVG',
        '最大': 'MAX', '最高': 'MAX', '最多': 'MAX',
        '最小': 'MIN', '最低': 'MIN', '最少': 'MIN',
        '数量': 'COUNT', '个数': 'COUNT', '多少': 'COUNT', '几个': 'COUNT',
        # 英文聚合关键词
        'total': 'SUM', 'sum': 'SUM',
        'average': 'AVG', 'avg': 'AVG', 'mean': 'AVG',
        'maximum': 'MAX', 'highest': 'MAX',
        'minimum': 'MIN', 'lowest': 'MIN',
        'count': 'COUNT', 'how many': 'COUNT',
    }

    # 排序意图关键词
    SORT_KEYWORDS = {
        '前': 'TOP', '排名': 'ORDER', '排序': 'ORDER',
        '最高': 'DESC', '最低': 'ASC', '最多': 'DESC', '最少': 'ASC',
        # 英文排序关键词
        'top': 'TOP', 'rank': 'ORDER', 'sort': 'ORDER', 'order by': 'ORDER',
        'highest': 'DESC', 'lowest': 'ASC', 'most': 'DESC', 'least': 'ASC',
    }

    @staticmethod
    def rewrite(question: str, terminologies: List[Dict] = None, ds_type: str = 'database') -> Dict[str, any]:
        """执行查询重写，返回重写结果"""
        if not question or not question.strip():
            return {
                'original': question,
                'rewritten': question,
                'expanded_queries': [],
                'extracted_keywords': [],
                'intent': 'unknown',
                'intent_keywords': [],
                'rewrite_applied': False,
            }

        original = question.strip()
        rewritten = original
        rewrite_applied = False

        # Step 1: 去除口语化表达和停用词
        cleaned = QueryRewriter._remove_stop_words(rewritten)
        if cleaned != rewritten:
            rewritten = cleaned
            rewrite_applied = True

        # Step 1.5: PDF 文档问答专用口语化清理
        if ds_type == 'pdf' and not QueryRewriter._is_trivial_chat(rewritten):
            _pdf_cleaned = rewritten
            for phrase in QueryRewriter.PDF_STOP_PHRASES:
                _pdf_cleaned = _pdf_cleaned.replace(phrase, '')
            # 去除残留的前导"的"（如"这份文档的摘要"→"的摘要"→"摘要"）
            _pdf_cleaned = re.sub(r'^[的地得]+', '', _pdf_cleaned)
            _pdf_cleaned = re.sub(r'\s+', ' ', _pdf_cleaned).strip()
            # 安全兜底：如果清理后为空或太短（<4字），说明整句几乎都是口语表达
            # 此时补充"概述 摘要 总结"关键词，让向量检索能匹配到文档的摘要/概述段落
            if not _pdf_cleaned or len(_pdf_cleaned) < 4:
                _core = _pdf_cleaned if _pdf_cleaned else '内容'
                # 避免重复：如果核心词已包含"概述/摘要/总结"，不再重复追加
                _supplements = [w for w in ['概述', '摘要', '总结'] if w not in _core]
                rewritten = f'{_core} {" ".join(_supplements)}'.strip()
                rewrite_applied = True
            elif _pdf_cleaned != rewritten:
                rewritten = _pdf_cleaned
                rewrite_applied = True

        # Step 2: 时间表达规范化
        if ds_type != 'pdf':
            normalized = QueryRewriter._normalize_time_expressions(rewritten)
            if normalized != rewritten:
                rewritten = normalized
                rewrite_applied = True

        # Step 3: 同义词扩展（基于术语库）
        expanded = QueryRewriter._expand_with_terminologies(rewritten, terminologies)
        if expanded != rewritten:
            rewritten = expanded
            rewrite_applied = True

        # Step 4: 提取关键词和查询意图
        keywords = QueryRewriter._extract_keywords(rewritten)
        # 意图检测应基于原始查询（去停用词后、时间规范化前）
        intent = QueryRewriter._detect_intent(cleaned if cleaned else original, ds_type=ds_type)
        # Step 4b: 解释意图判定依据（返回命中的关键词规则）
        intent_keywords = QueryRewriter._explain_intent(cleaned if cleaned else original, intent, ds_type=ds_type)

        # Step 5: 生成扩展查询（用于多路检索）
        expanded_queries = QueryRewriter._generate_expanded_queries(rewritten, keywords, intent)

        return {
            'original': original,
            'rewritten': rewritten,
            'expanded_queries': expanded_queries,
            'extracted_keywords': keywords,
            'intent': intent,
            'intent_keywords': intent_keywords,
            'rewrite_applied': rewrite_applied,
        }

    @staticmethod
    def _remove_stop_words(question: str) -> str:
        """去除停用词和口语化表达（中英文通用）"""
        # 单字语气词：仅在句尾去除
        _sentence_final_particles = {'了', '吗', '呢', '啊', '哦', '嗯', '吧', '呗'}
        # 多字中文停用词中需要边界保护的（可能是其他词的子串）
        _boundary_protected_cn = {'的话'}

        result = question
        for word in QueryRewriter.STOP_WORDS:
            if word in _sentence_final_particles:
                # 单字语气词只去除句尾出现（可能有标点在后面）
                result = re.sub(re.escape(word) + r'([？?。！!，,\s]*)$', r'\1', result)
            elif word.isascii():
                # 英文停用词添加词边界 \b，防止跨词误匹配
                result = re.sub(r'\b' + re.escape(word) + r'\b', '', result, flags=re.IGNORECASE)
            elif word in _boundary_protected_cn:
                # 多字中文停用词仅在句尾或后接标点/空格时去除
                # "销售增长的话" → "销售增长"，但 "的话题" 不受影响
                result = re.sub(re.escape(word) + r'(?=[？?。！!，,\s]|$)', '', result)
            else:
                result = result.replace(word, '')
        # 去除多余空格
        result = re.sub(r'\s+', ' ', result).strip()
        return result if result else question

    @staticmethod
    def _normalize_time_expressions(question: str, reference_time=None) -> str:
        """规范化时间表达"""
        from datetime import datetime
        now = reference_time if reference_time else datetime.now()
        current_year = str(now.year)
        last_year = str(now.year - 1)
        current_month = str(now.month)
        # 1月的"上个月"需要回退到上一年12月
        if now.month > 1:
            last_month = str(now.month - 1)
            last_month_year = current_year
        else:
            last_month = '12'
            last_month_year = last_year
        
        result = question
        # 静态正则模式（不涉及动态值的）
        for pattern, replacement in QueryRewriter.TIME_PATTERNS.items():
            result = re.sub(pattern, replacement, result)
        
        # 动态时间替换（使用实际日期值）
        next_year = str(now.year + 1)
        # 计算下个月（处理12月→次年1月的跨年）
        if now.month < 12:
            next_month = str(now.month + 1)
            next_month_year = current_year
        else:
            next_month = '1'
            next_month_year = next_year
        # 计算当前季度和上/下季度
        current_quarter = (now.month - 1) // 3 + 1
        if current_quarter < 4:
            next_quarter = current_quarter + 1
            next_quarter_year = current_year
        else:
            next_quarter = 1
            next_quarter_year = next_year
        if current_quarter > 1:
            prev_quarter = current_quarter - 1
            prev_quarter_year = current_year
        else:
            prev_quarter = 4
            prev_quarter_year = last_year
        # _detect_intent 的 time_patterns 包含这些词，SQL生成也需要具体日期
        from datetime import timedelta
        today_str = now.strftime('%Y年%m月%d日')
        yesterday = now - timedelta(days=1)
        yesterday_str = yesterday.strftime('%Y年%m月%d日')
        # 本周：计算本周一的日期
        weekday = now.weekday()  # 0=Monday
        week_start = now - timedelta(days=weekday)
        week_start_str = week_start.strftime('%Y年%m月%d日')
        # 上周
        last_week_start = week_start - timedelta(days=7)
        last_week_end = week_start - timedelta(days=1)
        last_week_str = f"{last_week_start.strftime('%Y年%m月%d日')}至{last_week_end.strftime('%m月%d日')}"

        # 按长度降序排列替换项，防止子串冲突
        dynamic_replacements = [
            ('下个月', f'{next_month_year}年{next_month}月'),
            ('上个月', f'{last_month_year}年{last_month}月'),
            ('这个月', f'{current_year}年{current_month}月'),
            ('下季度', f'{next_quarter_year}年Q{next_quarter}'),
            ('上季度', f'{prev_quarter_year}年Q{prev_quarter}'),
            ('本季度', f'{current_year}年Q{current_quarter}'),
            ('明年', f'{next_year}年'),
            ('今年', f'{current_year}年'),
            ('本年', f'{current_year}年'),
            ('去年', f'{last_year}年'),
            ('本月', f'{current_year}年{current_month}月'),
            ('今天', today_str),
            ('昨天', yesterday_str),
            ('本周', f'{week_start_str}起的本周'),
            ('上周', last_week_str),
        ]
        # 按模式长度降序排列，长模式优先替换
        dynamic_replacements.sort(key=lambda x: len(x[0]), reverse=True)
        # 替换所有出现的时间表达式
        for pattern, replacement in dynamic_replacements:
            if pattern in result:
                result = result.replace(pattern, replacement)
        
        # 英文时间表达式规范化（大小写不敏感）
        en_dynamic_replacements = [
            ('next month', f'{next_month_year}-{int(next_month):02d}'),
            ('last month', f'{last_month_year}-{int(last_month):02d}'),
            ('this month', f'{current_year}-{int(current_month):02d}'),
            ('next quarter', f'{next_quarter_year} Q{next_quarter}'),
            ('last quarter', f'{prev_quarter_year} Q{prev_quarter}'),
            ('this quarter', f'{current_year} Q{current_quarter}'),
            ('next year', next_year),
            ('this year', current_year),
            ('last year', last_year),
            ('today', now.strftime('%Y-%m-%d')),
            ('yesterday', yesterday.strftime('%Y-%m-%d')),
            ('this week', f'week of {week_start.strftime("%Y-%m-%d")}'),
            ('last week', f'{last_week_start.strftime("%Y-%m-%d")} to {last_week_end.strftime("%Y-%m-%d")}'),
        ]
        en_dynamic_replacements.sort(key=lambda x: len(x[0]), reverse=True)
        for pattern, replacement in en_dynamic_replacements:
            if re.search(re.escape(pattern), result, re.IGNORECASE):
                result = re.sub(re.escape(pattern), replacement, result, flags=re.IGNORECASE)

        return result

    @staticmethod
    def _expand_with_terminologies(question: str, terminologies: List[Dict] = None) -> str:
        """基于术语库进行同义词扩展

         增强为模糊匹配，不再仅依赖精确子串匹配
        支持：精确匹配、部分包含匹配、字符重叠匹配
        """
        if not terminologies:
            return question

        result = question
        expansions_added = 0
        max_expansions = 3  # 限制最多追加3个术语，避免查询过长降低嵌入质量
        for term in terminologies:
            if expansions_added >= max_expansions:
                break
            word = term.get('word', '') or term.get('term', '')
            description = term.get('description', '')
            if not word or not description:
                continue

            # 1. 精确匹配：查询中包含术语或描述
            if description in result and word not in result:
                result = result + f'（{word}）'
                expansions_added += 1
            elif word in result and len(description) < 20:
                result = result + f'（{description}）'
                expansions_added += 1
            else:
                # 2. 模糊匹配：术语的关键字符与查询有显著重叠
                # 提取术语和描述中的关键词（2字以上中文词）
                term_keywords = set(re.findall(r'[\u4e00-\u9fff]{2,}', word + description))
                question_keywords = set(re.findall(r'[\u4e00-\u9fff]{2,}', result))
                # 过滤通用词，避免"数据"、"分析"等高频词触发误匹配
                generic_words = {'数据', '分析', '系统', '管理', '信息', '处理', '查询', '统计',
                                 '报表', '平台', '服务', '功能', '模块', '操作', '记录', '结果'}
                term_keywords -= generic_words
                question_keywords -= generic_words
                # 提高模糊匹配阈值，减少噪音
                overlap = term_keywords & question_keywords
                overlap_ratio = len(overlap) / max(len(term_keywords), 1)
                if len(overlap) >= 2 and overlap_ratio >= 0.4 and word not in result:
                    result = result + f'（{word}）'
                    expansions_added += 1
                elif len(overlap) >= 1 and len(word) <= 4 and word not in result:
                    # 短术语（如"GMV"）只需1个关键词重叠，但要求该重叠词长度>=3
                    # 避免"数据"这种2字通用词触发匹配
                    long_overlaps = [w for w in overlap if len(w) >= 3]
                    if long_overlaps:
                        result = result + f'（{word}: {description[:15]}）'
                        expansions_added += 1
        return result

    @staticmethod
    def post_expand_with_terminologies(rewritten_query: str, terminology_results: List[Dict]) -> str:
        """后置术语扩展：在RAG检索完成后，利用检索到的术语增强查询"""
        if not terminology_results:
            return rewritten_query
        
        # 将检索结果转换为_expand_with_terminologies需要的格式
        term_list = []
        for t in terminology_results:
            word = t.get('word', '')
            description = t.get('description', '')
            if word and description:
                term_list.append({'word': word, 'description': description})
        
        return QueryRewriter._expand_with_terminologies(rewritten_query, term_list)

    @staticmethod
    def _extract_keywords(question: str) -> List[str]:
        """提取查询中的关键词"""
        keywords = []

        # ========== 优先提取复合标识符（标准编号、版本号等）==========
        _compound_patterns = [
            r'[A-Z]{2,}/[A-Z]\s*\d+[-.:]\d+',                  # GB/T 28001-2011
            r'[A-Za-z]*\d+[.:/-]\d+\+?',                        # 14428:2004+, 9001:2015
        ]
        _compound_ids = []
        for pat in _compound_patterns:
            for m in re.finditer(pat, question):
                _compound_ids.append(m.group())
        # 将复合标识符作为高优先级关键词
        for cid in _compound_ids:
            if cid not in keywords:
                keywords.append(cid)

        # 提取聚合关键词
        for kw in QueryRewriter.AGG_KEYWORDS:
            if kw in question:
                keywords.append(kw)

        # 提取排序关键词
        for kw in QueryRewriter.SORT_KEYWORDS:
            if kw in question:
                keywords.append(kw)

        # 提取数字（可能是Top-N或阈值）
        # 跳过已被复合标识符覆盖的数字，避免重复
        _compound_joined = ' '.join(_compound_ids)
        numbers = re.findall(r'\d+', question)
        for num in numbers:
            if num not in keywords and num not in _compound_joined:
                keywords.append(num)

        # ========== 中文关键词提取（基于停用字符切分）==========
        _cn_stop_chars = set(
            '了吗呢啊哦嗯吧呀么哈是在有这那个些什为怎'
            '？。，！、；：""''（）【】《》·…—～'
            '?.,!;:()[]<>'
        )
        # 额外的多字停用短语（查询中常见但无检索价值的词）
        # 而是作为 "X的Y" 结构中的助词，通过 _cn_stop_phrases 处理
        _cn_stop_phrases = [
            '什么', '怎么', '如何', '哪些', '哪个', '为什么', '是否', '能否', '可以',
            '一下', '一份', '一个', '这份', '那份', '请问', '帮我', '我想', '告诉我',
            '看看', '查一下', '给我', '多少',
            # 补充文档类查询中常见的无检索价值短语
            # 注意：长短语放前面，短短语放后面，避免短短语先匹配导致长短语失效
            '中提到的', '里提到的', '中说到的',
            '中提到', '提到的', '里面的', '文中的', '报告中', '文档中', '文件中',
            '里说的', '中说的', '中描述', '中介绍',
            # 无检索价值的介词/连词短语
            '关于', '对于', '有关', '针对', '根据', '按照', '基于',
            '中关于', '中对于', '中有关',
            # 可视化/展示指令词对检索无价值，应过滤
            # "用饼图展示各产品销售额" 中 "用饼图展示" 不应作为检索关键词
            '用饼图展示', '用柱状图展示', '用折线图展示', '用表格展示',
            '用饼图显示', '用柱状图显示', '用折线图显示', '用表格显示',
            '用饼图', '用柱状图', '用折线图', '用表格',
            '饼图展示', '柱状图展示', '折线图展示', '表格展示',
            '饼图显示', '柱状图显示', '折线图显示', '表格显示',
            '展示', '显示', '列出', '查询', '统计', '计算', '生成',
        ]

        # Step 1: 去除多字停用短语（替换为空格作为切分点）
        remaining_cn = question
        for phrase in _cn_stop_phrases:
            remaining_cn = remaining_cn.replace(phrase, ' ')

        # Step 1.5: 处理结构助词"的"——仅当它作为"X的Y"结构中的助词时切分
        _de_word_prefixes = '目标有总确实际'  # "目的"、"标的"、"有的"、"总的"、"确的"、"实的"、"际的"
        remaining_cn = re.sub(
            r'(?<=[\u4e00-\u9fff]{2})(?<![' + _de_word_prefixes + r'])的(?=[\u4e00-\u9fff])',
            ' ', remaining_cn
        )

        # Step 2: 按停用字符切分
        buf = []
        segments = []
        for ch in remaining_cn:
            if ch in _cn_stop_chars or ch == ' ':
                if buf:
                    segments.append(''.join(buf))
                    buf = []
            else:
                buf.append(ch)
        if buf:
            segments.append(''.join(buf))

        # Step 3: 从片段中提取关键词
        for seg in segments:
            # 提取纯中文子串
            cn_parts = re.findall(r'[\u4e00-\u9fff]+', seg)
            for phrase in cn_parts:
                if 2 <= len(phrase) <= 6:
                    if phrase not in keywords:
                        keywords.append(phrase)
                elif len(phrase) > 6:
                    # 长片段：提取不同长度的n-gram子串
                    for n in [4, 3, 2]:
                        for i in range(len(phrase) - n + 1):
                            sub = phrase[i:i + n]
                            if sub not in keywords:
                                keywords.append(sub)
                                break  # 每个窗口大小只取第一个命中
                        if len(keywords) >= 10:
                            break

            # 提取英文/混合片段
            en_parts = re.findall(r'[a-zA-Z][a-zA-Z0-9_]*', seg)
            for ep in en_parts:
                if len(ep) >= 2 and ep not in keywords:
                    keywords.append(ep)

        # ========== 英文关键词补充==========
        en_remaining = question
        for word in list(QueryRewriter.STOP_WORDS) + list(QueryRewriter.AGG_KEYWORDS.keys()) + list(
                QueryRewriter.SORT_KEYWORDS.keys()):
            if word.isascii():
                en_remaining = re.sub(r'\b' + re.escape(word) + r'\b', ' ', en_remaining, flags=re.IGNORECASE)
        en_phrases = [p.strip() for p in en_remaining.split() if p.strip().isascii() and len(p.strip()) >= 2]
        for ep in en_phrases:
            if ep not in keywords and not ep.isdigit():
                keywords.append(ep)

        # 去重保序，最多10个关键词
        seen = set()
        deduped = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                deduped.append(kw)
        return deduped[:10]

    @staticmethod
    def _detect_intent(question: str, ds_type: str = 'database') -> str:
        """意图路由 - 基于规则的查询意图分类（18步流程·步骤3）"""
        question_lower = question.lower().strip()

        # ========== PDF数据源：执行细粒度意图检测，但路由统一走文档问答 ==========
        if ds_type == 'pdf':
            # PDF 专属意图检测（不走 SQL 相关路径）
            # 1. 总结/概括类
            _pdf_summarize = ['总结', '概括', '概述', '摘要', '归纳', '梳理', '整理',
                              '主要内容', '核心内容', '关键内容', '重点内容',
                              '讲了什么', '说了什么', '写了什么', '包含什么', '介绍了什么',
                              '哪一段', '哪个部分', '目录', '大纲', '结构',
                              'summarize', 'summary', 'overview', 'abstract', 'outline']
            if any(kw in question_lower for kw in _pdf_summarize):
                return 'document_qa'  # 文档总结映射到 document_qa
            # 2. 对比/比较类
            _pdf_compare = ['对比', '比较', '区别', '异同', '差异', '不同',
                            'compare', 'comparison', 'difference', 'versus', 'vs']
            if any(kw in question_lower for kw in _pdf_compare):
                return 'comparison_analysis'
            # 3. 纯寒暄/无关
            if any(kw in question_lower for kw in ['你好', '你是谁', '谢谢', 'hello', 'hi', 'thanks']):
                if not any(kw in question_lower for kw in ['文档', '报告', '内容', 'document', 'report']):
                    return 'irrelevant_query'
            # 4. 默认：文档问答
            return 'document_qa'

        # ========== 数据上下文关键词（多处复用）==========
        data_context_patterns = ['数据', '销售', '收入', '利润', '成本', '金额',
                                 '订单', '用户', '客户', '产品', '库存', '业绩',
                                 '指标', '报表', '营收', '增长率', '转化率',
                                 '同比', '环比', '季度', '月度', '年度',
                                 '毛利', '净利', 'roi', 'gmv', '客单价',
                                 '复购', '留存', '流失', '坪效', '人效',
                                 '市场份额', 'kpi', '绩效', '渠道', '区域',
                                 # 财务/运营指标缩写（防止因缩写不在词表中导致误判为 irrelevant_query）
                                 # 全部转为小写，与 question_lower 匹配
                                 'roe', 'roa', 'arpu', 'arppu', 'ltv', 'cac',
                                 'dau', 'mau', 'wau', 'ctr', 'cvr', 'cpc', 'cpm',
                                 'aov', 'sku', 'spu', 'nps', 'csat', 'sla',
                                 'mrr', 'arr', 'ebitda', 'eps', 'p/e',
                                 '周转率', '毛利率', '净利率', '负债率', '资产',
                                 '应收', '应付', '现金流', '净资产', '总资产',
                                 '出货量', '退货', '退款', '签约', '续费',
                                 '工单', '工时', '产能', '良品率', '合格率',
                                 # 英文数据上下文关键词
                                 'data', 'sales', 'revenue', 'profit', 'cost', 'amount',
                                 'order', 'customer', 'product', 'inventory', 'performance',
                                 'metric', 'report', 'growth rate', 'conversion rate',
                                 'yoy', 'mom', 'quarter', 'monthly', 'annual',
                                 'margin', 'retention', 'churn', 'market share',
                                 'turnover', 'budget', 'expense', 'invoice', 'payment',
                                 'subscription', 'refund', 'shipment', 'headcount',
                                 'utilization', 'throughput', 'yield rate', 'defect rate']

        # ========== 7. 连续追问（follow_up）==========
        follow_up_patterns = [
            '上面', '上述', '刚才', '之前', '前面', '上一个',
            '继续', '接着', '进一步', '再看看', '再分析',
            '那么', '还有呢', '然后呢', '其他的呢',
            '同样的', '类似的', '换成', '改成', '改为',
            # 英文追问模式
            'above', 'previous', 'earlier', 'before',
            'continue', 'furthermore', 'also show', 'what about',
            'same for', 'similar to', 'change to', 'switch to',
        ]
        if any(kw in question_lower for kw in follow_up_patterns):
            # "继续帮我查一下销售额"同时匹配follow_up("继续")和fact_query("查")
            # 应优先路由到fact_query，因为用户有明确的数据查询意图
            fact_keywords = ['查询', '统计', '计算', '列出', '显示', '对比', '分析',
                           '预测', '预估', '排名', '排序', '筛选', '过滤', '趋势',
                           'query', 'statistics', 'calculate', 'list', 'show', 'compare',
                           'analyze', 'predict', 'forecast', 'rank', 'sort', 'filter', 'trend']
            has_fact_intent = any(kw in question_lower for kw in fact_keywords)
            if len(question_lower) <= 40 and not has_fact_intent and \
               not any(kw in question_lower for kw in data_context_patterns[:15]):
                return 'follow_up'

        # ========== 9. 无效/无关问题（最高优先级）==========
        general_patterns = ['你好', '你是谁', '你能做什么', '使用说明',
                           '谢谢', '感谢', 'hello', 'hi', 'help',
                           '怎么用', '如何使用', '功能介绍', '你叫什么',
                           '再见', 'bye', 'thanks', 'thank you']
        if any(kw in question_lower for kw in general_patterns):
            if not any(kw in question_lower for kw in ['查询', '数据', '分析', '报告', '文档', '统计',
                                                        'query', 'data', 'analysis', 'report', 'document', 'statistics']):
                return 'irrelevant_query'

        # ========== 6. 术语/指标解释 ==========
        term_explanation_patterns = [
            '是什么', '什么是', '什么意思', '怎么计算', '计算公式', '口径',
            '定义是', '含义', '指的是', '代表什么', '缩写', '全称',
            '解释一下', '解释下', '请解释', '帮我解释',
            'what is', 'what does', 'define', 'meaning of'
        ]
        if any(kw in question_lower for kw in term_explanation_patterns):
            # 将'解释'加入排除列表
            data_op_words = ['查询', '统计', '列出', '显示', '对比', '分析', '解释',
                             'query', 'statistics', 'list', 'show', 'compare', 'analyze', 'explain']
            # 强术语解释模式优先返回（"怎么计算"、"计算公式"、"解释一下"等）
            # "ROI怎么计算" 是问术语定义，不是要求系统做计算
            strong_term_patterns = ['怎么计算', '计算公式', '口径', '是什么', '什么是', '什么意思',
                                    '定义是', '含义', '指的是', '代表什么', '缩写', '全称',
                                    '解释一下', '解释下', '请解释', '帮我解释',
                                    'what is', 'what does', 'define', 'meaning of',
                                    'please explain', 'explain to me', 'can you explain']
            # 区分中英文的术语解释模式
            cn_strong_term = ['怎么计算', '计算公式', '口径', '是什么', '什么是', '什么意思',
                              '定义是', '含义', '指的是', '代表什么', '缩写', '全称',
                              '解释一下', '解释下', '请解释', '帮我解释']
            en_strong_term = ['define', 'meaning of', 'please explain', 'explain to me', 'can you explain']
            en_weak_term = ['what is', 'what does']  # 英文弱信号，需排除数据上下文
            # 当"总结/概括"类关键词与"是什么"共现时，不应走术语解释
            _has_summarize_signal = any(kw in question_lower for kw in
                                        ['总结', '概括', '概述', '摘要', '归纳', '梳理', '整理',
                                         '主要内容', '核心内容', '讲了什么', '说了什么', '包含什么',
                                         'summarize', 'summary', 'overview'])
            if any(kw in question_lower for kw in cn_strong_term + en_strong_term):
                if not _has_summarize_signal:
                    return 'term_explanation'
                # 有总结信号 → 跳过术语解释，让后续的总结/概括类检测处理
            elif any(kw in question_lower for kw in en_weak_term):
                # "What is the total sales" 包含数据上下文 → 不走术语解释
                if not any(kw in question_lower for kw in data_context_patterns):
                    return 'term_explanation'
                # 包含数据上下文 → 跳过术语解释，继续后续意图检测
            elif not _has_summarize_signal and not any(kw in question_lower for kw in data_op_words):
                # 无总结信号且无数据操作词 → 术语解释
                return 'term_explanation'

        # ========== 6b. 纯知识/概念性问题检测（优先于数据查询路由）==========
        concept_patterns = [
            '应用场景', '使用场景', '适用场景', '落地场景',
            '技术方案', '技术架构', '技术原理', '技术路线', '技术栈',
            '方法论', '最佳实践', '设计模式', '解决方案',
            '优缺点', '优势', '劣势', '区别', '异同',
            '发展趋势', '行业趋势', '技术趋势',
            '如何实现', '怎么实现', '实现方式', '实现原理',
            '有哪些方法', '有哪些方式', '有哪些类型', '有哪些种类',
            '有哪些框架', '有哪些工具', '有哪些平台',
            # 英文概念性模式
            'use case', 'scenario', 'architecture', 'principle',
            'methodology', 'best practice', 'design pattern', 'solution',
            'pros and cons', 'advantage', 'disadvantage', 'difference',
            'how to implement', 'implementation', 'what are the methods',
            'what frameworks', 'what tools',
        ]
        # 技术/学术领域关键词（表明问题属于知识领域而非数据查询）
        tech_domain_patterns = [
            '大模型', '模型', '算法', '深度学习', '机器学习', '人工智能', 'ai', 'llm',
            '知识图谱', 'nlp', '自然语言处理', '神经网络', '向量', '嵌入',
            'rag', '检索增强', '微调', 'fine-tune', 'prompt',
            '架构', '框架', '中间件', '协议', '标准',
            '编程', '开发', '部署', '运维', '容器', '微服务',
        ]
        has_concept = any(kw in question_lower for kw in concept_patterns)
        has_tech_domain = any(kw in question_lower for kw in tech_domain_patterns)
        # 如果同时包含概念性模式词和技术领域词，且不包含数据上下文关键词 → 知识性问题
        if has_concept and has_tech_domain:
            if not any(kw in question_lower for kw in data_context_patterns):
                return 'term_explanation'
        # 仅有技术领域词 + "哪些/哪个/如何" 等提问词，且无数据上下文 → 知识性问题
        if has_tech_domain and not any(kw in question_lower for kw in data_context_patterns):
            knowledge_question_words = ['哪些', '哪个', '如何', '怎么', '什么', '为什么', '能否', '是否', '可以',
                                        'which', 'what', 'how', 'why', 'can', 'could', 'should']
            if any(kw in question_lower for kw in knowledge_question_words):
                return 'term_explanation'

        # ========== 5. 数据预测 ==========
        prediction_patterns = ['预测', '预估', '预计', '趋势预测', '走势预测', '增长预测',
                              'forecast', 'predict']
        has_explicit_predict = any(kw in question_lower for kw in ['预测', '预估', '预计', 'forecast', 'predict'])
        if any(kw in question_lower for kw in prediction_patterns):
            if has_explicit_predict or not any(kw in question_lower for kw in ['分析趋势', '趋势分析']):
                return 'prediction'
        if any(kw in question_lower for kw in ['未来', '下个月', '下季度', '明年',
                                              'future', 'next month', 'next quarter', 'next year']):
            if any(kw in question_lower for kw in ['会', '将', '可能', '预计', '预测', '多少',
                                                    'will', 'would', 'might', 'expect', 'estimate', 'how much']):
                return 'prediction'

        # ========== 总结/概括类 → 统计分析 ==========
        summarization_patterns = ['总结', '概括', '概述', '摘要', '归纳', '梳理', '整理',
                                  '主要内容', '核心内容', '关键内容', '重点内容',
                                  '讲了什么', '说了什么', '写了什么', '包含什么', '介绍了什么',
                                  '哪一段', '哪个部分',
                                  '总览', '概览', '概况', '数据概览', '数据总览',
                                  'summarize', 'summary', 'overview', 'abstract']
        if any(kw in question_lower for kw in summarization_patterns):
            return 'statistical_analysis'

        # ========== 3. 对比分析（优先于统计分析和趋势分析）==========
        comparison_patterns = ['对比', '比较', '对照', '相比', '差异', '差距',
                              '同比', '环比', '跨地区', '跨品类', '跨时间',
                              'vs', 'versus', 'compare', 'comparison', 'differ',
                              '哪个更', '哪个高', '哪个低', '哪个好', '哪个多',
                              'which is higher', 'which is lower', 'which is more',
                              'difference between', 'compared to']
        # "哪个" + 动词 + 比较形容词（如"哪个卖得好"、"哪个跑得快"）
        if re.search(r'哪个.{0,6}[好坏多少高低大小快慢强弱]', question_lower):
            if any(kw in question_lower for kw in data_context_patterns):
                return 'comparison_analysis'
        if any(kw in question_lower for kw in comparison_patterns):
            if any(kw in question_lower for kw in data_context_patterns):
                return 'comparison_analysis'
            # 强对比词直接路由（但需排除"比较"作为程度副词的用法，如"比较好"、"比较多"）
            strong_compare = ['对比', '同比', '环比', 'compare', 'vs']
            if any(kw in question_lower for kw in strong_compare):
                return 'comparison_analysis'
            # "比较"单独出现时，需要有数据上下文才路由（排除"比较好用"等程度副词用法）
            if '比较' in question_lower:
                # "比较" 后面跟形容词/副词 → 程度副词，不是对比分析
                if not re.search(r'比较[好坏大小多少高低快慢强弱]', question_lower):
                    # 无数据上下文时，"比较"可能是知识性问题（如"比较一下这两个方案"）
                    # 仅当有数据上下文或明确的对比对象时才路由到 comparison_analysis
                    if any(kw in question_lower for kw in data_context_patterns):
                        return 'comparison_analysis'

        # ========== 4. 趋势分析 ==========
        trend_patterns = ['趋势', '走势', '变化', '波动', '升降', '涨跌',
                         '变化规律', '变化趋势', '增长趋势', '下降趋势',
                         'trend', 'fluctuation', 'growth pattern']
        if any(kw in question_lower for kw in trend_patterns):
            if any(kw in question_lower for kw in data_context_patterns):
                return 'trend_analysis'
            # 强趋势词直接路由，但排除纯知识性问题（如"AI发展趋势"、"行业趋势分析"）
            # 如果同时包含技术/学术领域关键词，说明是知识性问题，不走SQL路径
            if any(kw in question_lower for kw in ['趋势', '走势', 'trend']):
                if not has_tech_domain:
                    return 'trend_analysis'

        # 将"增长/下降"检测提前到 statistical_analysis 之前
        # 增加数据上下文检查，避免纯知识性问题（如"公司增长策略"）被误路由到SQL路径
        if any(kw in question_lower for kw in ['增长', '下降', 'growth', 'decline', 'increase', 'decrease']):
            if any(kw in question_lower for kw in data_context_patterns):
                return 'trend_analysis'
            # 无数据上下文但有强趋势信号词（增长率、下降幅度等）也路由到趋势分析
            strong_trend_with_growth = ['增长率', '下降率', '增长幅度', '下降幅度', '增长趋势', '下降趋势',
                                        'growth rate', 'decline rate', 'rate of increase', 'rate of decrease']
            if any(kw in question_lower for kw in strong_trend_with_growth):
                return 'trend_analysis'

        # ========== 2. 统计分析（含深度分析）==========
        analysis_patterns = ['分析', '解读', '评估', '诊断', '洞察',
                            '原因是什么', '为什么', '影响因素', '相关性',
                            '深入分析', '详细分析', '全面分析',
                            'analyze', 'analysis', 'insight', 'explain why']
        # '解释' 关键词路由冲突
        if '解释' in question_lower or 'explain' in question_lower:
            # 如果包含明确的术语解释模式（"解释一下"、"请解释"等），优先走 term_explanation
            explicit_explain_patterns = ['解释一下', '解释下', '请解释', '帮我解释',
                                         'please explain', 'explain to me', 'can you explain']
            if any(kw in question_lower for kw in explicit_explain_patterns):
                return 'term_explanation'
            # 去停用词后 "解释一下毛利率"→"解释毛利率"，"一下"被去除
            analysis_signal_in_explain = ['原因', '下降', '增长', '变化', '趋势', '波动',
                                          '为什么', '影响', '因素', '问题',
                                          'reason', 'cause', 'decline', 'growth', 'change', 'why']
            if not any(kw in question_lower for kw in analysis_signal_in_explain):
                return 'term_explanation'
            if any(kw in question_lower for kw in data_context_patterns):
                return 'statistical_analysis'
        elif any(kw in question_lower for kw in analysis_patterns):
            if any(kw in question_lower for kw in data_context_patterns):
                return 'statistical_analysis'
            strong_analysis = ['深入分析', '详细分析', '全面分析', 'analyze', 'analysis',
                              '帮我分析', '分析一下', '分析下', '做个分析', '做分析',
                              'deep analysis', 'detailed analysis', 'comprehensive analysis']
            if any(kw in question_lower for kw in strong_analysis):
                return 'statistical_analysis'
            weak_analysis = ['为什么', '原因是什么', '影响因素', '相关性',
                            'why', 'reason', 'cause', 'factor', 'correlation']
            if any(kw in question_lower for kw in weak_analysis):
                return 'ambiguous_query'
            return 'statistical_analysis'

        # ========== 1. 事实数据查询 ==========
        fact_query_patterns = ['查询', '查一下', '查下', '看一下', '看下',
                               '列出', '显示', '展示',
                               '筛选', '过滤',
                               '柱状图', '折线图', '饼图', '表格', '图表',
                               '用图', '用表', '画图', '画个', '生成图',
                               '做个图', '做图', '绘制', '可视化',
                               '算一下', '算算', '帮我算',
                               'show', 'list', 'query', 'chart', 'graph',
                               'display', 'filter', 'select', 'find',
                               'bar chart', 'line chart', 'pie chart',
                               'visualize', 'plot', 'draw', 'table']
        if any(kw in question_lower for kw in fact_query_patterns):
            return 'fact_query'

        # 聚合类关键词单独检测，路由到 statistical_analysis
        # 这些词表达的是统计分析意图，不应归入 fact_query
        agg_fact_patterns = ['统计', '计算', '合计', '平均', '均值', '数量', '求和',
                             '排名', '排序', '最高', '最低', 'top',
                             'count', 'total', 'average']
        if any(kw in question_lower for kw in agg_fact_patterns):
            return 'statistical_analysis'

        if '多少' in question_lower or 'how many' in question_lower or 'how much' in question_lower:
            # "多少"/"how many"/"how much" 需要有数据上下文才路由到数据查询
            if any(kw in question_lower for kw in data_context_patterns):
                return 'fact_query'
            # 无数据上下文也大概率是数据查询（如"有多少条记录"）
            return 'fact_query'

        if any(kw in question_lower for kw in ['哪些', '哪个', 'which', 'what are']):
            # "哪些/哪个/which" 只有在涉及数据上下文时才路由到数据查询
            if any(kw in question_lower for kw in data_context_patterns):
                return 'fact_query'
            # 无数据上下文 → 默认走 irrelevant_query（后续由 general_chat 处理）

        if re.search(r'个数(?!据)', question_lower):
            return 'fact_query'

        # ========== 8. 模糊/不完整提问 ==========
        vague_data_patterns = ['情况', '怎么样', '如何', '看看', '看一下', '查看', '了解', '报告',
                               '汇报', '明细', '详情', '清单',
                               '给我', '帮我', '告诉我', '我想知道', '我想看',
                               # 英文模糊查询模式
                               'how is', 'how are', 'what about', 'look at', 'check',
                               'overview', 'summary', 'detail', 'breakdown',
                               'i want to know', 'i want to see', 'give me', 'show me']
        if any(kw in question_lower for kw in vague_data_patterns):
            if any(kw in question_lower for kw in data_context_patterns):
                return 'ambiguous_query'
        
        time_patterns = ['今年', '去年', '上个月', '这个月', '本月', '本年',
                        '上季度', '本季度', '今天', '昨天', '本周', '上周',
                        '最近', '最新', '近期',
                        '2024', '2025', '2026', '一月', '二月', '三月',
                        # 英文时间模式
                        'this year', 'last year', 'last month', 'this month',
                        'last quarter', 'this quarter', 'today', 'yesterday',
                        'this week', 'last week', 'recent', 'latest',
                        'january', 'february', 'march', 'april', 'may', 'june',
                        'july', 'august', 'september', 'october', 'november', 'december']
        if any(kw in question_lower for kw in time_patterns):
            if any(kw in question_lower for kw in data_context_patterns):
                return 'fact_query'
        
        group_patterns = ['各', '每个', '每月', '每年', '每天', '每周', '按',
                         # 英文分组模式
                         'each', 'every', 'per', 'by', 'group by', 'grouped by']
        if any(kw in question_lower for kw in group_patterns):
            if any(kw in question_lower for kw in data_context_patterns):
                return 'fact_query'

        # ========== 默认：根据是否包含数据上下文决定路由 ==========
        if any(kw in question_lower for kw in data_context_patterns):
            return 'ambiguous_query'
        return 'irrelevant_query'

    @staticmethod
    def _explain_intent(question: str, intent: str, ds_type: str = 'database') -> List[str]:
        """解释意图判定依据 — 返回命中的关键词列表"""
        question_lower = question.lower().strip()
        matched = []

        # PDF 数据源的意图解释
        if ds_type == 'pdf':
            _pdf_kws = {
                'document_qa': ['总结', '概括', '概述', '摘要', '归纳', '梳理',
                                '主要内容', '核心内容', '讲了什么', '说了什么',
                                'summarize', 'summary', 'overview'],
                'comparison_analysis': ['对比', '比较', '区别', '异同', '差异',
                                        'compare', 'comparison', 'difference'],
                'irrelevant_query': ['你好', '你是谁', '谢谢', 'hello', 'hi', 'thanks'],
            }
            for kw in _pdf_kws.get(intent, []):
                if kw in question_lower:
                    matched.append(kw)
            if not matched and intent == 'document_qa':
                matched.append('PDF默认：文档问答')
            return matched[:5]

        # 各意图对应的关键词池（与 _detect_intent 中的规则保持一致）
        _intent_keyword_pools = {
            'follow_up': ['上面', '上述', '刚才', '之前', '前面', '上一个',
                          '继续', '接着', '进一步', '再看看', '再分析',
                          '那么', '还有呢', '然后呢', '其他的呢',
                          'above', 'previous', 'earlier', 'continue', 'what about'],
            'irrelevant_query': ['你好', '你是谁', '你能做什么', '使用说明',
                                 '谢谢', '感谢', 'hello', 'hi', 'help',
                                 '怎么用', '如何使用', '功能介绍', '再见', 'bye'],
            'term_explanation': ['是什么', '什么是', '什么意思', '怎么计算', '计算公式', '口径',
                                 '定义是', '含义', '指的是', '代表什么', '解释一下', '解释下',
                                 '应用场景', '技术方案', '技术架构', '方法论', '优缺点',
                                 'what is', 'what does', 'define', 'meaning of'],
            'prediction': ['预测', '预估', '预计', '趋势预测', '走势预测',
                           '未来', '下个月', '下季度', '明年',
                           'forecast', 'predict', 'future', 'next month', 'next year'],
            'comparison_analysis': ['对比', '比较', '对照', '相比', '差异', '差距',
                                    '同比', '环比', '跨地区', '跨品类', 'vs', 'compare',
                                    '哪个更', '哪个高', '哪个低'],
            'trend_analysis': ['趋势', '走势', '变化', '波动', '升降', '涨跌',
                               '增长', '下降', 'trend', 'growth', 'decline'],
            'statistical_analysis': ['分析', '解读', '评估', '诊断', '洞察',
                                     '原因是什么', '为什么', '影响因素', '相关性',
                                     '深入分析', '详细分析', '统计', '计算', '合计',
                                     '平均', '均值', '排名', '排序', '最高', '最低',
                                     '总结', '概括', '概述', '摘要', '归纳', '梳理', '整理',
                                     '总览', '概览', '概况',
                                     'analyze', 'analysis', 'insight', 'count', 'total', 'average',
                                     'summarize', 'summary', 'overview'],
            'fact_query': ['查询', '列出', '显示', '展示', '筛选', '过滤',
                           '柱状图', '折线图', '饼图', '图表', '可视化',
                           '画图', '画个', '生成图', '多少',
                           'show', 'list', 'query', 'chart', 'filter', 'how many'],
            'ambiguous_query': ['情况', '怎么样', '如何', '看看', '查看', '了解',
                                '报告', '明细', '详情',
                                'how is', 'detail', 'breakdown'],
        }

        # 数据上下文关键词（辅助判定依据）
        _data_context_sample = ['数据', '销售', '收入', '利润', '成本', '金额',
                                '订单', '用户', '客户', '产品', '库存', '业绩',
                                '毛利', '净利', 'roi', 'gmv', '客单价',
                                'revenue', 'profit', 'cost', 'sales', 'order']

        # 1. 从对应意图的关键词池中查找命中
        pool = _intent_keyword_pools.get(intent, [])
        for kw in pool:
            if kw in question_lower and kw not in matched:
                matched.append(kw)

        # 2. 补充数据上下文命中（很多意图需要数据上下文共现才触发）
        for kw in _data_context_sample:
            if kw.lower() in question_lower and kw not in matched:
                matched.append(f'{kw}(数据上下文)')
                break  # 只展示1个数据上下文命中，避免过多

        # 3. 聚合关键词命中（statistical_analysis / fact_query 常用）
        if intent in ('statistical_analysis', 'fact_query', 'trend_analysis'):
            for kw, agg_type in QueryRewriter.AGG_KEYWORDS.items():
                if kw in question_lower and kw not in matched:
                    matched.append(f'{kw}({agg_type})')

        # 4. 时间关键词命中（prediction 常用）
        if intent == 'prediction':
            time_kws = ['未来', '下个月', '下季度', '明年', '会', '将', '可能',
                        'future', 'next month', 'will', 'would']
            for kw in time_kws:
                if kw in question_lower and kw not in matched:
                    matched.append(kw)

        # 如果没有找到任何命中（fallback 路径），标注默认规则
        if not matched:
            if intent == 'ambiguous_query':
                matched.append('含数据上下文但无明确操作词 → 模糊查询')
            elif intent == 'irrelevant_query':
                matched.append('无数据上下文关键词 → 默认无关')

        return matched[:6]

    @staticmethod
    def _is_trivial_chat(question: str) -> bool:
        """判断是否为纯寒暄/打招呼类问题（不需要任何RAG检索）

        与_detect_intent配合使用：
        - _detect_intent返回'irrelevant_query'时，进一步判断是否为纯寒暄
        - 纯寒暄：跳过RAG，快速回答（如"你好"、"谢谢"）
        - 非纯寒暄的irrelevant_query：仍执行RAG，让LLM结合知识回答
        """
        question_lower = question.lower().strip()
        q = question.strip()
        
        # 完全匹配寒暄词 → 纯寒暄（最快路径）
        exact_trivial = {
            '你好', '你好呀', '你好啊', '嗨', '嗨嗨', 'hi', 'hello', 'hey',
            '谢谢', '感谢', '谢谢你', '谢了', 'thanks', 'thank you', 'thx',
            '再见', '拜拜', 'bye', 'goodbye',
            '你是谁', '你叫什么', '你叫什么名字',
            '你能做什么', '你会什么', '你有什么功能',
            '使用说明', '功能介绍', '怎么用', '如何使用',
            'help', '帮助',
            '早上好', '下午好', '晚上好', '晚安',
            '好的', '知道了', '明白了', '收到', 'ok', 'okay',
            '哈哈', '哈哈哈', '嗯', '嗯嗯', '哦', '噢',
            '测试', 'test', '试试',
        }
        if q in exact_trivial or question_lower in exact_trivial:
            return True
        
        # 短问题（<=10字符）且匹配寒暄模式 → 纯寒暄
        trivial_patterns = [
            '你好', '你是谁', '你能做什么', '使用说明',
            '谢谢', '感谢', 'hello', 'hi', 'help',
            '怎么用', '如何使用', '功能介绍', '你叫什么',
            '再见', 'bye', 'thanks', 'thank you',
            '早上好', '下午好', '晚上好', '嗨',
            '好的', '知道了', '明白了', '收到',
        ]
        if len(q) <= 10 and any(kw in question_lower for kw in trivial_patterns):
            # 额外检查：如果包含数据相关词，不算纯寒暄
            data_words = ['数据', '分析', '查询', '统计', '报告', '文档', '预测', '销售', '订单']
            if not any(dw in question for dw in data_words):
                return True
        
        return False

    @staticmethod
    def _generate_expanded_queries(question: str, keywords: List[str], intent: str) -> List[str]:
        """
        生成扩展查询，用于多路检索提升召回率
        
         原代码检查intent=='aggregation'和'ranking'，但_detect_intent
        从不返回这些值（它返回data_query/analysis/prediction/general_chat）
        现在使用实际的intent值 + 关键词检测来生成扩展查询
        """
        expanded = []

        # 基于关键词检测聚合意图
        if intent in ('data_query', 'fact_query', 'trend_analysis'):
            has_agg = any(kw in question for kw in QueryRewriter.AGG_KEYWORDS)
            has_sort = any(kw in question for kw in QueryRewriter.SORT_KEYWORDS)
            
            if has_agg:
                core = question
                for kw in QueryRewriter.AGG_KEYWORDS:
                    core = core.replace(kw, '')
                core = core.strip()
                if core and core != question and len(core) >= 2:
                    expanded.append(core)
            
            if has_sort:
                core = question
                for kw in QueryRewriter.SORT_KEYWORDS:
                    core = core.replace(kw, '')
                core = re.sub(r'\d+', '', core).strip()
                if core and core != question and len(core) >= 2:
                    expanded.append(core)
        
        # comparison_analysis 独立分支（原代码被第一个 if 吞掉）
        elif intent == 'comparison_analysis':
            core = re.sub(r'(对比|比较|同比|环比|差异|差距|compare|comparison|versus|vs|differ)', '', question, flags=re.IGNORECASE).strip()
            if core and core != question and len(core) >= 2:
                expanded.append(core)
            # 对比查询也可能包含聚合关键词
            has_agg = any(kw in question for kw in QueryRewriter.AGG_KEYWORDS)
            if has_agg:
                agg_core = question
                for kw in QueryRewriter.AGG_KEYWORDS:
                    agg_core = agg_core.replace(kw, '')
                agg_core = agg_core.strip()
                if agg_core and agg_core != question and len(agg_core) >= 2 and agg_core not in expanded:
                    expanded.append(agg_core)

        elif intent in ('analysis', 'statistical_analysis'):
            core = re.sub(r'(分析|解读|评估|诊断|洞察|原因|影响|analyze|analysis|insight|evaluate|diagnose)', '', question, flags=re.IGNORECASE).strip()
            if core and core != question and len(core) >= 2:
                expanded.append(core)
        
        elif intent == 'prediction':
            core = re.sub(r'(预测|预估|预计|未来|明年|下个月|predict|forecast|future|next month|next year)', '', question, flags=re.IGNORECASE).strip()
            if core and core != question and len(core) >= 2:
                expanded.append(core)

        elif intent == 'document_qa':
            # 文档问答：提取核心问题作为扩展查询（去除文档相关修饰词）
            core = re.sub(r'(文档|报告|根据|里面|提到|内容|document|report|according to|mentioned)', '', question, flags=re.IGNORECASE).strip()
            if core and core != question and len(core) >= 2:
                expanded.append(core)

        elif intent == 'term_explanation':
            # 术语解释：提取被解释的核心术语作为扩展查询
            core = re.sub(r'(是什么|什么是|什么意思|怎么计算|计算公式|口径|定义|含义|解释|what is|what does|define|meaning of|explain)', '', question, flags=re.IGNORECASE).strip()
            if core and core != question and len(core) >= 2:
                expanded.append(core)

        elif intent == 'follow_up':
            # 追问：去除指代词，保留核心实体
            core = re.sub(r'(上面|上述|刚才|之前|继续|接着|进一步|那么|这个|这些|那个|那些|它的|再|above|previous|earlier|continue|furthermore|also|what about)', '', question, flags=re.IGNORECASE).strip()
            if core and core != question and len(core) >= 2:
                expanded.append(core)

        # 使用关键词组合生成简短查询
        if len(keywords) >= 2:
            short_query = ' '.join(keywords[:3])
            if short_query != question and short_query not in expanded:
                expanded.append(short_query)

        seen = set()
        deduped = []
        for q in expanded:
            q_stripped = q.strip()
            if q_stripped and q_stripped not in seen and 2 <= len(q_stripped) <= 100:
                seen.add(q_stripped)
                deduped.append(q_stripped)

        return deduped[:3]  # 最多3个扩展查询


    @staticmethod
    def decompose_complex_query(question: str) -> Dict[str, any]:
        """复杂查询分解：将复杂的分析请求拆解为多个子任务"""
        if not question or not question.strip():
            return {'is_complex': False, 'sub_tasks': [question], 'task_type': 'single'}

        sub_tasks = []
        task_type = 'single'

        # 检测对比类查询
        comparison_patterns = [
            r'对比(.+?)和(.+?)的(.+)',
            r'比较(.+?)与(.+?)的(.+)',
            r'(.+?)和(.+?)哪个(.+)',
            r'(.+?)vs(.+)',
        ]
        for pattern in comparison_patterns:
            match = re.search(pattern, question)
            if match:
                task_type = 'comparison'
                groups = match.groups()
                if len(groups) >= 3:
                    sub_tasks.append(f'{groups[0].strip()}的{groups[2].strip()}')
                    sub_tasks.append(f'{groups[1].strip()}的{groups[2].strip()}')
                elif len(groups) >= 2:
                    sub_tasks.append(groups[0].strip())
                    sub_tasks.append(groups[1].strip())
                break

        # 检测多步骤查询（"并"、"然后"、"同时"连接的多个操作）
        if not sub_tasks:
            # 移除过短的连接词"并"，它会错误匹配"并列"、"合并"、"并且"等词
            # "并且"已在列表中，足以覆盖"并"的合理用例
            multi_step_connectors = ['并且', '同时', '然后', '以及', '还要', '另外']
            for connector in multi_step_connectors:
                if connector in question:
                    parts = question.split(connector)
                    if len(parts) >= 2:
                        task_type = 'multi_step'
                        # 增强动词补充逻辑
                        first_part = parts[0].strip()
                        action_verbs = ['查询', '统计', '分析', '对比', '比较', '计算', '显示', '列出', '预测']
                        # 从整个问题中提取第一个出现的动词作为全局动词前缀
                        global_verb_prefix = ''
                        for v in action_verbs:
                            if v in question:
                                global_verb_prefix = v
                                break
                        for i, part in enumerate(parts):
                            part = part.strip()
                            if len(part) >= 3:
                                if i > 0:
                                    # 检查后续片段是否缺少动词（以名词/时间词开头）
                                    has_verb = any(v in part for v in action_verbs)
                                    if not has_verb:
                                        # 优先从第一个片段提取动词，回退到全局动词
                                        verb_prefix = ''
                                        for v in action_verbs:
                                            if v in first_part:
                                                verb_prefix = v
                                                break
                                        if not verb_prefix:
                                            verb_prefix = global_verb_prefix
                                        if verb_prefix:
                                            part = f'{verb_prefix}{part}'
                                sub_tasks.append(part)
                        break

        # 检测趋势分析类查询
        if not sub_tasks:
            trend_keywords = ['趋势', '变化', '增长率', '同比', '环比', '走势']
            if any(kw in question for kw in trend_keywords):
                task_type = 'trend_analysis'
                # 趋势分析通常需要先获取数据再分析
                core = re.sub(r'(趋势|变化|增长率|同比|环比|走势|分析)', '', question).strip()
                if core:
                    sub_tasks.append(f'查询{core}数据')
                    sub_tasks.append(question)  # 原始查询作为分析任务

        is_complex = len(sub_tasks) >= 2

        if not sub_tasks:
            sub_tasks = [question]

        # 语义完整性检查
        if is_complex:
            entity_pattern = re.compile(
                r'[\u4e00-\u9fff]{2,}|[a-zA-Z]{2,}|\d+(?:\.\d+)?(?:万|亿|%|元)?'
            )
            # 纯动词/助词不算有效实体
            verb_only_pattern = re.compile(
                r'^(?:查询|统计|分析|对比|比较|计算|显示|列出|预测|帮我|请|看看|了解)+$'
            )
            valid_tasks = []
            for task in sub_tasks:
                entities = entity_pattern.findall(task)
                # 过滤掉纯动词匹配
                meaningful = [e for e in entities if not verb_only_pattern.match(e)]
                if meaningful:
                    valid_tasks.append(task)
            if len(valid_tasks) < 2:
                # 有效子任务不足2个，回退为单任务
                return {
                    'is_complex': False,
                    'sub_tasks': [question],
                    'task_type': 'single'
                }
            sub_tasks = valid_tasks

        return {
            'is_complex': is_complex,
            'sub_tasks': sub_tasks,
            'task_type': task_type
        }

    @staticmethod
    def map_intent_to_dialogue_intent(rewriter_intent: str) -> str:
        """统一9种细粒度意图与DialogueIntent枚举的映射"""
        _INTENT_MAP = {
            # 数据查询类 → SQL路径
            'fact_query': 'query',
            'statistical_analysis': 'analysis',
            'comparison_analysis': 'query',
            'trend_analysis': 'query',
            # 预测类
            'prediction': 'prediction',
            # 非SQL类 → 直接回答路径
            'term_explanation': 'query',
            'follow_up': 'query',
            'ambiguous_query': 'query',
            'irrelevant_query': 'query',
            # 兼容旧意图
            'data_query': 'query',
            'analysis': 'analysis',
            'general_chat': 'query',
        }
        return _INTENT_MAP.get(rewriter_intent, 'query')

    @staticmethod
    def map_to_route(intent: str) -> str:
        """将细粒度意图映射到4种处理路由（18步流程核心路由）"""
        _ROUTE_MAP = {
            'fact_query': 'data_query',
            'statistical_analysis': 'analysis',
            'comparison_analysis': 'analysis',
            'trend_analysis': 'analysis',
            'prediction': 'prediction',
            'term_explanation': 'general_chat',
            'follow_up': 'data_query',  # 追问：实际由llm.py在运行时继承上轮意图，此处为兜底默认值
            'ambiguous_query': 'general_chat',  # 模糊问题→主动反问
            'irrelevant_query': 'general_chat',  # 无关问题→礼貌拒绝
            # 兼容旧意图
            'data_query': 'data_query',
            'analysis': 'analysis',
            'general_chat': 'general_chat',
            'document_qa': 'general_chat',  # PDF文档问答→直接回答
        }
        return _ROUTE_MAP.get(intent, 'general_chat')
