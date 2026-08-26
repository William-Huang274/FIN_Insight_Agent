# Model Run: FIN013-S1-DELL-03B-INTERNAL-CHAIN-CEILING-R6

## 摘要

- 状态：`executed_success / author_exact_recompile_and_reprojection_pass / fresh_independent_dual_audit_FAIL / immutable_bounded_observations_retained / same_stage_R7_required`。
- attempt：`dell-rsq-03b-internal-chain-r6`；R5 result 与 fresh-audit failure 保持不可变，不覆盖、不重试。
- 目的：用 clause-scoped typed propositions、entity/period canonical anchors v2 与 recursive explicit public allowlist，重算 current R39 上 6 个 DELL report-material target。
- 权限：仅 5 个冻结 request、1 个本地 Qwen3-Embedding-0.6B query batch。网络、Provider、生成模型、外源、4B、reranker、retry、mutation、promotion 与 closure 均为 0。

## TokenBudgetBasis 与执行门

节点覆盖 1,888 source records、34,199 compiled objects 与 5 个 request；每 request 必须精确产生 96 union／16 final rank permutation，并输出六目标 typed proposition、anchor、source/compiled/union/final completeness、coverage、route、privacy 和 zero-authority 结果。

implementation=`512aa32b0f312499b430c483ebfd3fbd9c520d38`，authority=`b6410eb274601abc0913c90f6b4adcf08c91cd48`；authority 的唯一父节点与唯一 policy path、`HEAD==upstream`、24 inputs、14 implementation SHA、canonical output collision 与 free bytes=`1,370,591,232` 全部精确。一次非 canonical import wrapper 在进入 runner 前失败且经零写入复核确认没有消费 attempt；正式执行只使用 canonical script 一次。

## 实际执行与结果

- recorded at=`2026-08-26T09:26:11+00:00`；request=5、local embedding batch=1、union=338、final=80、target-union occurrences=794。
- ASP=`2/2/2/2`，rank 15，reranker challenger eligible；supplier=`2/2/2/1`，rank 2；capacity、yield、HBM、units 均=`0/0/0/0`。
- 六目标 material coverage gap=0；external route required=4；4B recall eligible=0；local repair=0。
- 所有 Candidate/Evidence/NumericFact promotion、gap closure、03C/4B/reranker execution、S1/S2/S3、report/product/publication/release authority=false。

## 完整性

- policy digest/SHA=`6b0049f4a63b99983b2d0444a1dd123c325ad703d354bc70508a46b19ce50294` / `9ba4fb9be570ede9bc3c0f00ae1008afe6b3c2085195969311a6657d1f3dff65`。
- receipt digest/SHA=`35e78361c64b81b7e6d4957a9d16374bc845939e1671308f89a3b7e89b4c0e94` / `89f110b919caaa76a3dcd5a331fc8bb7c4f90a97ef0c108c6fa078787fe1228b`。
- private digest/SHA=`5ec6e86d685c0dd323f316ee5367120d0f9baf0dc13d3ff4b2143c2cb4f1d169` / `41e35ba9114e1ac05558818af4bf7d8ecc4c349e2df6c3ee71888bb24df5e37a`。
- public digest/SHA=`396bdf25ee481e6a389d585950182c5c053cb95452bca36487d9b2f640a89c09` / `53114d2954aeb64b5d2329fe14d76a10943bfc102d9e56ecbc66e30002a8d00a`。
- raw execution SHA=`0e9e4456ba75ecd07bc2e3bd6d5deddafc1972ba19700b029b2e6793e99f7458`。
- 四份 self-digest、private link 与 raw SHA 全通过；218.543 秒全量只读重编得到 private 逐字段全等、public reprojection 逐字段全等。

## 研究与报告边界

R6 没有补源，未运行 4B 或 reranker。Rank-15 ASP 的 reranker challenger 仍保留；4B mixed challenger 没有被取消，但本次六个 target 不满足 target-specific recall 执行资格。四个外源 target 也仍只是 route candidate，不是已证明的 public-information gap。

Fresh fork-none reviewer 必须同时审 immutable R6 的工程/语义/anchor/privacy/route，以及 R17 reader-visible citation appendix、gap crosswalk、WWC、密度/重复和 qualified-human/formal 8D。审计前 03B、S1、S2、report quality、product、publication 与 release 均不通过。

Post-result gate：R6 targeted=`95 passed`、Project OS=`82 passed`、active baseline=`213/8/5/28/0`、1,148 config JSON、8 个 Project OS JSONL／1,280 行、8,141-file secret scan／0、compileall、四份 self-digest 与 diff check 全部通过。

## Fresh independent dual audit

全新的 fork-none、作者分离、只读 reviewer 对 immutable result commit `9ca3c83087644496c08ddcc43b5a7d871efa52ef` 判定 Overall=`FAIL`。R6 新 finding=`P0/P1/P2/P3=0/0/3/0`；R17 open=`0/1/2/1`；combined=`0/1/5/1`。审计 self-digest=`11935696805f386364661f95c0ab1ae3076f86f5edc562d8d58f339e39516342`。

Integrity、exact execution、saved-raw replay、当前 public cleanliness 与 actual route 均独立通过；reviewer 以零模型方式对 1,888/34,199 全量重编 `126.711s`，private/public exact equal。因此当前 ASP=`2/2/2/2` rank15、supplier=`2/2/2/1` rank2、四 residual target=0、external=4、reranker eligible=1、4B eligible=0 仍是 bounded observations。

通用资格失败的三项 P2 为：完成组仍可跨 proposition/clause/sentence 拼接且无法稳定处理 polarity/modality/revocation/reported owner；material anchors 仍非 role-bound 并受产品/期间/货币语法及无关数字污染；public key allowlist 的允许字段仍可放行 credential-like、secret-like、encoded locator 与 relative traversal 内容。R17 仍缺 reader citation/source appendix、crosswalk consumption、operational WWC，并有事实/WWC 重复；formal 8D 和 qualified-human gate 无效。

R6 不覆盖、不重试。下一合法动作只允许先写 R7 program-level execution plan，再做 non-overwriting same-stage R7；03C、4B、reranker、Evidence/NumericFact、gap closure、S2、R17 successor、产品、publication 与 release 均不获授权。详见 audit artifact 与工作记录 095。
