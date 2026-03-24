#!/usr/bin/env python3
"""RAG知识库数据初始化脚本（商业级）"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from sqlmodel import Session, select, delete, func
from sqlalchemy import and_
from common.core.db import engine
from apps.terminology.models.terminology_model import Terminology
from apps.data_training.models.data_training_model import DataTraining
from apps.datasource.models.datasource import CoreDatasource


TERMINOLOGIES = [
    # ── 销售核心指标 ──
    {
        "word": "销售额",
        "description": "指商品或服务销售所获得的总收入金额，是衡量企业经营规模的核心业务指标。计算公式：销售额 = 销售数量 × 单价。",
        "other_words": ["营业额", "销售收入", "营收", "总收入", "收入", "Revenue"]
    },
    {
        "word": "订单数",
        "description": "指在一定时期内完成的订单总数量，反映业务活动的活跃程度和市场需求。",
        "other_words": ["订单量", "订单数量", "成交量", "交易数", "单量"]
    },
    {
        "word": "客单价",
        "description": "平均每个客户或每笔订单的消费金额。计算公式：客单价 = 总销售额 ÷ 订单数（或客户数）。是衡量消费水平的重要业务指标。",
        "other_words": ["平均订单金额", "单均价", "订单均价", "平均消费", "均价"]
    },
    {
        "word": "GMV",
        "description": "商品交易总额（Gross Merchandise Volume），指一定时间内的成交总额，包含已付款和未付款订单。是电商和零售行业的核心业务指标。",
        "other_words": ["交易总额", "成交总额", "商品交易额"]
    },
    # ── 财务指标 ──
    {
        "word": "毛利",
        "description": "销售收入减去销售成本后的利润。计算公式：毛利 = 销售收入 - 销售成本。反映企业产品的基本盈利能力。",
        "other_words": ["毛利润", "销售毛利"]
    },
    {
        "word": "毛利率",
        "description": "毛利占销售收入的百分比，衡量企业产品定价能力和成本控制水平。计算公式：毛利率 = (销售收入 - 销售成本) ÷ 销售收入 × 100%。",
        "other_words": ["销售毛利率", "Gross Margin"]
    },
    {
        "word": "净利润",
        "description": "企业在一定时期内扣除所有成本、费用和税金后的最终利润。计算公式：净利润 = 总收入 - 总成本 - 税费。",
        "other_words": ["纯利润", "税后利润", "净收益", "Net Profit"]
    },
    {
        "word": "净利润率",
        "description": "净利润占销售收入的百分比，衡量企业整体盈利能力。计算公式：净利润率 = 净利润 ÷ 销售收入 × 100%。",
        "other_words": ["净利率", "利润率", "Net Margin"]
    },
    {
        "word": "ROI",
        "description": "投资回报率（Return On Investment），衡量投资效益的核心业务指标。计算公式：ROI = (投资收益 - 投资成本) ÷ 投资成本 × 100%。",
        "other_words": ["投资回报率", "投资回报", "回报率"]
    },
    # ── 增长分析指标 ──
    {
        "word": "同比增长",
        "description": "与去年同期相比的增长率，用于消除季节性因素的影响。计算公式：同比增长率 = (本期值 - 去年同期值) ÷ 去年同期值 × 100%。",
        "other_words": ["同比", "年同比", "YoY", "去年同期", "同比增长率"]
    },
    {
        "word": "环比增长",
        "description": "与上一期（如上月、上周）相比的增长率，反映短期变化趋势。计算公式：环比增长率 = (本期值 - 上期值) ÷ 上期值 × 100%。",
        "other_words": ["环比", "月环比", "MoM", "周环比", "上期对比", "环比增长率"]
    },
    # ── 客户管理指标 ──
    {
        "word": "复购率",
        "description": "重复购买的客户占总客户数的比例，衡量客户忠诚度和产品粘性。计算公式：复购率 = 重复购买客户数 ÷ 总客户数 × 100%。",
        "other_words": ["回购率", "重复购买率", "Repeat Purchase Rate"]
    },
    {
        "word": "客户生命周期价值",
        "description": "CLV（Customer Lifetime Value），指一个客户在整个合作期间为企业带来的总价值。计算公式：CLV = 平均客单价 × 购买频率 × 客户生命周期。",
        "other_words": ["CLV", "LTV", "客户终身价值", "生命周期价值", "用户价值"]
    },
    {
        "word": "客户留存率",
        "description": "在一定时间后仍然活跃或继续消费的客户比例，衡量客户维系能力。计算公式：留存率 = 期末留存客户数 ÷ 期初客户数 × 100%。",
        "other_words": ["留存率", "用户留存", "Retention Rate", "留存"]
    },
    {
        "word": "客户流失率",
        "description": "用户停止使用产品或服务的比例，与留存率互补。计算公式：流失率 = 1 - 留存率 = 流失客户数 ÷ 期初客户数 × 100%。",
        "other_words": ["流失率", "用户流失", "Churn Rate"]
    },
    {
        "word": "转化率",
        "description": "用户完成目标行为（如购买、注册）的比例。计算公式：转化率 = 完成目标行为的用户数 ÷ 总访问用户数 × 100%。是衡量营销效果的关键业务指标。",
        "other_words": ["转换率", "CVR", "Conversion Rate", "成交转化率"]
    },
    {
        "word": "ARPU",
        "description": "每用户平均收入（Average Revenue Per User），衡量每个用户贡献的平均收入。计算公式：ARPU = 总收入 ÷ 用户数。",
        "other_words": ["每用户平均收入", "用户均收入", "人均收入"]
    },
    # ── 运营效率指标 ──
    {
        "word": "库存周转率",
        "description": "衡量库存流转速度的业务指标。计算公式：库存周转率 = 销售成本 ÷ 平均库存金额。周转率越高说明库存管理效率越好。",
        "other_words": ["存货周转率", "库存周转", "Inventory Turnover"]
    },
    {
        "word": "坪效",
        "description": "每平方米营业面积产生的销售额，衡量零售门店空间利用效率。计算公式：坪效 = 销售额 ÷ 营业面积。",
        "other_words": ["每平米销售额", "面积效率"]
    },
    {
        "word": "人效",
        "description": "每个员工产生的销售额或利润，衡量人力资源利用效率。计算公式：人效 = 销售额 ÷ 员工数。",
        "other_words": ["人均产出", "人均销售额", "员工效率"]
    },
    {
        "word": "市场占有率",
        "description": "企业产品销售额占同类产品市场总销售额的比例。计算公式：市场占有率 = 企业销售额 ÷ 市场总销售额 × 100%。",
        "other_words": ["市场份额", "市占率", "Market Share"]
    },
    # ── 电商与流量指标 ──
    {
        "word": "DAU",
        "description": "日活跃用户数（Daily Active Users），指每日使用产品或服务的独立用户数量，衡量产品日常活跃度。",
        "other_words": ["日活", "日活用户", "日活跃用户"]
    },
    {
        "word": "MAU",
        "description": "月活跃用户数（Monthly Active Users），指每月使用产品或服务的独立用户数量，衡量产品整体用户规模。",
        "other_words": ["月活", "月活用户", "月活跃用户"]
    },
    {
        "word": "UV",
        "description": "独立访客数（Unique Visitor），指访问网站或应用的不重复用户数，衡量流量规模。",
        "other_words": ["独立访客", "访客数", "独立用户数"]
    },
    {
        "word": "SKU",
        "description": "库存量单位（Stock Keeping Unit），指商品的最小销售单位或品类编码，用于库存管理和商品分析。",
        "other_words": ["商品编码", "单品", "品类"]
    },
    # ── 通用分析术语 ──
    {
        "word": "日期",
        "description": "交易发生的时间，用于时间序列分析和趋势预测。对应数据表中的日期字段。",
        "other_words": ["时间", "交易日期", "订单日期", "销售日期", "日"]
    },
    {
        "word": "趋势",
        "description": "数据随时间变化的方向和规律，用于预测未来走势和发现业务规律。",
        "other_words": ["走势", "变化趋势", "发展趋势", "增长趋势", "趋势分析"]
    },
    {
        "word": "汇总",
        "description": "将多条数据记录合并计算，得出总计值。常用于统计总销售额、总订单数等业务汇总分析。",
        "other_words": ["合计", "总计", "求和", "统计", "累计"]
    },
    {
        "word": "平均值",
        "description": "一组数据的算术平均数，用于衡量数据的集中趋势。在企业数据分析中常用于计算平均客单价、平均销售额等。",
        "other_words": ["均值", "平均", "AVG", "平均数"]
    },
    {
        "word": "最大值",
        "description": "一组数据中的最大数值，用于找出峰值或最高记录。在企业数据分析中常用于找出最高销售额、最大订单等。",
        "other_words": ["最高", "峰值", "MAX", "最高值", "最大"]
    },
    {
        "word": "最小值",
        "description": "一组数据中的最小数值，用于找出谷值或最低记录。在企业数据分析中常用于找出最低销售额、最小订单等。",
        "other_words": ["最低", "谷值", "MIN", "最低值", "最小"]
    },
    # ── 区域与渠道 ──
    {
        "word": "区域",
        "description": "指销售区域或地理区域，用于区域销售分析和市场布局。在数据表中对应「销售区域」字段。",
        "other_words": ["地区", "区", "地域", "销售区域"]
    },
    {
        "word": "渠道",
        "description": "指销售渠道，如线上、线下、电商平台等。用于渠道效益分析和渠道策略优化。",
        "other_words": ["销售渠道", "渠道类型", "分销渠道"]
    },
    {
        "word": "产品",
        "description": "指企业销售的商品或服务。在数据表中对应「产品名称」字段。",
        "other_words": ["商品", "产品名", "品名"]
    },
    {
        "word": "类别",
        "description": "指产品类别或分类，用于品类分析和品类管理。",
        "other_words": ["分类", "产品类别", "产品分类", "品类"]
    },
]


SQL_EXAMPLES = [
    # 基础汇总查询
    {
        "question": "查询总销售额",
        "description": 'SELECT SUM("销售额") AS "总销售额" FROM "public"."Sheet1_306d4bb608"'
    },
    {
        "question": "查询总订单数",
        "description": 'SELECT SUM("订单数") AS "总订单数" FROM "public"."Sheet1_306d4bb608"'
    },
    {
        "question": "查询平均客单价",
        "description": 'SELECT ROUND(AVG("客单价"), 2) AS "平均客单价" FROM "public"."Sheet1_306d4bb608"'
    },
    {
        "question": "查询销售数据概览",
        "description": 'SELECT SUM("销售额") AS "总销售额", SUM("订单数") AS "总订单数", ROUND(AVG("客单价"), 2) AS "平均客单价" FROM "public"."Sheet1_306d4bb608"'
    },
    # 时间序列分析
    {
        "question": "按日期查询销售额",
        "description": 'SELECT "日期", "销售额" FROM "public"."Sheet1_306d4bb608" ORDER BY "日期" ASC'
    },
    {
        "question": "查询销售额趋势",
        "description": 'SELECT "日期", "销售额" FROM "public"."Sheet1_306d4bb608" ORDER BY "日期" ASC'
    },
    {
        "question": "按月统计销售额",
        "description": "SELECT TO_CHAR(\"日期\", 'YYYY-MM') AS \"月份\", SUM(\"销售额\") AS \"月销售额\" FROM \"public\".\"Sheet1_306d4bb608\" GROUP BY \"月份\" ORDER BY \"月份\" ASC"
    },
    {
        "question": "按日期统计订单数",
        "description": 'SELECT "日期", "订单数" FROM "public"."Sheet1_306d4bb608" ORDER BY "日期" ASC'
    },
    {
        "question": "查询每日客单价变化",
        "description": 'SELECT "日期", "客单价" FROM "public"."Sheet1_306d4bb608" ORDER BY "日期" ASC'
    },
    {
        "question": "展示销售趋势",
        "description": 'SELECT "日期", "销售额", "订单数" FROM "public"."Sheet1_306d4bb608" ORDER BY "日期" ASC'
    },
    {
        "question": "月度销售趋势",
        "description": "SELECT TO_CHAR(\"日期\", 'YYYY-MM') AS \"月份\", SUM(\"销售额\") AS \"月销售额\", SUM(\"订单数\") AS \"月订单数\" FROM \"public\".\"Sheet1_306d4bb608\" GROUP BY \"月份\" ORDER BY \"月份\" ASC"
    },
    # 极值与排名查询
    {
        "question": "查询销售额最高的日期",
        "description": 'SELECT "日期", "销售额" FROM "public"."Sheet1_306d4bb608" ORDER BY "销售额" DESC LIMIT 1'
    },
    {
        "question": "查询销售额最低的日期",
        "description": 'SELECT "日期", "销售额" FROM "public"."Sheet1_306d4bb608" ORDER BY "销售额" ASC LIMIT 1'
    },
    {
        "question": "查询订单数最多的日期",
        "description": 'SELECT "日期", "订单数" FROM "public"."Sheet1_306d4bb608" ORDER BY "订单数" DESC LIMIT 1'
    },
    {
        "question": "查询客单价最高的日期",
        "description": 'SELECT "日期", "客单价" FROM "public"."Sheet1_306d4bb608" ORDER BY "客单价" DESC LIMIT 1'
    },
    {
        "question": "查询销售额前10的日期",
        "description": 'SELECT "日期", "销售额" FROM "public"."Sheet1_306d4bb608" ORDER BY "销售额" DESC LIMIT 10'
    },
    {
        "question": "查询订单数前5的日期",
        "description": 'SELECT "日期", "订单数" FROM "public"."Sheet1_306d4bb608" ORDER BY "订单数" DESC LIMIT 5'
    },
    # 统计分析
    {
        "question": "查询销售额的最大值和最小值",
        "description": 'SELECT MAX("销售额") AS "最高销售额", MIN("销售额") AS "最低销售额" FROM "public"."Sheet1_306d4bb608"'
    },
    {
        "question": "查询订单数的统计信息",
        "description": 'SELECT SUM("订单数") AS "总订单数", AVG("订单数") AS "平均订单数", MAX("订单数") AS "最高订单数", MIN("订单数") AS "最低订单数" FROM "public"."Sheet1_306d4bb608"'
    },
    {
        "question": "查询数据记录数",
        "description": 'SELECT COUNT(*) AS "记录数" FROM "public"."Sheet1_306d4bb608"'
    },
    # 增长分析
    {
        "question": "本月环比增长率",
        "description": "SELECT TO_CHAR(\"日期\", 'YYYY-MM') AS \"月份\", SUM(\"销售额\") AS \"月销售额\", ROUND((SUM(\"销售额\") - LAG(SUM(\"销售额\")) OVER (ORDER BY TO_CHAR(\"日期\", 'YYYY-MM'))) * 100.0 / NULLIF(LAG(SUM(\"销售额\")) OVER (ORDER BY TO_CHAR(\"日期\", 'YYYY-MM')), 0), 2) AS \"环比增长率%\" FROM \"public\".\"Sheet1_306d4bb608\" GROUP BY \"月份\" ORDER BY \"月份\""
    },
    # 综合查询
    {
        "question": "查询所有销售数据",
        "description": 'SELECT "日期", "销售额", "订单数", "客单价" FROM "public"."Sheet1_306d4bb608" ORDER BY "日期" ASC'
    },
    {
        "question": "查询最近的销售数据",
        "description": 'SELECT "日期", "销售额", "订单数", "客单价" FROM "public"."Sheet1_306d4bb608" ORDER BY "日期" DESC LIMIT 10'
    },
    # ── 分类/分组维度查询（通用模式）──
    # 补充分类维度的 SQL 示例，覆盖 GROUP BY 类查询
    {
        "question": "查询各产品类别的销售额",
        "description": 'SELECT "产品类别", SUM("销售额") AS "销售额" FROM "public"."Sheet1_306d4bb608" GROUP BY "产品类别" ORDER BY "销售额" DESC'
    },
    {
        "question": "按类别统计销售数据",
        "description": 'SELECT "产品类别", SUM("销售额") AS "总销售额", SUM("订单数") AS "总订单数" FROM "public"."Sheet1_306d4bb608" GROUP BY "产品类别" ORDER BY "总销售额" DESC'
    },
    {
        "question": "各区域销售额对比",
        "description": 'SELECT "区域", SUM("销售额") AS "总销售额" FROM "public"."Sheet1_306d4bb608" GROUP BY "区域" ORDER BY "总销售额" DESC'
    },
    {
        "question": "按渠道统计销售额",
        "description": 'SELECT "渠道", SUM("销售额") AS "总销售额", SUM("订单数") AS "总订单数" FROM "public"."Sheet1_306d4bb608" GROUP BY "渠道" ORDER BY "总销售额" DESC'
    },
    {
        "question": "各产品销售排名",
        "description": 'SELECT "产品", SUM("销售额") AS "总销售额" FROM "public"."Sheet1_306d4bb608" GROUP BY "产品" ORDER BY "总销售额" DESC LIMIT 10'
    },
    {
        "question": "查询各类别的平均客单价",
        "description": 'SELECT "产品类别", ROUND(AVG("客单价"), 2) AS "平均客单价" FROM "public"."Sheet1_306d4bb608" GROUP BY "产品类别" ORDER BY "平均客单价" DESC'
    },
    {
        "question": "各类别销售额占比",
        "description": 'SELECT "产品类别", SUM("销售额") AS "销售额", ROUND(SUM("销售额") * 100.0 / (SELECT SUM("销售额") FROM "public"."Sheet1_306d4bb608"), 2) AS "占比%" FROM "public"."Sheet1_306d4bb608" GROUP BY "产品类别" ORDER BY "销售额" DESC'
    },
    {
        "question": "按区域和月份统计销售额",
        "description": "SELECT \"区域\", TO_CHAR(\"日期\", 'YYYY-MM') AS \"月份\", SUM(\"销售额\") AS \"月销售额\" FROM \"public\".\"Sheet1_306d4bb608\" GROUP BY \"区域\", TO_CHAR(\"日期\", 'YYYY-MM') ORDER BY \"区域\", \"月份\" ASC"
    },
    {
        "question": "销售额最高的类别",
        "description": 'SELECT "产品类别", SUM("销售额") AS "总销售额" FROM "public"."Sheet1_306d4bb608" GROUP BY "产品类别" ORDER BY "总销售额" DESC LIMIT 1'
    },
    {
        "question": "各类别订单数统计",
        "description": 'SELECT "产品类别", SUM("订单数") AS "总订单数", COUNT(*) AS "记录数" FROM "public"."Sheet1_306d4bb608" GROUP BY "产品类别" ORDER BY "总订单数" DESC'
    },
]


def clear_existing_data(session: Session, oid: int = 1):
    """清除现有的知识库数据"""
    if oid is None or oid <= 0:
        print(f"  ⚠️ 无效的工作空间 ID: {oid}，跳过清除操作")
        return
    
    try:
        # 清除术语库
        term_count = session.exec(
            select(func.count(Terminology.id)).where(Terminology.oid == oid)
        ).one() or 0
        session.exec(delete(Terminology).where(Terminology.oid == oid))
        
        # 清除示例SQL
        train_count = session.exec(
            select(func.count(DataTraining.id)).where(DataTraining.oid == oid)
        ).one() or 0
        session.exec(delete(DataTraining).where(DataTraining.oid == oid))
        
        session.commit()
        print(f"  已清除旧数据: {term_count} 条术语, {train_count} 条示例SQL")
    except Exception as e:
        session.rollback()
        print(f"  ⚠️ 清除数据时出错: {e}")
        raise


def init_terminology_data(session: Session, oid: int = 1, datasource_id: int = None):
    """初始化术语库数据"""
    
    created_count = 0
    
    for term_data in TERMINOLOGIES:
        # 创建主术语 - 全局适用，不限定特定数据源
        main_term = Terminology(
            oid=oid,
            word=term_data["word"],
            description=term_data["description"],
            sql_mapping=term_data.get("sql_mapping"),
            create_time=datetime.now(),
            enabled=True,
            specific_ds=False,  # 改为False，全局适用
            datasource_ids=[]   # 空数组表示适用于所有数据源
        )
        session.add(main_term)
        session.flush()
        session.refresh(main_term)
        
        # 创建同义词 - 也是全局适用
        for other_word in term_data.get("other_words", []):
            child_term = Terminology(
                oid=oid,
                pid=main_term.id,
                word=other_word,
                create_time=datetime.now(),
                enabled=True,
                specific_ds=False,  # 改为False，全局适用
                datasource_ids=[]   # 空数组表示适用于所有数据源
            )
            session.add(child_term)
        
        created_count += 1
        print(f"  ✓ {term_data['word']} (同义词: {len(term_data.get('other_words', []))}个)")
    
    session.commit()
    return created_count


def init_sql_examples(session: Session, oid: int = 1, datasource_id: int = None):
    """初始化示例SQL数据，存储前使用sqlparse验证SQL语法，跳过无效示例。"""
    import sqlparse
    
    created_count = 0
    skipped_count = 0
    
    for example in SQL_EXAMPLES:
        sql_text = example["description"]
        
        try:
            parsed = sqlparse.parse(sql_text)
            if not parsed or not parsed[0].tokens:
                print(f"  ⚠️ 跳过（SQL解析为空）: {example['question']}")
                skipped_count += 1
                continue
            # 检查是否以 SELECT 开头（只允许查询语句）
            first_token = parsed[0].token_first(skip_cm=True, skip_ws=True)
            if first_token and first_token.ttype is sqlparse.tokens.Keyword.DML:
                if first_token.normalized.upper() not in ('SELECT',):
                    print(f"  ⚠️ 跳过（非SELECT语句）: {example['question']}")
                    skipped_count += 1
                    continue
        except Exception as e:
            print(f"  ⚠️ 跳过（SQL验证异常: {e}）: {example['question']}")
            skipped_count += 1
            continue
        
        training = DataTraining(
            oid=oid,
            datasource=None,  # 不使用旧字段
            question=example["question"],
            description=example["description"],
            create_time=datetime.now(),
            enabled=True,
            specific_ds=False,  # 全局适用
            datasource_ids=[]   # 空数组表示适用于所有数据源
        )
        session.add(training)
        created_count += 1
        print(f"  ✓ {example['question']}")
    
    if skipped_count > 0:
        print(f"  ⚠️ 共跳过 {skipped_count} 条无效SQL示例")
    
    session.commit()
    return created_count


def main():
    print("=" * 60)
    print("商业级RAG知识库数据更新")
    print("ChatBI — 基于RAG与大语言模型的商业智能分析对话系统")
    print("=" * 60)
    
    with Session(engine) as session:
        # 使用默认工作空间ID=1
        oid = 1
        
        print(f"\n📊 工作空间ID: {oid}")
        print("💡 提示: 数据将全局适用于所有数据源")
        
        # 清除旧数据
        print("\n🗑️  清除旧数据...")
        clear_existing_data(session, oid=oid)
        
        # 初始化术语库 - 不指定datasource_id，全局适用
        print("\n📚 创建商业级术语库...")
        term_count = init_terminology_data(session, oid=oid, datasource_id=None)
        
        # 初始化示例SQL - 不指定datasource_id，全局适用
        print("\n📖 创建商业级SQL示例...")
        sql_count = init_sql_examples(session, oid=oid, datasource_id=None)
        
        print("\n" + "=" * 60)
        print("商业级RAG知识库更新完成!")
        print("=" * 60)
        print(f"\n📊 数据统计:")
        print(f"   - 商业术语库: {term_count} 个术语")
        print(f"   - SQL示例库: {sql_count} 个示例")
        print(f"\n📋 商业级覆盖:")
        print(f"   • 销售指标: 销售额、订单数、客单价、GMV")
        print(f"   • 财务指标: 毛利率、净利润率、ROI")
        print(f"   • 增长指标: 同比增长、环比增长")
        print(f"   • 客户指标: 复购率、CLV、留存率、流失率、转化率、ARPU")
        print(f"   • 运营指标: 库存周转率、坪效、人效、市场占有率")
        print(f"   • 电商指标: DAU、MAU、UV、SKU")
        print(f"\n💡 特性:")
        print(f"   - 所有数据全局适用（specific_ds=False）")
        print(f"   - 适用于所有数据源（datasource_ids=[]）")
        print("\n💡 提示: 如需生成向量嵌入，请运行:")
        print("   python scripts/generate_embeddings.py")


if __name__ == "__main__":
    main()
