#!/usr/bin/env python3
"""
为术语库和知识库生成向量嵌入
启用向量检索后必须运行此脚本
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select
from sqlalchemy import update, and_, or_
from common.core.db import engine
from common.core.config import settings
from apps.terminology.models.terminology_model import Terminology
from apps.data_training.models.data_training_model import DataTraining
from apps.ai_model.embedding import EmbeddingModelCache


def generate_terminology_embeddings(session: Session):
    """为术语库生成向量嵌入"""
    print("\n📚 为术语库生成向量嵌入...")
    
    # 获取所有术语（包括主术语和同义词）
    terms = session.exec(select(Terminology)).all()
    
    if not terms:
        print("   没有找到术语数据")
        return 0
    
    model = EmbeddingModelCache.get_model()
    
    # 批量生成嵌入
    words = [t.word for t in terms]
    print(f"   正在为 {len(words)} 个术语生成向量...")
    
    embeddings = model.embed_documents(words)
    
    # 更新数据库
    updated = 0
    for i, term in enumerate(terms):
        stmt = update(Terminology).where(Terminology.id == term.id).values(embedding=embeddings[i])
        session.execute(stmt)
        updated += 1
        if updated % 10 == 0:
            print(f"   已处理 {updated}/{len(terms)} 个术语")
    
    session.commit()
    print(f"   完成! 共更新 {updated} 个术语的向量嵌入")
    return updated


def generate_training_embeddings(session: Session):
    """为知识库生成向量嵌入"""
    print("\n📖 为知识库生成向量嵌入...")
    
    # 获取所有SQL示例
    trainings = session.exec(select(DataTraining)).all()
    
    if not trainings:
        print("   没有找到知识库数据")
        return 0
    
    model = EmbeddingModelCache.get_model()
    
    # 批量生成嵌入
    questions = [t.question for t in trainings]
    print(f"   正在为 {len(questions)} 个SQL示例生成向量...")
    
    embeddings = model.embed_documents(questions)
    
    # 更新数据库
    updated = 0
    for i, training in enumerate(trainings):
        stmt = update(DataTraining).where(DataTraining.id == training.id).values(embedding=embeddings[i])
        session.execute(stmt)
        updated += 1
    
    session.commit()
    print(f"   完成! 共更新 {updated} 个SQL示例的向量嵌入")
    return updated


def test_vector_search(session: Session):
    """测试向量检索效果"""
    print("\n🔍 测试向量检索效果...")
    
    model = EmbeddingModelCache.get_model()
    
    test_queries = [
        "查询营收情况",  # 应该匹配"销售额"（同义词）
        "计算盈利能力",  # 应该匹配"利润率"
        "统计各品类销售",  # 应该匹配"产品类别"
        "分析销售走势",  # 应该匹配"销售趋势"相关
    ]
    
    for query in test_queries:
        print(f"\n   查询: '{query}'")
        
        # 生成查询向量
        query_embedding = model.embed_query(query)
        
        # 术语向量检索
        from sqlalchemy import text
        term_sql = f"""
        SELECT id, word, (1 - (embedding <=> :embedding)) AS similarity
        FROM business_term
        WHERE embedding IS NOT NULL AND enabled = true
        ORDER BY similarity DESC
        LIMIT 3
        """
        term_results = session.execute(text(term_sql), {'embedding': str(query_embedding)}).fetchall()
        
        print(f"   术语匹配:")
        for r in term_results:
            print(f"      - {r.word} (相似度: {r.similarity:.4f})")
        
        # SQL示例向量检索
        training_sql = f"""
        SELECT id, question, (1 - (embedding <=> :embedding)) AS similarity
        FROM business_sql_example
        WHERE embedding IS NOT NULL AND enabled = true
        ORDER BY similarity DESC
        LIMIT 3
        """
        training_results = session.execute(text(training_sql), {'embedding': str(query_embedding)}).fetchall()
        
        print(f"   SQL示例匹配:")
        for r in training_results:
            print(f"      - {r.question} (相似度: {r.similarity:.4f})")


def main():
    print("=" * 60)
    print("ChatBI 向量嵌入生成工具")
    print("=" * 60)
    
    if not settings.EMBEDDING_ENABLED:
        print("\n⚠️ 警告: EMBEDDING_ENABLED=false")
        print("   请在 .env 中设置 EMBEDDING_ENABLED=true")
        return
    
    print(f"\n配置信息:")
    print(f"   模型路径: {settings.LOCAL_MODEL_PATH}")
    print(f"   相似度阈值: {settings.EMBEDDING_TERMINOLOGY_SIMILARITY}")
    print(f"   检索数量: {settings.EMBEDDING_TERMINOLOGY_TOP_COUNT}")
    
    with Session(engine) as session:
        # 生成术语嵌入
        term_count = generate_terminology_embeddings(session)
        
        # 生成知识库嵌入
        training_count = generate_training_embeddings(session)
        
        # 测试向量检索
        if term_count > 0 or training_count > 0:
            test_vector_search(session)
        
        print("\n" + "=" * 60)
        print("向量嵌入生成完成!")
        print("=" * 60)
        print(f"\n📊 统计:")
        print(f"   术语向量: {term_count} 个")
        print(f"   SQL示例向量: {training_count} 个")
        print("\n💡 提示: 请重启后端服务以使配置生效")


if __name__ == "__main__":
    main()
