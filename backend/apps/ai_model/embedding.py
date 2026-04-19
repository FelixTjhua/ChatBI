import os.path
import threading
from typing import Optional

from langchain_core.embeddings import Embeddings
from langchain_huggingface import HuggingFaceEmbeddings
from pydantic import BaseModel

from common.core.config import settings

os.environ["TOKENIZERS_PARALLELISM"] = "false"


class EmbeddingModelInfo(BaseModel):
    folder: str
    name: str
    device: str = 'cpu'


local_embedding_model = EmbeddingModelInfo(folder=settings.LOCAL_MODEL_PATH,
                                           name=os.path.join(settings.LOCAL_MODEL_PATH, 'embedding',
                                                             "BAAI_bge-base-zh-v1.5"))

_lock = threading.Lock()
locks = {}

_embedding_model: dict[str, Optional[Embeddings]] = {}


class _InstructionEmbeddingsWrapper(Embeddings):
    """Wrapper that prepends a query instruction prefix for BGE-style models."""
    # Pydantic v2: 允许任意类型的字段（Embeddings 实例不是标准 JSON 类型）
    model_config = {"arbitrary_types_allowed": True}

    _base: Embeddings
    _query_instruction: str

    def __init__(self, base: Embeddings, query_instruction: str = ""):
        # 调用 super().__init__() 初始化 Pydantic BaseModel，
        # 然后通过 object.__setattr__ 设置私有属性（Pydantic v2 不允许直接赋值未声明字段）
        super().__init__()
        object.__setattr__(self, '_base', base)
        object.__setattr__(self, '_query_instruction', query_instruction)

    def embed_query(self, text: str) -> list[float]:
        if self._query_instruction:
            text = self._query_instruction + text
        return self._base.embed_query(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._base.embed_documents(texts)


class EmbeddingModelCache:

    # 本地目录名 → HuggingFace Hub 模型 ID 的映射
    _LOCAL_TO_HUB: dict[str, str] = {
        "BAAI_bge-base-zh-v1.5": "BAAI/bge-base-zh-v1.5",
    }

    @staticmethod
    def _new_instance(config: EmbeddingModelInfo = local_embedding_model):
        import logging
        logger = logging.getLogger(__name__)

        model_name = config.name
        cache_folder = config.folder

        if not os.path.exists(model_name):
            # 本地直接路径不存在，尝试查找 HuggingFace 缓存格式
            # HuggingFace Hub 下载的模型存储在 models--{org}--{name}/snapshots/{hash}/ 下
            basename = os.path.basename(model_name)
            parent_dir = os.path.dirname(model_name) or config.folder
            hf_cache_dir = os.path.join(parent_dir, f"models--{basename.replace('_', '--', 1)}")
            snapshots_dir = os.path.join(hf_cache_dir, "snapshots")

            _found_local = False
            if os.path.isdir(snapshots_dir):
                # 取最新的 snapshot（按修改时间排序）
                try:
                    snaps = sorted(
                        [d for d in os.listdir(snapshots_dir)
                         if os.path.isdir(os.path.join(snapshots_dir, d))],
                        key=lambda d: os.path.getmtime(os.path.join(snapshots_dir, d)),
                        reverse=True
                    )
                    if snaps:
                        resolved = os.path.join(snapshots_dir, snaps[0])
                        # 验证 snapshot 目录包含模型文件
                        if os.path.exists(os.path.join(resolved, "config.json")):
                            logger.info(
                                f"本地模型路径不存在: {model_name}，"
                                f"但在 HuggingFace 缓存中找到: {resolved}"
                            )
                            model_name = resolved
                            _found_local = True
                except Exception as e:
                    logger.warning(f"扫描 HuggingFace 缓存目录失败: {e}")

            if not _found_local:
                # 缓存中也没有，回退到在线下载
                hub_id = EmbeddingModelCache._LOCAL_TO_HUB.get(basename, basename.replace("_", "/", 1))
                logger.info(
                    f"本地模型路径不存在: {model_name}，将从 HuggingFace Hub 下载: {hub_id}"
                )
                model_name = hub_id
                # cache_folder 指向 embedding 子目录，确保目录存在
                cache_folder = parent_dir
                os.makedirs(cache_folder, exist_ok=True)

        base = HuggingFaceEmbeddings(
            model_name=model_name,
            cache_folder=cache_folder,
            model_kwargs={'device': config.device},
            encode_kwargs={'normalize_embeddings': True},
        )
        # BGE 模型推荐在查询时添加指令前缀以提升检索质量
        query_instruction = ""
        if "bge" in config.name.lower():
            query_instruction = "为这个句子生成表示以用于检索相关文章："
        if query_instruction:
            return _InstructionEmbeddingsWrapper(base, query_instruction)
        return base

    @staticmethod
    def _get_lock(key: str = settings.DEFAULT_EMBEDDING_MODEL):
        lock = locks.get(key)
        if lock is None:
            with _lock:
                lock = locks.get(key)
                if lock is None:
                    lock = threading.Lock()
                    locks[key] = lock

        return lock

    @staticmethod
    def get_model(key: str = settings.DEFAULT_EMBEDDING_MODEL,
                  config: EmbeddingModelInfo = local_embedding_model) -> Embeddings:
        """获取嵌入模型实例（支持按 key 缓存多个模型）
        
        默认使用 BAAI/bge-base-zh-v1.5 中英双语模型（768维），
        同时支持中文和英文语义检索。
        """
        model_instance = _embedding_model.get(key)
        if model_instance is None:
            lock = EmbeddingModelCache._get_lock(key)
            with lock:
                model_instance = _embedding_model.get(key)
                if model_instance is None:
                    model_instance = EmbeddingModelCache._new_instance(config)
                    _embedding_model[key] = model_instance

        return model_instance

    @staticmethod
    def get_model_for_datasource(ds_type: str = 'database', language: str = 'zh') -> Embeddings:
        """按数据源类型和语言获取合适的 embedding 模型"""
        # BAAI/bge-base-zh-v1.5 原生支持中英双语，统一使用同一模型
        return EmbeddingModelCache.get_model()

    @staticmethod
    def invalidate_model(key: str = None):
        """模型热更新时清除缓存的模型实例和查询向量缓存"""
        with _lock:
            if key is None:
                _embedding_model.clear()
                locks.clear()
            elif key in _embedding_model:
                del _embedding_model[key]
                locks.pop(key, None)
        # 同时清除文档检索的查询向量缓存（避免旧模型向量与新模型文档向量不匹配）
        try:
            from apps.datasource.document_retrieval import _embed_cache
            _embed_cache.clear()
        except (ImportError, AttributeError):
            pass
