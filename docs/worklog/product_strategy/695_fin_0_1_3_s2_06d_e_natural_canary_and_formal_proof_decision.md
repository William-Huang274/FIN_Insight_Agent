# FIN 0.1.3 S2-06D/E 最小自然 canary 与正式证明决定

日期：2026-08-07

状态：`natural_canary_failed_formal_DELL_proof_not_authorized`

## 1. Canary 实际表现

在 clean/synced `499e933f` 上签发并 exact-once 消费一个 DELL/U3 admission。DeepSeek v4 Pro 完成 `1 call / 1 capture / stop / 4,483 tokens / 0 retry`，返回合法 corrected-node envelope，也正确使用了 numeric alias placeholder。

但它在 `counterevidence_ids=[]` 的同时把支持供应约束的 `DELL_E04/E08` 当成反证依据，并把 correction resolution 声明为 `closed`。本地 closure validator 在 `s2_06_counterevidence_objective_not_closed` 终止。原始请求/输出已 capture-first 保存；candidate、报告、score、promotion 均为 0。

输出中还存在未走到的后续问题：`what_would_change` 继续自由写百分比阈值。由于第一可信失败已足以否定自然遵循，本轮没有继续逐项 live 修补。

## 2. S2-06E 决定

当前不值得也不授权正式 DELL 八调用监督证明。原因不是 Harness 又坏了，而是最便宜的一节点 canary 已证明：模型能形式上遵循 envelope，却没有语义上理解“反证非空或 typed unresolved”的 closure 规则。直接跑完整链只会放大费用并产生同类失败。

S2 的确定性工程修复保留为通过：它准确拦截了错误且完整留存。模型自然 correction adherence 记为失败，不用它反向否定新 guard。

## 3. 流转

- 按冻结顺序，立即工作转到 S1 检索工具可靠性和外部来源 Runtime。
- “自由 correction closure”重构流转到 S3 动态研究/内容质量：优先改成 evidence-role-aware selection 或更小的 typed judgment atom，而不是继续扩大 Prompt。
- 未来若要正式 DELL proof，必须先在新合同下通过另一次最小自然节点 canary；不得自动 R3、MU/NVDA 或 full graph。
