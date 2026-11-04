# AI Universe · 个人 AI 公司

一个可本地运行、带独立工作进程的个人公司管理系统，支持 SQLite 个人本地版和 PostgreSQL 标准部署。已实现公司/部门/员工、任务编排、审批、文件版本、四级记忆、调用记录、预算边界与可交互 GLB 办公楼层。

当前已加入：8 位中文员工及独立写实虚拟头像、可编辑姓名与人物档案、英国/法国可选形象、新版总部楼层，以及官方 Sign in with ChatGPT 模型适配和模型驱动的多员工任务规划。

**本人 ChatGPT 授权与真实推理仍需在本机完成验证；完整写实 3D 人物与生活动画尚未交付。** 官方开源/个人本地集成条件已核实，软件不读取 Cookie、独立 API key 或 Codex 凭据，不购买额度、不回退付费 API。具体见 [验收清单](docs/ACCEPTANCE.md) 和 [模型授权说明](docs/MODEL_AUTHORIZATION.md)。本地规则模式无需模型，能够整理材料、统计数据和生成文件。

## 本机启动

### 推荐：免 Docker 个人本地版（macOS13.5+）

支持 Intel Mac（含 macOS13.7.8）和 Apple Silicon。无需预装 Python、Node.js、Docker、PostgreSQL 或 Redis。下载最新源码并解压，在项目目录执行：

```sh
bash scripts/start-local.sh
```

例如下载 main 分支 ZIP 并解压到桌面后：

```sh
cd "$HOME/Desktop/AI-Universe-main" && bash scripts/start-local.sh
```

首次自动准备并验证便携 Python3.12.16 / Node24.22.2、安装锁定依赖、构建界面、初始化本机 SQLite，并启动 API、工作进程和网页。看到“AI Universe 已就绪”后自动打开浏览器。保持终端开启；按 Ctrl+C 停止。以后执行同一命令会复用已验证运行时和有效构建。

`启动 AI Universe.command` 也使用免 Docker 模式；如果 Mac 拒绝直接双击，使用上面的 Bash 命令，不需要关闭系统安全保护。首次安装需要访问 GitHub、nodejs.org、PyPI 和 npm；不会安装 Homebrew，不需要管理员权限，不购买服务。

数据、运行时和日志位于 `~/Library/Application Support/AI Universe/local/`，不会随源码重新下载而重置。停止后备份整个 `data` 目录，包含 SQLite、相关 WAL 文件和 artifacts。此模式不读取/覆盖项目 .env，也不迁移或覆盖原有 PostgreSQL 数据。详情见 [本地运行时说明](docs/LOCAL_RUNTIME.md)。

### 可选：Docker Desktop 全栈

仅在电脑支持且已运行 Docker Desktop 时，用 `bash scripts/start-docker.sh` 启动，`bash scripts/stop-docker.sh` 停止。独立项目 ai-universe-desktop 包含 PostgreSQL/Redis/API/worker/网页，数据保存在对应命名卷。两种模式的数据不自动迁移；不要同时占用同一网页端口。

### 本机开发模式（已有 Python 和 Node.js 时）

需要 Node.js 22+（建议24）、Python 3.11+（已测3.12）、Docker/Compose v2。`bash scripts/check-environment.sh` 会逐项显示缺失或过旧的工具，并检查 Docker 是否已运行。

在项目目录执行：

```sh
bash scripts/setup.sh
bash scripts/start.sh
```

启动脚本兼容 Mac 自带 Bash 3.2。已在 Linux 容器中实测 Bash 3.2 脚本契约及完整容器运行；尚未在用户的 macOS 实机完成验收。

然后用本机浏览器打开 **http://localhost:3000**。首次启动创建唯一的所有者账户，密码至少 12 位；以后只显示登录，不开放商业注册。`Ctrl+C` 停止应用进程，数据保留；数据库和 Redis 容器继续运行。需要停止基础服务时执行 `docker compose stop`，不要使用带 `-v` 的删除命令。

`setup.sh` 在 `.env` 不存在时生成随机数据库密码，安装锁定依赖、等待数据库/Redis、执行迁移、构建前端。可重复运行，不覆盖已有 `.env`，不重置数据库。已交付生成好的 GLB 文件，普通使用者无需安装 Blender。

仓库中可参考 `.env.example`；不要把示例中的 CHANGE_ME 当作真实配置。不要将本机 `.env`、`.data` 或数据库快照上传到 GitHub。项目没有自动推送或发布流程，也没有调用任何付费模型的代码路径。

修改端口时同时调整 `.env` 中 `AIU_PORT` / `AIU_WEB_PORT` / `AIU_ORIGIN`，并重新运行 setup 以更新 Next 的代理目标。默认只允许回环访问，不是公网部署方案。

## 开发

```sh
# 在项目根目录；先运行 setup.sh
# 终端一：加载本地配置，启动 API
set -a; source .env; set +a
cd backend
../.venv/bin/uvicorn app.main:app --no-access-log --host 127.0.0.1 --port 8000 --reload

# 终端二：同样加载 .env 后
cd backend
../.venv/bin/python -m app.runtime

# 终端三
cd frontend
npm run dev
```

公司工作区是当前任务内的已有 checkout，不需要另建 Git worktree。

## 测试

```sh
# 项目根目录；不触碰所有者业务数据
.venv/bin/python -m pytest backend/tests -q
npm --prefix frontend run typecheck

# 便携运行时 + SQLite + worker + Next + Chromium 完整安装与端到端
.venv/bin/python scripts/test_local_e2e.py

# 可选：真实 PostgreSQL + worker + Next + Chromium 端到端
# 先停止 start.sh；需要系统 Chromium 或设置 AIU_CHROMIUM 的浏览器路径
.venv/bin/python scripts/test_e2e.py
```

E2E 会创建唯一的临时 PostgreSQL 数据库，启动三个真实进程，用浏览器操作界面和下载文件。退出时只清理自己创建的进程与临时数据库；保留 `docs/evidence/` 中的报告截图与 `.run/` 中日志。不会初始化所有者数据库里的测试账号。

## 文件导航

- [使用说明](docs/USER_GUIDE.md)
- [功能验收清单](docs/ACCEPTANCE.md)
- [测试报告](docs/TEST_REPORT.md)
- [本地运行时说明](docs/LOCAL_RUNTIME.md)
- [模型授权核验](docs/MODEL_AUTHORIZATION.md)
- [架构与当前限制](docs/ARCHITECTURE.md)
- [3D 资产授权](docs/ASSET_LICENSES.md)
- `backend/app/migrate.py`：可重复执行的数据库初始化/迁移
- `scripts/setup.sh` / `scripts/start.sh`：安装与统一启动
- `frontend/public/assets/` / `assets/`：GLB 与 Blender 源文件

数据：免 Docker 本地版使用用户目录下的 SQLite 和成果目录；开发模式使用 PostgreSQL/Redis 命名卷与 `.data/artifacts`；容器版使用 PostgreSQL/Redis/成果三个命名卷。备份需要同时保存 `.env`、数据库和相应成果存储，不能只复制前端目录。
