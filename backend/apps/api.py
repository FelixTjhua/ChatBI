from fastapi import APIRouter

from apps.chat.api import chat
from apps.dashboard.api import dashboard_api
from apps.dashboard.api import analytics_api
from apps.data_training.api import data_training
from apps.datasource.api import datasource, table_relation, ds_permission
from apps.mcp import mcp
from apps.system.api import login, user, aimodel, appearance, rag_status, custom_prompt, rag_test, rag_evaluation, workspace
from apps.terminology.api import terminology
from common.audit.api import audit_api

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(user.router)
api_router.include_router(appearance.router)
api_router.include_router(rag_status.router)
api_router.include_router(aimodel.router)
api_router.include_router(terminology.router)
api_router.include_router(data_training.router)
api_router.include_router(datasource.router)
api_router.include_router(ds_permission.router)
api_router.include_router(chat.router)
api_router.include_router(dashboard_api.router)
api_router.include_router(analytics_api.router)
api_router.include_router(mcp.router)
api_router.include_router(table_relation.router)
api_router.include_router(custom_prompt.router)
api_router.include_router(rag_test.router)
api_router.include_router(audit_api.router)
api_router.include_router(rag_evaluation.router)
api_router.include_router(workspace.router)
