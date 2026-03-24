#!/usr/bin/env python3
"""
修复字段映射问题：为数据库字段添加注释，帮助LLM理解字段含义
"""
import sys
sys.path.insert(0, '.')

from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker
from common.core.config import settings
from apps.datasource.models.datasource import CoreField, CoreTable
from common.utils.utils import ChatBILogUtil

def main():
    engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))
    Session = sessionmaker(bind=engine)
    session = Session()
    
    print("=" * 80)
    print("为数据库字段添加注释")
    print("=" * 80)
    
    # 常见字段名到中文描述的映射
    field_mappings = {
        # 时间相关
        '日期': '日期',
        '年': '年份',
        '月': '月份',
        '季度': '季度',
        '星期': '星期',
        'date': '日期',
        'year': '年份',
        'month': '月份',
        'quarter': '季度',
        'week': '星期',
        
        # 销售相关
        '销售额': '销售金额',
        '销售区域': '销售区域/地区',
        '销售渠道': '销售渠道',
        '销售人员': '销售人员姓名',
        '订单数': '订单数量',
        '客单价': '平均客单价',
        'sales_amount': '销售金额',
        'sales': '销售额',
        'region': '区域',
        'area': '区域',
        'channel': '渠道',
        'salesperson': '销售人员',
        'orders': '订单数',
        'order_count': '订单数',
        
        # 产品相关
        '产品名称': '产品名称',
        '产品类别': '产品类别/分类',
        '产品编号': '产品编号',
        'product_name': '产品名称',
        'product': '产品',
        'category': '类别',
        'product_id': '产品编号',
        
        # 其他
        'id': 'ID主键',
        'name': '名称',
        'description': '描述',
        'amount': '金额',
        'quantity': '数量',
        'price': '价格',
        'total': '总计',
        'count': '数量',
    }
    
    # 获取所有字段
    fields = session.query(CoreField).all()
    
    updated_count = 0
    for field in fields:
        # 如果字段已有注释，跳过
        if field.custom_comment and field.custom_comment.strip():
            continue
        
        # 查找匹配的注释
        comment = None
        field_name_lower = field.field_name.lower()
        
        # 精确匹配
        if field.field_name in field_mappings:
            comment = field_mappings[field.field_name]
        elif field_name_lower in field_mappings:
            comment = field_mappings[field_name_lower]
        else:
            # 模糊匹配
            for key, value in field_mappings.items():
                if key in field.field_name or key in field_name_lower:
                    comment = value
                    break
        
        if comment:
            # 获取表名用于日志
            table = session.query(CoreTable).filter(CoreTable.id == field.table_id).first()
            table_name = table.table_name if table else "unknown"
            
            print(f"更新字段: {table_name}.{field.field_name} -> {comment}")
            
            # 更新字段注释
            stmt = update(CoreField).where(CoreField.id == field.id).values(custom_comment=comment)
            session.execute(stmt)
            updated_count += 1
    
    session.commit()
    
    print(f"\n总共更新了 {updated_count} 个字段的注释")
    print("=" * 80)
    
    # 重新生成表的embedding（如果启用）
    if settings.TABLE_EMBEDDING_ENABLED and updated_count > 0:
        print("\n重新生成表的embedding...")
        from apps.datasource.crud.table import save_table_embedding
        from sqlalchemy.orm import scoped_session
        
        session_maker = scoped_session(sessionmaker(bind=engine))
        
        # 获取所有表ID
        tables = session.query(CoreTable).all()
        table_ids = [table.id for table in tables]
        
        if table_ids:
            save_table_embedding(session_maker, table_ids)
            print(f"已重新生成 {len(table_ids)} 个表的embedding")
    
    session.close()
    print("\n完成！")

if __name__ == "__main__":
    main()
