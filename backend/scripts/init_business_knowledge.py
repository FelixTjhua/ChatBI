#!/usr/bin/env python3
"""ChatBI 商业级知识库初始化脚本"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from sqlmodel import Session, select, func
from sqlalchemy import and_
from common.core.db import engine
from apps.terminology.models.terminology_model import Terminology
from apps.data_training.models.data_training_model import DataTraining


BUSINESS_TERMINOLOGIES = [
    # ── 销售核心指标 ──
    {
        "word": "销售额",
        "description": "指商品或服务销售所获得的总收入金额，是衡量企业经营规模的核心业务指标。计算公式：销售额 = 销售数量 × 单价。",
        "sql_mapping": 'SUM("销售额")',
        "other_words": ["营业额", "销售收入", "营收", "总收入", "收入", "Revenue"]
    },
    {
        "word": "订单数",
        "description": "指在一定时期内完成的订单总数量，反映业务活动的活跃程度和市场需求。",
        "sql_mapping": 'SUM("订单数")',
        "other_words": ["订单量", "订单数量", "成交量", "交易数", "单量"]
    },
    {
        "word": "客单价",
        "description": "平均每个客户或每笔订单的消费金额。计算公式：客单价 = 总销售额 ÷ 订单数（或客户数）。是衡量消费水平的重要业务指标。",
        "sql_mapping": 'ROUND(AVG("客单价"), 2)',
        "other_words": ["平均订单金额", "单均价", "订单均价", "平均消费", "均价"]
    },
    {
        "word": "GMV",
        "description": "商品交易总额（Gross Merchandise Volume），指一定时间内的成交总额，包含已付款和未付款订单。是电商和零售行业的核心业务指标。",
        "sql_mapping": 'SUM("销售额")',
        "other_words": ["交易总额", "成交总额", "商品交易额"]
    },
    # ── 财务指标 ──
    {
        "word": "毛利",
        "description": "销售收入减去销售成本后的利润。计算公式：毛利 = 销售收入 - 销售成本。反映企业产品的基本盈利能力。",
        "sql_mapping": 'SUM("销售额") - SUM("成本")',
        "other_words": ["毛利润", "销售毛利"]
    },
    {
        "word": "毛利率",
        "description": "毛利占销售收入的百分比，衡量企业产品定价能力和成本控制水平。计算公式：毛利率 = (销售收入 - 销售成本) ÷ 销售收入 × 100%。",
        "sql_mapping": 'ROUND((SUM("销售额") - SUM("成本")) * 100.0 / NULLIF(SUM("销售额"), 0), 2)',
        "other_words": ["销售毛利率", "Gross Margin"]
    },
    {
        "word": "净利润",
        "description": "企业在一定时期内扣除所有成本、费用和税金后的最终利润。计算公式：净利润 = 总收入 - 总成本 - 税费。",
        "sql_mapping": 'SUM("净利润")',
        "other_words": ["纯利润", "税后利润", "净收益", "Net Profit"]
    },
    {
        "word": "净利润率",
        "description": "净利润占销售收入的百分比，衡量企业整体盈利能力。计算公式：净利润率 = 净利润 ÷ 销售收入 × 100%。",
        "sql_mapping": 'ROUND(SUM("净利润") * 100.0 / NULLIF(SUM("销售额"), 0), 2)',
        "other_words": ["净利率", "利润率", "Net Margin"]
    },
    {
        "word": "ROI",
        "description": "投资回报率（Return On Investment），衡量投资效益的核心业务指标。计算公式：ROI = (投资收益 - 投资成本) ÷ 投资成本 × 100%。",
        "sql_mapping": 'ROUND((SUM("收益") - SUM("投资成本")) * 100.0 / NULLIF(SUM("投资成本"), 0), 2)',
        "other_words": ["投资回报率", "投资回报", "回报率"]
    },
    # ── 增长分析指标 ──
    {
        "word": "同比增长",
        "description": "与去年同期相比的增长率，用于消除季节性因素的影响。计算公式：同比增长率 = (本期值 - 去年同期值) ÷ 去年同期值 × 100%。",
        "sql_mapping": "ROUND((本期值 - 去年同期值) * 100.0 / NULLIF(去年同期值, 0), 2)",
        "other_words": ["同比", "年同比", "YoY", "去年同期", "同比增长率"]
    },
    {
        "word": "环比增长",
        "description": "与上一期（如上月、上周）相比的增长率，反映短期变化趋势。计算公式：环比增长率 = (本期值 - 上期值) ÷ 上期值 × 100%。",
        "sql_mapping": "ROUND((本期值 - LAG(本期值) OVER (ORDER BY 日期)) * 100.0 / NULLIF(LAG(本期值) OVER (ORDER BY 日期), 0), 2)",
        "other_words": ["环比", "月环比", "MoM", "周环比", "上期对比", "环比增长率"]
    },
    # ── 客户管理指标 ──
    {
        "word": "复购率",
        "description": "重复购买的客户占总客户数的比例，衡量客户忠诚度和产品粘性。计算公式：复购率 = 重复购买客户数 ÷ 总客户数 × 100%。",
        "sql_mapping": 'COUNT(DISTINCT CASE WHEN "购买次数" > 1 THEN "客户名称" END) * 100.0 / NULLIF(COUNT(DISTINCT "客户名称"), 0)',
        "other_words": ["回购率", "重复购买率", "Repeat Purchase Rate"]
    },
    {
        "word": "客户生命周期价值",
        "description": "CLV（Customer Lifetime Value），指一个客户在整个合作期间为企业带来的总价值。计算公式：CLV = 平均客单价 × 购买频率 × 客户生命周期。",
        "sql_mapping": 'AVG("客单价") * AVG("购买频率") * AVG("客户生命周期")',
        "other_words": ["CLV", "LTV", "客户终身价值", "生命周期价值", "用户价值"]
    },
    {
        "word": "客户留存率",
        "description": "在一定时间后仍然活跃或继续消费的客户比例，衡量客户维系能力。计算公式：留存率 = 期末留存客户数 ÷ 期初客户数 × 100%。",
        "sql_mapping": 'ROUND(COUNT(DISTINCT "留存客户") * 100.0 / NULLIF(COUNT(DISTINCT "期初客户"), 0), 2)',
        "other_words": ["留存率", "用户留存", "Retention Rate", "留存"]
    },
    {
        "word": "客户流失率",
        "description": "用户停止使用产品或服务的比例，与留存率互补。计算公式：流失率 = 1 - 留存率 = 流失客户数 ÷ 期初客户数 × 100%。",
        "sql_mapping": 'ROUND(COUNT(DISTINCT "流失客户") * 100.0 / NULLIF(COUNT(DISTINCT "期初客户"), 0), 2)',
        "other_words": ["流失率", "用户流失", "Churn Rate"]
    },
    {
        "word": "转化率",
        "description": "用户完成目标行为（如购买、注册）的比例。计算公式：转化率 = 完成目标行为的用户数 ÷ 总访问用户数 × 100%。是衡量营销效果的关键业务指标。",
        "sql_mapping": 'ROUND(COUNT(DISTINCT "转化用户") * 100.0 / NULLIF(COUNT(DISTINCT "访问用户"), 0), 2)',
        "other_words": ["转换率", "CVR", "Conversion Rate", "成交转化率"]
    },
    {
        "word": "ARPU",
        "description": "每用户平均收入（Average Revenue Per User），衡量每个用户贡献的平均收入。计算公式：ARPU = 总收入 ÷ 用户数。",
        "sql_mapping": 'ROUND(SUM("销售额") / NULLIF(COUNT(DISTINCT "客户名称"), 0), 2)',
        "other_words": ["每用户平均收入", "用户均收入", "人均收入"]
    },
    # ── 运营效率指标 ──
    {
        "word": "库存周转率",
        "description": "衡量库存流转速度的业务指标。计算公式：库存周转率 = 销售成本 ÷ 平均库存金额。周转率越高说明库存管理效率越好。",
        "sql_mapping": 'ROUND(SUM("销售成本") / NULLIF(AVG("库存金额"), 0), 2)',
        "other_words": ["存货周转率", "库存周转", "Inventory Turnover"]
    },
    {
        "word": "库存周转天数",
        "description": "库存从入库到售出的平均天数。计算公式：库存周转天数 = 365 ÷ 库存周转率。天数越少说明库存流转越快。",
        "sql_mapping": 'ROUND(365.0 / NULLIF(SUM("销售成本") / NULLIF(AVG("库存金额"), 0), 0), 1)',
        "other_words": ["存货周转天数", "库存天数"]
    },
    {
        "word": "坪效",
        "description": "每平方米营业面积产生的销售额，衡量零售门店空间利用效率。计算公式：坪效 = 销售额 ÷ 营业面积。",
        "sql_mapping": 'ROUND(SUM("销售额") / NULLIF(SUM("营业面积"), 0), 2)',
        "other_words": ["每平米销售额", "面积效率"]
    },
    {
        "word": "人效",
        "description": "每个员工产生的销售额或利润，衡量人力资源利用效率。计算公式：人效 = 销售额 ÷ 员工数。",
        "sql_mapping": 'ROUND(SUM("销售额") / NULLIF(COUNT(DISTINCT "员工"), 0), 2)',
        "other_words": ["人均产出", "人均销售额", "员工效率"]
    },
    {
        "word": "市场占有率",
        "description": "企业产品销售额占同类产品市场总销售额的比例。计算公式：市场占有率 = 企业销售额 ÷ 市场总销售额 × 100%。",
        "sql_mapping": 'ROUND(SUM("销售额") * 100.0 / NULLIF((SELECT SUM("销售额") FROM "{table}"), 0), 2)',
        "other_words": ["市场份额", "市占率", "Market Share"]
    },
    # ── 电商与流量指标 ──
    {
        "word": "DAU",
        "description": "日活跃用户数（Daily Active Users），指每日使用产品或服务的独立用户数量，衡量产品日常活跃度。",
        "sql_mapping": 'COUNT(DISTINCT "用户ID")',
        "other_words": ["日活", "日活用户", "日活跃用户"]
    },
    {
        "word": "MAU",
        "description": "月活跃用户数（Monthly Active Users），指每月使用产品或服务的独立用户数量，衡量产品整体用户规模。",
        "sql_mapping": 'COUNT(DISTINCT "用户ID")',
        "other_words": ["月活", "月活用户", "月活跃用户"]
    },
    {
        "word": "UV",
        "description": "独立访客数（Unique Visitor），指访问网站或应用的不重复用户数，衡量流量规模。",
        "sql_mapping": 'COUNT(DISTINCT "访客ID")',
        "other_words": ["独立访客", "访客数", "独立用户数"]
    },
    {
        "word": "SKU",
        "description": "库存量单位（Stock Keeping Unit），指商品的最小销售单位或品类编码，用于库存管理和商品分析。",
        "sql_mapping": 'COUNT(DISTINCT "商品编码")',
        "other_words": ["商品编码", "单品", "品类"]
    },
    # ── 通用分析术语 ──
    {
        "word": "日期",
        "description": "交易发生的时间，用于时间序列分析和趋势预测。对应数据表中的日期字段。",
        "sql_mapping": '"日期"',
        "other_words": ["时间", "交易日期", "订单日期", "销售日期", "日"]
    },
    {
        "word": "趋势",
        "description": "数据随时间变化的方向和规律，用于预测未来走势和发现业务规律。",
        "sql_mapping": 'ORDER BY "日期" ASC',
        "other_words": ["走势", "变化趋势", "发展趋势", "增长趋势", "趋势分析"]
    },
    {
        "word": "汇总",
        "description": "将多条数据记录合并计算，得出总计值。常用于统计总销售额、总订单数等业务汇总分析。",
        "sql_mapping": "SUM()",
        "other_words": ["合计", "总计", "求和", "统计", "累计"]
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
    # ── 区域与渠道 ──
    {
        "word": "区域",
        "description": "指销售区域或地理区域，用于区域销售分析和市场布局。在数据表中对应「销售区域」字段。",
        "sql_mapping": '"销售区域"',
        "other_words": ["地区", "区", "地域", "销售区域"]
    },
    {
        "word": "渠道",
        "description": "指销售渠道，如线上、线下、电商平台等。用于渠道效益分析和渠道策略优化。",
        "sql_mapping": '"渠道类型"',
        "other_words": ["销售渠道", "渠道类型", "分销渠道"]
    },
    {
        "word": "产品",
        "description": "指企业销售的商品或服务。在数据表中对应「产品名称」字段。",
        "sql_mapping": '"产品名称"',
        "other_words": ["商品", "产品名", "品名"]
    },
    {
        "word": "类别",
        "description": "指产品类别或分类，用于品类分析和品类管理。",
        "sql_mapping": '"产品类别"',
        "other_words": ["分类", "产品类别", "产品分类", "品类"]
    },
    # ── 成本与费用指标 ──
    {
        "word": "销售成本",
        "description": "为实现销售而直接发生的成本，包括采购成本、生产成本等。计算公式：销售成本 = 采购价 × 销售数量。",
        "sql_mapping": 'SUM("成本")',
        "other_words": ["成本", "COGS", "直接成本", "货物成本"]
    },
    {
        "word": "费用率",
        "description": "各项费用占销售收入的百分比，衡量企业费用控制水平。计算公式：费用率 = 费用总额 ÷ 销售收入 × 100%。",
        "sql_mapping": 'ROUND(SUM("费用") * 100.0 / NULLIF(SUM("销售额"), 0), 2)',
        "other_words": ["费销比", "费用占比", "Expense Ratio"]
    },
    {
        "word": "折扣率",
        "description": "实际成交价格相对于原价的折扣比例。计算公式：折扣率 = (原价 - 实际售价) ÷ 原价 × 100%。",
        "sql_mapping": 'ROUND((SUM("原价") - SUM("实际售价")) * 100.0 / NULLIF(SUM("原价"), 0), 2)',
        "other_words": ["折扣", "优惠率", "让利率", "Discount Rate"]
    },
    # ── 供应链指标 ──
    {
        "word": "缺货率",
        "description": "因库存不足导致无法满足客户需求的比例。计算公式：缺货率 = 缺货次数 ÷ 总需求次数 × 100%。",
        "sql_mapping": 'ROUND(SUM(CASE WHEN "库存" <= 0 THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0), 2)',
        "other_words": ["断货率", "Stock-out Rate"]
    },
    {
        "word": "退货率",
        "description": "退货订单数占总订单数的比例，衡量产品质量和客户满意度。计算公式：退货率 = 退货订单数 ÷ 总订单数 × 100%。",
        "sql_mapping": 'ROUND(SUM(CASE WHEN "状态" = \'退货\' THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0), 2)',
        "other_words": ["退款率", "Return Rate", "退单率"]
    },
    # ── 营销指标 ──
    {
        "word": "获客成本",
        "description": "获取一个新客户所需的平均成本。计算公式：CAC = 营销总费用 ÷ 新增客户数。是衡量营销效率的关键指标。",
        "sql_mapping": 'ROUND(SUM("营销费用") / NULLIF(COUNT(DISTINCT "新客户"), 0), 2)',
        "other_words": ["CAC", "客户获取成本", "拉新成本", "Customer Acquisition Cost"]
    },
    {
        "word": "投入产出比",
        "description": "营销投入与产出收益的比值。计算公式：投入产出比 = 营销带来的收入 ÷ 营销投入成本。",
        "sql_mapping": 'ROUND(SUM("销售额") / NULLIF(SUM("营销费用"), 0), 2)',
        "other_words": ["ROI", "投产比", "营销ROI"]
    },
    # ── 时间维度术语 ──
    {
        "word": "季度",
        "description": "一年分为四个季度（Q1-Q4），用于季度业绩对比和季节性分析。",
        "sql_mapping": "EXTRACT(QUARTER FROM \"日期\")",
        "other_words": ["Q1", "Q2", "Q3", "Q4", "季"]
    },
    {
        "word": "年度",
        "description": "以自然年为单位的时间维度，用于年度业绩汇总和同比分析。",
        "sql_mapping": "EXTRACT(YEAR FROM \"日期\")",
        "other_words": ["年", "年份", "财年"]
    },
    # ── 数据质量与分布 ──
    {
        "word": "中位数",
        "description": "将数据从小到大排列后位于中间位置的值，比平均值更能反映数据的典型水平，不受极端值影响。",
        "sql_mapping": "PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY \"{field}\")",
        "other_words": ["中值", "Median"]
    },
    {
        "word": "标准差",
        "description": "衡量数据离散程度的统计量，标准差越大说明数据波动越大。用于评估销售稳定性、价格波动等。",
        "sql_mapping": "ROUND(STDDEV(\"{field}\"), 2)",
        "other_words": ["波动", "离散度", "Standard Deviation", "STDDEV"]
    },
    {
        "word": "占比",
        "description": "某部分数值占总体的百分比，用于结构分析。计算公式：占比 = 部分值 ÷ 总值 × 100%。",
        "sql_mapping": 'ROUND("{field}" * 100.0 / NULLIF(SUM("{field}") OVER (), 0), 2)',
        "other_words": ["比例", "百分比", "份额", "比重", "Proportion"]
    },
    # ── 应收应付指标 ──
    {
        "word": "应收账款",
        "description": "企业因销售商品或提供服务而应向客户收取但尚未收到的款项。反映企业的信用销售规模。",
        "sql_mapping": 'SUM("应收账款")',
        "other_words": ["应收款", "赊销额", "Accounts Receivable"]
    },
    {
        "word": "回款率",
        "description": "实际收回的款项占应收账款的比例。计算公式：回款率 = 已收款金额 ÷ 应收账款总额 × 100%。",
        "sql_mapping": 'ROUND(SUM("已收款") * 100.0 / NULLIF(SUM("应收账款"), 0), 2)',
        "other_words": ["收款率", "Collection Rate"]
    },
]


BUSINESS_SQL_EXAMPLES = [
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
        "description": "SELECT TO_CHAR(\"日期\", 'YYYY-MM') AS \"月份\", SUM(\"销售额\") AS \"月销售额\" FROM \"{table}\" GROUP BY \"月份\" ORDER BY \"月份\" ASC"
    },
    {
        "question": "展示销售趋势",
        "description": 'SELECT "日期", "销售额", "订单数" FROM "{table}" ORDER BY "日期" ASC'
    },
    # ── 排名分析 ──
    {
        "question": "各产品销售额排名",
        "description": 'SELECT "产品名称", SUM("销售额") AS "总销售额" FROM "{table}" GROUP BY "产品名称" ORDER BY "总销售额" DESC'
    },
    {
        "question": "查询销售额前10的产品",
        "description": 'SELECT "产品名称", SUM("销售额") AS "总销售额" FROM "{table}" GROUP BY "产品名称" ORDER BY "总销售额" DESC LIMIT 10'
    },
    {
        "question": "查询销售额最高的日期",
        "description": 'SELECT "日期", "销售额" FROM "{table}" ORDER BY "销售额" DESC LIMIT 1'
    },
    {
        "question": "TOP10客户",
        "description": 'SELECT "客户名称", SUM("销售额") AS "总消费" FROM "{table}" GROUP BY "客户名称" ORDER BY "总消费" DESC LIMIT 10'
    },
    # ── 区域分析 ──
    {
        "question": "各区域销售对比",
        "description": 'SELECT "销售区域", SUM("销售额") AS "总销售额", SUM("订单数") AS "总订单数" FROM "{table}" GROUP BY "销售区域" ORDER BY "总销售额" DESC'
    },
    {
        "question": "各区域销售占比",
        "description": 'SELECT "销售区域", SUM("销售额") AS "总销售额", ROUND(SUM("销售额") * 100.0 / (SELECT SUM("销售额") FROM "{table}"), 2) AS "占比%" FROM "{table}" GROUP BY "销售区域" ORDER BY "总销售额" DESC'
    },
    # ── 增长分析 ──
    {
        "question": "本月环比增长率",
        "description": "SELECT TO_CHAR(\"日期\", 'YYYY-MM') AS \"月份\", SUM(\"销售额\") AS \"月销售额\", ROUND((SUM(\"销售额\") - LAG(SUM(\"销售额\")) OVER (ORDER BY TO_CHAR(\"日期\", 'YYYY-MM'))) * 100.0 / NULLIF(LAG(SUM(\"销售额\")) OVER (ORDER BY TO_CHAR(\"日期\", 'YYYY-MM')), 0), 2) AS \"环比增长率%\" FROM \"{table}\" GROUP BY \"月份\" ORDER BY \"月份\""
    },
    {
        "question": "月度销售趋势",
        "description": "SELECT TO_CHAR(\"日期\", 'YYYY-MM') AS \"月份\", SUM(\"销售额\") AS \"月销售额\", SUM(\"订单数\") AS \"月订单数\" FROM \"{table}\" GROUP BY \"月份\" ORDER BY \"月份\" ASC"
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
    # ── 综合查询 ──
    {
        "question": "查询所有销售数据",
        "description": 'SELECT "日期", "销售额", "订单数", "客单价" FROM "{table}" ORDER BY "日期" ASC'
    },
    {
        "question": "查询最近的销售数据",
        "description": 'SELECT "日期", "销售额", "订单数", "客单价" FROM "{table}" ORDER BY "日期" DESC LIMIT 10'
    },
    # ── 客户分析 ──
    {
        "question": "客户复购率统计",
        "description": 'SELECT COUNT(DISTINCT CASE WHEN "购买次数" > 1 THEN "客户名称" END) * 100.0 / NULLIF(COUNT(DISTINCT "客户名称"), 0) AS "复购率%" FROM "{table}"'
    },
    {
        "question": "销售人员业绩排名",
        "description": 'SELECT "销售人员", SUM("销售额") AS "总业绩", COUNT(*) AS "订单数" FROM "{table}" GROUP BY "销售人员" ORDER BY "总业绩" DESC'
    },
    # ── 条件聚合（CASE WHEN） ──
    {
        "question": "各产品类别的销售额占比",
        "description": 'SELECT "产品类别", SUM("销售额") AS "类别销售额", ROUND(SUM("销售额") * 100.0 / NULLIF((SELECT SUM("销售额") FROM "{table}"), 0), 2) AS "占比%" FROM "{table}" GROUP BY "产品类别" ORDER BY "类别销售额" DESC'
    },
    {
        "question": "统计高价值和低价值订单数量",
        "description": 'SELECT SUM(CASE WHEN "销售额" >= 10000 THEN 1 ELSE 0 END) AS "高价值订单", SUM(CASE WHEN "销售额" < 10000 THEN 1 ELSE 0 END) AS "低价值订单" FROM "{table}"'
    },
    {
        "question": "各区域达标情况统计",
        "description": 'SELECT "销售区域", SUM("销售额") AS "实际销售额", SUM("目标值") AS "目标销售额", CASE WHEN SUM("销售额") >= SUM("目标值") THEN \'达标\' ELSE \'未达标\' END AS "达标状态" FROM "{table}" GROUP BY "销售区域"'
    },
    # ── 窗口函数（RANK / ROW_NUMBER / NTILE） ──
    {
        "question": "产品销售额排名（含排名序号）",
        "description": 'SELECT "产品名称", SUM("销售额") AS "总销售额", RANK() OVER (ORDER BY SUM("销售额") DESC) AS "排名" FROM "{table}" GROUP BY "产品名称"'
    },
    {
        "question": "每个区域销售额最高的产品",
        "description": 'SELECT * FROM (SELECT "销售区域", "产品名称", SUM("销售额") AS "总销售额", ROW_NUMBER() OVER (PARTITION BY "销售区域" ORDER BY SUM("销售额") DESC) AS rn FROM "{table}" GROUP BY "销售区域", "产品名称") t WHERE rn = 1'
    },
    {
        "question": "将客户按消费金额分为4个等级",
        "description": 'SELECT "客户名称", SUM("销售额") AS "总消费", NTILE(4) OVER (ORDER BY SUM("销售额") DESC) AS "消费等级" FROM "{table}" GROUP BY "客户名称"'
    },
    # ── 日期函数（EXTRACT / DATE_TRUNC） ──
    {
        "question": "按季度统计销售额",
        "description": 'SELECT EXTRACT(YEAR FROM "日期") AS "年份", EXTRACT(QUARTER FROM "日期") AS "季度", SUM("销售额") AS "季度销售额" FROM "{table}" GROUP BY "年份", "季度" ORDER BY "年份", "季度"'
    },
    {
        "question": "按周统计订单数",
        "description": "SELECT DATE_TRUNC('week', \"日期\") AS \"周起始日\", SUM(\"订单数\") AS \"周订单数\" FROM \"{table}\" GROUP BY \"周起始日\" ORDER BY \"周起始日\" ASC"
    },
    {
        "question": "按年度汇总销售业绩",
        "description": 'SELECT EXTRACT(YEAR FROM "日期") AS "年份", SUM("销售额") AS "年销售额", SUM("订单数") AS "年订单数", ROUND(AVG("客单价"), 2) AS "年均客单价" FROM "{table}" GROUP BY "年份" ORDER BY "年份"'
    },
    # ── HAVING 过滤 ──
    {
        "question": "销售额超过10万的产品",
        "description": 'SELECT "产品名称", SUM("销售额") AS "总销售额" FROM "{table}" GROUP BY "产品名称" HAVING SUM("销售额") > 100000 ORDER BY "总销售额" DESC'
    },
    {
        "question": "订单数超过50的客户",
        "description": 'SELECT "客户名称", COUNT(*) AS "订单数", SUM("销售额") AS "总消费" FROM "{table}" GROUP BY "客户名称" HAVING COUNT(*) > 50 ORDER BY "订单数" DESC'
    },
    # ── 百分比与占比计算 ──
    {
        "question": "各产品销售额累计占比",
        "description": 'SELECT "产品名称", SUM("销售额") AS "总销售额", ROUND(SUM(SUM("销售额")) OVER (ORDER BY SUM("销售额") DESC) * 100.0 / NULLIF((SELECT SUM("销售额") FROM "{table}"), 0), 2) AS "累计占比%" FROM "{table}" GROUP BY "产品名称" ORDER BY "总销售额" DESC'
    },
    {
        "question": "各渠道订单占比",
        "description": 'SELECT "渠道类型", COUNT(*) AS "订单数", ROUND(COUNT(*) * 100.0 / NULLIF((SELECT COUNT(*) FROM "{table}"), 0), 2) AS "占比%" FROM "{table}" GROUP BY "渠道类型" ORDER BY "订单数" DESC'
    },
    # ── 累计求和 ──
    {
        "question": "按日期累计销售额",
        "description": 'SELECT "日期", "销售额", SUM("销售额") OVER (ORDER BY "日期" ASC) AS "累计销售额" FROM "{table}" ORDER BY "日期" ASC'
    },
    # ── 移动平均 ──
    {
        "question": "7日移动平均销售额",
        "description": 'SELECT "日期", "销售额", ROUND(AVG("销售额") OVER (ORDER BY "日期" ASC ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 2) AS "7日移动平均" FROM "{table}" ORDER BY "日期" ASC'
    },
    # ── 同比分析 ──
    {
        "question": "月度销售额同比增长率",
        "description": "SELECT cur.\"月份\", cur.\"月销售额\", prev.\"月销售额\" AS \"去年同期\", ROUND((cur.\"月销售额\" - prev.\"月销售额\") * 100.0 / NULLIF(prev.\"月销售额\", 0), 2) AS \"同比增长率%\" FROM (SELECT TO_CHAR(\"日期\", 'YYYY-MM') AS \"月份\", SUM(\"销售额\") AS \"月销售额\" FROM \"{table}\" GROUP BY \"月份\") cur LEFT JOIN (SELECT TO_CHAR(\"日期\", 'YYYY-MM') AS \"月份\", SUM(\"销售额\") AS \"月销售额\" FROM \"{table}\" GROUP BY \"月份\") prev ON cur.\"月份\" = TO_CHAR(TO_DATE(prev.\"月份\", 'YYYY-MM') + INTERVAL '1 year', 'YYYY-MM')"
    },
    # ── NULL 处理 ──
    {
        "question": "统计缺失数据的记录数",
        "description": 'SELECT COUNT(*) AS "总记录数", SUM(CASE WHEN "销售额" IS NULL THEN 1 ELSE 0 END) AS "销售额缺失", SUM(CASE WHEN "客户名称" IS NULL THEN 1 ELSE 0 END) AS "客户缺失" FROM "{table}"'
    },
    {
        "question": "查询有效销售数据（排除空值）",
        "description": 'SELECT "日期", "产品名称", "销售额" FROM "{table}" WHERE "销售额" IS NOT NULL AND "产品名称" IS NOT NULL ORDER BY "日期" DESC'
    },
    # ── DISTINCT 去重统计 ──
    {
        "question": "统计不同产品数量",
        "description": 'SELECT COUNT(DISTINCT "产品名称") AS "产品种类数" FROM "{table}"'
    },
    {
        "question": "统计各区域的客户数量",
        "description": 'SELECT "销售区域", COUNT(DISTINCT "客户名称") AS "客户数" FROM "{table}" GROUP BY "销售区域" ORDER BY "客户数" DESC'
    },
    # ── 日期范围过滤 ──
    {
        "question": "查询本月销售数据",
        "description": "SELECT \"日期\", \"产品名称\", \"销售额\", \"订单数\" FROM \"{table}\" WHERE DATE_TRUNC('month', \"日期\") = DATE_TRUNC('month', CURRENT_DATE) ORDER BY \"日期\" ASC"
    },
    {
        "question": "查询最近30天的销售汇总",
        "description": 'SELECT SUM("销售额") AS "近30天销售额", SUM("订单数") AS "近30天订单数", ROUND(AVG("客单价"), 2) AS "平均客单价" FROM "{table}" WHERE "日期" >= CURRENT_DATE - INTERVAL \'30 days\''
    },
    # ── 多维度分组 ──
    {
        "question": "按区域和产品类别统计销售额",
        "description": 'SELECT "销售区域", "产品类别", SUM("销售额") AS "总销售额", SUM("订单数") AS "总订单数" FROM "{table}" GROUP BY "销售区域", "产品类别" ORDER BY "销售区域", "总销售额" DESC'
    },
    {
        "question": "按月份和渠道统计订单数",
        "description": "SELECT TO_CHAR(\"日期\", 'YYYY-MM') AS \"月份\", \"渠道类型\", SUM(\"订单数\") AS \"订单数\" FROM \"{table}\" GROUP BY \"月份\", \"渠道类型\" ORDER BY \"月份\", \"订单数\" DESC"
    },
    # ── 毛利与利润分析 ──
    {
        "question": "各产品毛利率排名",
        "description": 'SELECT "产品名称", SUM("销售额") AS "总销售额", SUM("成本") AS "总成本", ROUND((SUM("销售额") - SUM("成本")) * 100.0 / NULLIF(SUM("销售额"), 0), 2) AS "毛利率%" FROM "{table}" GROUP BY "产品名称" ORDER BY "毛利率%" DESC'
    },
    {
        "question": "各区域利润贡献分析",
        "description": 'SELECT "销售区域", SUM("销售额") - SUM("成本") AS "毛利", ROUND((SUM("销售额") - SUM("成本")) * 100.0 / NULLIF((SELECT SUM("销售额") - SUM("成本") FROM "{table}"), 0), 2) AS "利润贡献占比%" FROM "{table}" GROUP BY "销售区域" ORDER BY "毛利" DESC'
    },
    # ── 子查询 ──
    {
        "question": "销售额高于平均值的产品",
        "description": 'SELECT "产品名称", SUM("销售额") AS "总销售额" FROM "{table}" GROUP BY "产品名称" HAVING SUM("销售额") > (SELECT AVG(sub."总销售额") FROM (SELECT SUM("销售额") AS "总销售额" FROM "{table}" GROUP BY "产品名称") sub) ORDER BY "总销售额" DESC'
    },
]


# ============================================================

def init_business_terminologies(session: Session, oid: int = 1):
    """初始化商业级术语库"""
    created_count = 0
    skipped_count = 0

    for term_data in BUSINESS_TERMINOLOGIES:
        # 检查是否已存在（按word + oid判断）
        existing = session.exec(
            select(Terminology).where(
                and_(
                    Terminology.word == term_data["word"],
                    Terminology.oid == oid,
                    Terminology.pid.is_(None)  # 只检查主术语
                )
            )
        ).first()

        if existing:
            skipped_count += 1
            print(f"  ⊙ 跳过已存在: {term_data['word']}")
            continue

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
        print(f"  ✓ {term_data['word']} (同义词: {synonym_count}个)")

    session.commit()
    return created_count, skipped_count


def init_business_sql_examples(session: Session, oid: int = 1):
    """初始化商业级SQL示例库"""
    created_count = 0
    skipped_count = 0

    for example in BUSINESS_SQL_EXAMPLES:
        # 检查是否已存在
        existing = session.exec(
            select(DataTraining).where(
                and_(
                    DataTraining.question == example["question"],
                    DataTraining.oid == oid,
                )
            )
        ).first()

        if existing:
            skipped_count += 1
            print(f"  ⊙ 跳过已存在: {example['question']}")
            continue

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
        print(f"  ✓ {example['question']}")

    session.commit()
    return created_count, skipped_count


def clear_and_rebuild(session: Session, oid: int = 1):
    """清除旧数据并重建商业知识库"""
    from sqlmodel import delete as sql_delete

    # 统计旧数据
    term_count = session.exec(
        select(func.count(Terminology.id)).where(Terminology.oid == oid)
    ).one() or 0
    train_count = session.exec(
        select(func.count(DataTraining.id)).where(DataTraining.oid == oid)
    ).one() or 0

    print(f"  现有数据: {term_count} 条术语, {train_count} 条SQL示例")

    # 清除
    session.exec(sql_delete(Terminology).where(Terminology.oid == oid))
    session.exec(sql_delete(DataTraining).where(DataTraining.oid == oid))
    session.commit()
    print(f"  已清除旧数据")


def main():
    print("=" * 70)
    print("  ChatBI — 商业级知识库初始化")
    print("  基于RAG与大语言模型的商业智能分析对话系统")
    print("=" * 70)

    # 询问是否清除旧数据
    mode = "rebuild"
    if len(sys.argv) > 1:
        mode = sys.argv[1]  # rebuild / append

    oid = 1

    with Session(engine) as session:
        if mode == "rebuild":
            print("\n🗑️  模式: 清除旧数据并重建")
            clear_and_rebuild(session, oid)
        else:
            print("\n➕ 模式: 追加（跳过已存在的条目）")

        # 初始化术语库
        print("\n📚 初始化商业级术语库...")
        term_created, term_skipped = init_business_terminologies(session, oid)

        # 初始化SQL示例库
        print("\n📖 初始化商业级SQL示例库...")
        sql_created, sql_skipped = init_business_sql_examples(session, oid)

        print("\n" + "=" * 70)
        print("商业级知识库初始化完成")
        print("=" * 70)
        print(f"\n📊 统计:")
        print(f"   术语库: 新增 {term_created} 条, 跳过 {term_skipped} 条")
        print(f"   SQL示例: 新增 {sql_created} 条, 跳过 {sql_skipped} 条")
        print(f"\n📋 术语库覆盖 (50条):")
        print(f"   • 销售指标: 销售额、订单数、客单价、GMV")
        print(f"   • 财务指标: 毛利率、净利润率、ROI、费用率、折扣率")
        print(f"   • 增长指标: 同比增长、环比增长")
        print(f"   • 客户指标: 复购率、CLV、留存率、流失率、转化率、ARPU")
        print(f"   • 运营指标: 库存周转率、坪效、人效、市场占有率")
        print(f"   • 电商指标: DAU、MAU、UV、SKU")
        print(f"   • 供应链: 缺货率、退货率")
        print(f"   • 营销: 获客成本、投入产出比")
        print(f"   • 统计分析: 中位数、标准差、占比")
        print(f"   • 应收应付: 应收账款、回款率")
        print(f"\n📋 SQL示例库覆盖 (50条):")
        print(f"   • 基础汇总: SUM/AVG/COUNT/MAX/MIN")
        print(f"   • 时间序列: 按日/周/月/季度/年度统计")
        print(f"   • 排名分析: TOP N、RANK、ROW_NUMBER、NTILE")
        print(f"   • 区域分析: 区域对比、区域占比、多维度分组")
        print(f"   • 增长分析: 环比增长、同比增长、移动平均、累计求和")
        print(f"   • 条件聚合: CASE WHEN、HAVING过滤")
        print(f"   • 利润分析: 毛利率排名、利润贡献占比")
        print(f"   • 客户分析: 复购率、客户分级、高低价值订单")
        print(f"   • 数据质量: NULL处理、DISTINCT去重、日期范围过滤")
        print(f"   • 高级查询: 窗口函数、子查询、累计占比")
        print(f"\n💡 提示: 如需生成向量嵌入，请运行:")
        print(f"   python scripts/generate_embeddings.py")
        print(f"\n💡 运行参数:")
        print(f"   python scripts/init_business_knowledge.py          # 清除旧数据并重建")
        print(f"   python scripts/init_business_knowledge.py append   # 追加模式（保留已有数据）")


if __name__ == "__main__":
    main()
