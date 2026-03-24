import asyncio
import hashlib
import json
import os
import re
import uuid
from io import StringIO
from typing import List, Dict

import orjson
import pandas as pd
from fastapi import APIRouter, File, UploadFile, HTTPException
from sqlalchemy import text

from apps.db.db import get_schema
from apps.db.engine import get_engine_conn
from common.core.config import settings
from common.core.deps import SessionDep, CurrentUser, Trans
from common.utils.utils import ChatBILogUtil
from common.audit.audit_helper import log_datasource_created, log_datasource_deleted, log_file_uploaded
from common.utils.locale import I18n
from ..crud.datasource import get_datasource_list, check_status, create_ds, update_ds, delete_ds, getTables, getFields, \
    execSql, update_table_and_fields, getTablesByDs, chooseTables, preview, updateTable, updateField, get_ds, fieldEnum, \
    check_status_by_id
from ..crud.field import get_fields_by_table_id
from ..crud.table import get_tables_by_ds_id
from ..models.datasource import CoreDatasource, CreateDatasource, TableObj, CoreTable, CoreField, DatasourceResponse
from ..utils.utils import aes_decrypt

router = APIRouter(tags=["datasource"], prefix="/datasource")
# 按文件类型分目录存储
UPLOAD_BASE = settings.DATA_PATH


def _get_upload_path(file_ext: str) -> str:
    """根据文件扩展名返回对应的存储子目录"""
    ext = file_ext.lower().lstrip('.')
    if ext == 'pdf':
        sub = 'pdf'
    elif ext == 'csv':
        sub = 'csv'
    else:
        sub = 'excel'
    upload_dir = os.path.join(UPLOAD_BASE, sub)
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir

_i18n = I18n("locales")


def _ds_trans(user=None) -> callable:
    """获取基于用户语言的翻译函数"""
    lang = (user.language if user and hasattr(user, 'language') else 'zh-CN') or 'zh-CN'
    _lang = lang.lower().replace('_', '-')
    translations = _i18n.translations.get(_lang, _i18n.translations.get('zh-cn', {}))
    def _t(key: str, **kwargs) -> str:
        keys = key.split('.')
        current = translations
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return key
        if isinstance(current, str) and kwargs:
            try:
                return current.format(**kwargs)
            except (KeyError, ValueError):
                return current
        return current if isinstance(current, str) else key
    return _t


# OID 权限验证辅助函数，防止跨工作空间访问
def _verify_ds_ownership(session: SessionDep, ds_id: int, user: CurrentUser) -> CoreDatasource:
    """验证数据源存在且属于当前用户的工作空间"""
    ds = session.get(CoreDatasource, ds_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Datasource not found")
    if hasattr(ds, 'oid') and ds.oid != user.oid:
        raise HTTPException(status_code=403, detail="No permission to access this datasource")
    return ds

# 文件上传限制
MAX_UPLOAD_SIZE_MB = 50  # 最大上传文件大小（MB）
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

ALLOWED_EXCEL_EXTENSIONS = {"xlsx", "xls", "csv"}

# MIME类型白名单
ALLOWED_MIME_TYPES = {
    "pdf": ["application/pdf"],
    "xlsx": ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
    "xls": ["application/vnd.ms-excel"],
    "csv": ["text/csv", "application/csv", "text/plain"],
}


async def _validate_upload_file(file: UploadFile, allowed_extensions: set, user=None):
    """通用文件上传校验：扩展名、MIME类型、文件大小"""
    t = _ds_trans(user)
    if not file.filename:
        raise HTTPException(status_code=400, detail=t('i18n_file.filename_empty'))

    file_ext = file.filename.lower().rsplit('.', 1)[-1] if '.' in file.filename else ''
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=t('i18n_file.unsupported_type', ext=f'.{file_ext}', types=', '.join('.' + e for e in sorted(allowed_extensions)))
        )

    # MIME类型校验
    if file.content_type:
        expected_mimes = ALLOWED_MIME_TYPES.get(file_ext, [])
        if expected_mimes and file.content_type not in expected_mimes:
            ChatBILogUtil.warning(
                f"MIME type mismatch: file={file.filename}, ext={file_ext}, "
                f"content_type={file.content_type}, expected={expected_mimes}"
            )

    # 文件大小校验（读取内容并检查）
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=t('i18n_file.size_limit', max=MAX_UPLOAD_SIZE_MB, current=f"{len(content) / 1024 / 1024:.1f}")
        )
    if len(content) == 0:
        raise HTTPException(status_code=400, detail=t('i18n_file.file_is_empty'))

    # 重置文件指针以便后续读取
    await file.seek(0)
    return file_ext, content


@router.get("/ws/{oid}", include_in_schema=False)
async def query_by_oid(session: SessionDep, user: CurrentUser, oid: int) -> List[DatasourceResponse]:
    if not user.isAdmin:
        raise Exception("no permission to execute")
    ds_list = get_datasource_list(session=session, user=user, oid=oid)
    return [DatasourceResponse.from_datasource(ds) for ds in ds_list]


@router.get("/list")
async def datasource_list(session: SessionDep, user: CurrentUser) -> List[DatasourceResponse]:
    ds_list = get_datasource_list(session=session, user=user)
    return [DatasourceResponse.from_datasource(ds) for ds in ds_list]


@router.post("/get/{id}")
async def get_datasource(session: SessionDep, user: CurrentUser, id: int) -> DatasourceResponse:
    ds = _verify_ds_ownership(session, id, user)
    return DatasourceResponse.from_datasource(ds)


@router.post("/check")
async def check(session: SessionDep, trans: Trans, ds: CoreDatasource):
    def inner():
        return check_status(session, trans, ds, True)

    return await asyncio.to_thread(inner)


@router.get("/check/{ds_id}")
async def check_by_id(session: SessionDep, trans: Trans, user: CurrentUser, ds_id: int):
    _verify_ds_ownership(session, ds_id, user)

    def inner():
        return check_status_by_id(session, trans, ds_id, True)

    return await asyncio.to_thread(inner)


@router.post("/add", response_model=DatasourceResponse)
async def add(session: SessionDep, trans: Trans, user: CurrentUser, ds: CreateDatasource):
    def inner():
        result = create_ds(session, trans, user, ds)
        try:
            log_datasource_created(session, user.id, user.name or '', result.id,
                                   ds.name or '', oid=user.oid or 1)
        except Exception:
            pass

        # PDF数据源：将document记录关联到新创建的数据源
        if result.type == 'pdf' and result.configuration:
            try:
                from apps.datasource.models.document import CoreDocument
                conf = json.loads(aes_decrypt(result.configuration))
                doc_id = conf.get("document_id")
                if doc_id:
                    doc = session.query(CoreDocument).filter(CoreDocument.id == doc_id).first()
                    if doc:
                        doc.ds_id = result.id
                        session.add(doc)
                        session.commit()
                        ChatBILogUtil.info(f"PDF文档 doc_id={doc_id} 已关联到数据源 ds_id={result.id}")
                    else:
                        ChatBILogUtil.error(f"PDF文档 doc_id={doc_id} 不存在，数据源 ds_id={result.id} 将无法检索文档")
            except Exception as e:
                # 关联失败从"非致命"提升为错误级别日志
                # ds_id 未关联会导致：1) delete_ds 无法级联清理 2) search_document_chunks 按 ds_id 过滤时漏掉文档
                ChatBILogUtil.error(f"关联PDF文档到数据源失败: {e}，ds_id={result.id}")

        return DatasourceResponse.from_datasource(result)

    return await asyncio.to_thread(inner)


@router.post("/chooseTables/{id}")
async def choose_tables(session: SessionDep, trans: Trans, user: CurrentUser, id: int, tables: List[CoreTable]):
    _verify_ds_ownership(session, id, user)

    def inner():
        chooseTables(session, trans, id, tables)

    await asyncio.to_thread(inner)


@router.post("/update", response_model=DatasourceResponse)
async def update(session: SessionDep, trans: Trans, user: CurrentUser, ds: CoreDatasource):
    # 更新时也验证数据源类型合法性
    from ..models.datasource import VALID_DS_TYPES
    if ds.type and ds.type not in VALID_DS_TYPES:
        t = _ds_trans(user)
        raise HTTPException(status_code=400, detail=t('i18n_file.unsupported_ds_type', type=ds.type, types=', '.join(sorted(VALID_DS_TYPES))))
    # 验证要更新的数据源属于当前用户
    if ds.id:
        _verify_ds_ownership(session, int(ds.id), user)

    def inner():
        result = update_ds(session, trans, user, ds)
        return DatasourceResponse.from_datasource(result)

    return await asyncio.to_thread(inner)


@router.post("/delete/{id}")
async def delete(session: SessionDep, user: CurrentUser, id: int):
    ds = _verify_ds_ownership(session, id, user)
    result = delete_ds(session, id)
    try:
        log_datasource_deleted(session, user.id, user.name or '', id, oid=user.oid or 1)
    except Exception as e:
        # 记录审计日志失败而非静默忽略
        ChatBILogUtil.warning(f"Failed to log datasource deletion: {e}")
    return result


@router.post("/getTables/{id}")
async def get_tables(session: SessionDep, user: CurrentUser, id: int):
    _verify_ds_ownership(session, id, user)
    return getTables(session, id)


@router.post("/getTablesByConf")
async def get_tables_by_conf(session: SessionDep, trans: Trans, ds: CoreDatasource):
    try:
        def inner():
            return getTablesByDs(session, ds)

        return await asyncio.to_thread(inner)
    except Exception as e:
        # check ds status
        def inner():
            return check_status(session, trans, ds, True)

        status = await asyncio.to_thread(inner)
        if status:
            ChatBILogUtil.error(f"get table failed: {e}")
            raise HTTPException(status_code=500, detail=f'Get table Failed: {e.args}')


@router.post("/getSchemaByConf")
async def get_schema_by_conf(session: SessionDep, trans: Trans, ds: CoreDatasource):
    try:
        def inner():
            return get_schema(ds)

        return await asyncio.to_thread(inner)
    except Exception as e:
        # check ds status
        def inner():
            return check_status(session, trans, ds, True)

        status = await asyncio.to_thread(inner)
        if status:
            ChatBILogUtil.error(f"get table failed: {e}")
            raise HTTPException(status_code=500, detail=f'Get table Failed: {e.args}')


@router.post("/getFields/{id}/{table_name}")
async def get_fields(session: SessionDep, user: CurrentUser, id: int, table_name: str):
    _verify_ds_ownership(session, id, user)
    return getFields(session, id, table_name)


from pydantic import BaseModel


class TestObj(BaseModel):
    sql: str = None


# not used, just do test
@router.post("/execSql/{id}")
async def exec_sql(session: SessionDep, user: CurrentUser, id: int, obj: TestObj):
    _verify_ds_ownership(session, id, user)

    def inner():
        data = execSql(session, id, obj.sql)
        try:
            data_obj = data.get('data')
            # ChatBILogUtil.info(orjson.dumps(data, option=orjson.OPT_NON_STR_KEYS).decode())
            ChatBILogUtil.info(orjson.dumps(data_obj).decode())
        except Exception:
            from common.utils.utils import ChatBILogUtil
            ChatBILogUtil.exception()

        return data

    return await asyncio.to_thread(inner)


@router.post("/tableList/{id}")
async def table_list(session: SessionDep, user: CurrentUser, id: int):
    _verify_ds_ownership(session, id, user)
    return get_tables_by_ds_id(session, id)


@router.post("/fieldList/{id}")
async def field_list(session: SessionDep, user: CurrentUser, id: int):
    # fieldList 接收的是 table_id，需要通过 table 找到 ds 再验证
    from ..models.datasource import CoreTable as CT
    table = session.get(CT, id)
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    ds = _verify_ds_ownership(session, table.ds_id, user)
    fields = get_fields_by_table_id(session, id)
    return fields


@router.post("/editLocalComment")
async def edit_local(session: SessionDep, user: CurrentUser, data: TableObj):
    if data.table and data.table.ds_id:
        _verify_ds_ownership(session, data.table.ds_id, user)
    update_table_and_fields(session, data)


@router.post("/editTable")
async def edit_table(session: SessionDep, user: CurrentUser, table: CoreTable):
    if table.ds_id:
        _verify_ds_ownership(session, table.ds_id, user)
    updateTable(session, table)


@router.post("/editField")
async def edit_field(session: SessionDep, user: CurrentUser, field: CoreField):
    if field.ds_id:
        _verify_ds_ownership(session, field.ds_id, user)
    updateField(session, field)


@router.post("/previewData/{id}")
async def preview_data(session: SessionDep, trans: Trans, current_user: CurrentUser, id: int, data: TableObj):
    _verify_ds_ownership(session, id, current_user)

    def inner():
        try:
            return preview(session, current_user, id, data)
        except HTTPException:
            raise
        except Exception as e:
            ds = session.query(CoreDatasource).filter(CoreDatasource.id == id).first()
            if ds:
                # check_status with is_raise=True will raise HTTPException if connection fails
                check_status(session, trans, ds, True)
            # 如果连接正常但预览仍然失败，抛出原始错误
            ChatBILogUtil.error(f"Preview failed: {e}")
            raise HTTPException(status_code=500, detail=f'Preview Failed: {e.args}')

    return await asyncio.to_thread(inner)


# not used
@router.post("/fieldEnum/{id}")
async def field_enum(session: SessionDep, user: CurrentUser, id: int):
    _verify_ds_ownership(session, id, user)

    def inner():
        return fieldEnum(session, id)

    return await asyncio.to_thread(inner)


def _build_excel_preview(save_path: str, original_filename: str, content: bytes,
                         sheets: list, created_tables: list,
                         cleaning_stats: dict | None = None) -> dict:
    """构建 Excel/CSV 上传后的前端预览数据"""
    import pandas as pd
    ext = os.path.splitext(save_path)[1].lower()
    is_csv = ext == '.csv'

    preview_sheets = []
    total_rows = 0
    total_cols = 0  # 所有sheet的字段总数（累加）

    try:
        if is_csv:
            # CSV预览也需要智能编码/分隔符检测（与upload_excel一致）
            _prev_encoding = 'utf-8'
            _prev_sep = ','
            try:
                with open(save_path, 'rb') as _f:
                    _raw = _f.read(8192)
                # 检测 UTF-8 BOM，使用 utf-8-sig 自动剥离
                if _raw[:3] == b'\xef\xbb\xbf':
                    _prev_encoding = 'utf-8-sig'
                else:
                    try:
                        _raw.decode('utf-8')
                    except UnicodeDecodeError:
                        try:
                            _raw.decode('gbk')
                            _prev_encoding = 'gbk'
                        except UnicodeDecodeError:
                            _prev_encoding = 'latin-1'
                with open(save_path, 'r', encoding=_prev_encoding) as _f:
                    _first_line = _f.readline()
                _tab_c = _first_line.count('\t')
                _comma_c = _first_line.count(',')
                _semi_c = _first_line.count(';')
                if _tab_c > _comma_c and _tab_c > _semi_c:
                    _prev_sep = '\t'
                elif _semi_c > _comma_c:
                    _prev_sep = ';'
            except Exception:
                pass
            # 获取真实行数：优先使用 cleaning_stats（已经完整扫描过），避免大文件重复逐行计数
            df = pd.read_csv(save_path, nrows=100, encoding=_prev_encoding, sep=_prev_sep, on_bad_lines='skip')
            if cleaning_stats and cleaning_stats.get("original_rows", 0) > 0:
                real_row_count = cleaning_stats["original_rows"]
            else:
                real_row_count = len(df)  # 仅预览行数作为兜底
            dfs = {"Sheet1": (df, max(real_row_count, len(df)))}
        else:
            xls = pd.ExcelFile(save_path)
            dfs = {}
            for name in xls.sheet_names:
                # 只读第一列来快速获取真实行数
                df_col0 = pd.read_excel(xls, sheet_name=name, usecols=[0])
                df_preview = pd.read_excel(xls, sheet_name=name, nrows=100)
                dfs[name] = (df_preview, max(len(df_col0), len(df_preview)))

        for sheet_name, (df, real_rows) in dfs.items():
            cols = [str(c) for c in df.columns.tolist()]
            total_rows += real_rows
            total_cols += len(cols)  # -15：累加所有sheet的字段数，而非取max

            # 数据类型统计
            numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
            text_cols = [c for c in cols if not pd.api.types.is_numeric_dtype(df[c])]

            # 前5行数据预览
            sample_rows = []
            for _, row in df.head(5).iterrows():
                sample_rows.append({str(c): str(v) for c, v in row.items()})

            preview_sheets.append({
                "name": sheet_name,
                "columns": cols,
                "rows_count": real_rows,
                "numeric_columns": numeric_cols,
                "text_columns": text_cols,
                "sample_rows": sample_rows,
            })
    except Exception as e:
        ChatBILogUtil.warning(f"构建Excel预览失败(非致命): {e}")

    # 优先使用 cleaning_stats 中的真实行数（来自完整数据清洗流程）
    if cleaning_stats and cleaning_stats.get("original_rows", 0) > total_rows:
        total_rows = cleaning_stats["original_rows"]

    result = {
        "file_type": "csv" if is_csv else "excel",
        "file_size": len(content),
        "original_filename": original_filename,
        "sheet_count": len(preview_sheets) if preview_sheets else len(sheets),
        "total_rows": total_rows,
        "total_columns": total_cols,
        "tables_created": len(created_tables),
        "sheets": preview_sheets,
    }
    if cleaning_stats:
        result["cleaning_stats"] = cleaning_stats
        # 提供清洗摘要，让前端可以提示"预览数据与实际导入可能有差异"
        removed = cleaning_stats.get("dedup_removed", 0) + cleaning_stats.get("null_rows_removed", 0)
        if removed > 0:
            result["cleaning_note"] = f"数据清洗移除了 {removed} 行（重复 {cleaning_stats.get('dedup_removed', 0)}，空行 {cleaning_stats.get('null_rows_removed', 0)}）"
            result["rows_after_cleaning"] = cleaning_stats.get("cleaned_rows", total_rows - removed)
    return result


@router.post("/uploadExcel")
async def upload_excel(session: SessionDep, current_user: CurrentUser, file: UploadFile = File(...)):
    file_ext, content = await _validate_upload_file(file, ALLOWED_EXCEL_EXTENSIONS, current_user)

    upload_path = _get_upload_path(file_ext)
    # 使用 os.path.basename 清理文件名，防止路径穿越攻击（与 uploadPdf 一致）
    safe_name = os.path.basename(file.filename or 'unnamed')
    filename = f"{safe_name.rsplit('.', 1)[0]}_{hashlib.sha256(uuid.uuid4().bytes).hexdigest()[:10]}.{file_ext}"
    save_path = os.path.join(upload_path, filename)
    with open(save_path, "wb") as f:
        f.write(content)

    def inner():
        created_tables = []  # 记录已创建的表，用于失败时回滚
        try:
            sheets = []
            all_cleaning_stats = []  # 汇总各工作表的清洗统计
            engine = get_engine_conn()
            if filename.endswith(".csv"):
                # CSV上传使用智能编码/分隔符检测（与document_parser._read_csv_smart一致）
                # GBK编码或制表符/分号分隔的CSV文件会解析失败或乱码
                _csv_encoding = 'utf-8'
                _csv_sep = ','
                try:
                    with open(save_path, 'rb') as _f:
                        _raw = _f.read(8192)
                    # 检测 UTF-8 BOM（EF BB BF），使用 utf-8-sig 自动剥离
                    if _raw[:3] == b'\xef\xbb\xbf':
                        _csv_encoding = 'utf-8-sig'
                    else:
                        try:
                            _raw.decode('utf-8')
                        except UnicodeDecodeError:
                            try:
                                _raw.decode('gbk')
                                _csv_encoding = 'gbk'
                            except UnicodeDecodeError:
                                _csv_encoding = 'latin-1'
                    with open(save_path, 'r', encoding=_csv_encoding) as _f:
                        _first_line = _f.readline()
                    _tab_c = _first_line.count('\t')
                    _comma_c = _first_line.count(',')
                    _semi_c = _first_line.count(';')
                    if _tab_c > _comma_c and _tab_c > _semi_c:
                        _csv_sep = '\t'
                    elif _semi_c > _comma_c:
                        _csv_sep = ';'
                except Exception:
                    pass
                df = pd.read_csv(save_path, encoding=_csv_encoding, sep=_csv_sep, on_bad_lines='skip')
                ChatBILogUtil.info(f"[COLUMN-TRACE] read_csv columns: {list(df.columns)}")
                tableName = f"sheet1_{hashlib.sha256(uuid.uuid4().bytes).hexdigest()[:10]}"
                sheets.append({"tableName": tableName, "tableComment": file.filename})
                created_tables.append(tableName)
                stats = insert_pg(df, tableName, engine)
                all_cleaning_stats.append(stats)
            else:
                sheet_names = pd.ExcelFile(save_path).sheet_names
                for sheet_name in sheet_names:
                    tableName = f"{sheet_name}_{hashlib.sha256(uuid.uuid4().bytes).hexdigest()[:10]}"
                    sheets.append({"tableName": tableName, "tableComment": f"{file.filename} - {sheet_name}"})
                    created_tables.append(tableName)
                    df = pd.read_excel(save_path, sheet_name=sheet_name, engine='calamine')
                    ChatBILogUtil.info(f"[COLUMN-TRACE] read_excel columns (sheet={sheet_name}): {list(df.columns)}")
                    # 诊断：对比 openpyxl 引擎读取的列名，检测 calamine 是否错误读取注音数据
                    try:
                        _df_openpyxl = pd.read_excel(save_path, sheet_name=sheet_name, engine='openpyxl', nrows=0)
                        _openpyxl_cols = list(_df_openpyxl.columns)
                        if list(df.columns) != _openpyxl_cols:
                            ChatBILogUtil.warning(
                                f"[COLUMN-TRACE] ⚠️ calamine与openpyxl列名不一致! "
                                f"calamine={list(df.columns)}, openpyxl={_openpyxl_cols}"
                            )
                            # calamine 读取了错误的列名（可能是注音/拼音），使用 openpyxl 的列名
                            ChatBILogUtil.info(f"[COLUMN-TRACE] 使用openpyxl列名替换calamine列名")
                            df.columns = _openpyxl_cols
                        else:
                            ChatBILogUtil.info(f"[COLUMN-TRACE] calamine与openpyxl列名一致")
                    except Exception as _cmp_e:
                        ChatBILogUtil.warning(f"[COLUMN-TRACE] openpyxl对比失败: {_cmp_e}")
                    stats = insert_pg(df, tableName, engine)
                    all_cleaning_stats.append(stats)

            # 汇总所有工作表的清洗统计
            aggregated_stats = {
                "original_rows": sum(s.get("original_rows", 0) for s in all_cleaning_stats),
                "cleaned_rows": sum(s.get("cleaned_rows", 0) for s in all_cleaning_stats),
                "dedup_removed": sum(s.get("dedup_removed", 0) for s in all_cleaning_stats),
                "null_rows_removed": sum(s.get("null_rows_removed", 0) for s in all_cleaning_stats),
            }

            return {
                "filename": filename,
                "sheets": sheets,
                "excel_preview": _build_excel_preview(save_path, file.filename, content, sheets, created_tables, aggregated_stats),
            }
        except Exception:
            # 导入失败时清理已保存的文件和已创建的表
            if os.path.exists(save_path):
                try:
                    os.remove(save_path)
                except OSError:
                    pass
            if created_tables:
                try:
                    cleanup_engine = get_engine_conn()
                    with cleanup_engine.connect() as conn:
                        for t_name in created_tables:
                            # 验证表名合法性，防止 SQL 注入
                            if not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]*', t_name):
                                ChatBILogUtil.warning(f"Skipping invalid table name during cleanup: {t_name}")
                                continue
                            conn.execute(text(f'DROP TABLE IF EXISTS "{t_name}"'))
                        conn.commit()
                except Exception as e:
                    ChatBILogUtil.error(f"Failed to cleanup tables: {e}")
            raise

    return await asyncio.to_thread(inner)


ALLOWED_PDF_EXTENSIONS = {"pdf"}


@router.post("/uploadPdf")
async def upload_pdf(session: SessionDep, current_user: CurrentUser, file: UploadFile = File(...)):
    """PDF文件上传：文档RAG处理流水线"""
    file_ext, content = await _validate_upload_file(file, ALLOWED_PDF_EXTENSIONS, current_user)

    upload_path = _get_upload_path(file_ext)
    # 使用 os.path.basename 清理文件名，防止路径穿越攻击（如 ../../etc/passwd.pdf）
    safe_name = os.path.basename(file.filename or 'unnamed')
    filename = f"{safe_name.rsplit('.', 1)[0]}_{hashlib.sha256(uuid.uuid4().bytes).hexdigest()[:10]}.{file_ext}"
    save_path = os.path.join(upload_path, filename)
    with open(save_path, "wb") as f:
        f.write(content)

    def inner():
        try:
            from apps.datasource.document_parser import DocumentPipeline
            from apps.datasource.models.document import CoreDocument, CoreDocumentChunk
            from datetime import datetime

            # ===== 文档RAG处理流水线 =====
            result = DocumentPipeline.process(save_path)
            stats = result.get("stats", {})
            parse_result = result.get("parse_result")
            chunks = result.get("chunks", [])
            vectorized = result.get("vectorized", [])

            # PDF空内容校验 — 扫描版PDF或空白PDF会解析出0个chunk
            # 此时静默成功会误导用户以为上传正常，实际无任何可检索内容
            _scanned_count = parse_result.metadata.get("scanned_page_count", 0) if parse_result else 0
            _total_pages = parse_result.metadata.get("total_pages", 0) if parse_result else 0
            if len(chunks) == 0:
                # 清理已保存的文件
                if os.path.exists(save_path):
                    try:
                        os.remove(save_path)
                    except OSError:
                        pass
                _t = _ds_trans(current_user)
                if _scanned_count > 0 and _scanned_count >= _total_pages:
                    raise HTTPException(
                        status_code=400,
                        detail=_t('i18n_document.scanned_pdf', pages=_total_pages)
                    )
                else:
                    raise HTTPException(
                        status_code=400,
                        detail=_t('i18n_document.empty_pdf', pages=_total_pages)
                    )

            # ===== 存入数据库：文档元信息 + 分块 + 向量 =====
            doc = CoreDocument(
                filename=file.filename,
                file_type=".pdf",
                file_size=len(content),
                file_path=save_path,
                total_chunks=stats.get("total_chunks", 0),
                vectorized_count=stats.get("vectorized_count", 0),
                total_sections=stats.get("total_sections", 0),
                total_tables=stats.get("total_tables", 0),
                processing_time=stats.get("total_time", 0),
                oid=current_user.oid or 1,
                user_id=current_user.id,  # 记录上传用户，与 parse_document 保持一致
                create_time=datetime.now(),
                source_type='PDF',
                source_name=file.filename,
                # 存储完整原始文本，确保"零丢失解析"可验证
                # raw_text 保留 PDF 的全部原始文本（含被 table_overlap 跳过的内容）
                raw_text=parse_result.raw_text if parse_result else None,
            )
            session.add(doc)
            session.flush()

            # 存入文档分块记录
            for i, chunk in enumerate(chunks):
                chunk_record = CoreDocumentChunk(
                    document_id=doc.id,
                    chunk_index=i,
                    text=chunk.text,
                    source_file=chunk.metadata.get("source_file", ""),
                    section_title=chunk.metadata.get("section_title", ""),
                    page_number=chunk.metadata.get("page_number"),
                    chunk_type=chunk.metadata.get("chunk_type", ""),
                    create_time=datetime.now(),
                    source_type='PDF',
                    source_name=file.filename,
                    library_id=doc.id,
                )
                session.add(chunk_record)

            # 存入向量（批量写入，通过 chunk_index 精确匹配）
            session.flush()
            if vectorized:
                from sqlalchemy import text as sa_text
                # 一次查询获取所有 chunk 的 id→chunk_index 映射
                all_chunk_recs = session.query(
                    CoreDocumentChunk.id, CoreDocumentChunk.chunk_index
                ).filter(
                    CoreDocumentChunk.document_id == doc.id
                ).all()
                index_to_id = {rec.chunk_index: rec.id for rec in all_chunk_recs}

                # 批量构建 UPDATE 参数
                update_count = 0
                for v_item in vectorized:
                    embedding = v_item.get("embedding")
                    v_meta = v_item.get("metadata", {})
                    chunk_index = v_meta.get("chunk_index")
                    if embedding and chunk_index is not None and chunk_index in index_to_id:
                        emb_str = "[" + ",".join(str(x) for x in embedding) + "]"
                        session.execute(
                            sa_text(
                                "UPDATE core_document_chunk SET embedding = :emb WHERE id = :cid"
                            ),
                            {"emb": emb_str, "cid": index_to_id[chunk_index]}
                        )
                        update_count += 1

                ChatBILogUtil.info(f"向量批量写入: {update_count}/{len(vectorized)} embeddings")

            session.commit()
            ChatBILogUtil.info(
                f"PDF文档RAG处理完成: {file.filename}, "
                f"doc_id={doc.id}, chunks={len(chunks)}, vectorized={len(vectorized)}"
            )

            # ===== 构建前端预览数据 =====
            raw_text_preview = ""
            if parse_result and parse_result.raw_text:
                raw_text_preview = parse_result.raw_text[:500]
                if len(parse_result.raw_text) > 500:
                    raw_text_preview += "..."

            # 2. 章节列表
            sections_preview = []
            if parse_result:
                for sec in parse_result.sections[:30]:
                    sections_preview.append({
                        "title": sec.get("title", ""),
                        "page": sec.get("page", 1),
                        "content_preview": (sec.get("content", "")[:120] + "...") if len(sec.get("content", "")) > 120 else sec.get("content", ""),
                    })

            # 3. 表格预览（Markdown 格式，展示PDF中提取的表格已转为文本chunk）
            tables_preview = []
            if parse_result:
                for idx_t, tbl in enumerate(parse_result.tables[:10]):
                    headers = tbl.get("headers", [])
                    rows = tbl.get("rows", [])[:5]
                    md_lines = ["| " + " | ".join(headers) + " |"]
                    md_lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
                    for row in rows:
                        md_lines.append("| " + " | ".join(str(c) for c in row) + " |")
                    if len(tbl.get("rows", [])) > 5:
                        md_lines.append(f"_...共 {len(tbl.get('rows', []))} 行_")
                    tables_preview.append({
                        "index": idx_t + 1,
                        "page": tbl.get("page", "?"),
                        "columns": len(headers),
                        "rows": len(tbl.get("rows", [])),
                        "markdown": "\n".join(md_lines),
                    })

            # 4. 分块预览（前 20 个 chunk）
            chunks_preview = []
            for c in chunks[:20]:
                chunks_preview.append({
                    "index": c.metadata.get("chunk_index", 0),
                    "chunk_type": c.metadata.get("chunk_type", "text"),
                    "page_number": c.metadata.get("page_number"),
                    "section_title": c.metadata.get("section_title", ""),
                    "text_preview": (c.text[:150] + "...") if len(c.text) > 150 else c.text,
                    "text_length": len(c.text),
                })

            # PDF不再返回sheets（不导入PostgreSQL）
            _warnings = []
            _t = _ds_trans(current_user)
            if _scanned_count > 0 and _scanned_count < _total_pages:
                _warnings.append(
                    _t('i18n_document.scanned_warning', scanned=_scanned_count, total=_total_pages)
                )
            if stats.get("vectorized_count", 0) < stats.get("total_chunks", 0):
                _vec_count = stats.get("vectorized_count", 0)
                _chunk_count = stats.get("total_chunks", 0)
                _warnings.append(
                    _t('i18n_document.vectorize_warning', vectorized=_vec_count, total=_chunk_count)
                )
            return {
                "filename": filename,
                "document_id": doc.id,
                "sheets": [],
                "warnings": _warnings,
                "pdf_stats": {
                    "total_chunks": stats.get("total_chunks", 0),
                    "vectorized_count": stats.get("vectorized_count", 0),
                    "total_pages": parse_result.metadata.get("total_pages", 0) if parse_result else 0,
                    "total_sections": stats.get("total_sections", 0),
                    "total_tables": stats.get("total_tables", 0),
                    "processing_time": stats.get("total_time", 0),
                    "file_size": len(content),
                    "scanned_pages": parse_result.metadata.get("scanned_page_count", 0) if parse_result else 0,
                    "ocr_pages": parse_result.metadata.get("ocr_page_count", 0) if parse_result else 0,
                    "raw_text_length": len(parse_result.raw_text) if parse_result and parse_result.raw_text else 0,
                    "chunks_total_chars": sum(len(c.text) for c in chunks) if chunks else 0,
                    "table_chunks": len([c for c in chunks if c.metadata.get("chunk_type") == "table"]),
                },
                "pdf_preview": {
                    "raw_text_preview": raw_text_preview,
                    "sections": sections_preview,
                    "tables": tables_preview,
                    "chunks": chunks_preview,
                },
            }
        except Exception:
            # 失败时清理已保存的文件
            session.rollback()
            if os.path.exists(save_path):
                try:
                    os.remove(save_path)
                except OSError:
                    pass
            raise

    return await asyncio.to_thread(inner)



def _clean_dataframe(df):
    """数据清洗：去重、空值处理、格式统一、异常值过滤"""
    from common.utils.utils import ChatBILogUtil
    original_rows = len(df)
    
    # 1. 去重
    df = df.drop_duplicates()
    dedup_removed = original_rows - len(df)
    
    # 2. 删除全空行
    after_dedup_rows = len(df)
    df = df.dropna(how='all')
    
    # 3. 列名格式统一：去除首尾空格
    df.columns = [str(col).strip() for col in df.columns]
    
    # 4. 空值处理 + 格式统一
    for col in df.columns:
        if df[col].dtype in ('float64', 'float32', 'int64', 'int32'):
            # 数值列：空值填0
            df[col] = df[col].fillna(0)
        elif str(df[col].dtype).lower() in ('object', 'str', 'string'):
            # 文本列：空值填空字符串，去首尾空格
            df[col] = df[col].fillna('').astype(str).str.strip()
    
    # 5. 异常值标记（仅记录，不修改原始数据）
    import re as _re_date
    for col in df.columns:
        # 兼容 pandas 2.x 的 StringDtype 和旧版的 object dtype
        _dtype_str = str(df[col].dtype).lower()
        _is_string_col = _dtype_str in ('object', 'str', 'string')
        if _is_string_col:
            # 检查列名是否包含日期相关关键词
            col_lower = str(col).lower()
            is_date_name = any(kw in col_lower for kw in ['日期', '时间', 'date', 'time', '年月'])
            if is_date_name:
                # 尝试将字符串列转换为datetime
                try:
                    sample = df[col].dropna().head(20)
                    if len(sample) > 0:
                        # 检查是否符合日期格式 (YYYY-MM-DD 或 YYYY/MM/DD)
                        date_pattern = _re_date.compile(r'^\d{4}[-/]\d{1,2}[-/]\d{1,2}')
                        match_count = sum(1 for v in sample if date_pattern.match(str(v).strip()))
                        if match_count >= len(sample) * 0.8:  # 80%以上匹配则转换
                            import pandas as _pd_date
                            df[col] = _pd_date.to_datetime(df[col], errors='coerce')
                            non_null = df[col].notna().sum()
                            ChatBILogUtil.info(
                                f"日期列自动转换: '{col}' -> datetime64 "
                                f"({non_null}/{len(df)} 行成功)"
                            )
                except Exception as _date_e:
                    ChatBILogUtil.warning(f"日期列自动转换失败 '{col}': {_date_e}")

    outlier_count = 0
    for col in df.select_dtypes(include=['float64', 'float32', 'int64', 'int32']).columns:
        if len(df[col]) < 10:
            continue
        mean = df[col].mean()
        std = df[col].std()
        if std > 0:
            lower = mean - 3 * std
            upper = mean + 3 * std
            col_outliers = ((df[col] < lower) | (df[col] > upper)).sum()
            outlier_count += col_outliers
    if outlier_count > 0:
        ChatBILogUtil.info(f"数据质量提示: 检测到 {outlier_count} 个超出3σ范围的值（已保留原始值）")
    
    cleaned_rows = len(df)
    ChatBILogUtil.info(
        f"数据清洗完成: 原始{original_rows}行 → 清洗后{cleaned_rows}行, "
        f"去重删除{dedup_removed}行"
    )
    # 返回清洗后的 DataFrame 和清洗统计信息
    # null_rows_removed 应基于去重后的行数计算，而非原始行数
    cleaning_stats = {
        "original_rows": original_rows,
        "cleaned_rows": cleaned_rows,
        "dedup_removed": dedup_removed,
        "null_rows_removed": after_dedup_rows - cleaned_rows,
    }
    return df, cleaning_stats


def _sanitize_column_names(df):
    """清理 DataFrame 列名，避免 PostgreSQL 保留字和特殊字符导致建表/COPY 失败"""
    # PostgreSQL 常见保留字（会导致 CREATE TABLE / COPY 失败的关键词）
    PG_RESERVED = {
        'order', 'user', 'group', 'table', 'column', 'index', 'select', 'insert',
        'update', 'delete', 'create', 'drop', 'alter', 'where', 'from', 'join',
        'limit', 'offset', 'having', 'union', 'all', 'and', 'or', 'not', 'null',
        'true', 'false', 'default', 'primary', 'key', 'foreign', 'references',
        'check', 'unique', 'constraint', 'grant', 'revoke', 'end', 'case', 'when',
        'then', 'else', 'do', 'for', 'in', 'to', 'as', 'by', 'on', 'is', 'like',
        'between', 'exists', 'desc', 'asc', 'values', 'set', 'into', 'with',
        'type', 'comment', 'database', 'schema', 'sequence', 'trigger', 'view',
        'function', 'procedure', 'role', 'session', 'time', 'timestamp', 'date',
        'interval', 'array', 'row', 'cross', 'natural', 'left', 'right', 'full',
        'inner', 'outer', 'using', 'any', 'some', 'cast', 'current', 'position',
    }
    
    new_cols = []
    seen = {}  # 用于去重
    
    for i, col in enumerate(df.columns):
        col_str = str(col).strip()
        
        # 剥离 UTF-8 BOM 字符（\ufeff），防止列名前缀带不可见字符
        # 即使上游 read_csv 使用了 utf-8-sig，这里也做防御性清理
        col_str = col_str.lstrip('\ufeff')
        
        # 空列名处理
        if not col_str or col_str in ('', 'nan', 'None', 'Unnamed'):
            col_str = f'col_{i + 1}'
        elif col_str.startswith('Unnamed:'):
            col_str = f'col_{i + 1}'
        
        # 移除双引号（防止 SQL 注入）
        col_str = col_str.replace('"', '')
        
        # 保留字处理：追加下划线
        if col_str.lower() in PG_RESERVED:
            col_str = col_str + '_'
        
        # 重复列名处理
        base = col_str
        count = seen.get(base.lower(), 0)
        if count > 0:
            col_str = f'{base}_{count + 1}'
        seen[base.lower()] = count + 1
        
        new_cols.append(col_str)
    
    if list(df.columns) != new_cols:
        from common.utils.utils import ChatBILogUtil
        changed = [(str(old), new) for old, new in zip(df.columns, new_cols) if str(old) != new]
        if changed:
            ChatBILogUtil.info(f"列名清理: {changed[:10]}{'...' if len(changed) > 10 else ''}")
        df.columns = new_cols
    
    return df


def insert_pg(df, tableName, engine):
    from common.utils.utils import ChatBILogUtil
    
    ChatBILogUtil.info(f"[COLUMN-TRACE] insert_pg入口 columns: {list(df.columns)}")
    
    # 步骤4：数据清洗（去重、空值处理、格式统一、异常值过滤）
    df, cleaning_stats = _clean_dataframe(df)
    
    ChatBILogUtil.info(f"[COLUMN-TRACE] _clean_dataframe后 columns: {list(df.columns)}")
    
    # 保存清洗后、sanitize前的原始列名（用于后续写入PG列注释）
    # Excel/CSV的原始列名可能是中文，sanitize后可能变化（保留字追加下划线等）
    _original_columns = [str(c).strip() for c in df.columns]
    
    # 清理列名，处理 PostgreSQL 保留字和特殊字符
    df = _sanitize_column_names(df)
    
    ChatBILogUtil.info(f"[COLUMN-TRACE] _sanitize_column_names后 columns: {list(df.columns)}")
    
    # fix field type
    for i in range(len(df.dtypes)):
        if str(df.dtypes[i]) == 'uint64':
            df[str(df.columns[i])] = df[str(df.columns[i])].astype('string')

    conn = engine.raw_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        # 仅创建表结构（不插入数据），使用 head(0) 获取空 DataFrame 保留列定义
        df.head(0).to_sql(
            tableName,
            engine,
            if_exists='replace',
            index=False
        )
        
        # 日志追踪：验证PG表实际创建的列名
        try:
            _verify_result = conn.cursor()
            _verify_result.execute(
                f"SELECT column_name FROM information_schema.columns "
                f"WHERE table_name = '{tableName}' ORDER BY ordinal_position"
            )
            _pg_cols = [row[0] for row in _verify_result.fetchall()]
            _verify_result.close()
            ChatBILogUtil.info(f"[COLUMN-TRACE] PG表实际列名 (to_sql后): {_pg_cols}")
        except Exception as _trace_e:
            ChatBILogUtil.warning(f"[COLUMN-TRACE] 无法验证PG列名: {_trace_e}")
        # 使用 COPY 批量导入数据（比 to_sql 的逐行 INSERT 性能更好）
        for col in df.columns:
            _col_dtype = str(df[col].dtype).lower()
            if _col_dtype in ('object', 'str', 'string'):
                df[col] = df[col].str.replace('\x01', ' ', regex=False)
        output = StringIO()
        df.to_csv(output, sep='\x01', header=False, index=False)
        output.seek(0)

        # pg copy
        cursor.copy_expert(
            sql=f"""COPY "{tableName}" FROM STDIN WITH (FORMAT CSV, DELIMITER E'\x01', ENCODING 'UTF8')""",
            file=output
        )
        conn.commit()
        
        # 将原始列名写入PG列注释（COMMENT ON COLUMN）
        try:
            _final_columns = list(df.columns)
            _comment_count = 0
            for _orig, _final in zip(_original_columns, _final_columns):
                _orig_stripped = _orig.strip()
                # 始终写入列注释（保留原始列名，无论是否被sanitize修改）
                if _orig_stripped:
                    _safe_comment = _orig_stripped.replace("'", "''")
                    _safe_col = str(_final).replace('"', '""')
                    cursor.execute(
                        f'COMMENT ON COLUMN "{tableName}"."{_safe_col}" IS \'{_safe_comment}\''
                    )
                    _comment_count += 1
            conn.commit()
            ChatBILogUtil.info(f"[COLUMN-TRACE] 写入{_comment_count}个列注释, 原始列名={_original_columns}, PG列名={_final_columns}")
        except Exception as _comment_e:
            from common.utils.utils import ChatBILogUtil
            ChatBILogUtil.warning(f"Failed to set column comments: {_comment_e}")
            try:
                conn.rollback()
            except Exception:
                pass
    except Exception as e:
        # 异常时必须 rollback，否则连接处于未完成事务状态，
        # 归还连接池后下一次使用该连接会报 "InFailedSqlTransaction" 错误
        try:
            conn.rollback()
        except Exception:
            pass
        from common.utils.utils import ChatBILogUtil
        ChatBILogUtil.exception()
        raise HTTPException(status_code=400, detail=_ds_trans()('i18n_file.import_failed'))
    finally:
        if cursor:
            cursor.close()
        # raw_connection() 返回的是底层 DBAPI 连接，
        conn.close()
    return cleaning_stats



ALLOWED_DOC_EXTENSIONS = {"pdf", "xlsx", "xls", "csv"}


@router.post("/document/parse")
async def parse_document(
    session: SessionDep,
    current_user: CurrentUser,
    file: UploadFile = File(...)
):
    """文档解析接口：上传文档并执行完整的解析→分块→向量化流程

    支持格式：PDF、Excel、CSV
    返回：解析结果摘要（文本块数量、元数据等）
    同时将文档元信息和分块存入数据库
    """
    filename = file.filename or "unknown"
    file_ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if file_ext not in ALLOWED_DOC_EXTENSIONS:
        _t = _ds_trans(current_user)
        raise HTTPException(
            status_code=400,
            detail=_t('i18n_file.unsupported_format', ext=file_ext, types=', '.join(ALLOWED_DOC_EXTENSIONS))
        )

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        _t = _ds_trans(current_user)
        raise HTTPException(status_code=400, detail=_t('i18n_file.size_limit', max=MAX_UPLOAD_SIZE_MB, current=f"{len(content) / 1024 / 1024:.1f}"))

    upload_path = _get_upload_path(file_ext)
    temp_filename = f"doc_{hashlib.sha256(uuid.uuid4().bytes).hexdigest()[:10]}.{file_ext}"
    save_path = os.path.join(upload_path, temp_filename)

    def inner():
        from apps.datasource.document_parser import DocumentPipeline
        from apps.datasource.models.document import CoreDocument, CoreDocumentChunk
        from datetime import datetime

        try:
            with open(save_path, "wb") as f:
                f.write(content)

            pipeline = DocumentPipeline()
            result = pipeline.process(save_path)

            chunks = result.get("chunks", [])
            vectorized = result.get("vectorized", [])
            stats = result.get("stats", {})

            # 存入业务数据库：文档元信息
            # 确定来源类型
            source_type_map = {
                'pdf': 'PDF',
                'xlsx': 'Excel', 'xls': 'Excel', 'csv': 'CSV',
            }
            doc_source_type = source_type_map.get(file_ext, 'file')

            doc = CoreDocument(
                filename=filename,
                file_type=f".{file_ext}",
                file_size=len(content),
                file_path=save_path,
                total_chunks=stats.get("total_chunks", 0),
                vectorized_count=stats.get("vectorized_count", 0),
                total_sections=stats.get("total_sections", 0),
                total_tables=stats.get("total_tables", 0),
                processing_time=stats.get("total_time", 0),
                oid=current_user.oid or 1,
                user_id=current_user.id,
                create_time=datetime.now(),
                source_type=doc_source_type,
                source_name=filename,
                # 存储完整原始文本，确保"零丢失解析"可验证
                raw_text=result.get("parse_result").raw_text if result.get("parse_result") else None,
            )
            session.add(doc)
            session.flush()

            # 存入数据库：文档分块（含向量）
            for i, chunk in enumerate(chunks):
                chunk_record = CoreDocumentChunk(
                    document_id=doc.id,
                    chunk_index=i,
                    text=chunk.text,
                    source_file=chunk.metadata.get("source_file", ""),
                    section_title=chunk.metadata.get("section_title", ""),
                    page_number=chunk.metadata.get("page_number"),
                    chunk_type=chunk.metadata.get("chunk_type", ""),
                    create_time=datetime.now(),
                    source_type=doc_source_type,
                    source_name=filename,
                    library_id=doc.id,
                )
                session.add(chunk_record)

            # 存入向量（通过原生SQL写入pgvector列）
            # 使用 chunk_index 精确匹配（与 uploadPdf 一致），
            session.flush()
            if vectorized:
                from sqlalchemy import text as sa_text
                # 一次查询获取所有 chunk 的 id→chunk_index 映射
                all_chunk_recs = session.query(
                    CoreDocumentChunk.id, CoreDocumentChunk.chunk_index
                ).filter(
                    CoreDocumentChunk.document_id == doc.id
                ).all()
                index_to_id = {rec.chunk_index: rec.id for rec in all_chunk_recs}

                for v_item in vectorized:
                    embedding = v_item.get("embedding")
                    v_meta = v_item.get("metadata", {})
                    chunk_index = v_meta.get("chunk_index")
                    if embedding and chunk_index is not None and chunk_index in index_to_id:
                        emb_str = "[" + ",".join(str(x) for x in embedding) + "]"
                        session.execute(
                            sa_text(
                                "UPDATE core_document_chunk SET embedding = :emb WHERE id = :cid"
                            ),
                            {"emb": emb_str, "cid": index_to_id[chunk_index]}
                        )

            session.commit()

            try:
                log_file_uploaded(session, current_user.id, current_user.name or '',
                                  filename, file_type=f".{file_ext}", oid=current_user.oid or 1)
            except Exception:
                pass

            # 记录解析日志到 parse_log 表
            try:
                from apps.datasource.models.document import ParseLog
                parse_log = ParseLog(
                    document_id=doc.id,
                    source_type=doc_source_type,
                    source_name=filename,
                    status='success',
                    total_chunks=stats.get("total_chunks", 0),
                    vectorized_count=stats.get("vectorized_count", 0),
                    processing_time=stats.get("total_time", 0),
                    oid=current_user.oid or 1,
                    user_id=current_user.id,
                    create_time=datetime.now(),
                )
                session.add(parse_log)
                session.commit()
            except Exception as log_err:
                ChatBILogUtil.warning(f"记录解析日志失败: {log_err}")

            return {
                "success": True,
                "id": doc.id,
                "filename": filename,
                "total_chunks": stats.get("total_chunks", 0),
                "metadata": {
                    "file_type": stats.get("file_type", ""),
                    "total_sections": stats.get("total_sections", 0),
                    "total_tables": stats.get("total_tables", 0),
                    "vectorized_count": stats.get("vectorized_count", 0),
                    "processing_time": stats.get("total_time", 0),
                },
                "pipeline_stages": [
                    "文档解析（Document Parsing）",
                    "文本预处理（Preprocessing）",
                    "语义分块（Text Chunking）",
                    "向量化嵌入（Embedding）",
                    "向量库存储（Vector Store）",
                ],
                "chunks_preview": [
                    {
                        "text": c.text[:200] + "..." if len(c.text) > 200 else c.text,
                        "metadata": c.metadata,
                    }
                    for c in chunks[:5]
                ],
            }
        except Exception as e:
            session.rollback()
            # 失败时清理已保存的临时文件（与 upload_pdf 一致）
            if os.path.exists(save_path):
                try:
                    os.remove(save_path)
                except OSError:
                    pass
            ChatBILogUtil.error(f"文档处理失败: {e}")
            # 记录失败的解析日志
            try:
                from apps.datasource.models.document import ParseLog
                from datetime import datetime as dt_err
                err_log = ParseLog(
                    source_type=locals().get('source_type_map', {}).get(file_ext, 'file'),
                    source_name=filename,
                    status='failed',
                    error_message=str(e)[:500],
                    oid=current_user.oid or 1,
                    user_id=current_user.id,
                    create_time=dt_err.now(),
                )
                session.add(err_log)
                session.commit()
            except Exception:
                pass
            raise HTTPException(status_code=500, detail=_ds_trans(current_user)('i18n_file.doc_process_failed', msg=str(e)))

    return await asyncio.to_thread(inner)


@router.get("/document/list")
async def list_documents(session: SessionDep, current_user: CurrentUser):
    """获取已上传的文档列表"""
    from apps.datasource.models.document import CoreDocument

    docs = session.query(CoreDocument).filter(
        CoreDocument.oid == (current_user.oid or 1)
    ).order_by(CoreDocument.id.desc()).all()

    return [
        {
            "id": d.id,
            "filename": d.filename,
            "file_type": d.file_type,
            "file_size": d.file_size,
            "total_chunks": d.total_chunks,
            "vectorized_count": d.vectorized_count,
            "total_sections": d.total_sections,
            "total_tables": d.total_tables,
            "processing_time": d.processing_time,
            "source_type": d.source_type or ('CSV' if d.file_type == '.csv' else 'Excel'),
            "source_name": d.source_name or d.filename,
            "create_time": d.create_time.isoformat() if d.create_time else None,
        }
        for d in docs
    ]


@router.post("/document/delete/{doc_id}")
async def delete_document(session: SessionDep, current_user: CurrentUser, doc_id: int):
    """删除文档及其所有分块"""
    from apps.datasource.models.document import CoreDocument, CoreDocumentChunk

    doc = session.get(CoreDocument, doc_id)
    if not doc:
        _t = _ds_trans(current_user)
        raise HTTPException(status_code=404, detail=_t('i18n_document.not_found'))
    if doc.oid != (current_user.oid or 1):
        _t = _ds_trans(current_user)
        raise HTTPException(status_code=403, detail=_t('i18n_document.no_permission'))

    # 删除分块
    session.query(CoreDocumentChunk).filter(CoreDocumentChunk.document_id == doc_id).delete()
    # 删除文档记录
    session.delete(doc)
    session.commit()

    # 清理文件
    if doc.file_path and os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except OSError:
            pass

    return {"success": True}


@router.get("/document/chunks/{doc_id}")
async def get_document_chunks(session: SessionDep, current_user: CurrentUser, doc_id: int):
    """获取文档的分块详情"""
    from apps.datasource.models.document import CoreDocument, CoreDocumentChunk

    doc = session.get(CoreDocument, doc_id)
    if not doc:
        _t = _ds_trans(current_user)
        raise HTTPException(status_code=404, detail=_t('i18n_document.not_found'))
    if doc.oid != (current_user.oid or 1):
        _t = _ds_trans(current_user)
        raise HTTPException(status_code=403, detail=_t('i18n_document.no_permission'))

    chunks = session.query(CoreDocumentChunk).filter(
        CoreDocumentChunk.document_id == doc_id
    ).order_by(CoreDocumentChunk.chunk_index).all()

    return {
        "document": {
            "id": doc.id,
            "filename": doc.filename,
            "file_type": doc.file_type,
        },
        "chunks": [
            {
                "id": c.id,
                "chunk_index": c.chunk_index,
                "text": c.text,
                "metadata": {
                    "source_file": c.source_file,
                    "section_title": c.section_title,
                    "page_number": c.page_number,
                    "chunk_type": c.chunk_type,
                },
            }
            for c in chunks
        ],
    }


@router.get("/document/byDatasource/{ds_id}")
async def get_document_by_datasource(session: SessionDep, current_user: CurrentUser, ds_id: int):
    """根据数据源ID获取关联的PDF文档信息和分块预览

    查找策略（按优先级）：
    1. 通过 CoreDocument.ds_id 直接关联
    2. 从 configuration 中读取 document_id
    3. 通过文件名匹配查找 CoreDocument 记录
    """
    from apps.datasource.models.document import CoreDocument, CoreDocumentChunk

    ds = session.get(CoreDatasource, ds_id)
    if not ds:
        _t = _ds_trans(current_user)
        raise HTTPException(status_code=404, detail=_t('i18n_document.ds_not_found'))

    # 宽松检测：type='pdf' 或 type_name='PDF' 或 configuration中有document_id
    is_pdf = ds.type == "pdf" or (ds.type_name and ds.type_name.upper() == "PDF")
    if not is_pdf:
        # 额外检查configuration中是否有document_id（兼容旧数据）
        try:
            conf = json.loads(aes_decrypt(ds.configuration))
            if conf.get("document_id"):
                is_pdf = True
        except Exception:
            pass
    if not is_pdf:
        _t = _ds_trans(current_user)
        raise HTTPException(status_code=400, detail=_t('i18n_document.not_pdf_ds'))

    user_oid = current_user.oid or 1
    doc = None

    # 策略1：通过 ds_id 直接关联（最可靠）
    doc = session.query(CoreDocument).filter(
        CoreDocument.ds_id == ds_id
    ).order_by(CoreDocument.create_time.desc()).first()

    # 策略2：从 configuration 中获取 document_id
    if not doc:
        try:
            conf = json.loads(aes_decrypt(ds.configuration))
            doc_id = conf.get("document_id")
            if doc_id:
                doc = session.query(CoreDocument).filter(
                    CoreDocument.id == doc_id
                ).first()
                # 找到后回填 ds_id 以便下次直接查找
                if doc and not doc.ds_id:
                    doc.ds_id = ds_id
                    session.add(doc)
                    try:
                        session.commit()
                    except Exception:
                        session.rollback()
        except Exception:
            pass

    # 策略3：通过文件名匹配
    if not doc:
        try:
            conf = json.loads(aes_decrypt(ds.configuration))
            filename = conf.get("filename", "")
            if filename:
                name_no_ext = filename.rsplit('.', 1)[0] if '.' in filename else filename
                original_name = name_no_ext.rsplit('_', 1)[0] if '_' in name_no_ext else name_no_ext

                doc = session.query(CoreDocument).filter(
                    CoreDocument.file_type == ".pdf",
                    CoreDocument.filename.ilike(f"%{original_name}%"),
                    CoreDocument.oid == user_oid
                ).order_by(CoreDocument.create_time.desc()).first()

                if not doc:
                    doc = session.query(CoreDocument).filter(
                        CoreDocument.file_type == ".pdf",
                        CoreDocument.filename.ilike(f"%{original_name}%")
                    ).order_by(CoreDocument.create_time.desc()).first()

                # 找到后回填 ds_id
                if doc and not doc.ds_id:
                    doc.ds_id = ds_id
                    session.add(doc)
                    try:
                        session.commit()
                    except Exception:
                        session.rollback()
        except Exception:
            pass

    if not doc:
        return {
            "document": None,
            "chunks": [],
            "stats": {"total_chunks": 0, "total_sections": 0, "total_tables": 0, "total_pages": 0, "text_chunks": 0, "table_chunks": 0},
            "sections": []
        }

    chunks = session.query(CoreDocumentChunk).filter(
        CoreDocumentChunk.document_id == doc.id
    ).order_by(CoreDocumentChunk.chunk_index).all()

    # ── 统计各类分块信息（用于前端 RAG 流水线展示） ──
    sections = set()
    pages = set()
    text_chunks = 0
    table_chunks = 0
    table_overlap_chunks = 0
    sliding_window_chunks = 0
    section_split_chunks = 0
    vectorized_chunks = 0
    skipped_chunks = 0
    total_chunk_chars = 0
    embedding_dim = None

    for c in chunks:
        if c.section_title:
            sections.add(c.section_title)
        if c.page_number:
            pages.add(c.page_number)
        ct = c.chunk_type or "text"
        if ct == "table":
            table_chunks += 1
        elif ct == "table_overlap":
            table_overlap_chunks += 1
        elif ct == "section_split":
            section_split_chunks += 1
        elif ct == "sliding_window":
            sliding_window_chunks += 1
        else:
            text_chunks += 1
        total_chunk_chars += len(c.text) if c.text else 0
        if c.embedding is not None:
            vectorized_chunks += 1
            if embedding_dim is None:
                try:
                    embedding_dim = len(c.embedding)
                except Exception:
                    pass
        else:
            skipped_chunks += 1

    raw_text_length = len(doc.raw_text) if doc.raw_text else 0

    return {
        "document": {
            "id": doc.id,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "file_size": doc.file_size,
            "total_chunks": doc.total_chunks,
            "vectorized_count": doc.vectorized_count,
            "total_sections": doc.total_sections,
            "total_tables": doc.total_tables,
            "processing_time": doc.processing_time,
            "raw_text_length": raw_text_length,
            "raw_text_preview": (doc.raw_text[:2000] if doc.raw_text else ""),
            "create_time": doc.create_time.isoformat() if doc.create_time else None,
        },
        "chunks": [
            {
                "id": c.id,
                "chunk_index": c.chunk_index,
                "text": c.text[:500] if c.text else "",
                "full_text": c.text or "",
                "full_length": len(c.text) if c.text else 0,
                "section_title": c.section_title,
                "page_number": c.page_number,
                "chunk_type": c.chunk_type or "text",
                "has_embedding": c.embedding is not None,
            }
            for c in chunks
        ],
        "stats": {
            "total_chunks": len(chunks),
            "total_sections": len(sections),
            "total_pages": len(pages),
            "text_chunks": text_chunks,
            "table_chunks": table_chunks,
            "table_overlap_chunks": table_overlap_chunks,
            "sliding_window_chunks": sliding_window_chunks,
            "section_split_chunks": section_split_chunks,
            "vectorized_count": doc.vectorized_count or 0,
            "vectorized_actual": vectorized_chunks,
            "skipped_count": skipped_chunks,
            "raw_text_length": raw_text_length,
            "total_chunk_chars": total_chunk_chars,
        },
        "vectorization": {
            "embedding_model": "BAAI/bge-base-zh-v1.5",
            "embedding_dim": embedding_dim or 768,
            "vector_db": "pgvector",
            "index_type": "HNSW",
            "similarity_metric": "cosine",
            "vectorized_count": vectorized_chunks,
            "skipped_count": skipped_chunks,
            "total_chunks": len(chunks),
            "skip_reasons": {
                "table_overlap": table_overlap_chunks,
                "short_text": skipped_chunks - table_overlap_chunks if skipped_chunks > table_overlap_chunks else 0,
            },
        },
        "sections": sorted(list(sections)),
    }


