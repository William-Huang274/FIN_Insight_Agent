# 458｜FIN 0.1 S4-T06 入口 Sub2API 路由更正与 HTTP 429 重分类

日期：2026-07-28

## 结论

用户澄清：目标并非 OpenAI 官方 API，而是自建 Sub2API。

零调用审计确认，先前 credential metadata probe、fresh canary authority、runner 和 HTTP 429 result 全部绑定：

`https://api.openai.com/v1`

本地 `.env` 与进程环境均未配置 `OPENAI_BASE_URL`、`BASE_URL`、`OPENAI_API_BASE`、`API_BASE_URL` 或 `SUB2API_BASE_URL`。runner 也没有从环境读取目标地址，而是硬编码官方 OpenAI base URL。

因此：

- 历史 HTTP 429 仍是一次真实的官方 OpenAI 请求结果，但它打到了错误的 Provider 路由；
- 该 429 不能用于判断自建 Sub2API 的 rate limit、quota、上游渠道、模型映射、Responses 支持或 strict-schema 能力；
- 先前计划检查 OpenAI Platform billing/usage/limits 的方向被撤销；
- 当前最早故障改为项目内 Provider route authority mismatch，而不是外部 OpenAI 配额阻断。

## 证据边界

- metadata probe 只证明官方 OpenAI Key 能访问官方 `gpt-5.6-sol` metadata；
- HTTP 429 只属于官方 `api.openai.com` 请求；
- 自建 Sub2API 从未被当前 authority、probe 或 canary 联系；
- 本轮 model/provider/network call 为 `0/0/0`；
- 未读取、输出、替换或写入任何凭据；
- 未检查或修改任何官方或 Sub2API billing/limit 配置。

## Root cause 迁移

- RC-P36-072：保留为官方 endpoint 历史事实，但不再是目标 Sub2API 路径的当前 blocker；
- RC-P36-073：新增项目内 blocker，表示 authority/runner 错把官方 OpenAI 冻结为目标，而自建 Sub2API base URL、API dialect、模型映射和 capability contract 均未绑定；
- RC-P36-070：OpenAI-specific request proof 不能直接外推到 Sub2API，等待 Provider target/capability rebaseline；
- RC-P36-071：只在官方 OpenAI credential scope 内保持 closed，不是 Sub2API 认证证据。

## 下一项

`S4-T06-ENTRY-SUB2API-PROVIDER-ROUTE-AND-CAPABILITY-CONTRACT-REBASELINE-DECISION`

该步骤仍为零调用，需要用户提供或确认非敏感的 Sub2API base URL，并冻结：

1. Provider identity 与 OpenAI-compatible API dialect；
2. `/models`、`/responses`、`/chat/completions` 的实际支持边界；
3. `gpt-5.6-sol` 在 Sub2API 中的模型别名或上游映射；
4. structured output / strict JSON Schema 是否由 Sub2API 和上游共同支持；
5. credential env binding 与安全边界。

在这些事实冻结前，不签发新 probe/canary，不重放历史 canary，不修改 runtime/schema，也不进入 MU T06。

## Git

工作树已有大量 mixed staged/unstaged/untracked 历史变更。本轮只追加路由更正、状态迁移与合同验证，不清理、不 stage、不 commit；`.env` 保持 ignored/untracked。

## 验证

- 全部 S4-T06 contract tests：`72 passed`；
- 历史 official OpenAI probe/canary 文件保持不可变；
- 新状态只授权未来的零调用 Sub2API route/capability rebaseline，不授权任何 Provider request。
