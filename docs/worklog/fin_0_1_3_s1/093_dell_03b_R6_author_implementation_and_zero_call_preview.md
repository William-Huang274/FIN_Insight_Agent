# S1 工作记录 093：DELL 03B R6 作者实现与零调用全量预演

日期：2026-08-26

状态：`author implementation and zero-call preview pass / R6 policy and attempt not created / fresh audit pending`

## 1. 实际完成的 owning-stage 修复

R6 没有覆盖或重试 R5，而是新增 v1.5 module、runner 与 tests，处理 fresh R5 audit 的三个根因：

- `RC-S1-079`：supplier、capacity、HBM、yield、units 与 ASP 改为 clause-scoped typed proposition。判定同时约束 actor／subject、predicate、object／recipient、affirmative polarity、speculative modality、process identity 与 reported-speech direction；ASP 新增 affirmative quote role。
- `RC-S1-080`：新增 `typed_entity_period_canonical_v2`。`H100/H-100/H/100/H 100`、`XE9680/XE-9680/XE/9680/XE 9680` 分别归一为同一 product-code anchor，产品码数字不再泄漏为普通 number；`FY26/FY2026` 归一为 `fiscal_year:2026`。anchor 只从成立的 typed proposition clause 提取，不把同句 next-process target 作为当前 claim obligation。
- `RC-S0-105`：public projection 从“复制后删五个字段”改为 top-level、target、candidate ceiling、downstream disposition、public package、input binding、execution summary、summary、registry 与 authority 的递归显式 allowlist。未知字段、`model_text`／material sentence／secret／locator、HTTP(S)／`www.` 与绝对本地路径均在 publication 前 fail-close。

R6 还保留 raw occurrence 先赋绝对位置、最多八个绝对相邻 unit、candidate-not-Evidence、configuration price-not-company ASP 与全部 downstream authority=false 的前序边界。

## 2. 冻结攻击与正向控制

定向测试共 `95 passed`，覆盖：

- R4/R5 的 no/lack/denied、not/never/unavailable、failed/rejected/refused、should/will/forecast/anticipated/estimated/planned、pilot/prototype/wrong-process attacks；
- `Dell disclosed NVIDIA shipped`、第三方 reported Dell shipment、`Dell refuted reports`、negative ASP quote；
- 真正 Dell self-report、真实 allocation、observed yield、affirmative quote，以及正例后接无关 AMD negative／component unavailable／next-process target 的 recall controls；
- product-code separator、FY two/four digit equivalence、`15 != 150`、自然语言 `a 100 servers` 不误认 A100、命题槽 anchor；
- target/nested unknown private field、`private_secret_payload`、`source_locator=www...`、allowed-text URL 与绝对路径注入；
- R5 audit/root-cause/input/receipt/result/Git/output/disk execution seal。

R1/R3/R4/R5/R6 相邻合同联合为 `206 passed`。`compileall`、`pyflakes`、`git diff --check` 与 Project OS `82 passed`；全仓为 `1575 passed, 2 skipped, 2 existing SWIG warnings`。Active baseline=`213 Python / 8 frontend / 5 detectors / 28 resources / 0 failures`；`1,146` 个 config JSON、`8` 个 Project OS JSONL／`1,275` 行可解析；repository secret scan=`8,137 files / 0 findings`。

## 3. 1,888／34,199 全语料零调用预演

预演只复用 immutable R5 `raw_execution_receipt`，不执行新 embedding、模型、Provider、网络、03C、4B 或 reranker，也不写 R6 private/public/receipt，不消费 attempt。最终 R6 single-pass 编译与 recursive-allowlist public projection 用时 `224.279s`：

- ASP source/compiled/union/final=`2/2/2/2`，best final rank=`15`；
- supplier=`2/2/2/1`，best rank=`2`；
- capacity release、observed yield、Dell-HBM bridge、Dell company-period physical units 都为 `0/0/0/0`；
- 六 target material coverage gap=`0`，local repair=`0`；
- external-route-required target=`4`，same-pool reranker eligible=`1`，target-specific 4B embedding recall eligible=`0`；
- 所有 Candidate/Evidence/NumericFact promotion、gap closure、S1/S2/S3、report/product/publication/release authority 仍为 false。

R6 与 R5 的 current corpus target counts 完全一致，所以本轮没有把 classifier drift 伪装成检索改进。R6 修复的是新文本和未来 schema 的通用资格，不改变当前两条 bounded observation 与四条 residual-route candidate 的事实状态。

## 4. 仍未完成与下一门

当前尚未创建或签发 R6 policy，也没有 R6 attempt/result/receipt。下一步必须按顺序：

1. 完成 config／JSONL／secret／active-baseline 最终门；
2. clean implementation commit/push；
3. 以该 commit/tree 和 24 个 immutable inputs／14 个 implementation SHA 生成 policy-only authority commit/push；
4. clean `HEAD==upstream`、authority parent exact、free disk 与 output collision 门通过后，只执行一次新 R6 0.6B local query batch；
5. 作者 exact private recompile/public reprojection 后提交 immutable result；
6. 启动另一个全新 fork-none、作者分离、只读 reviewer，同时审 R6 工程/语义/route/privacy 和 R17 研报质量。

R17 的 reader-visible citation/source appendix、14/9/4/10 crosswalk consumption、WWC `0/6` operationalization、事实密度/重复、02B qualified-human `0/16` 与 formal 8D 仍失败。R6 即使通过 fresh audit，也不能自动让 R17、S2、产品、publication 或 release 通过。
