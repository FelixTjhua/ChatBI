#!/usr/bin/env python3
"""ChatBI 全部示例数据初始化脚本"""

import sys
import os
import traceback

# 确保可以导入其他脚本
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    print("=" * 70)
    print("  ChatBI — 基于RAG与大语言模型的商业智能分析对话系统")
    print("  商业级示例数据初始化")
    print("=" * 70)
    
    errors = []
    
    # 1. 初始化用户和工作空间
    print("\n" + "─" * 70)
    print("📌 步骤 1/4: 初始化用户和工作空间")
    print("─" * 70)
    try:
        from scripts.init_user_data import main as init_users
        init_users()
        print("用户和工作空间初始化完成")
    except Exception as e:
        error_msg = f"用户初始化出错: {e}"
        print(f"⚠️  {error_msg}")
        errors.append(error_msg)
        traceback.print_exc()
    
    # 2. 初始化RAG知识库
    print("\n" + "─" * 70)
    print("📌 步骤 2/4: 初始化商业级RAG知识库")
    print("─" * 70)
    try:
        from scripts.init_rag_data import main as init_rag
        init_rag()
        print("商业级RAG知识库初始化完成")
    except Exception as e:
        error_msg = f"商业级RAG知识库初始化出错: {e}"
        print(f"⚠️  {error_msg}")
        errors.append(error_msg)
        traceback.print_exc()
    
    # 3. 初始化Prompt模板
    print("\n" + "─" * 70)
    print("📌 步骤 3/4: 初始化Prompt模板")
    print("─" * 70)
    try:
        from scripts.init_prompt_data import init_prompt_data
        init_prompt_data()
        print("Prompt模板初始化完成")
    except Exception as e:
        error_msg = f"Prompt模板初始化出错: {e}"
        print(f"⚠️  {error_msg}")
        errors.append(error_msg)
        traceback.print_exc()
    
    # 4. 初始化仪表板
    print("\n" + "─" * 70)
    print("📌 步骤 4/4: 初始化仪表板")
    print("─" * 70)
    try:
        from scripts.init_dashboard_data import init_dashboard_data
        init_dashboard_data()
        print("仪表板初始化完成")
    except Exception as e:
        error_msg = f"仪表板初始化出错: {e}"
        print(f"⚠️  {error_msg}")
        errors.append(error_msg)
        traceback.print_exc()
    
    # 完成
    print("\n" + "=" * 70)
    if errors:
        print("⚠️  ChatBI 示例数据初始化完成（有错误）")
        print("=" * 70)
        print("\n以下步骤出现错误:")
        for i, err in enumerate(errors, 1):
            print(f"   {i}. {err}")
    else:
        print("🎉 ChatBI 全部示例数据初始化完成!")
        print("=" * 70)
    
    print("""📋 初始化内容摘要:""")
    
    # 返回错误数量，用于脚本退出码
    return len(errors)


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
