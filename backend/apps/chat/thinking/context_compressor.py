"""上下文压缩模块 (Context Compression)"""
import re
from typing import List, Dict, Optional, Tuple

from common.utils.utils import ChatBILogUtil


class CompressorConfig:
    """上下文压缩器的可配置参数，支持按场景定制"""

    def __init__(
        self,
        max_terminologies: int = 5,
        max_sql_examples: int = 3,
        max_schema_length: int = 3000,
        min_similarity: float = 0.35,
        high_similarity: float = 0.7,
        max_custom_prompt_chars: int = 2000,
    ):
        self.max_terminologies = max_terminologies
        self.max_sql_examples = max_sql_examples
        self.max_schema_length = max_schema_length
        self.min_similarity = min_similarity
        self.high_similarity = high_similarity
        self.max_custom_prompt_chars = max_custom_prompt_chars


# 预置场景配置
COMPRESSOR_PRESETS: Dict[str, CompressorConfig] = {
    'default': CompressorConfig(),
    'analysis': CompressorConfig(max_terminologies=8, max_sql_examples=0, min_similarity=0.30),
    'prediction': CompressorConfig(max_terminologies=8, max_sql_examples=0, min_similarity=0.30),
    'sql_generation': CompressorConfig(max_terminologies=5, max_sql_examples=5, min_similarity=0.35),
}


class ContextCompressor:
    """上下文压缩器 - 优化RAG检索结果以减少Token消耗"""

    # 默认配置（保留类常量以兼容旧代码）
    DEFAULT_MAX_TERMINOLOGIES = 5
    DEFAULT_MAX_SQL_EXAMPLES = 3
    DEFAULT_MAX_SCHEMA_LENGTH = 3000  # 字符数
    DEFAULT_MIN_SIMILARITY = 0.35

    @staticmethod
    def _apply_overflow_truncation(
        compressed_terms: str,
        compressed_sql: str,
        compressed_schema: str,
        char_budget: int,
        caller: str = "compress",
    ) -> tuple:
        """溢出截断逻辑：当压缩后总长度超出预算时按优先级截断"""
        compressed_length = len(compressed_terms) + len(compressed_sql) + len(compressed_schema)
        if compressed_length <= char_budget:
            return compressed_terms, compressed_sql, compressed_schema

        overflow = compressed_length - char_budget
        ChatBILogUtil.warning(
            f"{caller} overflow: {compressed_length} > {char_budget}, "
            f"trimming {overflow} chars"
        )

        # 1. 截断术语（最低优先级）
        if len(compressed_terms) > 0 and overflow > 0:
            trim = min(overflow, len(compressed_terms))
            truncated = compressed_terms[:len(compressed_terms) - trim]
            last_close = truncated.rfind('</terminology>')
            if last_close > 0:
                candidate = truncated[:last_close + len('</terminology>')]
                if len(candidate) < len(compressed_terms):
                    truncated = candidate
            elif truncated.rfind('\n') > 0:
                truncated = truncated[:truncated.rfind('\n')]
            compressed_terms = truncated
            overflow = (len(compressed_terms) + len(compressed_sql) + len(compressed_schema)) - char_budget

        # 2. 截断SQL示例
        if len(compressed_sql) > 0 and overflow > 0:
            trim = min(overflow, len(compressed_sql))
            truncated = compressed_sql[:len(compressed_sql) - trim]
            found_tag = False
            for close_tag in ['</document-knowledge>', '</example>', '</sql-examples>']:
                last_close = truncated.rfind(close_tag)
                if last_close > 0:
                    candidate = truncated[:last_close + len(close_tag)]
                    if len(candidate) < len(compressed_sql):
                        truncated = candidate
                        found_tag = True
                        break
            if not found_tag:
                last_nl = truncated.rfind('\n')
                if last_nl > 0:
                    truncated = truncated[:last_nl]
            compressed_sql = truncated
            overflow = (len(compressed_terms) + len(compressed_sql) + len(compressed_schema)) - char_budget

        # 3. 截断Schema（最高优先级，最后兜底）
        if len(compressed_schema) > 0 and overflow > 0:
            target_len = max(0, len(compressed_schema) - overflow)
            truncated = compressed_schema[:target_len]
            last_table = max(
                truncated.rfind('\nTable'),
                truncated.rfind('\n表'),
                truncated.rfind('\n# Table'),
            )
            if last_table > len(truncated) // 2:
                truncated = truncated[:last_table]
            compressed_schema = truncated

        # 最终硬截断兜底：如果边界对齐导致总长度仍超出预算，强制截断Schema
        final_total = len(compressed_terms) + len(compressed_sql) + len(compressed_schema)
        if final_total > char_budget and len(compressed_schema) > 0:
            final_overflow = final_total - char_budget
            compressed_schema = compressed_schema[:max(0, len(compressed_schema) - final_overflow)]
            ChatBILogUtil.warning(
                f"{caller} hard truncation applied: schema trimmed by {final_overflow} chars"
            )

        return compressed_terms, compressed_sql, compressed_schema

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """估算文本的Token数量（分组估算）

        - 中文字符：1字符 ≈ 1.5 Token
        - 英文/数字：1字符 ≈ 0.25 Token
        - 标点/空白：1字符 ≈ 0.5 Token
        """
        if not text:
            return 0
        cn_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        en_chars = len(re.findall(r'[a-zA-Z0-9]', text))
        other_chars = len(text) - cn_chars - en_chars
        return int(cn_chars * 1.5 + en_chars * 0.25 + other_chars * 0.5)

    @staticmethod
    def get_config(scenario: str = 'default') -> CompressorConfig:
        """获取指定场景的压缩配置"""
        return COMPRESSOR_PRESETS.get(scenario, COMPRESSOR_PRESETS['default'])

    @staticmethod
    def compress(
        terminologies: str = "",
        sql_examples: str = "",
        schema: str = "",
        question: str = "",
        max_total_tokens: int = 800,
        config: Optional[CompressorConfig] = None,
        custom_prompt: str = "",
    ) -> Dict[str, str]:
        """压缩所有RAG上下文"""
        _cfg = config or CompressorConfig()

        # 自定义提示词纳入 token 预算管控
        # 截断超出预算的自定义提示词，防止无限制膨胀 prompt
        compressed_custom_prompt = custom_prompt
        if custom_prompt and len(custom_prompt) > _cfg.max_custom_prompt_chars:
            truncated = custom_prompt[:_cfg.max_custom_prompt_chars]
            # 在最后一个完整行处截断，避免截断到一半
            last_nl = truncated.rfind('\n')
            if last_nl > _cfg.max_custom_prompt_chars // 2:
                truncated = truncated[:last_nl]
            compressed_custom_prompt = truncated
            ChatBILogUtil.info(
                f"Custom prompt truncated: {len(custom_prompt)} -> {len(compressed_custom_prompt)} chars "
                f"(budget: {_cfg.max_custom_prompt_chars})"
            )

        result = {
            'terminologies': terminologies,
            'sql_examples': sql_examples,
            'schema': schema,
            'custom_prompt': compressed_custom_prompt,
            'compression_applied': False,
            'stats': {}
        }

        original_length = len(terminologies) + len(sql_examples) + len(schema)
        estimated_tokens = ContextCompressor._estimate_tokens(terminologies + sql_examples + schema)

        # 使用 Token 估算值而非字符数判断是否需要压缩
        if estimated_tokens <= max_total_tokens:
            result['stats'] = {
                'original_length': original_length,
                'compressed_length': original_length,
                'estimated_tokens': estimated_tokens,
                'compression_ratio': 1.0
            }
            return result

        # 将 Token 预算转换为字符预算（用于子模块截断）
        _all_text = terminologies + sql_examples + schema
        _cn = len(re.findall(r'[\u4e00-\u9fff]', _all_text))
        _en = len(re.findall(r'[a-zA-Z0-9]', _all_text))
        _other = len(_all_text) - _cn - _en
        _total_chars = len(_all_text) or 1
        # 每种字符类型的 chars_per_token：cn=1/1.5, en=1/0.25=4, other=1/0.5=2
        # 加权平均 chars_per_token
        _chars_per_token = (
            (_cn / _total_chars) * (1 / 1.5) +
            (_en / _total_chars) * (1 / 0.25) +
            (_other / _total_chars) * (1 / 0.5)
        ) if _total_chars > 0 else 1.2
        # 限制在合理范围内：最低0.8（纯中文），最高3.0（纯英文偏保守）
        _chars_per_token = max(0.8, min(3.0, _chars_per_token))
        char_budget = int(max_total_tokens * _chars_per_token)

        # 按优先级动态分配Token预算
        budget_weights = {}
        if schema and schema.strip():
            budget_weights['schema'] = 0.45
        if sql_examples and sql_examples.strip():
            budget_weights['sql'] = 0.30
        if terminologies and terminologies.strip():
            budget_weights['term'] = 0.25
        
        # 重新归一化权重（将空字段的份额按比例分配给非空字段）
        total_weight = sum(budget_weights.values()) or 1.0
        # 使用 config.max_schema_length 限制 schema 预算上限
        # 使用 char_budget（字符预算）而非 max_total_tokens（Token预算）分配子模块预算
        schema_budget = min(
            int(char_budget * budget_weights.get('schema', 0) / total_weight),
            _cfg.max_schema_length
        )
        sql_budget = int(char_budget * budget_weights.get('sql', 0) / total_weight)
        term_budget = int(char_budget * budget_weights.get('term', 0) / total_weight)

        # 压缩Schema
        compressed_schema = ContextCompressor._compress_schema(schema, schema_budget, question)

        # 压缩术语
        compressed_terms = ContextCompressor._compress_terminologies(terminologies, term_budget)

        # 压缩SQL示例
        compressed_sql = ContextCompressor._compress_sql_examples(sql_examples, sql_budget)

        # 压缩后验证关键Schema信息是否保留
        # 如果问题中提到的表名在压缩后的Schema中丢失，尝试恢复
        if schema and compressed_schema and question:
            compressed_schema = ContextCompressor._validate_schema_preservation(
                original_schema=schema,
                compressed_schema=compressed_schema,
                question=question,
                budget=schema_budget
            )

        compressed_length = len(compressed_terms) + len(compressed_sql) + len(compressed_schema)

        # 使用共享的溢出截断方法
        compressed_terms, compressed_sql, compressed_schema = \
            ContextCompressor._apply_overflow_truncation(
                compressed_terms, compressed_sql, compressed_schema,
                char_budget, caller="compress"
            )
        compressed_length = len(compressed_terms) + len(compressed_sql) + len(compressed_schema)

        result['terminologies'] = compressed_terms
        result['sql_examples'] = compressed_sql
        result['schema'] = compressed_schema
        result['compression_applied'] = True
        result['stats'] = {
            'original_length': original_length,
            'compressed_length': compressed_length,
            'compression_ratio': round(compressed_length / original_length, 2) if original_length > 0 else 1.0,
            'schema_compressed': len(compressed_schema) < len(schema),
            'terms_compressed': len(compressed_terms) < len(terminologies),
            'sql_compressed': len(compressed_sql) < len(sql_examples),
            'custom_prompt_compressed': len(compressed_custom_prompt) < len(custom_prompt) if custom_prompt else False,
        }

        ChatBILogUtil.info(
            f"Context compressed: {original_length} -> {compressed_length} chars "
            f"(ratio: {result['stats']['compression_ratio']})"
        )

        return result

    @staticmethod
    def _compress_schema(schema: str, budget: int, question: str = "") -> str:
        """
        压缩Schema信息
        策略：保留与查询最相关的表，截断过长的字段列表
        
         增强：使用商业级关键词匹配提升相关性判断准确度
        """
        if not schema or len(schema) <= budget:
            return schema

        # 按表分割Schema
        lines = schema.split('\n')
        tables = []
        current_table = []

        for line in lines:
            if line.strip().startswith('Table') or line.strip().startswith('表') or line.strip().startswith('# Table'):
                if current_table:
                    tables.append('\n'.join(current_table))
                current_table = [line]
            else:
                current_table.append(line)
        if current_table:
            tables.append('\n'.join(current_table))

        if not tables:
            return schema[:budget]

        # 提取问题中的关键词（去除停用词）
        question_keywords = set(re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]+', question.lower()))
        # 移除常见停用词
        stop_words = {'查询', '统计', '显示', '列出', '帮我', '请', '一下', '看看', '什么', '哪些', '多少'}
        question_keywords -= stop_words
        
        scored_tables = []
        for table in tables:
            table_lower = table.lower()
            # 关键词匹配得分（比字符重叠更准确）
            keyword_score = sum(1 for kw in question_keywords if kw in table_lower)
            # 表名/注释匹配额外加分
            first_line = table.split('\n')[0] if table else ''
            first_line_score = sum(2 for kw in question_keywords if kw in first_line.lower())
            # 外键关联表加分，保留表关系信息
            # 如果某个高分表引用了当前表（或当前表引用了高分表），应保留
            fk_score = 0
            fk_keywords = ['foreign', 'references', '外键', 'fk_', '_id']
            if any(fk in table_lower for fk in fk_keywords):
                fk_score = 1  # 有外键关系的表基础加分
            total_score = keyword_score + first_line_score + fk_score
            scored_tables.append((table, total_score))

        scored_tables.sort(key=lambda x: x[1], reverse=True)

        # 按预算拼接
        result_parts = []
        current_length = 0
        for table, _ in scored_tables:
            if current_length + len(table) + 1 <= budget:
                result_parts.append(table)
                current_length += len(table) + 1
            else:
                # 截断当前表的字段信息
                # 预留截断标记的长度，确保不超出预算
                truncation_marker = '\n  ...(fields omitted / 字段已省略)'
                remaining = budget - current_length - len(truncation_marker)
                if remaining > 50:
                    result_parts.append(table[:remaining] + truncation_marker)
                break

        return '\n'.join(result_parts)

    @staticmethod
    def _validate_schema_preservation(
        original_schema: str,
        compressed_schema: str,
        question: str,
        budget: int
    ) -> str:
        """
         验证压缩后的Schema是否保留了问题中引用的关键表信息。
        如果关键表在压缩中被丢弃，尝试将其摘要追加到压缩结果中。
        """
        # 提取问题中的关键词
        question_keywords = set(re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z_]+', question.lower()))
        stop_words = {'查询', '统计', '显示', '列出', '帮我', '请', '一下', '看看', '什么', '哪些', '多少', '所有'}
        question_keywords -= stop_words

        if not question_keywords:
            return compressed_schema

        # 按表分割原始Schema
        lines = original_schema.split('\n')
        tables = []
        current_table = []
        for line in lines:
            if line.strip().startswith('Table') or line.strip().startswith('表') or line.strip().startswith('# Table'):
                if current_table:
                    tables.append('\n'.join(current_table))
                current_table = [line]
            else:
                current_table.append(line)
        if current_table:
            tables.append('\n'.join(current_table))

        # 找出问题中引用但在压缩结果中丢失的表
        compressed_lower = compressed_schema.lower()
        missing_tables = []
        for table in tables:
            first_line = table.split('\n')[0].lower() if table else ''
            # 检查该表是否与问题相关
            is_relevant = any(kw in first_line for kw in question_keywords)
            if not is_relevant:
                continue
            # 检查该表是否在压缩结果中
            if first_line not in compressed_lower:
                # 只保留表头（表名+前几个字段），作为最小摘要
                table_lines = table.split('\n')
                summary = '\n'.join(table_lines[:min(4, len(table_lines))]) + '\n  ...(compressed / 已压缩)'
                missing_tables.append(summary)

        if not missing_tables:
            return compressed_schema

        # 追加丢失的关键表摘要（不超过预算的10%额外空间）
        extra_budget = int(budget * 0.1)
        extra = ''
        for mt in missing_tables:
            if len(extra) + len(mt) + 1 <= extra_budget:
                extra += '\n' + mt
        
        if extra:
            ChatBILogUtil.info(f"Schema preservation: recovered {len(missing_tables)} critical table(s)")
            return compressed_schema + extra

        return compressed_schema

    @staticmethod
    def _compress_terminologies(terminologies: str, budget: int) -> str:
        """
        压缩术语信息
        策略：按<terminology>标签分割，保留完整的术语条目，避免在XML标签中间截断
        """
        if not terminologies or len(terminologies) <= budget:
            return terminologies
        
        # 按<terminology>标签分割，保留完整条目
        terms = re.findall(r'<terminology>.*?</terminology>', terminologies, re.DOTALL)
        
        if not terms:
            # 没有标签结构，安全截断到最后一个完整行
            truncated = terminologies[:budget]
            last_newline = truncated.rfind('\n')
            if last_newline > 0:
                return truncated[:last_newline]
            return truncated
        
        # 保留前N个完整术语条目
        result_parts = []
        current_length = 0
        for term in terms:
            if current_length + len(term) + 1 <= budget:
                result_parts.append(term)
                current_length += len(term) + 1
            else:
                break
        
        if result_parts:
            return '\n'.join(result_parts)
        # 如果第一个术语超出预算，截断它而非完整保留
        if terms:
            first_term = terms[0]
            if len(first_term) <= budget:
                return first_term
            # 截断到预算内，但确保 XML 标签闭合
            # 直接截断会破坏 XML 结构，改为返回空（宁可不注入也不注入损坏的 XML）
            ChatBILogUtil.warning(
                f"First terminology ({len(first_term)} chars) exceeds budget ({budget}), skipping"
            )
            return ''
        return ''

    @staticmethod
    def _compress_sql_examples(sql_examples: str, budget: int) -> str:
        """
        压缩SQL示例（兼容文档知识块）
        策略：保留相似度最高的示例，截断过长的SQL
        对于<document-knowledge>块（PDF数据源），优先保留完整文档知识
        """
        if not sql_examples or len(sql_examples) <= budget:
            return sql_examples

        # 检测并优先保留<document-knowledge>块（PDF数据源的RAG检索结果）
        # document-knowledge块包含从文档知识库检索到的关键知识片段，不应被SQL示例压缩逻辑截断
        doc_knowledge_match = re.search(
            r'(<document-knowledge>.*?</document-knowledge>)', sql_examples, re.DOTALL
        )
        if doc_knowledge_match:
            doc_block = doc_knowledge_match.group(1)
            non_doc_part = sql_examples[:doc_knowledge_match.start()] + sql_examples[doc_knowledge_match.end():]
            non_doc_part = non_doc_part.strip()
            # 文档知识块优先保留，剩余预算分配给SQL示例
            if len(doc_block) <= budget:
                remaining_budget = budget - len(doc_block) - 2  # 2 for newlines
                if non_doc_part and remaining_budget > 50:
                    compressed_non_doc = ContextCompressor._compress_sql_examples(non_doc_part, remaining_budget)
                    return (compressed_non_doc + '\n\n' + doc_block).strip() if compressed_non_doc else doc_block
                return doc_block
            else:
                # 文档知识块本身超出预算，截断到预算内（保留前N个知识片段）
                return doc_block[:budget]

        # 按<example>标签分割
        examples = re.findall(r'<example>.*?</example>', sql_examples, re.DOTALL)

        if not examples:
            return sql_examples[:budget]

        # 预留 XML 包装标签的开销
        wrapper_overhead = len('<sql-examples>\n') + len('\n</sql-examples>')
        effective_budget = max(0, budget - wrapper_overhead)

        # 保留前N个示例（已按相似度排序）
        result_parts = []
        current_length = 0
        for example in examples:
            if current_length + len(example) + 1 <= effective_budget:
                result_parts.append(example)
                current_length += len(example) + 1
            else:
                break

        if result_parts:
            return '<sql-examples>\n' + '\n'.join(result_parts) + '\n</sql-examples>'
        return ''

    @staticmethod
    def compress_retrieval_results(
        terminology_results: List[Dict],
        sql_example_results: List[Dict],
        min_similarity: float = 0.35,
        max_terminologies: int = 5,
        max_sql_examples: int = 3,
        config: Optional[CompressorConfig] = None,
    ) -> Tuple[List[Dict], List[Dict], Dict]:
        """压缩检索结果列表（在重排序之后、组装Prompt之前调用）"""
        # config 参数优先于显式参数
        if config:
            min_similarity = config.min_similarity
            max_terminologies = config.max_terminologies
            max_sql_examples = config.max_sql_examples

        stats = {
            'original_terms': len(terminology_results),
            'original_examples': len(sql_example_results),
        }

        # 过滤低相关性结果
        filtered_terms = [
            t for t in terminology_results
            if t.get('similarity', 0) >= min_similarity or t.get('match_type') == 'keyword'
        ]

        filtered_examples = [
            e for e in sql_example_results
            if e.get('similarity', 0) >= min_similarity or e.get('match_type') == 'keyword'
        ]

        # 去除冗余（基于内容相似性）
        deduped_terms = ContextCompressor._deduplicate_terms(filtered_terms)
        deduped_examples = ContextCompressor._deduplicate_examples(filtered_examples)

        # 截断到最大数量
        compressed_terms = deduped_terms[:max_terminologies]
        compressed_examples = deduped_examples[:max_sql_examples]

        stats['compressed_terms'] = len(compressed_terms)
        stats['compressed_examples'] = len(compressed_examples)
        stats['terms_removed'] = stats['original_terms'] - stats['compressed_terms']
        stats['examples_removed'] = stats['original_examples'] - stats['compressed_examples']

        return compressed_terms, compressed_examples, stats

    @staticmethod
    def _deduplicate_terms(terms: List[Dict]) -> List[Dict]:
        """去除重复术语"""
        seen_words = set()
        result = []
        for term in terms:
            word = term.get('word', '') or term.get('term', '')
            if word not in seen_words:
                seen_words.add(word)
                result.append(term)
        return result

    @staticmethod
    def _deduplicate_examples(examples: List[Dict]) -> List[Dict]:
        """去除重复SQL示例"""
        seen_questions = set()
        result = []
        for example in examples:
            question = example.get('question', '')
            if question not in seen_questions:
                seen_questions.add(question)
                result.append(example)
        return result

    @staticmethod
    def compress_with_reranking(
        terminologies: str,
        sql_examples: str,
        schema: str,
        question: str,
        terminology_results: List[Dict] = None,
        sql_example_results: List[Dict] = None,
        max_total_tokens: int = 800,
        config: Optional[CompressorConfig] = None,
    ) -> Dict[str, str]:
        """结合重排序的上下文压缩（高级压缩策略）"""
        _cfg = config or CompressorConfig()
        original_length = len(terminologies) + len(sql_examples) + len(schema)
        estimated_tokens = ContextCompressor._estimate_tokens(terminologies + sql_examples + schema)
        
        # 使用 Token 估算值而非字符数判断是否需要压缩
        if estimated_tokens <= max_total_tokens:
            return {
                'terminologies': terminologies,
                'sql_examples': sql_examples,
                'schema': schema,
                'compression_applied': False,
                'stats': {
                    'original_length': original_length,
                    'compressed_length': original_length,
                    'estimated_tokens': estimated_tokens,
                    'compression_ratio': 1.0
                }
            }
        
        # 将 Token 预算转换为字符预算（与 compress() 方法一致）
        # 基于实际内容的中英比例动态计算转换系数
        _all_text = terminologies + sql_examples + schema
        _cn = len(re.findall(r'[\u4e00-\u9fff]', _all_text))
        _en = len(re.findall(r'[a-zA-Z0-9]', _all_text))
        _other = len(_all_text) - _cn - _en
        _total_chars = len(_all_text) or 1
        _chars_per_token = (
            (_cn / _total_chars) * (1 / 1.5) +
            (_en / _total_chars) * (1 / 0.25) +
            (_other / _total_chars) * (1 / 0.5)
        ) if _total_chars > 0 else 1.2
        _chars_per_token = max(0.8, min(3.0, _chars_per_token))
        char_budget = int(max_total_tokens * _chars_per_token)
        
        # 动态预算分配：根据检索质量调整
        has_doc_knowledge = bool(
            sql_examples and '<document-knowledge>' in sql_examples
        )
        
        if has_doc_knowledge:
            # PDF数据源：文档知识优先，schema通常为空
            # PDF提取表格后导入PG会有schema，给予15%预算（原5%太低）
            schema_ratio = 0.15 if schema and schema.strip() else 0.0
            sql_ratio = 0.60  # document-knowledge获得主要预算
            term_ratio = 0.25
        else:
            schema_ratio = 0.45
            sql_ratio = 0.30
            term_ratio = 0.25
        
        # 如果术语质量高，增加术语预算
        # 从 sql_ratio 而非 schema_ratio 借预算，避免 PDF 场景 schema 被清零
        if terminology_results:
            avg_score = sum(t.get('rerank_score', 0) for t in terminology_results) / len(terminology_results)
            if avg_score > 0.3:
                term_ratio += 0.05
                if has_doc_knowledge:
                    sql_ratio = max(0.50, sql_ratio - 0.05)  # PDF 场景从文档预算借，保底 50%
                else:
                    schema_ratio = max(0.10, schema_ratio - 0.05)  # 非 PDF 场景从 schema 借，保底 10%
        
        # 如果SQL示例质量高，增加示例预算（非PDF场景）
        if sql_example_results and not has_doc_knowledge:
            avg_score = sum(e.get('rerank_score', 0) for e in sql_example_results) / len(sql_example_results)
            if avg_score > 0.3:
                sql_ratio = 0.35
                schema_ratio = max(0.10, schema_ratio - 0.05)  # 保底 10%
        
        # 空字段预算重新分配（与compress()方法一致）
        budget_weights = {}
        if schema and schema.strip():
            budget_weights['schema'] = schema_ratio
        if sql_examples and sql_examples.strip():
            budget_weights['sql'] = sql_ratio
        if terminologies and terminologies.strip():
            budget_weights['term'] = term_ratio
        
        # 归一化
        total_ratio = sum(budget_weights.values()) or 1.0
        # 使用 char_budget（字符预算）分配子模块预算，与 compress() 方法一致
        schema_budget = min(
            int(char_budget * budget_weights.get('schema', 0) / total_ratio),
            _cfg.max_schema_length
        )
        sql_budget = int(char_budget * budget_weights.get('sql', 0) / total_ratio)
        term_budget = int(char_budget * budget_weights.get('term', 0) / total_ratio)
        
        compressed_schema = ContextCompressor._compress_schema(schema, schema_budget, question)
        compressed_terms = ContextCompressor._compress_terminologies(terminologies, term_budget)
        compressed_sql = ContextCompressor._compress_sql_examples(sql_examples, sql_budget)
        
        # 压缩后验证关键Schema信息是否保留
        if schema and compressed_schema and question:
            compressed_schema = ContextCompressor._validate_schema_preservation(
                original_schema=schema,
                compressed_schema=compressed_schema,
                question=question,
                budget=schema_budget
            )
        
        compressed_length = len(compressed_terms) + len(compressed_sql) + len(compressed_schema)
        
        # 使用共享的溢出截断方法
        compressed_terms, compressed_sql, compressed_schema = \
            ContextCompressor._apply_overflow_truncation(
                compressed_terms, compressed_sql, compressed_schema,
                char_budget, caller="compress_with_reranking"
            )
        compressed_length = len(compressed_terms) + len(compressed_sql) + len(compressed_schema)
        
        return {
            'terminologies': compressed_terms,
            'sql_examples': compressed_sql,
            'schema': compressed_schema,
            'compression_applied': True,
            'stats': {
                'original_length': original_length,
                'compressed_length': compressed_length,
                'compression_ratio': round(compressed_length / original_length, 2) if original_length > 0 else 1.0,
                'dynamic_budget': True,
                'budget_allocation': {
                    'schema': schema_budget,
                    'sql_examples': sql_budget,
                    'terminologies': term_budget,
                }
            }
        }
