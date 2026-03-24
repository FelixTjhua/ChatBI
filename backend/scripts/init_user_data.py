#!/usr/bin/env python3
"""
ChatBI 用户初始化脚本
创建示例用户数据
"""

import sys
import os
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select
from common.core.db import engine
from common.core.security import default_hashed_pwd
from common.utils.time import get_timestamp
from apps.system.models.user import UserModel


def init_users(session: Session):
    """初始化用户数据 - 5个管理员 + 5个普通用户"""
    # 2026-02-04 00:00:00 的时间戳
    admin_create_time = int(datetime(2026, 2, 4, 0, 0, 0).timestamp())
    
    users = [
        # 5个管理员
        {
            "account": "admin",
            "name": "Administrator",
            "email": "admin@chatbi.com",
            "status": 1,
            "role": "admin",
            "create_time": admin_create_time,  # 特定时间
        },
        {
            "account": "admin2",
            "name": "李四",
            "email": "lisi@chatbi.com",
            "status": 1,
            "role": "admin",
            "create_time": None,  # 使用当前时间
        },
        {
            "account": "admin3",
            "name": "王五",
            "email": "wangwu@chatbi.com",
            "status": 1,
            "role": "admin",
            "create_time": None,
        },
        {
            "account": "admin4",
            "name": "赵六",
            "email": "zhaoliu@chatbi.com",
            "status": 1,
            "role": "admin",
            "create_time": None,
        },
        {
            "account": "admin5",
            "name": "孙七",
            "email": "sunqi@chatbi.com",
            "status": 1,
            "role": "admin",
            "create_time": None,
        },
        # 5个普通用户
        {
            "account": "user1",
            "name": "张三",
            "email": "zhangsan@chatbi.com",
            "status": 1,
            "role": "member",
            "create_time": None,
        },
        {
            "account": "user2",
            "name": "周八",
            "email": "zhouba@chatbi.com",
            "status": 1,
            "role": "member",
            "create_time": None,
        },
        {
            "account": "user3",
            "name": "吴九",
            "email": "wujiu@chatbi.com",
            "status": 1,
            "role": "member",
            "create_time": None,
        },
        {
            "account": "user4",
            "name": "郑十",
            "email": "zhengshi@chatbi.com",
            "status": 1,
            "role": "member",
            "create_time": None,
        },
        {
            "account": "user5",
            "name": "钱十一",
            "email": "qianshiyi@chatbi.com",
            "status": 1,
            "role": "member",
            "create_time": None,
        },
    ]
    
    created_users = 0
    updated_users = 0
    
    for user_data in users:
        # 检查用户是否存在
        existing = session.exec(
            select(UserModel).where(UserModel.account == user_data["account"])
        ).first()
        
        if existing:
            print(f"  用户已存在: {user_data['name']} ({user_data['account']})")
            # 更新现有用户的role字段和创建时间
            updated = False
            if not hasattr(existing, 'role') or existing.role != user_data["role"]:
                existing.role = user_data["role"]
                updated = True
                print(f"  ✓ 更新用户角色: {user_data['name']} -> {user_data['role']}")
            
            # 如果是 Administrator 账号，更新创建时间
            if user_data["account"] == "admin" and user_data.get("create_time"):
                existing.create_time = user_data["create_time"]
                updated = True
                print(f"  ✓ 更新创建时间: {user_data['name']} -> 2026-02-04")
            
            if updated:
                session.add(existing)
                updated_users += 1
        else:
            user = UserModel(
                account=user_data["account"],
                name=user_data["name"],
                email=user_data["email"],
                status=user_data["status"],
                role=user_data["role"],
                oid=1,  # 默认工作空间ID
                password=default_hashed_pwd(),
                create_time=user_data.get("create_time") or get_timestamp(),
                language="zh-CN"
            )
            session.add(user)
            created_users += 1
            print(f"  ✓ 创建用户: {user_data['name']} ({user_data['account']}) - {user_data['role']}")
    
    session.commit()
    return created_users, updated_users


def main():
    print("=" * 60)
    print("ChatBI 用户数据初始化")
    print("=" * 60)
    
    with Session(engine) as session:
        # 初始化用户
        print("\n👥 初始化用户...")
        user_count, updated_count = init_users(session)
        print(f"   创建了 {user_count} 个新用户")
        print(f"   更新了 {updated_count} 个现有用户")
        
        print("\n" + "=" * 60)
        print("用户数据初始化完成!")
        print("=" * 60)
        print("\n📋 提示: 默认密码请查看系统配置文件")
        print("\n👤 创建的用户 (5个管理员 + 5个普通用户):")
        print("\n   管理员:")
        print("   - admin (Administrator) - 创建时间: 2026-02-04")
        print("   - admin2 (李四)")
        print("   - admin3 (王五)")
        print("   - admin4 (赵六)")
        print("   - admin5 (孙七)")
        print("\n   普通用户:")
        print("   - user1 (张三)")
        print("   - user2 (周八)")
        print("   - user3 (吴九)")
        print("   - user4 (郑十)")
        print("   - user5 (钱十一)")


if __name__ == "__main__":
    main()
