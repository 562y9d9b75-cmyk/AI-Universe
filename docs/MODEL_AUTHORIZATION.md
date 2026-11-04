# ChatGPT Plus / Pro 计划接入

核验日期：**2026-11-04**。本次成功读取用户指定的两篇 OpenAI 官方文档（HTTP 200），以及其链接的注册、推理、账户、令牌和错误处理文档。此前“文档被环境拦截，资格待核实”的记录已被本次核验取代。

**当前成品已实现官方本地 OAuth 动态注册、PKCE、账户令牌存储/刷新、模型目录和 Responses 流式推理适配。项目所有者仍需在自己的浏览器登录并同意 ChatGPT 计划用量。没有本人授权时，不会调用模型，也不会使用付费 API。真实 Plus 推理和额度行为尚未实测通过。**

## 已核实的官方条件

| 事项 | 官方结论与本项目行为 |
| --- | --- |
| 资格 | 官方 Cookbook 明确适用于开源工具和**本地运行的个人项目**；使用者需有符合条件的 Plus 或 Pro 账户。用户账户、工作空间、服务地区及政策仍可能限制使用。MIT 源码加本地个人使用符合文档描述的集成类别，但不代表 OpenAI 已批准具体账户。 |
| 预先注册 / 密钥 | 本地开源直接流程无需提前获取 client secret 或 API key。首次使用官方公开入口 `client_id=dynamic_agent_client`；这只是动态注册入口，绝不是保存的应用 ID 或 token exchange 的 ID。 |
| 用户授权 | 用户在 OpenAI 官方页面登录、选择工作空间并授权；回调由 OpenAI 颁发应用独立 `client_id`。系统保存这个 ID，即使授权码交换过期，也会在下次复用注册。 |
| 安装标识 | 每个本地安装生成并持久化独立 `urn:uuid:…` 格式的 `ext_agent_host_id`，应用名称始终使用真实名称 `AI Universe`。不复用 Codex、开发环境或其他应用的注册身份。 |
| OAuth | Authorization Code + PKCE S256；每次独立的随机 state、nonce、verifier；回调为 `http://127.0.0.1:端口/api/model/chatgpt/callback`，不能替换成 `localhost`。 |
| 授权权限 | 请求 `openid profile email offline_access resource.invoke chatgpt.tokens.use.direct`，resource 为 `https://api.openai.com/v1`。以 token 响应实际授予权限为准；只有身份登录不允许推理。 |
| 推理 | 仅向 `POST https://api.openai.com/v1/responses` 发送本人 OAuth Bearer token。`input` 为数组、`store:false`、`stream:true`，收到 `response.completed` 才算交付完成。 |
| 额度 | Plus 五小时用量在所有使用其计划的应用之间共享，不是每个应用独享一份。额度可能来自计划或用户在 ChatGPT 中配置的可用 credits。系统不会购买 credits、开通计费、提交独立 API key 或切换付费 API。用户可在 ChatGPT 用量设置限制应用使用。 |
| 远程 / 商业用途 | 本次只交付用户本机个人版。官方 Cookbook 要求付费或远程托管产品先申请接入；不得将本地适配直接解释为可商业运营或公开部署许可。官方另有个人自托管 VM 流程，本次不转移任何用户令牌。 |

官方依据：

- [Quickstart](https://developers.openai.com/siwc/quickstart)
- [Integrating Sign in with ChatGPT in your open-source app（2026-09-28）](https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt)
- [Registration and sign-in](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
- [Models and inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference)
- [Accounts and sessions](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions)
- [Token reference](https://developers.openai.com/siwc/token-sharing-open-source/token-reference)
- [Errors and recovery](https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery)
- [Preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)
- [OIDC discovery / ID-token verification example](https://developers.openai.com/siwc/website)

官方生产配置为 issuer `https://auth.openai.com`、authorize `/api/accounts/authorize`、token `/api/accounts/oauth/token`、JWKS `/.well-known/jwks.json`。实际授权时还会读取 `https://auth.openai.com/.well-known/openid-configuration` 并检查其与文档生产配置一致，随后使用公开 JWKS 验证 ID token 签名、issuer、audience、有效期、nonce；配置若发生变化则停止连接，不绕过验证。

## 在本机完成接入

1. 正常启动 AI Universe，登录个人工作空间，进入“模型接入”。
2. 选择 **Continue with ChatGPT**。页面会说明任务将消耗本人 ChatGPT 计划额度；这一步没有 API key 输入框。
3. 在新开的 **OpenAI 官方登录页面**完成本人登录，选定工作空间，并同意允许 AI Universe 使用 ChatGPT 计划。
4. 浏览器返回本机 `127.0.0.1` 授权结果页。关闭此页，回到原工作台，刷新接入状态。
5. 刷新模型列表并选择该账户实际可用的模型。目录请求不进行推理。
6. 创建使用“ChatGPT 计划”的任务。只有收到完整模型响应后，接入页面才显示“真实推理已验证”，任务执行记录中才会写入实际 token 数、模型和 response/request ID。
7. 开始自主协作前先用一条小任务验证；随后执行至少三名员工参与的完整任务并审核成果。

首次本人 OAuth 同意无法由开发者代替。既不需要把密码、Cookie 或 token 发给开发者，也不需要安装 Docker 或购买独立 API。开发云环境里的 OAuth callback 无法抵达用户电脑，须在运行软件的本人电脑上完成；不能在云测试报告里假装已授权。

## 实现和安全边界

- `backend/app/model_auth.py` 是官方连接模块；`providers.py` 保留可扩展提供方接口。所有提供方均不读取环境中的 `OPENAI_API_KEY`、`ACCESS_TOKEN` 或开发环境凭据。
- 授权启动 API 需要现有个人工作空间身份与应用的防跨站请求头。一次性随机 state 将初始用户和组织绑定到本次授权，10 分钟有效；回调成功或失败均消费该 state。外站回跳时，即使 `SameSite=Strict` 登录 Cookie 不随请求发送，也不会丢失目标组织或信任任意回调组织参数。
- 每个组织有独立账户注册、身份与 token 记录；不同注册即使邮箱相同也不会合并。只有经过验签且匹配所选原身份的新授权才会替换连接。
- 令牌仅位于 `AIU_DATA_DIR/model-auth/` 的本机文件中，目录权限 `0700`、记录和锁权限 `0600`、原子写入；文件名以组织/尝试键的 SHA-256 派生，无法通过组织名称进行路径穿越。此目录由 `.data/` 忽略规则排除，不提交源码。
- 令牌不会返回给前端，不存浏览器 storage，不写审计/任务日志。重新授权 URL 允许向 OpenAI 发送 `id_token_hint`，因此授权响应正文不能写日志；回调页面使用禁止缓存及禁止 referrer 的响应头。
- 跨进程文件锁串行化刷新，防止多个员工抢用旋转 refresh token；刷新时同时保存新 token、有效期及权限。暂时网络错误保留原记录，确定的 refresh-token 失效清除不可用凭据并要求重新连接。
- 退出会向官方 discovery 提供的同域 revocation endpoint 撤销 refresh session，再清除本地 token 并保留独立注册。若网络失败，明确说明远程撤销未确认，可在 [ChatGPT 设置 → 用量](https://chatgpt.com/settings/usage)断开应用。
- `subscription_sharing_usage_limit_exceeded`、HTTP 429 及用量检查暂不可用映射为任务 `paused_quota`；未授权映射 `blocked_auth`。没有自动付费回退，失败任务不会伪造成功成果。恢复仍需用户明确操作。
- HTTP 流严格等待 `response.completed`；失败、incomplete、中断及部分文本都不交付文件。根据官方 preview 限制，不发送 `temperature`、`max_output_tokens`、`previous_response_id`、后台任务或不支持的工具字段。运行器自己的轮次、单日、并发及超时限制仍生效。
- 默认 `local` 提供方是确定性文本/CSV 整理与文件生成工具，明确标记未使用模型。模型连接不会悄悄改变已有任务的提供方。

## 测试证据与尚待本人完成的验收

`backend/tests/test_model_auth.py` 使用隔离目录、模拟官方 HTTP authority 和真实 RSA 签名测试，覆盖完整注册→令牌交换→OIDC/JWKS 验证→目录→Responses SSE 完成链路，还覆盖 PKCE、state 过期/复用、nonce/issuer/audience/签名错误、无计划权限、失败后保留注册、并发刷新、失效刷新、账户不符、额度与中途中断、禁止环境付费 key、组织隔离及文件权限。它证明代码契约和失败处理，不等同于本人 Plus 真实授权测试。

本次 managed cloud 已允许 `developers.openai.com`，官方文档核验成功；但对 `auth.openai.com` 的只读 discovery 探测仍被 CONNECT 代理以 403 拦截。云内未配置任何 ChatGPT token，也未进行模型调用。本人本机的软件请求使用本机网络，若在云中另做真实授权测试，应先显式开放官方 `auth.openai.com` 和 `api.openai.com` 网络访问，仍须本人 OAuth。

最终仍需在用户本机补验：本人账户资格与地区、动态注册真实回调、真实模型目录、一次真实 Responses 请求、三员工协作交接、用量达到限制后的暂停与手动恢复、退出与重新登录。状态页分别显示“实现可用 / 本人授权 / 计划权限 / 已完成真实推理”，不以代码或模拟测试冒充真实接通。
