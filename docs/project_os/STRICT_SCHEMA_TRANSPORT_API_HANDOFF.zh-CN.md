# ⚠ Strict-Schema Transport API Handoff

状态：**已停放，不阻断 DeepSeek 主线**

更新时间：2026-07-29

这是 FIN Insight 后续拿到新 API 时恢复 strict-schema transport 资格判断的唯一醒目入口。不要从历史聊天猜配置，也不要复用已经消费的 canary identity。

## 当前主线与停放边界

- S4/T06 主线 Provider：`deepseek`
- 主线模型：`deepseek-v4-pro`（Pro，不是 Flash）
- 主线 HTTPS base URL：`https://api.deepseek.com/beta`
- 主线 credential env：`DEEPSEEK_API_KEY`
- 主线可靠性合同：模型输出 typed judgment atoms；本地拥有 material number、period、unit、sign、entity/title、ID、ordering、lineage、确定性渲染和 L1 fail-closed 校验。
- strict server-side JSON Schema：属于可选 Provider transport 增强；未证明前不得成为 release capability claim，但也不再阻断 DeepSeek 上的 MU T06。

## 已知 strict-schema transport 结果

1. Official OpenAI canary 曾在 generation 前得到 HTTP 401；后续 credential metadata probe 成功，但 fresh canary 又在 generation 前得到 HTTP 429。两次都没有评价 schema 或模型行为。
2. 用户随后澄清目标是自建 Sub2API，不是 official OpenAI。
3. Sub2API exact-once public diagnostic 请求：
   - URL：`http://43.135.174.27:8080/responses`
   - model alias：`gpt-5.5`
   - 结果：HTTP 401，`321 ms`
   - tokens：`0/0/0`
   - retry/provider hopping/repair：`0/0/0`
   - generation、strict parse、本地 validator：均未到达
4. 结论：现有截图不是完整 standalone raw-client access contract；不能判断模型是否支持 strict schema，也不能把 401 归因于模型不遵循指令。

关键证据：

- `configs/releases/fin_ia_0_1_s4_t06_entry_sub2api_public_nonsensitive_diagnostic_canary_exact_once_execution_result_v1_0.json`
- `docs/worklog/product_strategy/463_fin_0_1_s4_t06_entry_sub2api_public_diagnostic_http401_terminal_result.md`
- RC-P36-070、RC-P36-073、RC-P36-074、RC-P36-075

## 新 API 到手时请提供

只需要把下面信息发给 Codex；真实密钥不要写进仓库文档或普通聊天：

1. Provider/运营方名称与联系人或文档入口。
2. 完整 HTTPS base URL，以及 exact endpoint path。
3. 一份可在独立终端运行的 standalone raw HTTP/curl 示例；secret 用占位符表示。
4. 所有必需 headers，以及每个 header 是固定非敏感 marker、session、Bearer/API key，还是其他授权材料。
5. 是否需要客户端注册、IP allowlist、账户会话、特定 User-Agent 或额外签名。
6. wire API：Responses、Chat Completions、tool/function calling 或其他。
7. 精确 model alias；是否支持目标模型、版本是否固定。
8. strict JSON Schema 的支持方式、支持子集、已知限制和官方示例。
9. rate limit、quota、计费和最大输入/输出限制。
10. 一条完全合成、无业务数据的预期成功响应示例。

推荐向 Provider 直接发送：

> 请提供一份不依赖 Codex Desktop/CLI 登录态、可在全新终端直接运行的 standalone curl 示例，包含完整 HTTPS URL、endpoint、model、全部 headers、认证方式与成功响应；请说明是否需要 client registration、session、IP allowlist，以及 Responses/Chat 接口对 strict JSON Schema 的支持范围。请将 secret 写成占位符，不要发送真实密钥。

## 恢复流程

收到完整资料后，固定按以下顺序恢复：

1. 零调用 route/auth/schema contract rebaseline。
2. secret-safe credential presence/metadata 资格判断。
3. 新 identity、完全合成、exact-once、no-retry single-node canary。
4. 只有 generation、strict parse 和本地 semantic validator 全部通过，才记录 transport capability。
5. Provider 兼容性通过后，也不得替代本地 L1 authority validation。

禁止：

- 复用已消费的 Sub2API diagnostic identity；
- 猜 header、轮换 key、自动 Provider hopping；
- 在 plain HTTP 上传业务、金融或 credential 数据；
- 把 transport schema conformance 当作金融语义正确；
- 因新 API 到手而改写既有 DeepSeek Run 的历史事实。

恢复口令可以直接说：

> 我拿到新的 API 了，按 strict-schema handoff 恢复资格判断。
