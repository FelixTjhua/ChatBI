import json
from typing import List, Union

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from apps.ai_model.model_factory import LLMConfig, LLMFactory
from apps.system.schemas.ai_model_schema import AiModelConfigItem, AiModelCreator, AiModelEditor, AiModelGridItem
from fastapi import APIRouter, Query
from sqlmodel import func, select, update

from apps.system.models.system_model import AiModelDetail
from common.core.deps import CurrentUser, SessionDep, Trans
from common.utils.crypto import chatbi_decrypt
from common.utils.time import get_timestamp
from common.utils.utils import ChatBILogUtil, prepare_model_arg

router = APIRouter(tags=["system/aimodel"], prefix="/system/aimodel")

@router.post("/status")
async def check_llm(info: AiModelCreator, trans: Trans, current_user: CurrentUser):
    async def generate():
        try:
            additional_params = {item.key: prepare_model_arg(item.val) for item in info.config_list if item.key and item.val}
            config = LLMConfig(
                model_type="openai" if info.protocol == 1 else "vllm",
                model_name=info.base_model,
                api_key=info.api_key,
                api_base_url=info.api_domain,
                additional_params=additional_params,
            )
            llm_instance = LLMFactory.create_llm(config)
            async for chunk in llm_instance.llm.astream("1+1=?"):
                ChatBILogUtil.info(chunk)
                if chunk and isinstance(chunk, str):
                    yield json.dumps({"content": chunk}) + "\n"
                if chunk and isinstance(chunk, dict) and chunk.content:
                    yield json.dumps({"content": chunk.content}) + "\n"
        
        except Exception as e:
            ChatBILogUtil.error(f"Error checking LLM: {e}")
            error_msg = trans('i18n_llm.validate_error', msg=str(e))
            yield json.dumps({"error": error_msg}) + "\n"
    
    return StreamingResponse(generate(), media_type="application/x-ndjson")

@router.get("/default")
async def check_default(session: SessionDep, trans: Trans):
    db_model = session.exec(
        select(AiModelDetail).where(AiModelDetail.default_model == True)
    ).first()
    if not db_model:
        raise HTTPException(status_code=400, detail=trans('i18n_llm.miss_default'))
    # 添加返回值，避免 FastAPI 返回 null
    return {"id": db_model.id, "name": db_model.name}
    
@router.put("/default/{id}")
async def set_default(session: SessionDep, id: int, current_user: CurrentUser):
    # 添加管理员权限检查，AI模型配置属于系统管理功能
    if not current_user.isAdmin:
        raise HTTPException(status_code=403, detail="Only admin can change default model")
    db_model = session.get(AiModelDetail, id)
    if not db_model:
        raise HTTPException(status_code=404, detail=f"AiModelDetail with id {id} not found")
    if db_model.default_model:
        return

    try:
        session.exec(
            update(AiModelDetail).values(default_model=False)
        )
        db_model.default_model = True
        session.add(db_model)
        session.commit()
    except Exception as e:
        session.rollback()
        raise e

@router.get("", response_model=list[AiModelGridItem])
async def query(
        session: SessionDep,
        keyword: Union[str, None] = Query(default=None, max_length=255)
):
    statement = select(AiModelDetail.id, 
                       AiModelDetail.name, 
                       AiModelDetail.model_type, 
                       AiModelDetail.base_model, 
                       AiModelDetail.supplier,
                       AiModelDetail.protocol, 
                       AiModelDetail.default_model)
    if keyword is not None:
        # 转义 LIKE 通配符，防止用户输入 % 或 _ 改变查询语义
        safe_keyword = keyword.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        statement = statement.where(AiModelDetail.name.like(f"%{safe_keyword}%"))
    statement = statement.order_by(AiModelDetail.default_model.desc(), AiModelDetail.name, AiModelDetail.create_time)
    items = session.exec(statement).all()
    return items

@router.get("/{id}", response_model=AiModelEditor)
async def get_model_by_id(
        session: SessionDep,
        id: int
):
    db_model = session.get(AiModelDetail, id)
    if not db_model:
        raise HTTPException(status_code=404, detail=f"AiModelDetail with id {id} not found")

    config_list: List[AiModelConfigItem] = []
    if db_model.config:
        try:
            raw = json.loads(db_model.config)
            config_list = [AiModelConfigItem(**item) for item in raw]
        except Exception as e:
            from common.utils.utils import ChatBILogUtil
            ChatBILogUtil.warning(f"Failed to parse AI model config: {e}")
    if db_model.api_key:
        db_model.api_key = await chatbi_decrypt(db_model.api_key)
    if db_model.api_domain:
        db_model.api_domain = await chatbi_decrypt(db_model.api_domain)
    data = AiModelDetail.model_validate(db_model).model_dump(exclude_unset=True)
    data.pop("config", None)
    data["config_list"] = config_list
    return AiModelEditor(**data)

@router.post("")
async def add_model(
        session: SessionDep,
        creator: AiModelCreator,
        current_user: CurrentUser
):
    # 添加管理员权限检查
    if not current_user.isAdmin:
        raise HTTPException(status_code=403, detail="Only admin can add AI models")
    data = creator.model_dump(exclude_unset=True)
    data["config"] = json.dumps([item.model_dump(exclude_unset=True) for item in creator.config_list])
    data.pop("config_list", None)
    detail = AiModelDetail.model_validate(data)
    detail.create_time = get_timestamp()
    count = session.exec(select(func.count(AiModelDetail.id))).one()
    if count == 0:
        detail.default_model = True
    session.add(detail)
    session.commit()

@router.put("")
async def update_model(
        session: SessionDep,
        editor: AiModelEditor,
        current_user: CurrentUser
):
    # 添加管理员权限检查
    if not current_user.isAdmin:
        raise HTTPException(status_code=403, detail="Only admin can update AI models")
    id = int(editor.id)
    data = editor.model_dump(exclude_unset=True)
    data["config"] = json.dumps([item.model_dump(exclude_unset=True) for item in editor.config_list])
    data.pop("config_list", None)
    db_model = session.get(AiModelDetail, id)
    # 添加空值检查，防止 NoneType.sqlmodel_update() 崩溃
    if not db_model:
        raise HTTPException(status_code=404, detail=f"AiModelDetail with id {id} not found")
    db_model.sqlmodel_update(data)
    session.add(db_model)
    session.commit()

@router.delete("/{id}")
async def delete_model(
        session: SessionDep,
        trans: Trans,
        id: int,
        current_user: CurrentUser
):
    # 添加管理员权限检查
    if not current_user.isAdmin:
        raise HTTPException(status_code=403, detail="Only admin can delete AI models")
    item = session.get(AiModelDetail, id)
    # 添加空值检查
    if not item:
        raise HTTPException(status_code=404, detail=f"AiModelDetail with id {id} not found")
    if item.default_model:
        raise HTTPException(status_code=400, detail=trans('i18n_llm.delete_default_error', key = item.name))
    session.delete(item)
    session.commit()
    

    