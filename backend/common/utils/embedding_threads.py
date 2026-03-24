import atexit
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List

from sqlalchemy.orm import sessionmaker, scoped_session

executor = ThreadPoolExecutor(max_workers=50)
# 注册 atexit 钩子，确保进程退出时线程池被正确关闭
atexit.register(executor.shutdown, wait=False)

from common.core.db import engine

session_maker = scoped_session(sessionmaker(bind=engine))


def _retry_save_embeddings(save_fn, session_maker_ref, ids: List[int], max_retries: int = 2):
    """ embedding 生成失败时自动重试
    
    create_terminology/create_training 在 commit 后异步生成 embedding，
    如果首次失败（模型加载慢、临时网络问题等），embedding 字段保持 NULL，
    直到下次 fill_empty_embeddings 定时任务才能补偿。
    添加重试机制减少 NULL embedding 的窗口期。
    """
    for attempt in range(max_retries + 1):
        try:
            save_fn(session_maker_ref, ids)
            return  # 成功则退出
        except Exception:
            if attempt < max_retries:
                time.sleep(2 ** attempt)  # 指数退避：1s, 2s
            else:
                from common.utils.utils import ChatBILogUtil
                ChatBILogUtil.error(
                    f"Embedding generation failed after {max_retries + 1} attempts for ids={ids}"
                )


def run_save_terminology_embeddings(ids: List[int]):
    from apps.terminology.crud.terminology import save_embeddings
    executor.submit(_retry_save_embeddings, save_embeddings, session_maker, ids)


def fill_empty_terminology_embeddings():
    from apps.terminology.crud.terminology import run_fill_empty_embeddings
    executor.submit(run_fill_empty_embeddings, session_maker)


def run_save_data_training_embeddings(ids: List[int]):
    from apps.data_training.crud.data_training import save_embeddings
    executor.submit(_retry_save_embeddings, save_embeddings, session_maker, ids)


def fill_empty_data_training_embeddings():
    from apps.data_training.crud.data_training import run_fill_empty_embeddings
    executor.submit(run_fill_empty_embeddings, session_maker)


def run_save_table_embeddings(ids: List[int]):
    from apps.datasource.crud.table import save_table_embedding
    executor.submit(_retry_save_embeddings, save_table_embedding, session_maker, ids)


def run_save_ds_embeddings(ids: List[int]):
    from apps.datasource.crud.table import save_ds_embedding
    executor.submit(_retry_save_embeddings, save_ds_embedding, session_maker, ids)


def fill_empty_table_and_ds_embeddings():
    from apps.datasource.crud.table import run_fill_empty_table_and_ds_embedding
    executor.submit(run_fill_empty_table_and_ds_embedding, session_maker)
