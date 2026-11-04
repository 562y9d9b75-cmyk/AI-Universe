# 架构与数据

## 运行组件

- Next.js / TypeScript / Tailwind：同源中文管理界面、响应式布局、浅色/深色主题。
- React Three Fiber / Three.js：可交互的 GLB 总部楼层；弱设备降低像素倍率、关闭阴影；无 WebGL 时提供员工列表。
- FastAPI：个人账户、组织隔离、任务、审批、成果、记忆、调用记录。
- PostgreSQL：业务事实来源。首次迁移由 `backend/app/migrate.py` 完成，记录 `schema_migrations`，可重复运行，不重置数据。
- Redis：通知发布，故障不丢任务。页面当前用 3 秒轮询刷新。
- 独立 Python worker：轮询数据库、行锁领取任务、执行 DAG；最多 8 个线程并行调度；工具运行在独立子进程，超时强制终止。
- 本机文件存储：`.data/artifacts/<organization>/<task>/<run>/`，数据库记录版本、SHA-256、大小与可读预览。

`compose.yaml` 仅运行免费的 PostgreSQL 与 Redis，端口只绑定回环地址。Web/API 也仅绑定回环地址；未部署公网。

## 执行语义

所有新任务依赖只能指向已存在的、同组织的任务，因此依赖图不会引入后向新节点成环。员工汇报关系另外检查循环。任务至少有输入、输出格式、验收标准、工具、执行员工、预算单位和状态。

本地自主组织采用明确标注的三员工模板：材料整理与统计复核并行执行，汇总任务等待二者均完成，接收文本上下文和文件 ID。它是实际任务编排，不是三个聊天框；但它**不是模型自主规划**。模型模式在尚未授权时不创建虚构拆解。

调度时锁定组织以串行进行额度准入，再锁定任务；执行在事务外进行。消费前预留调用单位，检查单任务和协作目标总轮次、组织日额度（UTC）、组织并发、截止时间和工具权限。租约标识当前 run，旧 run 即使返回也不能覆盖新结果。

状态：`queued → running → review → completed`。失败可在上限内重试；退回增加版本，保留旧文件。暂停/取消会使在途 run 失效。进程异常后等待租约过期，任务重新入队，旧运行记为 interrupted。取消/超时后可能留下未登记的运行文件；它们不作为有效成果交付。任务预算仅允许实际费用为零的本地工具；没有可消耗付费额度的实现。

结果至少生成一个文件并通过生成器异常检查后才能进入 review/completed。文件下载重新校验 SHA-256。`criteria` 是人类审核依据；当前不会用语言模型自动断言内容质量验收成功。

## 数据表

包含 users、organizations、sessions、departments、agents、agent_skills、agent_permissions、projects、tasks、task_dependencies、task_runs、agent_messages、artifacts、memories、knowledge_items、approvals、usage_records、audit_logs、office_assets、employee_animations。业务记录均带 organization_id；组织根表以 id 自隔离。当前是单所有者安装，可建立和切换多个公司，不提供多人注册。

员工技能和权限有标准化子表，员工 JSON 字段是页面聚合数据，通过配置接口同步。公司/部门/员工/项目记忆有来源、建立时间、可信度和人工核实状态。仅人工核实且范围匹配的记忆被注入输入；不自动把模型推断存为事实。

## 扩展边界

提供方、工具执行器、文件生成器、DB 模型和办公室资产分开。添加模型必须经过官方授权核验；禁止自动付费回退。添加工具必须声明权限，并在受控子进程实现，不直接运行模型给出的 shell。当前未开放通用 shell、浏览器操作、网络搜索和任意上传代码执行。

## 当前限制

- 还没有真实模型授权与模型规划/推理。最新版官方接入条件因网络阻断尚未确认。
- 3D 是可用的建筑/家具楼层，不是最终写实人物视觉交付。人物面部、皮肤、头发、动作与混合动画尚未实现。
- 生活状态可以独立保存，UI 不伪造实际任务完成；尚没有对应完整人物动画。
- 列表默认显示最近 300 条，API 可设 limit 至 1000；尚无分页检索与归档管理。
- 只有初始版本迁移；未来调整 schema 必须新增迁移，不能修改已运行的 migration 1。
- 面向本机个人使用；未完成公网、多租户、多用户、离线安装和跨平台安装器验收。

人物接入使用本地资产清单与 `EmployeeModel` 的 GLB clips 混合播放。清单目前无人物；动画接口实现不代表已有可验收的人物资产或自然动作。一个 URI 不能重复注册多名员工，缺失时只保留管理标记。

## Docker Desktop 简易入口

`compose.desktop.yaml` 使用独立项目 `ai-universe-desktop` 运行全套服务，宿主机只需 Docker/Compose；`docker/api.Dockerfile` 安装锁定 Python 依赖，`docker/web.Dockerfile` 在 Node24 镜像中构建 Next。API 与 worker 以同一非 root UID 共享成果卷；网页以 node 用户运行。只绑定本机网页端口，数据库与 API 没有宿主机端口。宿主机开发模式的数据不自动迁移到容器版，两个项目分别保留自己的命名卷。

镜像构建可选挂载 `proxy_ca` BuildKit secret，以支持受管环境中的可信代理；不携带会话 CA 到镜像层，也不关闭 TLS 校验。普通 Mac Docker Desktop 无需提供这个构建 secret。`.dockerignore` 排除 .env、私有数据、依赖和日志。


## 免 Docker 个人模式

入口 scripts/start-local.sh。固定 SHA256 的便携 Python/Node 安装到用户数据目录，再准备私有 venv 和可复用的前端构建；不覆盖项目 .env 或其他部署数据。SQLite 使用 WAL、外键校验、30秒忙等待；事务用 BEGIN IMMEDIATE 在读取调度/控制状态前取得写入资格，替代 SQLite 不支持的 FOR UPDATE。系统 flock 限制每个 SQLite 数据库只有一个 worker；多个工具任务仍在独立子进程执行。Redis URL 为空时关闭 Redis 通知，页面仍轮询业务事实。PostgreSQL 路径保持原有行锁行为。

单独 Python 监督器管理自己启动的 API、worker、Next 子进程组，提供互斥启动、端口检查、数据库健康检查、失败日志和安全停止。数据保存在用户固定目录，源码更新不重置账户或成果。SQLite 个人模式不是原 PostgreSQL 架构的完整验收替代；完整部署仍可选 Docker/原生服务。真实模型与写实人物的未完成状态不变。
