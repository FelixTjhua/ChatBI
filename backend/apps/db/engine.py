# Author: Junjun
# Date: 2025/5/19
import re
import urllib.parse
from typing import List

from sqlalchemy import create_engine, text, MetaData, Table
from sqlalchemy.orm import sessionmaker

from apps.datasource.models.datasource import DatasourceConf
from common.core.config import settings


# 合法标识符正则：仅允许字母、数字、下划线、中文字符
_SAFE_IDENTIFIER_RE = re.compile(r'^[\w\u4e00-\u9fff][\w\u4e00-\u9fff\s]*$')

# 允许的字段类型白名单
_ALLOWED_FIELD_TYPES = {'text', 'bigint', 'numeric', 'timestamp'}


def get_engine_config():
    return DatasourceConf(username=settings.POSTGRES_USER, password=settings.POSTGRES_PASSWORD,
                          host=settings.POSTGRES_SERVER, port=settings.POSTGRES_PORT, database=settings.POSTGRES_DB,
                          dbSchema="public", timeout=30) # read engine config


def get_engine_uri(conf: DatasourceConf):
    return f"postgresql+psycopg2://{urllib.parse.quote(conf.username)}:{urllib.parse.quote(conf.password)}@{conf.host}:{conf.port}/{urllib.parse.quote(conf.database)}"


def get_engine_conn():
    conf = get_engine_config()
    db_url = get_engine_uri(conf)
    # 显式设置 client_encoding=utf8，防止 Docker 容器中
    # PostgreSQL 客户端编码与服务端不一致导致中文列名/数据乱码
    engine = create_engine(db_url,
                           connect_args={
                               "options": f"-c search_path={conf.dbSchema} -c client_encoding=utf8",
                               "connect_timeout": conf.timeout,
                           },
                           pool_timeout=conf.timeout)
    return engine


# 内部PG引擎单例，避免每次调用创建新Engine导致连接泄漏
_internal_pg_engine = None
_internal_pg_engine_lock = __import__('threading').Lock()


def _get_cached_engine():
    """获取缓存的内部PG引擎（单例模式）"""
    global _internal_pg_engine
    if _internal_pg_engine is None:
        with _internal_pg_engine_lock:
            if _internal_pg_engine is None:
                _internal_pg_engine = get_engine_conn()
    return _internal_pg_engine


def get_data_engine():
    engine = _get_cached_engine()
    session_maker = sessionmaker(bind=engine)
    session = session_maker()
    return session


def _validate_identifier(name: str, label: str = "identifier") -> str:
    """验证并清理SQL标识符，防止SQL注入"""
    if not name or not name.strip():
        raise ValueError(f"Invalid {label}: empty value")
    
    cleaned = name.strip()
    # 移除所有双引号后检查
    check_name = cleaned.replace('"', '')
    if not _SAFE_IDENTIFIER_RE.match(check_name):
        raise ValueError(f"Invalid {label}: '{cleaned}' contains illegal characters")
    
    # 转义双引号
    return cleaned.replace('"', '""')


def create_table(session, table_name: str, fields: List[any]):
    """
    安全地创建数据表
    
    使用标识符验证和类型白名单防止SQL注入
    """
    safe_table_name = _validate_identifier(table_name, "table name")
    
    col_defs = []
    for f in fields:
        if "object" in f["type"]:
            f["relType"] = "text"
        elif "int" in f["type"]:
            f["relType"] = "bigint"
        elif "float" in f["type"]:
            f["relType"] = "numeric"
        elif "datetime" in f["type"]:
            f["relType"] = "timestamp"
        else:
            f["relType"] = "text"
        
        # 验证字段类型在白名单中
        if f["relType"] not in _ALLOWED_FIELD_TYPES:
            raise ValueError(f"Invalid field type: {f['relType']}")
        
        safe_col_name = _validate_identifier(f["name"], "column name")
        col_defs.append(f'"{safe_col_name}" {f["relType"]}')

    sql = f"""
            CREATE TABLE "{safe_table_name}" (
                {", ".join(col_defs)}
            );
            """
    session.execute(text(sql))
    session.commit()


def insert_data(session, table_name: str, fields: List[any], data: List[any]):
    # 使用缓存的单例引擎，避免每次调用创建新Engine导致连接泄漏
    engine = _get_cached_engine()
    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=engine)
    with engine.connect() as conn:
        stmt = table.insert().values(data)
        conn.execute(stmt)
        conn.commit()
