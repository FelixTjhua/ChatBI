#!/usr/bin/env python3
"""从SQLBot导入数据"""

import sys
import os
import csv
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from sqlmodel import Session, create_engine, select
from common.core.db import engine
from apps.terminology.models.terminology_model import Terminology
from apps.data_training.models.data_training_model import DataTraining
from common.chatbi.custom_prompt import CustomPrompt


def import_terminology(csv_file: str):
    """导入术语库数据"""
    if not os.path.exists(csv_file):
        print(f"⊙ 跳过术语库: 文件不存在 ({csv_file})")
        return 0
    
    with Session(engine) as session:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                try:
                    term = Terminology(
                        oid=int(row.get('oid', 1)),
                        word=row['word'],
                        description=row.get('description'),
                        pid=int(row['pid']) if row.get('pid') and row['pid'] != '' else None,
                        enabled=row.get('enabled', 'true').lower() in ['true', '1', 't'],
                        specific_ds=row.get('specific_ds', 'false').lower() in ['true', '1', 't'],
                        datasource_ids=eval(row['datasource_ids']) if row.get('datasource_ids') and row['datasource_ids'] != '' else [],
                        create_time=datetime.now()
                    )
                    session.add(term)
                    count += 1
                except Exception as e:
                    print(f"  ⚠️ 跳过术语 '{row.get('word')}': {e}")
            
            session.commit()
            print(f"✓ 导入术语库: {count} 条")
            return count


def import_training(csv_file: str):
    """导入SQL示例库数据"""
    if not os.path.exists(csv_file):
        print(f"⊙ 跳过SQL示例库: 文件不存在 ({csv_file})")
        return 0
    
    with Session(engine) as session:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                try:
                    training = DataTraining(
                        oid=int(row.get('oid', 1)),
                        datasource=int(row['datasource']) if row.get('datasource') and row['datasource'] != '' else None,
                        question=row['question'],
                        description=row['description'],
                        enabled=row.get('enabled', 'true').lower() in ['true', '1', 't'],
                        specific_ds=row.get('specific_ds', 'false').lower() in ['true', '1', 't'],
                        datasource_ids=eval(row['datasource_ids']) if row.get('datasource_ids') and row['datasource_ids'] != '' else [],
                        create_time=datetime.now()
                    )
                    session.add(training)
                    count += 1
                except Exception as e:
                    print(f"  ⚠️ 跳过示例 '{row.get('question')}': {e}")
            
            session.commit()
            print(f"✓ 导入SQL示例库: {count} 条")
            return count


def import_prompts(csv_file: str):
    """导入提示词数据"""
    if not os.path.exists(csv_file):
        print(f"⊙ 跳过提示词: 文件不存在 ({csv_file})")
        return 0
    
    with Session(engine) as session:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                try:
                    prompt = CustomPrompt(
                        oid=int(row.get('oid', 1)),
                        name=row['name'],
                        type=row['type'],
                        prompt=row['prompt'],
                        specific_ds=row.get('specific_ds', 'false').lower() in ['true', '1', 't'],
                        datasource_ids=eval(row['datasource_ids']) if row.get('datasource_ids') and row['datasource_ids'] != '' else None,
                        create_time=datetime.now()
                    )
                    session.add(prompt)
                    count += 1
                except Exception as e:
                    print(f"  ⚠️ 跳过提示词 '{row.get('name')}': {e}")
            
            session.commit()
            print(f"✓ 导入提示词: {count} 条")
            return count


def import_from_sqlbot_db(sqlbot_db_url: str):
    """从SQLBot数据库直接导入数据"""
    print("\n🔗 连接SQLBot数据库...")
    try:
        sqlbot_engine = create_engine(sqlbot_db_url)
    except Exception as e:
        print(f"连接失败: {e}")
        return 0
    
    total_count = 0
    
    # 导入术语库
    print("\n📚 导入术语库...")
    with Session(sqlbot_engine) as sqlbot_session:
        with Session(engine) as chatbi_session:
            try:
                # SQLBot的terminology表结构
                result = sqlbot_session.execute(
                    "SELECT id, oid, pid, create_time, word, description, enabled, specific_ds, datasource_ids FROM terminology"
                )
                count = 0
                for row in result:
                    try:
                        term = Terminology(
                            oid=row[1] if row[1] else 1,
                            pid=row[2],
                            create_time=row[3] if row[3] else datetime.now(),
                            word=row[4],
                            description=row[5],
                            enabled=row[6] if row[6] is not None else True,
                            specific_ds=row[7] if row[7] is not None else False,
                            datasource_ids=row[8] if row[8] else []
                        )
                        chatbi_session.add(term)
                        count += 1
                    except Exception as e:
                        print(f"  ⚠️ 跳过术语 '{row[4]}': {e}")
                
                chatbi_session.commit()
                print(f"✓ 导入术语库: {count} 条")
                total_count += count
            except Exception as e:
                print(f"  ⚠️ 术语库导入失败: {e}")
    
    # 导入SQL示例库
    print("\n📝 导入SQL示例库...")
    with Session(sqlbot_engine) as sqlbot_session:
        with Session(engine) as chatbi_session:
            try:
                result = sqlbot_session.execute(
                    "SELECT id, oid, datasource, create_time, question, description, enabled, specific_ds, datasource_ids FROM data_training"
                )
                count = 0
                for row in result:
                    try:
                        training = DataTraining(
                            oid=row[1] if row[1] else 1,
                            datasource=row[2],
                            create_time=row[3] if row[3] else datetime.now(),
                            question=row[4],
                            description=row[5],
                            enabled=row[6] if row[6] is not None else True,
                            specific_ds=row[7] if row[7] is not None else False,
                            datasource_ids=row[8] if row[8] else []
                        )
                        chatbi_session.add(training)
                        count += 1
                    except Exception as e:
                        print(f"  ⚠️ 跳过示例 '{row[4]}': {e}")
                
                chatbi_session.commit()
                print(f"✓ 导入SQL示例库: {count} 条")
                total_count += count
            except Exception as e:
                print(f"  ⚠️ SQL示例库导入失败: {e}")
    
    # 导入提示词
    print("\n💬 导入提示词...")
    with Session(sqlbot_engine) as sqlbot_session:
        with Session(engine) as chatbi_session:
            try:
                result = sqlbot_session.execute(
                    "SELECT id, oid, type, create_time, name, prompt, specific_ds, datasource_ids FROM custom_prompt"
                )
                count = 0
                for row in result:
                    try:
                        prompt = CustomPrompt(
                            oid=row[1] if row[1] else 1,
                            type=row[2],
                            create_time=row[3] if row[3] else datetime.now(),
                            name=row[4],
                            prompt=row[5],
                            specific_ds=row[6] if row[6] is not None else False,
                            datasource_ids=row[7] if row[7] else None
                        )
                        chatbi_session.add(prompt)
                        count += 1
                    except Exception as e:
                        print(f"  ⚠️ 跳过提示词 '{row[4]}': {e}")
                
                chatbi_session.commit()
                print(f"✓ 导入提示词: {count} 条")
                total_count += count
            except Exception as e:
                print(f"  ⚠️ 提示词导入失败: {e}")
    
    return total_count


def main():
    print("=" * 70)
    print("从SQLBot导入数据")
    print("=" * 70)
    
    # 检查是否有SQLBot数据库连接信息
    sqlbot_db_url = os.environ.get('SQLBOT_DATABASE_URL')
    
    if sqlbot_db_url:
        print("\n🔍 检测到SQLBot数据库连接信息")
        print(f"   数据库: {sqlbot_db_url.split('@')[-1] if '@' in sqlbot_db_url else 'localhost'}")
        
        confirm = input("\n确认从SQLBot数据库导入？(输入 yes 确认): ")
        if confirm.lower() != 'yes':
            print("\n操作已取消")
            return
        
        print("\n🚀 开始从数据库导入...\n")
        total_count = import_from_sqlbot_db(sqlbot_db_url)
        
        print("\n" + "=" * 70)
        print(f"导入完成！共导入 {total_count} 条数据")
        print("=" * 70)
        print("\n💡 提示:")
        print("   - 请在Web界面验证数据是否正确导入")
        print("   - 如需重新导入，请先运行 clear_rag_data.py 清空数据")
        return
    
    # CSV文件导入模式
    print("\n📁 查找CSV文件...")
    
    # 检查文件是否存在
    files = {
        'terminology.csv': '术语库',
        'data_training.csv': 'SQL示例库',
        'custom_prompt.csv': '提示词'
    }
    
    found_files = []
    for filename, desc in files.items():
        if os.path.exists(filename):
            found_files.append((filename, desc))
            print(f"  ✓ 找到 {desc}: {filename}")
        else:
            print(f"  ⊙ 未找到 {desc}: {filename}")
    
    if not found_files:
        print("\n错误: 未找到任何CSV文件或数据库连接")
        print("\n💡 提示:")
        print("   方式1: 从SQLBot数据库导入")
        print("      export SQLBOT_DATABASE_URL='postgresql://user:pass@host:port/dbname'")
        print("      cd backend && python scripts/import_from_sqlbot.py")
        print("\n   方式2: 从CSV文件导入")
        print("      1. 请将CSV文件放在 backend 目录下")
        print("      2. 文件名应为: terminology.csv, data_training.csv, custom_prompt.csv")
        print("      3. 参考 IMPORT_SQLBOT_DATA.md 了解如何从SQLBot导出数据")
        return
    
    print(f"\n📊 准备导入 {len(found_files)} 个文件...")
    
    # 确认操作
    confirm = input("\n确认开始导入？(输入 yes 确认): ")
    if confirm.lower() != 'yes':
        print("\n操作已取消")
        return
    
    print("\n🚀 开始导入...\n")
    
    total_count = 0
    
    # 导入术语库
    if os.path.exists('terminology.csv'):
        count = import_terminology('terminology.csv')
        total_count += count
    
    # 导入SQL示例库
    if os.path.exists('data_training.csv'):
        count = import_training('data_training.csv')
        total_count += count
    
    # 导入提示词
    if os.path.exists('custom_prompt.csv'):
        count = import_prompts('custom_prompt.csv')
        total_count += count
    
    print("\n" + "=" * 70)
    print(f"导入完成！共导入 {total_count} 条数据")
    print("=" * 70)
    print("\n💡 提示:")
    print("   - 请在Web界面验证数据是否正确导入")
    print("   - 如需重新导入，请先运行 clear_rag_data.py 清空数据")


if __name__ == "__main__":
    main()
