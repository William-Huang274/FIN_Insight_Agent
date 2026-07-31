# FIN 0.1 S2-T05 exact Agent-vs-fallback 技术比较

日期：2026-07-21
状态：`technical_comparison_pass_owner_product_review_pending`

## 问题与边界

用户授权继续 S2-T05。任务要求比较同一 exact evaluation input 下的 Agent 与 deterministic fallback，并取得 owner product review；禁止重跑已消费的 T03 Agent admission，也不得进入 S3、release 或 production。Codex 可以独立复核产品价值，但不能代替用户签署 owner acceptance。

独立核验发现：T03 `agent_fallback_comparison` Artifact 嵌入了 deterministic baseline，并写有 `runs_must_be_distinct=true`，但 isolated live store 实际只有一个逻辑 Agent ResearchRun。T02 测试证明双 Run 能工作，却不能充当 T03 live paired evidence。最早 owned root cause 是 comparison contract 把“必须不同”写成布尔声明，却没有区分“等待 baseline Run”和“已绑定 baseline Run”。

## 根因修复与执行

- 未来 bounded Agent comparison 新增 `comparison_status=pending_distinct_deterministic_run`、`agent_research_run_id` 和空 `deterministic_research_run_id`，不再暗示 paired Run 已物化；
- 新增 `run_fin_ia_0_1_s2_t05_exact_agent_fallback_review.py`，只有在同 Case/CaseVersion/as-of/input digest、不同 ResearchRun、embedded baseline 可由 canonical deterministic Artifact 重建、Agent Artifact identity/content digest 不变时通过；
- 在 T03 同一 isolated evaluation store 中执行一次 `p36_local_deterministic:v1`，创建 Run `research_run_fin01_7fa8f05bf3864a6673fee088`、Attempt `attempt_fin01_9d8dee57ef29fa1acf14fc28` 和 Artifact `artifact_fin01_a31db6c15dd3f6b84071b115:v1`；
- Agent Run 保持 `research_run_fin01_9c03f2ff9b221e7c8a42c121`，九个 ArtifactVersion 与摘要全部不变；Agent admission 没有重跑；
- deterministic model/provider/network/external tool=`0/0/0/0`，live business Case head write=0。第二次幂等复演 `created_in_this_execution=false`，总量稳定为 2 WorkUnit、2 Attempt、2 ResearchRun、10 Artifact；Gateway 仍为原 Agent 的 8 条 start/finish 事件。

## 独立产品复核

九维比较中，直接回答与同一组三条 local official candidates 的证据权威持平；Agent 没有新增来源、支持性 numeric bridge 或长期需求持续性证明。实质改善集中在：

- 将容量/能源、供应约束、一次性建设与长期趋势拆成可复核机制；
- 三条 evidence-bounded finding 和更显式 counter-thesis；
- remaining gaps 从 1 条扩为 3 条，WWC 从 1 条扩为 3 条；
- 报告从 1 个 baseline section 变为 3 sections + 3 limitations；
- 以九个 exact ArtifactVersion manifest 提高 Workpaper/Report 重建和 review 可追溯性。

因此 Codex 独立 disposition 为 `material_gain_candidate`，且只限于 reasoning/boundary/WWC/reviewability，不代表新事实或更强数值结论。是否把这类可审性提升认定为 S2 的 material value，必须由用户 owner 明确接受或拒绝。

## 验证与状态

- focused T04+T05：`9 passed in 2.62s`；
- focused T05：`3 passed in 1.80s`；
- Gateway + S2-T01/T02/T03/T04/T05 + Project OS：`106 passed in 63.36s`；
- 结果合同：`configs/releases/fin_ia_0_1_s2_t05_exact_agent_fallback_review_v1_0.json`。

S2-T05 技术比较通过，owner product review 仍为 `awaiting_user_owner_decision`。在 owner 决策写入前，S2-T06、S3、release 和 production 保持 blocked/not admitted。本轮没有新模型推理或模型运行账本条目。
