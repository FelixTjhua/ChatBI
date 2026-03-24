import os

from alembic.config import Config
from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from fastapi_mcp import FastApiMCP
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from alembic import command
from apps.api import api_router
from common.utils.embedding_threads import fill_empty_table_and_ds_embeddings
from apps.system.crud.aimodel_manage import async_model_info
from apps.system.crud.assistant import init_dynamic_cors
from apps.system.middleware.auth import TokenMiddleware
from common.core.config import settings
from common.core.response_middleware import ResponseMiddleware, exception_handler
from common.core.chatbi_cache import init_chatbi_cache
from common.utils.embedding_threads import fill_empty_terminology_embeddings, fill_empty_data_training_embeddings
from common.utils.utils import ChatBILogUtil


def run_migrations():
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")


def init_terminology_embedding_data():
    fill_empty_terminology_embeddings()


def init_data_training_embedding_data():
    fill_empty_data_training_embeddings()


def init_table_and_ds_embedding():
    fill_empty_table_and_ds_embeddings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    init_chatbi_cache()
    init_dynamic_cors(app)
    # 在后台线程中初始化embedding数据，避免阻塞应用启动
    import threading
    def _init_embeddings():
        try:
            init_terminology_embedding_data()
            init_data_training_embedding_data()
            init_table_and_ds_embedding()
            ChatBILogUtil.info("Embedding数据初始化完成")
        except Exception as e:
            ChatBILogUtil.error(f"Embedding数据初始化失败: {e}")
    
    embedding_thread = threading.Thread(target=_init_embeddings, daemon=True)
    embedding_thread.start()
    ChatBILogUtil.info("ChatBI 初始化完成（Embedding数据正在后台加载）")
    await async_model_info()  # 异步加密已有模型的密钥和地址
    yield
    ChatBILogUtil.info("ChatBI 应用关闭")


def custom_generate_unique_id(route: APIRoute) -> str:
    tag = route.tags[0] if route.tags and len(route.tags) > 0 else ""
    return f"{tag}-{route.name}"


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan
)

mcp_app = FastAPI()
# mcp server, images path
images_path = settings.MCP_IMAGE_PATH
os.makedirs(images_path, exist_ok=True)
mcp_app.mount("/images", StaticFiles(directory=images_path), name="images")

mcp = FastApiMCP(
    app,
    name="ChatBI MCP Server",
    description="ChatBI MCP Server",
    describe_all_responses=True,
    describe_full_response_schema=True,
    include_operations=["get_datasource_list", "get_model_list", "mcp_question", "mcp_start", "mcp_assistant"]
)

mcp.mount(mcp_app)

# Set all CORS enabled origins
if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.add_middleware(TokenMiddleware)
app.add_middleware(ResponseMiddleware)

# 新增：API请求频率限制，防止恶意用户消耗LLM API配额
from common.middleware.rate_limiter import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware, llm_rate=10, api_rate=60, window=60)

app.include_router(api_router, prefix=settings.API_V1_STR)

# Register exception handlers
app.add_exception_handler(StarletteHTTPException, exception_handler.http_exception_handler)
app.add_exception_handler(Exception, exception_handler.global_exception_handler)

mcp.setup_server()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_delay=3,
        reload_excludes=["*.pyc", ".git/*", "__pycache__/*", ".hypothesis/*", "alembic/*"],
    )
    # uvicorn.run("main:mcp_app", host="0.0.0.0", port=8001) # mcp server
