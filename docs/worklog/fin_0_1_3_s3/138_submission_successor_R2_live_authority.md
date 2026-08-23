# FIN 0.1.3 S3 submission successor R2 live authority

时间：2026-08-23

状态：`signed / exact_once / not_executed`

## 决策

基于 clean commit `f3f4c73d2d975cb32730dc74187c0692f8f824fd` 和 fresh zero-call result `80977102...9fe15`，签发一次新的 capture-bound submission successor authority：

`configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_submission_successor_live_authority_v1_1.json`

authority SHA-256：`ce62f7e0faf03d29fb792ce6a5d4490a55e97558376c419d5b364fc82ec093ad`。

## 有界范围

- 最多 25 次新模型／传输调用，按真实节点拓扑相加，不是成本优先的任意上限；
- 只允许 1 个新 S1/S2 request 和 1 个 retrieval round，即 Supply 的未覆盖关系请求；
- 其余六角色研究状态和八份 draft 均从 R1 immutable captures 恢复；
- 最多 2 个 Lead round、3 个角色内 repair；0 retry、fallback、外源网络、Candidate promotion 或产品指针修改；
- 禁止 Harness 代写金融判断、Writer、发布、S3 acceptance 或泛化声明。

九类模型节点均带独立 `TokenBudgetBasis`，依据任务目的、输入规模、产出、schema 负担、研究质量风险、历史运行证据、reasoning profile 和截断行为设定。任何失败都会消费 R2 identity，并作为新 terminal evidence 保留。
