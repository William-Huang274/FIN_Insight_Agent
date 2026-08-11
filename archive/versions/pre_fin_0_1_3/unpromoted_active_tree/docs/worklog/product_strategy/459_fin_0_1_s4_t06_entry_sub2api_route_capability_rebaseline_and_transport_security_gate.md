# 459｜FIN 0.1 S4-T06 入口 Sub2API 路由/能力重建与传输安全门禁

日期：2026-07-28

## 结论

用户提供的 Codex 兼容模式连接示例明确给出：

- base URL：`http://43.135.174.27:8080`，不带 `/v1`；
- wire API：`responses`；
- authentication：`requires_openai_auth = true`；
- model/review model alias：`gpt-5.5`。

对 FIN Insight runner 而言，候选请求路径应是 base URL 加 `/responses`，不能沿用官方 OpenAI 的 `/v1` base，也不能继续使用先前冻结的 `gpt-5.6-sol`。Provider label `OpenAI` 只表示 OpenAI-compatible 配置槽，不证明请求由官方 OpenAI 提供。

## 安全门禁

当前示例使用非 loopback 公网 IP 上的明文 HTTP，同时要求认证。如果直接请求，API credential 的传输机密性没有建立。项目不得把现有官方 `OPENAI_API_KEY` 或任何 Sub2API key 发到该地址。

只有以下任一边界被确认后，才允许继续：

1. 服务端提供有效 TLS 的 HTTPS base URL；或
2. 使用加密隧道，并把项目连接地址冻结为本地 loopback endpoint。

未来项目侧 credential 必须使用独立 `SUB2API_API_KEY` 绑定，禁止复用官方 `OPENAI_API_KEY`，防止 Provider credential 串线。

## 能力边界

截图只说明运营配置宣称支持 Responses wire 和 `gpt-5.5` alias，尚未证明：

- `/responses` 实际可达或认证成功；
- `/models` 或 `/chat/completions` 是否存在；
- `gpt-5.5` 映射到哪个真实上游模型；
- strict JSON Schema、reasoning effort、response storage 语义是否被完整透传；
- rate、quota、cost 或研究质量。

本轮 model/provider/network call 为 `0/0/0`，未读取或写入 credential，也未修改 runner。

## 状态

- RC-P36-073：路由来源已绑定，但 runner/authority 尚未实现，等待安全传输边界；
- RC-P36-074：新增外部 authenticated plain-HTTP transport blocker；
- RC-P36-070：等待 Sub2API `gpt-5.5 /responses` 和 strict-schema 的后续 live proof；
- S4-T06 未进入，MU、S5、release、production 继续 blocked；
- DELL R12 继续禁止。

下一项为：

`S4-T06-ENTRY-SUB2API-SECURE-TRANSPORT-ENDPOINT-CONFIRMATION`

该项需要用户提供 HTTPS base URL，或提供/确认通过加密隧道暴露的本地 loopback base URL。本次不接受把 bearer-style credential 直接发往当前公网 HTTP 地址。

## Git

工作树仍有大量历史 mixed staged/unstaged/untracked 变更。本轮仅追加零调用合同、账本和验证，不清理、不 stage、不 commit。

## 验证

- 全部 S4-T06 contract tests：`77 passed`；
- Project OS 精确 scope 预检：待安全 endpoint confirmation 范围通过；
- JSON/JSONL 重复键、Python syntax、敏感凭据模式与 scoped diff 检查通过；
- 实际 model/provider/network call：`0/0/0`。
