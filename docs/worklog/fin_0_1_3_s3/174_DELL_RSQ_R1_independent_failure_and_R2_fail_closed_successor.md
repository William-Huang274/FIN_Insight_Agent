# S3 工作记录 174：DELL-RSQ R1 独立审计失败与 R2 fail-closed successor

日期：2026-08-25

状态：`R1_independent_FAIL_immutable / R2_materialized / fresh_reaudit_pending / G1_false`

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
