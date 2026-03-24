"""
RAG 系统状态 API
用于检测 RAG 系统各组件的运行状态
"""
import time
import traceback
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlmodel import func, select

from apps.ai_model.embedding import EmbeddingModelCache, _embedding_model
from apps.data_training.models.data_training_model import DataTraining
from apps.system.models.system_model import AiModelDetail
from apps.terminology.models.terminology_model import Terminology
from common.core.config import settings
from common.core.deps import SessionDep, CurrentUser
from common.utils.utils import ChatBILogUtil

router = APIRouter(tags=["system/rag-status"], prefix="/system/rag")


class EmbeddingStatusResponse(BaseModel):
    status: str = Field(..., description="Status: 'active' | 'inactive' | 'error'")
    model_name: str = Field(..., description="Embedding model name")
    loaded: bool = Field(..., description="Whether the model is loaded")
    error: Optional[str] = Field(None, description="Error message if any")


class LLMStatusResponse(BaseModel):
    status: str = Field(..., description="Status: 'active' | 'inactive' | 'error'")
    model_name: Optional[str] = Field(None, description="LLM model name")
    latency_ms: Optional[int] = Field(None, description="Response latency in milliseconds")
    error: Optional[str] = Field(None, description="Error message if any")


class StatsResponse(BaseModel):
    count: int = Field(0, description="Total count")
    last_updated: Optional[str] = Field(None, description="Last updated timestamp")
    error: Optional[str] = Field(None, description="Error message if any")


class RAGStatusResponse(BaseModel):
    embedding: EmbeddingStatusResponse
    llm: LLMStatusResponse
    terminology: StatsResponse
    training: StatsResponse



@router.get("/status", response_model=RAGStatusResponse)
async def get_rag_status(session: SessionDep, current_user: CurrentUser):
    """
    获取 RAG 系统状态
    包括：向量嵌入模型状态、LLM 连接状态、术语库统计、知识库统计
    """
    # 验证用户工作空间 ID
    oid = current_user.oid
    if oid is None or oid <= 0:
        ChatBILogUtil.warning(f"Invalid workspace ID for user {current_user.id}, using default oid=1")
        oid = 1
    
    # 1. 检查向量嵌入模型状态
    embedding_status = await check_embedding_status()
    
    # 2. 检查 LLM 状态
    llm_status = await check_llm_status(session)
    
    # 3. 获取术语库统计
    terminology_stats = get_terminology_stats(session, oid)
    
    # 4. 获取知识库统计
    training_stats = get_training_stats(session, oid)
    
    return RAGStatusResponse(
        embedding=embedding_status,
        llm=llm_status,
        terminology=terminology_stats,
        training=training_stats
    )


async def check_embedding_status() -> EmbeddingStatusResponse:
    """检查向量嵌入模型状态"""
    model_name = settings.DEFAULT_EMBEDDING_MODEL
    
    # 如果嵌入功能被禁用，直接返回 inactive
    if not settings.EMBEDDING_ENABLED:
        return EmbeddingStatusResponse(
            status='inactive',
            model_name=model_name,
            loaded=False,
            error='Embedding feature is disabled in configuration'
        )
    
    # 检查模型是否已加载到缓存
    is_loaded = model_name in _embedding_model and _embedding_model[model_name] is not None
    
    # 尝试获取模型实例（如果未加载会自动加载）
    try:
        model = EmbeddingModelCache.get_model()
        if model is not None:
            return EmbeddingStatusResponse(
                status='active',
                model_name=model_name,
                loaded=True,
                error=None
            )
        else:
            return EmbeddingStatusResponse(
                status='inactive',
                model_name=model_name,
                loaded=False,
                error='Model instance is None'
            )
    except Exception as e:
        error_msg = str(e)
        ChatBILogUtil.error(f"Failed to check embedding model: {error_msg}\n{traceback.format_exc()}")
        return EmbeddingStatusResponse(
            status='error',
            model_name=model_name,
            loaded=False,
            error=error_msg[:200]  # 限制错误消息长度
        )


async def check_llm_status(session: SessionDep) -> LLMStatusResponse:
    """检查 LLM 连接状态"""
    start_time = time.time()
    
    try:
        # 获取默认模型
        db_model = session.exec(
            select(AiModelDetail).where(AiModelDetail.default_model == True)
        ).first()
        
        if not db_model:
            return LLMStatusResponse(
                status='inactive',
                model_name=None,
                latency_ms=None,
                error='No default model configured'
            )
        
        # 验证模型配置是否完整
        if not db_model.api_domain:
            return LLMStatusResponse(
                status='inactive',
                model_name=db_model.name,
                latency_ms=None,
                error='Model API endpoint not configured'
            )
        
        # 测量配置检查延迟
        latency_ms = int((time.time() - start_time) * 1000)
        
        return LLMStatusResponse(
            status='active',
            model_name=db_model.name,
            latency_ms=latency_ms,
            error=None
        )
    except Exception as e:
        error_msg = str(e)
        ChatBILogUtil.error(f"Failed to check LLM status: {error_msg}\n{traceback.format_exc()}")
        return LLMStatusResponse(
            status='error',
            model_name=None,
            latency_ms=None,
            error=error_msg[:200]  # 限制错误消息长度
        )


def get_terminology_stats(session: SessionDep, oid: int) -> StatsResponse:
    """获取术语库统计"""
    # 参数验证
    if oid is None or oid <= 0:
        ChatBILogUtil.warning(f"Invalid oid parameter: {oid}")
        return StatsResponse(count=0, last_updated=None, error='Invalid workspace ID')
    
    try:
        # 获取总数 - 只计算父节点（主术语），不包含同义词
        count = session.exec(
            select(func.count(Terminology.id)).where(
                Terminology.oid == oid,
                Terminology.pid.is_(None)  # 只计算父节点
            )
        ).one()
        
        # 获取最近创建时间（作为最近更新时间）- 只看父节点
        latest = session.exec(
            select(Terminology.create_time)
            .where(
                Terminology.oid == oid,
                Terminology.pid.is_(None)  # 只看父节点
            )
            .order_by(Terminology.create_time.desc())
            .limit(1)
        ).first()
        
        last_updated = None
        if latest:
            last_updated = latest.isoformat() if hasattr(latest, 'isoformat') else str(latest)
        
        return StatsResponse(count=count or 0, last_updated=last_updated, error=None)
    except Exception as e:
        error_msg = str(e)
        ChatBILogUtil.error(f"Failed to get terminology stats for oid={oid}: {error_msg}\n{traceback.format_exc()}")
        return StatsResponse(count=0, last_updated=None, error=error_msg[:100])


def get_training_stats(session: SessionDep, oid: int) -> StatsResponse:
    """获取知识库统计"""
    # 参数验证
    if oid is None or oid <= 0:
        ChatBILogUtil.warning(f"Invalid oid parameter: {oid}")
        return StatsResponse(count=0, last_updated=None, error='Invalid workspace ID')
    
    try:
        # 获取总数
        count = session.exec(
            select(func.count(DataTraining.id)).where(DataTraining.oid == oid)
        ).one()
        
        # 获取最近创建时间（作为最近更新时间）
        latest = session.exec(
            select(DataTraining.create_time)
            .where(DataTraining.oid == oid)
            .order_by(DataTraining.create_time.desc())
            .limit(1)
        ).first()
        
        last_updated = None
        if latest:
            last_updated = latest.isoformat() if hasattr(latest, 'isoformat') else str(latest)
        
        return StatsResponse(count=count or 0, last_updated=last_updated, error=None)
    except Exception as e:
        error_msg = str(e)
        ChatBILogUtil.error(f"Failed to get training stats for oid={oid}: {error_msg}\n{traceback.format_exc()}")
        return StatsResponse(count=0, last_updated=None, error=error_msg[:100])

