#!/bin/bash
set -e

SSR_PATH=/opt/chatbi/g2-ssr
APP_PATH=/opt/chatbi/app

PM2_CMD_PATH=$SSR_PATH/node_modules/pm2/bin/pm2

# 显式设置 UTF-8 locale，防止 PostgreSQL 客户端编码不一致导致中文乱码
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
export PGCLIENTENCODING=UTF8

# Start PostgreSQL
service postgresql start

# Wait for PostgreSQL to be ready
until pg_isready -U root -d chatbi; do
  echo "Waiting for PostgreSQL to be ready..."
  sleep 2
done

echo "PostgreSQL is ready."

# Start g2-ssr with PM2
cd $SSR_PATH
$PM2_CMD_PATH start app.js --name g2-ssr
echo "G2 SSR service started."

# Start FastAPI application
cd $APP_PATH
uvicorn main:mcp_app --host 0.0.0.0 --port 8001 &
echo "MCP server started on port 8001."

uvicorn main:app --host 0.0.0.0 --port 8000
