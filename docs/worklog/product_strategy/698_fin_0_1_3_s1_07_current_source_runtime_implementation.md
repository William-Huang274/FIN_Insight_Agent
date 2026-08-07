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

## 5. R1 exact-once canary 与处置

实现 commit `15d0430a` clean/synced 后执行 R1。三条 admission calls 与三条 network-attempt count 均准确，0 retry；三案均在 HTTP 前返回 `official_source_private_network_forbidden`，request/failure capture 全部存在、worker close no orphan。只读 DNS 诊断显示：

- DELL=`198.18.1.52`；
- MU=`198.18.1.53`；
- NVDA=`198.18.1.54`。

三个地址都属于 RFC 2544 benchmark network `198.18.0.0/15`，是当前 Codex 网络的 synthetic DNS 映射。因此 R1 是 guard environment-compatibility false positive，不证明来源不可用或 parser 不工作。

处置保持有界：普通 runtime 仍拒绝所有 non-global destinations；只有 canary runner 确认所有显式 allowlist hostname 均解析到 `198.18/15` 时，才通过受控环境标志允许该 synthetic transit，HTTPS hostname/certificate 校验不变。新增 default-reject / explicit-mode-allow mutation，broader=`83 passed`。R1 结果保存为 `configs/releases/fin_ia_0_1_3_s1_07_current_source_canary_result_v1_0.json`；修复提交后只允许 new admission 的 R2 v1.1。

## 6. R2 live partial 与最终有界 fallback

修复 commit `f576ac48` clean/synced 后执行 R2 v1.1，仍为 3 calls/0 retry：

- MU：official investor PDF fetch 成功，raw response capture 约 `5.7 MB`，PDF text parse、parser lineage、promotion receipt 均成功；
- NVDA：official IR HTML fetch 成功，raw response capture 约 `618 KB`，HTML text parse、parser lineage、promotion receipt 均成功；
- DELL：official IR PDF 在约 `31.1 s` 返回 `official_source_transport_failed`，request 与 failure capture 完整，无 parser/promotion；
- shared worker clean close、no orphan。

R2 证明 runtime 主体真实可用，也证明单一 source route 可能超时。当前不把 timeout 提高成通用补丁，不重跑成功的 MU/NVDA。最后一个有界动作是 new admission/1 call 的 Dell SEC official 10-K HTML fallback；它复用 immutable R2 的两条成功结果。若 fallback 仍失败，S1-07 停止，不进入 R4。
