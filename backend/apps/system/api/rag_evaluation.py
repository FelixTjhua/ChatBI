"""
RAG评估指标API
提供检索质量、生成质量、端到端性能的评估接口

"""
import json
import traceback
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import select
from sqlalchemy import func

from apps.chat.models.chat_model import ChatRecord, ChatLog, OperationEnum, Chat
from apps.chat.thinking.rag_evaluator import RAGEvaluator, EvaluationReport
from apps.chat.thinking.dialogue_state import DialogueStateTracker
from common.core.deps import SessionDep, CurrentUser
from common.utils.utils import ChatBILogUtil

router = APIRouter(tags=["system/rag-evaluation"], prefix="/system/rag")


class EvaluationRequest(BaseModel):
    record_id: int = Field(..., description="聊天记录ID")


class BatchEvaluationRequest(BaseModel):
    chat_id: int = Field(..., description="会话ID")
    limit: int = Field(10, description="评估最近N条记录")


class EvaluationResponse(BaseModel):
    success: bool
    report: Optional[dict] = None
    error: Optional[str] = None


class BatchEvaluationResponse(BaseModel):
    success: bool
    reports: List[dict] = []
    summary: Optional[dict] = None
    error: Optional[str] = None


@router.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_record(
    request: EvaluationRequest,
    session: SessionDep,
    current_user: CurrentUser
):
    """
    评估单条聊天记录的RAG质量
    
    返回检索质量（Precision@K, MRR, NDCG）、
    生成质量（SQL成功率、Token效率）、
    端到端性能（延迟、完成率）的综合评估报告。
    """
    try:
        record = session.get(ChatRecord, request.record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")
        # 安全修复：验证记录归属当前用户，防止越权访问
        if record.create_by != current_user.id:
            raise HTTPException(status_code=404, detail="Record not found")

        # 1. 提取检索结果
        retrieval_items = []
        if record.rag_results:
            try:
                rag_data = json.loads(record.rag_results)
                for term in rag_data.get('terminologies', []):
                    retrieval_items.append({'similarity': term.get('similarity', 0)})
                for ex in rag_data.get('sql_examples', []):
                    retrieval_items.append({'similarity': ex.get('similarity', 0)})
                # PDF数据源的主要检索源是文档片段(document_chunks)，
                for dc in rag_data.get('document_chunks', []):
                    retrieval_items.append({'similarity': dc.get('similarity', 0)})
            except (json.JSONDecodeError, TypeError):
                pass

        # 2. 评估检索质量
        retrieval_metrics = RAGEvaluator.evaluate_retrieval(retrieval_items)

        # 3. 提取生成信息
        sql = record.sql or ""
        sql_success = bool(record.data and not record.error)
        token_usage = {}
        generation_time = 0.0

        # 从chat_log获取token使用量
        log = session.exec(
            select(ChatLog).where(
                ChatLog.pid == record.id,
                ChatLog.operate == OperationEnum.GENERATE_SQL
            ).order_by(ChatLog.start_time.desc()).limit(1)
        ).first()
        if log:
            if log.token_usage:
                token_usage = log.token_usage if isinstance(log.token_usage, dict) else {}
            if log.start_time and log.finish_time:
                generation_time = (log.finish_time - log.start_time).total_seconds()

        # 4. 评估生成质量
        # 加载Schema用于幻觉检测
        rag_context = {}
        schema_str = ''
        if record.rag_results:
            try:
                rag_data = json.loads(record.rag_results)
                rag_context = {
                    'terminologies_used': len(rag_data.get('terminologies', [])),
                    'sql_examples_used': len(rag_data.get('sql_examples', [])),
                    'schema': schema_str
                }
            except (json.JSONDecodeError, TypeError):
                pass
        
        # 从thinking_process中提取schema信息
        if record.thinking_process:
            try:
                tp = json.loads(record.thinking_process) if isinstance(record.thinking_process, str) else record.thinking_process
                stages = tp.get('stages', {})
                schema_stage = stages.get('rag_retrieval', stages.get('schema_retrieval', {})) if isinstance(stages, dict) else None
                if schema_stage and schema_stage.get('extra_data', {}).get('schema'):
                    schema_str = schema_stage['extra_data']['schema']
                    rag_context['schema'] = schema_str
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass
        
        # 如果thinking_process中没有schema，尝试从数据源获取
        if not schema_str and record.chat_id:
            try:
                chat = session.get(Chat, record.chat_id)
                if chat and chat.datasource:
                    from apps.datasource.crud.datasource import get_table_schema
                    from apps.datasource.models.datasource import CoreDatasource
                    ds = session.get(CoreDatasource, chat.datasource)
                    if ds:
                        schema_str = get_table_schema(session=session, current_user=current_user, ds=ds, question=record.question or '')
                        rag_context['schema'] = schema_str[:2000]  # 限制长度
            except Exception as e:
                ChatBILogUtil.debug(f"Schema loading failed for record {record.id} (non-blocking): {e}")  # Schema加载失败不影响其他评估

        generation_metrics = RAGEvaluator.evaluate_generation(
            generated_content=record.analysis or record.chart_answer or "",
            sql=sql,
            sql_executed=sql_success,
            sql_error=record.error or "",
            token_usage=token_usage,
            generation_time=generation_time,
            rag_context=rag_context
        )

        # 5. 评估端到端性能
        stages = {}
        if record.thinking_process:
            try:
                tp = json.loads(record.thinking_process)
                for stage_name, stage_data in tp.get('stages', {}).items():
                    stages[stage_name] = {
                        'duration': stage_data.get('duration', 0),
                        'status': stage_data.get('status', 'unknown')
                    }
            except (json.JSONDecodeError, TypeError):
                pass

        end_to_end_metrics = RAGEvaluator.evaluate_end_to_end(
            stages=stages,
            task_completed=bool(record.finish),
            total_steps=3,
            error_count=1 if record.error else 0
        )

        # 6. 生成综合报告
        report = RAGEvaluator.generate_report(
            question=record.question or "",
            chat_id=record.chat_id,
            record_id=record.id,
            retrieval_metrics=retrieval_metrics,
            generation_metrics=generation_metrics,
            end_to_end_metrics=end_to_end_metrics
        )

        return EvaluationResponse(success=True, report=report.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        ChatBILogUtil.error(f"Evaluation failed: {e}\n{traceback.format_exc()}")
        return EvaluationResponse(success=False, error=str(e))


@router.post("/evaluate/batch", response_model=BatchEvaluationResponse)
async def evaluate_batch(
    request: BatchEvaluationRequest,
    session: SessionDep,
    current_user: CurrentUser
):
    """
    批量评估会话中的聊天记录
    
    返回每条记录的评估报告和整体统计摘要。
    """
    try:
        # 安全修复：验证会话归属当前用户
        chat = session.get(Chat, request.chat_id)
        if not chat or chat.create_by != current_user.id:
            return BatchEvaluationResponse(success=False, error="Chat not found")
        
        records = session.exec(
            select(ChatRecord).where(
                ChatRecord.chat_id == request.chat_id
            ).order_by(ChatRecord.create_time.desc()).limit(request.limit)
        ).all()

        if not records:
            return BatchEvaluationResponse(success=True, reports=[], summary={'total': 0})

        reports = []
        total_score = 0.0
        grade_counts = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}

        for record in records:
            try:
                # 简化的单条评估
                retrieval_items = []
                if record.rag_results:
                    try:
                        rag_data = json.loads(record.rag_results)
                        for term in rag_data.get('terminologies', []):
                            retrieval_items.append({'similarity': term.get('similarity', 0)})
                        for ex in rag_data.get('sql_examples', []):
                            retrieval_items.append({'similarity': ex.get('similarity', 0)})
                        # PDF数据源的主要检索源是文档片段(document_chunks)
                        for dc in rag_data.get('document_chunks', []):
                            retrieval_items.append({'similarity': dc.get('similarity', 0)})
                    except (json.JSONDecodeError, TypeError):
                        pass

                retrieval_metrics = RAGEvaluator.evaluate_retrieval(retrieval_items)
                
                # 加载Schema用于幻觉检测
                rag_context = {}
                schema_str = ''
                if record.rag_results:
                    try:
                        rag_data_batch = json.loads(record.rag_results)
                        rag_context = {
                            'terminologies_used': len(rag_data_batch.get('terminologies', [])),
                            'terminologies': rag_data_batch.get('terminologies', []),
                            'sql_examples_used': len(rag_data_batch.get('sql_examples', [])),
                            'sql_examples': rag_data_batch.get('sql_examples', []),
                        }
                    except (json.JSONDecodeError, TypeError):
                        pass
                
                # 从thinking_process中提取schema
                if record.thinking_process:
                    try:
                        tp_batch = json.loads(record.thinking_process) if isinstance(record.thinking_process, str) else record.thinking_process
                        stages_batch = tp_batch.get('stages', {})
                        schema_stage_batch = stages_batch.get('rag_retrieval', stages_batch.get('schema_retrieval', {})) if isinstance(stages_batch, dict) else None
                        if schema_stage_batch and schema_stage_batch.get('extra_data', {}).get('schema'):
                            schema_str = schema_stage_batch['extra_data']['schema']
                            rag_context['schema'] = schema_str[:2000]
                    except (json.JSONDecodeError, TypeError, AttributeError):
                        pass
                
                # 如果没有schema，尝试从数据源获取
                if not schema_str and record.chat_id:
                    try:
                        chat_batch = session.get(Chat, record.chat_id)
                        if chat_batch and chat_batch.datasource:
                            from apps.datasource.crud.datasource import get_table_schema
                            from apps.datasource.models.datasource import CoreDatasource as _CoreDS
                            ds_batch = session.get(_CoreDS, chat_batch.datasource)
                            if ds_batch:
                                schema_str = get_table_schema(session=session, current_user=current_user, ds=ds_batch, question=record.question or '')
                                rag_context['schema'] = schema_str[:2000]
                    except Exception:
                        pass
                
                generation_metrics = RAGEvaluator.evaluate_generation(
                    generated_content=record.analysis or "",
                    sql=record.sql or "",
                    sql_executed=bool(record.data and not record.error),
                    rag_context=rag_context
                )

                report = RAGEvaluator.generate_report(
                    question=record.question or "",
                    chat_id=record.chat_id,
                    record_id=record.id,
                    retrieval_metrics=retrieval_metrics,
                    generation_metrics=generation_metrics
                )

                reports.append(report.to_dict())
                total_score += report.overall_score
                grade_counts[report.grade] = grade_counts.get(report.grade, 0) + 1
            except Exception as e:
                ChatBILogUtil.error(f"Failed to evaluate record {record.id}: {e}")

        avg_score = round(total_score / len(reports), 1) if reports else 0

        # 根据平均分计算平均评级（满分100分制，对齐 generate_report）
        def score_to_grade(score: float) -> str:
            if score >= 90: return 'A'
            if score >= 75: return 'B'
            if score >= 60: return 'C'
            if score >= 40: return 'D'
            return 'F'

        summary = {
            'total': len(reports),
            'avg_score': avg_score,
            'grade_distribution': grade_counts,
            'avg_grade': score_to_grade(avg_score) if reports else 'N/A'
        }

        return BatchEvaluationResponse(success=True, reports=reports, summary=summary)

    except Exception as e:
        ChatBILogUtil.error(f"Batch evaluation failed: {e}\n{traceback.format_exc()}")
        return BatchEvaluationResponse(success=False, error=str(e))


@router.get("/dialogue-state/{chat_id}")
async def get_dialogue_state(
    chat_id: int,
    session: SessionDep,
    current_user: CurrentUser
):
    """
    获取会话的对话状态追踪信息
    
    返回意图追踪、话题检测、实体记忆等对话状态。
    """
    try:
        # 安全修复：验证会话归属当前用户
        chat = session.get(Chat, chat_id)
        if not chat or chat.create_by != current_user.id:
            return {"success": False, "error": "Chat not found"}
        
        records = session.exec(
            select(ChatRecord).where(
                ChatRecord.chat_id == chat_id
            ).order_by(ChatRecord.create_time.asc())
        ).all()

        if not records:
            return {"success": True, "state": {"dialogue_length": 0}}

        tracker = DialogueStateTracker()
        turn_results = []

        for record in records:
            if not record.question:
                continue
            result = tracker.track_turn(
                question=record.question,
                sql=record.sql or "",
                sql_success=bool(record.data and not record.error)
            )
            turn_results.append(result)

        return {
            "success": True,
            "state": tracker.get_state_summary(),
            "context": tracker.get_dialogue_context(),
            "turns": turn_results[-10:]  # 最近10轮
        }

    except Exception as e:
        ChatBILogUtil.error(f"Dialogue state failed: {e}\n{traceback.format_exc()}")
        return {"success": False, "error": str(e)}

@router.get("/recent-chats")
async def get_recent_chats(
    session: SessionDep,
    current_user: CurrentUser,
    limit: int = Query(20, ge=1, le=50, description="返回最近N个会话")
):
    """获取最近的会话列表（用于评估面板下拉选择）"""
    try:
        chats = session.exec(
            select(Chat).where(
                Chat.create_by == current_user.id
            ).order_by(Chat.create_time.desc()).limit(limit)
        ).all()

        result = []
        for chat in chats:
            last_record = session.exec(
                select(ChatRecord).where(
                    ChatRecord.chat_id == chat.id
                ).order_by(ChatRecord.create_time.desc()).limit(1)
            ).first()
            record_count = session.exec(
                select(func.count(ChatRecord.id)).where(ChatRecord.chat_id == chat.id)
            ).one()
            result.append({
                'chat_id': chat.id,
                'brief': chat.brief or (last_record.question[:40] if last_record and last_record.question else f'会话 #{chat.id}'),
                'record_count': record_count or 0,
                'last_question': last_record.question[:60] if last_record and last_record.question else None,
                'create_time': chat.create_time.isoformat() if chat.create_time else None,
            })
        return {"success": True, "chats": result}
    except Exception as e:
        ChatBILogUtil.error(f"Get recent chats failed: {e}")
        return {"success": False, "chats": [], "error": str(e)}


@router.get("/recent-records")
async def get_recent_records(
    session: SessionDep,
    current_user: CurrentUser,
    limit: int = Query(20, ge=1, le=50, description="返回最近N条记录")
):
    """获取最近的聊天记录列表（用于单条评估下拉选择）"""
    try:
        records = session.exec(
            select(ChatRecord).where(
                ChatRecord.create_by == current_user.id,
                ChatRecord.question.isnot(None)
            ).order_by(ChatRecord.create_time.desc()).limit(limit)
        ).all()
        result = []
        for r in records:
            result.append({
                'record_id': r.id,
                'chat_id': r.chat_id,
                'question': (r.question[:60] + '...' if r.question and len(r.question) > 60 else r.question) or f'记录 #{r.id}',
                'has_rag': bool(r.rag_results),
                'has_sql': bool(r.sql),
                'success': bool(r.finish and not r.error),
                'create_time': r.create_time.isoformat() if r.create_time else None,
            })
        return {"success": True, "records": result}
    except Exception as e:
        ChatBILogUtil.error(f"Get recent records failed: {e}")
        return {"success": False, "records": [], "error": str(e)}



@router.get("/evaluation-history")
async def get_evaluation_history(
    session: SessionDep,
    current_user: CurrentUser,
    days: int = Query(7, ge=1, le=90, description="查询最近N天的历史数据")
):
    """
    获取RAG评估质量指标的历史趋势数据

    按日期聚合评估指标（Precision、Recall、MRR、NDCG），
    用于前端质量趋势图展示。
    """
    try:
        start_date = datetime.now() - timedelta(days=days)

        records = session.exec(
            select(ChatRecord).where(
                ChatRecord.create_time >= start_date,
                ChatRecord.create_by == current_user.id,
                ChatRecord.rag_results.isnot(None)
            ).order_by(ChatRecord.create_time.asc())
        ).all()

        # 按日期聚合指标
        daily_metrics: dict[str, list] = defaultdict(list)

        for record in records:
            if not record.rag_results or not record.create_time:
                continue

            try:
                rag_data = json.loads(record.rag_results)
            except (json.JSONDecodeError, TypeError):
                continue

            retrieval_items = []
            for term in rag_data.get('terminologies', []):
                retrieval_items.append({'similarity': term.get('similarity', 0)})
            for ex in rag_data.get('sql_examples', []):
                retrieval_items.append({'similarity': ex.get('similarity', 0)})
            # PDF数据源的主要检索源是文档片段(document_chunks)
            for dc in rag_data.get('document_chunks', []):
                retrieval_items.append({'similarity': dc.get('similarity', 0)})

            if not retrieval_items:
                continue

            metrics = RAGEvaluator.evaluate_retrieval(retrieval_items)
            date_key = record.create_time.strftime('%Y-%m-%d')
            daily_metrics[date_key].append(metrics)

        # 计算每日平均值
        trend_data = []
        for date_key in sorted(daily_metrics.keys()):
            items = daily_metrics[date_key]
            n = len(items)
            # items 是 RetrievalMetrics 数据类实例，使用属性访问
            avg_precision = sum(m.precision_at_k.get(3, 0) for m in items) / n
            avg_recall = sum(m.recall_at_k.get(3, 0) for m in items) / n
            avg_mrr = sum(m.mrr for m in items) / n
            avg_ndcg = sum(m.ndcg for m in items) / n
            avg_similarity = sum(m.avg_similarity for m in items) / n

            trend_data.append({
                'date': date_key,
                'precision': round(avg_precision, 4),
                'recall': round(avg_recall, 4),
                'mrr': round(avg_mrr, 4),
                'ndcg': round(avg_ndcg, 4),
                'avg_similarity': round(avg_similarity, 4),
                'sample_count': n
            })

        return {
            "success": True,
            "trend_data": trend_data,
            "days": days,
            "total_records": sum(d['sample_count'] for d in trend_data)
        }

    except Exception as e:
        ChatBILogUtil.error(f"Evaluation history failed: {e}\n{traceback.format_exc()}")
        return {"success": False, "error": str(e), "trend_data": []}
