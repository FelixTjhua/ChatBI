"""ChatBI 自定义 Prompt 模块（重构版）"""

import logging
from enum import Enum
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime

from sqlmodel import SQLModel, Field, select, Column, func
from sqlalchemy.dialects.postgresql import JSONB


logger = logging.getLogger('chatbi')


class CustomPromptTypeEnum(str, Enum):
    GENERATE_SQL = "GENERATE_SQL"
    ANALYSIS = "ANALYSIS"
    PREDICT_DATA = "PREDICT_DATA"


# ========== 三张提示词表模型 ==========

class PromptSQL(SQLModel, table=True):
    __tablename__ = "prompt_business_sql"
    id: Optional[int] = Field(default=None, primary_key=True)
    oid: Optional[int] = Field(default=1)
    name: Optional[str] = Field(default="")
    prompt: Optional[str] = Field(default="")
    specific_ds: Optional[bool] = Field(default=False)
    datasource_ids: Optional[List[int]] = Field(default=None, sa_column=Column(JSONB))
    always_inject: Optional[bool] = Field(default=False)
    create_time: Optional[datetime] = Field(default=None)


class PromptAnalysis(SQLModel, table=True):
    __tablename__ = "prompt_business_analysis"
    id: Optional[int] = Field(default=None, primary_key=True)
    oid: Optional[int] = Field(default=1)
    name: Optional[str] = Field(default="")
    prompt: Optional[str] = Field(default="")
    specific_ds: Optional[bool] = Field(default=False)
    datasource_ids: Optional[List[int]] = Field(default=None, sa_column=Column(JSONB))
    always_inject: Optional[bool] = Field(default=False)
    create_time: Optional[datetime] = Field(default=None)


class PromptForecast(SQLModel, table=True):
    __tablename__ = "prompt_business_forecast"
    id: Optional[int] = Field(default=None, primary_key=True)
    oid: Optional[int] = Field(default=1)
    name: Optional[str] = Field(default="")
    prompt: Optional[str] = Field(default="")
    specific_ds: Optional[bool] = Field(default=False)
    datasource_ids: Optional[List[int]] = Field(default=None, sa_column=Column(JSONB))
    always_inject: Optional[bool] = Field(default=False)
    create_time: Optional[datetime] = Field(default=None)



# ========== 类型 → 模型映射 ==========

_TYPE_MODEL_MAP = {
    CustomPromptTypeEnum.GENERATE_SQL: PromptSQL,
    CustomPromptTypeEnum.ANALYSIS: PromptAnalysis,
    CustomPromptTypeEnum.PREDICT_DATA: PromptForecast,
}


def _get_model(prompt_type: CustomPromptTypeEnum):
    """根据类型返回对应的 ORM 模型类"""
    return _TYPE_MODEL_MAP.get(prompt_type, PromptSQL)


# ========== 对外接口函数 ==========

def count_custom_prompts(
    session: Any,
    prompt_type: CustomPromptTypeEnum,
    oid: int,
    ds_id: Optional[int] = None,
) -> int:
    """统计指定类型的自定义提示词总数。"""
    try:
        Model = _get_model(prompt_type)
        stmt = select(func.count()).select_from(Model).where(Model.oid == oid)
        total = session.exec(stmt).one()
        return total or 0
    except Exception as e:
        logger.error(f"count_custom_prompts failed: {e}")
        return 0


def find_custom_prompts(
    session: Any,
    prompt_type: CustomPromptTypeEnum,
    oid: int,
    ds_id: Optional[int] = None,
) -> str:
    """查找并拼接所有匹配的自定义提示词内容（不做相关性筛选）。"""
    try:
        Model = _get_model(prompt_type)
        stmt = select(Model).where(Model.oid == oid)
        prompts = session.exec(stmt).all()

        if not prompts:
            return ""

        parts = []
        for p in prompts:
            # 数据源过滤逻辑
            if p.specific_ds:
                if not ds_id:
                    continue  # 无数据源上下文，跳过限定了特定数据源的提示词
                if p.datasource_ids and ds_id not in p.datasource_ids:
                    continue
            if p.prompt:
                parts.append(p.prompt)

        return "\n".join(parts)
    except Exception as e:
        logger.error(f"find_custom_prompts failed: {e}")
        return ""


def find_relevant_custom_prompts(
    session: Any,
    prompt_type: CustomPromptTypeEnum,
    oid: int,
    question: str,
    ds_id: Optional[int] = None,
) -> Tuple[str, List[Dict]]:
    """全量注入自定义提示词（v4：对齐原版 SQLBot 行为）。"""
    try:
        Model = _get_model(prompt_type)
        stmt = select(Model).where(Model.oid == oid)
        prompts = session.exec(stmt).all()

        if not prompts:
            logger.info(f"[custom_prompt] type={prompt_type.value}, oid={oid}: 数据库中无提示词")
            return "", []

        matched_parts = []
        details = []
        # token 预算上限（字符数）
        MAX_INJECT_CHARS = 5000
        inject_chars = 0

        logger.info(f"[custom_prompt] ===== 全量注入开始 =====")
        logger.info(f"[custom_prompt] type={prompt_type.value}, 问题='{question[:80]}', "
                     f"共{len(prompts)}条提示词")

        for p in prompts:
            # 数据源过滤逻辑
            if p.specific_ds:
                if not ds_id:
                    logger.info(f"[custom_prompt]   [{p.id}] '{p.name}' → 跳过(限定数据源但当前无数据源上下文)")
                    details.append({
                        'id': p.id,
                        'name': p.name or '',
                        'reason': 'not_matched',
                        'detail': '限定数据源但当前无数据源上下文',
                        'score': 0,
                    })
                    continue
                if p.datasource_ids and ds_id not in p.datasource_ids:
                    logger.info(f"[custom_prompt]   [{p.id}] '{p.name}' → 跳过(数据源不匹配)")
                    details.append({
                        'id': p.id,
                        'name': p.name or '',
                        'reason': 'not_matched',
                        'detail': '数据源不匹配',
                        'score': 0,
                    })
                    continue

            # 全量注入（token 预算检查）
            prompt_text = p.prompt or ''
            if inject_chars + len(prompt_text) > MAX_INJECT_CHARS:
                logger.info(
                    f"[custom_prompt]   [{p.id}] '{p.name}' → ⚠️ 跳过(注入预算已满: "
                    f"{inject_chars}/{MAX_INJECT_CHARS})"
                )
                details.append({
                    'id': p.id,
                    'name': p.name or '',
                    'reason': 'budget_exceeded',
                    'detail': f'注入预算已满({inject_chars}/{MAX_INJECT_CHARS}字符)',
                    'score': 0.8,
                })
                continue

            matched_parts.append(prompt_text)
            inject_chars += len(prompt_text)
            logger.info(f"[custom_prompt]   [{p.id}] '{p.name}' → 全量注入")
            details.append({
                'id': p.id,
                'name': p.name or '',
                'reason': 'intent_inject',
                'detail': '全量注入',
                'score': 1.0,
            })

        content = "\n".join(matched_parts) if matched_parts else ""
        injected_count = len([d for d in details if d['reason'] == 'intent_inject'])
        budget_count = len([d for d in details if d['reason'] == 'budget_exceeded'])
        logger.info(f"[custom_prompt] ===== 注入结果: {injected_count}/{len(prompts)}条注入"
                     f"{f', {budget_count}条预算超限' if budget_count else ''}"
                     f", 内容长度={len(content)} =====")
        return content, details

    except Exception as e:
        logger.error(f"find_relevant_custom_prompts failed: {e}")
        return "", []
