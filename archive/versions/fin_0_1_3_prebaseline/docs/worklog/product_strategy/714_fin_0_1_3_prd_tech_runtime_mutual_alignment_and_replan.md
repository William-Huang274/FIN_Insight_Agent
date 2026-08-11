# 714 — FIN 0.1.3 PRD / TECH / Runtime 相互校准与计划重排

日期：2026-08-08
阶段：`FIN 0.1.3 cross-stage planning audit`
状态：`mutual alignment complete / no new execution authority / current next unchanged`

## 1. 触发原因

用户要求根据 S1-08 成熟组件回放和此前 FIN 0.1.3 实际工程结果，重新对照 PRD、TECH 与版本计划，并让工程发现反向更新产品与技术合同。审计确认旧计划存在一个实质漂移：它把 S1-08 写得过于接近“候选实现后做排序”，但 DELL R2 live 已证明真正阻断仍在 provider/locator/candidate ceiling，ranking 尚未准入。

本轮先执行 Project OS `repository_and_git_hygiene` scoped preflight，结果 pass；随后只读核对 PRD、TECH_00A/01/02/03/10、FIN 0.1.3 主计划、current context、capability/root-cause ledgers 与 worklog。没有运行网络、模型、Provider、ranking 或业务链。

## 2. 对齐后的事实

1. S0-01–03 仍为 pass，但 RC-P36-156 是真实共享治理债务：自由文本 run scope 与固定开放状态集合可能 fail-open；应归 `013-S0-04G`，S5 再验。
2. S1-01–05 的“pass closed”是当时本地 truth/governed pack 的历史状态；S1-06 MCP、S1-07 official-source runtime 后，S1-08 仍未关闭。最新 DELL live 为 `16 calls / 1 unique source / target-in-pool 0`。
3. S1-08 v3 mature-component/relationship/budget 只有 zero-call engineering pass；clean independent proof 仍是唯一当前下一项。
4. S2 已完成 experiment/capability boundary 与 deterministic correction guard，但 DeepSeek natural evidence-role/closure 失败，不能写成模型自主纠错通过。
5. S3-01–05 只是 minimum engineering anchor；29 个 Cell 未研究、自然 thesis support/counterevidence 和正式八维内容验收不足。S3-06–09 尚未开始。
6. FIN 0.1.3 current candidate 尚未进入 S4 dogfood；S5 RG1–RG5 未开始。0.1.2 的只读 Workbench/Report surface 不能自动成为 0.1.3 产品验收。

## 3. 产品文档更新

PRD 新增：

- Search capability lifecycle：`declared/configured/operational/replay_proven/live_proven`；
- provider→route→locator→capture/parser→target-in-pool→ranking→promotion→utilization 的不可倒置梯级；
- target-in-pool 未通过时 ranking/NDCG/MRR/BGE/Milvus=`not_admitted`；
- typed gap 必须区分 route unavailable、未尝试、slot starvation、parser/date/relationship reject 与真实 source exhaustion；
- unique canonical network document、role binding、本地 snapshot 分账；
- typed blocker state、versioned RunScopeRegistry 与 unknown fail-closed；
- S0–S5 最早责任阶段边界与 Search Quality Card 对 S3 的准入。

产品范围没有扩大到通用搜索平台，也没有降低 FIN 0.1 Internal Alpha 的研究内容质量门；如果 broad external search 是当前版本必需能力而又没有运营 Provider，后续必须做 provider acquisition 或明确缩小 source claim 的产品决定。

## 4. 技术文档更新

- TECH_00A：新增 2026-08-08 current implementation overlay，分开报告 search/numeric/model/research/product/release 成熟度。
- TECH_01：Lead/S3 必须消费 SearchQualityCard；未进入候选池的 Cell 只能 needs_source/typed_gap/blocked，不能靠叙事补齐；调用次数由 open Cells 与 repair value 决定。
- TECH_02：冻结 S1-08 关闭梯级、三案关闭条件与 provider/product-scope 决策边界；v3 clean proof之后仍需独立 live authority。
- TECH_03：新增 candidate-ceiling、index freshness、canonical source accounting 与 ranking admission；旧 89,112-row BM25 保持 non-authority。
- TECH_10：把 Search、Model adherence、Research content 定义为三个独立 EvalSubject，建立 SQ0–SQ5 gate ladder 和 failure attribution。

## 5. 更新后的执行顺序

1. S1-08 v3 clean independent zero-call proof。
2. 独立决定是否签发一次 DELL fresh-live；不自动执行。
3. 若 DELL candidate ceiling 仍失败，停止 live retry，做 provider acquisition 或 Internal Alpha source-scope 决定；不得先调 reranker。
4. 在任何 MU/NVDA transfer/S3 前完成 `013-S0-04G` typed blocker state 与 RunScopeRegistry。
5. DELL 通过且 S0-04G 关闭后做 MU/NVDA bounded transfer；三案 target-in-pool 通过后才评价 ranking/selected pack，并关闭 S1-08。
6. DS-A1/A2/A3 model-family profile、judgment atom、protected narrative。
7. S3-06/07 动态研究与 targeted repair；不把 9 次调用当产品上限或质量代理。
8. S3-08/09 三案 Experiment B＋八维内容质量＋qualified-human acceptance。
9. S4-06 current candidate Workbench dogfood。
10. S5 RG1–RG5 release/rollback/portability decision。

## 6. 边界与权限

机器计划：`configs/releases/fin_ia_0_1_3_prd_tech_runtime_mutual_alignment_and_replan_v1_0.json`。

本轮新授权为 0：network/model/provider/admission/ranking/release 均未授权。FIN 0.1.3 继续作为 current version，FIN 0.2 定义不变；单个 proof、canary 或 stage failure 不创建 0.1.4。当前下一项仍是 `S1_08_V3_MATURE_COMPONENT_RELATIONSHIP_BUDGET_CLEAN_INDEPENDENT_ZERO_CALL_PROOF`。
