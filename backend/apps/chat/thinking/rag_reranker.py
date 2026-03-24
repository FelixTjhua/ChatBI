"""RAG检索结果智能重排序（Reranking）"""
from typing import List, Dict, Any
from datetime import datetime
import threading

from common.utils.utils import ChatBILogUtil


# CrossEncoder 模块级单例缓存
# 避免每次调用 _cross_encoder_rerank 都重新加载模型（约 2-5 秒）
_cross_encoder_model = None
_cross_encoder_lock = threading.Lock()


def _get_cross_encoder_model():
    """线程安全的 CrossEncoder 单例获取"""
    global _cross_encoder_model
    if _cross_encoder_model is None:
        with _cross_encoder_lock:
            if _cross_encoder_model is None:
                from sentence_transformers import CrossEncoder
                _cross_encoder_model = CrossEncoder('BAAI/bge-reranker-base', max_length=256)
                ChatBILogUtil.info("[Reranker] CrossEncoder model loaded (singleton)")
    return _cross_encoder_model


class RAGReranker:
    """RAG检索结果重排序器"""
    
    # 混合检索融合系数α（S_hybrid = α·S_sparse + (1-α)·S_dense）
    HYBRID_ALPHA = 0.4  # 稀疏检索权重，可根据领域调整
    
    @staticmethod
    def rerank_terminologies(
        terminologies: List[Dict],
        question: str,
        datasource_id: int = None,
        top_k: int = 5
    ) -> List[Dict]:
        """术语表结果重排序"""
        if not terminologies:
            return []
        
        alpha = RAGReranker.HYBRID_ALPHA
        scored_terms = []
        for term in terminologies:
            score = 0.0
            
            # 1. 混合检索融合分数（S_hybrid = α·S_sparse + (1-α)·S_dense）
            similarity = term.get('similarity', 0)
            if similarity > 1:  # 百分比格式
                similarity = similarity / 100.0
            
            match_type = term.get('match_type', 'vector')
            if match_type == 'keyword':
                # 稀疏检索结果：关键词精确匹配 → S_sparse = 1.0（完美匹配）
                hybrid_score = alpha * 1.0 + (1 - alpha) * similarity
            elif match_type == 'vector':
                # 稠密检索结果：S_sparse = 0（无关键词分数）, S_dense = similarity
                hybrid_score = (1 - alpha) * similarity
            else:
                # 混合匹配或未知类型
                hybrid_score = similarity
            
            score += hybrid_score * 0.6
            
            # 2. 特定数据源加权（针对性更强）
            if datasource_id and term.get('is_specific', False):
                score += 0.25
            
            # 3. 描述完整性（信息量）
            description = term.get('description', '')
            if len(description) > 50:
                score += 0.05
            elif len(description) > 20:
                score += 0.025
            
            # 4. 问题相关性加权（术语名称与问题的字符重叠度）
            word = term.get('word', '')
            if word and question and word in question:
                score += 0.1  # 术语名称直接出现在问题中
            
            scored_terms.append({
                **term,
                'rerank_score': round(score, 4),
                'hybrid_score': round(hybrid_score, 4)
            })
        
        # 按重排序分数排序
        scored_terms.sort(key=lambda x: x['rerank_score'], reverse=True)
        
        # 术语多样性保证，避免检索到的术语全是同一个业务域
        diverse_terms = RAGReranker._ensure_terminology_diversity(scored_terms, top_k)
        
        return diverse_terms
    
    @staticmethod
    def rerank_sql_examples(
        examples: List[Dict],
        question: str,
        datasource_id: int = None,
        datasource_type: str = None,
        top_k: int = 3
    ) -> List[Dict]:
        """SQL示例结果重排序"""
        if not examples:
            return []
        
        # 分析问题复杂度
        question_complexity = RAGReranker._analyze_question_complexity(question)
        
        scored_examples = []
        for example in examples:
            score = 0.0
            
            # 1. 相似度分数
            # 权重从 0.4 提高到 0.5，语义相关性应是最重要的信号
            similarity = example.get('similarity', 0)
            if similarity > 1:
                similarity = similarity / 100.0
            score += similarity * 0.5
            
            # 2. 特定数据源优先（更精准）
            if datasource_id and example.get('is_specific', False):
                score += 0.3
            
            # 3. SQL复杂度匹配
            sql = example.get('sql', '')
            sql_complexity = RAGReranker._analyze_sql_complexity(sql)
            complexity_match = 1.0 - abs(question_complexity - sql_complexity)
            score += complexity_match * 0.1
            
            # 4. 匹配类型加权
            if example.get('match_type') == 'keyword':
                score += 0.1
            elif example.get('match_type') == 'token_fuzzy':
                score += 0.07  # 分词模糊匹配：介于精确匹配和向量匹配之间
            
            scored_examples.append({
                **example,
                'rerank_score': round(score, 4)
            })
        
        # 按重排序分数排序
        scored_examples.sort(key=lambda x: x['rerank_score'], reverse=True)
        
        # 多样性处理：确保不同类型的SQL都有代表
        diverse_examples = RAGReranker._ensure_diversity(scored_examples, top_k)
        
        return diverse_examples
    
    @staticmethod
    def _analyze_question_complexity(question: str) -> float:
        """分析问题复杂度（0-1）"""
        complexity = 0.0
        question_lower = question.lower()
        
        # 聚合函数
        agg_keywords = ['sum', 'count', 'avg', 'max', 'min', '总', '平均', '最大', '最小', '统计']
        if any(kw in question_lower for kw in agg_keywords):
            complexity += 0.3
        
        # 分组
        group_keywords = ['group', 'by', '按', '分组', '每个', '各']
        if any(kw in question_lower for kw in group_keywords):
            complexity += 0.2
        
        # 排序
        sort_keywords = ['top', 'limit', 'order', '前', '后', '排序', '最']
        if any(kw in question_lower for kw in sort_keywords):
            complexity += 0.2
        
        # 时间范围
        time_keywords = ['年', '月', '日', '时间', 'date', 'time', 'year', 'month']
        if any(kw in question_lower for kw in time_keywords):
            complexity += 0.15
        
        # 多表关联
        join_keywords = ['join', '关联', '连接']
        if any(kw in question_lower for kw in join_keywords):
            complexity += 0.15
        
        return min(complexity, 1.0)
    
    @staticmethod
    def _analyze_sql_complexity(sql: str) -> float:
        """
        分析SQL复杂度（0-1）
        """
        if not sql:
            return 0.0
        
        complexity = 0.0
        sql_upper = sql.upper()
        
        # 聚合函数
        if any(func in sql_upper for func in ['SUM(', 'COUNT(', 'AVG(', 'MAX(', 'MIN(']):
            complexity += 0.3
        
        # GROUP BY
        if 'GROUP BY' in sql_upper:
            complexity += 0.2
        
        # ORDER BY
        if 'ORDER BY' in sql_upper:
            complexity += 0.2
        
        # JOIN
        if 'JOIN' in sql_upper:
            complexity += 0.15
        
        # 子查询
        if sql_upper.count('SELECT') > 1:
            complexity += 0.15
        
        return min(complexity, 1.0)
    
    @staticmethod
    def _ensure_diversity(examples: List[Dict], top_k: int) -> List[Dict]:
        """
        确保结果多样性
        避免所有示例都是同一类型
        """
        if len(examples) <= top_k:
            return examples
        
        # 按SQL类型分类
        type_groups = {
            'simple_select': [],
            'aggregation': [],
            'join': [],
            'complex': []
        }
        
        for example in examples:
            sql = example.get('sql', '').upper()
            if 'JOIN' in sql:
                type_groups['join'].append(example)
            elif any(func in sql for func in ['SUM(', 'COUNT(', 'AVG(', 'GROUP BY']):
                type_groups['aggregation'].append(example)
            elif sql.count('SELECT') > 1 or 'UNION' in sql:
                type_groups['complex'].append(example)
            else:
                type_groups['simple_select'].append(example)
        
        # 从每个类型中选择最佳示例
        diverse_results = []
        remaining_slots = top_k
        
        # 优先选择每个类型的最佳示例
        for type_name, group in type_groups.items():
            if group and remaining_slots > 0:
                diverse_results.append(group[0])
                remaining_slots -= 1
        
        # 如果还有空位，按分数填充
        # 使用id()比较避免字典对象的不可靠相等性判断
        if remaining_slots > 0:
            selected_ids = {id(ex) for ex in diverse_results}
            all_remaining = [ex for ex in examples if id(ex) not in selected_ids]
            diverse_results.extend(all_remaining[:remaining_slots])
        
        # 多样性选择后重新按rerank_score降序排列，确保保序性
        diverse_results.sort(key=lambda x: x.get('rerank_score', 0), reverse=True)
        
        return diverse_results[:top_k]
    
    @staticmethod
    def _ensure_terminology_diversity(terms: List[Dict], top_k: int) -> List[Dict]:
        """
        确保术语结果多样性
        避免所有术语都来自同一个业务域（如全是财务指标或全是销售指标）
        
        策略：按术语描述中的业务域关键词分组，每组优先选最高分的，
        然后按分数填充剩余名额。
        """
        if len(terms) <= top_k:
            return terms
        
        # 业务域关键词分组
        domain_keywords = {
            'finance': ['利润', '成本', '费用', '资产', '负债', '现金', '收入', '支出', 'profit', 'cost', 'revenue'],
            'sales': ['销售', '订单', '客户', '商品', '产品', '交易', 'sales', 'order', 'customer'],
            'operations': ['库存', '物流', '生产', '供应', '采购', 'inventory', 'supply'],
            'analytics': ['增长', '趋势', '占比', '环比', '同比', '分布', 'growth', 'trend'],
        }
        
        domain_groups: Dict[str, List[Dict]] = {'other': []}
        for kw_domain in domain_keywords:
            domain_groups[kw_domain] = []
        
        for term in terms:
            desc = (term.get('description', '') + ' ' + term.get('word', '')).lower()
            assigned = False
            for domain, keywords in domain_keywords.items():
                if any(kw in desc for kw in keywords):
                    domain_groups[domain].append(term)
                    assigned = True
                    break
            if not assigned:
                domain_groups['other'].append(term)
        
        # 从每个非空域中选最高分的
        diverse_results = []
        remaining_slots = top_k
        for domain, group in domain_groups.items():
            if group and remaining_slots > 0:
                diverse_results.append(group[0])
                remaining_slots -= 1
        
        # 按分数填充剩余名额
        if remaining_slots > 0:
            selected_ids = {id(t) for t in diverse_results}
            all_remaining = [t for t in terms if id(t) not in selected_ids]
            diverse_results.extend(all_remaining[:remaining_slots])
        
        # 重新按 rerank_score 降序排列
        diverse_results.sort(key=lambda x: x.get('rerank_score', 0), reverse=True)
        
        return diverse_results[:top_k]
    
    @staticmethod
    def rerank_combined_results(
        terminologies: List[Dict],
        sql_examples: List[Dict],
        custom_prompts: List[Dict],
        question: str,
        datasource_id: int = None
    ) -> Dict[str, List[Dict]]:
        """综合重排序所有RAG检索结果"""
        # 阶段1：规则粗排
        reranked_terms = RAGReranker.rerank_terminologies(
            terminologies, question, datasource_id, top_k=5
        )
        reranked_examples = RAGReranker.rerank_sql_examples(
            sql_examples, question, datasource_id, top_k=3
        )
        
        # 阶段2：Cross-Encoder精排（可选）
        reranked_terms = RAGReranker._cross_encoder_rerank(
            reranked_terms, question, content_key='description'
        )
        reranked_examples = RAGReranker._cross_encoder_rerank(
            reranked_examples, question, content_key='question'
        )
        
        return {
            'terminologies': reranked_terms,
            'sql_examples': reranked_examples,
            'custom_prompts': custom_prompts,
        }

    @staticmethod
    def _cross_encoder_rerank(
        items: List[Dict],
        question: str,
        content_key: str = 'description',
        top_k: int = None,
    ) -> List[Dict]:
        """Cross-Encoder精排"""
        if not items or len(items) <= 1:
            return items
        
        try:
            from sentence_transformers import CrossEncoder
            
            # 使用模块级单例缓存，避免每次调用都重新加载模型
            model = _get_cross_encoder_model()
            
            # 构建 (question, candidate) 对
            pairs = []
            for item in items:
                text = item.get(content_key, '') or item.get('word', '') or ''
                pairs.append((question, text))
            
            # 批量预测相关性分数
            scores = model.predict(pairs)
            
            # Cross-Encoder输出为logits（可能为负数），需sigmoid归一化到[0,1]
            import math
            normalized_scores = []
            for s in scores:
                s_float = float(s)
                # sigmoid归一化
                normalized_scores.append(1.0 / (1.0 + math.exp(-s_float)))
            
            # 融合Cross-Encoder分数与粗排分数
            for i, item in enumerate(items):
                ce_score = normalized_scores[i]
                rule_score = item.get('rerank_score', 0)
                # 加权融合：Cross-Encoder 60% + 规则粗排 40%
                item['cross_encoder_score'] = round(ce_score, 4)
                # round到3位小数消除MPS浮点非确定性
                # CrossEncoder在MPS设备上对相同输入可能产生±1e-5级别的分数差异，
                item['rerank_score'] = round(0.6 * ce_score + 0.4 * rule_score, 3)
            
            items.sort(key=lambda x: x['rerank_score'], reverse=True)
            
            if top_k:
                items = items[:top_k]
                
        except ImportError:
            # sentence-transformers未安装，静默降级
            ChatBILogUtil.warning("[Reranker] sentence-transformers not installed, skipping cross-encoder rerank")
        except Exception as e:
            # 模型加载或推理失败，静默降级为粗排结果
            ChatBILogUtil.warning(f"[Reranker] Cross-encoder rerank failed, falling back to rule-based: {e}")
        
        return items


class RAGQualityEnhancer:
    """RAG质量增强器 - 提升检索结果的可用性"""
    
    @staticmethod
    def enhance_terminology(term: Dict, lang: str = "") -> Dict:
        """
        增强术语信息
        添加上下文提示（中英文双语）
        """
        enhanced = term.copy()
        is_en = lang.lower().startswith('en') if lang else False
        
        # 添加使用建议（双语）
        if term.get('similarity', 0) > 0.9:
            enhanced['usage_hint'] = 'Highly relevant, recommended for direct use' if is_en else '高度相关，建议直接使用'
        elif term.get('similarity', 0) > 0.7:
            enhanced['usage_hint'] = 'Fairly relevant, can be used as reference' if is_en else '相关性较高，可参考使用'
        else:
            enhanced['usage_hint'] = 'Moderately relevant, use with caution' if is_en else '相关性一般，谨慎使用'
        
        return enhanced
    
    @staticmethod
    def enhance_sql_example(example: Dict, lang: str = "") -> Dict:
        """
        增强SQL示例
        添加适用场景说明（中英文双语）
        """
        enhanced = example.copy()
        is_en = lang.lower().startswith('en') if lang else False
        
        sql = example.get('sql', '').upper()
        
        # 分析SQL特征（双语）
        features = []
        if 'GROUP BY' in sql:
            features.append('Group Aggregation' if is_en else '分组聚合')
        if 'JOIN' in sql:
            features.append('Multi-table Join' if is_en else '多表关联')
        if 'ORDER BY' in sql:
            features.append('Sorting' if is_en else '排序')
        if 'LIMIT' in sql or 'TOP' in sql:
            features.append('Result Limiting' if is_en else '限制结果数')
        
        enhanced['sql_features'] = features
        
        # 添加适用场景（双语）
        if features:
            if is_en:
                enhanced['applicable_scenarios'] = f"Applicable for {', '.join(features)} scenarios"
            else:
                enhanced['applicable_scenarios'] = f"适用于{', '.join(features)}场景"
        
        return enhanced
