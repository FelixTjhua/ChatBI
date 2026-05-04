#!/usr/bin/env python3
"""补充"毛利+产品"组合查询的SQL示例"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from sqlmodel import Session, select
from sqlalchemy import and_
from common.core.db import engine
from apps.data_training.models.data_training_model import DataTraining
from apps.data_training.crud.data_training import save_embeddings
from sqlalchemy.orm import sessionmaker, scoped_session

NEW_EXAMPLES = [
    {
        "question": "找出毛利最高的产品",
        "description": 'SELECT "产品", SUM("毛利") AS "总毛利" FROM "{table}" GROUP BY "产品" ORDER BY "总毛利" DESC LIMIT 5'
    },
    {
        "question": "毛利最高的5个产品",
        "description": 'SELECT "产品", SUM("毛利") AS "总毛利" FROM "{table}" GROUP BY "产品" ORDER BY "总毛利" DESC LIMIT 5'
    },
    {
        "question": "各产品毛利排名",
        "description": 'SELECT "产品", SUM("毛利") AS "总毛利", ROUND(AVG("毛利率"), 2) AS "平均毛利率" FROM "{table}" GROUP BY "产品" ORDER BY "总毛利" DESC'
    },
    {
        "question": "各产品类别的毛利对比",
        "description": 'SELECT "产品类别", SUM("毛利") AS "总毛利", SUM("销售额") AS "总销售额", ROUND(SUM("毛利") * 100.0 / NULLIF(SUM("销售额"), 0), 2) AS "毛利率%" FROM "{table}" GROUP BY "产品类别" ORDER BY "总毛利" DESC'
    },
    {
        "question": "毛利率最高的产品",
        "description": 'SELECT "产品", ROUND(AVG("毛利率"), 2) AS "平均毛利率", SUM("毛利") AS "总毛利" FROM "{table}" GROUP BY "产品" ORDER BY "平均毛利率" DESC LIMIT 5'
    },
    {
        "question": "各产品的利润贡献",
        "description": 'SELECT "产品", SUM("毛利") AS "总毛利", ROUND(SUM("毛利") * 100.0 / NULLIF((SELECT SUM("毛利") FROM "{table}"), 0), 2) AS "利润贡献占比%" FROM "{table}" GROUP BY "产品" ORDER BY "总毛利" DESC'
    },
]


def main():
    oid = 1
    inserted_ids = []

    print("=" * 50)
    print("  补充「毛利+产品」SQL示例")
    print("=" * 50)

    with Session(engine) as session:
        for ex in NEW_EXAMPLES:
            # 检查是否已存在（避免重复插入）
            exists = session.execute(
                select(DataTraining.id).where(
                    and_(DataTraining.question == ex["question"], DataTraining.oid == oid)
                )
            ).first()

            if exists:
                print(f"  ⏭️  已存在，跳过: {ex['question']}")
                continue

            record = DataTraining(
                oid=oid,
                datasource=None,
                question=ex["question"],
                description=ex["description"],
                create_time=datetime.now(),
                enabled=True,
            )
            session.add(record)
            session.flush()
            session.refresh(record)
            inserted_ids.append(record.id)
            print(f"  已插入: {ex['question']} (id={record.id})")

        session.commit()

    if not inserted_ids:
        print("\n没有新示例需要插入，全部已存在。")
        return

    # 生成向量嵌入
    print(f"\n🔄 正在为 {len(inserted_ids)} 条新示例生成向量嵌入...")
    try:
        sm = scoped_session(sessionmaker(bind=engine))
        save_embeddings(sm, inserted_ids)
        print("向量嵌入生成完成")
    except Exception as e:
        print(f"⚠️  向量嵌入生成失败: {e}")
        print("   系统会在下次定时任务中自动补偿（fill_empty_embeddings）")

    print(f"\n🎉 完成！共插入 {len(inserted_ids)} 条新SQL示例。")
    print("   现在提问「找出毛利最高的5个产品」应该能命中SQL示例库了。")


if __name__ == "__main__":
    main()
