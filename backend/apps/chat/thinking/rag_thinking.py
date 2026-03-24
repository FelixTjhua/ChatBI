"""
RAG增强的思考过程系统
记录RAG检索→LLM生成→执行验证的全链路
"""
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict



class RAGQualityMetrics:
    """RAG质量指标计算器"""

    # 各知识维度的饱和阈值（达到此数量时覆盖率趋近1.0）
    # 基于经验：术语通常需要更多条目才能充分覆盖，SQL示例则少量高质量即可
    SATURATION_THRESHOLDS = {
        'table_matches': 5,        # 表检索：选对表是SQL生成的前提
        'terminologies': 8,
        'sql_examples': 5,
        'analysis_examples': 4,
        'predict_examples': 4,
        'doc_chunks': 5,           # 文档片段：PDF/Excel/CSV的核心知识源
    }

    # 各知识维度的默认权重（反映对最终生成质量的贡献度）
    # 注意：实际使用时应通过 get_dimension_weights(scenario) 获取场景化权重
    DIMENSION_WEIGHTS = {
        'table_matches': 0.25,     # 表检索对SQL准确性至关重要
        'terminologies': 0.25,     # 术语对理解业务语义关键
        'sql_examples': 0.25,      # SQL示例对生成准确SQL关键
        'analysis_examples': 0.05, # 分析示例辅助
        'predict_examples': 0.05,  # 预测示例辅助
        'doc_chunks': 0.15,        # 文档片段对文档类数据源关键
    }

    # 场景化权重矩阵：不同数据源类型 × 不同意图下，各知识维度的贡献度不同
    # 每个场景的权重之和 = 1.0，确保归一化正确
    SCENARIO_WEIGHTS = {
        # Database: 表检索+SQL生成是核心，术语帮助理解业务
        'database_sql': {
            'table_matches': 0.25, 'terminologies': 0.25, 'sql_examples': 0.40,
            'analysis_examples': 0.05, 'predict_examples': 0.05, 'doc_chunks': 0.00,
        },
        'database_analysis': {
            'table_matches': 0.15, 'terminologies': 0.40, 'sql_examples': 0.10,
            'analysis_examples': 0.25, 'predict_examples': 0.10, 'doc_chunks': 0.00,
        },
        'database_prediction': {
            'table_matches': 0.15, 'terminologies': 0.35, 'sql_examples': 0.10,
            'analysis_examples': 0.05, 'predict_examples': 0.35, 'doc_chunks': 0.00,
        },
        # PDF: 文档片段是核心知识源，无表检索
        'pdf_document_qa': {
            'table_matches': 0.00, 'terminologies': 0.25, 'sql_examples': 0.00,
            'analysis_examples': 0.00, 'predict_examples': 0.00, 'doc_chunks': 0.75,
        },
        # 以下 pdf_sql/pdf_analysis/pdf_prediction 为防御性兜底配置
        'pdf_sql': {
            'table_matches': 0.00, 'terminologies': 0.25, 'sql_examples': 0.00,
            'analysis_examples': 0.00, 'predict_examples': 0.00, 'doc_chunks': 0.75,
        },
        'pdf_analysis': {
            'table_matches': 0.00, 'terminologies': 0.25, 'sql_examples': 0.00,
            'analysis_examples': 0.00, 'predict_examples': 0.00, 'doc_chunks': 0.75,
        },
        'pdf_prediction': {
            'table_matches': 0.00, 'terminologies': 0.25, 'sql_examples': 0.00,
            'analysis_examples': 0.00, 'predict_examples': 0.00, 'doc_chunks': 0.75,
        },
        # Excel/CSV: 表检索重要（多sheet场景），SQL路径与Database类似
        'excel_sql': {
            'table_matches': 0.25, 'terminologies': 0.25, 'sql_examples': 0.40,
            'analysis_examples': 0.05, 'predict_examples': 0.05, 'doc_chunks': 0.00,
        },
        'excel_analysis': {
            'table_matches': 0.15, 'terminologies': 0.35, 'sql_examples': 0.10,
            'analysis_examples': 0.30, 'predict_examples': 0.10, 'doc_chunks': 0.00,
        },
        'excel_prediction': {
            'table_matches': 0.15, 'terminologies': 0.30, 'sql_examples': 0.10,
            'analysis_examples': 0.10, 'predict_examples': 0.35, 'doc_chunks': 0.00,
        },
    }

    @staticmethod
    def get_dimension_weights(ds_type: str = 'database', intent: str = 'sql') -> Dict[str, float]:
        """根据数据源类型和意图获取场景化的维度权重"""
        ds = ds_type.lower() if ds_type else 'database'
        # csv 与 excel 共享权重配置
        if ds == 'csv':
            ds = 'excel'
        # pg/mysql/oracle → database
        if ds not in ('database', 'pdf', 'excel'):
            ds = 'database'

        # 映射意图到权重键
        intent_key = intent.lower() if intent else 'sql'
        if intent_key in ('data_query', 'visualization', 'sql_generation', 'sql'):
            intent_key = 'sql'
        elif intent_key in ('data_analysis', 'analysis'):
            intent_key = 'analysis'
        elif intent_key in ('data_prediction', 'prediction'):
            intent_key = 'prediction'
        elif intent_key == 'document_qa':
            intent_key = 'document_qa'
        else:
            intent_key = 'sql'

        scenario_key = f'{ds}_{intent_key}'
        return RAGQualityMetrics.SCENARIO_WEIGHTS.get(
            scenario_key, RAGQualityMetrics.DIMENSION_WEIGHTS
        )

    @staticmethod
    def _extract_similarities(items: List[Dict]) -> List[float]:
        """从检索结果中提取并归一化相似度分数"""
        similarities = []
        for item in items:
            sim = item.get('similarity', 0) or 0
            if sim > 1:
                sim = sim / 100.0
            similarities.append(max(0.0, min(1.0, sim)))
        return similarities

    @staticmethod
    def _log_saturation(count: int, threshold: int) -> float:
        """对数饱和曲线：模拟知识数量的边际递减效应"""
        import math
        if threshold <= 0 or count <= 0:
            return 0.0
        return min(1.0, math.log(1 + count) / math.log(1 + threshold))

    @staticmethod
    def calculate_retrieval_quality(items: List[Dict], threshold: float = 0.7) -> Dict[str, Any]:
        """计算检索质量指标"""
        if not items:
            return {
                'total_count': 0,
                'high_quality_count': 0,
                'avg_similarity': 0.0,
                'median_similarity': 0.0,
                'similarity_variance': 0.0,
                'quality_score': 0.0,
                'confidence': 'none',
                'score_breakdown': {
                    'median_component': 0.0,
                    'high_quality_component': 0.0,
                    'consistency_component': 0.0
                }
            }

        similarities = RAGQualityMetrics._extract_similarities(items)
        n = len(similarities)

        # 基础统计
        avg_sim = sum(similarities) / n
        sorted_sims = sorted(similarities)
        median_sim = sorted_sims[n // 2] if n % 2 == 1 else (sorted_sims[n // 2 - 1] + sorted_sims[n // 2]) / 2

        # 方差（衡量结果一致性）
        variance = sum((s - avg_sim) ** 2 for s in similarities) / n

        high_quality = sum(1 for s in similarities if s >= threshold)
        high_quality_ratio = high_quality / n

        # 一致性分数：方差越小越好，variance * 4 是归一化因子
        # 当方差=0时一致性=1，方差>=0.25时一致性=0
        consistency = max(0.0, 1.0 - min(variance * 4, 1.0))

        # 综合质量评分
        median_component = median_sim * 0.5
        hq_component = high_quality_ratio * 0.3
        consistency_component = consistency * 0.2
        quality_score = median_component + hq_component + consistency_component

        # 置信度评级（基于质量评分而非单一平均值）
        if quality_score >= 0.75:
            confidence = 'high'
        elif quality_score >= 0.55:
            confidence = 'medium'
        elif quality_score >= 0.35:
            confidence = 'low'
        elif quality_score > 0:
            confidence = 'very_low'
        else:
            confidence = 'none'

        return {
            'total_count': n,
            'high_quality_count': high_quality,
            'avg_similarity': round(avg_sim, 3),
            'median_similarity': round(median_sim, 3),
            'similarity_variance': round(variance, 4),
            'quality_score': round(quality_score, 3),
            'confidence': confidence,
            'score_breakdown': {
                'median_component': round(median_component, 3),
                'high_quality_component': round(hq_component, 3),
                'consistency_component': round(consistency_component, 3)
            }
        }

    @staticmethod
    def calculate_rag_impact(rag_enabled: bool, terminologies: List, sql_examples: List,
                            analysis_examples: List = None, predict_examples: List = None,
                            doc_chunks: List = None, table_matches: List = None,
                            ds_type: str = 'database', intent: str = 'sql') -> Dict[str, Any]:
        """计算RAG对结果的影响程度"""
        import math

        if not rag_enabled:
            return {
                'impact_level': 'none',
                'knowledge_coverage': 0.0,
                'coverage_breakdown': {},
                'expected_improvement': 0.0,
                'expected_improvement_display': '0%',
                'quality_score': 0.0,
                'confidence': 'none',
                'recommendation': '建议开启RAG以提升准确性'
            }

        # 各维度数据（包含表检索和文档片段维度）
        dimensions = {
            'table_matches': table_matches or [],
            'terminologies': terminologies or [],
            'sql_examples': sql_examples or [],
            'analysis_examples': analysis_examples or [],
            'predict_examples': predict_examples or [],
            'doc_chunks': doc_chunks or [],
        }

        total_knowledge = sum(len(v) for v in dimensions.values())

        if total_knowledge == 0:
            return {
                'impact_level': 'none',
                'knowledge_coverage': 0.0,
                'coverage_breakdown': {},
                'expected_improvement': 0.0,
                'expected_improvement_display': '0%',
                'quality_score': 0.0,
                'confidence': 'none',
                'recommendation': '未检索到相关知识，建议补充术语库、SQL示例或上传文档，或尝试用更具体的关键词提问',
                'fallback_triggered': True
            }

        # === 1. 多维度知识覆盖率 ===
        scenario_weights = RAGQualityMetrics.get_dimension_weights(ds_type, intent)
        coverage_breakdown = {}
        weighted_coverage = 0.0
        active_weight_sum = 0.0
        active_dimensions = 0

        for dim_name, dim_items in dimensions.items():
            threshold = RAGQualityMetrics.SATURATION_THRESHOLDS[dim_name]
            weight = scenario_weights.get(dim_name, 0.1)

            dim_coverage = RAGQualityMetrics._log_saturation(len(dim_items), threshold)
            coverage_breakdown[dim_name] = {
                'count': len(dim_items),
                'saturation_threshold': threshold,
                'coverage': round(dim_coverage, 3)
            }

            if len(dim_items) > 0:
                active_dimensions += 1
                weighted_coverage += dim_coverage * weight
                active_weight_sum += weight

        # 归一化：只按有数据的维度权重归一化，避免空维度拉低分数
        knowledge_coverage = round(weighted_coverage / active_weight_sum, 3) if active_weight_sum > 0 else 0.0

        # === 2. 综合质量评分 ===
        all_items = []
        for dim_items in dimensions.values():
            all_items.extend(dim_items)

        quality_metrics = RAGQualityMetrics.calculate_retrieval_quality(all_items)
        quality_score = quality_metrics['quality_score']

        # === 3. 预期提升（连续函数计算） ===
        base_improvement = quality_score * 0.40

        # 多样性加成：使用多种知识源有协同效应（每多一个维度+15%加成）
        diversity_bonus = 1.0 + 0.15 * max(0, active_dimensions - 1)

        # 数量边际递减：总知识量的对数饱和
        diminishing_factor = RAGQualityMetrics._log_saturation(total_knowledge, 15)

        # 最终预期提升百分比
        expected_improvement = base_improvement * diversity_bonus * diminishing_factor
        expected_improvement = round(min(expected_improvement, 0.50), 3)  # 封顶50%

        # === 4. 影响等级（基于实际计算的improvement） ===
        if expected_improvement >= 0.25:
            impact_level = 'high'
        elif expected_improvement >= 0.12:
            impact_level = 'medium'
        elif expected_improvement >= 0.05:
            impact_level = 'low'
        else:
            impact_level = 'minimal'

        # 显示格式
        improvement_pct = round(expected_improvement * 100, 1)
        improvement_display = f'{improvement_pct}%'

        recommendation_parts = []
        if quality_metrics['confidence'] in ('low', 'very_low'):
            recommendation_parts.append('检索质量偏低，建议优化知识库内容')
        if active_dimensions <= 1:
            recommendation_parts.append('建议补充更多类型的知识（术语+SQL示例+文档）以获得协同效应')
        if knowledge_coverage < 0.5:
            recommendation_parts.append('知识覆盖不足，建议增加相关知识条目')
        if not recommendation_parts:
            recommendation_parts.append(f'RAG质量{quality_metrics["confidence"]}，预期提升{improvement_display}')

        return {
            'impact_level': impact_level,
            'knowledge_coverage': knowledge_coverage,
            'coverage_breakdown': coverage_breakdown,
            'expected_improvement': expected_improvement,
            'expected_improvement_display': improvement_display,
            'quality_score': quality_score,
            'quality_breakdown': quality_metrics.get('score_breakdown', {}),
            'confidence': quality_metrics['confidence'],
            'active_dimensions': active_dimensions,
            'total_knowledge': total_knowledge,
            'recommendation': '；'.join(recommendation_parts)
        }



@dataclass
class RAGRetrievalResult:
    """RAG检索结果"""
    # 数据源级别检索
    datasource_candidates: List[Dict] = field(default_factory=list)
    datasource_selected: Optional[Dict] = None
    datasource_similarity: float = 0.0
    
    # 表级别检索
    table_candidates: List[Dict] = field(default_factory=list)
    tables_selected: List[str] = field(default_factory=list)
    table_similarities: List[float] = field(default_factory=list)
    
    # 术语库检索
    terminologies: List[Dict] = field(default_factory=list)
    terminology_count: int = 0
    terminology_quality: Dict = field(default_factory=dict)  # 新增：术语质量评估
    
    # SQL示例检索
    sql_examples: List[Dict] = field(default_factory=list)
    example_count: int = 0
    example_quality: Dict = field(default_factory=dict)  # 新增：示例质量评估
    
    # 分析示例检索（用于数据分析任务）
    analysis_examples: List[Dict] = field(default_factory=list)
    analysis_example_count: int = 0
    
    # 预测示例检索（用于数据预测任务）
    predict_examples: List[Dict] = field(default_factory=list)
    predict_example_count: int = 0
    
    # 文档片段检索（PDF/Excel/CSV的核心知识源）
    doc_chunks: List[Dict] = field(default_factory=list)
    doc_chunk_count: int = 0
    
    # 自定义提示词（注意：这不属于RAG检索，而是Prompt工程的一部分）
    custom_prompts: List[Dict] = field(default_factory=list)
    
    # 检索统计
    total_retrieval_time: float = 0.0
    rag_enabled: bool = True
    
    # RAG影响评估（新增）
    rag_impact: Dict = field(default_factory=dict)
    
    def calculate_quality_metrics(self, ds_type: str = 'database', intent: str = 'sql'):
        """计算并更新质量指标"""
        # 术语质量
        if self.terminologies:
            self.terminology_quality = RAGQualityMetrics.calculate_retrieval_quality(
                self.terminologies, threshold=0.7
            )
        
        # SQL示例质量
        if self.sql_examples:
            self.example_quality = RAGQualityMetrics.calculate_retrieval_quality(
                self.sql_examples, threshold=0.7
            )
        
        # 构建表检索的质量评估数据（将 table_similarities 转为 calculate_rag_impact 期望的格式）
        _table_match_items = []
        for i, tbl_name in enumerate(self.tables_selected):
            sim = self.table_similarities[i] if i < len(self.table_similarities) else 0.0
            _table_match_items.append({'name': tbl_name, 'similarity': sim})
        
        # RAG整体影响（使用场景化权重，包含表检索维度）
        self.rag_impact = RAGQualityMetrics.calculate_rag_impact(
            self.rag_enabled,
            self.terminologies,
            self.sql_examples,
            self.analysis_examples,
            self.predict_examples,
            doc_chunks=self.doc_chunks,
            table_matches=_table_match_items,
            ds_type=ds_type,
            intent=intent,
        )


@dataclass
class LLMGenerationResult:
    """LLM生成结果"""
    # 输入上下文
    context_from_rag: Dict = field(default_factory=dict)
    
    # 生成结果
    generated_content: str = ""
    reasoning_process: str = ""
    
    # 生成统计
    generation_time: float = 0.0
    token_usage: Dict = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """执行结果"""
    sql: str = ""
    execution_time: float = 0.0
    row_count: int = 0
    success: bool = True
    error: Optional[str] = None


@dataclass
class ThinkingStage:
    """思考阶段"""
    stage_name: str
    status: str = "running"  # running, completed, failed
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    
    # RAG检索结果
    rag_retrieval: Optional[RAGRetrievalResult] = None
    
    # LLM生成结果
    llm_generation: Optional[LLMGenerationResult] = None
    
    # 执行结果
    execution: Optional[ExecutionResult] = None
    
    # 额外数据
    extra_data: Dict = field(default_factory=dict)
    
    def complete(self):
        """完成阶段"""
        self.status = "completed"
        self.end_time = time.time()
    
    def fail(self, error: str):
        """失败阶段"""
        self.status = "failed"
        self.end_time = time.time()
        self.extra_data['error'] = error
    
    def duration(self) -> float:
        """获取耗时（秒）"""
        if self.end_time:
            return round(self.end_time - self.start_time, 3)
        return round(time.time() - self.start_time, 3)
    
    def duration_ms(self) -> int:
        """获取耗时（毫秒）- 用于前端显示"""
        return int(self.duration() * 1000)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "stage": self.stage_name,
            "status": self.status,
            "duration": self.duration_ms()
        }
        
        if self.rag_retrieval:
            result["rag_retrieval"] = asdict(self.rag_retrieval)
        
        if self.llm_generation:
            result["llm_generation"] = asdict(self.llm_generation)
        
        if self.execution:
            result["execution"] = asdict(self.execution)
        
        result["extra_data"] = self.extra_data
        return result


class RAGThinkingProcess:
    """RAG增强的思考过程记录器"""
    
    def __init__(self):
        self.stages: Dict[str, ThinkingStage] = {}
        self.question: str = ""
        self.rag_enabled: bool = True
        self.dialogue_context_injected: Optional[Dict[str, Any]] = None
    
    def set_question(self, question: str):
        """设置用户问题"""
        self.question = question
    
    def set_rag_enabled(self, enabled: bool):
        """设置RAG模式"""
        self.rag_enabled = enabled
    
    def start_stage(self, stage_name: str) -> ThinkingStage:
        """开始新阶段
        
         如果同名阶段已存在，记录警告日志，避免数据被静默覆盖。
        prompt_construction 阶段允许覆盖（内部有合并逻辑）。
        """
        if stage_name in self.stages and stage_name != 'prompt_construction':
            try:
                from common.utils.utils import ChatBILogUtil
                ChatBILogUtil.warning(
                    f"[ThinkingProcess] Stage '{stage_name}' already exists and will be overwritten. "
                    f"Previous status: {self.stages[stage_name].status}"
                )
            except Exception:
                pass
        stage = ThinkingStage(stage_name=stage_name)
        self.stages[stage_name] = stage
        return stage
    
    def get_stage(self, stage_name: str) -> Optional[Dict[str, Any]]:
        """获取阶段数据"""
        if stage_name in self.stages:
            return self.stages[stage_name].to_dict()
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """导出所有数据 - 兼容前端期望的格式"""
        # 阶段名称映射：后端名称 -> 前端期望名称
        # 重构：统一使用 rag_retrieval 阶段名，不再需要 schema_retrieval 映射
        stage_name_mapping = {
            'sql_generation': 'sql_generation',
            'sql_execution': 'sql_execution',
            'chart_generation': 'chart_generation',
            'data_analysis': 'data_analysis',
            'data_prediction': 'data_prediction'
        }
        
        # 转换为前端期望的格式
        stages_dict = {}
        for backend_name, stage in self.stages.items():
            frontend_name = stage_name_mapping.get(backend_name, backend_name)
            # 如果映射后的名称已存在，保留已完成的阶段，跳过重复的
            if frontend_name in stages_dict:
                existing_status = stages_dict[frontend_name].get('status', '')
                new_status = stage.status
                # 优先保留 completed 状态的阶段
                if existing_status == 'completed' and new_status != 'completed':
                    try:
                        from common.utils.utils import ChatBILogUtil
                        ChatBILogUtil.warning(
                            f"[ThinkingProcess] Stage name conflict: '{backend_name}' -> '{frontend_name}' "
                            f"already exists (status={existing_status}), skipping duplicate"
                        )
                    except Exception:
                        pass
                    continue
            stage_data = stage.to_dict()
            stage_data['name'] = frontend_name  # 添加 name 字段
            stages_dict[frontend_name] = stage_data
        
        result = {
            "question": self.question,
            "rag_enabled": self.rag_enabled,
            "stages": stages_dict  # 保持对象格式，前端会处理
        }
        
        # 包含对话上下文注入信息（如果有多轮对话）
        if self.dialogue_context_injected:
            result["dialogue_context_injected"] = self.dialogue_context_injected
        
        return result
    
    def record_stage(
        self,
        name: str,
        status: str = 'completed',
        duration: int = 0,
        extra_data: Dict[str, Any] = None,
        llm_generation: Dict[str, Any] = None
    ) -> ThinkingStage:
        """便捷方法：一次性创建并完成一个阶段"""
        stage = self.start_stage(name)
        
        if extra_data:
            stage.extra_data = extra_data
        
        if llm_generation:
            stage.llm_generation = LLMGenerationResult(
                generation_time=llm_generation.get('generation_time', 0),
                token_usage=llm_generation.get('token_usage', {}),
                generated_content=llm_generation.get('generated_content', ''),
                reasoning_process=llm_generation.get('reasoning_process', ''),
                context_from_rag=llm_generation.get('context_from_rag', {})
            )
        
        # 使用传入的duration设置end_time
        if duration > 0:
            stage.end_time = stage.start_time + (duration / 1000.0)
        else:
            stage.end_time = time.time()
        
        stage.status = status
        return stage

    def to_json_string(self) -> str:
        """导出为JSON字符串"""
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False)


# ============ 便捷函数 ============


def record_datasource_selection(
    thinking: RAGThinkingProcess,
    question: str,
    datasource_candidates: List[Dict],
    selected_datasource: Dict,
    similarity: float,
    rag_enabled: bool = True
) -> ThinkingStage:
    """记录数据源选择阶段（RAG核心：数据源级别检索）"""
    stage = thinking.start_stage("datasource_selection")
    
    # RAG检索结果
    rag_result = RAGRetrievalResult(
        datasource_candidates=datasource_candidates[:5],  # 只保留前5个候选
        datasource_selected=selected_datasource,
        datasource_similarity=similarity,
        rag_enabled=rag_enabled
    )
    stage.rag_retrieval = rag_result
    
    # LLM生成结果（如果使用LLM选择）
    if not rag_enabled:
        llm_result = LLMGenerationResult(
            context_from_rag={},
            generated_content=f"Selected datasource: {selected_datasource.get('name')}"
        )
        stage.llm_generation = llm_result
    
    stage.complete()
    return stage


def record_rag_retrieval(
    thinking: RAGThinkingProcess,
    question: str,
    table_candidates: List[Dict] = None,
    selected_tables: List[str] = None,
    similarities: List[float] = None,
    terminologies: List[Dict] = None,
    sql_examples: List[Dict] = None,
    custom_prompts: List[Dict] = None,
    retrieval_time: float = 0.0,
    rag_enabled: bool = True,
    analysis_examples: List[Dict] = None,
    predict_examples: List[Dict] = None,
    doc_chunks: List[Dict] = None,
    ds_type: str = 'database',
    intent: str = 'sql',
) -> ThinkingStage:
    """记录RAG知识检索阶段（统一函数，所有路径共用）"""
    _table_candidates = table_candidates or []
    _selected_tables = selected_tables or []
    _similarities = similarities or []
    _terminologies = terminologies or []
    _sql_examples = sql_examples or []
    _custom_prompts = custom_prompts or []

    stage = thinking.start_stage("rag_retrieval")
    
    # RAG检索结果
    rag_result = RAGRetrievalResult(
        table_candidates=_table_candidates[:10],
        tables_selected=_selected_tables,
        table_similarities=_similarities,
        terminologies=_terminologies[:5],
        terminology_count=len(_terminologies),
        sql_examples=_sql_examples[:3] if _sql_examples else [],
        example_count=len(_sql_examples) if _sql_examples else 0,
        analysis_examples=analysis_examples[:3] if analysis_examples else [],  # 前3个分析示例
        analysis_example_count=len(analysis_examples) if analysis_examples else 0,
        predict_examples=predict_examples[:3] if predict_examples else [],  # 前3个预测示例
        predict_example_count=len(predict_examples) if predict_examples else 0,
        doc_chunks=doc_chunks[:8] if doc_chunks else [],  # 前8个文档片段
        doc_chunk_count=len(doc_chunks) if doc_chunks else 0,
        custom_prompts=_custom_prompts,
        total_retrieval_time=retrieval_time,
        rag_enabled=rag_enabled
    )
    
    # 计算质量指标（使用场景化权重）
    rag_result.calculate_quality_metrics(ds_type=ds_type, intent=intent)
    
    stage.rag_retrieval = rag_result
    
    # 添加质量摘要到额外数据
    rag_knowledge_count = len(_terminologies) + len(_sql_examples) + len(analysis_examples or []) + len(predict_examples or []) + len(doc_chunks or [])
    stage.extra_data = {
        "terminology_confidence": rag_result.terminology_quality.get('confidence', 'none'),
        "example_confidence": rag_result.example_quality.get('confidence', 'none'),
        "rag_impact_level": rag_result.rag_impact.get('impact_level', 'none'),
        "expected_improvement": rag_result.rag_impact.get('expected_improvement_display', '0%'),
        "knowledge_types": [],
        "total_knowledge_items": rag_knowledge_count,
    }
    
    # 记录使用的 RAG 知识类型（仅向量检索的知识库）
    if _terminologies:
        stage.extra_data["knowledge_types"].append(f"术语库({len(_terminologies)})")
    if _sql_examples:
        stage.extra_data["knowledge_types"].append(f"SQL示例({len(_sql_examples)})")
    if analysis_examples:
        stage.extra_data["knowledge_types"].append(f"分析示例({len(analysis_examples)})")
    if predict_examples:
        stage.extra_data["knowledge_types"].append(f"预测示例({len(predict_examples)})")
    if doc_chunks:
        stage.extra_data["knowledge_types"].append(f"文档片段({len(doc_chunks)})")
    
    stage.end_time = stage.start_time + max(retrieval_time, 0)
    
    stage.status = "completed"
    
    return stage


# 向后兼容别名
record_schema_retrieval = record_rag_retrieval


def record_sql_generation(
    thinking: RAGThinkingProcess,
    sql: str,
    tables: List[str],
    reasoning: str,
    rag_context: Dict,
    generation_time: float,
    token_usage: Dict,
    model_name: Optional[str] = None
) -> ThinkingStage:
    """记录SQL生成阶段（LLM基于RAG上下文生成）"""
    stage = thinking.start_stage("sql_generation")
    
    # LLM生成结果
    llm_result = LLMGenerationResult(
        context_from_rag=rag_context,
        generated_content=sql,
        reasoning_process=reasoning[:500],  # 限制长度
        generation_time=generation_time,
        token_usage=token_usage
    )
    stage.llm_generation = llm_result
    
    # 额外数据
    stage.extra_data = {
        "tables_used": tables,
        "sql_length": len(sql),
        "model_name": model_name  # 添加模型名称
    }
    
    stage.end_time = stage.start_time + max(generation_time, 0)
    
    stage.status = "completed"
    
    return stage


def record_sql_execution(
    thinking: RAGThinkingProcess,
    sql: str,
    execution_time: float,
    row_count: int,
    success: bool = True,
    error: Optional[str] = None
) -> ThinkingStage:
    """记录SQL执行阶段"""
    stage = thinking.start_stage("sql_execution")
    
    # 执行结果
    exec_result = ExecutionResult(
        sql=sql,
        execution_time=execution_time,
        row_count=row_count,
        success=success,
        error=error
    )
    stage.execution = exec_result
    
    # execution_time是毫秒，需要转换为秒来计算end_time
    stage.end_time = stage.start_time + max(execution_time / 1000.0, 0)
    
    if success:
        stage.status = "completed"
    else:
        stage.fail(error or "SQL execution failed")
    
    return stage


def record_chart_generation(
    thinking: RAGThinkingProcess,
    chart_type: str,
    reasoning: str,
    rag_context: Dict,
    generation_time: float,
    token_usage: Dict = None
) -> ThinkingStage:
    """记录图表生成阶段（LLM基于数据生成）"""
    stage = thinking.start_stage("chart_generation")
    
    # LLM生成结果
    llm_result = LLMGenerationResult(
        context_from_rag=rag_context,
        generated_content=chart_type,
        reasoning_process=reasoning[:500],
        generation_time=generation_time,
        token_usage=token_usage or {}
    )
    stage.llm_generation = llm_result
    
    stage.extra_data = {"chart_type": chart_type}
    
    # generation_time=0 时直接设置 end_time = start_time，
    # 避免 duration() 返回从 start_stage 到 time.time() 的偏大值
    stage.end_time = stage.start_time + max(generation_time, 0)
    
    stage.status = "completed"
    
    return stage


def record_data_analysis(
    thinking: RAGThinkingProcess,
    analysis: str,
    reasoning: str,
    rag_context: Dict,
    generation_time: float,
    token_usage: Dict = None
) -> ThinkingStage:
    """记录数据分析阶段（LLM基于数据分析）"""
    stage = thinking.start_stage("data_analysis")
    
    # LLM生成结果
    llm_result = LLMGenerationResult(
        context_from_rag=rag_context,
        generated_content=analysis[:1000],
        reasoning_process=reasoning[:500],
        generation_time=generation_time,
        token_usage=token_usage or {}
    )
    stage.llm_generation = llm_result
    
    stage.end_time = stage.start_time + max(generation_time, 0)
    
    stage.status = "completed"
    
    return stage


def record_data_prediction(
    thinking: RAGThinkingProcess,
    prediction: str,
    reasoning: str,
    rag_context: Dict,
    generation_time: float,
    token_usage: Dict = None
) -> ThinkingStage:
    """记录数据预测阶段（LLM基于数据预测）"""
    stage = thinking.start_stage("data_prediction")
    
    # LLM生成结果
    llm_result = LLMGenerationResult(
        context_from_rag=rag_context,
        generated_content=prediction[:1000],
        reasoning_process=reasoning[:500],
        generation_time=generation_time,
        token_usage=token_usage or {}
    )
    stage.llm_generation = llm_result
    
    stage.end_time = stage.start_time + max(generation_time, 0)
    
    stage.status = "completed"
    
    return stage
