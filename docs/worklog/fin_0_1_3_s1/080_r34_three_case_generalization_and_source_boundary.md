# S1 工作记录 080：R34 三案例泛化与补源边界

日期：2026-08-25

状态：`DELL_R34_current / three_case_runtime_generalization_pass / source_coverage_and_S1_qualification_open`

## 1. 本轮回答的问题

本轮不再用“七项流程已实现”代替产品验收，而是分别回答：

1. DELL 定向补源是否真的进入 current；
2. current S1/S3 控制链是否能在 DELL、MU、NVDA 三案复用；
3. 8GB 量化 4B 是否值得替换 current 0.6B；
4. 哪些资料仍然不能称为已补齐。

## 2. DELL 定向补源的 current 事实

工作记录 078 已完成三个原 `not_ready` 请求的受控处置。五条原文路线经历 capture-first、
日期纠错、对象重编、穷尽 CandidateDecision、Evidence Gate 和 R4 原子晋升：

- current DELL Pack 为 `55 Evidence / 14 residual gaps`，payload digest
  `1654b68f...e2a98`；
- 价格／配置有公共采购和有界 bundle 样本，状态可研究，但不能称 Dell 公司 ASP；
- 当前 Dell↔NVIDIA 双向关系已 ready，但不能推导私有 allocation 或合同条款；
- 公司级 unit/share 仍是唯一 task-level `not_ready` 请求；公共采购四套系统不能代替公司出货量；
- `14 -> 14` gap、`0` closed、`3` narrowed。这个结果不是“补源没有做”，而是补源后证据只支持
  更窄边界，不能诚实关闭公司级 ASP、units/share、PVM 或产品利润问题。

R34 current 由 registry `FIN-0.1.3-CURRENT-PRODUCT-RUNTIME-RESOURCE-REGISTRY-R34` 和 binding
receipt v1.10 约束；MU、NVDA 以及三条 holdout case 都按 predecessor digest 保留，没有用 DELL
晋升覆盖其它案例。

## 3. fresh 三案例泛化回执

旧三案例 materializer 把 `recorded_at` 固定为 2026-08-22，且会覆盖输出。它不能证明今天读取的
是 R34，也不符合 attempt immutable 规则。本轮将其改为：

- 必须从 clean commit 启动并记录 `prepared_from_commit`；
- 显式绑定 R34 current pack、binding receipt 和 DELL/MU/NVDA readiness 的 ref、SHA 与 digest；
- 验证 DELL 是 current replacement、MU/NVDA 是 retained-by-digest；
- 自动记录真实时区时间，public result exclusive-create，输出冲突先于 GPU 检索 fail closed。

attempt `three-case-r34-generalization-r1-20260824T165538Z` 从 commit `1487b5b7...c1070c5`
执行。公开结果：
`configs/research/evals/fin_ia_0_1_3_s1_s3_actionable_research_three_case_zero_call_result_v1_1.json`，
digest `b81ee944...5cddd`，重算一致。

| 案例 | Current Evidence | Gap | ProductReadiness | Actionable-state gate |
|---|---:|---:|---|---|
| DELL | 55 | 14 | `blocked_by_evidence_admission` | 12/12 pass |
| MU | 14 | 15 | `blocked_by_candidate_coverage` | 12/12 pass |
| NVDA | 25 | 13 | `blocked_by_candidate_coverage` | 12/12 pass |

DELL 五个 S3 cell 均收到 current typed control context；candidate auto-promotion、public-gap
authorization、network、natural model 和 paid calls 均为 `0`。

## 4. 不能扩大的结论

三案运行时泛化通过不等于三案来源完备：

- DELL 当前仍有 `12` 个 `targeted_source_supplement` 动作、`4` 个 candidate admission 动作；
- MU 当前仍有 `17` 个 targeted supplement 动作、`3` 个 admission 动作；
- NVDA 当前仍有 `14` 个 targeted supplement 动作、`3` 个 admission 动作；
- 三案 `public_information_gap_authorized_count` 都是 `0`，所以未执行或未穷尽路线不能伪装成
  “公开信息不存在”。

因此，“之前研报里能补的源是否全补了”的准确答案是：DELL 被点名的三个重点请求已走完本轮
批准的原文梯子并有边界回执；更广的 DELL 命题、MU 和 NVDA 尚未完成完整外源梯子。当前系统
已经能诚实列出下一条补源动作，但不能声称 S1 source completeness 或 `S1_qualified_stable`。

## 5. 4B 结论

工作记录 079 的 Q4_K_M 4B shadow 已证明当前 8GB GPU 可 full-offload：embedding／reranker
峰值分别 4,524／4,333 MiB。未晋升原因是受控质量：embedding 在 NVDA 回退，reranker 总体和
MU/NVDA 均回退。current 继续使用 0.6B FP16；不再为“模型更大”扩大评测。
