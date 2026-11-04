# 免 Docker 个人本地版

用户设备：Intel x86_64、macOS13.7.8。启动命令：在本项目目录运行 `bash scripts/start-local.sh`。

自动下载并校验便携 CPython3.12.16（Astral python-build-standalone release20261026）与官方 Node24.22.2；版本与固定 SHA256 在 scripts/runtime-versions.sh。校验不匹配即停止，不禁用 TLS。不需要 Docker、Homebrew、管理员权限或系统预装 Python/Node。首次安装需要能访问 GitHub 发布资产、nodejs.org、PyPI 和 npm。

数据、私有运行时、日志放在 `~/Library/Application Support/AI Universe/local/`；Linux 放在用户数据目录。源码重新下载不清空该目录。不读取/覆盖项目 .env；原有 PostgreSQL/Docker 部署保留，但数据不会自动迁移。

本模式使用 SQLite WAL，事务在读取调度/控制状态前执行 BEGIN IMMEDIATE，单 worker 使用系统文件锁防止重复启动；任务在独立子进程执行。通知使用页面轮询，不需要 Redis。公司、员工、记忆、任务、审批、文件版本与预算规则共用原有后端。

校验清单：
- https://nodejs.org/dist/v24.22.2/SHASUMS256.txt
- https://github.com/astral-sh/python-build-standalone/releases/download/20261026/SHA256SUMS

Node Intel 二进制最低 macOS13.5；便携 Python 最低 macOS10.15（由实际 Mach-O 标记核对）。Next SWC、Tailwind oxide、LightningCSS、Sharp 原生模块也按 package-lock 的 SHA512 与 Mach-O 标记核对。证据位于 docs/evidence/local-mode。静态兼容检查不等于在用户 Mac 实机执行；完整运行在独立 Linux 环境测试，实机需用户最后确认。

运行时由上游提供，保留其发行文件与许可证；下载的运行时、依赖、数据库和用户凭据不提交到 GitHub。本模式不启用付费模型；真实 ChatGPT 授权、AI 自主规划、写实人物和完整生活动画仍未完成。
