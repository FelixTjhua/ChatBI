"""ChatBI 自定义 Prompt API（重构版）"""

from typing import Optional, List
from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime

from common.core.deps import SessionDep, CurrentUser
from common.chatbi.custom_prompt import PromptSQL, PromptAnalysis, PromptForecast
from common.utils.utils import ChatBILogUtil
from apps.datasource.models.datasource import CoreDatasource
from sqlmodel import select, func

router = APIRouter(tags=["system/custom_prompt"], prefix="/system/custom_prompt")


def _get_model(prompt_type: str):
    """根据类型返回对应的模型类"""
    mapping = {
        'GENERATE_SQL': PromptSQL,
        'ANALYSIS': PromptAnalysis,
        'PREDICT_DATA': PromptForecast,
    }
    return mapping.get(prompt_type, PromptSQL)


class CustomPromptCreate(BaseModel):
    name: str
    type: str = "GENERATE_SQL"
    prompt: str
    specific_ds: bool = False
    datasource_ids: Optional[List[int]] = None
    always_inject: bool = False


class CustomPromptUpdate(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    type: Optional[str] = None
    prompt: Optional[str] = None
    specific_ds: Optional[bool] = None
    datasource_ids: Optional[List[int]] = None
    always_inject: Optional[bool] = None


def get_datasource_names(session, datasource_ids: List[int]) -> List[str]:
    if not datasource_ids:
        return []
    try:
        stmt = select(CoreDatasource).where(CoreDatasource.id.in_(datasource_ids))
        datasources = session.exec(stmt).all()
        return [ds.name for ds in datasources if ds.name]
    except Exception:
        return []


@router.get("/{prompt_type}/page/{page}/{size}")
async def get_prompts_page(
    session: SessionDep,
    current_user: CurrentUser,
    prompt_type: str,
    page: int = 1,
    size: int = 10,
    name: Optional[str] = None
):
    """分页获取自定义 Prompt"""
    try:
        Model = _get_model(prompt_type)
        stmt = select(Model).where(Model.oid == current_user.oid)
        if name:
            stmt = stmt.where(Model.name.contains(name))
        
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = session.exec(count_stmt).one()
        
        offset = (page - 1) * size
        stmt = stmt.offset(offset).limit(size).order_by(Model.id.desc())
        items = session.exec(stmt).all()
        
        data = []
        for item in items:
            ds_ids = item.datasource_ids or []
            ds_names = get_datasource_names(session, ds_ids) if ds_ids else []
            data.append({
                "id": item.id,
                "name": item.name,
                "type": prompt_type,
                "prompt": item.prompt,
                "specific_ds": item.specific_ds or False,
                "datasource_ids": ds_ids,
                "datasource_names": ds_names,
                "always_inject": item.always_inject or False,
                "create_time": item.create_time.timestamp() * 1000 if item.create_time else None,
            })
        
        return {"total_count": total, "data": data}
    except Exception as e:
        ChatBILogUtil.error(f"Error in get_prompts_page: {e}")
        return {"total_count": 0, "data": []}


@router.get("/{prompt_type}")
async def get_prompts(session: SessionDep, current_user: CurrentUser, prompt_type: str):
    try:
        Model = _get_model(prompt_type)
        stmt = select(Model).where(Model.oid == current_user.oid)
        items = session.exec(stmt).all()
        return [
            {
                "id": item.id, "name": item.name, "type": prompt_type,
                "prompt": item.prompt, "specific_ds": item.specific_ds,
                "datasource_ids": item.datasource_ids or [],
                "always_inject": item.always_inject or False,
            }
            for item in items
        ]
    except Exception:
        return []


@router.get("/{prompt_type}/export")
async def export_prompts(session: SessionDep, current_user: CurrentUser, prompt_type: str, name: Optional[str] = None):
    import io, pandas as pd
    from fastapi.responses import StreamingResponse
    try:
        Model = _get_model(prompt_type)
        stmt = select(Model).where(Model.oid == current_user.oid)
        if name:
            stmt = stmt.where(Model.name.contains(name))
        items = session.exec(stmt).all()
        data = []
        for item in items:
            ds_ids = item.datasource_ids or []
            ds_names = get_datasource_names(session, ds_ids) if ds_ids else []
            data.append({
                "名称": item.name, "提示词内容": item.prompt,
                "应用范围": "指定数据源" if item.specific_ds else "所有数据源",
                "数据源": ", ".join(ds_names) if ds_names else "-",
                "创建时间": item.create_time.strftime("%Y-%m-%d %H:%M:%S") if item.create_time else "-",
            })
        df = pd.DataFrame(data)
        output = io.BytesIO()
        df.to_excel(output, index=False, engine='openpyxl')
        output.seek(0)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''prompts_{prompt_type}.xlsx"}
        )
    except Exception as e:
        ChatBILogUtil.error(f"Error exporting prompts: {e}")
        return []


@router.get("/detail/{prompt_id}")
async def get_prompt_detail(
    session: SessionDep, current_user: CurrentUser,
    prompt_id: int, prompt_type: Optional[str] = None
):
    """获取 Prompt 详情
    
     三张表使用独立自增 ID，仅凭 prompt_id 可能匹配到错误的表。
    新增 prompt_type 查询参数消歧：指定时直接查对应表，未指定时回退遍历（兼容旧前端）。
    """
    # 优先使用 prompt_type 精确查询
    if prompt_type:
        Model = _get_model(prompt_type)
        try:
            prompt = session.get(Model, prompt_id)
            if prompt and prompt.oid == current_user.oid:
                ds_ids = prompt.datasource_ids or []
                ds_names = get_datasource_names(session, ds_ids) if ds_ids else []
                return {
                    "id": prompt.id, "name": prompt.name, "type": prompt_type,
                    "prompt": prompt.prompt, "specific_ds": prompt.specific_ds or False,
                    "datasource_ids": ds_ids, "datasource_names": ds_names,
                    "always_inject": prompt.always_inject or False,
                    "create_time": prompt.create_time.timestamp() * 1000 if prompt.create_time else None,
                }
        except Exception as e:
            ChatBILogUtil.debug(f"Custom prompt lookup failed for id={prompt_id}, type={prompt_type}: {e}")
        return None

    # 回退：遍历三张表（兼容旧前端，但存在 ID 冲突风险）
    for Model, ptype in [(PromptSQL, 'GENERATE_SQL'), (PromptAnalysis, 'ANALYSIS'), (PromptForecast, 'PREDICT_DATA')]:
        try:
            prompt = session.get(Model, prompt_id)
            if prompt and prompt.oid == current_user.oid:
                ds_ids = prompt.datasource_ids or []
                ds_names = get_datasource_names(session, ds_ids) if ds_ids else []
                return {
                    "id": prompt.id, "name": prompt.name, "type": ptype,
                    "prompt": prompt.prompt, "specific_ds": prompt.specific_ds or False,
                    "datasource_ids": ds_ids, "datasource_names": ds_names,
                    "always_inject": prompt.always_inject or False,
                    "create_time": prompt.create_time.timestamp() * 1000 if prompt.create_time else None,
                }
        except Exception:
            continue
    return None


@router.post("")
async def create_prompt(session: SessionDep, current_user: CurrentUser, data: CustomPromptCreate):
    Model = _get_model(data.type)
    prompt = Model(
        name=data.name, prompt=data.prompt,
        specific_ds=data.specific_ds, datasource_ids=data.datasource_ids,
        always_inject=data.always_inject, oid=current_user.oid,
        create_time=datetime.now()
    )
    session.add(prompt)
    session.commit()
    session.refresh(prompt)
    return {"id": prompt.id, "message": "创建成功"}


@router.put("")
async def update_prompt(session: SessionDep, current_user: CurrentUser, data: CustomPromptUpdate):
    if not data.id:
        Model = _get_model(data.type or 'GENERATE_SQL')
        prompt = Model(
            name=data.name, prompt=data.prompt,
            specific_ds=data.specific_ds, datasource_ids=data.datasource_ids,
            always_inject=data.always_inject if data.always_inject is not None else False,
            oid=current_user.oid, create_time=datetime.now()
        )
        session.add(prompt)
        session.commit()
        session.refresh(prompt)
        return {"id": prompt.id, "message": "创建成功"}
    
    # 优先使用 data.type 精确定位表，避免跨表 ID 冲突
    prompt = None
    if data.type:
        Model = _get_model(data.type)
        prompt = session.get(Model, data.id)
        if prompt and prompt.oid != current_user.oid:
            prompt = None
    
    # 回退：遍历三张表（兼容旧前端）
    if not prompt:
        for Model in [PromptSQL, PromptAnalysis, PromptForecast]:
            prompt = session.get(Model, data.id)
            if prompt and prompt.oid == current_user.oid:
                break
            prompt = None
    
    if not prompt:
        return {"error": "Prompt not found"}
    
    if data.name is not None: prompt.name = data.name
    if data.prompt is not None: prompt.prompt = data.prompt
    if data.specific_ds is not None: prompt.specific_ds = data.specific_ds
    if data.datasource_ids is not None: prompt.datasource_ids = data.datasource_ids
    if data.always_inject is not None: prompt.always_inject = data.always_inject
    
    session.add(prompt)
    session.commit()
    return {"message": "更新成功"}


@router.delete("/{prompt_id}")
async def delete_prompt(
    session: SessionDep, current_user: CurrentUser,
    prompt_id: int, prompt_type: Optional[str] = None
):
    """删除 Prompt
    
     新增 prompt_type 查询参数，精确定位目标表，避免跨表 ID 冲突误删。
    """
    # 优先使用 prompt_type 精确查询
    if prompt_type:
        Model = _get_model(prompt_type)
        prompt = session.get(Model, prompt_id)
        if prompt and prompt.oid == current_user.oid:
            session.delete(prompt)
            session.commit()
            return {"message": "删除成功"}
        return {"message": "删除成功"}

    # 回退：遍历三张表
    for Model in [PromptSQL, PromptAnalysis, PromptForecast]:
        prompt = session.get(Model, prompt_id)
        if prompt and prompt.oid == current_user.oid:
            session.delete(prompt)
            session.commit()
            return {"message": "删除成功"}
    return {"message": "删除成功"}


@router.delete("")
async def delete_prompts_batch(session: SessionDep, current_user: CurrentUser, ids: List[int]):
    try:
        for prompt_id in ids:
            for Model in [PromptSQL, PromptAnalysis, PromptForecast]:
                prompt = session.get(Model, prompt_id)
                if prompt and prompt.oid == current_user.oid:
                    session.delete(prompt)
                    break
        session.commit()
        return {"message": "删除成功"}
    except Exception as e:
        ChatBILogUtil.error(f"Error in delete_prompts_batch: {e}")
        return {"error": str(e)}


class BatchDeleteRequest(BaseModel):
    ids: List[int]
    prompt_type: Optional[str] = None


@router.post("/batch_delete")
async def delete_prompts_batch_post(session: SessionDep, current_user: CurrentUser, data: BatchDeleteRequest):
    """ POST 方式的批量删除（替代 DELETE + body）
    
    部分代理/网关会剥离 DELETE 请求体，导致后端收到空数组。
    前端改用 POST /batch_delete 发送批量删除请求。
    """
    try:
        for prompt_id in data.ids:
            if data.prompt_type:
                Model = _get_model(data.prompt_type)
                prompt = session.get(Model, prompt_id)
                if prompt and prompt.oid == current_user.oid:
                    session.delete(prompt)
                    continue
            # 回退：遍历三张表
            for Model in [PromptSQL, PromptAnalysis, PromptForecast]:
                prompt = session.get(Model, prompt_id)
                if prompt and prompt.oid == current_user.oid:
                    session.delete(prompt)
                    break
        session.commit()
        return {"message": "删除成功"}
    except Exception as e:
        ChatBILogUtil.error(f"Error in delete_prompts_batch_post: {e}")
        return {"error": str(e)}
