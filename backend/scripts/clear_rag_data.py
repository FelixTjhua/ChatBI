#!/usr/bin/env python3
"""清空RAG知识库数据"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select, delete, func
from common.core.db import engine
from apps.terminology.models.terminology_model import Terminology
from apps.data_training.models.data_training_model import DataTraining
from common.chatbi.custom_prompt import CustomPrompt


def clear_all_data():
    """清空所有RAG相关数据"""
    print("=" * 70)
    print("清空RAG知识库数据")
    print("=" * 70)
    
    with Session(engine) as session:
        # 统计当前数据量
        term_count = session.exec(select(func.count(Terminology.id))).one() or 0
        train_count = session.exec(select(func.count(DataTraining.id))).one() or 0
        prompt_count = session.exec(select(func.count(CustomPrompt.id))).one() or 0
        
        print(f"\n📊 当前数据统计:")
        print(f"   - 术语库: {term_count} 条")
        print(f"   - SQL示例库: {train_count} 条")
        print(f"   - 提示词: {prompt_count} 条")
        
        if term_count == 0 and train_count == 0 and prompt_count == 0:
            print("\n数据库已经是空的，无需清空")
            return
        
        # 确认操作
        print("\n⚠️  警告: 此操作将删除所有数据，且不可恢复！")
        confirm = input("确认清空所有数据？(输入 yes 确认): ")
        
        if confirm.lower() != 'yes':
            print("\n操作已取消")
            return
        
        try:
            # 清空术语库
            if term_count > 0:
                session.exec(delete(Terminology))
                print(f"\n✓ 已清空术语库: {term_count} 条")
            
            # 清空SQL示例库
            if train_count > 0:
                session.exec(delete(DataTraining))
                print(f"✓ 已清空SQL示例库: {train_count} 条")
            
            # 清空提示词
            if prompt_count > 0:
                session.exec(delete(CustomPrompt))
                print(f"✓ 已清空提示词: {prompt_count} 条")
            
            session.commit()
            
            print("\n" + "=" * 70)
            print("所有数据已成功清空！")
            print("=" * 70)
            
        except Exception as e:
            session.rollback()
            print(f"\n清空数据时出错: {e}")
            raise


if __name__ == "__main__":
    clear_all_data()
