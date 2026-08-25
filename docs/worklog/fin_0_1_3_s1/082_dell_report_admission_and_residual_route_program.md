# S1 工作记录 082：DELL 研报 Evidence admission packet 与 residual route program

日期：2026-08-25

状态：`R1 independent audit failed and preserved / R2 author implementation full gate pass / clean materialization and fresh independent audit pending`

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

## 6. Clean implementation commit 与 Project OS 时间纠正

实现提交：`29b4fc2e108cd9b3d4776ce911f21bca77f05856`；tree：
`ff9520105323d48fe82420ae67febb2ae893160a`；commit time：
`2026-08-25T15:41:22+08:00`。提交后工作树 clean。首次 push 因 GitHub 443 无法连接而失败，
本地分支相对 origin 为 ahead 1／behind 0；没有远端变更。

该提交里的两条 RC-S1-065／capability 作者状态记录误把手填计划时间 `16:30/16:55` 当成
`updated_at/occurred_at`，晚于机器实际时间。代码、测试、输入 SHA、commit/tree 和物化结果不受影响，
但这两条时间不能作为真实 chronology。按 append-only 规则不改写提交，已在机器时间
`2026-08-25T15:43:06+08:00` 追加 `RC-S0-102` 和 capability correction；旧两行只保留为错误记录
证据，其实质状态由纠正行接续。

## 7. 02A exclusive-create materialization

从 clean implementation commit `29b4fc2e...f05856` 物化：

- public manifest：
  `configs/retrieval/fin_ia_0_1_3_s1_dell_report_evidence_admission_manifest_v1_0.json`；
- private packet：
  `data/workbench_private/fin_0_1_3_dell_report_evidence_admission/dell-r1/full_result.json`；
- recorded at：`2026-08-25T15:42:23+08:00`；
- packet digest：`6bcee241c5dc7366b1fde513973448d590dcb30094f6bdc06cd2ed95f651cec7`；
- public result digest／SHA：`199b5d56e7ea419268a56deb333e66fa8c06f46000d3e53c5cab1e10340edcb2`／
  `5af6e9b4028c0ba02642733330db9a8f6ff564073e9d116b984710ba8b3f7306`；
- private result digest／SHA：`d5494b4ea30653792f3d7daf6efab00c0b9dbbcdee09a32f6040c553e9e9950a`／
  `895d340ebdd9e79f4aa8b46344aaf925ed83ead5aa50c3310d946f07cd7ef0f7`。

用相同 `recorded_at`、`prepared_from_commit` 和 private ref 重编，public/private 对象逐字段完全相等；
21 项定向合同复跑通过，公开文件不含 `bounded_excerpt`、`source_url` 或 `https://`。决定计数仍为 0，
G2 与所有阶段／产品 authority 均为 false。

## 8. 03A exclusive-create materialization

02A public manifest 和时间纠正进入 commit
`f66f07d73e976cd7f15bdf3af2e5aaf9b126bd82`、tree
`f13402bc401c7f1177ce4970999ee6cf5c954481` 后，工作树恢复 clean。03A 随后绑定该 commit 与
02A manifest 的 SHA/result/packet digest，exclusive-create：

- output：
  `configs/retrieval/fin_ia_0_1_3_s1_dell_report_residual_source_ladder_program_v1_0.json`；
- recorded at：`2026-08-25T15:45:53+08:00`；
- prepared from commit：`f66f07d73e976cd7f15bdf3af2e5aaf9b126bd82`；
- program digest：`eccc6dfbe421ccc30e0ef0ab500da3e52a7808a722f087f6c48fee55a4788ad8`；
- file SHA：`a2caf24d0e2dd8bddc5bbe9d40ffcbdeb82027273a34c92d05b85de006ced90d`。

用保存的时间和 commit 重编，程序对象逐字段完全相等。结果精确为 14 Pack gap、8 Pack acquisition
target、1 independent S2 product-profit target、9 targets、6 unoverlapped、3 admission-held、6
non-acquisition Pack dispositions、7 route families、63 route contracts。三项 held 是 demand durability、
product profit 和 working capital；所有 locator template 均无 URL/qrel seed。execution 的
network/provider/model/embedding/reranker 均为 0，`G3=false`。

## 9. Fresh author-separated R1 审计失败（不可变保留）

全新、无历史上下文继承、只读且作者分离的审计者检查 immutable commit
`581c1d6e89f27981298d8fd9379bf53b40dc488c`／tree
`55b5c81a80d2db03765f6ec79ffaefb4ffa85e66`，最终 verdict 为 **FAIL**，
`P0/P1/P2/P3 = 1/2/1/0`。开始和结束时 HEAD/tree/index/worktree 完全相同；审计者 0 写入、
0 network/provider/model/embedding/reranker 调用，未签发任何 qualified-human decision。

通过的边界仅是：当前文件 SHA/self-digest、历史 commit:path 绑定、02A/03A exact recompile、当前
`8/18/16 + 4/8` 和 `14 + 1 / 9 / 6 / 3 / 6 / 7 / 63` 快照、三模型节点保留、当前权限全 false、
零执行、时间 append-only 更正以及既有 G1。失败根因是：

1. `RC-S1-066`：02A 只编译 16 个 human rows，未从全部嵌套对象复数 8 requests／18 items；重签后
   删除或修改 non-human item、增加第九个 zero-human request 仍可通过。
2. `RC-S1-067`：至少 10/16 claim-use 存在融资流→OCF、年度→季度、non-GAAP→GAAP、segment→
   company/product、旧期间 WWC 或跨公司无关映射；`forbidden_inference` 不能修复错误的
   `support_if_admitted`，无 material use 的候选不得作为 citation padding 硬挂 R17 claim。
3. `RC-S1-068`：03A 只守数量而未守 exact target↔gap↔held identity；子节点可暗开 authority，
   predecessor 可在 stale digest 下把 22 改成 99，裸域名可绕过 URL guard。

失败回执：
`configs/audits/fin_ia_0_1_3_commit_581c1d6e_dell_02a_03a_fresh_audit_fail_v1_0.json`，
digest `061cd35c...a3ea`。R1 产物不覆盖、不追认为 PASS。

下一合法动作不是 02B 或 03B，而是在 S1 同阶段形成 non-overwriting 02A/03A successor：全量嵌套
重数和 identity seal；逐项 reject/rebind 16 个 claim-use；冻结 exact semantic map；递归零权限；
重验 prior self-digest/22-query 和 URL-like leakage。新 attempt 通过定向、全仓、exact recompile 后，
必须再次交由新的 fresh read-only reviewer 同时审工程和研报来源/claim-use 质量。此前 G2/G3、
S1/S2/S3、report/product/publication/release 全部为 false，上一版研报信源缺口仍未解决。

## 10. 同阶段 R2 作者实现与完整工程门

R1 failure receipt 已先进入独立提交 `6431f69c...`，R1 代码、public/private packet 和 route program
均未覆盖。随后在同一 S1 owning stage 实现 02A/03A R2：

- 02A v1.1 从 public/private ProductReadiness 的全部 8 requests／18 nested items 重新计数，逐项校验
  request/ref/digest/human flag、per-request item/human/issue-class counts、全局唯一性以及 item/request/
  packet 自摘要，并冻结 18 项精确 inventory；删除或改写两个 non-human item、增加第九个 zero-human
  request、切换 human flag，即使同步重签底层摘要也必须失败。
- 16 个 human item 不再强制挂 claim。作者建议分区为 5 个 bounded possible use、10 个
  `reject_no_current_material_report_use`、1 个 exact duplicate rebind；reject/rebind 项必须为空 claim／
  surface。5 个可能用途只保留历史同公司 timing/backlog/mix context、FCF definition boundary 和
  Dell 风险反证，且精确绑定 R17 surface path。所有建议仍不是 human decision，`0/16` 不变。
- 03A v1.1 冻结 9 个 target 的 exact target↔Pack/S2 gap↔crosswalk disposition↔prior proposition↔
  admission overlap map，以及 demand/WWC/product-profit 三个 exact held identity；重算 predecessor
  七命题全部 `50=28 replay+22 fresh` 及 fresh `6/6/10` query units。
- 03A 递归拒绝 nested execution/model/embedding/reranker authority，拒绝 scheme、`www`、裸域名、
  qrel/answer locator；并精确消费 02A 的 16 项 request/claim-use/decision map、18 项 inventory digest、
  execution/authority/lineage。作者自审额外发现“重新签名后交换 admission item request/claim-use”
  仍可能仅靠数量通过，已在提交前补成攻击测试并 fail closed。
- BM25＋Qwen3-Embedding-0.6B baseline、4-bit Qwen 4B embedding shadow challenger 和 4-bit
  Qwen 4B reranker 均保留；candidate ceiling 仍先于 reranker，所有 TokenBudgetBasis authority=false。

R2 配置身份：

- 02A program digest／SHA：`0b34d8f6...fb267`／`57cac427...381c8`；
- 03A policy digest／SHA：`cb0b4d61...fd819`／`ce02b647...92130`；
- frozen execution program SHA 仍为 `5bbb5269...ae4f0d`。

作者工程门：02A/03A 定向 `48 passed`；连同 crosswalk、candidate review、external ladder、S2 bridge、
R17 的相邻合同 `101 passed`；全仓 `1361 passed, 2 skipped, 2 warnings`，warning 为既有 SWIG
deprecation。compileall、pyflakes、diff check、active baseline `213/8/5/28/0`、1121 config JSON、
8 个 Project OS JSONL／1203 行、8078-file secret scan／0 均通过。全程
network/provider/model/embedding/reranker/promotion/gap-closure=`0/0/0/0/0/0/0`。

这只是作者实现通过：尚未物化 R2 public/private/program，尚未 exact recompile，尚未经过新的
author-separated 审计。02B human admission、03B/03C source execution、真实 residual 补源、Pack／
Readiness／S2 重编、新 Writer 和报告质量验收均未发生；上一版研报信源缺口仍未解决，G2/G3、
S1/S2/S3、report/product/publication/release 继续为 false。

## 11. 02A R2 non-overwriting materialization

从 clean implementation commit `8dbdb96356875ba99f0dff829ba49f01e31e3d84`／tree
`c3d658e5e1bee3b259c36e3d2a5bf54f71dfb5b2` exclusive-create：

- public manifest：
  `configs/retrieval/fin_ia_0_1_3_s1_dell_report_evidence_admission_manifest_v1_1.json`；
- private packet：
  `data/workbench_private/fin_0_1_3_dell_report_evidence_admission/dell-r2/full_result.json`；
- recorded at：`2026-08-25T17:19:08+08:00`；
- packet digest：`6ea77971bdb039008df6ebb74294fb5d17cef2d55bc8d3867b78104c53b2882f`；
- public result digest／SHA：`0b74f9698326a4649c3970d5097a65eb0ed3d30bdb8eb7235b0fa5b161f6ab68`／
  `5064dbbc964b4062ec40d29e3258a3effce1ca130df1527bcec85f9ba2954e1f`；
- private full result digest／SHA：`a90ed777fe85956889976aea2baa50d3b2f84f7a058e21e3eacde3f5b1f6c4fd`／
  `9679d9e73668f12fb3e306eb3f5e73723e65a5a97247f74607374367668bcf11`。

用保存的 recorded_at、prepared commit 和 private ref 重编，public/private 逐字段完全相等；公开
manifest 不含 bounded excerpt、`source_url`、HTTP(S) locator 或完整私有来源。结果仍是
8 requests／18 predecessor items／16 human items、4 blocked requests／8 blocker items、建议分区
5/10/1、qualified-human decisions `0/16`；全部调用和 promotion 为 0，G2 及所有 stage/report/product
authority 为 false。该物化不是 02B admission、Evidence promotion、真实补源或研报质量通过。

## 12. 03A R2 non-overwriting materialization

02A public record 进入 clean commit `75d99f8d208282d5d050002bd210454103e46a1d`／tree
`edb1d7a42ea128a7ac8fdbc709485ba87b240a26` 后，03A R2 精确绑定其 public SHA/result/packet digest 并
exclusive-create：

- output：
  `configs/retrieval/fin_ia_0_1_3_s1_dell_report_residual_source_ladder_program_v1_1.json`；
- recorded at：`2026-08-25T17:24:48+08:00`；
- prepared from commit：`75d99f8d208282d5d050002bd210454103e46a1d`；
- program digest：`ed6f11a8fe091d84362d2df041d5ea0bffa50a5c781274f60eaf9e73d6919d50`；
- file SHA：`581c290df98b75fb06fb86842532cdc2c719d235b2aa6524f89f99a534780f64`；
- bound 02A manifest SHA：`5064dbbc964b4062ec40d29e3258a3effce1ca130df1527bcec85f9ba2954e1f`。

保存的 recorded_at／prepared commit 重编后逐字段相等。结果精确为 14 Pack gaps、8 Pack targets、
1 independent S2 product-profit target、9 total targets、6 unoverlapped、3 held、6 non-acquisition、
7 route families、63 contracts；held identity 仅 demand durability、product profit、working capital。
全部 63 个 locator template 的 URL-like/qrel 计数为 0；prior 50 queries／22 fresh 已对账；
network/provider/model/embedding/reranker/capture/promotion/gap closure 全为 0，`G3=false`。

下一门是将本 program 与记录提交为 immutable target，再由全新、无历史上下文继承的只读 reviewer
独立重放 R1 attacks、R2 新增 admission-map attacks、exact recompile，并逐项审 16 个 claim-use 的
period/basis/owner/role/material report use。工程审计必须与研报质量审计分别判定。审计通过也仍不等于
qualified-human 02B、真实补源、S2 重编、Writer 或产品验收。
