# AI Universe · 个人 AI 公司

一个可本地运行、使用 PostgreSQL 持久化和独立工作进程的个人公司管理系统。已实现公司/部门/员工、任务编排、审批、文件版本、四级记忆、调用记录、预算边界与可交互 GLB 办公楼层。

**当前是可运行的基础版本，尚不满足任务书的完整旗舰版验收。** 尚无真实模型授权或自主 AI 推理；指定官方文档被当前云网络阻断，未能确认最新 Sign in with ChatGPT 集成条件。写实员工与完整生活动画尚未制作。具体见 [验收清单](docs/ACCEPTANCE.md) 与 [模型授权记录](docs/MODEL_AUTHORIZATION.md)。本地模式是明确标注的确定性文件工具，不伪装为模型生成。

## 本机启动

需要 Node.js 22.0+（建议 24）、Python 3.11+（已测 3.12）、Docker Engine/Compose v2，以及首次安装依赖的网络访问。支持 Linux；macOS 和 Windows WSL2 应具备上述环境，尚未在这些系统实机验收。无需服务器、付费数据库或模型 API key。

在项目目录执行：

```sh
./scripts/setup.sh
./scripts/start.sh
```

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

数据：PostgreSQL 和 Redis 使用 Docker 命名卷；成果保存在 `.data/artifacts`。备份需要同时保存 `.env`、`.data`、PostgreSQL 数据或 SQL dump；不能只复制前端目录。
