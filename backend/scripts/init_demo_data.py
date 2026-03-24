"""
ChatBI 演示数据初始化脚本
为新用户自动创建演示数据，帮助快速体验系统功能
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from common.core.config import settings
from sqlmodel import Session, select
from common.core.db import engine
from apps.datasource.models.datasource import CoreDatasource
from apps.terminology.models.terminology import Terminology
from apps.data_training.models.data_training import DataTraining
from common.chatbi.custom_prompt import PromptSQL, PromptAnalysis, PromptForecast
from common.utils.utils import ChatBILogUtil
import pandas as pd
from datetime import datetime


def create_demo_excel():
    """创建演示 Excel 文件（销售数据）"""
    demo_data = {
        '产品名称': ['笔记本电脑', '台式电脑', '显示器', '键盘', '鼠标', '耳机', '摄像头', '音箱', '路由器', '硬盘'],
        '销售额': [15000, 12000, 3000, 500, 300, 800, 600, 1200, 400, 1500],
        '销售数量': [10, 8, 20, 50, 60, 30, 25, 15, 40, 35],
        '销售日期': ['2024-01-15', '2024-01-20', '2024-02-10', '2024-02-15', '2024-03-05',
                   '2024-03-20', '2024-04-10', '2024-04-25', '2024-05-15', '2024-05-30'],
        '销售区域': ['华东', '华北', '华南', '华东', '华北', '华南', '华东', '华北', '华南', '华东'],
        '销售人员': ['张三', '李四', '王五', '赵六', '张三', '李四', '王五', '赵六', '张三', '李四']
    }
    
    df = pd.DataFrame(demo_data)
    excel_path = Path(settings.DATA_PATH) / 'excel' / '演示销售数据.xlsx'
    excel_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(excel_path, index=False, engine='openpyxl')
    
    ChatBILogUtil.info(f"演示 Excel 文件已创建: {excel_path}")
    return excel_path


def create_demo_datasource(session: Session, oid: int) -> int:
    """创建演示数据源"""
    # 检查是否已存在演示数据源
    stmt = select(CoreDatasource).where(
        CoreDatasource.oid == oid,
        CoreDatasource.name == '演示数据源（销售数据）'
    )
    existing = session.exec(stmt).first()
    
    if existing:
        ChatBILogUtil.info(f"⚠️  演示数据源已存在，跳过创建")
        return existing.id
    
    # 创建 Excel 文件
    excel_path = create_demo_excel()
    
    # 创建数据源记录
    datasource = CoreDatasource(
        oid=oid,
        name='演示数据源（销售数据）',
        description='这是一个演示数据源，包含销售数据示例。您可以用它来体验 ChatBI 的功能。',
        type='excel',
        type_name='Excel',
        configuration=str(excel_path),
        status=True
    )
    
    session.add(datasource)
    session.commit()
    session.refresh(datasource)
    
    ChatBILogUtil.info(f"演示数据源已创建: ID={datasource.id}")
    return datasource.id


def create_demo_terminologies(session: Session, oid: int, ds_id: int = None):
    """创建演示术语"""
    demo_terms = [
        {
            'word': 'GMV',
            'description': '商品交易总额（Gross Merchandise Volume），指一定时间内的成交总额',
            'synonyms': ['交易额', '销售总额', '成交额']
        },
        {
            'word': 'DAU',
            'description': '日活跃用户数（Daily Active Users），指每日活跃用户的数量',
            'synonyms': ['日活', '日活用户']
        },
        {
            'word': 'ROI',
            'description': '投资回报率（Return On Investment），衡量投资效益的指标',
            'synonyms': ['投资回报', '回报率']
        },
        {
            'word': '转化率',
            'description': '用户完成目标行为的比例，如购买转化率、注册转化率等',
            'synonyms': ['转换率', 'CVR']
        },
        {
            'word': '客单价',
            'description': '平均每个客户的消费金额，计算公式：总销售额 / 客户数',
            'synonyms': ['平均客单价', 'ARPU']
        },
        {
            'word': '复购率',
            'description': '重复购买的客户占总客户数的比例',
            'synonyms': ['回购率', '重复购买率']
        },
        {
            'word': '留存率',
            'description': '在一定时间后仍然活跃的用户比例',
            'synonyms': ['用户留存', '留存']
        },
        {
            'word': '流失率',
            'description': '用户停止使用产品或服务的比例',
            'synonyms': ['用户流失', 'Churn Rate']
        },
        {
            'word': 'SKU',
            'description': '库存量单位（Stock Keeping Unit），指商品的最小销售单位',
            'synonyms': ['商品编码', '单品']
        },
        {
            'word': 'UV',
            'description': '独立访客数（Unique Visitor），指访问网站的不重复用户数',
            'synonyms': ['独立访客', '访客数']
        }
    ]
    
    created_count = 0
    for term_data in demo_terms:
        # 检查是否已存在
        stmt = select(Terminology).where(
            Terminology.oid == oid,
            Terminology.word == term_data['word']
        )
        existing = session.exec(stmt).first()
        
        if existing:
            continue
        
        # 创建术语
        term = Terminology(
            oid=oid,
            datasource_id=ds_id,
            word=term_data['word'],
            description=term_data['description'],
            other_words=term_data['synonyms']
        )
        
        session.add(term)
        created_count += 1
    
    session.commit()
    ChatBILogUtil.info(f"已创建 {created_count} 个演示术语")


def create_demo_sql_examples(session: Session, oid: int, ds_id: int = None):
    """创建演示 SQL 示例"""
    demo_examples = [
        {
            'question': '今年销售额是多少',
            'sql': "SELECT SUM(销售额) as 总销售额 FROM sales WHERE strftime('%Y', 销售日期) = '2024'"
        },
        {
            'question': '显示销售额最高的10个产品',
            'sql': 'SELECT 产品名称, SUM(销售额) as 总销售额 FROM sales GROUP BY 产品名称 ORDER BY 总销售额 DESC LIMIT 10'
        },
        {
            'question': '按月统计销售额',
            'sql': "SELECT strftime('%Y-%m', 销售日期) as 月份, SUM(销售额) as 月销售额 FROM sales GROUP BY 月份 ORDER BY 月份"
        },
        {
            'question': '各区域的销售情况',
            'sql': 'SELECT 销售区域, SUM(销售额) as 总销售额, SUM(销售数量) as 总数量 FROM sales GROUP BY 销售区域'
        },
        {
            'question': '销售人员业绩排名',
            'sql': 'SELECT 销售人员, SUM(销售额) as 总业绩, COUNT(*) as 订单数 FROM sales GROUP BY 销售人员 ORDER BY 总业绩 DESC'
        },
        {
            'question': '最近30天的销售趋势',
            'sql': "SELECT 销售日期, SUM(销售额) as 日销售额 FROM sales WHERE 销售日期 >= date('now', '-30 days') GROUP BY 销售日期 ORDER BY 销售日期"
        },
        {
            'question': '平均客单价是多少',
            'sql': 'SELECT AVG(销售额) as 平均客单价 FROM sales'
        },
        {
            'question': '销售数量超过30的产品',
            'sql': 'SELECT 产品名称, SUM(销售数量) as 总数量 FROM sales GROUP BY 产品名称 HAVING 总数量 > 30'
        },
        {
            'question': '华东地区的销售明细',
            'sql': "SELECT * FROM sales WHERE 销售区域 = '华东' ORDER BY 销售日期 DESC"
        },
        {
            'question': '每个产品的平均销售额',
            'sql': 'SELECT 产品名称, AVG(销售额) as 平均销售额, COUNT(*) as 销售次数 FROM sales GROUP BY 产品名称'
        }
    ]
    
    created_count = 0
    for example_data in demo_examples:
        # 检查是否已存在
        stmt = select(DataTraining).where(
            DataTraining.oid == oid,
            DataTraining.question == example_data['question']
        )
        existing = session.exec(stmt).first()
        
        if existing:
            continue
        
        # 创建 SQL 示例
        example = DataTraining(
            oid=oid,
            datasource_id=ds_id,
            question=example_data['question'],
            description=example_data['sql']
        )
        
        session.add(example)
        created_count += 1
    
    session.commit()
    ChatBILogUtil.info(f"已创建 {created_count} 个演示 SQL 示例")


def create_demo_custom_prompts(session: Session, oid: int):
    """创建演示自定义提示词（SQL生成 + 数据分析 + 数据预测）
    
    提示词名称设计原则：
    名称中包含业务关键词，使关键词匹配算法能根据用户问题自动命中。
    例如用户问"分析各区域销售表现"，名称"销售分析报告格式"中的"销售"和"分析"
    会被bigram算法提取并与问题匹配。
    """
    # ===== SQL生成提示词 =====
    sql_prompts = [
        {
            'name': '销售数据查询规范',
            'prompt': '查询销售相关数据时，请注意：\n1. 金额字段使用SUM聚合，不要直接SELECT原始值\n2. 涉及时间范围时，优先使用日期字段过滤\n3. 分组统计时，GROUP BY字段必须出现在SELECT中\n4. 结果按关键指标降序排列，便于用户快速定位重点数据',
            'always_inject': False,
        },
        {
            'name': '产品统计SQL规则',
            'prompt': '统计产品相关数据时：\n1. 产品名称作为分组维度\n2. 同时输出销售额、销售数量等多维指标\n3. 使用HAVING过滤低值数据，提升结果质量\n4. 默认LIMIT 20，避免返回过多数据',
            'always_inject': False,
        },
        {
            'name': '区域对比查询模板',
            'prompt': '进行区域对比分析时：\n1. 按销售区域GROUP BY\n2. 计算各区域的销售额、数量、占比\n3. 使用子查询计算总量，再用除法得到占比\n4. 按销售额降序排列',
            'always_inject': False,
        },
    ]
    
    # ===== 数据分析提示词 =====
    analysis_prompts = [
        {
            'name': '销售分析报告格式',
            'prompt': '生成销售数据分析报告时，请按以下结构输出：\n1. 📊 数据概览：总销售额、总数量、平均客单价等核心指标\n2. 📈 趋势分析：识别增长/下降趋势，标注关键转折点\n3. 🏆 排名分析：Top产品/区域/人员，突出头部效应\n4. ⚠️ 异常发现：标注异常值（如某产品销售额远高于均值）\n5. 💡 建议：基于数据给出可操作的业务建议',
            'always_inject': False,
        },
        {
            'name': '产品对比分析规则',
            'prompt': '对比分析产品数据时：\n1. 从销售额、销售数量、增长率等多维度对比\n2. 识别高销售额低数量（高客单价）和低销售额高数量（走量型）产品\n3. 计算各产品的销售额占比，识别核心产品\n4. 给出产品组合优化建议',
            'always_inject': False,
        },
        {
            'name': '区域销售表现分析',
            'prompt': '分析区域销售表现时：\n1. 对比各区域的销售额和销售数量\n2. 计算区域贡献度（占总销售额的百分比）\n3. 识别优势区域和待提升区域\n4. 分析区域间的差异原因（如产品偏好、季节性等）\n5. 给出区域策略建议',
            'always_inject': False,
        },
        {
            'name': '数据趋势与异常检测',
            'prompt': '进行趋势和异常分析时：\n1. 识别时间维度上的增长/下降趋势\n2. 计算环比和同比变化率\n3. 标注偏离均值超过2个标准差的异常数据点\n4. 分析异常原因（季节性、促销活动、数据质量等）',
            'always_inject': False,
        },
        {
            'name': '通用分析输出规范',
            'prompt': '所有数据分析报告必须：\n1. 使用Markdown格式，层次清晰\n2. 关键数字加粗显示\n3. 百分比保留1位小数\n4. 金额超过万元时使用"万元"单位\n5. 结论部分用emoji标注重要程度',
            'always_inject': False,  # 已改为意图规则注入，不再使用全局注入
        },
    ]
    
    # ===== 数据预测提示词 =====
    forecast_prompts = [
        {
            'name': '销售趋势预测方法',
            'prompt': '预测销售趋势时：\n1. 基于历史数据识别周期性模式（月度/季度/年度）\n2. 考虑季节性因素对销售的影响\n3. 标注预测的置信区间（高/中/低）\n4. 给出乐观、基准、悲观三种预测场景\n5. 说明预测依据和假设条件',
            'always_inject': False,
        },
        {
            'name': '预测结果输出格式',
            'prompt': '预测报告格式要求：\n1. 明确标注预测时间范围\n2. 给出具体的预测数值和变化率\n3. 用📈📉标注增长/下降趋势\n4. 列出影响预测的关键因素\n5. 给出风险提示和应对建议',
            'always_inject': False,  # 已改为意图规则注入，不再使用全局注入
        },
    ]
    
    created = {'sql': 0, 'analysis': 0, 'forecast': 0}
    
    for data in sql_prompts:
        existing = session.exec(
            select(PromptSQL).where(PromptSQL.oid == oid, PromptSQL.name == data['name'])
        ).first()
        if not existing:
            session.add(PromptSQL(
                oid=oid, name=data['name'], prompt=data['prompt'],
                always_inject=data['always_inject'], create_time=datetime.now()
            ))
            created['sql'] += 1
    
    for data in analysis_prompts:
        existing = session.exec(
            select(PromptAnalysis).where(PromptAnalysis.oid == oid, PromptAnalysis.name == data['name'])
        ).first()
        if not existing:
            session.add(PromptAnalysis(
                oid=oid, name=data['name'], prompt=data['prompt'],
                always_inject=data['always_inject'], create_time=datetime.now()
            ))
            created['analysis'] += 1
    
    for data in forecast_prompts:
        existing = session.exec(
            select(PromptForecast).where(PromptForecast.oid == oid, PromptForecast.name == data['name'])
        ).first()
        if not existing:
            session.add(PromptForecast(
                oid=oid, name=data['name'], prompt=data['prompt'],
                always_inject=data['always_inject'], create_time=datetime.now()
            ))
            created['forecast'] += 1
    
    session.commit()
    ChatBILogUtil.info(f"已创建演示提示词: SQL生成 {created['sql']}条, 数据分析 {created['analysis']}条, 数据预测 {created['forecast']}条")


def init_demo_data(oid: int = 1):
    """初始化演示数据"""
    ChatBILogUtil.info("=" * 60)
    ChatBILogUtil.info("开始初始化演示数据...")
    ChatBILogUtil.info("=" * 60)
    
    with Session(engine) as session:
        try:
            # 1. 创建演示数据源
            ChatBILogUtil.info("\n📊 步骤 1/4: 创建演示数据源")
            ds_id = create_demo_datasource(session, oid)
            
            # 2. 创建演示术语
            ChatBILogUtil.info("\n📚 步骤 2/4: 创建演示术语")
            create_demo_terminologies(session, oid, None)  # 全局术语
            
            # 3. 创建演示 SQL 示例
            ChatBILogUtil.info("\n💡 步骤 3/4: 创建演示 SQL 示例")
            create_demo_sql_examples(session, oid, ds_id)
            
            # 4. 创建演示自定义提示词
            ChatBILogUtil.info("\n步骤 4/4: 创建演示自定义提示词")
            create_demo_custom_prompts(session, oid)
            
            ChatBILogUtil.info("\n" + "=" * 60)
            ChatBILogUtil.info("演示数据初始化完成！")
            ChatBILogUtil.info("=" * 60)
            ChatBILogUtil.info("\n您现在可以:")
            ChatBILogUtil.info("1. 前往「数据源」页面查看演示数据源")
            ChatBILogUtil.info("2. 前往「知识库」→「术语库」查看演示术语")
            ChatBILogUtil.info("3. 前往「知识库」→「SQL 示例库」查看演示 SQL")
            ChatBILogUtil.info("4. 前往「系统管理」→「提示词」查看演示提示词")
            ChatBILogUtil.info("5. 前往「智能对话」开始体验 RAG 功能")
            ChatBILogUtil.info("\n💡 提示: 演示数据可以随时删除\n")
            
        except Exception as e:
            ChatBILogUtil.error(f"初始化演示数据失败: {e}")
            ChatBILogUtil.exception()
            session.rollback()
            raise


if __name__ == '__main__':
    # 从命令行参数获取 oid，默认为 1
    oid = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    init_demo_data(oid)
