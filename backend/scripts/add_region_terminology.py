#!/usr/bin/env python3
"""
添加区域相关的术语映射
"""
import sys
sys.path.insert(0, '.')

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from common.core.config import settings
from apps.terminology.crud.terminology import create_terminology
from apps.terminology.models.terminology_model import TerminologyInfo
from common.core.deps import Trans

def main():
    engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # 创建翻译函数（简单实现）
    def trans(key):
        translations = {
            'i18n_terminology.datasource_cannot_be_none': '数据源不能为空',
            'i18n_terminology.cannot_be_repeated': '术语不能重复',
            'i18n_terminology.exists_in_db': '术语已存在',
            'i18n_terminology.terminology_not_exists': '术语不存在'
        }
        return translations.get(key, key)
    
    print("=" * 80)
    print("添加区域相关术语映射")
    print("=" * 80)
    
    # 定义要添加的术语
    terminologies = [
        {
            'word': '区域',
            'other_words': ['地区', '区', '地域'],
            'description': '指销售区域或地理区域。在数据表中对应"销售区域"字段。查询时应使用"销售区域"作为字段名。',
            'enabled': True
        },
        {
            'word': '渠道',
            'other_words': ['销售渠道', '渠道类型'],
            'description': '指销售渠道，如线上、线下、电商等。在数据表中对应"销售渠道"字段。',
            'enabled': True
        },
        {
            'word': '产品',
            'other_words': ['商品', '产品名'],
            'description': '指产品或商品。在数据表中对应"产品名称"字段。',
            'enabled': True
        },
        {
            'word': '类别',
            'other_words': ['分类', '产品类别', '产品分类'],
            'description': '指产品类别或分类。在数据表中对应"产品类别"字段。',
            'enabled': True
        },
    ]
    
    added_count = 0
    for term_data in terminologies:
        try:
            info = TerminologyInfo(
                word=term_data['word'],
                other_words=term_data['other_words'],
                description=term_data['description'],
                enabled=term_data['enabled']
            )
            
            term_id = create_terminology(session, info, oid=1, trans=trans)
            print(f"✓ 添加术语: {term_data['word']} (ID: {term_id})")
            print(f"  同义词: {', '.join(term_data['other_words'])}")
            print(f"  描述: {term_data['description'][:80]}...")
            added_count += 1
            
        except Exception as e:
            if '术语已存在' in str(e) or 'exists_in_db' in str(e):
                print(f"⊙ 跳过已存在的术语: {term_data['word']}")
            else:
                print(f"✗ 添加术语失败: {term_data['word']}")
                print(f"  错误: {e}")
    
    print(f"\n总共添加了 {added_count} 个新术语")
    print("=" * 80)
    
    session.close()
    print("\n完成！")

if __name__ == "__main__":
    main()
