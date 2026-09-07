# S1 工作记录 086：DELL 03B R3 bounded-package 结果与 fresh audit 门

日期：2026-08-25

状态：`R3 exact-once executed / author integrity verification pass / fresh author-separated audit pending`

## 1. 结论先行

R2 fresh audit 的 P0/P1/P2 问题已在 non-overwriting R3 中实现 successor，并在 clean、
`HEAD == upstream` 的 authority commit 上完成唯一一次本地执行。R3 不是新 Evidence，也没有关闭上一版研报的
任何 gap；它把 6 个 report-material target 的本地 source／compiled object／candidate union／final review
状态重新分类，并把本地编译缺文、候选召回、同池排序与真实 residual 外源需求分开。

作者侧完整性检查通过，但 03B 尚不能写成独立通过。新的无上下文继承、作者分离、只读 reviewer 必须同时审查
执行封印、语义 precision/recall、source→object coverage、route eligibility，以及 R17 的正文信源与读者可见
citation/source appendix 质量。Reviewer 不是 qualified human；02B 仍为 `0/16`。

## 2. 两阶段执行身份与一次性约束

- implementation commit：`6548e0fb94714e045753db6b3c25f7c939872de3`，tree
  `26c2c793a08cc42ee5d52f1ea4058a22d71b16e8`；只包含 R3 compiler、runner、测试和 current runtime
  authority-counter 投影。
- authority commit：`41959e0a826179fa877cbd5015e612a279346fd7`，唯一父提交为 implementation commit，唯一变更路径为
  `configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_2.json`。
- policy digest：`891d2cc370d9bd63986b04125d4a4ec72b191cead280c9d4385da0060bc77c55`；执行前本地与远端均为
  authority commit，branch、tree、四个 implementation SHA 和 canonical output paths 全部匹配。
- attempt：`dell-rsq-03b-internal-chain-r3`；先 exclusive-create consumption receipt，再执行，禁止同 attempt
  retry。receipt digest=`e20125bb...5d45e`，SHA=`43fee21b...4bfa`。
- private result digest=`7e108554...b7c20`，SHA=`807d8249...db267`；public result digest=
  `7efa24a4...067e3`，SHA=`a65b7e3e...aeaa`。公共结果由私有结果 exact reprojection 得到，三份 self-digest、
  private SHA/digest、attempt SHA/digest 和 raw execution validation 均通过。

## 3. 执行与权限事实

R3 精确消费 5 个唯一 request、1 个本地 Qwen3-Embedding-0.6B query batch；每 request 精确有 96 个唯一
union seed 和 16 个唯一 final candidate，rank 均为完整排列。request-level hybrid union 为 339、final 为 80，
target-scoped union occurrence 为 795。

`network/model/generation/provider/external/4B/reranker/retry/current mutation/candidate promotion/Evidence
promotion/gap closure` 全部为 0；held target execution 为 0。任何一个字段、request、rank、ID、路径、Git 身份或
输出事务漂移都 fail closed。该事实只说明 R3 没有越权，不授予后续调用。

执行前作者工程门为 R3 focused `29 passed`、DELL/current-runtime adjacent `149 passed`、legacy/R2
compatibility `36 passed`、全仓 `1419 passed, 2 skipped, 2 existing SWIG warnings`；compileall、精确
pyflakes、active baseline `213/8/5/28/0`、1129 config JSON、8 份 Project OS JSONL／1227 行、Project OS
`82 passed`、8097-file secret scan／0 和 diff check 全部通过。

结果物化后的 R3＋Project OS 定向门为 `111 passed`；active baseline 仍为 `213/8/5/28/0`，1131 份
config JSON 与 8 份 Project OS JSONL／1231 行全部可解析，8101-file secret scan／0，diff check 通过。

## 4. 六个 target 的作者侧 R3 结果

`source/compiled/union/final` 是 complete bounded-package 数，不是 Evidence 数。coverage gap 为 occurrence，
父 source 与其 slice 可重复出现，不能当成独立事实数量。

| target | complete source/compiled/union/final | best final rank | coverage-gap occurrence | 作者侧后续分类 |
|---|---:|---:|---:|---|
| ASP | 2/2/2/2 | 15 | 0 | bounded configuration/bundle price 已在本地；company-wide realized ASP/units/mix 仍 open；同池 reranker challenger eligible |
| capacity release | 0/0/0/0 | — | 4 | 先审计并修 source→object materialization；之后才可对 allocation/timetable 做 bounded 03C |
| capacity utilization/yield | 0/0/0/0 | — | 0 | 当前本地完整对象缺失；bounded 03C eligible，但不是 public-information boundary |
| HBM supply | 0/0/0/0 | — | 0 | 有 HBM context、无 Dell configuration/allocation bridge；bounded residual 03C eligible |
| supplier→Dell | 4/4/4/2 | 2 | 4 | relationship/delivery 已在本地，不再为该部分补源；capacity/allocation residual 仍 open；先审 coverage |
| Dell AI-server units | 0/0/0/0 | — | 5 | GPU/采购/行业 shipment context 不是 Dell company-period physical units；先审本地 coverage，再做 bounded 03C |

R3 因而报告 `external_route_required_target_count=4`、`same_pool_reranker_challenger_eligible_target_count=1`、
`4B_embedding_challenger_eligible_target_count=0`、`local_source_to_object_repair_target_count=3`。这些是待独立
复核的 route outputs，不是执行 authority。

## 5. 本地 coverage 的质量边界

容量释放与 supplier 的 4 个 occurrence 来自两条 material sentence 在 parent source 与 slice 上的重复投影：
Dell/NVIDIA partnering-to-deliver，以及 Dell 美国工厂一周可 ship 数千 Blackwell GPU。它们能支持关系／交付／
产能上下文，不等于供应商 allocation 或 Dell 物理 server units。

units 的 5 个 occurrence 包含 NVIDIA 出口许可限制与行业 AI-server shipment growth 等 partial context。它们即使
未进入 compiled object，也不自动支持 Dell company-period physical units。Fresh reviewer 必须判断 coverage
detector 是正确的保守阻断，还是把非 material context 误计为本地修复义务；还要检查 parent/slice 去重。作者
不得用 `3 repair targets` 直接签发数据重编。

## 6. 对上一版研报信源问题的实际含义

上一版研报的信源缺失仍未“全部解决”：Pack 仍为 55 Evidence／14 gaps，qualified-human decision 仍为
`0/16`，本次 Evidence promotion 与 gap closure 都为 0。R3 只纠正了两类旧误判：

1. 两组 bounded configuration/bundle price 不是 corpus absent，但也不能推导 Dell company-wide ASP；
2. Dell/NVIDIA relationship/delivery 已存在，不应重复补源，但 supplier capacity/allocation 仍未证明。

yield、Dell-specific HBM bridge、Dell company-period physical AI-server units，以及 ASP/units/mix 到 PVM/产品利润桥
仍未闭合。R17 仍缺 reader-facing claim citation 和 source appendix，WWC、重复、事实密度等报告质量项也未关闭。

## 7. 下一合法顺序

1. 先提交并推送本 R3 public result 与记录，保持 private result/attempt receipt 原样；
2. 让新的 fresh、author-separated、fork-none、只读 reviewer 审 immutable R3，覆盖工程与研报质量；
3. 审计通过后，先处置真实的 source→object materialization 缺陷并重算受影响 target；若审计发现 R3 material
   finding，则保留 R3 并开新的 same-stage successor，不能改写或重跑 R3；
4. 单独预注册 ASP 的 same-pool reranker challenger；本结果未授权运行。4B recall challenger 在这 6 个 target
   上为 0，不代表通用 4B 方案被永久取消；它只是不能修复“完整对象不在本地 corpus”或“对象已在 final 15/16”这两类问题；
5. 对审计后仍属真实 residual 的 yield、HBM bridge、capacity allocation/timetable、units 运行 prior-capture
   crosswalk 后的 bounded 03C；不得扩大成泛搜，也不得把 reachable failure 写成信息边界；
6. 之后才进入 CandidateDecision、02B qualified-human Evidence admission、Pack/Readiness/S2 bridge 重编、
   受影响动态单元、新报告与 reader-facing citation/source appendix；最终再做工程、研报和 qualified-human 产品验收。

当前 `03B independent pass/03C/4B/reranker/Evidence/gap closure/G3/S1/S2/S3/report/product/publication/release`
全部仍为 false。
