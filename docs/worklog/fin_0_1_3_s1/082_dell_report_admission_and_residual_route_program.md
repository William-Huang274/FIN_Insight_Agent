# S1 工作记录 082：DELL 研报 Evidence admission packet 与 residual route program

日期：2026-08-25

状态：`DELL-RSQ-02A/03A author implementation complete / 21 targeted tests pass / clean materialization and independent audit pending`

## 1. 先纠正 4 请求／16 human item 的口径

冻结执行程序写的是“4 请求／16 human item packet”。重新从 ProductReadiness v1.7 的 private
`candidate_review_packet` 逐 request、逐 item 复算后，实际集合是：

- 8 个产品请求、18 个 review item；
- 其中 16 个 `human_review_required=true`，分布在全部 8 个请求；
- 4 个 `blocked_by_evidence_admission` 请求各有 2 个 human item，共 8 个；
- 其余 8 个 human item 分布在 3 个 partial 和 1 个 ready 请求。

因此不能把冻结短语解释成“4 个 blocked 请求各有 4 项”。本轮不改写已冻结、SHA 为
`5bbb5269...ae4f0d` 的 program source，而是形成双集合合同：

1. `all_human_required_decision_set = 8 requests / 16 items`：G2 必须由 qualified human 对全部
   16 项逐项决定；
2. `four_request_readiness_blocker_subset = 4 requests / 8 items`：只解释当前四个 readiness block。

这项纠正登记为 `RC-S1-065`。它不减少 human work，也不授予 Codex、模型或 Harness 任何
`accept/reject/rebind/defer` 权限。

## 2. DELL-RSQ-02A 工程实现

新增：

- `src/retrieval/dell_report_evidence_admission.py`；
- `configs/retrieval/fin_ia_0_1_3_s1_dell_report_evidence_admission_program_v1_0.json`；
- `scripts/data_retrieval/materialize_dell_report_evidence_admission_packet.py`；
- `tests/test_dell_report_evidence_admission.py`。

实现从 G1 audit、crosswalk、ProductReadiness public/private、R17 private report 和 immutable execution
program 的精确 SHA/digest 编译 identity-sealed packet。每个 human item 都保留：

- review ref/digest、compiled object、source record、lineage/surface digest；
- source owner、research subject、source type/tier、publication/reporting period、section、locator；
- private-only bounded excerpt 和 citation/redistribution right；
- route membership 与 advisory-only rank trace；
- request/facet/slot requirement alignment hypothesis；
- 对 R17 `WPCLAIM` 的 material support/limit/context 用途与 forbidden inference。

公开 manifest 不含 excerpt、source URL 或完整未授权原文。embedding/ranker 只能保留发现顺序，不能
成为 admission 理由。每个 item 的 decision 都保持未填；qualified-human schema 要求 reviewer identity、
时间、理由、Evidence Role、claim-use、period、polarity、authority 和 license/citation right。

## 3. DELL-RSQ-03A 工程实现

新增：

- `src/retrieval/dell_report_residual_source_program.py`；
- `configs/retrieval/fin_ia_0_1_3_s1_dell_report_residual_source_ladder_policy_v1_0.json`；
- `scripts/data_retrieval/materialize_dell_report_residual_source_program.py`；
- `tests/test_dell_report_residual_source_program.py`。

03A 对 14 个 Pack gap 全量分区，并额外纳入独立 S2
`dell-gap-product-profit-attribution`：

- 8 个 Pack gap 有 source-acquisition target；独立产品利润再加 1 个，共 9 个 target；
- demand durability、AI working capital、product profit 三项与 02A 未决候选重叠，当前 held；
- capacity release、utilization/yield、HBM supply、ASP、units、supplier-to-Dell read-through 六项仅形成
  后续 03B internal-chain／bounded 03C 的计划，当前仍没有执行 authority；
- PVM 是 ASP/units/mix 的 derived dependency，不另抓网页；两个 S3 threshold 留在 S3；price-in、
  valuation basis、scenario sensitivity 留在后续 valuation scope。

每个 target 都具备七层路线：local data/object/index/SQL、official issuer/regulator、named customer、
named supplier、industry primary、product/procurement/deployment、trusted context/counter；每层都有
target proposition、subject、owner、time、source role、forbidden inference、max attempts、capture、
fallback 和 stop。

旧 external ladder 的 22 个 fresh provider query 被精确绑定为 predecessor。所有 target 必须先复核
已有 capture/object/candidate，禁止把旧 query unit 原样作为 fresh call 重跑。budget exhaustion、未审
candidate、抓取或解析失败都不能冒充 proved information boundary。

## 4. 4B embedding 与 reranker 没有被删除

03A 的 downstream 03D 条件合同同时保留：

- BM25＋Qwen3-Embedding-0.6B regression baseline；
- 8GB GPU 上单模型加载、4-bit Qwen 4B embedding shadow challenger；
- target-in-pool 已证明后才允许的 4-bit Qwen 4B reranker。

三节点都有 task-specific `TokenBudgetBasis`、同候选集对照、DELL/MU/NVDA no-case-regression、资源
遥测与 stop 条件。03A 当前 `authority_granted=false`，所以本轮调用为
`network/provider/model/embedding/reranker = 0/0/0/0/0`。

## 5. 当前验证与下一门

定向测试：

- 02A：`10 passed`；
- 03A：`11 passed`；
- 合计：`21 passed in 1.31s`。

覆盖 scope 误读、nested item 删除/flag 漂移、input SHA、item digest、R17 claim membership、public
excerpt/URL 泄漏、14-gap partition、admission overlap、63 route contract、旧 22-query 重跑、4B/reranker
authority、dirty worktree 和 output collision。

随后工程门全部通过：

- 02A/03A＋crosswalk＋candidate review＋external ladder＋S2 bridge＋R17 相邻合同：
  `75 passed in 11.69s`；
- 全仓：`1334 passed, 2 skipped, 2 warnings in 458.19s`；两条 warning 是既有 SWIG
  deprecation；
- compileall、精确 pyflakes、`git diff --check` 通过；
- active baseline：`213 Python / 8 frontend / 5 detectors / 28 resources / 0 forbidden`；
- `1116` 份 config JSON、8 个 Project OS JSONL／`1191` 行通过；
- secret scan：`8073 files / 0 findings`；
- frozen execution program SHA 保持
  `5bbb52691fd183bae5c61c6d6dd1b119544e76ffa2625a42dcb1297bd1ae4f0d`。

下一步是形成 clean implementation commit。随后 exclusive-create 02A private/public，提交公开
manifest；在 clean 状态下用该 manifest 物化 03A program。最后由无历史上下文
的 author-separated read-only subagent 同时审计工程、Evidence 边界和研报 claim-use/来源质量。

在 qualified human 完成 16 项决定前，G2、02C、Pack promotion、Readiness/S2 重编、动态 Agent、Writer、
report quality、S1/S2/S3、product、publication 和 release 均保持 false。
