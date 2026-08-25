# S3 工作记录 174：DELL-RSQ R1/R2 独立审计失败与 R3 fail-closed successor

日期：2026-08-25

状态：`R1_R2_independent_FAIL_immutable / R3_clean_materialized / fresh_reaudit_pending / G1_false`

## 1. 为什么不能把 R1 追认为通过

Owner 要求实现后由一个干净 subagent 同时审计工程和研报质量。无历史上下文继承、只读、零网络、
零模型的 reviewer 审计 immutable commit
`4cce5d51d6a138391b9627698bec9de171ec4470`、tree
`f9104073f1d023fefa463974999e228a8f14dfd7`，结论为：

- `P0/P1/P2/P3 = 1/2/1/0`；
- engineering/evidence pipeline：`FAIL`；
- crosswalk research quality：`FAIL`；
- report research quality：`OPEN_NOT_ASSESSABLE`；
- qualified-human：`FALSE_NOT_GRANTED`；
- `G1=false`。

R1 的实际 14／9／4／10 内容、SHA、自摘要和当时的 Git blob 值都碰巧正确，但下面四项 gate 不具
fail-closed 证明力：

1. **P0 baseline trust seal**：`frozen_counts` 只和硬编码值比较，没有从绑定输入复算；tracked
   binding 只要求 commit/blob 非空，没有验证原始 bytes、repository clean filter 后的 blob 和
   `commit:path` blob 三者一致。内存中把 Evidence 55 改成 54 或伪造 40-hex Git identity，重算
   自摘要后仍可通过。
2. **P1 projection seal**：三投影只比较 digest 字符串，没有从 audit canonical content 重算并
   确定性重建 model/reader；删除 reader 的 product-profit null 仍可通过。
3. **P1 quality protocol**：没有精确冻结 research-as-of、八维身份及 0–4 范围、P0–P3 meaning/
   blocks、reason-ref schema、required report surfaces 和 immutable target contract。
4. **P2 axis separation**：未被当前单元选择的 5 个 gap 同时把
   `unit_selection_state` 和 `technical_chain_state` 写成 `not_selected_by_unit`，合同声明的正交轴
   没有真正实现；两个枚举也没有被 validator 消费。

R1 public/private 产物和 v1.0 governance 文件均保持不可变，不覆盖、不删改，也不把这次失败生成
新的产品版本。

## 2. R2 最早责任层修复

新增 append-only verification：

- `configs/research/evals/fin_ia_0_1_3_dell_source_report_quality_baseline_verification_v1_0.json`。

它冻结 R1 失败 target、四项 findings、R4 successor result、R4 Evidence Gate 和 v1.0 baseline，
并把 12 项基线计数及三项 narrowed gap ID 作为复算目标。R2 没有修改预注册的 v1.0 rubric、protocol、
authority template 或 crosswalk policy，只加强执行 validator 和新 attempt identity。

`src/sec_agent/research/report_gap_crosswalk.py` 的修复：

- 从 Pack Evidence/gaps、R4 coverage/gate、R38 cards、R17 groups/refs、ProductReadiness public/private
  requests/review packet 和 S2 bridge receipts 实际复算全部 12 项 frozen counts，并同时要求
  `actual == manifest == verification == frozen contract`；
- tracked 输入同时验证 raw SHA-256、同一 raw bytes 经 repository clean filter 的 Git blob 和历史
  `commit:path` blob；commit/path 不存在、object 非 blob 或任一不一致均失败；
- 对完整 quality protocol exact-validate：as-of、immutable target、L1/L2 packet、八维身份/范围/
  阈值、P0–P3 meaning/blocks、三 verdict、reason-ref、报告必需 surface、scoring authority 与冻结
  R17 baseline；
- 从 audit 投影重建 canonical content 并重算 content digest，再按白名单确定性重建 audit/model/
  reader 三投影；PVM 和独立 product-profit 两个 null 都必须对读者可见；
- `technical_chain_state` 只允许 `technical_chain_closed` 或
  `technical_chain_not_evaluated`；`unit_selection_state` 只允许 selected/not-selected，并校验允许组合、
  dynamic ref 和 Writer group/ref membership。

`scripts/research/materialize_dell_report_gap_crosswalk.py` 默认改为新 attempt：

- private `data/workbench_private/fin_0_1_3_report_gap_crosswalk/dell-r2/full_result.json`；
- public `configs/research/evals/fin_ia_0_1_3_dell_report_gap_crosswalk_result_v1_1.json`；
- R1 失败收据、verification binding 和三项新 acceptance receipt 都进入 R2；
- 输出继续 exclusive-create，且只允许 clean worktree materialization。

## 3. 新增负向证明

定向 crosswalk tests 从 17 增至 25；与 S2 product bridge、R17 successor 合计 `36 passed`。新增覆盖：

- Evidence `55→54` 与 R4 coverage 的实际复算不一致；
- 任意伪造 tracked Git commit/blob；
- quality protocol as-of、八维 identity、reason refs、P1 blocks、immutable R17 漂移；
- 未选择 gap 再次把 technical axis 写成 `not_selected_by_unit`；
- audit 内容改变后只同步三处 digest 字符串；
- reader 隐藏 PVM null 或 product-profit null。

Windows 工作树的 CRLF 与 Git blob 的 LF clean-filter 差异已显式纳入测试和实现，不能再把 raw-byte
Git SHA-1 误当成仓库 blob。

本工程 successor 的全仓门为 `1309 passed, 2 skipped, 2 warnings`（两条 warning 均为既有 SWIG
deprecation）；compileall、pyflakes、Project OS JSONL parse、JSON parse、secret pattern scan 和
`git diff --check` 通过。

## 4. 当前门与后续

当前只是作者工程 successor。必须先形成 clean immutable commit，再零调用 materialize R2；随后由
另一名无上下文继承的 fresh read-only reviewer 复跑上述四类 mutation 和读者解释检查。只有新审计
没有 material finding，才可签 `independent_review_pass=true` 和 `G1=true`。

本修复仍未 admission 4 requests／16 human items，未执行 residual source ladder，未新增或关闭任何
研报信源，未重编 Pack／Readiness／S2，未运行 embedding、reranker、Agent 或 Writer，也未修复 R17
reader citation、WWC 或生成新研报。因此 S1／S2／S3、report quality、qualified-human、product、
publication 和 release 继续为 false。

## 5. Clean R2 materialization

工程 successor commit：`324bf2bc4a9529981b5015126737f0193c00823d`；tree：
`119ff18f11177bb2790aec4939e362a2e6988215`。物化前工作树 clean。GitHub HTTPS 443 当时不可达，
所以该 commit 的第一次 push 失败且没有远端变更；本地 immutable identity 不受影响，远端同步继续
作为交付边界保留。

2026-08-25T13:28:43+08:00 exclusive-create R2：

- public：`configs/research/evals/fin_ia_0_1_3_dell_report_gap_crosswalk_result_v1_1.json`；
- private：`data/workbench_private/fin_0_1_3_report_gap_crosswalk/dell-r2/full_result.json`；
- content digest：`f2ab679522d15ba9fe22e3f17b0010a032a4fb142fa918b56b5d344c47b8afc2`；
- public result digest：`3678204233d595df3090dd6526d19ebb4cdd748f6d5ead57ae344e6ba85a85e6`；
- public file SHA-256：`365471c0a3c2a9e5a12134eb6726b25f00d2846dcd2a855cce5cb691201b12f0`；
- private full result digest：`f9a1eaab3b97f3e4059ac11ae9c99a03cc37f072f6aec9643decee9879bc144f`；
- private file SHA-256：`06bbf47abde9ae989a3a93a6c5751d366c59059b939b2dcf7ea1821d8e984eae`。

用保存的 `recorded_at`、`prepared_from_commit` 和同一 private output ref 重新执行内存编译，public 与
private 两份对象均逐字段完全相等（`R2_exact_recompile_ok`）。

R2 acceptance 明确记录 R1 independent failure、12-count actual recomputation 和 tracked
`commit:path` blob verification 为 true；fresh independent review、G1、S1/S2/S3、product、
publication 和 release 全为 false。下一动作只允许提交这份新 public receipt 后，对 immutable R2
执行 fresh read-only re-audit；不能先进入需要 G1 的后续 live。

## 6. R2 fresh author-separated re-audit：唯一 P2，G1 仍失败

第二名无历史上下文继承的 reviewer 全程只读审计 immutable target
`1f3c3a5b93b96cd93650a443c5337cc89cd48ca6`、tree
`516b3f2634fc056354787c890ea0ab30f8b94191`。起止 worktree 均 clean，指定合同为
`36 passed`；public/private exact recompile、全部 SHA/self digest/content digest、tracked bytes/
clean-filter/`commit:path` blob 和 R1 immutable preservation 均通过。R1 的 55→54、伪造 Git
identity、协议重签漂移、digest-string-only projection drift、private leakage、隐藏 PVM／profit null、
非法 technical/unit 轴、缺 dynamic ref 和 Writer membership 攻击也全部 fail closed。

唯一 material finding 为 `R2-NEW-P2-01 candidate_packet_actual_recount_incomplete`：当前 private
packet 的底层对象逐项确实为 18 个 review item、16 个 `human_review_required=true`，且 request 小计、
唯一 ref/digest 均正确；完整文件改写也会被 frozen SHA/blob 拒绝。但
`_recompute_baseline_counts()` 对最后两项仍取 public/private summary。纯内存删除一个需人工 review
的 nested item、保留 summary 后，真实值变成 17/15，函数仍返回 18/16。因此 R2 的
`baseline_actual_counts_recomputed=true` 声明过强，12 项中末两项没有得到所声称的底层重算证明。

固定 verdict：

- `P0/P1/P2/P3 = 0/0/1/0`；
- engineering/evidence：`FAIL`；
- crosswalk content：`PASS_BOUNDED_CONTENT_ONLY`；
- report quality：`OPEN_NOT_ASSESSABLE`；
- qualified-human：`FALSE_NOT_GRANTED`；
- `G1=false`。

R2 public/private/v1.1 均保持不可变；内容正确不能抵消验收证明不实，也不能进入需 G1 的 human
admission、动态 Agent 或 Writer。

## 7. R3 同阶段 fail-closed successor 实现

新增 append-only verification v1.1：

- `configs/research/evals/fin_ia_0_1_3_dell_source_report_quality_baseline_verification_v1_1.json`；
- verification digest：`232be552ae24de61c92069d0b40dc5932216d8fcd48eac05336a5adb83c57c87`；
- 精确绑定 predecessor verification v1.0、R1/R2 failed public result、两次审计 findings 和 R4
  disposition inputs；不覆盖任何前代治理或结果文件。

R3 的 `_recompute_baseline_counts()` 现在：

- 要求 candidate packet、public readiness、private readiness 的 8 个 request ID 集合完全一致，并
  逐 request 对齐 facet/slot；
- 从每个 request 的 nested `review_items` 实际计数 review item 与 human-review flag，不再读取摘要
  作为 actual；flag 必须是真正的 boolean；
- 校验每 request 及 top-level 的 item/human/issue-class 小计；
- 校验 review-item ref 与 digest 全局唯一、item/request/packet canonical self digest；
- public summary 必须与已实际重算的 private packet 的 schema/status/counts/issue classes/digest 一致。

新增两组 attack proof：保留陈旧 summary 时，nested deletion 与 human-flag toggle 必须立即失败；
同步重签所有 summary/digest 时，函数分别真实返回 17/15 与 18/15，随后会与 frozen 18/16 基线不等，
不能冒充通过。crosswalk 定向从 25 增至 29，与 S2/R17 相邻合同为 `40 passed`；全仓为
`1313 passed, 2 skipped, 2 warnings in 327.51s`，两条 warning 仍是既有 SWIG deprecation。
compileall、精确 pyflakes 和 `git diff --check` 通过。

materializer 默认已前移到不可覆盖的 `dell-r3/full_result.json` 与 public v1.2；R3 acceptance 新增
R2 failure 和 `candidate_packet_actual_counts_recomputed`，仍保持 independent review、G1、S1/S2/S3、
report/product/publication/release 为 false。本节只是作者工程 successor；必须先形成 clean immutable
implementation commit，再 exclusive-create R3 并由第三名 fresh read-only reviewer 复审工程、
crosswalk 内容和研报质量边界。

## 8. Clean R3 materialization

R3 工程 successor commit：`883b0e467a43ccf542b3c02f77e265f55befeb30`；tree：
`4f158ecf0a144e0d1faf5a60e38fa1c26819e329`。提交后工作树 clean；向 GitHub HTTPS 443 push 再次因
连接失败而没有产生远端变更，本地 immutable identity 不受影响。

2026-08-25T14:18:05+08:00 exclusive-create R3：

- public：`configs/research/evals/fin_ia_0_1_3_dell_report_gap_crosswalk_result_v1_2.json`；
- private：`data/workbench_private/fin_0_1_3_report_gap_crosswalk/dell-r3/full_result.json`；
- content digest：`f2ab679522d15ba9fe22e3f17b0010a032a4fb142fa918b56b5d344c47b8afc2`；
- public result digest：`afc37e760cd88c107365e727d10b53694b299f93c4245cf90110775ec22676e2`；
- public file SHA-256：`990972fc1acb62696f0bebbc12713e100597271ec562424296cf8d220ff577f5`；
- private full result digest：`c31a51cf7b2252f94f66cdfff96d0263cb850835ab4d1ea264e1e217085849b9`；
- private file SHA-256：`61e627686bae188cfe9f3d58e95cbf230ac4195b855b9fb829975c6dda608880`。

R3 content digest 与 R2 相同是预期行为：本 successor 修的是 baseline actual-count proof，不改写
14/9/4/10 的研究内容。用保存的 `recorded_at`、`prepared_from_commit` 和同一 private ref 重新编译，
public/private 均逐字段完全相等；物化后定向＋相邻合同仍为 `40 passed`。

R3 execution 的 model/provider/network/embedding/reranker/candidate/Evidence/gap-closure 均为 0；
acceptance 保留 R1/R2 independent failure，声明 nested count 已实际重算，但 fresh independent review、
G1、S1/S2/S3、report/product/publication/release 仍全部 false。下一合法动作是提交 public v1.2 收据并
对该 immutable target 做第三次 fresh author-separated read-only audit；不能将作者物化追认为 G1。

传输后续更正：物化记录 commit `5f256f61fda5b2caad6898cf2b8bd2c7b63406de`、tree
`f9e2194181902518f518bea350248430b80637e0` 形成后，GitHub 连接恢复；此前积压的四个本地提交已成功
推送到 `origin/codex/fin013-dell-s1-s2-product-bridge`。早先两次 443 失败仍保留为当时的真实传输
证据，但“远端待同步”边界已关闭。
