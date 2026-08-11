# 121 - P38 Canonical / Legacy engineering handoff baseline

记录时间：2026-07-11

## 用户要求

在讨论新需求和新功能前，先完成旧工程到新工程的交接基础：

- 建立 Canonical Object Registry；
- 建立 Legacy Mapping Matrix；
- 拆分 pytest Test Profiles；
- 不新增 PRD/TECH 需求；
- 不把交接合同误写成新 runtime 已实现。

## 完成内容

### Canonical Object Registry

新增 `configs/engineering_handoff/canonical_object_registry_v0_1.json`，冻结 28 个对象，覆盖：

- control：TaskRun、WorkUnit、Attempt、EventEnvelope、ArtifactVersion；
- research：DecisionSurfaceContract、DecisionSurfaceCell、EvidenceSlot；
- evidence：EvidenceRequest、CandidateBundle、PromotionDecision、NumericProgramTrace；
- repair：GapRecord、RepairTicket、RepairAttempt、GapResolution；
- context：ContextSnapshot、ContextSelectionDecision、ContextInjectionPlan；
- judgment：DomainCellJudgmentPack、DecisionSurfacePack、LeadReviewDecision、WriterAdmission；
- release/evaluation：ReviewAction、ApprovalDecision、ReleaseTransaction、EvalSubject、FailureAttribution。

每个对象登记 identity、version、owner、target store、producer/consumer、dependency 和 runtime write status。全部固定为 `not_cut_over`，因此 registry 只完成身份和所有权交接，不代表 runtime 已切换。

### Legacy Mapping Matrix

新增 `configs/engineering_handoff/legacy_object_mapping_matrix_v0_1.json`，建立 28 条映射，覆盖当前 R53-R60、multi-agent、P34-P36、ContextEngine、Workbench、eval 和 Project OS 资产。

固定规则：

- legacy store 在 cutover gate 前继续拥有写权限；
- adapter 只允许 `legacy_to_canonical`；
- 禁止 canonical -> legacy -> canonical roundtrip；
- 每条 mapping 明确 information loss 和 cutover gate；
- cutover 需要 identity/version parity、shadow diff、trace、rollback 和 legacy read-only 证据。

### Test Profile Split

新增 pytest markers、测试 profile registry 和 collection hook。当前 1,953 个 test items 分类为：

- `fast_contract`：1,937；
- `fixture_integration`：7；
- `frontend_e2e`：4；
- `full_chain`：2；
- `local_data_integration`：3；
- `paid_model`：0。

默认 `pytest` 行为没有改变，避免交接阶段静默隐藏测试。已知受本地数据影响的 3 个 specialist tests 和 2 个 chain performance items 现在可以被显式隔离，但原有失败仍保留在 RC-P38-001 中。

### 可执行治理

新增：

- `src/sec_agent/engineering_handoff.py`；
- `scripts/engineering/build_engineering_handoff_baseline.py`；
- `tests/test_engineering_handoff.py`；
- `tests/conftest.py`；
- `data/manifests/engineering_handoff_summary_v0_1.json`；
- `data/manifests/test_profile_collection_v0_1.json`；
- `docs/architecture/repository/ENGINEERING_HANDOFF_BASELINE_20260711.zh-CN.md`。

## 验证

- registry/mapping/profile cross-validation：pass；
- canonical objects：28；legacy mappings：28；runtime cutovers：0；
- full pytest collection：1,953 items，全部获得唯一 execution profile；
- fixture integration + frontend E2E：11 passed；
- handoff + repository governance tests：6 passed；
- full default pytest：1,941 passed / 12 failed，失败集合与交接前一致，新增回归 0；
- 12 failures 的 profile attribution：local-data 3、full-chain 1、fast-contract 8；fixture/frontend 0；
- 未运行 paid model；
- 未运行 broad full-chain；
- 未修改 PRD/TECH 文档；
- 未切换任何 runtime write path。

## 后续边界

下一步讨论新功能前，工程上已经有稳定的新旧交接入口。实际迁移某个对象时必须新增对应 adapter、shadow projection 和 cutover evidence；不能仅把 registry 状态改成 active。
