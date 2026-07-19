# P38 Point 01 M2-A1 design/package full-contract repair

日期：2026-07-14

状态：`design_package_repaired_pending_independent_review`

## 背景与处置

total reviewer 接受 M1-A1 final reviewer closeout，但拒绝 M2-A1 初版 package `5e464a…2a35c`：初版只冻结了 contract 名称、通用 oracle 和 probe 标题，不能作为 future actual audit 的执行合同。本轮保留 v1 为拒绝证据，不覆盖该 artifact；新增 v1.1/v2 full-contract repair，仍仅是静态设计/package 变更。

## 新冻结内容

- `point01_m2_a1_adversarial_input_corpus_v1_1.json`：四个 sanitized synthetic cases 都提供可序列化 `CaseScope`、`CompilerInputSeed`、`LegacyResearchObjective` 与 `PackVersionMetadata` 值；每个 legacy objective 都有十个具体 required items，pack metadata 与现有 `CompilerInputContract`、`adapt_legacy_research_objective`、`PlanningPackVersion`、`FullSerializerScope` 的字段来源逐项对齐。
- `point01_m2_a1_independent_expected_cell_oracle_v1_1.json`：四行业 oracle 分别冻结 sector pack family/version、archetype family、required/forbidden cells、cell owner、required/forbidden evidence role、cell count、semantic-loss action/tag 和禁止断言；它仍是 post-actual reviewer input，actual 不得 import/read/hash/receive。
- `point01_m2_a1_owner_authority_typed_stop_matrix_v1_1.json`：P01 冻结 oracle separation 与 mutation invariance；P02 冻结 valid baseline、unversioned、stale/superseded、parent/digest mismatch、selector conflict、envelope replay mismatch；P03 冻结 feature-off、model-denied、fixed path、ambient resolver、provider constructor、network/tool transport。每条都有 input ref、mutation、owner、typed stop、actual assertion、independent oracle assertion。
- future topology 规定 actual runner 先输出 immutable actual result digest，oracle evaluator 才能接收该 ref；同时定义 oracle/store/transport/model canary 的接口和 open/read/write/constructor 计数合同。
- repaired package digest-bind A0 digest、Git-index input hashes、corpus/oracle/matrix digest、fixed approval DB fingerprint、canonical/business absence manifest、authority boundary、admission/receipt requirement 和 `actual_probes_currently_authorized=false`。

## 静态 gate

- package ref：`point01-m2-a1-independent-adversarial-audit-package-v2-full-contract`。
- package digest：`34a6877a084bc85aa28d160082661db7d1fc9ca04f44d576afe6bb5d5acc5d89`。
- corpus/oracle/matrix digest：`a11e0498c7befadf8c9a54db5fb0f3106956bfe9e6fea4edc6dda10af7e6581d` / `9dc32c4d02c5b2313a8a4b7bd35cd806672cf963a62a8191128333425a2d4e87` / `ba942471268f6434ab94a5d55901ea1f0c3c968243c6f5fe2c793e4130941cc9`。
- gate：`design_package_repaired_pending_independent_review`，digest=`02d83a8cdce1dbb983efae05a0982a5229802f5e72136e84f7c015b87d5c7ee8`。
- package verifier 先校验 canonical package digest，再校验 Git-index input bytes、A0 digest、corpus/oracle/matrix digest；任何 source、input hash、A0、fixed fingerprint、三类 artifact digest、authority boundary 或 actual-authorized flag 篡改都会 fail-closed。自签 package 即使结构/hash 自洽，仍需 package-external exact total-reviewer admission 才能进入 future actual。

## 验证与边界

- 已运行静态 JSON/`py_compile` 检查，以及 `pytest -q tests/contract/test_point01_m2_a1_design_package_static.py`：`5 passed`。
- 该 suite 只加载 standard-library-only freeze runner；其 AST import guard 明确禁止导入 M2 compiler/shadow/serializer/registry/store runtime。
- gate 记录 compiler/shadow fixture、model、network、tool、provider、store open/write、business Case 和 legacy authority mutation 均为 `0`；fixed approval DB 只作为已知 fingerprint 写入 package，未打开。
- 未运行 M2 compiler/shadow fixture、既有 M2 pytest、PostgreSQL、provider、network、tool、任何 store 或业务/legacy mutation。

## 停止点

下一步只能交 total reviewer 独立审阅本 v1.1/v2 design package。即便通过，未来 A0-M2-P01/P02/P03 actual 前仍必须再次 refreeze executable package，绑定 actual runner、oracle evaluator、canaries、tests 和 exact staged bytes，再获得 exact external admission 与 single-use execution receipt。不得进入 M3、M6/R3 或任何 runtime authority。
