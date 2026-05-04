#!/usr/bin/env python3
"""ChatBI 完整RAG知识库初始化脚本"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from sqlmodel import Session, select, func, delete as sql_delete
from sqlalchemy import and_, or_
from common.core.db import engine
from apps.terminology.models.terminology_model import Terminology
from apps.data_training.models.data_training_model import DataTraining
from common.chatbi.custom_prompt import PromptSQL, PromptAnalysis, PromptForecast, CustomPromptTypeEnum


TERMINOLOGIES = [
    # ── 销售核心指标 ──
    {
        "word": "销售额",
        "description": "指商品或服务销售所获得的总收入金额，是衡量企业经营规模的核心业务指标。计算公式：销售额 = 销售数量 × 单价。在SQL中通常使用SUM(\"销售额\")进行汇总。",
        "sql_mapping": 'SUM("销售额")',
        "other_words": ["营业额", "销售收入", "营收", "总收入", "收入", "Revenue", "总销售额"]
    },
    {
        "word": "订单数",
        "description": "指在一定时期内完成的订单总数量，反映业务活动的活跃程度和市场需求。在SQL中通常使用SUM(\"订单数\")或COUNT(*)进行统计。",
        "sql_mapping": 'SUM("订单数")',
        "other_words": ["订单量", "订单数量", "成交量", "交易数", "单量", "总订单数"]
    },
    {
        "word": "客单价",
        "description": "平均每个客户或每笔订单的消费金额。计算公式：客单价 = 总销售额 ÷ 订单数。是衡量消费水平的重要业务指标。",
        "sql_mapping": 'ROUND(AVG("客单价"), 2)',
        "other_words": ["平均订单金额", "单均价", "订单均价", "平均消费", "均价", "平均客单价"]
    },
    # ── 财务指标 ──
    {
        "word": "毛利",
        "description": "销售收入减去销售成本后的利润。计算公式：毛利 = 销售收入 - 销售成本。反映企业产品的基本盈利能力。",
        "sql_mapping": 'SUM("毛利")',
        "other_words": ["毛利润", "销售毛利", "总毛利"]
    },
    {
        "word": "毛利率",
        "description": "毛利占销售收入的百分比，衡量企业产品定价能力和成本控制水平。计算公式：毛利率 = (销售额 - 成本) ÷ 销售额 × 100%。当表中有毛利字段时：毛利率 = 毛利 ÷ 销售额 × 100%。",
        "sql_mapping": 'ROUND(SUM("毛利") * 100.0 / NULLIF(SUM("销售额"), 0), 2)',
        "other_words": ["销售毛利率", "Gross Margin", "利润率"]
    },
    {
        "word": "成本",
        "description": "生产或采购商品所花费的费用。在企业数据分析中，成本是计算毛利的关键因素。",
        "sql_mapping": 'SUM("成本")',
        "other_words": ["销售成本", "采购成本", "总成本"]
    },
    # ── 增长分析指标 ──
    {
        "word": "同比增长",
        "description": "与去年同期相比的增长率，用于消除季节性因素的影响。计算公式：同比增长率 = (本期值 - 去年同期值) ÷ 去年同期值 × 100%。",
        "sql_mapping": "同比增长率",
        "other_words": ["同比", "年同比", "YoY", "去年同期", "同比增长率"]
    },
    {
        "word": "环比增长",
        "description": "与上一期（如上月、上周）相比的增长率，反映短期变化趋势。计算公式：环比增长率 = (本期值 - 上期值) ÷ 上期值 × 100%。",
        "sql_mapping": "环比增长率",
        "other_words": ["环比", "月环比", "MoM", "周环比", "上期对比", "环比增长率"]
    },
    # ── 时间与趋势 ──
    {
        "word": "日期",
        "description": "交易发生的时间，用于时间序列分析和趋势预测。是进行趋势分析和预测的必要字段。",
        "sql_mapping": '"日期"',
        "other_words": ["时间", "交易日期", "订单日期", "销售日期", "日"]
    },
    {
        "word": "趋势",
        "description": "数据随时间变化的方向和规律，用于预测未来走势和发现业务规律。趋势分析需要按日期排序。",
        "sql_mapping": 'ORDER BY "日期" ASC',
        "other_words": ["走势", "变化趋势", "发展趋势", "增长趋势", "趋势分析", "销售趋势"]
    },
    {
        "word": "月份",
        "description": "按月汇总数据的时间维度，用于月度分析和同比环比计算。",
        "sql_mapping": "TO_CHAR(\"日期\", 'YYYY-MM')",
        "other_words": ["月", "月度", "每月", "按月"]
    },
    # ── 统计函数 ──
    {
        "word": "汇总",
        "description": "将多条数据记录合并计算，得出总计值。常用于统计总销售额、总订单数等业务汇总分析。",
        "sql_mapping": "SUM()",
        "other_words": ["合计", "总计", "求和", "统计", "累计", "总"]
    },
    {
        "word": "平均值",
        "description": "一组数据的算术平均数，用于衡量数据的集中趋势。在企业数据分析中常用于计算平均客单价、平均销售额等。",
        "sql_mapping": "AVG()",
        "other_words": ["均值", "平均", "AVG", "平均数"]
    },
    {
        "word": "最大值",
        "description": "一组数据中的最大数值，用于找出峰值或最高记录。在企业数据分析中常用于找出最高销售额、最大订单等。",
        "sql_mapping": "MAX()",
        "other_words": ["最高", "峰值", "MAX", "最高值", "最大"]
    },
    {
        "word": "最小值",
        "description": "一组数据中的最小数值，用于找出谷值或最低记录。在企业数据分析中常用于找出最低销售额、最小订单等。",
        "sql_mapping": "MIN()",
        "other_words": ["最低", "谷值", "MIN", "最低值", "最小"]
    },
    # ── 排名与限制 ──
    {
        "word": "排名",
        "description": "按某个指标对数据进行排序，找出前几名或后几名。常用于销售排行榜、业绩排名等场景。",
        "sql_mapping": "ORDER BY ... DESC",
        "other_words": ["排行", "排序", "TOP", "前几名", "榜单"]
    },
    {
        "word": "前10",
        "description": "取排名前10的记录，常用于TOP10分析。在SQL中使用LIMIT 10实现。",
        "sql_mapping": "LIMIT 10",
        "other_words": ["TOP10", "前十", "前10名", "十大"]
    },
    # ── 区域与渠道 ──
    # 补充分类维度术语，与 init_rag_data.py 对齐
    {
        "word": "区域",
        "description": "指销售区域或地理区域，用于区域销售分析和市场布局。在数据表中对应「区域」或「销售区域」字段。",
        "sql_mapping": '"区域"',
        "other_words": ["地区", "区", "地域", "销售区域"]
    },
    {
        "word": "渠道",
        "description": "指销售渠道，如线上、线下、电商平台等。用于渠道效益分析和渠道策略优化。",
        "sql_mapping": '"渠道"',
        "other_words": ["销售渠道", "渠道类型", "分销渠道"]
    },
    {
        "word": "产品",
        "description": "指企业销售的商品或服务。在数据表中对应「产品」或「产品名称」字段。",
        "sql_mapping": '"产品"',
        "other_words": ["商品", "产品名", "品名"]
    },
    {
        "word": "类别",
        "description": "指产品类别或分类，用于品类分析和品类管理。在数据表中对应「产品类别」或「类别」字段。",
        "sql_mapping": '"产品类别"',
        "other_words": ["分类", "产品类别", "产品分类", "品类"]
    },
]


SQL_EXAMPLES = [
    # ── 基础汇总查询 ──
    {
        "question": "查询总销售额",
        "description": 'SELECT SUM("销售额") AS "总销售额" FROM "{table}"'
    },
    {
        "question": "查询总订单数",
        "description": 'SELECT SUM("订单数") AS "总订单数" FROM "{table}"'
    },
    {
        "question": "查询平均客单价",
        "description": 'SELECT ROUND(AVG("客单价"), 2) AS "平均客单价" FROM "{table}"'
    },
    {
        "question": "查询销售数据概览",
        "description": 'SELECT SUM("销售额") AS "总销售额", SUM("订单数") AS "总订单数", ROUND(AVG("客单价"), 2) AS "平均客单价" FROM "{table}"'
    },
    {
        "question": "查询总毛利",
        "description": 'SELECT SUM("毛利") AS "总毛利" FROM "{table}"'
    },
    {
        "question": "查询平均毛利率",
        "description": 'SELECT ROUND(SUM("毛利") * 100.0 / NULLIF(SUM("销售额"), 0), 2) AS "平均毛利率%" FROM "{table}"'
    },
    # ── 时间序列分析 ──
    {
        "question": "按日期查询销售额",
        "description": 'SELECT "日期", "销售额" FROM "{table}" ORDER BY "日期" ASC'
    },
    {
        "question": "查询销售额趋势",
        "description": 'SELECT "日期", "销售额" FROM "{table}" ORDER BY "日期" ASC'
    },
    {
        "question": "按月统计销售额",
        "description": "SELECT TO_CHAR(\"日期\", 'YYYY-MM') AS \"月份\", SUM(\"销售额\") AS \"月销售额\" FROM \"{table}\" GROUP BY TO_CHAR(\"日期\", 'YYYY-MM') ORDER BY \"月份\" ASC"
    },
    {
        "question": "展示销售趋势",
        "description": 'SELECT "日期", "销售额", "订单数" FROM "{table}" ORDER BY "日期" ASC'
    },
    {
        "question": "月度销售趋势",
        "description": "SELECT TO_CHAR(\"日期\", 'YYYY-MM') AS \"月份\", SUM(\"销售额\") AS \"月销售额\", SUM(\"订单数\") AS \"月订单数\" FROM \"{table}\" GROUP BY TO_CHAR(\"日期\", 'YYYY-MM') ORDER BY \"月份\" ASC"
    },
    {
        "question": "每日客单价变化",
        "description": 'SELECT "日期", "客单价" FROM "{table}" ORDER BY "日期" ASC'
    },
    # ── 极值与排名查询 ──
    {
        "question": "查询销售额最高的日期",
        "description": 'SELECT "日期", "销售额" FROM "{table}" ORDER BY "销售额" DESC LIMIT 1'
    },
    {
        "question": "查询销售额最低的日期",
        "description": 'SELECT "日期", "销售额" FROM "{table}" ORDER BY "销售额" ASC LIMIT 1'
    },
    {
        "question": "查询订单数最多的日期",
        "description": 'SELECT "日期", "订单数" FROM "{table}" ORDER BY "订单数" DESC LIMIT 1'
    },
    {
        "question": "查询销售额前10的日期",
        "description": 'SELECT "日期", "销售额" FROM "{table}" ORDER BY "销售额" DESC LIMIT 10'
    },
    {
        "question": "查询销售额后10的日期",
        "description": 'SELECT "日期", "销售额" FROM "{table}" ORDER BY "销售额" ASC LIMIT 10'
    },
    # ── 统计分析 ──
    {
        "question": "查询销售额的最大值和最小值",
        "description": 'SELECT MAX("销售额") AS "最高销售额", MIN("销售额") AS "最低销售额" FROM "{table}"'
    },
    {
        "question": "查询订单数的统计信息",
        "description": 'SELECT SUM("订单数") AS "总订单数", ROUND(AVG("订单数"), 2) AS "平均订单数", MAX("订单数") AS "最高订单数", MIN("订单数") AS "最低订单数" FROM "{table}"'
    },
    {
        "question": "查询数据记录数",
        "description": 'SELECT COUNT(*) AS "记录数" FROM "{table}"'
    },
    {
        "question": "查询销售额统计",
        "description": 'SELECT SUM("销售额") AS "总销售额", ROUND(AVG("销售额"), 2) AS "平均销售额", MAX("销售额") AS "最高销售额", MIN("销售额") AS "最低销售额" FROM "{table}"'
    },
    # ── 环比增长分析 ──
    {
        "question": "月度环比增长率",
        "description": "WITH monthly AS (SELECT TO_CHAR(\"日期\", 'YYYY-MM') AS \"月份\", SUM(\"销售额\") AS \"月销售额\" FROM \"{table}\" GROUP BY TO_CHAR(\"日期\", 'YYYY-MM')) SELECT \"月份\", \"月销售额\", ROUND((\"月销售额\" - LAG(\"月销售额\") OVER (ORDER BY \"月份\")) * 100.0 / NULLIF(LAG(\"月销售额\") OVER (ORDER BY \"月份\"), 0), 2) AS \"环比增长率%\" FROM monthly ORDER BY \"月份\""
    },
    # ── 综合查询 ──
    {
        "question": "查询所有销售数据",
        "description": 'SELECT "日期", "销售额", "订单数", "客单价" FROM "{table}" ORDER BY "日期" ASC'
    },
    {
        "question": "查询最近的销售数据",
        "description": 'SELECT "日期", "销售额", "订单数", "客单价" FROM "{table}" ORDER BY "日期" DESC LIMIT 10'
    },
    {
        "question": "这个数据源有哪些数据",
        "description": 'SELECT * FROM "{table}" LIMIT 20'
    },
    # ── 分类/分组维度查询（通用模式，适配不同表结构）──
    # 补充分类维度的 SQL 示例，覆盖 GROUP BY 类查询
    {
        "question": "查询各产品类别的销售额",
        "description": 'SELECT "产品类别", SUM("销售额") AS "销售额" FROM "{table}" GROUP BY "产品类别" ORDER BY "销售额" DESC'
    },
    {
        "question": "按类别统计销售数据",
        "description": 'SELECT "产品类别", SUM("销售额") AS "总销售额", SUM("订单数") AS "总订单数" FROM "{table}" GROUP BY "产品类别" ORDER BY "总销售额" DESC'
    },
    {
        "question": "各区域销售额对比",
        "description": 'SELECT "区域", SUM("销售额") AS "总销售额" FROM "{table}" GROUP BY "区域" ORDER BY "总销售额" DESC'
    },
    {
        "question": "按渠道统计销售额",
        "description": 'SELECT "渠道", SUM("销售额") AS "总销售额", SUM("订单数") AS "总订单数" FROM "{table}" GROUP BY "渠道" ORDER BY "总销售额" DESC'
    },
    {
        "question": "各产品销售排名",
        "description": 'SELECT "产品", SUM("销售额") AS "总销售额" FROM "{table}" GROUP BY "产品" ORDER BY "总销售额" DESC LIMIT 10'
    },
    {
        "question": "查询各类别的平均客单价",
        "description": 'SELECT "产品类别", ROUND(AVG("客单价"), 2) AS "平均客单价" FROM "{table}" GROUP BY "产品类别" ORDER BY "平均客单价" DESC'
    },
    {
        "question": "各类别销售额占比",
        "description": 'SELECT "产品类别", SUM("销售额") AS "销售额", ROUND(SUM("销售额") * 100.0 / (SELECT SUM("销售额") FROM "{table}"), 2) AS "占比%" FROM "{table}" GROUP BY "产品类别" ORDER BY "销售额" DESC'
    },
    {
        "question": "按区域和月份统计销售额",
        "description": "SELECT \"区域\", TO_CHAR(\"日期\", 'YYYY-MM') AS \"月份\", SUM(\"销售额\") AS \"月销售额\" FROM \"{table}\" GROUP BY \"区域\", TO_CHAR(\"日期\", 'YYYY-MM') ORDER BY \"区域\", \"月份\" ASC"
    },
    {
        "question": "销售额最高的类别",
        "description": 'SELECT "产品类别", SUM("销售额") AS "总销售额" FROM "{table}" GROUP BY "产品类别" ORDER BY "总销售额" DESC LIMIT 1'
    },
    {
        "question": "各类别订单数统计",
        "description": 'SELECT "产品类别", SUM("订单数") AS "总订单数", COUNT(*) AS "记录数" FROM "{table}" GROUP BY "产品类别" ORDER BY "总订单数" DESC'
    },
    # ── 毛利/利润分析（按产品/类别维度）──
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
        "description": 'SELECT "产品", SUM("毛利") AS "总毛利", ROUND(SUM("毛利") * 100.0 / NULLIF(SUM("销售额"), 0), 2) AS "毛利率%" FROM "{table}" GROUP BY "产品" ORDER BY "总毛利" DESC'
    },
    {
        "question": "各产品类别的毛利对比",
        "description": 'SELECT "产品类别", SUM("毛利") AS "总毛利", SUM("销售额") AS "总销售额", ROUND(SUM("毛利") * 100.0 / NULLIF(SUM("销售额"), 0), 2) AS "毛利率%" FROM "{table}" GROUP BY "产品类别" ORDER BY "总毛利" DESC'
    },
    {
        "question": "毛利率最高的产品",
        "description": 'SELECT "产品", ROUND(SUM("毛利") * 100.0 / NULLIF(SUM("销售额"), 0), 2) AS "毛利率%", SUM("毛利") AS "总毛利" FROM "{table}" GROUP BY "产品" ORDER BY "毛利率%" DESC LIMIT 5'
    },
    {
        "question": "各产品的利润贡献",
        "description": 'SELECT "产品", SUM("毛利") AS "总毛利", ROUND(SUM("毛利") * 100.0 / NULLIF((SELECT SUM("毛利") FROM "{table}"), 0), 2) AS "利润贡献占比%" FROM "{table}" GROUP BY "产品" ORDER BY "总毛利" DESC'
    },
]



CUSTOM_PROMPTS = [
    # ============ SQL生成提示词 (GENERATE_SQL) ============
    
    {
        "type": "GENERATE_SQL",
        "name": "时间范围查询规范",
        "prompt": """当用户查询涉及时间范围时，请遵循以下规则：
1. 使用标准日期格式 'YYYY-MM-DD' 进行比较
2. 对于"最近N天"，使用 WHERE "日期" >= CURRENT_DATE - INTERVAL 'N days'
3. 对于"本月"，使用 WHERE TO_CHAR("日期", 'YYYY-MM') = TO_CHAR(CURRENT_DATE, 'YYYY-MM')
4. 对于"去年"，使用 WHERE EXTRACT(YEAR FROM "日期") = EXTRACT(YEAR FROM CURRENT_DATE) - 1
5. 始终按日期升序排列以展示趋势：ORDER BY "日期" ASC"""
    },
    {
        "type": "GENERATE_SQL",
        "name": "数值格式化规范",
        "prompt": """处理数值字段时，请遵循以下格式化规则：
1. 金额类字段（销售额、成本、毛利）保留2位小数：ROUND(SUM("销售额"), 2)
2. 百分比类字段（毛利率、增长率）保留2位小数并添加%标识
3. 平均值计算使用ROUND函数：ROUND(AVG("客单价"), 2)
4. 避免除零错误：使用NULLIF(分母, 0)
5. 大数值使用千分位格式化（在应用层处理）"""
    },
    {
        "type": "GENERATE_SQL",
        "name": "聚合查询规范",
        "prompt": """进行聚合查询时，请遵循以下规则：
     1. 汇总查询使用SUM()：SELECT SUM("销售额") AS "总销售额"
     """
    },
    {
        "type": "GENERATE_SQL",
        "name": "月度分组规范",
        "prompt": """按月份分组统计时，请使用以下标准格式：
     1. 提取月份：TO_CHAR("日期", 'YYYY-MM') AS "月份"
     """
    },
    {
        "type": "GENERATE_SQL",
        "name": "环比增长计算规范",
        "prompt": """计算环比增长率时，请使用窗口函数LAG：
     1. 使用LAG函数获取上期值：LAG(SUM("销售额")) OVER (ORDER BY "月份")
     """
    },
    
    # ============ 数据分析提示词 (ANALYSIS) ============
    
    {
        "type": "ANALYSIS",
        "name": "销售趋势分析框架",
        "prompt": """进行销售趋势分析时，请按以下框架组织分析报告："""
    },
    {
        "type": "ANALYSIS",
        "name": "数据洞察输出规范",
        "prompt": """生成数据分析报告时，请遵循以下规范："""
    },
    {
        "type": "ANALYSIS",
        "name": "对比分析方法",
        "prompt": """进行数据对比分析时，请使用以下方法："""
    },
    
    # ============ 数据预测提示词 (PREDICT_DATA) ============
    
    {
        "type": "PREDICT_DATA",
        "name": "预测报告框架",
        "prompt": """生成数据预测报告时，请按以下框架组织："""
    },
    {
        "type": "PREDICT_DATA",
        "name": "预测方法说明",
        "prompt": """在预测报告中说明预测方法时，请包含以下内容："""
    },
    {
        "type": "PREDICT_DATA",
        "name": "置信度解释规范",
        "prompt": """解释预测置信度时，请使用以下标准："""
    },
]


# ============================================================

def clear_all_data(session: Session, oid: int = 1):
    """清除所有RAG知识库数据"""
    print("  清除术语库...")
    session.exec(sql_delete(Terminology).where(Terminology.oid == oid))
    
    print("  清除SQL示例库...")
    session.exec(sql_delete(DataTraining).where(DataTraining.oid == oid))
    
    print("  清除自定义提示词...")
    session.exec(sql_delete(PromptSQL).where(PromptSQL.oid == oid))
    session.exec(sql_delete(PromptAnalysis).where(PromptAnalysis.oid == oid))
    session.exec(sql_delete(PromptForecast).where(PromptForecast.oid == oid))
    
    session.commit()
    print("  ✓ 清除完成")


def init_terminologies(session: Session, oid: int = 1) -> int:
    """初始化术语库"""
    created_count = 0
    
    for term_data in TERMINOLOGIES:
        # 创建主术语
        main_term = Terminology(
            oid=oid,
            word=term_data["word"],
            description=term_data["description"],
            sql_mapping=term_data.get("sql_mapping"),
            create_time=datetime.now(),
            enabled=True,
        )
        session.add(main_term)
        session.flush()
        session.refresh(main_term)
        
        # 创建同义词
        for other_word in term_data.get("other_words", []):
            child_term = Terminology(
                oid=oid,
                pid=main_term.id,
                word=other_word,
                create_time=datetime.now(),
                enabled=True,
            )
            session.add(child_term)
        
        created_count += 1
        synonym_count = len(term_data.get("other_words", []))
        print(f"    ✓ {term_data['word']} (同义词: {synonym_count}个)")
    
    session.commit()
    return created_count


def init_sql_examples(session: Session, oid: int = 1) -> int:
    """初始化SQL示例库"""
    created_count = 0
    
    for example in SQL_EXAMPLES:
        training = DataTraining(
            oid=oid,
            datasource=None,
            question=example["question"],
            description=example["description"],
            create_time=datetime.now(),
            enabled=True,
        )
        session.add(training)
        created_count += 1
        print(f"    ✓ {example['question']}")
    
    session.commit()
    return created_count


def init_custom_prompts(session: Session, oid: int = 1) -> dict:
    """初始化自定义提示词"""
    counts = {"GENERATE_SQL": 0, "ANALYSIS": 0, "PREDICT_DATA": 0}
    
    _type_model_map = {
        "GENERATE_SQL": PromptSQL,
        "ANALYSIS": PromptAnalysis,
        "PREDICT_DATA": PromptForecast,
    }
    
    for prompt_data in CUSTOM_PROMPTS:
        Model = _type_model_map[prompt_data["type"]]
        prompt = Model(
            oid=oid,
            name=prompt_data["name"],
            prompt=prompt_data["prompt"],
            create_time=datetime.now()
        )
        session.add(prompt)
        counts[prompt_data["type"]] += 1
        print(f"    ✓ [{prompt_data['type']}] {prompt_data['name']}")
    
    session.commit()
    return counts


def main():
    print("=" * 70)
    print("  ChatBI — 完整RAG知识库初始化")
    print("  基于RAG与大语言模型的商业智能分析对话系统")
    print("  毕业答辩演示专用")
    print("=" * 70)
    
    oid = 1  # 默认工作空间
    
    with Session(engine) as session:
        # 清除旧数据
        print("\n🗑️  清除旧数据...")
        clear_all_data(session, oid)
        
        # 初始化术语库
        print("\n📚 初始化术语库（RAG向量检索）...")
        term_count = init_terminologies(session, oid)
        
        # 初始化SQL示例库
        print("\n📖 初始化SQL示例库（RAG向量检索）...")
        sql_count = init_sql_examples(session, oid)
        
        # 初始化自定义提示词
        print("\n📝 初始化自定义提示词（关键词匹配）...")
        prompt_counts = init_custom_prompts(session, oid)
        
        # 统计
        print("\n" + "=" * 70)
        print("RAG知识库初始化完成！")
        print("=" * 70)
        
        print("\n📊 知识库统计:")
        print(f"   术语库: {term_count} 个术语（含同义词）")
        print(f"   SQL示例库: {sql_count} 个示例")
        print(f"   自定义提示词:")
        print(f"      - SQL生成提示词: {prompt_counts['GENERATE_SQL']} 条")
        print(f"      - 数据分析提示词: {prompt_counts['ANALYSIS']} 条")
        print(f"      - 数据预测提示词: {prompt_counts['PREDICT_DATA']} 条")
        
        print("\n📋 三大核心模块的RAG支撑:")
        print("   1. 推荐问题 → 术语库 + Schema检索")
        print("   2. 思考过程 → 展示RAG检索结果和质量评分")
        print("   3. 输出回答 → 术语库 + SQL示例 + 自定义提示词")
        
        print("\n💡 答辩演示建议:")
        print("   1. 上传演示数据Excel（每日销售汇总表）")
        print("   2. 观察推荐问题的生成（基于RAG检索）")
        print("   3. 提问并展开思考过程面板")
        print("   4. 重点讲解RAG检索阶段的术语匹配")
        print("   5. 演示数据分析和数据预测功能")
        
        print("\n⚠️  注意: 如需生成向量嵌入，请运行:")
        print("   python scripts/generate_embeddings.py")


if __name__ == "__main__":
    main()
