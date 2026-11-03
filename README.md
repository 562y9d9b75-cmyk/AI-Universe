# AI Universe · 个人 AI 公司

一个可本地运行、使用 PostgreSQL 持久化和独立工作进程的个人公司管理系统。已实现公司/部门/员工、任务编排、审批、文件版本、四级记忆、调用记录、预算边界与可交互 GLB 办公楼层。

**当前是可运行的基础版本，尚不满足任务书的完整旗舰版验收。** 尚无真实模型授权或自主 AI 推理；指定官方文档被当前云网络阻断，未能确认最新 Sign in with ChatGPT 集成条件。写实员工与完整生活动画尚未制作。具体见 [验收清单](docs/ACCEPTANCE.md) 与 [模型授权记录](docs/MODEL_AUTHORIZATION.md)。本地模式是明确标注的确定性文件工具，不伪装为模型生成。

## 本机启动

### Mac 简易启动（只安装 Docker Desktop）

1. 安装并打开 [Docker Desktop](https://www.docker.com/products/docker-desktop/)，等待引擎显示已运行。
2. 下载最新源码 ZIP 并解压。在文件夹中打开 `启动 AI Universe.command`。
3. 首次会下载免费开源组件并构建软件，可能需要几分钟。看到“AI Universe 已就绪”后会自动打开浏览器。

Python、Node.js、PostgreSQL、Redis 和后台工作进程均由容器提供，Mac 不需要单独安装 Python 或 Node.js。安装所缺软件、构建和启动失败都会显示具体提示，不会再静默退出。Mac 系统安全拦截时检查文件来源，不需要关闭系统安全保护；也可从终端用 Bash 运行文件：

```sh
cd "$HOME/Desktop/AI-Universe-main"
bash "启动 AI Universe.command"
```

停止容器版：`bash scripts/stop-docker.sh`。再次启动运行同一个 `.command` 即可。关闭终端不会删除数据。容器版数据存放在 Compose 项目的 `postgres_data`、`redis_data`、`artifacts_data` 命名卷；不要删除这些卷。默认只公开本机 3000 端口，数据库/API 不向宿主机公开。已有 `.env` 会保留。容器版使用独立 Compose 项目 `ai-universe-desktop`，开发模式的数据库和成果不受影响；两种方式的数据不会自动迁移，请选择一种日常使用，不要同时占用同一网页端口。

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
../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

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

# 真实 PostgreSQL + worker + Next + Chromium 端到端
# 先停止 start.sh；需要系统 Chromium 或设置 AIU_CHROMIUM 的浏览器路径
.venv/bin/python scripts/test_e2e.py
```

E2E 会创建唯一的临时 PostgreSQL 数据库，启动三个真实进程，用浏览器操作界面和下载文件。退出时只清理自己创建的进程与临时数据库；保留 `docs/evidence/` 中的报告截图与 `.run/` 中日志。不会初始化所有者数据库里的测试账号。

## 文件导航

- [使用说明](docs/USER_GUIDE.md)
- [功能验收清单](docs/ACCEPTANCE.md)
- [测试报告](docs/TEST_REPORT.md)
- [模型授权核验](docs/MODEL_AUTHORIZATION.md)
- [架构与当前限制](docs/ARCHITECTURE.md)
- [3D 资产授权](docs/ASSET_LICENSES.md)
- `backend/app/migrate.py`：可重复执行的数据库初始化/迁移
- `scripts/setup.sh` / `scripts/start.sh`：安装与统一启动
- `frontend/public/assets/` / `assets/`：GLB 与 Blender 源文件

数据：开发模式使用 PostgreSQL/Redis 命名卷与 `.data/artifacts`；容器版使用 PostgreSQL/Redis/成果三个命名卷。备份需要同时保存 `.env`、数据库和相应成果存储，不能只复制前端目录。
