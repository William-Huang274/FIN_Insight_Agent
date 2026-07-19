# Canonical / Legacy 工程交接基线

日期：2026-07-11

状态：`pass`。本文件是工程交接记录，不新增 PRD/TECH 需求，不表示 canonical runtime 已切换。

## 1. 交接结果

- Canonical objects：28。
- Legacy mappings：28。
- Runtime cutovers：0。
- Test files：268。
- Collected test items：1953。

| Canonical domain | Objects |
| --- | ---: |
| `context` | 3 |
| `control` | 5 |
| `evaluation` | 2 |
| `evidence` | 4 |
| `judgment` | 4 |
| `release` | 3 |
| `repair` | 4 |
| `research` | 3 |

| Test profile | Files by default file rule |
| --- | ---: |
| `fast_contract` | 262 |
| `fixture_integration` | 4 |
| `frontend_e2e` | 1 |
| `full_chain` | 1 |

| Test profile | Collected items |
| --- | ---: |
| `fast_contract` | 1937 |
| `fixture_integration` | 7 |
| `frontend_e2e` | 4 |
| `full_chain` | 2 |
| `local_data_integration` | 3 |

说明：node-specific rule 可覆盖文件默认 profile；最终 item 统计由 pytest collection manifest 提供。

## 2. Source-of-truth 规则

1. 当前 legacy store 继续拥有写权限，直到对应 mapping 的 cutover gate 通过。
2. Adapter 方向只允许 legacy -> canonical；禁止 canonical -> legacy -> canonical 循环。
3. Canonical registry 的 `not_cut_over` 是硬边界，不得解释为 runtime 已实现。
4. Cutover 必须有 shadow diff、identity/version parity、trace、rollback 和 legacy read-only 证据。
5. PRD/TECH 仍定义产品和技术 owner；本基线只负责旧资产如何交接，不扩展需求。

## 3. Canonical object registry

| Object | Domain | Owner | Target store | Runtime write |
| --- | --- | --- | --- | --- |
| `TaskRun` | `control` | `TECH_06` | `sql_control_ledger` | `not_cut_over` |
| `WorkUnit` | `control` | `TECH_06` | `sql_control_ledger` | `not_cut_over` |
| `Attempt` | `control` | `TECH_06` | `sql_control_ledger` | `not_cut_over` |
| `EventEnvelope` | `control` | `TECH_06` | `append_only_sql_event_ledger` | `not_cut_over` |
| `ArtifactVersion` | `control` | `TECH_06_TECH_09` | `sql_metadata_plus_immutable_object_store` | `not_cut_over` |
| `DecisionSurfaceContract` | `research` | `TECH_01` | `sql_research_ledger` | `not_cut_over` |
| `DecisionSurfaceCell` | `research` | `TECH_01` | `sql_research_ledger` | `not_cut_over` |
| `EvidenceSlot` | `research` | `TECH_01_TECH_02` | `sql_research_ledger` | `not_cut_over` |
| `EvidenceRequest` | `evidence` | `TECH_02` | `sql_evidence_ledger` | `not_cut_over` |
| `CandidateBundle` | `evidence` | `TECH_02_TECH_03` | `sql_metadata_plus_object_store` | `not_cut_over` |
| `PromotionDecision` | `evidence` | `TECH_02_TECH_04` | `append_only_sql_evidence_ledger` | `not_cut_over` |
| `NumericProgramTrace` | `evidence` | `TECH_04` | `sql_numeric_ledger_plus_object_store` | `not_cut_over` |
| `GapRecord` | `repair` | `TECH_01_TECH_02_TECH_09` | `sql_gap_ledger` | `not_cut_over` |
| `RepairTicket` | `repair` | `TECH_01_TECH_06_TECH_08` | `sql_gap_ledger` | `not_cut_over` |
| `RepairAttempt` | `repair` | `TECH_06_TECH_08` | `sql_gap_ledger` | `not_cut_over` |
| `GapResolution` | `repair` | `TECH_01_TECH_09` | `append_only_sql_gap_ledger` | `not_cut_over` |
| `ContextSnapshot` | `context` | `TECH_07` | `sql_context_ledger_plus_object_store` | `not_cut_over` |
| `ContextSelectionDecision` | `context` | `TECH_07` | `append_only_sql_context_ledger` | `not_cut_over` |
| `ContextInjectionPlan` | `context` | `TECH_07_TECH_08` | `sql_context_ledger_plus_object_store` | `not_cut_over` |
| `DomainCellJudgmentPack` | `judgment` | `TECH_05` | `sql_metadata_plus_immutable_object_store` | `not_cut_over` |
| `DecisionSurfacePack` | `judgment` | `TECH_01_TECH_05` | `sql_metadata_plus_immutable_object_store` | `not_cut_over` |
| `LeadReviewDecision` | `judgment` | `TECH_01_TECH_09` | `append_only_sql_review_ledger` | `not_cut_over` |
| `WriterAdmission` | `judgment` | `TECH_01_TECH_09` | `append_only_sql_review_ledger` | `not_cut_over` |
| `ReviewAction` | `release` | `TECH_09` | `append_only_sql_review_ledger` | `not_cut_over` |
| `ApprovalDecision` | `release` | `TECH_06_TECH_09` | `append_only_sql_review_ledger` | `not_cut_over` |
| `ReleaseTransaction` | `release` | `TECH_09_TECH_10` | `append_only_sql_release_ledger` | `not_cut_over` |
| `EvalSubject` | `evaluation` | `TECH_10` | `sql_quality_ledger_plus_object_store` | `not_cut_over` |
| `FailureAttribution` | `evaluation` | `TECH_10` | `append_only_sql_quality_ledger` | `not_cut_over` |

## 4. Legacy mapping matrix

| Mapping | Legacy object | Canonical target | Mode |
| --- | --- | --- | --- |
| `lm_task_runs` | r53_r60 task_runs and current graph run state | `co_task_run` | `merge_adapter` |
| `lm_node_execution_work_unit` | node_executions and graph node invocation | `co_work_unit` | `semantic_split` |
| `lm_retry_attempt` | node retry counters, writer repair attempts, tool invocations | `co_attempt` | `merge_adapter` |
| `lm_task_workpaper_tool_events` | task_events, WorkpaperEvents, tool ledgers and trace spans | `co_event_envelope` | `merge_adapter` |
| `lm_artifact_refs_render_jobs` | artifact_refs, render jobs and Workbench artifact rows | `co_artifact_version` | `merge_adapter` |
| `lm_research_objective_to_surface` | research objective contract, required item plan and P35 decision surface framework | `co_decision_surface_contract` | `merge_adapter` |
| `lm_dimensions_required_items_to_cells` | analysis dimensions, memo slots and required items | `co_decision_surface_cell` | `semantic_split` |
| `lm_p34_slots_to_evidence_slots` | P34 evidence-slot mapping and required source items | `co_evidence_slot` | `direct_adapter` |
| `lm_retrieval_intent_to_evidence_request` | retrieval intent, retrieval plan and source route plan | `co_evidence_request` | `merge_adapter` |
| `lm_candidates_to_bundle` | retrieval candidates, source bundles, graph hits and parser rows | `co_candidate_bundle` | `merge_adapter` |
| `lm_selected_dropped_to_promotion` | selected evidence, dropped candidates and authority gates | `co_promotion_decision` | `merge_adapter` |
| `lm_exact_derived_to_numeric_trace` | exact-value ledger, derived metrics and numeric lineage | `co_numeric_program_trace` | `merge_adapter` |
| `lm_typed_gaps_to_gap_record` | retrieval gaps, workpaper gaps and unsupported-claim gaps | `co_gap_record` | `merge_adapter` |
| `lm_targeted_repair_to_ticket` | targeted repair requests and lead repair instructions | `co_repair_ticket` | `merge_adapter` |
| `lm_route_tool_attempt_to_repair_attempt` | route executions, tool attempts and repair-loop observations | `co_repair_attempt` | `merge_adapter` |
| `lm_gap_status_to_resolution` | gap accepted, bounded, repaired, superseded and reviewer states | `co_gap_resolution` | `merge_adapter` |
| `lm_context_candidates_to_snapshot` | ContextEngine candidates, graph/skill/memory/evidence packs | `co_context_snapshot` | `merge_adapter` |
| `lm_context_selection_to_decision` | context selected and dropped refs | `co_context_selection_decision` | `direct_adapter` |
| `lm_context_plan_to_canonical_plan` | R53-R60 ContextInjectionPlan and live node prompt payloads | `co_context_injection_plan` | `merge_adapter` |
| `lm_claim_cards_to_domain_pack` | specialist ClaimCards and judgment_candidates | `co_domain_cell_judgment_pack` | `semantic_split` |
| `lm_judgment_state_to_surface_pack` | JudgmentState, aggregate judgment plan and P36 manual matrix | `co_decision_surface_pack` | `merge_adapter` |
| `lm_lead_checkpoint_to_review` | LeadReviewCheckpoint and aggregate validation | `co_lead_review_decision` | `merge_adapter` |
| `lm_writer_gate_to_admission` | memo_writer_allowed, MemoLogicPlan validation and material gates | `co_writer_admission` | `merge_adapter` |
| `lm_workbench_actions_to_review_action` | Workbench reviewer actions and WorkpaperEvents | `co_review_action` | `direct_adapter` |
| `lm_acceptance_to_approval` | reviewer acceptance and approval gate artifacts | `co_approval_decision` | `merge_adapter` |
| `lm_release_gate_to_transaction` | enterprise release candidate and deliverable release status | `co_release_transaction` | `merge_adapter` |
| `lm_eval_runs_to_subject` | eval run rows, fixtures, quality cards and release gates | `co_eval_subject` | `merge_adapter` |
| `lm_failures_to_attribution` | root-cause ledger, eval failure rows and trace observations | `co_failure_attribution` | `merge_adapter` |

每条 mapping 的 legacy refs、information loss 和 cutover gate 以 `configs/engineering_handoff/legacy_object_mapping_matrix_v0_1.json` 为准。

## 5. Test profile 使用

```powershell
pytest -m fast_contract
pytest -m fixture_integration
pytest -m local_data_integration
pytest -m frontend_e2e
pytest -m full_chain
pytest -m paid_model
pytest --collect-only -q --test-profile-report data/manifests/test_profile_collection_v0_1.json
```

默认 `pytest` 行为暂不改变，避免在交接阶段静默隐藏旧测试。CI 默认 profile 的切换应在基线稳定后作为单独工程决策进行。

## 6. Validation

- Error count：0。
- Canonical registry、legacy mapping 和 test profile registry 交叉校验通过。
