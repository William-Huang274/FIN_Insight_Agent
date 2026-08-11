# P38 Point01 M6.3R.2 Oracle、Diversity、Neighbor、Rerank 合同整改

## 结论与边界

- 日期：2026-07-14。
- 审计退回：`reject_and_repair_m6_3r_2_oracle_diversity_neighbor_rerank_contract`。
- 当前状态：`fixture_repaired_pending_total_reviewer_audit`。
- 本次只修 R.2 的纯内存 fixture/evaluator/oracle 合同；没有进入 R.3，也没有读取任何真实 adapter、index、graph、SQL 或 source bytes。

## 已修复的根因

1. corpus entry 不再包含 `expected_outcome`。新增独立、corpus-digest-bound 的 `LocalRetrievalFixtureOracle`；Harness 不导入、也不读取 oracle。oracle mutation regression 证明篡改期待值不会改变 actual evaluation。
2. 邻居引用增加 requiredness，且 relation 固定绑定方向化 seed field：section 的 previous/next、parent、table、previous/next page、previous/next row 不再共享无方向 `page_ref/row_ref`。required neighbor 缺失、cross-relation spoof 或 lineage mismatch 一律 typed exhaustion。
3. duplicate filter 先于 diversity。eligible pool 在 content/source cap 后按 first-pass-per-family、再 ranked fill 选择；capacity >=2 且可用 family >=2 时，低分第二 family 也必须进入 bundle。单 family 与 capacity=1 明确为 not-applicable。
4. Evidence Gate 集合先由 deterministic rerank top-N 决定，再按 bundle metadata 顺序形成 stable subset；不再由 metadata 重新选择成员。evaluation 与 gate 都验证 rerank-to-Gate set preserved。

## 产物与验证

- 新增：`src/sec_agent/canonical_runtime/local_retrieval_fixture_oracle.py`。
- 更新：fixture harness、directional candidate coordinate schema、schema export、R.2 runner/config/tests。
- corpus digest：由本轮 runner 输出；package manifest 和 gate result 同时固定 corpus/oracle/package digest 与 input file SHA-256。
- 定向回归：R2 `11 passed`；R1 `35 passed`；canonical schema `6 passed`；R0 `8 passed`。
- R1/R2 gate、compileall 通过；所有 adapter/index/graph/SQL/source read、ToolInvocation、network/model/provider、parser/promotion/store write/SourceHunter 均为 `0`。

## 未做事项与下一步

- 不存在 runtime retrieval、SQL authority、evidence promotion、Writer/Context/Domain Judgment、M6.3 full/calibrated 或 M6 complete 主张。
- R.3 继续 blocked。总 reviewer 复核该 repair 后，才可决定是否接受 R.2 fixture tranche；任何真实本地 read-only adapter execution 都仍须独立审批。
