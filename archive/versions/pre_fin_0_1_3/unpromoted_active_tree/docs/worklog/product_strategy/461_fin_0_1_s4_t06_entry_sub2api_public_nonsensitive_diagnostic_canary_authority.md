# 461｜FIN 0.1 S4-T06 入口 Sub2API public/non-sensitive diagnostic canary authority

日期：2026-07-29

## 决策

用户以“同意”授权一条 diagnostic-only canary。本轮只签发 authority，不实现 runner，也不发起 HTTP、模型或 Provider 请求。

未来 canary 精确绑定：

- self-hosted Sub2API `http://43.135.174.27:8080/responses`，不添加 `/v1`；
- Responses wire，model alias=`gpt-5.5`；
- `requires_openai_auth=false`，不读取、检查、发送或写入任何 OpenAI/Sub2API key；
- 使用运营界面给出的固定 `x-openai-actor-authorization` client marker；它按连接合同分类为非 API credential，禁止 raw-header logging 和 result persistence；
- 仅发送一条完全合成、无公司、无金融数据、无私密信息的三枚举 strict JSON Schema 请求；
- 最多 1 semantic/provider/network/transport request，output token ceiling=128，retry=0；
- 0 source/tool/chat-completions、0 WorkUnit/Attempt/Run/Artifact/Case write。

## 风险和验收边界

当前 endpoint 是公网 plain HTTP。诊断输入虽不敏感，但连接仍没有 TLS payload confidentiality、server identity authentication 或 response integrity。

因此成功只证明这条 route、alias、Responses wire 与 exact strict-schema request 在一次请求上兼容；不能关闭 RC-P36-074，不能作为 T06 主线 capability/acceptance 证据，也不能放行 MU、full chain、DELL R12、S5、release 或 production。

失败时首个可信 route/HTTP/schema/envelope/parse/value/budget 错误立即 terminal stop；不 retry、不 provider hopping、不自动 repair、不继续 full chain。结果只允许持久化脱敏状态、HTTP/failure class、digest、usage/latency 和 content-free validation shape，禁止 raw output、headers、marker value、stack、私有 reasoning 或业务内容。

## 当前计数与下一项

本轮 model/provider/network/source/tool/credential=`0/0/0/0/0/0`，diagnostic execution=`0`，runner/runtime change=`0`。

下一项已授权但未开始：

`S4-T06-ENTRY-SUB2API-PUBLIC-NON-SENSITIVE-DIAGNOSTIC-CANARY-MINIMUM-ZERO-CALL-IMPLEMENTATION-AND-PREFLIGHT`

该下一项仍必须是零调用：创建隔离 runner、冻结 request/schema digests，并通过 fake transport、严格解析、脱敏结果与 exact-once preflight；不能提前发真实请求。

## 验证

- 全部 S4-T06 contract tests：`86 passed`；
- Project OS 对下一项精确 scope 的 fail-closed preflight：`pass`，open blocker=`0`；
- authority result ref 在签发时不存在；
- JSON/JSONL、Python syntax、敏感凭据模式与 scoped diff 检查通过；
- model/provider/network call=`0/0/0`。

## Git

工作树继续保持历史 mixed state；不清理、不 stage、不 commit。
