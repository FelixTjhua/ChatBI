import atexit
import base64
import json
import os
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from typing import Dict, Optional

import oracledb
import sqlparse

from apps.db.db_sql import get_table_sql, get_field_sql, get_version_sql
from common.error import ParseSQLResultError

from sqlalchemy import create_engine, text, Engine
from sqlalchemy.engine import URL as SAUrl
from sqlalchemy.orm import sessionmaker

from apps.datasource.models.datasource import DatasourceConf, CoreDatasource, TableSchema, ColumnSchema
from apps.datasource.utils.utils import aes_decrypt
from apps.db.constant import DB, ConnectType
from apps.db.engine import get_engine_config
from apps.system.crud.assistant import get_ds_engine
from apps.system.schemas.system_schema import AssistantOutDsSchema
from common.core.deps import Trans
from common.utils.utils import ChatBILogUtil, equals_ignore_case
from fastapi import HTTPException


def _decimal_to_float(value: Decimal) -> float:
    """Decimal → float，避免浮点精度溢出（如 86.91 → 86.91000000000001）。
    通过 str 中转保留 Decimal 的精确表示，再转 float。"""
    return float(str(value))


def _clean_float(value: float) -> float:
    """修复浮点精度溢出（如 86.91000000000001 → 86.91）。
    
    利用 Python 的 repr 精度（17位有效数字）与 round 配合：
    对小数部分超过 10 位的 float，用 round(value, 10) 截断尾部噪声。
    整数值或短小数直接返回，不做任何修改。
    """
    import math
    if math.isinf(value) or math.isnan(value):
        return value
    # 整数值（如 100.0）直接返回
    if value == int(value) and abs(value) < 1e15:
        return value
    # 用 round(v, 10) 截断 double precision 运算产生的尾部噪声
    # 10 位小数精度对业务数据绰绰有余，同时能消除 1e-14 级别的浮点误差
    rounded = round(value, 10)
    return rounded


def _convert_value(value):
    """将数据库返回值转换为 JSON 可序列化的类型。
    
    参考 DataEase SQLBot 的 convert_value 设计，统一处理各种数据库驱动返回的特殊类型，
    避免 orjson/json 序列化失败导致数据丢失。
    """
    from datetime import datetime, date, time, timedelta
    
    if value is None:
        return None
    
    # bytes / bytearray（BIT 字段、二进制数据等）
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value) if isinstance(value, bytearray) else value
        # 短 bytes 尝试当 BIT 处理
        if len(raw) <= 8:
            try:
                int_val = int.from_bytes(raw, 'big')
                return bool(int_val) if int_val in (0, 1) else int_val
            except Exception:
                pass
        # 尝试 UTF-8 解码
        try:
            return raw.decode('utf-8')
        except UnicodeDecodeError:
            return f"0x{raw.hex()}"
    
    # Decimal → float（精度安全）
    if isinstance(value, Decimal):
        return _decimal_to_float(value)
    
    # float → 修复浮点精度溢出（如 86.91000000000001 → 86.91）
    if isinstance(value, float):
        return _clean_float(value)
    
    # timedelta → 字符串
    if isinstance(value, timedelta):
        return str(value)
    
    # datetime → 字符串（空格分隔，更常见）
    if isinstance(value, datetime):
        if value.hour == 0 and value.minute == 0 and value.second == 0 and value.microsecond == 0:
            return value.strftime('%Y-%m-%d')
        return value.strftime('%Y-%m-%d %H:%M:%S')
    
    # date → ISO 格式
    if isinstance(value, date):
        return value.isoformat()
    
    # time → 字符串
    if isinstance(value, time):
        return str(value)
    
    return value
from common.core.config import settings

# 后台缓存刷新线程池，限制最大并发数避免连接池耗尽
_bg_refresh_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix='cache_refresh')
# 注册 atexit 钩子，确保进程退出时线程池被正确关闭
atexit.register(_bg_refresh_executor.shutdown, wait=False)

# Engine 缓存，避免每次调用 get_engine() 都创建新的 Engine 实例
# SQLAlchemy Engine 内部维护连接池，反复创建 Engine 会导致连接池泄漏
import threading as _engine_threading
_engine_cache: Dict[str, Engine] = {}
_engine_cache_lock = _engine_threading.Lock()


# SQL 查询结果行数硬性上限，防止 OOM
MAX_RESULT_ROWS = 50000

def _cleanup_engine_cache():
    """进程退出时清理所有缓存的 Engine 实例，释放数据库连接池"""
    with _engine_cache_lock:
        for _key, _eng in _engine_cache.items():
            try:
                _eng.dispose()
            except Exception as e:
                ChatBILogUtil.debug(f"Engine dispose failed during cleanup for {_key}: {e}")
        _engine_cache.clear()


atexit.register(_cleanup_engine_cache)


def invalidate_engine_cache(ds_id: int):
    """当数据源配置变更时，清理该数据源的缓存 Engine 实例
    
     防止旧配置的 Engine（含过期凭据）继续被使用
    """
    with _engine_cache_lock:
        keys_to_remove = [k for k in _engine_cache if k.startswith(f"{ds_id}:")]
        for key in keys_to_remove:
            old_engine = _engine_cache.pop(key, None)
            if old_engine is not None:
                try:
                    old_engine.dispose()
                except Exception as e:
                    ChatBILogUtil.debug(f"Engine dispose failed during invalidation for ds_id={ds_id}: {e}")

try:
    if os.path.exists(settings.ORACLE_CLIENT_PATH):
        oracledb.init_oracle_client(
            lib_dir=settings.ORACLE_CLIENT_PATH
        )
        ChatBILogUtil.info("init oracle client success, use thick mode")
    else:
        ChatBILogUtil.info("init oracle client failed, because not found oracle client, use thin mode")
except Exception as e:
    ChatBILogUtil.error("init oracle client failed, check your client is installed, use thin mode")


def get_uri(ds: CoreDatasource) -> str:
    conf = DatasourceConf(**json.loads(aes_decrypt(ds.configuration))) if not equals_ignore_case(ds.type,
                                                                                                 "excel", "csv", "pdf") else get_engine_config()
    return get_uri_from_config(ds.type, conf)


def get_uri_from_config(type: str, conf: DatasourceConf) -> str:
    """构建数据库连接URL
    
     使用 sqlalchemy URL.create() 构建连接URL，
    避免密码以明文形式出现在日志中（SQLAlchemy会在repr中自动隐藏密码）。
    """
    if equals_ignore_case(type, "mysql"):
        url = SAUrl.create(
            "mysql+pymysql", username=conf.username, password=conf.password,
            host=conf.host, port=conf.port, database=conf.database,
            query=dict(item.split("=", 1) for item in conf.extraJdbc.split("&") if "=" in item) if conf.extraJdbc else {},
        )
    elif equals_ignore_case(type, "pg", "excel", "csv", "pdf"):
        url = SAUrl.create(
            "postgresql+psycopg2", username=conf.username, password=conf.password,
            host=conf.host, port=conf.port, database=conf.database,
            query=dict(item.split("=", 1) for item in conf.extraJdbc.split("&") if "=" in item) if conf.extraJdbc else {},
        )
    elif equals_ignore_case(type, "oracle"):
        if equals_ignore_case(conf.mode, "service_name"):
            query_params = {"service_name": conf.database}
            if conf.extraJdbc:
                query_params.update(dict(item.split("=", 1) for item in conf.extraJdbc.split("&") if "=" in item))
            url = SAUrl.create(
                "oracle+oracledb", username=conf.username, password=conf.password,
                host=conf.host, port=conf.port, query=query_params,
            )
        else:
            url = SAUrl.create(
                "oracle+oracledb", username=conf.username, password=conf.password,
                host=conf.host, port=conf.port, database=conf.database,
                query=dict(item.split("=", 1) for item in conf.extraJdbc.split("&") if "=" in item) if conf.extraJdbc else {},
            )
    else:
        raise ValueError(f'The datasource type "{type}" is not supported.')
    return str(url)


def get_extra_config(conf: DatasourceConf):
    config_dict = {}
    if conf.extraJdbc:
        config_arr = conf.extraJdbc.split("&")
        for config in config_arr:
            kv = config.split("=")
            if len(kv) == 2 and kv[0] and kv[1]:
                config_dict[kv[0]] = kv[1]
            else:
                raise Exception(f'param: {config} is error')
    return config_dict


# use sqlalchemy
def get_engine(ds: CoreDatasource, timeout: int = 0) -> Engine:
    """获取数据库引擎（带缓存）
    
     使用 Engine 缓存，按 ds.id + timeout 缓存 Engine 实例。
    SQLAlchemy Engine 内部维护连接池，反复创建 Engine 会导致连接池泄漏。
     使用 double-check locking 防止并发创建重复 Engine。
    """
    cache_key = f"{ds.id}:{timeout}"
    cached = _engine_cache.get(cache_key)
    if cached is not None:
        return cached

    # 在锁内再次检查，防止多线程同时创建同一 Engine
    with _engine_cache_lock:
        cached = _engine_cache.get(cache_key)
        if cached is not None:
            return cached

        conf = DatasourceConf(**json.loads(aes_decrypt(ds.configuration))) if not equals_ignore_case(ds.type,
                                                                                                     "excel", "csv", "pdf") else get_engine_config()
        if conf.timeout is None:
            conf.timeout = timeout
        if timeout > 0:
            conf.timeout = timeout
        if equals_ignore_case(ds.type, "pg", "excel", "csv", "pdf"):
            if conf.dbSchema is not None and conf.dbSchema != "":
                # 显式设置 client_encoding=utf8，防止中文列名/数据乱码
                engine = create_engine(get_uri(ds),
                                       connect_args={"options": f"-c search_path={urllib.parse.quote(conf.dbSchema)} -c client_encoding=utf8",
                                                     "connect_timeout": conf.timeout},
                                       pool_timeout=conf.timeout,
                                       pool_pre_ping=True)
            else:
                engine = create_engine(get_uri(ds),
                                       connect_args={"options": "-c client_encoding=utf8",
                                                     "connect_timeout": conf.timeout},
                                       pool_timeout=conf.timeout,
                                       pool_pre_ping=True)
        elif equals_ignore_case(ds.type, 'oracle'):
            engine = create_engine(get_uri(ds),
                                   pool_timeout=conf.timeout,
                                   pool_pre_ping=True)
        else:  # mysql
            engine = create_engine(get_uri(ds), connect_args={"connect_timeout": conf.timeout},
                                   pool_timeout=conf.timeout,
                                   pool_pre_ping=True)

        # Engine 缓存大小限制，防止无限增长
        # 当缓存超过 100 个 Engine 时，清理最早创建的（LRU 近似）
        if len(_engine_cache) >= 100:
            oldest_key = next(iter(_engine_cache))
            old_engine = _engine_cache.pop(oldest_key, None)
            if old_engine is not None:
                try:
                    old_engine.dispose()
                except Exception as e:
                    ChatBILogUtil.debug(f"Engine dispose failed during LRU eviction: {e}")

        _engine_cache[cache_key] = engine
    return engine


def get_session(ds: CoreDatasource | AssistantOutDsSchema):
    # 传入默认超时30秒，避免目标数据库不可达时无限期阻塞
    engine = get_engine(ds, timeout=30) if isinstance(ds, CoreDatasource) else get_ds_engine(ds)
    session_maker = sessionmaker(bind=engine)
    session = session_maker()
    return session


def check_connection(trans: Optional[Trans], ds: CoreDatasource | AssistantOutDsSchema, is_raise: bool = False):
    if isinstance(ds, CoreDatasource):
        conn = get_engine(ds, 10)
        try:
            with conn.connect() as connection:
                ChatBILogUtil.info("success")
                return True
        except Exception as e:
            ChatBILogUtil.error(f"Datasource {ds.id} connection failed: {e}")
            if is_raise:
                # 不将原始异常信息（含主机/端口/用户名）返回给前端
                raise HTTPException(status_code=500, detail=trans('i18n_ds_invalid'))
            return False
    else:
        conn = get_ds_engine(ds)
        try:
            with conn.connect() as connection:
                ChatBILogUtil.info("success")
                return True
        except Exception as e:
            ChatBILogUtil.error(f"Datasource {ds.id} connection failed: {e}")
            if is_raise:
                # 不将原始异常信息返回给前端
                raise HTTPException(status_code=500, detail=trans('i18n_ds_invalid'))
            return False

    return False


def get_version(ds: CoreDatasource | AssistantOutDsSchema) -> str:
    """获取数据库版本信息
    
     添加返回类型注解，确保所有路径返回str
    """
    version = ''
    conf = None
    if isinstance(ds, CoreDatasource):
        conf = DatasourceConf(
            **json.loads(aes_decrypt(ds.configuration))) if not equals_ignore_case(ds.type,
                                                                                   "excel", "csv", "pdf") else get_engine_config()
    if isinstance(ds, AssistantOutDsSchema):
        conf = DatasourceConf()
        conf.host = ds.host
        conf.port = ds.port
        conf.username = ds.user
        conf.password = ds.password
        conf.database = ds.dataBase
        conf.dbSchema = ds.db_schema
        conf.timeout = 10
    db = DB.get_db(ds.type)
    sql = get_version_sql(ds, conf)
    try:
        if db.connect_type == ConnectType.sqlalchemy:
            with get_session(ds) as session:
                with session.execute(text(sql)) as result:
                    res = result.fetchall()
                    version = res[0][0]
    except Exception as e:
        ChatBILogUtil.error(f"Failed to get database version: {e}")
        version = ''
    # 统一返回str，处理bytes和None
    if version is None:
        return ''
    return version.decode() if isinstance(version, bytes) else str(version)


def get_schema(ds: CoreDatasource):
    conf = DatasourceConf(**json.loads(aes_decrypt(ds.configuration))) if not equals_ignore_case(ds.type,
                                                                                                 "excel", "csv", "pdf") else get_engine_config()
    with get_session(ds) as session:
        sql: str = ''
        if equals_ignore_case(ds.type, "mysql"):
            sql = """SELECT SCHEMA_NAME FROM information_schema.SCHEMATA"""
        elif equals_ignore_case(ds.type, "pg", "excel", "csv", "pdf"):
            sql = """SELECT nspname FROM pg_namespace"""
        elif equals_ignore_case(ds.type, "oracle"):
            sql = """select * from all_users"""
        with session.execute(text(sql)) as result:
            res = result.fetchall()
            res_list = [item[0] for item in res]
            return res_list


def get_tables(ds: CoreDatasource):
    conf = DatasourceConf(**json.loads(aes_decrypt(ds.configuration))) if not equals_ignore_case(ds.type,
                                                                                                 "excel", "csv", "pdf") else get_engine_config()
    sql, sql_param = get_table_sql(ds, conf, get_version(ds))
    with get_session(ds) as session:
        with session.execute(text(sql), {"param": sql_param}) as result:
            res = result.fetchall()
            res_list = [TableSchema(*item) for item in res]
            return res_list


def get_fields(ds: CoreDatasource, table_name: str = None):
    conf = DatasourceConf(**json.loads(aes_decrypt(ds.configuration))) if not equals_ignore_case(ds.type,
                                                                                                 "excel", "csv", "pdf") else get_engine_config()
    sql, p1, p2 = get_field_sql(ds, conf, table_name)
    with get_session(ds) as session:
        with session.execute(text(sql), {"param1": p1, "param2": p2}) as result:
            res = result.fetchall()
            res_list = [ColumnSchema(*item) for item in res]
            ChatBILogUtil.info(
                f"[COLUMN-TRACE] get_fields table={table_name}, "
                f"PG返回=[{', '.join(f'{r.fieldName}(comment={r.fieldComment})' for r in res_list)}]"
            )
            return res_list


def _pg_round_fix(sql_text: str, _depth: int = 0) -> str:
    """递归处理嵌套ROUND调用，支持 ROUND(ROUND(col, 2) * 100, 1) 等复杂表达式
    
     提升为模块级函数，避免每次exec_sql调用都重新创建函数对象
     添加递归深度限制（最大10层），防止恶意构造的深层嵌套导致RecursionError
    """
    if _depth > 10:
        return sql_text
    result = []
    i = 0
    upper_sql = sql_text.upper()
    while i < len(sql_text):
        # 查找 ROUND( 的位置
        round_pos = upper_sql.find('ROUND(', i)
        if round_pos == -1:
            result.append(sql_text[i:])
            break
        result.append(sql_text[i:round_pos])
        # 从 ROUND( 之后开始，找到匹配的右括号
        paren_start = round_pos + 6  # len('ROUND(')
        depth = 1
        j = paren_start
        while j < len(sql_text) and depth > 0:
            if sql_text[j] == '(':
                depth += 1
            elif sql_text[j] == ')':
                depth -= 1
            j += 1
        if depth != 0:
            # 括号不匹配，保留原文
            result.append(sql_text[round_pos:j])
            i = j
            continue
        # 提取 ROUND(...) 内部内容
        inner = sql_text[paren_start:j - 1]
        # 递归处理内部的ROUND调用
        inner = _pg_round_fix(inner, _depth + 1)
        # 找到最后一个逗号（分隔表达式和精度）
        # 需要跳过括号内的逗号
        last_comma = -1
        comma_depth = 0
        for k in range(len(inner) - 1, -1, -1):
            if inner[k] == ')':
                comma_depth += 1
            elif inner[k] == '(':
                comma_depth -= 1
            elif inner[k] == ',' and comma_depth == 0:
                last_comma = k
                break
        if last_comma != -1:
            expr = inner[:last_comma].strip()
            precision = inner[last_comma + 1:].strip()
            # 检查precision是否为纯数字
            if precision.isdigit():
                result.append(f'ROUND(({expr})::numeric, {precision})')
            else:
                result.append(f'ROUND({inner})')
        else:
            result.append(f'ROUND({inner})')
        i = j
    return ''.join(result)


def _strip_sql_literals(sql_upper: str) -> str:
    """剥离SQL中的字符串常量、标识符和注释，用于安全关键词检测
    
    使用循环剥离美元引号，确保多个美元引号对都被正确移除。
    增加 PostgreSQL E'...' 转义字符串的剥离。
    将注释剥离提前到字符串剥离之前，防止注释中的引号干扰后续正则匹配。
    """
    result = sql_upper
    # 0. 优先移除SQL注释（注释中可能包含引号，干扰后续正则）
    result = re.sub(r'--[^\n]*', '', result)
    result = re.sub(r'/\*.*?\*/', '', result, flags=re.DOTALL)
    # 1. 循环移除 PostgreSQL $tag$...$tag$ 美元引号（贪婪匹配每一对）
    prev = None
    while prev != result:
        prev = result
        result = re.sub(r'\$([^$]*)\$.*?\$\1\$', '', result, count=1, flags=re.DOTALL)
    # 2. 移除 PostgreSQL E'...' 转义字符串（必须在普通单引号之前处理）
    result = re.sub(r"E'(?:[^'\\]|\\.)*'", '', result, flags=re.IGNORECASE)
    # 3. 移除转义引号感知的单引号字符串
    result = re.sub(r"'(?:[^'\\]|\\.)*'", '', result)
    # 4. 移除双引号标识符
    result = re.sub(r'"(?:[^"\\]|\\.)*"', '', result)
    return result


def exec_sql(ds: CoreDatasource | AssistantOutDsSchema, sql: str, origin_column=False):
    import time
    start_time = time.time()
    
    while sql.endswith(';'):
        sql = sql[:-1]

    # PostgreSQL兼容：ROUND(double precision, integer) 不存在，需要转为 ROUND(col::numeric, n)
    if equals_ignore_case(ds.type, "pg", "excel", "csv", "pdf"):
        sql = _pg_round_fix(sql)

    # SQL安全验证：仅允许SELECT语句（含WITH/CTE）
    # 检查所有语句（防止 "SELECT 1; DROP TABLE x" 多语句注入）
    sql_stripped = sql.strip().upper()
    parsed = sqlparse.parse(sql)
    # 拒绝多语句SQL（防止分号注入攻击）
    non_empty_stmts = [s for s in parsed if s.get_type() is not None or str(s).strip()]
    if len(non_empty_stmts) > 1:
        raise ParseSQLResultError("仅允许执行单条SQL语句，检测到多条语句")
    if parsed:
        stmt_type = parsed[0].get_type()
        if stmt_type and stmt_type not in ('SELECT', 'UNKNOWN'):
            raise ParseSQLResultError(f"仅允许执行SELECT查询，检测到: {stmt_type}")
        # UNKNOWN 类型（如 CTE）需额外验证以 SELECT 或 WITH 开头
        if stmt_type == 'UNKNOWN':
            _first_keyword = sql_stripped.lstrip()
            if not (_first_keyword.startswith('SELECT') or _first_keyword.startswith('WITH')):
                raise ParseSQLResultError(f"仅允许执行SELECT查询，检测到不安全的语句类型")
            # 移除冗余的 CTE 体内 DML 检测
    _dangerous_keywords = ['INSERT ', 'UPDATE ', 'DELETE ', 'DROP ', 'ALTER ', 'TRUNCATE ', 'CREATE ', 'GRANT ', 'REVOKE ']
    # 使用模块级函数剥离字符串常量，循环处理美元引号
    _sql_no_strings = _strip_sql_literals(sql_stripped)
    for kw in _dangerous_keywords:
        if kw in _sql_no_strings:
            raise ParseSQLResultError(f"SQL包含不允许的操作: {kw.strip()}")

    # 查询结果缓存，提升高频问题响应速度
    from apps.datasource.db_connection_pool import get_query_cache
    _cache = get_query_cache()
    ds_id = getattr(ds, 'id', None)

    # 仅对数据库类型数据源启用缓存（PDF/Excel/CSV内置库不缓存）
    _use_cache = ds.type.lower() not in ('excel', 'pdf', 'csv') if hasattr(ds, 'type') else True

    if _use_cache:
        cached_data, cache_status = _cache.get(sql, ds_id)
        if cached_data is not None and cache_status in ('hit', 'stale'):
            cached_data['cache_status'] = cache_status
            if cache_status == 'stale':
                # 缓存过期时附带降级提示
                from datetime import datetime
                _entry = _cache._cache.get(_cache._make_key(sql, ds_id))
                _created = datetime.fromtimestamp(_entry.created_at).strftime('%Y-%m-%d %H:%M:%S') if _entry else '未知'
                cached_data['cache_warning'] = f'数据暂未更新，当前为缓存数据（缓存时间：{_created}）'
                # stale 命中时触发后台异步刷新
                # 返回过时数据的同时，在后台线程中执行新查询并更新缓存
                if _cache.mark_refreshing(sql, ds_id):
                    def _bg_refresh(_sql, _ds, _ds_id, _cache_ref):
                        """ 显式关闭session避免连接泄漏
                         后台刷新前重新执行 SQL 安全验证，防止绕过入口检查
                        """
                        _sess = None
                        try:
                            # 重新验证 SQL 安全性（与 exec_sql 入口一致）
                            _sql_upper = _sql.strip().upper()
                            _parsed = sqlparse.parse(_sql)
                            _non_empty = [s for s in _parsed if s.get_type() is not None or str(s).strip()]
                            if len(_non_empty) > 1:
                                raise ParseSQLResultError("bg_refresh: 多语句SQL")
                            if _parsed:
                                _st = _parsed[0].get_type()
                                if _st and _st not in ('SELECT', 'UNKNOWN'):
                                    raise ParseSQLResultError(f"bg_refresh: 非SELECT: {_st}")
                                if _st == 'UNKNOWN':
                                    _fk = _sql_upper.lstrip()
                                    if not (_fk.startswith('SELECT') or _fk.startswith('WITH')):
                                        raise ParseSQLResultError("bg_refresh: 不安全的UNKNOWN语句")
                            _no_str = _strip_sql_literals(_sql_upper)
                            for _kw in ['INSERT ', 'UPDATE ', 'DELETE ', 'DROP ', 'ALTER ', 'TRUNCATE ', 'CREATE ', 'GRANT ', 'REVOKE ']:
                                if _kw in _no_str:
                                    raise ParseSQLResultError(f"bg_refresh: 危险关键词 {_kw.strip()}")

                            _sess = get_session(_ds)
                            with _sess.execute(text(_sql)) as _res:
                                _cols = [item.lower() for item in _res.keys()._keys]
                                # 后台刷新也需要行数限制（与主路径一致）
                                _rows = _res.fetchmany(MAX_RESULT_ROWS)
                                _data = [
                                    {str(_cols[i]): _convert_value(v)
                                     for i, v in enumerate(row)}
                                    for row in _rows
                                ]
                                _fresh = {"fields": _cols, "data": _data,
                                          "sql": bytes.decode(base64.b64encode(bytes(_sql, 'utf-8'))),
                                          "execution_time": 0, "cache_status": "miss"}
                                _cache_ref.put(_sql, _fresh, _ds_id)
                        except Exception as _e:
                            ChatBILogUtil.error(f"Background cache refresh failed: {_e}")
                        finally:
                            if _sess:
                                try:
                                    _sess.close()
                                except Exception as _close_err:
                                    ChatBILogUtil.debug(f"Session close failed in bg refresh: {_close_err}")
                            _cache_ref.clear_refreshing(_sql, _ds_id)
                    # 使用线程池限制最大并发刷新线程数
                    _bg_refresh_executor.submit(_bg_refresh, sql, ds, ds_id, _cache)
            return cached_data

    db = DB.get_db(ds.type)
    # exec_sql 对 fetchall 结果无行数限制，
    with get_session(ds) as session:
        with session.execute(text(sql)) as result:
            try:
                columns = result.keys()._keys if origin_column else [item.lower() for item in result.keys()._keys]
                # 复制 columns 列表，避免缓存与返回值共享引用
                columns = list(columns)
                ChatBILogUtil.info(f"[COLUMN-TRACE] exec_sql result.keys()._keys原始: {list(result.keys()._keys)}")
                ChatBILogUtil.info(f"[COLUMN-TRACE] exec_sql 处理后columns: {columns}")
                res = result.fetchmany(MAX_RESULT_ROWS + 1)
                _truncated = False
                if len(res) > MAX_RESULT_ROWS:
                    res = res[:MAX_RESULT_ROWS]
                    _truncated = True
                    ChatBILogUtil.warning(
                        f"exec_sql result truncated: query returned >{MAX_RESULT_ROWS} rows, "
                        f"only first {MAX_RESULT_ROWS} rows retained to prevent OOM"
                    )
                result_list = [
                    {str(columns[i]): _convert_value(value) for i, value in
                     enumerate(tuple_item)}
                    for tuple_item in res
                ]
                execution_time = int((time.time() - start_time) * 1000)  # 毫秒
                query_result = {"fields": columns, "data": result_list,
                        "sql": bytes.decode(base64.b64encode(bytes(sql, 'utf-8'))),
                        "execution_time": execution_time,
                        "cache_status": "miss"}
                # 将截断标记传递到结果中，让前端/LLM知道数据不完整
                if _truncated:
                    query_result["truncated"] = True
                    query_result["truncated_at"] = MAX_RESULT_ROWS

                # 写入缓存
                if _use_cache:
                    _cache.put(sql, query_result, ds_id)

                return query_result
            except Exception as ex:
                raise ParseSQLResultError(str(ex))
