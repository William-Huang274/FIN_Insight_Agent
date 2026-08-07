# FIN 0.1.3 S1-07 current-source runtime implementation

日期：2026-08-07

状态：`engineering_pass_clean_exact_once_canary_pending`

## 1. 最早根因

当前 MCP `web_evidence_snapshot` 的合同写着“fetch”，但 handler 只把传入 URL 包装为 `context_only` metadata，没有真实 HTTP、原始 response、redirect、PDF/HTML parser 或 Evidence promotion。与此同时，S1-03 已有 capture-first client、HTTPS allowlist transport、HTML/PDF/JSON parser、content-addressed object store 和 exact-once admission；问题是能力没有接到产品工具面，而不是仓库完全没有底层实现。

## 2. 有界实现

- 复用并扩展 `official_source_attempt_program.py`：public-network/SSRF guard、3-hop redirect ceiling、可配置 capture namespace。
- 新增 `web_evidence_runtime.py`：真实 fetch、request/response capture、parser capture、promotion receipt 和 typed gap。
- 公司官网/IR 必须 verified company domain；监管/政府允许 parsed Evidence；news/commerce/developer/social 仅 context-only。
- 所有 web rows 均 `exact_value_authority=false`；精确数字仍归 Numeric/SEC Ledger 或专职结构化 parser。
- MCP server/contract/profile 新增 capture root、fetch timeout、byte/excerpt budgets；默认 capture 位于 ignored `.codex_runtime`。
- 新增一次性三案官方来源 canary runner，使用共享 admission ledger、3 network calls、0 retry、0 model/provider。

## 3. 验证

- focused=`23 passed`；
- S1-03 compatibility + MCP + web/operator broader=`82 passed`；
- 覆盖 HTML/JSON、redirect lineage、trusted promotion、news non-promotion、unverified/cross-domain pre-fetch rejection、parser failure capture retention、timeout/cancel/no-orphan；
- compileall 与 diff check 通过；
- 当前真实网络、模型、Provider=`0/0/0`。

## 4. 边界与下一步

当前只到 engineering pass。提交并推送 clean commit 后，执行一次 DELL/MU/NVDA 官方来源 exact-once canary。只有三案均完成真实 fetch、raw capture、parse 和受控 Evidence promotion，S1-07 才可 `L4_scope_pass`；任一路失败保留 capture/typed gap 并继续归属 S1-07。即使通过，也不证明 S1-08 recall/ranking/diversity、DeepSeek 研究质量或 release。
