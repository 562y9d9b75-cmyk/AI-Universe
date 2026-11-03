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
