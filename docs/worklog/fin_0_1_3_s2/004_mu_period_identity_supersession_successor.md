# S2 工作记录 004：MU 期间身份 supersession successor

## 原失败

immutable MU replay 中，`net_income` 请求 `TFR::916e7ab7802ba4c47059ac2f` 把两个物理季度都投影为 FY2025 Q3：

- `2024-11-29 → 2025-02-27`；
- `2025-02-28 → 2025-05-29`。

执行器正确返回 `typed_fact_comparable_period_ambiguous`，没有任选一个值。该失败继续保存在 `data/workbench_private/fin_0_1_3_s1_candidate_provenance_replay/mu-r1/full_result.json`，本轮没有改写。

## 根因

SEC CompanyFacts 的 `fy/fp` 表示披露文档的 fiscal focus，历史比较列可继承当前文档的 `fp`。Mart 已按同一物理区间建立 `superseded_by_observation_id`：后续披露把截至 2025-02-27 的季度恢复为 FY2025 Q2。但 `_candidate_rows` 只按 accepted-at、period end 和 fiscal label 取行，完全没有在 `research_as_of` 上消费 supersession；旧 Q3 标签因此与真实 Q3 同时进入 comparable selection。

## 修复

查询层现在只排除满足以下全部条件的旧投影：

1. 有明确 `superseded_by_observation_id`；
2. successor 的 `accepted_at` 严格晚于旧投影；
3. successor 在本次 `research_as_of` 之前已经公开。

这保留两项金融控制面：

- 在 successor 尚未公开的历史时点，旧 vintage 仍可见；
- 同一 accepted-at 的真实数值分歧不会因 supersession link 被隐藏，继续返回 `typed_conflict`。

## 受影响单请求 successor

只重新执行原 `net_income` TypedFactRequest，没有重建 SQLite、没有重算其他 NumericFact，也没有模型／Provider／网络调用。结果：

- status=`resolved`，typed conflict 消失；
- quarter-discrete 为 FY2026 Q3 `2026-02-27 → 2026-05-28` 与 FY2025 Q3 `2025-02-28 → 2025-05-29`；
- 旧 `2024-11-29 → 2025-02-27` 不再被标成 FY2025 Q3；
- 共返回 3 个 source-bound NumericFact；原失败 receipt 仍存在。

机器结果：`configs/financial_facts/fin_ia_0_1_3_s2_mu_period_identity_successor_result_v1_0.json`。

## 验证与边界

- S2 定向回归：`10 passed`，覆盖 PIT 前后、假 Q3 collision、同日真冲突 fail-closed、公式与现有 qrel 非回归。
- 与 S1 challenger 合并复证的全仓门禁为 `1188 passed, 2 warnings`；compileall、变更文件 pyflakes、JSON／Project OS、active baseline、Workbench TypeScript／production build、secret scan 与 diff check 全部通过。
- 本轮只关闭 `RC-S2-006`。`RC-S2-004` 的产品收入／ASP／PVM／出货量／产品利润桥仍开放；S2 stage qualification、S1/S3 acceptance、publication 和 release 均为 false。
