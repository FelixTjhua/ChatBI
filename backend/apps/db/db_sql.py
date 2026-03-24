# Author: Junjun
# Date: 2025/8/20
from apps.datasource.models.datasource import CoreDatasource, DatasourceConf
from common.utils.utils import equals_ignore_case


def get_version_sql(ds: CoreDatasource, conf: DatasourceConf):
    if equals_ignore_case(ds.type, "mysql"):
        return """
                SELECT VERSION()
                """
    elif equals_ignore_case(ds.type, "pg", "excel", "csv", "pdf"):
        return """
              SELECT current_setting('server_version')
              """
    elif equals_ignore_case(ds.type, "oracle"):
        return """
                SELECT version FROM v$instance
                """


def get_table_sql(ds: CoreDatasource, conf: DatasourceConf, db_version: str = ''):
    if equals_ignore_case(ds.type, "mysql"):
        return """SELECT
     TABLE_NAME,
     """, conf.database
    elif equals_ignore_case(ds.type, "pg", "excel", "csv", "pdf"):
        return """SELECT c.relname                                       AS TABLE_NAME,
     COALESCE(d.description, obj_description(c.oid)) AS TABLE_COMMENT
     """, conf.dbSchema
    elif equals_ignore_case(ds.type, "oracle"):
        return """SELECT DISTINCT
     t.TABLE_NAME AS "TABLE_NAME",
     """, conf.dbSchema


def get_field_sql(ds: CoreDatasource, conf: DatasourceConf, table_name: str = None):
    if equals_ignore_case(ds.type, "mysql"):
        sql1 = """SELECT
     COLUMN_NAME,
     """
        sql2 = " AND TABLE_NAME = :param2" if table_name is not None and table_name != "" else ""
        return sql1 + sql2, conf.database, table_name
    elif equals_ignore_case(ds.type, "pg", "excel", "csv", "pdf"):
        sql1 = """SELECT a.attname                                       AS COLUMN_NAME,
     pg_catalog.format_type(a.atttypid, a.atttypmod) AS DATA_TYPE,
     """
        sql2 = " AND c.relname = :param2" if table_name is not None and table_name != "" else ""
        return sql1 + sql2, conf.dbSchema, table_name
    elif equals_ignore_case(ds.type, "oracle"):
        sql1 = """SELECT
     col.COLUMN_NAME AS "COLUMN_NAME",
     """
        sql2 = " AND col.TABLE_NAME = :param2" if table_name is not None and table_name != "" else ""
        return sql1 + sql2, conf.dbSchema, table_name
