# Build ChatBI
# Copyright © 2026 ChatBI
FROM --platform=${BUILDPLATFORM} registry.cn-qingdao.aliyuncs.com/dataease/chatbi-base:latest AS chatbi-ui-builder
ENV CHATBI_HOME=/opt/chatbi
ENV APP_HOME=${CHATBI_HOME}/app
ENV UI_HOME=${CHATBI_HOME}/frontend
ENV DEBIAN_FRONTEND=noninteractive

RUN mkdir -p ${APP_HOME} ${UI_HOME}

COPY frontend /tmp/frontend
RUN cd /tmp/frontend && npm install && npm run build && mv dist ${UI_HOME}/dist


FROM registry.cn-qingdao.aliyuncs.com/dataease/chatbi-base:latest AS chatbi-builder
# Set build environment variables
ENV PYTHONUNBUFFERED=1
ENV CHATBI_HOME=/opt/chatbi
ENV APP_HOME=${CHATBI_HOME}/app
ENV UI_HOME=${CHATBI_HOME}/frontend
ENV PYTHONPATH=${CHATBI_HOME}/app
ENV PATH="${APP_HOME}/.venv/bin:$PATH"
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV DEBIAN_FRONTEND=noninteractive

# Create necessary directories
RUN mkdir -p ${APP_HOME} ${UI_HOME}

WORKDIR ${APP_HOME}

COPY  --from=chatbi-ui-builder ${UI_HOME} ${UI_HOME}
# Install dependencies
RUN test -f "./uv.lock" && \
    --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=backend/uv.lock,target=uv.lock \
    --mount=type=bind,source=backend/pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project || echo "uv.lock file not found, skipping intermediate-layers"

COPY ./backend ${APP_HOME}

# Final sync to ensure all dependencies are installed
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --extra cpu

# Build g2-ssr
FROM registry.cn-qingdao.aliyuncs.com/dataease/chatbi-base:latest AS ssr-builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential python3 pkg-config \
    libcairo2-dev libpango1.0-dev libjpeg-dev libgif-dev librsvg2-dev \
    libpixman-1-dev libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

# configure npm
RUN npm config set fund false \
    && npm config set audit false \
    && npm config set progress false

COPY g2-ssr/app.js g2-ssr/package.json /app/
COPY g2-ssr/charts/* /app/charts/
RUN npm install

# Download bilingual embedding model (BAAI/bge-base-zh-v1.5, supports Chinese + English)
FROM python:3.11-slim-bookworm AS embedding-model-downloader
RUN pip install --no-cache-dir huggingface_hub
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('BAAI/bge-base-zh-v1.5', local_dir='/opt/chatbi/models/embedding/BAAI_bge-base-zh-v1.5')"

# Runtime stage
FROM --platform=${BUILDPLATFORM} registry.cn-qingdao.aliyuncs.com/dataease/chatbi-python-pg:latest

RUN ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    echo "Asia/Shanghai" > /etc/timezone

# 🔧 修复：设置 UTF-8 locale，防止 PostgreSQL 和 Python 使用非 UTF-8 编码
# Docker 容器默认 locale 可能是 POSIX/C，导致中文列名写入/读取时乱码
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8
ENV PGCLIENTENCODING=UTF8

# Set runtime environment variables
ENV PYTHONUNBUFFERED=1
ENV CHATBI_HOME=/opt/chatbi
ENV PYTHONPATH=${CHATBI_HOME}/app
ENV PATH="${CHATBI_HOME}/app/.venv/bin:$PATH"

ENV POSTGRES_DB=chatbi
ENV POSTGRES_USER=root
# 🔧 安全修复：不在镜像中硬编码数据库密码
# 运行时通过 docker run -e POSTGRES_PASSWORD=xxx 或 docker-compose.yml 注入
ENV POSTGRES_PASSWORD=""

# Add Oracle instant client path to ENV
ENV LD_LIBRARY_PATH="/opt/chatbi/db_client/oracle_instant_client:${LD_LIBRARY_PATH}"

# Copy necessary files from builder
COPY start.sh /opt/chatbi/app/start.sh
COPY g2-ssr/*.ttf /usr/share/fonts/truetype/liberation/
COPY --from=chatbi-builder ${CHATBI_HOME} ${CHATBI_HOME}
COPY --from=ssr-builder /app /opt/chatbi/g2-ssr
COPY --from=embedding-model-downloader /opt/chatbi/models /opt/chatbi/models

WORKDIR ${CHATBI_HOME}/app

RUN mkdir -p /opt/chatbi/images /opt/chatbi/g2-ssr

EXPOSE 3000 8000 8001 5432

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000 || exit 1

ENTRYPOINT ["sh", "start.sh"]
