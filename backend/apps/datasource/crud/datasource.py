import datetime
import json
import re
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import and_, text
from common.chatbi.permissions import DsRules
from sqlmodel import select

from apps.datasource.crud.permission import get_column_permission_fields, get_row_permission_filters, is_normal_user
from apps.datasource.embedding.table_embedding import calc_table_embedding
from apps.datasource.utils.utils import aes_decrypt
from apps.db.constant import DB
from apps.db.db import get_tables, get_fields, exec_sql, check_connection
from apps.db.engine import get_engine_config, get_engine_conn
from common.core.config import settings
from common.core.deps import SessionDep, CurrentUser, Trans
from common.utils.embedding_threads import run_save_table_embeddings, run_save_ds_embeddings
from common.utils.utils import deepcopy_ignore_extra
from common.utils.utils import equals_ignore_case
from common.utils.utils import ChatBILogUtil
from .table import get_tables_by_ds_id
from ..crud.field import delete_field_by_ds_id, update_field
from ..crud.table import delete_table_by_ds_id, update_table
from ..models.datasource import CoreDatasource, CreateDatasource, CoreTable, CoreField, ColumnSchema, TableObj, \
    DatasourceConf, TableAndFields


def get_datasource_list(session: SessionDep, user: CurrentUser, oid: Optional[int] = None) -> List[CoreDatasource]:
    current_oid = user.oid if user.oid is not None else 1
    if user.isAdmin and oid:
        current_oid = oid
    return session.exec(
        select(CoreDatasource).where(CoreDatasource.oid == current_oid).order_by(CoreDatasource.name)).all()


def get_ds(session: SessionDep, id: int):
    statement = select(CoreDatasource).where(CoreDatasource.id == id)
    datasource = session.exec(statement).first()
    return datasource


def check_status_by_id(session: SessionDep, trans: Trans, ds_id: int, is_raise: bool = False):
    ds = session.get(CoreDatasource, ds_id)
    if ds is None:
        if is_raise:
            raise HTTPException(status_code=500, detail=trans('i18n_ds_invalid'))
        return False
    return check_status(session, trans, ds, is_raise)


def check_status(session: SessionDep, trans: Trans, ds: CoreDatasource, is_raise: bool = False):
    # PDF/Excel/CSV 是文件类型数据源，无需检测数据库连接
    if ds.type and ds.type.lower() in ('pdf', 'excel', 'csv'):
        return True
    return check_connection(trans, ds, is_raise)


def check_name(session: SessionDep, trans: Trans, user: CurrentUser, ds: CoreDatasource):
    if ds.id is not None:
        ds_list = session.query(CoreDatasource).filter(
            and_(CoreDatasource.name == ds.name, CoreDatasource.id != ds.id, CoreDatasource.oid == user.oid)).all()
        if ds_list is not None and len(ds_list) > 0:
            raise HTTPException(status_code=500, detail=trans('i18n_ds_name_exist'))
    else:
        ds_list = session.query(CoreDatasource).filter(
            and_(CoreDatasource.name == ds.name, CoreDatasource.oid == user.oid)).all()
        if ds_list is not None and len(ds_list) > 0:
            raise HTTPException(status_code=500, detail=trans('i18n_ds_name_exist'))


def create_ds(session: SessionDep, trans: Trans, user: CurrentUser, create_ds: CreateDatasource):
    ds = CoreDatasource()
    deepcopy_ignore_extra(create_ds, ds)
    check_name(session, trans, user, ds)
    ds.create_time = datetime.datetime.now()
    # status = check_status(session, ds)
    ds.create_by = user.id
    ds.oid = user.oid if user.oid is not None else 1
    ds.status = "Success"
    ds.type_name = DB.get_db(ds.type).db_name
    record = CoreDatasource(**ds.model_dump())
    session.add(record)
    session.flush()
    session.refresh(record)
    ds.id = record.id
    session.commit()

    # save tables and fields
    sync_table(session, ds, create_ds.tables)
    updateNum(session, ds)
    return ds


def chooseTables(session: SessionDep, trans: Trans, id: int, tables: List[CoreTable]):
    ds = session.query(CoreDatasource).filter(CoreDatasource.id == id).first()
    check_status(session, trans, ds, True)
    sync_table(session, ds, tables)
    updateNum(session, ds)


def update_ds(session: SessionDep, trans: Trans, user: CurrentUser, ds: CoreDatasource):
    ds.id = int(ds.id)
    check_name(session, trans, user, ds)
    # status = check_status(session, trans, ds)
    ds.status = "Success"
    record = session.exec(select(CoreDatasource).where(CoreDatasource.id == ds.id)).first()
    update_data = ds.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(record, field, value)
    session.add(record)
    session.commit()

    # 数据源配置变更后清理缓存的 Engine 实例，防止使用过期凭据
    from apps.db.db import invalidate_engine_cache
    invalidate_engine_cache(ds.id)

    run_save_ds_embeddings([ds.id])
    return ds


def delete_ds(session: SessionDep, id: int):
    term = session.exec(select(CoreDatasource).where(CoreDatasource.id == id)).first()
    # 添加空值检查，防止数据源不存在时 AttributeError
    if not term:
        return {"message": f"Datasource with ID {id} not found."}

    # PDF级联清理必须在删除数据源之前执行（同一事务内）
    pdf_file_paths = []

    if term.type == "pdf":
        # PDF数据源：级联清理文档分块、向量数据、物理文件
        try:
            import os
            from apps.datasource.models.document import CoreDocument, CoreDocumentChunk
            docs = session.query(CoreDocument).filter(CoreDocument.ds_id == id).all()
            if docs:
                doc_ids = [d.id for d in docs]
                # 收集物理文件路径（在删除记录前获取）
                for d in docs:
                    if d.file_path:
                        pdf_file_paths.append(d.file_path)
                # 先删除分块（子表），再删除文档（父表）
                session.query(CoreDocumentChunk).filter(
                    CoreDocumentChunk.document_id.in_(doc_ids)
                ).delete(synchronize_session=False)
                session.query(CoreDocument).filter(CoreDocument.ds_id == id).delete(synchronize_session=False)
                ChatBILogUtil.info(f"Cascade marked {len(docs)} documents and their chunks for deletion (ds_id={id})")
        except Exception as e:
            ChatBILogUtil.error(f"Failed to cascade delete documents for ds_id={id}: {e}")

    if term.type in ["excel", "csv"]:
        # Excel/CSV数据源：删除导入到PG的数据表
        try:
            engine = get_engine_conn()
            conf = DatasourceConf(**json.loads(aes_decrypt(term.configuration)))
            with engine.connect() as conn:
                for sheet in conf.sheets:
                    table_name = sheet["tableName"]
                    # 验证表名，防止SQL注入
                    if not table_name or not all(c.isalnum() or c in ('_', '-') for c in table_name):
                        continue
                    conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}"'))
                conn.commit()
        except Exception as e:
            ChatBILogUtil.error(f"Failed to drop tables for ds_id={id}: {e}")
            # 解密失败或表删除失败不阻塞数据源记录删除
            # 残留的PG表不影响功能，可后续手动清理

    # 删除数据源主记录 + 关联的表/字段元数据（统一 commit）
    session.delete(term)
    delete_table_by_ds_id(session, id)
    delete_field_by_ds_id(session, id)
    session.commit()

    # 删除PDF物理文件（在数据库事务成功后执行）
    import os
    for fp in pdf_file_paths:
        try:
            if os.path.exists(fp):
                os.remove(fp)
                ChatBILogUtil.info(f"Deleted PDF file: {fp}")
        except OSError as e:
            ChatBILogUtil.warning(f"Failed to delete PDF file {fp}: {e}")

    # 删除数据源时清理缓存的 Engine 实例
    from apps.db.db import invalidate_engine_cache
    invalidate_engine_cache(id)

    return {
        "message": f"Datasource with ID {id} deleted successfully."
    }


def getTables(session: SessionDep, id: int):
    ds = session.exec(select(CoreDatasource).where(CoreDatasource.id == id)).first()
    # 空值检查，防止数据源不存在时 AttributeError
    if not ds:
        raise HTTPException(status_code=404, detail=f"Datasource with ID {id} not found")
    tables = get_tables(ds)
    return tables


def getTablesByDs(session: SessionDep, ds: CoreDatasource):
    # check_status(session, ds, True)
    tables = get_tables(ds)
    return tables


def getFields(session: SessionDep, id: int, table_name: str):
    ds = session.exec(select(CoreDatasource).where(CoreDatasource.id == id)).first()
    # 空值检查，防止数据源不存在时 AttributeError
    if not ds:
        raise HTTPException(status_code=404, detail=f"Datasource with ID {id} not found")
    fields = get_fields(ds, table_name)
    return fields


def getFieldsByDs(session: SessionDep, ds: CoreDatasource, table_name: str):
    fields = get_fields(ds, table_name)
    return fields


def execSql(session: SessionDep, id: int, sql: str):
    ds = session.exec(select(CoreDatasource).where(CoreDatasource.id == id)).first()
    # 空值检查，防止数据源不存在时 AttributeError
    if not ds:
        raise HTTPException(status_code=404, detail=f"Datasource with ID {id} not found")
    return exec_sql(ds, sql, True)


def sync_table(session: SessionDep, ds: CoreDatasource, tables: List[CoreTable]):
    id_list = []
    for item in tables:
        statement = select(CoreTable).where(and_(CoreTable.ds_id == ds.id, CoreTable.table_name == item.table_name))
        record = session.exec(statement).first()
        # update exist table, only update table_comment
        if record is not None:
            item.id = record.id
            id_list.append(record.id)

            record.table_comment = item.table_comment
            session.add(record)
            session.commit()
        else:
            # save new table
            table = CoreTable(ds_id=ds.id, checked=True, table_name=item.table_name, table_comment=item.table_comment,
                              custom_comment=item.table_comment)
            session.add(table)
            session.flush()
            session.refresh(table)
            item.id = table.id
            id_list.append(table.id)
            session.commit()

        # sync field
        fields = getFieldsByDs(session, ds, item.table_name)
        sync_fields(session, ds, item, fields)

    if len(id_list) > 0:
        session.query(CoreTable).filter(and_(CoreTable.ds_id == ds.id, CoreTable.id.not_in(id_list))).delete(
            synchronize_session=False)
        session.query(CoreField).filter(and_(CoreField.ds_id == ds.id, CoreField.table_id.not_in(id_list))).delete(
            synchronize_session=False)
        session.commit()
    else:  # delete all tables and fields in this ds
        session.query(CoreTable).filter(CoreTable.ds_id == ds.id).delete(synchronize_session=False)
        session.query(CoreField).filter(CoreField.ds_id == ds.id).delete(synchronize_session=False)
        session.commit()

    # do table embedding
    run_save_table_embeddings(id_list)
    run_save_ds_embeddings([ds.id])


def sync_fields(session: SessionDep, ds: CoreDatasource, table: CoreTable, fields: List[ColumnSchema]):
    from common.utils.utils import ChatBILogUtil
    ChatBILogUtil.info(
        f"[COLUMN-TRACE] sync_fields table={table.table_name}, "
        f"fields=[{', '.join(f'{f.fieldName}(comment={f.fieldComment})' for f in fields)}]"
    )
    id_list = []
    for index, item in enumerate(fields):
        statement = select(CoreField).where(
            and_(CoreField.table_id == table.id, CoreField.field_name == item.fieldName))
        record = session.exec(statement).first()
        if record is not None:
            item.id = record.id
            id_list.append(record.id)

            record.field_comment = item.fieldComment
            record.field_index = index
            record.field_type = item.fieldType
            session.add(record)
            session.commit()
        else:
            field = CoreField(ds_id=ds.id, table_id=table.id, checked=True, field_name=item.fieldName,
                              field_type=item.fieldType, field_comment=item.fieldComment,
                              custom_comment=item.fieldComment, field_index=index)
            session.add(field)
            session.flush()
            session.refresh(field)
            item.id = field.id
            id_list.append(field.id)
            session.commit()

    if len(id_list) > 0:
        session.query(CoreField).filter(and_(CoreField.table_id == table.id, CoreField.id.not_in(id_list))).delete(
            synchronize_session=False)
        session.commit()


def update_table_and_fields(session: SessionDep, data: TableObj):
    update_table(session, data.table)
    for field in data.fields:
        update_field(session, field)

    # do table embedding
    run_save_table_embeddings([data.table.id])
    run_save_ds_embeddings([data.table.ds_id])


def updateTable(session: SessionDep, table: CoreTable):
    update_table(session, table)

    # do table embedding
    run_save_table_embeddings([table.id])
    run_save_ds_embeddings([table.ds_id])


def updateField(session: SessionDep, field: CoreField):
    update_field(session, field)

    # do table embedding
    run_save_table_embeddings([field.table_id])
    run_save_ds_embeddings([field.ds_id])


def preview(session: SessionDep, current_user: CurrentUser, id: int, data: TableObj):
    ds = session.query(CoreDatasource).filter(CoreDatasource.id == id).first()
    if not ds:
        return {"fields": [], "data": [], "sql": ''}

    if data.fields is None or len(data.fields) == 0:
        return {"fields": [], "data": [], "sql": ''}

    where = ''
    f_list = [f for f in data.fields if f.checked]
    if is_normal_user(current_user):
        # column is checked, and, column permission for data.fields
        contain_rules = session.query(DsRules).all()
        f_list = get_column_permission_fields(session=session, current_user=current_user, table=data.table,
                                              fields=f_list, contain_rules=contain_rules)

        # row permission tree
        where_str = ''
        filter_mapping = get_row_permission_filters(session=session, current_user=current_user, ds=ds, tables=None,
                                                    single_table=data.table)
        if filter_mapping:
            mapping_dict = filter_mapping[0]
            where_str = mapping_dict.get('filter')
        where = (' where ' + where_str) if where_str is not None and where_str != '' else ''

    fields = [f.field_name for f in f_list]
    if fields is None or len(fields) == 0:
        return {"fields": [], "data": [], "sql": ''}

    # 安全加固：验证字段名和表名不含SQL注入字符
    _invalid_pattern = re.compile(r'[;\'"\\`]|--|\*/|/\*')
    for fname in fields:
        if _invalid_pattern.search(fname):
            raise HTTPException(status_code=400, detail=f"Invalid field name: {fname}")
    if _invalid_pattern.search(data.table.table_name):
        raise HTTPException(status_code=400, detail=f"Invalid table name: {data.table.table_name}")

    conf = DatasourceConf(**json.loads(aes_decrypt(ds.configuration))) if not equals_ignore_case(ds.type,
                                                                                                 "excel", "csv", "pdf") else get_engine_config()
    sql: str = ""
    if equals_ignore_case(ds.type, "mysql"):
        sql = f"""SELECT `{"`, `".join(fields)}` FROM `{data.table.table_name}` 
            {where} 
            LIMIT 100"""
    elif equals_ignore_case(ds.type, "pg", "excel", "csv", "pdf"):
        sql = f"""SELECT "{'", "'.join(fields)}" FROM "{conf.dbSchema}"."{data.table.table_name}" 
            {where} 
            LIMIT 100"""
    elif equals_ignore_case(ds.type, "oracle"):
        sql = f"""SELECT "{'", "'.join(fields)}" FROM
                    (SELECT "{'", "'.join(fields)}" FROM "{conf.dbSchema}"."{data.table.table_name}"
                    {where} 
                    ORDER BY "{fields[0]}")
                    WHERE ROWNUM <= 100
                    """
    return exec_sql(ds, sql, True)


def fieldEnum(session: SessionDep, id: int):
    field = session.query(CoreField).filter(CoreField.id == id).first()
    if field is None:
        return []
    table = session.query(CoreTable).filter(CoreTable.id == field.table_id).first()
    if table is None:
        return []
    ds = session.query(CoreDatasource).filter(CoreDatasource.id == table.ds_id).first()
    if ds is None:
        return []

    db = DB.get_db(ds.type)
    # 安全加固：验证字段名和表名
    _invalid_pattern = re.compile(r'[;\'"\\`]|--|\*/|/\*')
    if _invalid_pattern.search(field.field_name):
        return []
    if _invalid_pattern.search(table.table_name):
        return []
    sql = f"""SELECT DISTINCT {db.prefix}{field.field_name}{db.suffix} FROM {db.prefix}{table.table_name}{db.suffix}"""
    res = exec_sql(ds, sql, True)
    return [item.get(res.get('fields')[0]) for item in res.get('data')]


def updateNum(session: SessionDep, ds: CoreDatasource):
    if equals_ignore_case(ds.type, 'pdf'):
        # PDF: 从 CoreDocumentChunk 统计分块数
        chunk_count = 0
        try:
            from apps.datasource.models.document import CoreDocument, CoreDocumentChunk
            doc = None

            # 策略1：通过 ds_id 直接关联（最可靠）
            doc = session.query(CoreDocument).filter(
                CoreDocument.ds_id == ds.id
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
                except Exception:
                    pass

            if doc:
                chunk_count = session.query(CoreDocumentChunk).filter(
                    CoreDocumentChunk.document_id == doc.id
                ).count()
        except Exception:
            pass
        num = f'{chunk_count}'
    else:
        all_tables = get_tables(ds) if not equals_ignore_case(ds.type, 'excel', 'csv') else json.loads(aes_decrypt(ds.configuration)).get('sheets')
        selected_tables = get_tables_by_ds_id(session, ds.id)
        num = f'{len(selected_tables)}/{len(all_tables)}'

    record = session.exec(select(CoreDatasource).where(CoreDatasource.id == ds.id)).first()
    update_data = ds.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(record, field, value)
    record.num = num
    session.add(record)
    session.commit()


def get_table_obj_by_ds(session: SessionDep, current_user: CurrentUser, ds: CoreDatasource) -> List[TableAndFields]:
    _list: List = []
    tables = session.query(CoreTable).filter(CoreTable.ds_id == ds.id).all()
    conf = DatasourceConf(**json.loads(aes_decrypt(ds.configuration))) if not equals_ignore_case(ds.type,
                                                                                                 "excel", "csv", "pdf") else get_engine_config()
    schema = conf.dbSchema if conf.dbSchema is not None and conf.dbSchema != "" else conf.database

    # get all field
    table_ids = [table.id for table in tables]
    all_fields = session.query(CoreField).filter(
        and_(CoreField.table_id.in_(table_ids), CoreField.checked == True)).all()
    # build dict
    fields_dict = {}
    for field in all_fields:
        if fields_dict.get(field.table_id):
            fields_dict.get(field.table_id).append(field)
        else:
            fields_dict[field.table_id] = [field]

    contain_rules = session.query(DsRules).all()
    for table in tables:
        # fields = session.query(CoreField).filter(and_(CoreField.table_id == table.id, CoreField.checked == True)).all()
        fields = fields_dict.get(table.id)

        # do column permissions, filter fields
        fields = get_column_permission_fields(session=session, current_user=current_user, table=table, fields=fields,
                                              contain_rules=contain_rules)
        _list.append(TableAndFields(schema=schema, table=table, fields=fields))
    return _list


def get_table_schema(session: SessionDep, current_user: CurrentUser, ds: CoreDatasource, question: str,
                     embedding: bool = True) -> str:
    """获取表 schema 字符串（原始接口，保持向后兼容）"""
    result = get_table_schema_with_details(session, current_user, ds, question, embedding)
    return result['schema']


def get_table_schema_with_details(session: SessionDep, current_user: CurrentUser, ds: CoreDatasource, question: str,
                                  embedding: bool = True) -> dict:
    """获取表 schema 字符串 + 表匹配详情（供思考过程展示）"""
    schema_str = ""
    table_details = {
        'schema': '',
        'table_candidates': [],
        'selected_tables': [],
        'similarities': [],
    }
    table_objs = get_table_obj_by_ds(session=session, current_user=current_user, ds=ds)
    if len(table_objs) == 0:
        return table_details
    db_name = table_objs[0].schema
    schema_str += f"【DB_ID】 {db_name}\n【Schema】\n"
    tables = []
    all_tables = []  # temp save all tables
    # 记录表名映射（id → 表名/注释），用于后续构建 table_candidates
    _table_name_map = {}

    # 预取文本列的枚举值（低基数列），帮助 LLM 生成正确的 WHERE 条件
    _TEXT_TYPES = {'text', 'varchar', 'char', 'character varying', 'nvarchar', 'nchar', 'character'}
    _field_examples = {}  # key: (table_name, field_name), value: list[str]
    try:
        _ds_type_lower_enum = (ds.type or '').lower()
        for obj in table_objs:
            _tbl_name = obj.table.table_name
            if not obj.fields:
                continue
            for field in obj.fields:
                if not field.field_type:
                    continue
                ft = field.field_type.lower().split('(')[0].strip()
                if ft not in _TEXT_TYPES:
                    continue
                try:
                    _safe_tbl = '"' + _tbl_name.replace('"', '""') + '"'
                    _safe_fld = '"' + field.field_name.replace('"', '""') + '"'
                    _enum_sql = (
                        f'SELECT DISTINCT {_safe_fld} FROM {_safe_tbl} '
                        f'WHERE {_safe_fld} IS NOT NULL '
                        f'ORDER BY {_safe_fld} LIMIT 21'
                    )
                    _enum_values = []
                    if _ds_type_lower_enum in ('excel', 'csv'):
                        _engine_enum = get_engine_conn()
                        with _engine_enum.connect() as _conn_enum:
                            _rows = _conn_enum.execute(text(_enum_sql)).fetchall()
                            _enum_values = [str(r[0]) for r in _rows if r[0] is not None]
                    else:
                        from apps.db.db import exec_sql as _enum_exec_sql
                        _enum_result = _enum_exec_sql(ds=ds, sql=_enum_sql, origin_column=False)
                        if _enum_result and _enum_result.get('data'):
                            _flds = _enum_result.get('fields', [])
                            _fld_key = _flds[0] if _flds else field.field_name
                            _enum_values = [str(row.get(_fld_key, '')) for row in _enum_result['data']
                                            if row.get(_fld_key) is not None]
                    # 只注入低基数列（≤20个不同值），高基数列跳过
                    if 0 < len(_enum_values) <= 20:
                        _field_examples[(_tbl_name, field.field_name)] = _enum_values
                except Exception as _e:
                    ChatBILogUtil.warning(
                        f"[get_table_schema] Failed to query enum values for {_tbl_name}.{field.field_name}: {_e}")
    except Exception as _e:
        ChatBILogUtil.warning(f"[get_table_schema] Failed to pre-fetch enum values: {_e}")

    for obj in table_objs:
        schema_table = ''
        schema_table += f"# Table: {db_name}.{obj.table.table_name}" if ds.type != "mysql" else f"# Table: {obj.table.table_name}"
        table_comment = ''
        if obj.table.custom_comment:
            table_comment = obj.table.custom_comment.strip()
        if table_comment == '':
            schema_table += '\n[\n'
        else:
            schema_table += f", {table_comment}\n[\n"

        if obj.fields:
            field_list = []
            for field in obj.fields:
                field_comment = ''
                if field.custom_comment:
                    field_comment = field.custom_comment.strip()
                _examples = _field_examples.get((obj.table.table_name, field.field_name))
                _examples_str = ''
                if _examples:
                    _examples_str = ", examples:[" + ",".join(f"'{v}'" for v in _examples) + "]"
                if field_comment == '':
                    field_list.append(f"({field.field_name}:{field.field_type}{_examples_str})")
                else:
                    field_list.append(f"({field.field_name}:{field.field_type}, {field_comment}{_examples_str})")
            schema_table += ",\n".join(field_list)
        schema_table += '\n]\n'

        t_obj = {"id": obj.table.id, "schema_table": schema_table, "embedding": obj.table.embedding}
        tables.append(t_obj)
        all_tables.append(t_obj)
        _table_name_map[obj.table.id] = {
            'name': obj.table.table_name,
            'comment': (obj.table.custom_comment or obj.table.table_comment or '').strip(),
        }

    # 记录所有候选表（embedding 前）
    for t in all_tables:
        tid = t.get('id')
        info = _table_name_map.get(tid, {})
        table_details['table_candidates'].append({
            'name': info.get('name', ''),
            'comment': info.get('comment', ''),
            'similarity': 0.0,
        })

    # do table embedding
    if embedding and tables and settings.TABLE_EMBEDDING_ENABLED:
        tables = calc_table_embedding(tables, question)

    # 记录被选中的表及其相似度
    for t in tables:
        tid = t.get('id')
        info = _table_name_map.get(tid, {})
        sim = t.get('cosine_similarity', 0.0)
        table_details['selected_tables'].append(info.get('name', ''))
        table_details['similarities'].append(round(sim, 4) if isinstance(sim, float) else 0.0)
        # 更新候选表中对应项的相似度
        for cand in table_details['table_candidates']:
            if cand['name'] == info.get('name', ''):
                cand['similarity'] = round(sim, 4) if isinstance(sim, float) else 0.0

    # splice schema
    if tables:
        for s in tables:
            schema_str += s.get('schema_table')

    # field relation
    if tables and ds.table_relation:
        relations = list(filter(lambda x: x.get('shape') == 'edge', ds.table_relation))
        if relations:
            # Complete the missing table
            # get tables in relation, remove irrelevant relation
            embedding_table_ids = [s.get('id') for s in tables]
            all_relations = list(
                filter(lambda x: x.get('source').get('cell') in embedding_table_ids or x.get('target').get(
                    'cell') in embedding_table_ids, relations))

            # get relation table ids, sub embedding table ids
            relation_table_ids = []
            for r in all_relations:
                relation_table_ids.append(r.get('source').get('cell'))
                relation_table_ids.append(r.get('target').get('cell'))
            relation_table_ids = list(set(relation_table_ids))
            # get table dict
            table_records = session.query(CoreTable).filter(CoreTable.id.in_(list(map(int, relation_table_ids)))).all()
            table_dict = {}
            for ele in table_records:
                table_dict[ele.id] = ele.table_name

            # get lost table ids
            lost_table_ids = list(set(relation_table_ids) - set(embedding_table_ids))
            # get lost table schema and splice it
            lost_tables = list(filter(lambda x: x.get('id') in lost_table_ids, all_tables))
            if lost_tables:
                for s in lost_tables:
                    schema_str += s.get('schema_table')

            # get field dict
            relation_field_ids = []
            for relation in all_relations:
                relation_field_ids.append(relation.get('source').get('port'))
                relation_field_ids.append(relation.get('target').get('port'))
            relation_field_ids = list(set(relation_field_ids))
            field_records = session.query(CoreField).filter(CoreField.id.in_(list(map(int, relation_field_ids)))).all()
            field_dict = {}
            for ele in field_records:
                field_dict[ele.id] = ele.field_name

            if all_relations:
                schema_str += '【Foreign keys】\n'
                for ele in all_relations:
                    schema_str += f"{table_dict.get(int(ele.get('source').get('cell')))}.{field_dict.get(int(ele.get('source').get('port')))}={table_dict.get(int(ele.get('target').get('cell')))}.{field_dict.get(int(ele.get('target').get('port')))}\n"

    # 注入日期/时间字段的实际数据范围到 schema
    try:
        _ds_type_lower = (ds.type or '').lower()
        # 收集选中表的日期字段信息
        _date_field_info = []
        for obj in table_objs:
            _tbl_name = obj.table.table_name
            # 只处理被选中的表
            if _tbl_name not in table_details['selected_tables']:
                continue
            if not obj.fields:
                continue
            for field in obj.fields:
                if not field.field_type:
                    continue
                ft = field.field_type.lower()
                fn = (field.field_name or '').lower()
                is_date = any(t in ft for t in ['date', 'time', 'timestamp'])
                if not is_date:
                    is_date = any(t in fn for t in ['date', 'time', '日期', '时间', '年', '月'])
                if is_date:
                    _date_field_info.append({
                        'table': _tbl_name,
                        'field': field.field_name,
                        'type': field.field_type,
                    })

        if _date_field_info:
            _range_lines = []
            for dfi in _date_field_info:
                _tbl = dfi['table']
                _fld = dfi['field']
                try:
                    # 防 SQL 注入：禁止特殊字符
                    if re.search(r'[;\'"\\]', _tbl) or re.search(r'[;\'"\\]', _fld):
                        continue
                    _safe_tbl = '"' + _tbl.replace('"', '""') + '"'
                    _safe_fld = '"' + _fld.replace('"', '""') + '"'
                    _range_sql = f'SELECT MIN({_safe_fld}) AS min_val, MAX({_safe_fld}) AS max_val FROM {_safe_tbl}'

                    if _ds_type_lower in ('excel', 'csv'):
                        _engine = get_engine_conn()
                        with _engine.connect() as _conn:
                            _row = _conn.execute(text(_range_sql)).fetchone()
                            if _row and _row[0] is not None and _row[1] is not None:
                                _range_lines.append(
                                    f"{_tbl}.{_fld}: {_row[0]} ~ {_row[1]}"
                                )
                    else:
                        # 使用 apps.db.db.exec_sql（而非不存在的 db_connection_pool.exec_sql）
                        from apps.db.db import exec_sql as _range_exec_sql
                        _range_result = _range_exec_sql(ds=ds, sql=_range_sql, origin_column=False)
                        if _range_result and _range_result.get('data'):
                            _rd = _range_result['data'][0] if _range_result['data'] else {}
                            _min_v = _rd.get('min_val')
                            _max_v = _rd.get('max_val')
                            if _min_v is not None and _max_v is not None:
                                _range_lines.append(
                                    f"{_tbl}.{_fld}: {_min_v} ~ {_max_v}"
                                )
                except Exception as _e:
                    ChatBILogUtil.warning(f"[get_table_schema] Failed to query date range for {_tbl}.{_fld}: {_e}")
                    continue

            if _range_lines:
                schema_str += '【Data Time Range】\n'
                for _rl in _range_lines:
                    schema_str += _rl + '\n'
                ChatBILogUtil.info(f"[get_table_schema] Injected date range metadata: {_range_lines}")
    except Exception as _e:
        ChatBILogUtil.warning(f"[get_table_schema] Failed to inject date range metadata: {_e}")

    table_details['schema'] = schema_str
    return table_details
