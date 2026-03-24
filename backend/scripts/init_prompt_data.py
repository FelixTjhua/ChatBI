"""初始化 Prompt 模板示例数据"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from sqlmodel import Session, select
from common.core.db import engine
from common.chatbi.custom_prompt import CustomPrompt

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
]


def init_prompt_data():
    """初始化提示词数据"""
    with Session(engine) as session:
        # 检查是否已有数据
        existing = session.exec(select(CustomPrompt).limit(1)).first()
        if existing:
            print("提示词数据已存在，跳过初始化")
            return
        
        prompts_to_add = []
        
        # 添加SQL生成提示词
        for item in GENERATE_SQL_PROMPTS:
            prompts_to_add.append(CustomPrompt(
                name=item["name"],
                type="GENERATE_SQL",
                prompt=item["prompt"],
                specific_ds=False,
                datasource_ids=None,
                oid=1,
                create_time=datetime.now()
            ))
        
        # 添加数据分析提示词
        for item in ANALYSIS_PROMPTS:
            prompts_to_add.append(CustomPrompt(
                name=item["name"],
                type="ANALYSIS",
                prompt=item["prompt"],
                specific_ds=False,
                datasource_ids=None,
                oid=1,
                create_time=datetime.now()
            ))
        
        # 添加数据预测提示词
        for item in PREDICT_PROMPTS:
            prompts_to_add.append(CustomPrompt(
                name=item["name"],
                type="PREDICT_DATA",
                prompt=item["prompt"],
                specific_ds=False,
                datasource_ids=None,
                oid=1,
                create_time=datetime.now()
            ))
        
        # 批量添加
        for prompt in prompts_to_add:
            session.add(prompt)
        
        session.commit()
        print(f"成功添加 {len(prompts_to_add)} 条提示词数据")
        print(f"  - SQL生成: {len(GENERATE_SQL_PROMPTS)} 条")
        print(f"  - 数据分析: {len(ANALYSIS_PROMPTS)} 条")
        print(f"  - 数据预测: {len(PREDICT_PROMPTS)} 条")


if __name__ == "__main__":
    init_prompt_data()
