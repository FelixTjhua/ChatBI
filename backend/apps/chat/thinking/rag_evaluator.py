"""RAG评估指标模块 (RAG Evaluation Metrics)"""
import time
import math
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime

from common.utils.utils import ChatBILogUtil


@dataclass
class RetrievalMetrics:
    """检索质量评估指标"""
    # Precision@K: 前K个检索结果中相关结果的比例
    precision_at_k: Dict[int, float] = field(default_factory=dict)
    # Recall@K: 前K个检索结果覆盖的相关文档比例
    recall_at_k: Dict[int, float] = field(default_factory=dict)
    # MRR (Mean Reciprocal Rank): 第一个相关结果的排名倒数
    mrr: float = 0.0
    # NDCG (Normalized Discounted Cumulative Gain): 归一化折损累积增益
    ndcg: float = 0.0
    # 平均相似度
    avg_similarity: float = 0.0
    # 高质量结果比例 (similarity >= threshold)
    high_quality_ratio: float = 0.0
    # 检索结果总数
    total_retrieved: int = 0
    # 相关结果数
    relevant_count: int = 0


@dataclass
class GenerationMetrics:
    """生成质量评估指标"""
    # SQL执行成功率
    sql_execution_success: bool = False
    # SQL语法正确性
    sql_syntax_valid: bool = False
    # 响应长度（字符数）
    response_length: int = 0
    # 生成耗时（秒）
    generation_time: float = 0.0
    # Token使用量
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    # Token效率（有效输出/总Token）
    token_efficiency: float = 0.0
    # 幻觉检测分数（0-1，越低越好）
    hallucination_score: float = 0.0
    # 是否使用了RAG上下文
    rag_context_used: bool = False
    # RAG上下文利用率（生成内容中引用RAG知识的比例）
    rag_utilization: float = 0.0
    # 上下文相关性（0-1，越高越好）
    contextual_relevance: float = 0.0
    # 回答具体性（0-1，越高越好）
    specificity: float = 0.0
    # 回答完整性（0-1，越高越好）
    completeness: float = 0.0
    # 信息缺失率（0-1，越低越好）
    missing_rate: float = 0.0
    # 对齐分数（0-1，越高越好）
    # 衡量生成内容与检索上下文的事实一致性
    align_score: float = 0.0


@dataclass
class EndToEndMetrics:
    """端到端评估指标"""
    # 任务完成状态
    task_completed: bool = False
    # 完成的步骤数
    steps_completed: int = 0
    # 总步骤数
    total_steps: int = 0
    # 端到端延迟（秒）
    total_latency: float = 0.0
    # 各阶段延迟分布
    stage_latencies: Dict[str, float] = field(default_factory=dict)
    # 重试次数
    retry_count: int = 0
    # 错误数
    error_count: int = 0


@dataclass
class EvaluationReport:
    """完整的评估报告"""
    # 评估时间
    timestamp: str = ""
    # 会话ID
    chat_id: int = 0
    record_id: int = 0
    # 用户问题
    question: str = ""
    # 各维度指标
    retrieval: Optional[RetrievalMetrics] = None
    generation: Optional[GenerationMetrics] = None
    end_to_end: Optional[EndToEndMetrics] = None
    # 综合评分（0-100）
    overall_score: float = 0.0
    # 评估等级
    grade: str = ""  # A/B/C/D/F
    # 改进建议
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # 映射字段名以匹配前端期望的 API 格式
        d['retrieval_metrics'] = d.pop('retrieval', None)
        d['generation_metrics'] = d.pop('generation', None)
        d['end_to_end_metrics'] = d.pop('end_to_end', None)
        return d


class RAGEvaluator:
    """RAG系统评估器"""

    # 相关性阈值
    RELEVANCE_THRESHOLD = 0.6
    HIGH_QUALITY_THRESHOLD = 0.75

    # ============ 检索质量评估 ============

    @staticmethod
    def evaluate_retrieval(
        retrieved_items: List[Dict],
        relevance_threshold: float = 0.6,
        k_values: List[int] = None
    ) -> RetrievalMetrics:
        """评估检索质量"""
        if k_values is None:
            k_values = [1, 3, 5]

        metrics = RetrievalMetrics()

        if not retrieved_items:
            return metrics

        # 提取并归一化相似度
        similarities = []
        for item in retrieved_items:
            sim = item.get('similarity', 0) or 0
            if sim > 1:
                sim = sim / 100.0
            similarities.append(sim)

        metrics.total_retrieved = len(similarities)
        metrics.avg_similarity = round(sum(similarities) / len(similarities), 4) if similarities else 0
        
        # 判定相关性
        relevance = [1 if s >= relevance_threshold else 0 for s in similarities]
        metrics.relevant_count = sum(relevance)
        metrics.high_quality_ratio = round(
            sum(1 for s in similarities if s >= RAGEvaluator.HIGH_QUALITY_THRESHOLD) / len(similarities), 4
        ) if similarities else 0

        # Precision@K
        for k in k_values:
            if k <= len(relevance):
                precision = sum(relevance[:k]) / k
                metrics.precision_at_k[k] = round(precision, 4)

        # Recall@K（以全部相关结果为分母）
        total_relevant = max(sum(relevance), 1)
        for k in k_values:
            if k <= len(relevance):
                recall = sum(relevance[:k]) / total_relevant
                metrics.recall_at_k[k] = round(recall, 4)

        # MRR (Mean Reciprocal Rank)
        for i, rel in enumerate(relevance):
            if rel == 1:
                metrics.mrr = round(1.0 / (i + 1), 4)
                break

        # NDCG（使用归一化后的相似度分数）
        metrics.ndcg = round(RAGEvaluator._calculate_ndcg(similarities, k=min(5, len(similarities))), 4)

        return metrics

    @staticmethod
    def _calculate_ndcg(scores: List[float], k: int) -> float:
        """计算NDCG@K"""
        if not scores or k <= 0:
            return 0.0

        # DCG
        dcg = 0.0
        for i in range(min(k, len(scores))):
            dcg += scores[i] / math.log2(i + 2)

        # Ideal DCG
        ideal_scores = sorted(scores, reverse=True)
        idcg = 0.0
        for i in range(min(k, len(ideal_scores))):
            idcg += ideal_scores[i] / math.log2(i + 2)

        return dcg / idcg if idcg > 0 else 0.0

    # ============ 生成质量评估 ============

    @staticmethod
    def evaluate_generation(
        generated_content: str,
        sql: str = "",
        sql_executed: bool = False,
        sql_error: str = "",
        token_usage: Dict = None,
        generation_time: float = 0.0,
        rag_context: Dict = None
    ) -> GenerationMetrics:
        """评估生成质量"""
        metrics = GenerationMetrics()
        metrics.response_length = len(generated_content) if generated_content else 0
        metrics.generation_time = round(generation_time, 3)

        # SQL评估
        if sql:
            metrics.sql_syntax_valid = RAGEvaluator._check_sql_syntax(sql)
            metrics.sql_execution_success = sql_executed and not sql_error

        # Token统计
        if token_usage:
            metrics.input_tokens = token_usage.get('input_tokens', 0) or 0
            metrics.output_tokens = token_usage.get('output_tokens', 0) or 0
            metrics.total_tokens = token_usage.get('total_tokens', 0) or 0
            if metrics.total_tokens > 0:
                metrics.token_efficiency = round(metrics.output_tokens / metrics.total_tokens, 4)

        # RAG上下文利用率评估
        if rag_context:
            metrics.rag_context_used = True
            metrics.rag_utilization = RAGEvaluator._estimate_rag_utilization(
                generated_content, sql, rag_context
            )

        # 幻觉检测（基于启发式规则）
        if sql and rag_context:
            metrics.hallucination_score = RAGEvaluator._detect_hallucination(sql, rag_context)

        # 上下文相关性评估
        if rag_context:
            metrics.contextual_relevance = RAGEvaluator._evaluate_contextual_relevance(
                generated_content, sql, rag_context
            )

        # 具体性评估
        metrics.specificity = RAGEvaluator._evaluate_specificity(generated_content, sql)

        # 完整性评估
        metrics.completeness = RAGEvaluator._evaluate_completeness(
            generated_content, sql, sql_executed, rag_context
        )

        # 信息缺失率
        metrics.missing_rate = round(1.0 - metrics.completeness, 4)

        # AlignScore
        if rag_context and (generated_content or sql):
            hallucination_penalty = 1.0 - metrics.hallucination_score
            context_alignment = metrics.contextual_relevance
            utilization_bonus = metrics.rag_utilization * 0.2
            metrics.align_score = round(
                min(1.0, hallucination_penalty * 0.5 + context_alignment * 0.3 + utilization_bonus + metrics.completeness * 0.1),
                4
            )

        return metrics

    @staticmethod
    def _check_sql_syntax(sql: str) -> bool:
        """基础SQL语法检查"""
        if not sql or not sql.strip():
            return False
        sql_upper = sql.strip().upper()
        # 必须以SELECT开头（查询场景）
        if not sql_upper.startswith('SELECT'):
            return False
        # 必须包含FROM
        if 'FROM' not in sql_upper:
            return False
        return True

    @staticmethod
    def _estimate_rag_utilization(content: str, sql: str, rag_context: Dict) -> float:
        """
        估算RAG上下文利用率
        检查生成内容中是否实际引用了RAG检索到的知识
        
         使用实际字符串匹配替代朴素的除2启发式，
        检查术语词汇和SQL示例模式是否真正出现在生成内容中。
        """
        if not content and not sql:
            return 0.0

        combined = (content or '') + ' ' + (sql or '')
        combined_lower = combined.lower()
        utilized_count = 0
        total_count = 0

        # 检查术语是否被实际使用（通过字符串匹配）
        terminologies = rag_context.get('terminologies', [])
        if terminologies and isinstance(terminologies, list):
            for term in terminologies:
                total_count += 1
                # 检查术语的word或description中的关键词是否出现在生成内容中
                term_word = str(term.get('word', '')).lower() if isinstance(term, dict) else str(term).lower()
                if not term_word:
                    continue
                # 使用双向子串匹配，解决"销售额"与"销售"互相包含的问题
                # 术语出现在内容中，或内容中的某个词包含术语
                if term_word in combined_lower or any(
                    term_word in token or token in term_word
                    for token in re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z_]+', combined_lower)
                    if len(token) >= 2
                ):
                    utilized_count += 1
        elif rag_context.get('terminologies_used', 0) > 0:
            # 兼容旧格式：只有计数没有详情时，检查内容长度作为启发式
            count = rag_context['terminologies_used']
            total_count += count
            # 如果生成了有效SQL或内容，认为至少利用了部分术语
            if len(combined) > 50:
                utilized_count += max(1, count // 2)

        # 检查SQL示例是否影响了生成（通过模式匹配）
        sql_examples = rag_context.get('sql_examples', [])
        if sql_examples and isinstance(sql_examples, list) and sql:
            sql_upper = sql.upper()
            for example in sql_examples:
                total_count += 1
                example_sql = str(example.get('sql', '')).upper() if isinstance(example, dict) else ''
                if example_sql:
                    # 检查示例SQL中的关键模式（表名、函数等）是否出现在生成的SQL中
                    # 提取示例中的表名
                    example_tables = set(re.findall(r'(?:FROM|JOIN)\s+"?(\w+)"?', example_sql))
                    generated_tables = set(re.findall(r'(?:FROM|JOIN)\s+"?(\w+)"?', sql_upper))
                    if example_tables & generated_tables:
                        utilized_count += 1
        elif rag_context.get('sql_examples_used', 0) > 0:
            count = rag_context['sql_examples_used']
            total_count += count
            if sql and len(sql) > 20:
                utilized_count += max(1, count // 2)

        return round(utilized_count / total_count, 4) if total_count > 0 else 0.0

    @staticmethod
    def _evaluate_contextual_relevance(content: str, sql: str, rag_context: Dict) -> float:
        """
        评估上下文相关性
        检查生成内容与RAG检索上下文的语义对齐程度
        
         增加实际内容匹配检查，不仅看"是否有术语/示例"，
        还检查生成内容是否真正引用了检索到的知识。
        """
        if not rag_context:
            return 0.0

        score = 0.0
        checks = 0
        combined = ((content or '') + ' ' + (sql or '')).lower()

        # 检查术语是否被实际引用
        terminologies = rag_context.get('terminologies', [])
        term_count = rag_context.get('terminologies_used', 0)
        if terminologies and isinstance(terminologies, list):
            checks += 1
            # 实际检查术语词汇是否出现在生成内容中
            matched = sum(1 for t in terminologies 
                         if isinstance(t, dict) and str(t.get('word', '')).lower() in combined)
            if matched > 0:
                score += min(0.9, 0.5 + matched * 0.1)
            elif content or sql:
                score += 0.3  # 有输出但未直接引用术语
        elif term_count > 0:
            checks += 1
            score += 0.7 if (content or sql) else 0.2

        # 检查SQL示例是否影响了生成
        example_count = rag_context.get('sql_examples_used', 0)
        if example_count > 0:
            checks += 1
            if sql:
                score += 0.9  # 有示例且生成了SQL，高度相关
            else:
                score += 0.3

        # 检查Schema信息
        if rag_context.get('schema'):
            checks += 1
            if sql:
                score += 0.9
            else:
                score += 0.4

        return round(score / max(checks, 1), 4)

    @staticmethod
    def _evaluate_specificity(content: str, sql: str) -> float:
        """
        评估回答的具体性
        具体的回答包含数字、表名、字段名等具体信息
        """
        if not content and not sql:
            return 0.0

        combined = (content or '') + ' ' + (sql or '')
        score = 0.0

        # 包含具体数字
        numbers = re.findall(r'\d+', combined)
        if numbers:
            score += 0.3

        # SQL包含具体的表名和字段
        if sql:
            sql_upper = sql.upper()
            if 'SELECT' in sql_upper and 'FROM' in sql_upper:
                score += 0.3
            if 'WHERE' in sql_upper:
                score += 0.2
            if any(func in sql_upper for func in ['SUM(', 'COUNT(', 'AVG(', 'MAX(', 'MIN(']):
                score += 0.1

        # 内容长度（过短的回答不够具体）
        if len(content or '') > 100:
            score += 0.1

        return round(min(score, 1.0), 4)

    @staticmethod
    def _evaluate_completeness(
        content: str, sql: str, sql_executed: bool, rag_context: Dict = None
    ) -> float:
        """
        评估回答的完整性
        完整的回答应该覆盖查询的所有方面
        """
        score = 0.0

        # SQL生成完整性
        if sql:
            score += 0.3
            if sql_executed:
                score += 0.3  # SQL能执行说明语法完整

        # 内容完整性
        if content:
            if len(content) > 50:
                score += 0.2
            if len(content) > 200:
                score += 0.1

        # RAG上下文利用完整性
        if rag_context:
            total_sources = (
                rag_context.get('terminologies_used', 0) +
                rag_context.get('sql_examples_used', 0)
            )
            if total_sources > 0 and (content or sql):
                score += 0.1

        return round(min(score, 1.0), 4)

    @staticmethod
    def _detect_hallucination(sql: str, rag_context: Dict) -> float:
        """幻觉检测（启发式方法）
            检查SQL中是否引用了不存在于Schema中的表或字段
            """
        if not sql:
            return 0.0

        schema = rag_context.get('schema', '')
        if not schema:
            return 0.5  # 无法判断

        sql_upper = sql.upper()
        schema_upper = schema.upper()

        hallucination_indicators = 0
        total_checks = 0

        
        # SQL关键字和聚合函数，不应被当作列名检查
        SQL_KEYWORDS = {
            'SELECT', 'FROM', 'WHERE', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER',
            'ON', 'AND', 'OR', 'NOT', 'NULL', 'TRUE', 'FALSE', 'IS', 'IN', 'LIKE',
            'BETWEEN', 'AS', 'ORDER', 'BY', 'GROUP', 'HAVING', 'LIMIT', 'OFFSET',
            'ASC', 'DESC', 'DISTINCT', 'COUNT', 'SUM', 'AVG', 'MAX', 'MIN',
            'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'CAST', 'COALESCE', 'IFNULL',
            'UPPER', 'LOWER', 'TRIM', 'CONCAT', 'SUBSTRING', 'EXTRACT', 'DATE',
            'YEAR', 'MONTH', 'DAY', 'HOUR', 'MINUTE', 'SECOND', 'FORMAT',
            'ROUND', 'FLOOR', 'CEIL', 'ABS', 'OVER', 'PARTITION', 'ROW_NUMBER',
            'RANK', 'DENSE_RANK', 'LAG', 'LEAD', 'UNION', 'ALL', 'EXISTS',
            'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 'TABLE',
            'INTO', 'VALUES', 'SET', 'WITH', 'RECURSIVE', 'CROSS', 'FULL',
            'NATURAL', 'USING', 'FETCH', 'NEXT', 'ROWS', 'ONLY', 'TOP',
            'PERCENT', 'TIES', 'ROLLUP', 'CUBE', 'GROUPING'
        }
        
        # 1. 检查FROM/JOIN后的表名是否在schema中
        table_refs = re.findall(r'(?:FROM|JOIN)\s+"?(\w+)"?', sql_upper)
        table_aliases = set()
        # 提取 "table alias" 和 "table AS alias" 格式的别名
        alias_patterns = re.findall(r'(?:FROM|JOIN)\s+"?(\w+)"?\s+(?:AS\s+)?(\w+)', sql_upper)
        for real_table, alias in alias_patterns:
            if alias not in SQL_KEYWORDS:
                table_aliases.add(alias)
        # 也提取子查询别名和CTE名称
        cte_names = set(re.findall(r'WITH\s+(\w+)\s+AS', sql_upper))
        table_aliases.update(cte_names)
        
        for table in table_refs:
            if table in SQL_KEYWORDS:
                continue
            total_checks += 1
            if table not in schema_upper:
                hallucination_indicators += 1

        # 2. 检查 table.column 格式的列引用
        qualified_cols = re.findall(r'"?(\w+)"?\."?(\w+)"?', sql_upper)
        for table, col in qualified_cols:
            if col in SQL_KEYWORDS or table in SQL_KEYWORDS:
                continue
            # 跳过表别名前缀（t1.col中的t1是别名，不需要检查）
            if table in table_aliases:
                # 只检查列名是否在schema中
                total_checks += 1
                if col not in schema_upper:
                    hallucination_indicators += 1
                continue
            total_checks += 1
            if col not in schema_upper:
                hallucination_indicators += 1

        # 3. 检查SQL各子句中的独立列名（非 table.col 格式）
        qualified_col_names = set(col for _, col in qualified_cols)
        table_ref_names = set(table_refs)
        
        # 提取各子句内容
        clauses_to_check = []
        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql_upper, re.DOTALL)
        if select_match:
            clauses_to_check.append(('SELECT', select_match.group(1)))
        
        # WHERE 子句
        where_match = re.search(r'WHERE\s+(.*?)(?:\s+GROUP\s+BY|\s+ORDER\s+BY|\s+LIMIT|\s+HAVING|\s*$)', sql_upper, re.DOTALL)
        if where_match:
            clauses_to_check.append(('WHERE', where_match.group(1)))
        
        # GROUP BY 子句
        group_match = re.search(r'GROUP\s+BY\s+(.*?)(?:\s+HAVING|\s+ORDER\s+BY|\s+LIMIT|\s*$)', sql_upper, re.DOTALL)
        if group_match:
            clauses_to_check.append(('GROUP BY', group_match.group(1)))
        
        # ORDER BY 子句
        order_match = re.search(r'ORDER\s+BY\s+(.*?)(?:\s+LIMIT|\s+OFFSET|\s*$)', sql_upper, re.DOTALL)
        if order_match:
            clauses_to_check.append(('ORDER BY', order_match.group(1)))
        
        # 收集SELECT子句中AS后面的别名（这些在其他子句中可以合法引用）
        select_aliases = set()
        if select_match:
            select_clause_for_alias = re.sub(r"'[^']*'", '', select_match.group(1))
            alias_tokens = re.findall(r'\b(\w+)\b', select_clause_for_alias)
            alias_next_flag = False
            for tok in alias_tokens:
                if tok == 'AS':
                    alias_next_flag = True
                    continue
                if alias_next_flag:
                    select_aliases.add(tok)
                    alias_next_flag = False
        
        for clause_name, clause_content in clauses_to_check:
            # 移除字符串常量，避免将常量值误判为幻觉列名
            clause_clean = re.sub(r"'[^']*'", '', clause_content)
            tokens = re.findall(r'\b(\w+)\b', clause_clean)
            alias_next = False
            for token in tokens:
                if token == 'AS':
                    alias_next = True
                    continue
                if alias_next:
                    alias_next = False
                    continue
                if token in SQL_KEYWORDS:
                    continue
                if token.isdigit():
                    continue
                # 跳过已在 qualified_cols 中检查过的
                if token in qualified_col_names:
                    continue
                # 检查是否是表名（表名不需要在这里检查）
                if token in table_ref_names:
                    continue
                # 跳过表别名
                if token in table_aliases:
                    continue
                # 跳过SELECT子句中定义的列别名（在WHERE/GROUP BY/ORDER BY中合法引用）
                if clause_name != 'SELECT' and token in select_aliases:
                    continue
                total_checks += 1
                if token not in schema_upper:
                    hallucination_indicators += 1

        if total_checks == 0:
            return 0.0

        return round(hallucination_indicators / total_checks, 4)

    # ============ 端到端评估 ============

    @staticmethod
    def evaluate_end_to_end(
        stages: Dict[str, Dict],
        task_completed: bool = False,
        total_steps: int = 3,
        retry_count: int = 0,
        error_count: int = 0
    ) -> EndToEndMetrics:
        """端到端评估"""
        metrics = EndToEndMetrics()
        metrics.task_completed = task_completed
        metrics.total_steps = total_steps
        metrics.retry_count = retry_count
        metrics.error_count = error_count

        completed = 0
        total_latency = 0.0

        for stage_name, stage_data in stages.items():
            duration_ms = stage_data.get('duration', 0)
            duration_s = duration_ms / 1000.0
            metrics.stage_latencies[stage_name] = round(duration_s, 3)
            total_latency += duration_s

            if stage_data.get('status') == 'completed':
                completed += 1

        metrics.steps_completed = completed
        metrics.total_latency = round(total_latency, 3)

        return metrics

    # ============ 综合评估 ============

    @staticmethod
    def generate_report(
        question: str,
        chat_id: int = 0,
        record_id: int = 0,
        retrieval_metrics: RetrievalMetrics = None,
        generation_metrics: GenerationMetrics = None,
        end_to_end_metrics: EndToEndMetrics = None
    ) -> EvaluationReport:
        """
        生成综合评估报告
        
        综合检索、生成、端到端三个维度的指标，
        计算综合评分并给出改进建议。
        """
        report = EvaluationReport(
            timestamp=datetime.now().isoformat(),
            chat_id=chat_id,
            record_id=record_id,
            question=question,
            retrieval=retrieval_metrics,
            generation=generation_metrics,
            end_to_end=end_to_end_metrics
        )

        # 计算综合评分（满分100）
        score = 0.0
        weight_sum = 0.0

        # 检索质量（权重40%）
        if retrieval_metrics:
            retrieval_score = 0.0
            if retrieval_metrics.mrr > 0:
                retrieval_score += retrieval_metrics.mrr * 30
            if retrieval_metrics.precision_at_k.get(3, 0) > 0:
                retrieval_score += retrieval_metrics.precision_at_k[3] * 40
            if retrieval_metrics.ndcg > 0:
                retrieval_score += retrieval_metrics.ndcg * 30
            score += retrieval_score * 0.4
            weight_sum += 0.4

        # 生成质量（权重35%）
        if generation_metrics:
            gen_score = 0.0
            if generation_metrics.sql_execution_success:
                gen_score += 40
            if generation_metrics.sql_syntax_valid:
                gen_score += 15
            gen_score += (1 - generation_metrics.hallucination_score) * 15
            gen_score += generation_metrics.token_efficiency * 10
            gen_score += generation_metrics.contextual_relevance * 10
            gen_score += generation_metrics.specificity * 5
            gen_score += generation_metrics.completeness * 5
            gen_score += generation_metrics.align_score * 5
            score += gen_score * 0.35
            weight_sum += 0.35

        # 端到端性能（权重25%）
        if end_to_end_metrics:
            e2e_score = 0.0
            if end_to_end_metrics.task_completed:
                e2e_score += 50
            completion_ratio = min(1.0, end_to_end_metrics.steps_completed / 
                              max(end_to_end_metrics.total_steps, 1))
            e2e_score += completion_ratio * 30
            # 延迟惩罚（超过10秒开始扣分）
            if end_to_end_metrics.total_latency < 5:
                e2e_score += 20
            elif end_to_end_metrics.total_latency < 10:
                e2e_score += 10
            # 错误惩罚
            e2e_score -= end_to_end_metrics.error_count * 10
            e2e_score = max(0, e2e_score)
            score += e2e_score * 0.25
            weight_sum += 0.25

        # 归一化
        if weight_sum > 0:
            report.overall_score = round(min(100.0, max(0.0, score / weight_sum)), 1)
        
        # 评级
        if report.overall_score >= 90:
            report.grade = 'A'
        elif report.overall_score >= 75:
            report.grade = 'B'
        elif report.overall_score >= 60:
            report.grade = 'C'
        elif report.overall_score >= 40:
            report.grade = 'D'
        else:
            report.grade = 'F'

        # 改进建议
        report.recommendations = RAGEvaluator._generate_recommendations(
            retrieval_metrics, generation_metrics, end_to_end_metrics
        )

        return report

    @staticmethod
    def _generate_recommendations(
        retrieval: RetrievalMetrics = None,
        generation: GenerationMetrics = None,
        end_to_end: EndToEndMetrics = None
    ) -> List[str]:
        """生成改进建议"""
        recommendations = []

        if retrieval:
            if retrieval.avg_similarity < 0.5:
                recommendations.append("检索相似度偏低，建议补充知识库内容或优化向量模型")
            if retrieval.mrr < 0.5:
                recommendations.append("首个相关结果排名靠后，建议优化重排序策略")
            if retrieval.high_quality_ratio < 0.3:
                recommendations.append("高质量检索结果比例低，建议扩充术语库和SQL示例")
            p3 = retrieval.precision_at_k.get(3, 0)
            if 0 < p3 < 0.5:
                recommendations.append("Precision@3偏低，建议优化检索过滤阈值")

        if generation:
            if not generation.sql_execution_success:
                recommendations.append("SQL执行失败，建议检查Schema映射和SQL生成提示词")
            if generation.hallucination_score > 0.3:
                recommendations.append("检测到潜在幻觉，建议增强Schema约束和RAG上下文")
            if generation.token_efficiency < 0.2:
                recommendations.append("Token效率偏低，建议优化上下文压缩策略")
            if not generation.rag_context_used:
                recommendations.append("未使用RAG上下文，建议检查知识库配置")
            if generation.contextual_relevance < 0.5:
                recommendations.append("上下文相关性偏低，建议优化检索策略以提升语义匹配")
            if generation.specificity < 0.4:
                recommendations.append("回答具体性不足，建议增加Schema约束和示例引导")
            if generation.missing_rate > 0.5:
                recommendations.append("信息缺失率较高，建议补充知识库或优化Prompt模板")

        if end_to_end:
            if end_to_end.total_latency > 15:
                recommendations.append("端到端延迟过高，建议优化检索和生成流程")
            if end_to_end.error_count > 0:
                recommendations.append(f"存在{end_to_end.error_count}个错误，建议检查错误日志")
            if not end_to_end.task_completed:
                recommendations.append("任务未完成，建议检查流程中断原因")

        if not recommendations:
            recommendations.append("系统运行良好，各项指标正常")

        return recommendations

    # ============  评估反馈机制 ============

    @staticmethod
    def generate_feedback_adjustments(report: 'EvaluationReport') -> Dict[str, Any]:
        """根据评估报告生成反馈调整参数"""
        adjustments: Dict[str, Any] = {
            'similarity_threshold': 0.35,  # 默认值
            'max_terminologies': 5,
            'max_sql_examples': 3,
            'rerank_weight_boost': 1.0,
            'compression_budget_ratio': 1.0,
            'feedback_applied': False,
            'feedback_reasons': []
        }

        if not report:
            return adjustments

        retrieval = report.retrieval
        generation = report.generation

        # 检索质量反馈 — 使用互斥优先级避免 similarity_threshold 冲突覆盖
        low_precision = False
        low_recall = False
        if retrieval:
            low_precision = retrieval.precision_at_k.get(3, 1.0) < 0.3
            low_recall = retrieval.recall_at_k.get(5, 1.0) < 0.3

            if low_precision and low_recall:
                # 精度和召回同时低 → 折中阈值，侧重增加检索量 + 重排序兜底
                adjustments['similarity_threshold'] = 0.35
                adjustments['max_terminologies'] = 8
                adjustments['max_sql_examples'] = 5
                adjustments['rerank_weight_boost'] = 1.3
                adjustments['feedback_reasons'].append(
                    '检索精度与召回同时低，保持折中阈值并增加检索量+重排序兜底')
                adjustments['feedback_applied'] = True
            elif low_precision:
                # 仅精度低 → 提高相似度阈值，减少噪声
                adjustments['similarity_threshold'] = 0.45
                adjustments['feedback_reasons'].append('检索精度低，提高相似度阈值过滤噪声')
                adjustments['feedback_applied'] = True
            elif low_recall:
                # 仅召回低 → 降低阈值，增加检索数量
                adjustments['similarity_threshold'] = 0.25
                adjustments['max_terminologies'] = 8
                adjustments['max_sql_examples'] = 5
                adjustments['feedback_reasons'].append('检索召回低，降低阈值并增加检索数量')
                adjustments['feedback_applied'] = True

            # 高质量结果比例低 → 增强重排序权重（与上面不冲突，独立调整）
            if retrieval.high_quality_ratio < 0.2:
                adjustments['rerank_weight_boost'] = 1.3
                adjustments['feedback_reasons'].append('高质量结果少，增强重排序权重')
                adjustments['feedback_applied'] = True

        # 生成质量反馈
        if generation:
            # 幻觉分数高 → 增加Schema预算，减少术语干扰
            if generation.hallucination_score > 0.3:
                adjustments['compression_budget_ratio'] = 1.2  # 增加总预算
                adjustments['max_terminologies'] = 3  # 减少术语避免干扰
                adjustments['feedback_reasons'].append('幻觉风险高，增加Schema预算减少术语干扰')
                adjustments['feedback_applied'] = True

            # RAG利用率低 → 仅在检索阈值未被检索质量反馈调整时才降低阈值
            if generation.rag_context_used and generation.rag_utilization < 0.2:
                if not low_precision and not low_recall:
                    adjustments['similarity_threshold'] = 0.30
                adjustments['feedback_reasons'].append('RAG利用率低，降低检索阈值提升相关性')
                adjustments['feedback_applied'] = True

        if adjustments['feedback_applied']:
            ChatBILogUtil.info(
                f"RAG feedback adjustments: {adjustments['feedback_reasons']}"
            )

        return adjustments
