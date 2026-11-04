# 实际测试报告

日期：2026-11-03。执行环境：Linux x86_64，Node.js 24.22.1、Python 3.12.14、Docker 29.9.2、Blender 4.3.2。Next.js 16.4.4，PostgreSQL 17 Alpine，Redis 7 Alpine。此报告不表示已经在所有者的个人电脑或新发布云快照中复验。

## 已执行

| 检查 | 结果 | 方式 |
| --- | --- | --- |
| 冻结依赖安装 | 通过 | uv sync requirements.txt、npm ci；完整 setup.sh 实际执行 |
| 统一启动与重启 | 通过 | 直接运行交付 start.sh 两次，停止后重启，所有者库保持未初始化 |
| PostgreSQL/Redis 就绪 | 通过 | Compose health checks；真实 SQL 迁移与 API 请求 |
| 重复迁移 | 通过 | migration 1 可重复执行，不重置数据 |
| Next 生产构建与 TypeScript | 通过 | next build --webpack（含类型检查） |
| 后端集成回归 | 9 项通过，0跳过 | 真实 FastAPI 路由、SQL状态、调度器、工具子进程与文件；独立 SQLite 测试库 |
| 浏览器 E2E | 通过的完整运行记录见 evidence/playwright-results.json | 使用真实 PostgreSQL、独立 API/worker/Next 进程与系统 Chromium，不是 TestClient 代替浏览器 |
| 实际工作进程异常恢复 | 见 evidence/process-recovery.json | 对执行中的 worker 进程组 SIGKILL 后重启，等租约过期并验证重交付 |
| 前端依赖审计 | 全部依赖0项已知漏洞 | npm audit；具体锁版本见 package-lock.json |
| 3D GLB | 通过 | 校验 glTF 文件头、浏览器 GLB 加载及 WebGL2 上下文，实际截图 |
| 桌面/手机/平板 | 通过指定视口 | 1440×1000、390×844、820×1180；页面无横向溢出，真实浏览器操作 |

后端覆盖：登录初始化、部门/员工/项目、循环汇报拒绝、工具权限、两员工并行与最终依赖、上下文与文件交接、8类文件容器有效性、退回版本、重复审批拒绝、授权暂停、日额度/单任务限额、旧运行 fencing、租约恢复、记忆注入与删除、跨组织拒绝、CSRF/来源/字段保护、工具子进程硬超时、并发上限、父任务暂停级联与恢复。

E2E 操作：浏览器创建所有者、部门、Iris员工、项目、人工核实记忆、三员工任务；等待真实后台交付；退回修改后审批第二版；下载8种格式，检查 PDF 与 Office/ZIP 文件头；预览成果；检查授权和预算暂停；查看模型状态；实际渲染3D并反复切换；手机与深色模式；验证切换公司后不能读旧公司任务。

## 发现并修复

- 创建任务时遗漏 organization_id：集成测试发现，已修复并回归。
- Next 15 依赖的 PostCSS 漏洞：升级审计建议的 Next 16.4.4，复审为0。
- 当前沙箱限制本机 IPC：构建切换受支持的 Webpack 模式，并在允许本机运行通信的执行上下文测试。
- 浏览器初次测试的导航选择器未计入3D标记：修正测试选择器。
- 3D Html 标签卸载时发生 removeChild 页面错误：改为普通 DOM 坐标投影，重复切换复测；保留页面错误断言，没有忽略异常。
- 快速重启时端口预检查误判 TIME_WAIT 为监听占用：使用与服务器一致的 SO_REUSEADDR 检查，复验启动/停止/重启。
- 楼层有过多独立静态网格：合并到20个材质批次，保留模块化源 blend。

## 尚未执行 / 不能声称通过

- 真实 ChatGPT Plan Usage、OAuth/PKCE、Responses 请求、真实模型额度用尽及模型协作：未授权，未调用，无法验收。
- 写实人物的面部/皮肤/头发/衣服与自然生活动画：没有对应资产，未验收。
- Office 原生排版浏览器渲染、真实模型编写任意软件：未实现。
- macOS/Windows实机、Safari/Firefox、低端真实手机、公网、多用户与长期压力测试：未执行。
- 渗透测试和全面安全审计：未执行；现有安全检查不构成无漏洞保证。

测试结果文件与截图存于 `docs/evidence`。端到端测试只清理自己建立的临时数据库与进程，没有修改所有者业务库。测试警告：当前 Starlette 对 TestClient 的 httpx 兼容层发出弃用警告；9项测试仍完整执行，无跳过。

## Mac 启动问题修复与 Docker-only 交付

用户实际反馈：Mac 没有安装 Python、Node.js、npm 和 Docker；旧 setup.sh 的 `command -v` 遇到缺失即退出，没有解释原因。该反馈不是应用已启动的证据。

修复：新增明确环境检查、版本检查与 Docker 引擎就绪提示；原生启动器移除 Mac Bash 3.2 不支持的 `wait -n`。新增 `启动 AI Universe.command` 和 `scripts/start-docker.sh`，只要求安装并打开 Docker Desktop。Python、Node、PostgreSQL、Redis、API、worker 和 Next 全部在容器运行。没有自动安装系统软件或修改系统安全设置。

验证：

- Bash 5.2 与真正 Bash 3.2.57 容器中，7项启动契约通过：缺失依赖说明、过旧Python、Docker停止、正常预检、子服务退出码/清理/保留配置、无宿主机Python/Node/npm的Docker-only入口，以及缺Docker提示。
- 通过实际 Docker 构建全部镜像，并启动 PostgreSQL、Redis、API、worker、网页；就绪检查通过。
- 实际浏览器访问容器中的完整软件，原有整套 E2E 通过，结果与截图位于 `docs/evidence/docker-desktop`。
- Docker-only 实际交付脚本的启动/停止结果见 `docs/evidence/docker-entrypoint.json`。
- 首次容器测试发现非 root 用户不能读取宿主机权限为600的源码；修复镜像源码读取权限后复测通过，没有改用 root 运行。

以上为 Linux 中的完整容器与 Bash 3.2 兼容验证，不等同已在用户 Mac 实机验收。用户仍需完成 Docker Desktop 的本机安装并打开引擎；真实 ChatGPT 授权和写实人物仍按原验收清单标为未完成。

## 2026-11-04：环境恢复后的免 Docker 版重新验证

云工作区恢复后只保留已上传的4ec6a6c版本，因此根据恢复记录重建代码，并重新执行验证；没有将之前丢失的测试文件当成这次通过的证据。

- 10项后端测试通过，包含 SQLite 跨进程 worker 互斥锁、串行准入、预算、审批、交接和恢复，0跳过。
- 从固定 SHA256 的上游下载便携 CPython3.12.16 和 Node24.22.2，实际创建私有 venv、安装本地依赖和 npm、构建 Next，并启动独立 SQLite API、worker、网页；测试目录含空格。
- 真浏览器完整业务流程通过：三员工、两版交付、8种文件、审核退回、记忆、授权/预算暂停、组织隔离、3D、手机布局和主题切换。
- 强杀 worker 进程组后监督器停止本次其他服务；重新启动后自动恢复中断任务，保留 interrupted/succeeded 历史并重新交付5个文件。
- 实际下载并校验 Intel Mac Python/Node，检查 Mach-O CPU 与最低系统标记：Python10.15、Node13.5，适合用户报告的13.7.8。
- Next SWC、Tailwind oxide、LightningCSS、Sharp及libvips的锁定Intel包均验证 npm SHA512，Mach-O最低系统标记全部不高于13.7.8。
- 下载本地锁定依赖的32个 macOS13 Intel / CPython3.12预编译wheel，全部成功，无编译工具依赖。
- 便携引导脚本校验平台选择、缓存复用、坏校验值拒绝和空格路径/原子解压，5项通过；Bash3.2结果另见对应证据文件。

新证据存放 docs/evidence/local-mode；完整执行在隔离 Linux 环境，二进制兼容静态检查不等同 Mac 实机运行，用户实机仍需最后确认。免 Docker 本地版使用 SQLite/页面轮询，不要求 PostgreSQL或Redis。原标准部署保留；真实模型授权、模型自主规划、写实人物和完整生活动画仍未完成。
