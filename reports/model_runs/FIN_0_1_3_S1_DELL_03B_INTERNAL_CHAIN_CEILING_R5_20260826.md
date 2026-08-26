# Model Run: FIN013-S1-DELL-03B-INTERNAL-CHAIN-CEILING-R5

## 摘要

- 状态：`executed_success / author_exact_recompile_and_reprojection_pass / fresh_independent_dual_audit_pending`。
- attempt：`dell-rsq-03b-internal-chain-r5`；R1 terminal failure 与 R3/R4 fresh-audit failure 均保持不可变，R4 不重跑、不覆盖。
- 目标：在 current R39 上，以 raw sentence occurrence 先赋绝对位置、typed token-exact material anchors，以及 supplier/capacity/HBM/yield/units 的 scoped polarity、future/process、seller/shipper/reported-speech direction guard，重算 6 个 DELL report-material target。
- 权限：只运行 5 个冻结 request 与 1 个本地 CUDA/FP16 Qwen3-Embedding-0.6B query batch。network、Provider、生成模型、external capture、4B、reranker、retry、current mutation、Candidate/Evidence/NumericFact promotion 和 gap closure 全为 0。

## TokenBudgetBasis 与停止条件

本节点对 1,888 个 source record、34,199 个 compiled object 和 5 个冻结 request 执行非生成式检索诊断。每个 request 必须精确产生 96 个唯一 union candidate、16 个唯一 final candidate 和完整 rank permutation；R5 还必须对 raw occurrence positions、typed material coverage、每 target 的 source/compiled/union/final bounded-package 数、earliest limitation、residual route 与 03C/4B/reranker eligibility 给出完整输出。

执行只允许 authority commit `1e327656bbf61381128f612c571c20b51a8b51d6`；其唯一父提交为 implementation `9ed08c73fbae892535c4313a2fc5a191e67971d0`，唯一变更路径为 R5 policy。执行前 `HEAD==upstream`、工作树 clean、attempt/output 不存在、19 个输入与 12 个实现文件 SHA 精确、R4 audit 与 append-only correction 内外 SHA cross-binding 精确，D 盘 free bytes=`1,419,427,840`，高于 `536,870,912` 下限。消费回执先于 query batch 写入，同 attempt 禁止重试。

## 实际执行与完整性

- recorded at：`2026-08-26T06:07:12+00:00`；request=5、local query-embedding batch=1、request-level union=338、final=80、target-union occurrences=794。
- 每 request 精确 96 union／16 final；held target execution=0。
- `model_calls=0` 指 Provider/生成式模型调用为零；本次实际模型计算仅为 policy 单独授权并单独计数的 1 个本地 0.6B query-embedding batch。
- policy digest=`5477240da32474e8ff19f929d81183db7f55b6a346d83270609b354e730a776c`，SHA=`79c2f1f4db9014fc9ec7f9d322bb8d656715a083f555266d7e83ee4673698eee`。
- public digest=`bc916af92ce9f8346d7a96a51e04b8028ef832a3a4b7c975ea3e68ce9f50c3c1`，SHA=`1b8dc62ce76f8514b187cb173723b712ca1eac8e02b002c409079e0768636c9f`。
- private digest=`7949d84d8c802e2f6996f6b14ed5cfd474ef9636b58c8c86731a0d7efcc56df3`，SHA=`23b871247cf7b361ffcc7adfbfadd6df8f4aa1afd18a9cbf1e77a751be7b5c5d`。
- raw execution SHA=`0e9e4456ba75ecd07bc2e3bd6d5deddafc1972ba19700b029b2e6793e99f7458`；attempt receipt digest=`5251a8d74ecd40045c0706d37f887fec94a53c00f857feabfaecf7dc0fcb4044`，SHA=`ea88579eb8422e829a98fea9fa5a9d37deb0259f7c84d24c369dff7f390ade02`。
- policy/public/private/receipt self-digest、private SHA/digest link 与 raw execution SHA 均为 true；作者使用保存的 raw execution 对 1,888/34,199 全量只读重编 `144.925s`，private 逐字段相等，public exact reprojection 逐字段相等，且 public 无 model_text/material_sentence/URL 泄漏。

| target | complete source/compiled/union/final | best final rank | material coverage canonical/occurrence | author route output |
|---|---:|---:|---:|---|
| ASP | 2/2/2/2 | 15 | 0/0 | same-pool reranker challenger=1；bounded price 已在本地，Dell company realized ASP/mix 仍 open |
| capacity release | 0/0/0/0 | — | 0/0 | bounded 03C candidate；不是 public-information gap |
| capacity utilization/yield | 0/0/0/0 | — | 0/0 | bounded 03C candidate；不是 public-information gap |
| HBM supply | 0/0/0/0 | — | 0/0 | bounded 03C candidate；需要 Dell configuration/allocation bridge |
| supplier→Dell | 2/2/2/1 | 2 | 0/0 | relationship/delivery 在本地；supplier capacity/allocation 仍 open |
| units | 0/0/0/0 | — | 0/0 | bounded 03C candidate；需要 Dell company-period physical AI-server shipments |

## 研究、研报与后续边界

R5 的作者结果只证明 current local candidate chain 在本次 successor 语义下可重放。六目标 target-specific 4B recall challenger=0，不等于通用 mixed 4B program 被取消；ASP reranker 也只有实验资格，没有执行权限。四个 03C target 只是外源路线候选，必须先消费 prior-capture crosswalk，不能被称为已证明公共信息缺口。

上一版 R17 仍是 55 Evidence／14 gaps／0 closure，02B qualified-human decisions 仍为 `0/16`。reader-visible citation/source appendix、14/9/4/10 crosswalk、六项 WWC operationalization、重复与事实密度仍为 `OPEN/NOT_ASSESSABLE`。下一步必须先提交 immutable R5 result，再交给一个全新的 fork-none、作者分离、只读 reviewer，同时审 R5 engineering/semantics/route 与 R17 研报质量。审计通过前，03C、4B、reranker、Evidence/NumericFact admission、S2 重编、Pack/Readiness、新报告、产品、publication 与 release 全部禁止。

Post-result repository gate：R5 targeted=`41 passed`、Project OS=`82 passed`、active baseline=`213/8/5/28/0`、1,145 config JSON、8 Project OS JSONL／1,264 行、8,130-file secret scan／0、四份 self-digest、correction cross-binding 与 diff check 全部通过。

## 2026-08-26 fresh dual-audit 后置结果

Fresh fork-none、作者分离、只读 reviewer 判定 Overall **FAIL**。R5 新 finding=`P0/P1/P2/P3=0/0/3/0`：sentence-wide polarity/direction/modality 与 ASP affirmation 仍有 false complete/false partial；product-code 分隔符与 FY26/FY2026 typed anchor 不等价；public projector 是 denylist，未知 private 字段可进入未来 public。当前 immutable public 没有实际泄漏，实际 raw result、Git/19+12 bindings、四 digest、5×96/16、zero authority、private exact recompile 与 public exact reprojection全部独立通过。

R17 open finding=`0/1/2/1`：reader-visible citation/source appendix P1、crosswalk/WWC P2、density P3。Combined=`0/1/5/1`。R5 不覆盖、不重试；下一合法动作是 non-overwriting same-stage R6，且 R17 successor 继续分阶段等待 prerequisites。Audit digest=`56fc24881da2d814bce4daf7caac94df886e4c43be308b2105a07faaf48d7499`。
