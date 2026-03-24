#!/usr/bin/env python3
"""
下载嵌入模型脚本
Download embedding model script
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sentence_transformers import SentenceTransformer
from common.core.config import settings


def download_model():
    """下载嵌入模型到本地"""
    
    # 从配置获取模型路径
    model_path = settings.LOCAL_MODEL_PATH
    model_name = 'BAAI/bge-base-zh-v1.5'
    
    # 创建目标目录
    target_dir = os.path.join(model_path, 'embedding', 'BAAI_bge-base-zh-v1.5')
    os.makedirs(target_dir, exist_ok=True)
    
    print(f"正在下载模型: {model_name}")
    print(f"目标路径: {target_dir}")
    print("这可能需要几分钟时间，请耐心等待...\n")
    
    try:
        # 下载模型
        model = SentenceTransformer(model_name)
        
        # 保存到本地
        model.save(target_dir)
        
        print(f"\n✓ 模型下载成功！")
        print(f"保存位置: {target_dir}")
        
        # 验证模型
        print("\n正在验证模型...")
        test_model = SentenceTransformer(target_dir)
        test_embedding = test_model.encode("测试文本")
        print(f"✓ 模型验证成功！嵌入维度: {len(test_embedding)}")
        
    except Exception as e:
        print(f"\n✗ 下载失败: {str(e)}")
        print("\n可能的解决方案:")
        print("1. 检查网络连接")
        print("2. 如果在中国大陆，可能需要配置 HuggingFace 镜像:")
        print("   export HF_ENDPOINT=https://hf-mirror.com")
        print("3. 或者临时禁用嵌入功能:")
        print("   在 .env 文件中设置 EMBEDDING_ENABLED=false")
        sys.exit(1)


if __name__ == "__main__":
    download_model()
