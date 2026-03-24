"""
自动 Schema 分析器
自动分析数据库结构并生成业务含义
"""
import json
from typing import Dict, List, Optional
from sqlmodel import Session
from langchain_core.messages import SystemMessage, HumanMessage

from apps.datasource.models.datasource import CoreDatasource, TableSchema, ColumnSchema
from apps.db.db import get_tables, get_fields
from apps.ai_model.model_factory import LLMFactory, get_default_config
from common.utils.utils import ChatBILogUtil
from common.utils.locale import I18n

_i18n = I18n("locales")


def _schema_trans(lang: str = "zh-CN") -> callable:
    """获取基于语言的翻译函数"""
    _lang = (lang or 'zh-CN').lower().replace('_', '-')
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


class AutoSchemaAnalyzer:
    """自动分析数据库 Schema 并生成术语"""
    
    def __init__(self, session: Session, lang: str = "zh-CN"):
        self.session = session
        self.lang = lang
        self._t = _schema_trans(lang)
    
    async def analyze_datasource(self, ds: CoreDatasource) -> Dict:
        """自动分析数据源，生成：
            1. 表名及其业务含义
            """
        ChatBILogUtil.info(f"开始分析数据源: {ds.name} (ID: {ds.id})")
        
        schema_info = {
            'datasource_id': ds.id,
            'datasource_name': ds.name,
            'datasource_type': ds.type,
            'tables': [],
            'relationships': [],
            'common_patterns': []
        }
        
        try:
            # 1. 获取所有表
            tables = get_tables(ds)
            ChatBILogUtil.info(f"找到 {len(tables)} 个表")
            
            # 2. 分析每个表
            for table in tables:
                table_info = await self._analyze_table(ds, table)
                schema_info['tables'].append(table_info)
            
            # 3. 分析表关系
            schema_info['relationships'] = await self._analyze_relationships(ds, tables)
            
            # 4. 推断常见查询模式
            schema_info['common_patterns'] = await self._infer_common_patterns(ds, schema_info['tables'])
            
            ChatBILogUtil.info(f"数据源分析完成: {ds.name}")
            return schema_info
            
        except Exception as e:
            ChatBILogUtil.error(f"分析数据源失败: {e}")
            ChatBILogUtil.exception()
            raise
    
    async def _analyze_table(self, ds: CoreDatasource, table: TableSchema) -> Dict:
        """分析单个表"""
        table_info = {
            'name': table.table_name,
            'comment': table.table_comment or '',
            'business_meaning': '',
            'fields': [],
            'key_fields': [],
            'measure_fields': [],
            'dimension_fields': []
        }
        
        # 获取字段
        fields = get_fields(ds, table.table_name)
        
        # 分析字段
        for field in fields:
            field_info = {
                'name': field.field_name,
                'type': field.field_type,
                'comment': field.field_comment or '',
                'business_meaning': '',
                'is_key': False,
                'is_measure': self._is_measure_field(field),
                'is_dimension': self._is_dimension_field(field)
            }
            
            # 判断是否为关键字段
            if 'id' in field.field_name.lower() or 'key' in field.field_name.lower():
                field_info['is_key'] = True
                table_info['key_fields'].append(field.field_name)
            
            if field_info['is_measure']:
                table_info['measure_fields'].append(field.field_name)
            
            if field_info['is_dimension']:
                table_info['dimension_fields'].append(field.field_name)
            
            table_info['fields'].append(field_info)
        
        # 使用 LLM 推断表的业务含义
        table_info['business_meaning'] = await self._infer_table_meaning(table, fields)
        
        # 使用 LLM 推断字段的业务含义
        for field_info in table_info['fields']:
            if not field_info['comment']:  # 只为没有注释的字段推断含义
                field_info['business_meaning'] = await self._infer_field_meaning(
                    table.table_name, 
                    field_info['name'], 
                    field_info['type']
                )
        
        return table_info
    
    def _is_measure_field(self, field: ColumnSchema) -> bool:
        """判断是否为度量字段（数值型）"""
        numeric_types = ['int', 'integer', 'bigint', 'smallint', 'decimal', 'numeric', 
                        'float', 'double', 'real', 'money']
        field_type_lower = field.field_type.lower()
        
        # 排除ID字段
        if 'id' in field.field_name.lower():
            return False
        
        return any(t in field_type_lower for t in numeric_types)
    
    def _is_dimension_field(self, field: ColumnSchema) -> bool:
        """判断是否为维度字段（分类、时间等）"""
        dimension_types = ['varchar', 'char', 'text', 'string', 'date', 'datetime', 
                          'timestamp', 'time', 'boolean', 'bool']
        field_type_lower = field.field_type.lower()
        
        return any(t in field_type_lower for t in dimension_types)
    
    async def _infer_table_meaning(self, table: TableSchema, fields: List[ColumnSchema]) -> str:
        """使用 LLM 推断表的业务含义"""
        try:
            # 如果有注释，直接使用
            if table.table_comment:
                return table.table_comment
            
            # 构建提示词
            field_names = [f.field_name for f in fields[:10]]  # 只取前10个字段
            
            prompt = self._t('i18n_schema.infer_table', table=table.table_name, fields=', '.join(field_names))
            
            # 使用 LLM 推断
            # 添加超时保护，防止 LLM 调用阻塞整个 schema 分析流程
            import asyncio
            config = await get_default_config()
            llm_instance = LLMFactory.create_llm(config)
            
            messages = [
                SystemMessage(content=self._t('i18n_schema.system_table')),
                HumanMessage(content=prompt)
            ]
            
            response = await asyncio.wait_for(
                asyncio.to_thread(llm_instance.llm.invoke, messages),
                timeout=30.0  # 30秒超时
            )
            meaning = response.content.strip()
            
            ChatBILogUtil.info(f"推断表 {table.table_name} 的含义: {meaning}")
            return meaning
            
        except asyncio.TimeoutError:
            ChatBILogUtil.warning(f"推断表含义超时(30s): {table.table_name}")
            return f"表: {table.table_name}"
        except Exception as e:
            ChatBILogUtil.error(f"推断表含义失败: {e}")
            return f"表: {table.table_name}"
    
    async def _infer_field_meaning(self, table_name: str, field_name: str, field_type: str) -> str:
        """使用 LLM 推断字段的业务含义"""
        try:
            prompt = self._t('i18n_schema.infer_field', table=table_name, field=field_name, type=field_type)
            
            # 添加超时保护
            import asyncio
            config = await get_default_config()
            llm_instance = LLMFactory.create_llm(config)
            
            messages = [
                SystemMessage(content=self._t('i18n_schema.system_field')),
                HumanMessage(content=prompt)
            ]
            
            response = await asyncio.wait_for(
                asyncio.to_thread(llm_instance.llm.invoke, messages),
                timeout=30.0  # 30秒超时
            )
            meaning = response.content.strip()
            
            return meaning
            
        except asyncio.TimeoutError:
            ChatBILogUtil.warning(f"推断字段含义超时(30s): {table_name}.{field_name}")
            return f"字段: {field_name}"
        except Exception as e:
            ChatBILogUtil.error(f"推断字段含义失败: {e}")
            return f"字段: {field_name}"
    
    async def _analyze_relationships(self, ds: CoreDatasource, tables: List[TableSchema]) -> List[Dict]:
        """分析表之间的关系"""
        relationships = []
        
        # 简单的关系推断：基于字段名
        for table in tables:
            fields = get_fields(ds, table.table_name)
            
            for field in fields:
                field_name_lower = field.field_name.lower()
                
                # 查找外键关系（字段名包含其他表名）
                for other_table in tables:
                    if other_table.table_name == table.table_name:
                        continue
                    
                    other_table_name_lower = other_table.table_name.lower()
                    
                    # 如果字段名包含其他表名，可能是外键
                    if other_table_name_lower in field_name_lower or \
                       (other_table_name_lower.rstrip('s') in field_name_lower):
                        relationships.append({
                            'from_table': table.table_name,
                            'to_table': other_table.table_name,
                            'foreign_key': field.field_name,
                            'type': 'many_to_one',
                            'description': self._t('i18n_schema.relationship_desc', from_table=table.table_name, to_table=other_table.table_name, key=field.field_name)
                        })
        
        return relationships
    
    async def _infer_common_patterns(self, ds: CoreDatasource, tables: List[Dict]) -> List[Dict]:
        """推断常见查询模式"""
        patterns = []
        _is_en = self.lang.lower().startswith('en') if self.lang else False
        
        for table in tables:
            # 模式1：时间序列统计
            date_fields = [f for f in table['fields'] if 'date' in f['type'].lower() or 'time' in f['type'].lower()]
            measure_fields = table['measure_fields']
            
            if date_fields and measure_fields:
                for date_field in date_fields[:1]:  # 只取第一个时间字段
                    for measure_field in measure_fields[:2]:  # 只取前两个度量字段
                        patterns.append({
                            'pattern': f"Aggregate {measure_field} by {date_field['name']}" if _is_en else f"按{date_field['name']}统计{measure_field}",
                            'tables': [table['name']],
                            'fields': [date_field['name'], measure_field],
                            'type': 'time_series_aggregation',
                            'description': f"Aggregate {measure_field} trends over time dimension" if _is_en else f"按时间维度统计{measure_field}的变化趋势"
                        })
            
            # 模式2：分组统计
            dimension_fields = table['dimension_fields']
            if dimension_fields and measure_fields:
                for dim_field in dimension_fields[:2]:  # 只取前两个维度字段
                    for measure_field in measure_fields[:2]:
                        patterns.append({
                            'pattern': f"Group {measure_field} by {dim_field}" if _is_en else f"按{dim_field}分组统计{measure_field}",
                            'tables': [table['name']],
                            'fields': [dim_field, measure_field],
                            'type': 'group_aggregation',
                            'description': f"Group and aggregate {measure_field} by {dim_field} dimension" if _is_en else f"按{dim_field}维度分组统计{measure_field}"
                        })
            
            # 模式3：排名查询
            if measure_fields:
                for measure_field in measure_fields[:1]:
                    patterns.append({
                        'pattern': f"{measure_field} ranking" if _is_en else f"{measure_field}排名",
                        'tables': [table['name']],
                        'fields': [measure_field],
                        'type': 'ranking',
                        'description': f"Query ranking of {measure_field}" if _is_en else f"查询{measure_field}的排名情况"
                    })
        
        return patterns[:10]  # 只返回前10个模式
