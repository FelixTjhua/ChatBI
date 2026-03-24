import json
import time
from typing import List

from sqlalchemy import and_, select, update

from apps.ai_model.embedding import EmbeddingModelCache
from common.core.config import settings
from common.core.deps import SessionDep
from common.utils.utils import ChatBILogUtil
from ..models.datasource import CoreTable, CoreField, CoreDatasource


def delete_table_by_ds_id(session: SessionDep, id: int):
    session.query(CoreTable).filter(CoreTable.ds_id == id).delete(synchronize_session=False)
    session.commit()


def get_tables_by_ds_id(session: SessionDep, id: int):
    return session.query(CoreTable).filter(CoreTable.ds_id == id).order_by(
        CoreTable.table_name.asc()).all()


def update_table(session: SessionDep, item: CoreTable):
    record = session.query(CoreTable).filter(CoreTable.id == item.id).first()
    if not record:
        return
    record.checked = item.checked
    record.custom_comment = item.custom_comment
    session.add(record)
    session.commit()


def run_fill_empty_table_and_ds_embedding(session_maker):
    try:
        if not settings.TABLE_EMBEDDING_ENABLED:
            return

        session = session_maker()

        ChatBILogUtil.info('get tables')
        stmt = select(CoreTable.id).where(and_(CoreTable.embedding.is_(None)))
        results = session.execute(stmt).scalars().all()
        ChatBILogUtil.info('table result: ' + str(len(results)))
        save_table_embedding(session_maker, results)

        ChatBILogUtil.info('get datasource')
        ds_stmt = select(CoreDatasource.id).where(and_(CoreDatasource.embedding.is_(None)))
        ds_results = session.execute(ds_stmt).scalars().all()
        ChatBILogUtil.info('datasource result: ' + str(len(ds_results)))
        save_ds_embedding(session_maker, ds_results)
    except Exception:
        ChatBILogUtil.exception()
    finally:
        session_maker.remove()


def save_table_embedding(session_maker, ids: List[int]):
    if not settings.TABLE_EMBEDDING_ENABLED:
        return

    if not ids or len(ids) == 0:
        return
    try:
        ChatBILogUtil.info('start table embedding')
        start_time = time.time()
        model = EmbeddingModelCache.get_model()
        session = session_maker()
        
        # 性能优化：预加载所有表和字段，避免 N+1 查询
        tables_map = {}
        fields_map = {}
        all_tables = session.query(CoreTable).filter(CoreTable.id.in_(ids)).all()
        for t in all_tables:
            tables_map[t.id] = t
        if all_tables:
            table_ids = [t.id for t in all_tables]
            all_fields = session.query(CoreField).filter(CoreField.table_id.in_(table_ids)).all()
            for f in all_fields:
                fields_map.setdefault(f.table_id, []).append(f)
        
        batch_count = 0
        for _id in ids:
            table = tables_map.get(_id)
            if not table:
                ChatBILogUtil.warning(f'Table with id {_id} not found, skipping embedding')
                continue
            fields = fields_map.get(table.id, [])

            schema_table = ''
            schema_table += f"# Table: {table.table_name}"
            table_comment = ''
            if table.custom_comment:
                table_comment = table.custom_comment.strip()
            if table_comment == '':
                schema_table += '\n[\n'
            else:
                schema_table += f", {table_comment}\n[\n"

            if fields:
                field_list = []
                for field in fields:
                    field_comment = ''
                    if field.custom_comment:
                        field_comment = field.custom_comment.strip()
                    if field_comment == '':
                        field_list.append(f"({field.field_name}:{field.field_type})")
                    else:
                        field_list.append(f"({field.field_name}:{field.field_type}, {field_comment})")
                schema_table += ",\n".join(field_list)
            schema_table += '\n]\n'
            emb = json.dumps(model.embed_query(schema_table))

            stmt = update(CoreTable).where(and_(CoreTable.id == _id)).values(embedding=emb)
            session.execute(stmt)
            batch_count += 1
            # 性能优化：每20条批量 commit 一次，替代逐条 commit
            if batch_count % 20 == 0:
                session.commit()
        
        # 提交剩余的
        if batch_count % 20 != 0:
            session.commit()

        end_time = time.time()
        ChatBILogUtil.info('table embedding finished in: ' + str(end_time - start_time) + ' seconds')
    except Exception:
        ChatBILogUtil.exception()
    finally:
        session_maker.remove()


def save_ds_embedding(session_maker, ids: List[int]):
    if not settings.TABLE_EMBEDDING_ENABLED:
        return

    if not ids or len(ids) == 0:
        return
    try:
        ChatBILogUtil.info('start datasource embedding')
        start_time = time.time()
        model = EmbeddingModelCache.get_model()
        session = session_maker()
        
        # 性能优化：预加载所有数据源
        all_ds = session.query(CoreDatasource).filter(CoreDatasource.id.in_(ids)).all()
        ds_map = {d.id: d for d in all_ds}
        
        # 预加载所有结构化数据源的表和字段（一次查询替代 N+1）
        struct_ds_ids = [d.id for d in all_ds if (d.type or '').lower() != 'pdf']
        tables_by_ds = {}
        fields_by_table = {}
        if struct_ds_ids:
            all_tables = session.query(CoreTable).filter(CoreTable.ds_id.in_(struct_ds_ids)).all()
            for t in all_tables:
                tables_by_ds.setdefault(t.ds_id, []).append(t)
            table_ids = [t.id for t in all_tables]
            if table_ids:
                all_fields = session.query(CoreField).filter(CoreField.table_id.in_(table_ids)).all()
                for f in all_fields:
                    fields_by_table.setdefault(f.table_id, []).append(f)
        
        batch_count = 0
        for _id in ids:
            schema_table = ''
            ds = ds_map.get(_id)
            if not ds:
                ChatBILogUtil.warning(f'Datasource with id {_id} not found, skipping embedding')
                continue
            schema_table += f"{ds.name}, {ds.description}\n"

            ds_type = (ds.type or '').lower()
            if ds_type == 'pdf':
                try:
                    from apps.datasource.models.document import CoreDocument, CoreDocumentChunk
                    doc = session.query(CoreDocument).filter(
                        CoreDocument.ds_id == ds.id
                    ).order_by(CoreDocument.create_time.desc()).first()
                    if doc:
                        schema_table += f"# PDF Document: {doc.filename}\n"
                        section_chunks = session.query(CoreDocumentChunk.section_title).filter(
                            CoreDocumentChunk.document_id == doc.id,
                            CoreDocumentChunk.section_title.isnot(None),
                            CoreDocumentChunk.section_title != ''
                        ).distinct().limit(15).all()
                        section_titles = [s[0] for s in section_chunks if s[0]]
                        if section_titles:
                            schema_table += "Sections: " + ", ".join(section_titles) + "\n"
                        top_chunks = session.query(CoreDocumentChunk).filter(
                            CoreDocumentChunk.document_id == doc.id,
                            CoreDocumentChunk.embedding.isnot(None),
                            CoreDocumentChunk.chunk_type.in_(['section', 'text', None])
                        ).order_by(CoreDocumentChunk.chunk_index).limit(5).all()
                        for tc in top_chunks:
                            if tc.text:
                                schema_table += tc.text[:100] + "\n"
                except Exception as e:
                    ChatBILogUtil.warning(f'PDF embedding enrichment failed for ds_id={_id}: {e}')
            else:
                # 性能优化：使用预加载的表和字段数据
                tables = tables_by_ds.get(ds.id, [])
                for table in tables:
                    fields = fields_by_table.get(table.id, [])

                    schema_table += f"# Table: {table.table_name}"
                    table_comment = ''
                    if table.custom_comment:
                        table_comment = table.custom_comment.strip()
                    if table_comment == '':
                        schema_table += '\n[\n'
                    else:
                        schema_table += f", {table_comment}\n[\n"

                    if fields:
                        field_list = []
                        for field in fields:
                            field_comment = ''
                            if field.custom_comment:
                                field_comment = field.custom_comment.strip()
                            if field_comment == '':
                                field_list.append(f"({field.field_name}:{field.field_type})")
                            else:
                                field_list.append(f"({field.field_name}:{field.field_type}, {field_comment})")
                        schema_table += ",\n".join(field_list)
                    schema_table += '\n]\n'

            emb = json.dumps(model.embed_query(schema_table))

            stmt = update(CoreDatasource).where(and_(CoreDatasource.id == _id)).values(embedding=emb)
            session.execute(stmt)
            batch_count += 1
            # 性能优化：每10条批量 commit 一次
            if batch_count % 10 == 0:
                session.commit()

        if batch_count % 10 != 0:
            session.commit()

        end_time = time.time()
        ChatBILogUtil.info('datasource embedding finished in: ' + str(end_time - start_time) + ' seconds')
    except Exception:
        ChatBILogUtil.exception()
    finally:
        session_maker.remove()
