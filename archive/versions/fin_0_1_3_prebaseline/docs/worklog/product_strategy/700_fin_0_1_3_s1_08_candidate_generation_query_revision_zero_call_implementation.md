# 700 — FIN 0.1.3 S1-08 candidate generation 与 query revision 零调用实现

日期：2026-08-07
阶段：`013-S1-08`
状态：`engineering proof pass / clean proof and live candidate ceiling pending`

## 1. 问题与决策

S1-08 entry audit 已证明当前只有 7 个 active URL、没有 FIN 0.1.3 current Search 合同，也没有 query revision。继续调 BM25/BGE/Milvus 只会在目标材料进不了候选池时优化排序，指标没有产品含义。

本轮只修最早 owner：建立 provider-neutral source catalog、Evidence-role query planner、最多两次有理由的 revision、capture-first official discovery adapter，以及与 planner 物理分离的 evaluator-only Gold matcher。目录只含公司身份、CIK、官方 landing page 和产业角色，禁止包含 Gold Evidence/target ID、expected insight 或 benchmark 文档 URL。

## 2. 实现

- `configs/runtime/fin_ia_0_1_3_s1_08_current_source_catalog_and_query_revision_policy_v1_0.json`
  - 五类标准证据角色：issuer、regulatory、customer demand、supply/counterevidence、market context；
  - DELL/MU/NVDA/MSFT/TSMC 仅保存官方入口、CIK 和 ecosystem role；
  - 每 target 最多 2 次 revision、每案 24 个 pool 候选、selected pack 最多 8 个，模型调用为 0。
- `src/sec_agent/s1_08_candidate_generation_runtime.py`
  - 从 research objective 与标准 evidence role 编译 Gold-blind query；
  - revision 必须改变 query/route、记录 trigger 与 stop reason，禁止 identical retry；
  - future、cross-case、unknown entity、未晋升和缺 capture-first lineage 候选 fail closed；
  - hidden Gold 只在运行结束后按 source locator 计算 target-in-pool 和 selected-pack coverage。
- `src/sec_agent/s1_08_official_discovery_adapter.py`
  - 真实 adapter 先抓 official landing/SEC submissions 并保存 capture，再发现 source URL；
  - source document 再单独 capture、parse、保存 parser receipt，最后才能成为 candidate；
  - 支持 HTML anchor、SEC submissions JSON、受控 local market snapshot、document cache 与 network ceiling；
  - 无发布时间、parser 失败、超预算均保留 typed receipt，不伪造 current evidence。
- `scripts/releases/materialize_fin_ia_0_1_3_s1_08_candidate_generation_zero_call_proof.py`
  - 使用 evaluator fixture 模拟“外部世界中存在这些材料”，但 planner 从未接收 Gold ID/URL；
  - 版本化结果只保存摘要和 digest，不把 Gold 明细复制进 Runtime 计划。

## 3. 发现并修复的根因

首轮测试有两个 fixture/contract 缺口：local market runtime locator 与 evaluator artifact locator 未统一；DELL exhibit/call 的证据角色映射不正确。修复后仍有一次更重要的 planner 缺陷：`subject` 角色会把 MU/NVDA 的 `subject` 标签展开进 DELL issuer query，形成跨案例访问。修复位于 `_entities_for_role`，现在 `subject` 只选择 current case，relationship role 才能扩展其他实体；没有在 adapter 末端加过滤掩盖上游错误。

## 4. 结果

- focused：`15 passed`；
- S1-07/S1-08 related broad：`32 passed`；
- materializer 两次输出 byte-identical；
- 三案 fake pool/selected：DELL=`6/6`、MU=`7/7`、NVDA=`7/7`；
- evaluator-only：`12 target groups`，fixture target-in-pool=`1.0`，selected-pack coverage=`1.0`；
- mutation：Gold 泄漏、跨案、未来日期、lineage 缺失、未晋升、source 缺失、stale market snapshot 冒充 current Gold、identical retry、revision overflow、排序稳定性；
- model/provider/network=`0/0/0`，未调 ranking/reranker。

结果：`configs/releases/fin_ia_0_1_3_s1_08_candidate_generation_query_revision_and_gold_match_zero_call_proof_v1_0.json`。

## 5. 边界与下一步

这证明 current contract、query revision、capture-first discovery adapter 和 evaluator isolation 的工程形状成立；不证明真实 DELL 网络能发现任何 benchmark-equivalent source，也不证明 NDCG/MRR、S3 evidence utilization 或研究报告质量。

下一步先在 clean/synced commit 上重跑 materializer 与 focused/broad tests。通过后只做一次 DELL current-search canary authority decision；canary 必须有 exact-once admission、明确网络/文档预算和完整 receipts。若 target-in-pool 不足，留在 S1-08 修 discovery/source coverage，不进入 reranker；若是来源确实不存在，保留 typed gap，不伪造 Evidence。
