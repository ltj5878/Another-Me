# Repository Guidelines

## 项目结构与模块组织

- `backend/`：FastAPI 后端，包含 SQLAlchemy 模型、Pydantic Schema、服务层和 Alembic 迁移。
- `backend/app/api/v1/`：版本化 API 路由。
- `backend/app/services/`：文章处理、分块、embedding、检索、风格画像和生成逻辑。
- `backend/app/models/`、`backend/app/schemas/`、`backend/app/db/`：数据库模型、接口数据结构和数据库连接。
- `backend/alembic/versions/`：数据库迁移脚本。
- `frontend/`：Vue 3 + Vite + TypeScript 前端。
- `frontend/src/views/`、`components/`、`stores/`、`api/`、`types/`、`assets/`：页面、组件、Pinia 状态、接口封装、共享类型和样式。
- `start.sh`：统一启动、停止、重启和查看前后端状态。
- `logs/` 和 `.run/`：运行日志和 PID 文件，不应提交运行产物。

## 构建、测试与本地开发命令

- `./start.sh`：安装缺失依赖，并启动后端 `127.0.0.1:8000` 与前端 `127.0.0.1:5173`。
- `./start.sh stop|restart|status`：停止、重启或查看服务状态。
- `cd backend && .venv/bin/alembic upgrade head`：执行数据库迁移。
- `cd backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`：仅启动 API 服务。
- `cd frontend && npm run dev -- --host 127.0.0.1 --port 5173`：仅启动前端开发服务。
- `cd frontend && npm run build`：运行 `vue-tsc` 类型检查并构建生产资源。

## 代码风格与命名约定

后端使用 Python 3.12+、4 空格缩进，并尽量为函数添加类型标注。API 路由保持轻量，业务逻辑放入 `backend/app/services/`。Python 模块、函数和变量使用 `snake_case`。

前端使用 Vue 单文件组件和 TypeScript。组件文件使用 PascalCase，例如 `StyleFormDialog.vue`；变量和函数使用 camelCase。接口请求集中放在 `frontend/src/api/`，共享响应类型放在 `frontend/src/types/`。

## 测试指南

当前仓库尚未包含自动化测试。修改后至少通过 `curl http://127.0.0.1:8000/health` 检查后端健康状态，并在 `/docs` 或前端页面手动验证相关流程。新增测试时，后端优先使用 `pytest` 并放在 `backend/tests/`；前端建议使用 Vitest 风格的 `*.spec.ts` 文件。

## 提交与 Pull Request 规范

当前目录没有 Git 历史，无法推断既有提交规范。建议使用简洁的祈使句提交信息，例如 `Add style profile editor` 或 `Fix article upload status`。PR 应包含变更摘要、涉及数据库时的迁移说明、手动测试步骤、相关 issue 链接，以及 UI 变更截图。

## 安全与配置提示

从 `.env.example` 复制生成 `backend/.env`，不要提交 API Key 或本地密钥。数据库结构变更应通过 Alembic 迁移完成，不要直接手工改表。
