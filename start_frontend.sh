#!/bin/bash
echo "=========================================="
echo "启动 ChatBI 前端服务"
echo "=========================================="
echo ""
cd "$(dirname "$0")/frontend" || exit 1
if [ ! -d "node_modules" ]; then
    echo "❌ node_modules 不存在"
    exit 1
fi
echo "✅ 启动前端服务..."
echo ""
echo "前端地址: http://localhost:5173"
echo ""
npm run dev
