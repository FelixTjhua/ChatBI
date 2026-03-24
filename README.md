# ChatBI - 基于RAG与大语言模型的商业智能分析对话系统

<p align="center">
  <img src="frontend/public/favicon.png" alt="ChatBI" width="200" />
</p>

<h3 align="center">Business Intelligence Analysis Dialogue System based on RAG and Large Language Models</h3>

---

## 项目简介

ChatBI 是一款面向商业智能分析的对话系统，基于 RAG（检索增强生成）与大语言模型构建。系统通过构建结构化知识库（商业术语库、SQL示例库）与半结构化知识库（PDF文档），结合向量检索与大模型能力，实现自然语言驱动的数据查询、分析、预测与可视化。

## 核心功能

- **智能对话**: 自然语言转 SQL，支持销售、财务、运营等商业场景的数据分析
- **RAG 知识库**: 商业术语库 + SQL示例库，基于 pgvector 向量检索增强生成质量
- **文档问答**: PDF 文档语义分块与向量化检索，支持文档级知识问答
- **数据源管理**: 支持 PostgreSQL、MySQL、Oracle 及 Excel/CSV、PDF 文件
- **可视化仪表板**: 自动图表生成（折线图、柱状图、饼图等），支持保存与拖拽布局
- **多模型支持**: 兼容 ChatGPT、DeepSeek、通义千问等主流 LLM
- **多语言**: 中文 / English

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + TypeScript, Element Plus, Vite, Pinia |
| 后端 | Python 3.11, FastAPI, SQLModel, LangChain |
| 数据库 | PostgreSQL 15+ with pgvector |
| 向量模型 | BAAI/bge-base-zh-v1.5 (768维) |
| 图表渲染 | AntV G2 (前端) + G2 SSR (服务端) |

## 项目结构

```
ChatBI/
├── frontend/           # Vue 3 前端
├── backend/            # FastAPI 后端
│   ├── apps/           # 业务模块（chat, datasource, dashboard 等）
│   ├── alembic/        # 数据库迁移
│   └── scripts/        # 初始化脚本
├── g2-ssr/             # G2 图表服务端渲染服务
├── installer/          # 部署安装脚本
├── Dockerfile          # Docker 镜像构建
└── .env                # 环境变量配置（不提交到仓库）
```

## 快速开始

### 环境要求

- Node.js 18+
- Python 3.11+
- uv（Python 包管理器）
- PostgreSQL 15+（需启用 pgvector 扩展）

### 安装步骤

1. 克隆项目
```bash
git clone <repository-url>
cd ChatBI
```

2. 配置环境变量
```bash
# 编辑 .env，填写数据库连接信息
vi .env
```

3. 安装后端依赖并初始化数据库
```bash
cd backend
uv sync --extra cpu
alembic upgrade head
```

4. 下载嵌入模型
```bash
python scripts/download_embedding_model.py
```

5. 启动后端
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

6. 安装并启动前端
```bash
cd frontend
npm install
npm run dev
```

### Docker 部署

```bash
docker build -t chatbi .
docker run -p 8000:8000 chatbi
```

### 默认账号

- 地址: http://localhost:8000
- 账号: `admin`
- 密码: `ChatBI@123456`

## 论文信息

- **题目**: 基于RAG与大语言模型的商业智能分析对话系统
- **作者**: Felix Alvin Juandra (蔡威广)

## 版权声明

Copyright © Felix Alvin Juandra (蔡威广). All Rights Reserved.

本项目仅供学术研究和教育目的使用，详见 [LICENSE](LICENSE)。
