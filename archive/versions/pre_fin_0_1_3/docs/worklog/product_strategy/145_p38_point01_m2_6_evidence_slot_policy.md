# P38 Point 01 M2.6 Evidence Slot Policy Compiler

日期：2026-07-12

状态：`m2_6_full_implemented / calibrated_four_sector_policy_corpus / shadow_only`

## 完成

- 新增 `EvidenceSlotPolicyCompiler` 与 four-sector evidence ontology，将 cell slot 编译为 `CompiledEvidenceSlotPolicy` 或显式 `CompileTimeGapSeed`。
- issuer/parser 缺口与 commercial-only metric 不可用时输出 typed gap；不会以 public proxy 或关系图谱静默替代 exact fact。
- relationship evidence 只能 `bounded_context_only`；source/acceptance/forbidden-substitution 违反 ontology 均 fail-close。

## 校准与验证

- `run_point01_m2_6_evidence_slot_policy_fixture.py` 覆盖 AI/Semis、SaaS、Healthcare、Banks ready issuer slot，以及 parser gap、relationship overreach、commercial-data gap 负例。
- `tests/contract/test_point01_m2_evidence_policy.py`：`4 passed`；runner、runtime 和 tests `compileall` 通过。
- model/external call 为 0；gap 是 compile-time policy output，不是已取得的 Evidence。

## 边界与回滚

- 不检索、解析或晋升真实 evidence，不写 legacy/canonical runtime state，不运行模型或 Writer。
- 回滚为移除 ontology/compiler/fixture/tests；不会令关系图谱获得 primary-source authority。
