"""初始化仪表板示例数据"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uuid
import time
import json
from sqlmodel import Session, select, delete
from common.core.db import engine
from apps.dashboard.models.dashboard_model import CoreDashboard

# 画布默认样式
DEFAULT_CANVAS_STYLE = json.dumps({
    "width": 1920,
    "height": 1080,
    "scale": 100,
    "scaleWidth": 100,
    "scaleHeight": 100,
    "selfAdaption": True,
    "auxiliaryMatrix": True,
    "openCommonStyle": True,
    "background": {
        "backgroundColor": "#f0f2f5",
        "backgroundColorSelect": True,
        "backgroundImageEnable": False,
        "backgroundType": "backgroundColor",
        "outerBackgroundColor": "#f0f2f5"
    },
    "refreshViewEnable": False,
    "refreshUnit": "minute",
    "refreshTime": 5,
    "themeId": 10,
    "customTheme": {},
    "gap": 5,
    "resultMode": "all",
    "resultCount": 1000
})

def create_view_component(component_id, name, x, y, size_x=18, size_y=12):
    """创建视图组件"""
    return {
        "id": component_id,
        "component": "SQView",
        "name": name,
        "propValue": "&nbsp;",
        "icon": "icon_graphical",
        "innerType": "bar",
        "locked": False,
        "editing": False,
        "x": x,
        "y": y,
        "sizeX": size_x,
        "sizeY": size_y,
        "style": {}
    }

# 销售概览 - 带完整图表数据
def create_sales_dashboard():
    view1_id = f"view-{uuid.uuid4().hex[:8]}"
    view2_id = f"view-{uuid.uuid4().hex[:8]}"
    view3_id = f"view-{uuid.uuid4().hex[:8]}"
    view4_id = f"view-{uuid.uuid4().hex[:8]}"
    
    components = [
        create_view_component(view1_id, "总销售额", 1, 1, 18, 16),
        create_view_component(view2_id, "订单数量", 19, 1, 18, 16),
        create_view_component(view3_id, "客单价", 37, 1, 18, 16),
        create_view_component(view4_id, "销售趋势", 55, 1, 18, 16),
    ]
    
    # 视图信息 - 包含图表配置和数据
    view_info = {
        view1_id: {
            "id": view1_id,
            "chart": {
                "id": view1_id,
                "type": "column",
                "sourceType": "column",
                "title": "总销售额",
                "columns": ["月份", "销售额"],
                "xAxis": "月份",
                "yAxis": ["销售额"],
                "series": []
            },
            "data": {
                "data": [
                    {"月份": "1月", "销售额": 125000},
                    {"月份": "2月", "销售额": 138000},
                    {"月份": "3月", "销售额": 156000},
                    {"月份": "4月", "销售额": 142000},
                    {"月份": "5月", "销售额": 168000},
                    {"月份": "6月", "销售额": 185000}
                ]
            }
        },
        view2_id: {
            "id": view2_id,
            "chart": {
                "id": view2_id,
                "type": "column",
                "sourceType": "column",
                "title": "订单数量",
                "columns": ["月份", "订单数"],
                "xAxis": "月份",
                "yAxis": ["订单数"],
                "series": []
            },
            "data": {
                "data": [
                    {"月份": "1月", "订单数": 1250},
                    {"月份": "2月", "订单数": 1380},
                    {"月份": "3月", "订单数": 1560},
                    {"月份": "4月", "订单数": 1420},
                    {"月份": "5月", "订单数": 1680},
                    {"月份": "6月", "订单数": 1850}
                ]
            }
        },
        view3_id: {
            "id": view3_id,
            "chart": {
                "id": view3_id,
                "type": "line",
                "sourceType": "line",
                "title": "客单价趋势",
                "columns": ["月份", "客单价"],
                "xAxis": "月份",
                "yAxis": ["客单价"],
                "series": []
            },
            "data": {
                "data": [
                    {"月份": "1月", "客单价": 100},
                    {"月份": "2月", "客单价": 100},
                    {"月份": "3月", "客单价": 100},
                    {"月份": "4月", "客单价": 100},
                    {"月份": "5月", "客单价": 100},
                    {"月份": "6月", "客单价": 100}
                ]
            }
        },
        view4_id: {
            "id": view4_id,
            "chart": {
                "id": view4_id,
                "type": "line",
                "sourceType": "line",
                "title": "销售趋势",
                "columns": ["日期", "销售额"],
                "xAxis": "日期",
                "yAxis": ["销售额"],
                "series": []
            },
            "data": {
                "data": [
                    {"日期": "周一", "销售额": 32000},
                    {"日期": "周二", "销售额": 28000},
                    {"日期": "周三", "销售额": 35000},
                    {"日期": "周四", "销售额": 42000},
                    {"日期": "周五", "销售额": 48000},
                    {"日期": "周六", "销售额": 55000},
                    {"日期": "周日", "销售额": 38000}
                ]
            }
        }
    }
    
    return components, view_info

# 用户分析
def create_user_dashboard():
    view1_id = f"view-{uuid.uuid4().hex[:8]}"
    view2_id = f"view-{uuid.uuid4().hex[:8]}"
    view3_id = f"view-{uuid.uuid4().hex[:8]}"
    view4_id = f"view-{uuid.uuid4().hex[:8]}"
    
    components = [
        create_view_component(view1_id, "日活用户", 1, 1, 18, 16),
        create_view_component(view2_id, "月活用户", 19, 1, 18, 16),
        create_view_component(view3_id, "用户留存", 37, 1, 18, 16),
        create_view_component(view4_id, "用户增长", 55, 1, 18, 16),
    ]
    
    view_info = {
        view1_id: {
            "id": view1_id,
            "chart": {
                "id": view1_id,
                "type": "column",
                "sourceType": "column",
                "title": "日活用户(DAU)",
                "columns": ["日期", "用户数"],
                "xAxis": "日期",
                "yAxis": ["用户数"],
                "series": []
            },
            "data": {
                "data": [
                    {"日期": "周一", "用户数": 15600},
                    {"日期": "周二", "用户数": 14800},
                    {"日期": "周三", "用户数": 16200},
                    {"日期": "周四", "用户数": 17500},
                    {"日期": "周五", "用户数": 18900},
                    {"日期": "周六", "用户数": 22000},
                    {"日期": "周日", "用户数": 19500}
                ]
            }
        },
        view2_id: {
            "id": view2_id,
            "chart": {
                "id": view2_id,
                "type": "column",
                "sourceType": "column",
                "title": "月活用户(MAU)",
                "columns": ["月份", "用户数"],
                "xAxis": "月份",
                "yAxis": ["用户数"],
                "series": []
            },
            "data": {
                "data": [
                    {"月份": "1月", "用户数": 85000},
                    {"月份": "2月", "用户数": 89000},
                    {"月份": "3月", "用户数": 95000},
                    {"月份": "4月", "用户数": 102000},
                    {"月份": "5月", "用户数": 108000},
                    {"月份": "6月", "用户数": 115000}
                ]
            }
        },
        view3_id: {
            "id": view3_id,
            "chart": {
                "id": view3_id,
                "type": "line",
                "sourceType": "line",
                "title": "7日留存率",
                "columns": ["日期", "留存率"],
                "xAxis": "日期",
                "yAxis": ["留存率"],
                "series": []
            },
            "data": {
                "data": [
                    {"日期": "第1天", "留存率": 100},
                    {"日期": "第2天", "留存率": 65},
                    {"日期": "第3天", "留存率": 52},
                    {"日期": "第4天", "留存率": 45},
                    {"日期": "第5天", "留存率": 40},
                    {"日期": "第6天", "留存率": 38},
                    {"日期": "第7天", "留存率": 35}
                ]
            }
        },
        view4_id: {
            "id": view4_id,
            "chart": {
                "id": view4_id,
                "type": "line",
                "sourceType": "line",
                "title": "用户增长趋势",
                "columns": ["月份", "新增用户"],
                "xAxis": "月份",
                "yAxis": ["新增用户"],
                "series": []
            },
            "data": {
                "data": [
                    {"月份": "1月", "新增用户": 12000},
                    {"月份": "2月", "新增用户": 15000},
                    {"月份": "3月", "新增用户": 18000},
                    {"月份": "4月", "新增用户": 22000},
                    {"月份": "5月", "新增用户": 25000},
                    {"月份": "6月", "新增用户": 28000}
                ]
            }
        }
    }
    
    return components, view_info

# 产品分析
def create_product_dashboard():
    view1_id = f"view-{uuid.uuid4().hex[:8]}"
    view2_id = f"view-{uuid.uuid4().hex[:8]}"
    view3_id = f"view-{uuid.uuid4().hex[:8]}"
    view4_id = f"view-{uuid.uuid4().hex[:8]}"
    
    components = [
        create_view_component(view1_id, "品类销售", 1, 1, 18, 16),
        create_view_component(view2_id, "地区分布", 19, 1, 18, 16),
        create_view_component(view3_id, "销售排行", 37, 1, 18, 16),
        create_view_component(view4_id, "库存周转", 55, 1, 18, 16),
    ]
    
    view_info = {
        view1_id: {
            "id": view1_id,
            "chart": {
                "id": view1_id,
                "type": "pie",
                "sourceType": "pie",
                "title": "品类销售占比",
                "columns": ["品类", "销售额"],
                "xAxis": "品类",
                "yAxis": ["销售额"],
                "series": []
            },
            "data": {
                "data": [
                    {"品类": "电子产品", "销售额": 450000},
                    {"品类": "服装鞋帽", "销售额": 320000},
                    {"品类": "食品饮料", "销售额": 280000},
                    {"品类": "家居用品", "销售额": 180000},
                    {"品类": "其他", "销售额": 120000}
                ]
            }
        },
        view2_id: {
            "id": view2_id,
            "chart": {
                "id": view2_id,
                "type": "bar",
                "sourceType": "bar",
                "title": "地区销售分布",
                "columns": ["地区", "销售额"],
                "xAxis": "地区",
                "yAxis": ["销售额"],
                "series": []
            },
            "data": {
                "data": [
                    {"地区": "华东", "销售额": 380000},
                    {"地区": "华南", "销售额": 320000},
                    {"地区": "华北", "销售额": 280000},
                    {"地区": "西南", "销售额": 180000},
                    {"地区": "其他", "销售额": 150000}
                ]
            }
        },
        view3_id: {
            "id": view3_id,
            "chart": {
                "id": view3_id,
                "type": "bar",
                "sourceType": "bar",
                "title": "产品销售排行",
                "columns": ["产品", "销量"],
                "xAxis": "产品",
                "yAxis": ["销量"],
                "series": []
            },
            "data": {
                "data": [
                    {"产品": "产品A", "销量": 5600},
                    {"产品": "产品B", "销量": 4800},
                    {"产品": "产品C", "销量": 4200},
                    {"产品": "产品D", "销量": 3800},
                    {"产品": "产品E", "销量": 3200}
                ]
            }
        },
        view4_id: {
            "id": view4_id,
            "chart": {
                "id": view4_id,
                "type": "line",
                "sourceType": "line",
                "title": "库存周转率",
                "columns": ["月份", "周转率"],
                "xAxis": "月份",
                "yAxis": ["周转率"],
                "series": []
            },
            "data": {
                "data": [
                    {"月份": "1月", "周转率": 2.8},
                    {"月份": "2月", "周转率": 3.0},
                    {"月份": "3月", "周转率": 3.2},
                    {"月份": "4月", "周转率": 3.1},
                    {"月份": "5月", "周转率": 3.4},
                    {"月份": "6月", "周转率": 3.6}
                ]
            }
        }
    }
    
    return components, view_info


def init_dashboard_data():
    """初始化仪表板数据"""
    with Session(engine) as session:
        # 清除现有数据
        session.exec(delete(CoreDashboard))
        session.commit()
        print("已清除旧数据")
        
        current_time = int(time.time())
        dashboards_to_add = []
        
        # 创建根文件夹
        root_folder_id = uuid.uuid4().hex
        root_folder = CoreDashboard(
            id=root_folder_id,
            name="示例洞察",
            pid="root",
            workspace_id="1",
            org_id="1",
            level=0,
            node_type="folder",
            type="folder",
            status=1,
            sort=0,
            create_time=current_time,
            create_by="1",
            update_time=current_time,
            version=3,
            remark="ChatBI 示例洞察集合"
        )
        dashboards_to_add.append(root_folder)
        
        # 创建子文件夹
        sales_folder_id = uuid.uuid4().hex
        sales_folder = CoreDashboard(
            id=sales_folder_id,
            name="销售报表",
            pid=root_folder_id,
            workspace_id="1",
            org_id="1",
            level=1,
            node_type="folder",
            type="folder",
            status=1,
            sort=0,
            create_time=current_time,
            create_by="1",
            update_time=current_time,
            version=3,
            remark="销售相关的洞察"
        )
        dashboards_to_add.append(sales_folder)
        
        ops_folder_id = uuid.uuid4().hex
        ops_folder = CoreDashboard(
            id=ops_folder_id,
            name="运营分析",
            pid=root_folder_id,
            workspace_id="1",
            org_id="1",
            level=1,
            node_type="folder",
            type="folder",
            status=1,
            sort=1,
            create_time=current_time,
            create_by="1",
            update_time=current_time,
            version=3,
            remark="运营相关的洞察"
        )
        dashboards_to_add.append(ops_folder)
        
        # 创建销售数据概览
        sales_components, sales_view_info = create_sales_dashboard()
        sales_dashboard = CoreDashboard(
            id=uuid.uuid4().hex,
            name="销售数据概览",
            pid=sales_folder_id,
            workspace_id="1",
            org_id="1",
            level=2,
            node_type="leaf",
            type="dashboard",
            canvas_style_data=DEFAULT_CANVAS_STYLE,
            component_data=json.dumps(sales_components, ensure_ascii=False),
            canvas_view_info=json.dumps(sales_view_info, ensure_ascii=False),
            status=1,
            sort=0,
            create_time=current_time,
            create_by="1",
            update_time=current_time,
            version=3,
            remark="展示销售核心指标"
        )
        dashboards_to_add.append(sales_dashboard)
        
        # 创建用户行为分析
        user_components, user_view_info = create_user_dashboard()
        user_dashboard = CoreDashboard(
            id=uuid.uuid4().hex,
            name="用户行为分析",
            pid=ops_folder_id,
            workspace_id="1",
            org_id="1",
            level=2,
            node_type="leaf",
            type="dashboard",
            canvas_style_data=DEFAULT_CANVAS_STYLE,
            component_data=json.dumps(user_components, ensure_ascii=False),
            canvas_view_info=json.dumps(user_view_info, ensure_ascii=False),
            status=1,
            sort=0,
            create_time=current_time,
            create_by="1",
            update_time=current_time,
            version=3,
            remark="展示用户活跃度指标"
        )
        dashboards_to_add.append(user_dashboard)
        
        # 创建产品销售分析
        product_components, product_view_info = create_product_dashboard()
        product_dashboard = CoreDashboard(
            id=uuid.uuid4().hex,
            name="产品销售分析",
            pid=ops_folder_id,
            workspace_id="1",
            org_id="1",
            level=2,
            node_type="leaf",
            type="dashboard",
            canvas_style_data=DEFAULT_CANVAS_STYLE,
            component_data=json.dumps(product_components, ensure_ascii=False),
            canvas_view_info=json.dumps(product_view_info, ensure_ascii=False),
            status=1,
            sort=1,
            create_time=current_time,
            create_by="1",
            update_time=current_time,
            version=3,
            remark="展示产品相关指标"
        )
        dashboards_to_add.append(product_dashboard)
        
        # 批量添加
        for record in dashboards_to_add:
            session.add(record)
        
        session.commit()
        print(f"成功添加洞察数据:")
        print(f"  - 根文件夹: 1 个")
        print(f"  - 子文件夹: 2 个")
        print(f"  - 洞察: 3 个 (含完整图表数据)")


if __name__ == "__main__":
    init_dashboard_data()
