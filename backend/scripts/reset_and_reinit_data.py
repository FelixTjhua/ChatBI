#!/usr/bin/env python3
"""清空并重新初始化ChatBI数据"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select
from common.core.db import engine
from apps.terminology.models.terminology_model import Terminology
from apps.data_training.models.data_training_model import DataTraining
from common.chatbi.custom_prompt import CustomPrompt
from common.utils.utils import ChatBILogUtil


def clear_all_data(session: Session, oid: int = 1):
    """清空所有RAG数据"""
    ChatBILogUtil.info("=" * 70)
    ChatBILogUtil.info("开始清空数据...")
    ChatBILogUtil.info("=" * 70)
    
    # 清空术语库
    stmt = select(Terminology).where(Terminology.oid == oid)
    terms = session.exec(stmt).all()
    term_count = len(terms)
    for term in terms:
        session.delete(term)
    ChatBILogUtil.info(f"✓ 已清空术语库: {term_count} 条")
    
    # 清空SQL示例库
    stmt = select(DataTraining).where(DataTraining.oid == oid)
    trainings = session.exec(stmt).all()
    training_count = len(trainings)
    for training in trainings:
        session.delete(training)
    ChatBILogUtil.info(f"✓ 已清空SQL示例库: {training_count} 条")
    
    # 清空提示词
    stmt = select(CustomPrompt).where(CustomPrompt.oid == oid)
    prompts = session.exec(stmt).all()
    prompt_count = len(prompts)
    for prompt in prompts:
        session.delete(prompt)
    ChatBILogUtil.info(f"✓ 已清空提示词: {prompt_count} 条")
    
    session.commit()
    
    ChatBILogUtil.info("\n" + "=" * 70)
    ChatBILogUtil.info(f"数据清空完成！共清空 {term_count + training_count + prompt_count} 条数据")
    ChatBILogUtil.info("=" * 70)


def init_terminology_data(session: Session, oid: int = 1):
    """初始化术语库数据"""
    ChatBILogUtil.info("\n📚 初始化术语库...")
    
    from datetime import datetime
    create_time = datetime.now()
    
    # ========== 基础统计术语 ==========
    terms = [
        {
            'word': '销售额',
            'description': '商品或服务的销售金额总和，不包含退货金额。计算公式：SUM(订单金额) WHERE 订单状态 != "已退货"',
            'synonyms': ['营业额', '收入', '销售收入', '销售金额', '营收']
        },
        {
            'word': '订单数',
            'description': '客户下单的总数量，包含所有状态的订单',
            'synonyms': ['订单量', '成交单数', '订单总数', '成交量']
        },
        {
            'word': '客单价',
            'description': '平均每个订单的金额，计算公式：销售额 / 订单数',
            'synonyms': ['平均订单金额', 'AOV', 'Average Order Value', '单均价']
        },
        {
            'word': '日期',
            'description': '时间维度，用于统计和分析数据的时间范围',
            'synonyms': ['时间', '日期时间', 'date', '时间点', '日期字段']
        },
        {
            'word': '趋势',
            'description': '数据随时间变化的方向和模式，通常需要按时间排序展示',
            'synonyms': ['走势', '变化趋势', 'trend', '发展趋势', '变化规律']
        },
        {
            'word': '同比',
            'description': '与去年同期相比的增长率，计算公式：(本期值 - 去年同期值) / 去年同期值 * 100%',
            'synonyms': ['同比增长', 'YoY', 'Year over Year', '同期对比', '年同比']
        },
        {
            'word': '环比',
            'description': '与上一个统计周期相比的增长率，计算公式：(本期值 - 上期值) / 上期值 * 100%',
            'synonyms': ['环比增长', 'MoM', 'Month over Month', '月环比', '周期对比']
        },
        {
            'word': '汇总',
            'description': '对数据进行聚合统计，常用函数：SUM、COUNT、AVG、MAX、MIN',
            'synonyms': ['合计', '总计', '求和', 'sum', '聚合', '累计']
        },
        {
            'word': '平均值',
            'description': '所有数值的算术平均数',
            'synonyms': ['均值', '平均', 'average', 'avg', '平均数']
        },
        {
            'word': '最大值',
            'description': '数据集中的最大数值',
            'synonyms': ['最高', '峰值', 'max', 'maximum', '最高值']
        },
        {
            'word': '最小值',
            'description': '数据集中的最小数值',
            'synonyms': ['最低', '谷值', 'min', 'minimum', '最低值']
        },
        # ========== 业务实体术语 ==========
        {
            'word': 'GMV',
            'description': '总成交额（Gross Merchandise Volume），包含退货在内的所有订单金额总和。与销售额的区别：GMV包含退货，销售额不包含退货',
            'synonyms': ['总成交额', '成交总额', 'Gross Merchandise Volume']
        },
        {
            'word': '转化率',
            'description': '成交订单数占访问用户数的比例，计算公式：成交订单数 / 访问用户数 * 100%',
            'synonyms': ['成交率', '转换率', 'conversion rate', 'CVR']
        },
        {
            'word': '复购率',
            'description': '重复购买客户占总客户数的比例，计算公式：购买次数>1的客户数 / 总客户数 * 100%',
            'synonyms': ['回购率', '重复购买率', 'repurchase rate']
        },
        {
            'word': '退货率',
            'description': '退货订单数占总订单数的比例，计算公式：退货订单数 / 总订单数 * 100%',
            'synonyms': ['退单率', '退款率', 'return rate']
        },
        {
            'word': '毛利率',
            'description': '毛利润占销售额的比例，计算公式：(销售额 - 成本) / 销售额 * 100%',
            'synonyms': ['毛利', '利润率', 'gross margin', '毛利润率']
        },
        {
            'word': '库存',
            'description': '当前仓库中商品的存量数据',
            'synonyms': ['库存量', '存货', '库存数量', 'inventory', '在库量']
        },
        {
            'word': '产品类别',
            'description': '商品的分类维度，用于按类别进行分组统计和对比分析',
            'synonyms': ['商品分类', '品类', '类目', 'category', '产品分类']
        },
        {
            'word': '地区',
            'description': '地理维度，用于按区域进行分组统计和对比分析',
            'synonyms': ['区域', '省份', '城市', 'region', '地域']
        },
        # ========== 高级分析术语 ==========
        {
            'word': '排名',
            'description': '按某个指标对数据进行排序后的位次，SQL中常用ROW_NUMBER()或RANK()窗口函数实现',
            'synonyms': ['排行', '名次', 'ranking', 'TOP', '前几名']
        },
        {
            'word': '占比',
            'description': '某部分数值占总体的百分比，计算公式：部分值 / 总值 * 100%',
            'synonyms': ['比例', '百分比', '份额', 'proportion', '比重']
        },
        {
            'word': '分布',
            'description': '数据在不同区间或类别中的分散情况',
            'synonyms': ['分散', '分配', 'distribution', '数据分布']
        },
    ]
    
    main_term_count = 0
    synonym_count = 0
    
    for term_data in terms:
        # 创建主术语
        main_term = Terminology(
            oid=oid,
            pid=None,  # 主术语的pid为None
            word=term_data['word'],
            description=term_data['description'],
            create_time=create_time,
            enabled=True,
        )
        session.add(main_term)
        session.flush()  # 获取主术语的ID
        main_term_count += 1
        
        # 创建同义词
        for synonym in term_data['synonyms']:
            synonym_term = Terminology(
                oid=oid,
                pid=main_term.id,  # 同义词的pid指向主术语
                word=synonym,
                description=None,  # 同义词不需要描述
                create_time=create_time,
                enabled=True,
            )
            session.add(synonym_term)
            synonym_count += 1
    
    session.commit()
    ChatBILogUtil.info(f"✓ 已创建 {main_term_count} 个主术语，{synonym_count} 个同义词")


def init_training_data(session: Session, oid: int = 1):
    """初始化SQL示例库数据"""
    ChatBILogUtil.info("\n💾 初始化SQL示例库...")
    
    # ========== 基础单表查询 ==========
    examples = [
        {
            'question': '查询总销售额',
            'sql': 'SELECT SUM(销售额) as 总销售额 FROM sales'
        },
        {
            'question': '按日期统计销售额',
            'sql': 'SELECT 日期, SUM(销售额) as 销售额 FROM sales GROUP BY 日期 ORDER BY 日期'
        },
        {
            'question': '查询销售额最高的10个产品',
            'sql': 'SELECT 产品名称, SUM(销售额) as 总销售额 FROM sales GROUP BY 产品名称 ORDER BY 总销售额 DESC LIMIT 10'
        },
        {
            'question': '按月统计销售趋势',
            'sql': "SELECT DATE_FORMAT(日期, '%Y-%m') as 月份, SUM(销售额) as 月销售额 FROM sales GROUP BY 月份 ORDER BY 月份"
        },
        {
            'question': '计算平均客单价',
            'sql': 'SELECT AVG(订单金额) as 平均客单价 FROM orders'
        },
        {
            'question': '查询今年的销售数据',
            'sql': "SELECT * FROM sales WHERE YEAR(日期) = YEAR(CURDATE())"
        },
        {
            'question': '统计各地区销售额',
            'sql': 'SELECT 地区, SUM(销售额) as 地区销售额 FROM sales GROUP BY 地区 ORDER BY 地区销售额 DESC'
        },
        {
            'question': '查询销售额大于1000的订单',
            'sql': 'SELECT * FROM orders WHERE 订单金额 > 1000 ORDER BY 订单金额 DESC'
        },
        {
            'question': '统计每个客户的订单数',
            'sql': 'SELECT 客户名称, COUNT(*) as 订单数 FROM orders GROUP BY 客户名称 ORDER BY 订单数 DESC'
        },
        {
            'question': '查询最近7天的销售数据',
            'sql': 'SELECT 日期, SUM(销售额) as 销售额 FROM sales WHERE 日期 >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) GROUP BY 日期'
        },
        # ========== 多表JOIN查询 ==========
        {
            'question': '查询每个产品的销售额和库存',
            'sql': '''SELECT p.产品名称, SUM(s.销售额) as 总销售额, p.库存数量
FROM sales s
JOIN products p ON s.产品ID = p.id
GROUP BY p.产品名称, p.库存数量
ORDER BY 总销售额 DESC'''
        },
        {
            'question': '查询每个客户的订单总额和订单数',
            'sql': '''SELECT c.客户名称, c.地区, COUNT(o.id) as 订单数, SUM(o.订单金额) as 订单总额
FROM orders o
JOIN customers c ON o.客户ID = c.id
GROUP BY c.客户名称, c.地区
ORDER BY 订单总额 DESC'''
        },
        {
            'question': '查询每个销售员的业绩',
            'sql': '''SELECT e.姓名 as 销售员, COUNT(o.id) as 成交单数, SUM(o.订单金额) as 业绩总额
FROM orders o
JOIN employees e ON o.销售员ID = e.id
GROUP BY e.姓名
ORDER BY 业绩总额 DESC'''
        },
        {
            'question': '查询各产品类别在各地区的销售额',
            'sql': '''SELECT p.产品类别, c.地区, SUM(s.销售额) as 销售额
FROM sales s
JOIN products p ON s.产品ID = p.id
JOIN customers c ON s.客户ID = c.id
GROUP BY p.产品类别, c.地区
ORDER BY p.产品类别, 销售额 DESC'''
        },
        # ========== 窗口函数高级查询 ==========
        {
            'question': '计算销售额同比增长',
            'sql': '''SELECT 
    YEAR(日期) as 年份,
    SUM(销售额) as 年销售额,
    LAG(SUM(销售额)) OVER (ORDER BY YEAR(日期)) as 去年销售额,
    ROUND((SUM(销售额) - LAG(SUM(销售额)) OVER (ORDER BY YEAR(日期))) / LAG(SUM(销售额)) OVER (ORDER BY YEAR(日期)) * 100, 2) as 同比增长率
FROM sales
GROUP BY YEAR(日期)'''
        },
        {
            'question': '查询销售额环比增长',
            'sql': '''SELECT 
    DATE_FORMAT(日期, '%Y-%m') as 月份,
    SUM(销售额) as 月销售额,
    LAG(SUM(销售额)) OVER (ORDER BY DATE_FORMAT(日期, '%Y-%m')) as 上月销售额,
    ROUND((SUM(销售额) - LAG(SUM(销售额)) OVER (ORDER BY DATE_FORMAT(日期, '%Y-%m'))) / LAG(SUM(销售额)) OVER (ORDER BY DATE_FORMAT(日期, '%Y-%m')) * 100, 2) as 环比增长率
FROM sales
GROUP BY 月份'''
        },
        {
            'question': '查询销售额累计值',
            'sql': '''SELECT 
    日期,
    SUM(销售额) as 当日销售额,
    SUM(SUM(销售额)) OVER (ORDER BY 日期) as 累计销售额
FROM sales
GROUP BY 日期
ORDER BY 日期'''
        },
        {
            'question': '查询各产品销售额排名',
            'sql': '''SELECT 
    产品名称,
    SUM(销售额) as 总销售额,
    RANK() OVER (ORDER BY SUM(销售额) DESC) as 排名
FROM sales
GROUP BY 产品名称
ORDER BY 排名'''
        },
        # ========== 子查询和HAVING ==========
        {
            'question': '查询销售额大于平均值的产品',
            'sql': '''SELECT 产品名称, SUM(销售额) as 总销售额
FROM sales
GROUP BY 产品名称
HAVING 总销售额 > (SELECT AVG(总销售额) FROM (SELECT SUM(销售额) as 总销售额 FROM sales GROUP BY 产品名称) t)'''
        },
        {
            'question': '统计各产品类别的销售占比',
            'sql': '''SELECT 
    产品类别,
    SUM(销售额) as 类别销售额,
    ROUND(SUM(销售额) / (SELECT SUM(销售额) FROM sales) * 100, 2) as 销售占比
FROM sales
GROUP BY 产品类别
ORDER BY 销售占比 DESC'''
        },
        {
            'question': '查询重复购买的客户',
            'sql': 'SELECT 客户名称, COUNT(*) as 购买次数 FROM orders GROUP BY 客户名称 HAVING 购买次数 > 1'
        },
        {
            'question': '查询没有订单的客户',
            'sql': '''SELECT c.客户名称, c.地区
FROM customers c
LEFT JOIN orders o ON c.id = o.客户ID
WHERE o.id IS NULL'''
        },
        # ========== 时间维度查询 ==========
        {
            'question': '查询销售额前3名的产品',
            'sql': 'SELECT 产品名称, SUM(销售额) as 总销售额 FROM sales GROUP BY 产品名称 ORDER BY 总销售额 DESC LIMIT 3'
        },
        {
            'question': '统计每月订单数',
            'sql': "SELECT DATE_FORMAT(日期, '%Y-%m') as 月份, COUNT(*) as 订单数 FROM orders GROUP BY 月份 ORDER BY 月份"
        },
        {
            'question': '查询销售额最低的产品',
            'sql': 'SELECT 产品名称, SUM(销售额) as 总销售额 FROM sales GROUP BY 产品名称 ORDER BY 总销售额 ASC LIMIT 1'
        },
        {
            'question': '按季度统计销售额',
            'sql': "SELECT CONCAT(YEAR(日期), '-Q', QUARTER(日期)) as 季度, SUM(销售额) as 季度销售额 FROM sales GROUP BY 季度 ORDER BY 季度"
        },
        {
            'question': '统计每天的平均订单金额',
            'sql': 'SELECT 日期, AVG(订单金额) as 平均订单金额 FROM orders GROUP BY 日期 ORDER BY 日期'
        },
        # ========== 业务场景查询 ==========
        {
            'question': '查询退货率最高的产品',
            'sql': '''SELECT 
    p.产品名称,
    COUNT(CASE WHEN o.订单状态 = '已退货' THEN 1 END) as 退货数,
    COUNT(*) as 总订单数,
    ROUND(COUNT(CASE WHEN o.订单状态 = '已退货' THEN 1 END) / COUNT(*) * 100, 2) as 退货率
FROM orders o
JOIN products p ON o.产品ID = p.id
GROUP BY p.产品名称
HAVING 退货率 > 0
ORDER BY 退货率 DESC'''
        },
        {
            'question': '查询各地区的客户数量和平均消费',
            'sql': '''SELECT 
    c.地区,
    COUNT(DISTINCT c.id) as 客户数,
    ROUND(SUM(o.订单金额) / COUNT(DISTINCT c.id), 2) as 人均消费
FROM customers c
JOIN orders o ON c.id = o.客户ID
GROUP BY c.地区
ORDER BY 人均消费 DESC'''
        },
        {
            'question': '查询库存不足的产品',
            'sql': '''SELECT p.产品名称, p.库存数量, COALESCE(SUM(s.数量), 0) as 近30天销量
FROM products p
LEFT JOIN sales s ON p.id = s.产品ID AND s.日期 >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
GROUP BY p.产品名称, p.库存数量
HAVING p.库存数量 < 近30天销量
ORDER BY p.库存数量 ASC'''
        },
        {
            'question': '对比今年和去年各月的销售额',
            'sql': '''SELECT 
    MONTH(日期) as 月份,
    SUM(CASE WHEN YEAR(日期) = YEAR(CURDATE()) THEN 销售额 ELSE 0 END) as 今年销售额,
    SUM(CASE WHEN YEAR(日期) = YEAR(CURDATE()) - 1 THEN 销售额 ELSE 0 END) as 去年销售额
FROM sales
WHERE YEAR(日期) >= YEAR(CURDATE()) - 1
GROUP BY MONTH(日期)
ORDER BY 月份'''
        },
    ]
    
    count = 0
    for example_data in examples:
        example = DataTraining(
            oid=oid,
            question=example_data['question'],
            description=example_data['sql'],
            enabled=True,
        )
        session.add(example)
        count += 1
    
    session.commit()
    ChatBILogUtil.info(f"✓ 已创建 {count} 个SQL示例")


def init_prompt_data(session: Session, oid: int = 1):
    """初始化提示词数据"""
    ChatBILogUtil.info("\n💡 初始化提示词...")
    
    from datetime import datetime
    create_time = datetime.now()
    
    # SQL生成提示词示例
    GENERATE_SQL_PROMPTS = [
        {
            "name": "返回结果格式化",
            "prompt": "查询结果请按照以下格式返回：数值类型保留2位小数，日期格式为YYYY-MM-DD，金额添加千分位分隔符。"
        },
        {
            "name": "SQL优化建议",
            "prompt": "生成SQL时请注意：1. 优先使用索引字段进行查询；2. 避免使用SELECT *；3. 大表查询时添加LIMIT限制。"
        },
        {
            "name": "数据安全规范",
            "prompt": "查询时请遵守数据安全规范：不返回用户敏感信息如身份证号、手机号等，如需显示请进行脱敏处理。"
        },
        {
            "name": "业务术语映射",
            "prompt": "业务术语对照：GMV=销售总额，DAU=日活跃用户数，MAU=月活跃用户数，ARPU=每用户平均收入，转化率=成交订单数/访问用户数。"
        },
        {
            "name": "时间范围默认值",
            "prompt": "当用户未指定时间范围时，查询全部数据，不添加时间限制条件。如果查询涉及同比，则自动对比去年同期数据。"
        },
        {
            "name": "业务规则约束",
            "prompt": "业务规则：1. 统计销售额时不包含已退货订单（订单状态!='已退货'）；2. 客户分类按VIP/普通/新客划分；3. 计算毛利率时成本取products表的成本价字段。"
        },
        {
            "name": "多表关联规范",
            "prompt": "多表关联时请注意：1. 优先使用INNER JOIN确保数据完整性；2. 使用LEFT JOIN时注意NULL值处理；3. 关联条件使用主键或外键字段；4. 避免笛卡尔积。"
        },
    ]
    
    # 数据分析提示词示例
    ANALYSIS_PROMPTS = [
        {
            "name": "分析报告格式",
            "prompt": "数据分析报告请包含以下部分：1. 数据概览；2. 关键指标分析；3. 趋势变化；4. 异常点说明；5. 建议措施。"
        },
        {
            "name": "对比分析规范",
            "prompt": "进行数据对比分析时，请计算环比增长率和同比增长率，并用百分比形式展示，增长用绿色标注，下降用红色标注。"
        },
        {
            "name": "图表推荐规则",
            "prompt": "根据数据特点推荐合适的图表：时间序列用折线图，占比分析用饼图，对比分析用柱状图，分布分析用直方图。"
        },
        {
            "name": "异常检测标准",
            "prompt": "数据异常判断标准：偏离均值超过2个标准差视为异常，环比变化超过30%需要重点关注并给出可能原因。"
        },
        {
            "name": "多维度分析要求",
            "prompt": "分析数据时请从多个维度展开：时间维度（日/周/月/季/年趋势）、空间维度（地区对比）、产品维度（类别对比）、客户维度（客群分析）。"
        },
    ]
    
    # 数据预测提示词示例
    PREDICT_PROMPTS = [
        {
            "name": "预测模型说明",
            "prompt": "数据预测请说明使用的预测方法（如移动平均、指数平滑、线性回归等），并给出预测的置信区间。"
        },
        {
            "name": "预测结果展示",
            "prompt": "预测结果请包含：预测值、预测区间（上限和下限）、预测准确度评估、影响预测的关键因素。"
        },
        {
            "name": "季节性调整",
            "prompt": "进行预测时请考虑季节性因素，如节假日、促销活动、行业淡旺季等对数据的影响。"
        },
        {
            "name": "预测周期规范",
            "prompt": "预测周期要求：短期预测（1-4周）使用移动平均法，中期预测（1-3月）使用指数平滑法，长期预测（3月以上）使用趋势外推法。预测数据至少覆盖2个完整周期。"
        },
    ]
    
    prompts_to_add = []
    
    # 添加SQL生成提示词
    for item in GENERATE_SQL_PROMPTS:
        prompts_to_add.append(CustomPrompt(
            name=item["name"],
            type="GENERATE_SQL",
            prompt=item["prompt"],
            oid=oid,
            create_time=create_time
        ))
    
    # 添加数据分析提示词
    for item in ANALYSIS_PROMPTS:
        prompts_to_add.append(CustomPrompt(
            name=item["name"],
            type="ANALYSIS",
            prompt=item["prompt"],
            oid=oid,
            create_time=create_time
        ))
    
    # 添加数据预测提示词
    for item in PREDICT_PROMPTS:
        prompts_to_add.append(CustomPrompt(
            name=item["name"],
            type="PREDICT_DATA",
            prompt=item["prompt"],
            oid=oid,
            create_time=create_time
        ))
    
    # 批量添加
    for prompt in prompts_to_add:
        session.add(prompt)
    
    session.commit()
    ChatBILogUtil.info(f"✓ 已创建 {len(prompts_to_add)} 个提示词")
    ChatBILogUtil.info(f"  - SQL生成: {len(GENERATE_SQL_PROMPTS)} 条")
    ChatBILogUtil.info(f"  - 数据分析: {len(ANALYSIS_PROMPTS)} 条")
    ChatBILogUtil.info(f"  - 数据预测: {len(PREDICT_PROMPTS)} 条")


def main():
    print("=" * 70)
    print("ChatBI 数据重置和重新初始化")
    print("=" * 70)
    print("\n⚠️  警告: 此操作将清空以下数据:")
    print("   1. 术语库")
    print("   2. SQL示例库")
    print("   3. 提示词")
    print("\n然后重新初始化演示数据。")
    
    confirm = input("\n确认继续？(输入 yes 确认): ")
    if confirm.lower() != 'yes':
        print("\n操作已取消")
        return
    
    with Session(engine) as session:
        try:
            # 1. 清空数据
            clear_all_data(session, oid=1)
            
            # 2. 重新初始化
            ChatBILogUtil.info("\n" + "=" * 70)
            ChatBILogUtil.info("开始重新初始化数据...")
            ChatBILogUtil.info("=" * 70)
            
            init_terminology_data(session, oid=1)
            init_training_data(session, oid=1)
            init_prompt_data(session, oid=1)
            
            # 统计实际数据
            stmt = select(Terminology).where(Terminology.oid == 1, Terminology.pid.is_(None))
            main_terms = session.exec(stmt).all()
            main_term_count = len(main_terms)
            
            stmt = select(Terminology).where(Terminology.oid == 1, Terminology.pid.isnot(None))
            synonyms = session.exec(stmt).all()
            synonym_count = len(synonyms)
            
            stmt = select(DataTraining).where(DataTraining.oid == 1)
            trainings = session.exec(stmt).all()
            training_count = len(trainings)
            
            stmt = select(CustomPrompt).where(CustomPrompt.oid == 1)
            prompts = session.exec(stmt).all()
            prompt_count = len(prompts)
            
            ChatBILogUtil.info("\n" + "=" * 70)
            ChatBILogUtil.info("数据重置和初始化完成！")
            ChatBILogUtil.info("=" * 70)
            ChatBILogUtil.info("\n📊 数据统计:")
            ChatBILogUtil.info(f"   - 术语库: {main_term_count}个主术语，{synonym_count}个同义词")
            ChatBILogUtil.info(f"   - SQL示例库: {training_count}个示例")
            ChatBILogUtil.info(f"   - 提示词: {prompt_count}个提示词")
            ChatBILogUtil.info("\n💡 下一步:")
            ChatBILogUtil.info("   1. 运行 python backend/scripts/generate_embeddings.py 生成向量嵌入")
            ChatBILogUtil.info("   2. 访问Web界面验证数据")
            ChatBILogUtil.info("   3. 测试RAG功能\n")
            
        except Exception as e:
            ChatBILogUtil.error(f"操作失败: {e}")
            session.rollback()
            raise


if __name__ == "__main__":
    main()
