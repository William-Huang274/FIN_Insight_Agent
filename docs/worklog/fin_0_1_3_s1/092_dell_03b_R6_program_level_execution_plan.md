# S1 工作记录 092：DELL 03B R6 program-level execution plan

日期：2026-08-26

状态：`approved same-stage R6 planning / implementation not started / no R6 policy or attempt`

## 1. 目标与不变边界

R6 只修复 fresh R5 audit 的三个 owning-stage 根因：

- `RC-S1-079`：clause-scoped polarity、modality、subject/object direction 与 ASP affirmative quote。
- `RC-S1-080`：product-code separator 与 FY typed-anchor canonicalization。
- `RC-S0-105`：private→public projection 必须由递归 allowlist/schema fail-close。

R5 policy/private/public/receipt/audit 保持 immutable；R6 使用新 schema、module、runner、policy、attempt 和 result path。R6 不补源、不跑 03C/4B/reranker、不晋升 Candidate/Evidence/NumericFact、不关闭 gap、不重编 S2、不改 R17，不给 product/publication/release authority。

## 2. 需求票与依赖图

### R6-01：typed clause proposition

输入：R4 base target groups、R5 known attacks、R5 fresh audit 新 attacks、current R39 source/object/raw receipt。

输出：每个 target 的 typed clause proposition predicate，至少绑定：

- clause boundary；
- subject／actor；
- predicate／event；
- object／recipient；
- affirmative/negative polarity；
- observed/future/estimated modality；
- process/pilot/prototype identity；
- direct action 与 reported-speech direction。

规则：

- supplier、capacity、HBM、yield、units 与 ASP 都不得仅依赖整句关键词共现；
- 无关从句的否定、unavailable 或 next-process target 不得误杀前一条已完整肯定命题；
- `failed/rejected/refused/denied/not/never/without/lack` 等必须绑定到相关 predicate；
- `should/will/expected/forecast/anticipated/estimated/planned/projected` 与 pilot/prototype/trial/test/wrong-process 必须阻止“observed yield”；
- units 的 shipment actor 必须为 Dell，不能是 reported counterparty；`refuted/denied reports` 不能形成 Dell shipment；
- ASP price/quote 命题必须是 affirmative，`did not quote/denied quoting` 不得 complete。

依赖：R4 classifier 的稳定 group vocabulary；不修改 R4/R5 bytes。

### R6-02：typed material anchor v2

输入：source material sentence、compiled bounded window、target proposition role。

输出：canonical typed anchors v2。

规则：

- `H100/H-100/H/100/H 100` 统一为 `product_code:h100`，不产生 `number:100`；
- `XE9680/XE-9680/XE/9680/XE 9680` 同理；覆盖当前已知 AI accelerator/server product prefix；
- `FY26/FY2026` 统一到同一 canonical fiscal year；
- currency/percent/decimal normalization 保留；`$15.00=USD 15.000`，`15 != 150`；
- product entity 内数字不得满足独立 quantity/price/time proposition；
- coverage 仍要求 required material group + anchor containment，不把非材料句尾数字创建 repair obligation。

依赖：R6-01 的 proposition role，用于后续把 numeric anchor 进一步绑定到命题槽。

### R6-03：recursive public schema

输入：R6 private result。

输出：R6 public result。

规则：

- target row、candidate ceiling、public package、downstream disposition、input bindings、execution summary、summary、runtime registry 与 authority 全部使用显式字段 allowlist；
- private target row 的所有已知 private 字段只能被消费而不能复制；任何未知字段 fail；
- 递归拒绝 raw/model/private/secret payload、URL/URI/`www.`、绝对本地路径、private locator；
- public 仍可保留 contract 明确允许的 repo-relative refs、digest、SHA、rank/count/route/authority；
- 任何 schema drift 在 publication 前失败，不能“删除几个已知 key 后继续”。

依赖：R6 private schema 完整字段清单；R5 actual private 用作正例，injected fields 用作负例。

### R6-04：predecessor、authority 与 execution seal

输入：R5 的 policy/public/private/receipt/fresh audit，加 R5 已绑定的全部 predecessor/R39 runtime。

输出：R6 policy validator 与 exact-once runner。

规则：

- R5 audit 必须是 Overall FAIL、new R5=`0/0/3/0`，且包含 RC-S1-079/080、RC-S0-105；
- 保留 R5 actual execution/integrity observations，但验证 R5 retry/overwrite=false、R6 successor=true；
- 绑定 24 个 immutable inputs 与 14 个 implementation files（最终数以 validator exact set 为准）；
- 5 request、1 local 0.6B query batch、每 request 96/16、所有 zero authority counter 不变；
- canonical output、exclusive attempt、atomic pair、no retry、clean HEAD/upstream、authority parent=implementation、policy-only authority commit、minimum free disk gate 全部 fail-close。

## 3. 输入与输出

冻结输入：

- R5 policy/public/private/receipt/audit；
- R4 correction 与所有 R5 bound predecessors；
- current R39 runtime registry/binding、source=1,888、objects=34,199；
- R5 raw receipt 只用于零模型 preview/replay，不冒充未来 R6 formal attempt；
- R17/crosswalk/WWC/02B artifacts 只用于保持 report-quality boundary，不进入 R6 classifier 输出。

新增输出（实现后）：

- `src/retrieval/dell_report_internal_chain_ceiling_r6.py`
- `scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r6.py`
- `tests/test_dell_report_internal_chain_ceiling_r6.py`
- R6 policy/private/public/receipt 使用 v1.5 与 attempt `dell-rsq-03b-internal-chain-r6`；policy 只在 clean implementation push 后生成。

## 4. 工程验收标准

1. R5 全部 41 tests 在 R6 seam 下不回退。
2. Fresh auditor 的 false-complete、false-partial、anchor 与 injected-secret attacks 全部冻结。
3. 至少补充同义否定/模态/报告动词、标点/从句、未知 counterparty、正例后无关否定、多个 observed/future measure 的自设计 attacks。
4. R6 policy 对 root cause、input SHA、implementation SHA、Git topology、attempt/output collision、disk、rank/counter drift fail-close。
5. compileall、pyflakes、diff check、Project OS、active baseline、JSON/JSONL、secret scan、focused 与 full repository 通过。
6. R6 implementation 不修改 R4/R5 或 current runtime/Evidence/S2/R17 bytes。

## 5. 模型环节与研究输出质量标准

检索执行质量：

- 5 个唯一 request，每个 96 unique union／16 unique final；
- local embedding batch=1，CPU fallback/network/provider/generation/4B/reranker/retry=0；
- raw execution SHA 与 validated digest 一致。

语义/coverage 输出质量：

- false complete=0、false partial=0（对冻结 controlled set）；
- source/compiled/union/final completeness 必须基于相同 R6 proposition；
- raw occurrence adjacency 与 typed-anchor v2 必须同时成立；
- actual current corpus 若与 R5 不同，必须逐 target 给出 sentence/package-level cause，不能把 classifier drift 伪装成检索改进；
- empty local result 仍不是 proved public-information gap。

privacy 输出质量：

- private exact recompile；
- public exact reprojection；
- explicit schema/unknown-field attacks 全拒绝；
- current public 不含 private text、locator、URL、绝对路径；
- public digest/private link 精确。

## 6. 最终研报质量边界

R6 只改善 S1 candidate-chain qualification，不会自动解决 R17：

- reader-visible citation/source appendix；
- 14/9/4/10 crosswalk consumption；
- typed WWC operational register；
- fact density/repetition；
- 02B qualified-human 0/16；
- formal 8D invalid。

Fresh R6 reviewer 必须再次把“R6 工程 verdict”和“R17 研报 verdict”分开计数。即使 R6 PASS，也只能解冻后续受控 route 规划，不能直接写新报告或判产品通过。

## 7. 阶段顺序与停止条件

1. 完成本计划并写入 Project OS。
2. 实现 R6-01/02/03/04 与 targeted tests。
3. 用 immutable R5 raw execution 做零模型 full-corpus R6 preview；不写 R6 result/receipt。
4. 若任一新 attack、正例 recall、current target cause、privacy schema 或 coverage 不可解释，停止在 R6 implementation，不签 policy。
5. 全仓门通过后，clean implementation commit/push；再单独 policy commit/push。
6. 只有 clean `HEAD==upstream`、parent/path/input/output/disk 全 exact 才消费一次 R6 attempt；失败后同 attempt 不重试。
7. 作者 exact recompile/reprojection 与 immutable result commit 后，启动另一个全新 fork-none read-only reviewer。
8. Fresh R6 audit PASS 前，所有下游 authority 继续 false。
