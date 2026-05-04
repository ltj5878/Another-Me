# Another Me

Another Me 是一个本地运行的“个人写作风格资料库 + AI 写作生成器”。它可以上传个人旧文，提取并分析写作风格，再基于风格画像、用户输入和可选旧文片段生成新文章。

## 当前完成情况

已完成的主要能力：

- Vue 3 前端工作台，包含风格库、风格详情和写文章页面。
- FastAPI 后端 API，使用 SQLAlchemy 2.0、Alembic、PostgreSQL 16 和 pgvector。
- 风格分类的创建、查看、编辑、删除。
- `.txt` / `.md` / `.docx` 源文章上传、文本提取、清洗、字数统计、分块和 embedding 入库。
- 源文章列表、详情查看、原文/清洗文本/分块查看和删除。
- 基于至少 3 篇 completed 文章生成风格画像，并支持手动编辑画像。
- 写文章页面支持写作类型、长度、语气强度、补充要求和是否引用旧文片段。
- 生成正文、最近生成历史、生成历史删除、复制正文和导出 Markdown。
- 对生成结果执行重新生成、继续改写、缩短、扩写、更尖锐、更克制、更像原风格、降低模仿痕迹、修改开头、修改结尾。
- Prompt 调试台可查看 System Prompt、User Prompt、风格画像、检索片段和最终结果，并可修改 Prompt 后重新生成。

暂未包含：登录与多用户隔离、流式输出、异步任务队列、生成版本树/对比、收藏功能和自动化测试套件。

## 技术栈

前端：

- Vue 3
- Vite
- TypeScript
- Pinia
- Vue Router
- Element Plus
- Axios

后端：

- Python 3.12+
- FastAPI
- SQLAlchemy 2.0
- Alembic
- Pydantic Settings
- psycopg
- python-docx
- OpenAI Python SDK，用于调用兼容 OpenAI 协议的 embedding 与 LLM 服务

数据库：

- PostgreSQL 16
- pgvector，`article_chunks.embedding` 使用 `vector(1536)`

## 项目结构

```text
.
├── backend/
│   ├── app/
│   │   ├── api/v1/        # styles、search、generations API
│   │   ├── core/          # 配置和日志
│   │   ├── db/            # 数据库会话和自定义类型
│   │   ├── models/        # SQLAlchemy 模型
│   │   ├── schemas/       # Pydantic Schema
│   │   └── services/      # 文章、分块、embedding、检索、画像、生成逻辑
│   ├── alembic/           # 数据库迁移
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/           # Axios API 封装
│   │   ├── components/    # 复用组件
│   │   ├── layouts/       # 页面布局
│   │   ├── stores/        # Pinia 状态
│   │   ├── types/         # 共享类型
│   │   └── views/         # Styles、StyleDetail、Write 页面
│   └── package.json
├── start.sh               # 一键启动/停止脚本
├── .env.example           # 环境变量示例
└── README.md
```

## 环境准备

需要本机已安装：

- Node.js 20+
- npm
- Python 3.12+
- PostgreSQL 16
- pgvector

如果使用 Homebrew 的 PostgreSQL 16，常用命令一般位于：

```bash
/opt/homebrew/opt/postgresql@16/bin
```

创建数据库：

```bash
/opt/homebrew/opt/postgresql@16/bin/createdb vibe_writer
```

安装 pgvector：

```bash
brew install pgvector
```

如果 Homebrew 安装的 pgvector 没有覆盖 PostgreSQL 16，需要针对 PostgreSQL 16 编译安装 pgvector。

## 环境变量

后端读取 `backend/.env`。可以参考 `.env.example` 创建：

```bash
DATABASE_URL=postgresql+psycopg://lvtongjie@localhost:5432/vibe_writer
BACKEND_CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
EMBEDDING_API_KEY=
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v4
LLM_API_KEY=
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-pro
LLM_TEMPERATURE=0.3
```

说明：

- 上传文章会立即分块并调用 embedding 服务，因此需要配置 `EMBEDDING_API_KEY`。
- 生成风格画像和正文需要配置 `LLM_API_KEY`。
- 前端默认请求 `http://127.0.0.1:8000`。如需覆盖，创建 `frontend/.env.local` 并设置 `VITE_API_BASE_URL=http://127.0.0.1:8000`。

## 数据库迁移

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head
```

当前迁移会创建：

- `users`
- `style_categories`
- `source_articles`
- `article_chunks`
- `style_profiles`
- `generation_tasks`
- `generated_outputs`

## 一键启动

在项目根目录运行：

```bash
./start.sh
```

脚本会安装缺失依赖并启动：

- 后端：http://127.0.0.1:8000
- 前端：http://127.0.0.1:5173

管理命令：

```bash
./start.sh status
./start.sh restart
./start.sh stop
```

日志和 PID 文件：

```text
logs/backend.log
logs/frontend.log
.run/backend.pid
.run/frontend.pid
```

## 手动启动

后端：

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

前端：

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

生产构建前端：

```bash
cd frontend
npm run build
```

健康检查和 API 文档：

```bash
curl http://127.0.0.1:8000/health
```

```text
http://127.0.0.1:8000/docs
```

## 使用流程

1. 打开 `http://127.0.0.1:5173`。
2. 在风格库创建一个风格分类，并选择写作类型提示。
3. 进入风格详情，上传 `.txt`、`.md` 或 `.docx` 源文章。
4. 等待文章同步完成清洗、分块和 embedding，状态变为 `completed`。
5. 至少上传 3 篇 completed 文章后，点击“重新分析风格”生成风格画像。
6. 在“写文章”页面选择风格，填写写作要求，选择是否引用旧文片段后生成正文。
7. 需要时继续改写、调试 Prompt、复制正文或导出 Markdown。

## API 概览

主要接口挂载在 `/api/v1`：

- `GET /styles`、`POST /styles`、`GET/PATCH/DELETE /styles/{style_id}`
- `GET /styles/{style_id}/articles`
- `POST /styles/{style_id}/articles/upload`
- `GET/DELETE /styles/{style_id}/articles/{article_id}`
- `GET /styles/{style_id}/profile`
- `POST /styles/{style_id}/profile/generate`
- `PATCH /styles/{style_id}/profile`
- `POST /search`
- `POST /generations`
- `GET /generations`
- `GET/DELETE /generations/{generation_id}`
- `POST /generations/{generation_id}/revise`
- `POST /generations/debug-run`

## 文章处理状态

系统预留这些状态：

- `uploaded`
- `cleaning`
- `chunking`
- `embedding`
- `analyzing`
- `completed`
- `failed`

当前采用同步处理。上传成功后通常会依次进入 `cleaning`、`chunking`、`embedding`，完成后写入 `completed`；如果 embedding 或文件解析失败，会写入 `failed`。

## 开发说明

- 业务逻辑优先放在 `backend/app/services/`，API 层保持薄封装。
- 数据库结构变更必须新增 Alembic 迁移，不要直接手工改表。
- 前端 API 封装集中在 `frontend/src/api/`，共享类型集中在 `frontend/src/types/`。
- `backend/.env`、`backend/.venv/`、`frontend/node_modules/`、`frontend/dist/`、`.run/` 和 `logs/` 已在 `.gitignore` 中排除。
- 当前没有自动化测试。改动后至少运行后端健康检查、前端 `npm run build`，并手动验证相关页面流程。
