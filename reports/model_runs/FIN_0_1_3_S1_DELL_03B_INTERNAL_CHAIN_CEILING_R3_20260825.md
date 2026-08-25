# Model Run: FIN013-S1-DELL-03B-INTERNAL-CHAIN-CEILING-R3

## 摘要

- 状态：`executed_success / author_integrity_pass / fresh_independent_audit_pending`。
- attempt：`dell-rsq-03b-internal-chain-r3`；R1 terminal failure 与 R2 fresh-audit failure 均保持不可变。
- 目标：在修复 R2 execution seal、bounded same-source evidence unit、实体／关系方向、scope separation 和
  source→object material coverage 后，重新计算 6 个 DELL report-material target 的本地 candidate ceiling。
- 权限：仅 5 个冻结请求与 1 个本地 Qwen3-Embedding-0.6B query batch；network/model/provider/external/4B/
  reranker/retry/mutation/promotion/gap closure 全为 0。

## TokenBudgetBasis 与停止条件

本节点对 1,888 个 source record、34,198 个 compiled object 和 5 个冻结请求执行非生成式诊断。每个 request
必须精确产生 96 个唯一 union seed、16 个唯一 final candidate 和完整 rank permutation。结果必须输出每 target
的 source/compiled/union/final bounded-package 数、coverage loss、earliest limitation、residual research boundary
和 4B/reranker/03C eligibility。

执行只允许 authority commit `41959e0a826179fa877cbd5015e612a279346fd7`，其唯一父提交为 implementation
`6548e0fb94714e045753db6b3c25f7c939872de3`，唯一变更路径为 R3 policy。dirty/unsynced Git、branch/tree/
implementation SHA、predecessor SHA/digest、canonical path、attempt collision、request/rank 形状或任一 zero-authority
字段漂移均在执行或发布前 fail closed。Attempt consumption receipt 先于 query batch 写入，同 attempt 禁止重试。

## 实际执行

- recorded at：`2026-08-25T15:37:03+00:00`；
- request=5、query-embedding batch=1、request-level union=339、final=80、target-union occurrences=795；
- held target execution=0；全部外网、模型、4B、重排、重试、mutation、promotion、closure=0；
- public digest=`7efa24a4...067e3`，SHA=`a65b7e3e...aeaa`；
- private digest=`7e108554...b7c20`，SHA=`807d8249...db267`；
- raw execution SHA=`6216ec5f...2358`，attempt receipt SHA=`43fee21b...4bfa`；
- public exact reprojection、private/public/attempt self-digest、private SHA/digest parity 与 raw execution validation
  全部为 true。
- post-result R3＋Project OS=`111 passed`；active baseline=`213/8/5/28/0`，config JSON=`1131/0 invalid`，
  Project OS JSONL=`8 files/1231 rows/0 invalid`，secret scan=`8101/0`，diff check 通过。

| target | complete source/compiled/union/final | best final rank | coverage occurrence | route output |
|---|---:|---:|---:|---|
| ASP | 2/2/2/2 | 15 | 0 | reranker eligible；不需为 bounded price 全量 03C；realized ASP/units/mix 仍 open |
| capacity release | 0/0/0/0 | — | 4 | local coverage review/repair 后才可做 allocation/timetable 03C |
| capacity utilization/yield | 0/0/0/0 | — | 0 | bounded 03C eligible |
| HBM supply | 0/0/0/0 | — | 0 | Dell bridge residual 03C eligible |
| supplier→Dell | 4/4/4/2 | 2 | 4 | relationship/delivery 已在本地；capacity/allocation open |
| units | 0/0/0/0 | — | 5 | local coverage review/repair 后才可做 units 03C |

## 研究与研报边界

ASP 的两个 complete package 是有限 configuration/bundle price，不是 company-wide realized ASP。Supplier complete
是 relationship/delivery，不是 supplier capacity allocation。Coverage count 是 occurrence，parent/slice 可能重复；
units coverage 还含 NVIDIA/industry partial context，必须由 fresh reviewer 检查 materiality 与去重。候选仍不是
Evidence。

R3 没有解决上一版研报全部信源问题：55 Evidence／14 gaps、02B `0/16`、Evidence promotion=0、gap closure=0。
R17 的 reader-facing citations/source appendix、WWC 和正文质量仍 open。只有新的 author-separated reviewer 同时
通过工程与研报质量后，才能决定是否修本地 materialization、单独授权 ASP reranker、运行 bounded residual 03C，
以及再进入 admission、S2、动态单元和新报告。
