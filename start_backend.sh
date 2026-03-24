#!/bin/bash
echo "=========================================="
echo "启动 ChatBI 后端服务"
echo "=========================================="
echo ""
cd "$(dirname "$0")/backend" || exit 1
if [ ! -d ".venv" ]; then
    echo "❌ 虚拟环境不存在"
    exit 1
fi
echo "✅ 激活虚拟环境..."
source .venv/bin/activate
echo "✅ 启动后端服务..."
echo ""
echo "后端地址: http://localhost:8000"
echo "API 文档: http://localhost:8000/docs"
echo ""
python main.py
