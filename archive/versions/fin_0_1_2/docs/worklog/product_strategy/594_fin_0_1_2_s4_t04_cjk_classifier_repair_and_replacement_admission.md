# FIN 0.1.2 S4-T04 CJK classifier 修复与 replacement admission

时间：2026-08-04

## 结果

RC-P36-116 的同源边界问题已在零调用范围内修复。`C001有`、`C002（...）`、`Claim_17`、`fact#004` 等 request-local ID 现在按 ASCII 标识边界识别，不再因相邻中文字符被拆成重要数字；CJK 相邻 ISO 日期与报告期也使用相同边界以保留准确 typed classification。金额、百分比、期限、未知日期和嵌入 ASCII identifier 仍 terminal fail-closed，未放宽财务数值硬门禁。

聚焦 classifier 26 tests、T04 集成/runner/三案例/产品表面 47 tests、R2 admission 与完整 fake 9-Artifact 2 tests 均通过。R1 admission、captures、typed terminal 和 0 Artifact 失败事实保持不可变。

## R2

新的 execution identity 为 `fin012-s4-t04-nvda-current-evidence-replacement-exact-live-r2`，admission digest=`b6d66b68…180e`。它继续绑定 DeepSeek Pro、9 calls、retry=0、USD 0.06、同一 current Evidence pack，并预测新的 WorkUnit/Attempt/Run。admission 已签发但未消费。

下一步只允许从 clean/synced HEAD 做 zero-call preflight 后 exact-once 执行 R2。成功仍必须独立验证 9 Artifacts、L1–L4、Agent 增益与 owner 产品结论；失败首错停止且不自动进入 R3。
