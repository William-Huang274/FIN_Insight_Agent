# FIN 0.1 S3-T09 segmented transport v2 字段级文本合同修复

日期：2026-07-22

## 授权与边界

用户以“授权”只允许 `S3-T09-OWNER-GRADE-V3-SEGMENTED-FIELD-LOCAL-TEXT-CONTRACT-AND-SAFE-SUBTYPE-TELEMETRY-ZERO-CALL-IMPLEMENTATION`。本轮只实现代码、fake Provider fixtures、canonical 安全持久化回归与项目账本收口；没有签发或消费 admission，没有真实模型、Provider、网络、source、tool、canonical business execution、paired comparison 或 Human Review。

## 实现结果

新增独立 transport `fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v2`，没有改写历史 v1。canonical output 仍为 `fin01.s3.bounded_agent_three_cell_output:v3`，本地 narrative 上限仍为 320 Unicode 字符，未来精确执行预算仍为 12 calls / 16200 output tokens。

v2 在 facts、explanation、remaining gaps、Claim Cards 与 WWC 的 narrative 字段旁直接表达非空 string/≤320 合同；system instruction 要求逐字段响应前检查并优先使用简洁 typed boundary。validator 不做 truncate、trim 成合法、coerce、drop、join 或 split；发现首个非法 segment 即停止。

新增 closed `segmented_specialist_text` telemetry。只允许五个字段族、三个 subtype（非 string、空白、超 320）和 failing count；不保存 raw text、item index、任意 key name 或 private reasoning。canonical allowlist 只接受精确闭合结构，并拒绝额外 raw text；与既有 strict parse / segment shape telemetry 保持单一族互斥。

## 验证与产品判断

实现专项为 11 个测试：v1/v2 提示隔离、v2 正例 12 次假调用/六逻辑节点/九 Artifact family、五个字段族的第 1/1/1/2/3 次调用 earliest-stop、三个 subtype、结构错误不误归类为文本错误、v1/v2 admission 区分及结果/下一授权冻结。canonical integration 另含安全持久化正例和 raw-text 负例。首轮独立全量 S3-T09 发现 5 个历史/current 状态断言滞后（实现、telemetry、canonical 行为均未失败），修正后五文件定向 `26 passed`；代码复读再收紧结构/文本 validator 所有权，最终聚焦组合 `33 passed`、完整 S3-T09 `139 passed in 272.55s`。`compileall`、JSON/JSONL parse、`git diff --check` 与 Project OS closeout scoped preflight（0 open blocker）均通过。

产品能力提升仅限 Provider 合同稳健性和可审计诊断；研究质量没有提升，新增 Artifact/Evidence/Numeric/Alpha 均为 0。fixture 不能证明 DeepSeek 会遵守 v2，也不能证明 owner-grade 研究产品合格。RC-P36-039 已到“v2 fixture-proven，待 fresh proof decision”；RC-P36-037、T09、T10、S4、release 与 production 继续 blocked。

## 下一项

当前唯一下一项为 `S3-T09-OWNER-GRADE-V3-SEGMENTED-TEXT-CONTRACT-V2-FRESH-AGENT-PROOF-DECISION`，需单独授权。它只能零调用冻结新 WorkUnit/Attempt/Run identity、exact input、12-call/16200-token/USD ceiling、retry-zero、nonreuse、baseline blinding 与首错停止合同；不得在同一授权中签发、执行、比较 baseline、Human Review 或进入 T10。
