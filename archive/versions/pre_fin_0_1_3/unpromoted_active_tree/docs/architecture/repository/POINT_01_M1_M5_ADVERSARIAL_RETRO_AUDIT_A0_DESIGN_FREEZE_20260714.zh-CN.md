# Point 01 M1–M5 对抗性追溯复审 A0：设计冻结

状态：`design_frozen_pending_total_reviewer_audit`
日期：2026-07-14
适用范围：Point 01 的 M1、M2、M3、M4、M5 历史 closeout claim。
本产物不是一次复审执行、不是新的 runtime gate，也不改变任何已有 authority。

机器矩阵：`configs/engineering_handoff/point01_m1_m5_adversarial_retro_audit_design_freeze_v1_0.json`
设计 digest：`75a76e24a3a730b82942b9861b9d203a5ec0e735a936dbc229d1c68681ff250d`

## 1. 决策与硬边界

总审计决定已经接受 M6.3R.2 的 sanitized fixture/evaluator repair，但明确冻结 M6.3R.3。下一步先对 M1–M5 做同等级 adversarial retro-audit。本 A0 只冻结审计设计：不运行测试、runner、runtime、数据库、网络、模型、工具或 mutation。

以下边界在 A0 期间保持不变：

- M1–M5 的已有历史 closeout 不是被撤销，而是统一标为 `historical_claim_retained_pending_independent_adversarial_reaudit`；只有后续 A1 证据才可决定 retain、provisional 或 reject-and-repair。
- M2 仍只主张 deterministic DecisionSurface Planning Shadow；M3 仍只主张 deterministic shadow comparison/calibration；M4 仍只主张 non-production synthetic persistent pilot；M5 仍只主张 local temporary-store durable harness。
- legacy TaskRun/legacy authority 仍为业务 authoritative。不得由 A0 或任何复审测试改变业务 Case、tenant、lane 或 authority。
- R3、真实 adapter/index/graph/SQL/source read、ToolInvocation、网络、provider/model、Evidence/Writer/full-chain、promotion、生产 persistent store 写入、业务 Case mutation、legacy cutover 均禁止。

## 2. 既有 claim 与待审计成熟度

| Milestone | canonical historical claim | 现有主要证据 | 历史成熟度（限定范围） | authority boundary | 首要自证循环风险 | A0 初始处置 |
| --- | --- | --- | --- | --- | --- | --- |
| M1 | `M1_complete`：SQLite-first canonical control kernel、Attempt retry/recovery、artifact/event/replay 与 PostgreSQL logical conformance 已 closeout | M1 closeout/PostgreSQL manifests、M1.1–M1.5 contract suite、reviewer receipt、worklogs 137/138/170 | `full + calibrated`，仅 SQLite-first/PostgreSQL-compatible control slice，非生产服务 | legacy TaskRun authoritative；no compiler/cutover | fixed-hash gate、replay fixture 或 ambient store 可能自证 | `retained_pending_M1_A1` |
| M2 | `M2_complete`：no-model deterministic DecisionSurface Planning Shadow compiler/pack/serialization/orchestration 完成 | M2.0 lint、M2.1–M2.9 runners、M2.10 aggregate gate、four-sector positives/negatives、worklog 151 | `full + calibrated`，仅 shadow/no-model | legacy authoritative；DecisionSurface shadow-only | compiler oracle 与 expected fixture/legacy mapping 共用输入或 digest 漂移 | `retained_pending_M2_A1` |
| M3 | `M3_complete`：shadow comparison、semantic mapping、five-chain/four-sector/negative controls 与 reviewer trace 完成 | M3.0 lint、M3.1–M3.7 fixtures、M3.8 closeout、worklog 152 | `full + calibrated`，仅 deterministic comparison calibration | no M4 switch；no Evidence/Writer/provider | comparison expected result、legacy/canonical projection或 reviewer trace 可形成同源自证 | `retained_pending_M3_A1` |
| M4 | `M4_complete_nonproduction_synthetic_pilot`：synthetic persistent Case 的 request/execute/pinned read/rollback/backup restore 已 store-backed closeout | synthetic pilot result、execution evidence、source/restore verification、M4 synthetic closeout gate、worklogs 153–157 | `full + calibrated`，仅 isolated non-production synthetic persistent pilot | business Case rejected; final authority legacy | approval/evidence JSON、backup/restore 或 event/version projection可能绕过实际 store 事实 | `retained_pending_M4_A1` |
| M5 | `M5_complete_temporary_store_full_calibrated_reviewed`：temporary-store scheduler/recovery/checkpoint/security/budget/HITL/context/observability 与 child-process calibration 已 closeout | 92-file package digest、full human receipt、M5.9 gate、six calibration results、worklogs 158–173 | `full + calibrated`，仅 local temporary-store harness，非常驻生产服务 | no worker service; no provider/tool/Evidence/Writer; no legacy change | package/receipt self-invalidation、same-process substitute、test-induced production access或 calibration JSON 自证 | `retained_pending_M5_A1` |

“历史成熟度”描述已被接受的精确范围，不得外推为 production runtime、真实业务 Case migration、external tool 或 full-chain 能力。

## 3. 统一的 adversarial 审计协议

每个后续 `Mx-A1` 只可在独立总 reviewer 放行后执行，且必须使用下列共同协议。

1. **冻结输入。** 先记录 exact code/config/manifest/result/receipt/store snapshot references 与 SHA-256；缺失或漂移即 `typed_stop:input_snapshot_mismatch`。
2. **双路径裁判。** 被测 runner 不可读取 expected/oracle；oracle 必须独立、只在 runner 输出之后比较。任何 expected/oracle mutation 改变 actual 的情况均为 `typed_stop:oracle_leakage_detected`。
3. **显式依赖。** test、fixture 与 library path 必须注入 temporary store、clock、transport 和 authority；读取 ambient/production store 或创建真实 client 即 `typed_stop:test_runtime_isolation_violation`。
4. **可重放而不可伪造。** owned digest/id 由 canonical serialization 重算；外部 snapshot 必须同时有 registry ref/version/digest/admission state。篡改后仍可 replay 即 `typed_stop:digest_or_replay_tamper_detected`。
5. **只读/零副作用默认。** 除经单个 A1 再批准的 isolated synthetic temporary store 外，network/tool/model/production-store/business-Case/legacy-authority 写入均为 0。任何超额计数为 `typed_stop:execution_budget_or_scope_violation`。
6. **逐 milestone 停止。** M1-A1 结果只能交回总 reviewer；M2-A1 不因 M1 green 自动获准，依此类推至 M5-A1。

## 4. 对抗 probe matrix

`allowed counts` 代表单 probe 的硬上限；`canonical write=0` 既包括 production/fixed approval store，也包括业务 Case。若 probe 的设计需要 isolated temporary write，会在后续 A1 另列 `temporary_write_allowance`，A0 不授予。

| ID | Milestone / owner | adversarial input snapshot | 允许调用/写入计数 | probe 与预期 typed stop | closeout gate |
| --- | --- | --- | --- | --- | --- |
| A0-M1-P01 | M1 / canonical-store & facade owner | M1 fixed-hash closeout manifest、PostgreSQL sample result、SQLite schema/event/artifact snapshots | network/tool/model=0; canonical write=0 | mutate package input hash、owned event/artifact digest、replay payload；任一 mismatch → `input_snapshot_mismatch` 或 `digest_or_replay_tamper_detected` | `M1-A1 package-and-replay independent verifier` |
| A0-M1-P02 | M1 / lifecycle transaction owner | one WorkUnit with retryable failure, Attempt N/N+1, lease/fencing and idempotency receipt fixture | all external=0; production/business write=0 | duplicate retry, stale Attempt commit, duplicate idempotency key, same WorkUnit multi-attempt race；错误路径 → `stale_write_fenced` / `idempotency_conflict` / `retry_budget_exhausted` | `M1-A1 transaction-idempotency-fencing verifier` |
| A0-M1-P03 | M1 / test-isolation owner | pristine injected temp store plus fingerprinted fixed approval/canonical store canary | all external=0; fixed/production write=0 | import/pytest fixture attempts ambient store, implicit transport or production DB access → `test_runtime_isolation_violation` | `M1-A1 test-isolation fingerprint gate` |
| A0-M1-P04 | M1 / legacy bridge owner | legacy binding snapshot, recovery/outbox/artifact replay fixture | all external=0; legacy authority mutation=0 | restart/replay with changed legacy binding/version or forged event sequence → `legacy_binding_mismatch` / `replay_integrity_failure` | `M1-A1 legacy-authority/recovery gate` |
| A0-M2-P01 | M2 / compiler & serializer owner | exact compiler policy, source packs, legacy objective, full serialized bundle and independent expected oracle | all external=0; canonical/legacy write=0 | mutate expected cell/slot/gap/oracle only; actual compiler output must not change; mismatch → `oracle_leakage_detected` | `M2-A1 compiler-oracle separation gate` |
| A0-M2-P02 | M2 / pack/policy owner | versioned pack registry, selection trace, EvidenceRequest policy and artifact envelope | all external=0; persistence=0 | stale pack, unversioned label, forged lineage/digest, role/source substitution → `pack_version_or_lineage_mismatch` / `policy_upgrade_required` | `M2-A1 package-lineage/replay gate` |
| A0-M2-P03 | M2 / shadow admission owner | four-sector cases plus feature-off/model-admission fixtures and fixed production-store fingerprint | network/model/provider/tool=0; fixed/production write=0 | enable ambient provider/model, use real source, or let a test touch production store → `shadow_scope_violation` / `test_runtime_isolation_violation` | `M2-A1 shadow-vs-runtime boundary gate` |
| A0-M3-P01 | M3 / comparator & calibration owner | frozen legacy/canonical pair, independent comparison oracle, mapping provenance and reviewer trace | all external=0; persistence=0 | mutate expected comparison/reviewer disposition without pair data; same actual output required; mismatch → `oracle_leakage_detected` | `M3-A1 independent-comparison-oracle gate` |
| A0-M3-P02 | M3 / semantic mapping owner | four-sector + five-chain positive corpus and negative controls, case/source snapshots | all external=0; legacy/canonical authority mutation=0 | cross-case row substitution, shared mapping cache, same-source projection masquerading as comparison → `cross_case_contamination` / `non_independent_comparison_input` | `M3-A1 cross-case/provenance gate` |
| A0-M3-P03 | M3 / reviewer trace owner | reviewer trace receipt, mapping/comparison digests, threshold policy | all external=0; store write=0 | expired/revoked/mismatched trace or threshold/digest tamper → `reviewer_trace_not_authoritative` | `M3-A1 reviewer-trace/replay gate` |
| A0-M4-P01 | M4 / cutover state-machine owner | isolated synthetic store, four authority events, decision v1/v2/v3, approval scope, event/version snapshots | network/tool/model=0; business/fixed store write=0; synthetic write requires separate A1 authority | stale approval/revocation/expiry, forged transition, concurrent request/execute, stale decision version → `approval_not_active` / `state_version_conflict` | `M4-A1 persistent-state transition verifier` |
| A0-M4-P02 | M4 / rollback & recovery owner | pre-mutation backup hash, source/restore fingerprints, exact refs and kill-switch receipt | all external=0; business write=0 | wrong backup/store, missing/ordered events, restore mismatch or kill switch bypass → `backup_restore_mismatch` / `rollback_not_proven` | `M4-A1 backup-restore/kill-switch gate` |
| A0-M4-P03 | M4 / tenancy/authority owner | two synthetic tenants/cases/lanes, legacy authority snapshot and read-lock contract | all external=0; business/legacy authority mutation=0 | cross-case calibration/evidence reuse, pinned-contract drift, business Case target or legacy authority mutation → `tenant_or_case_scope_violation` / `legacy_authority_change_forbidden` | `M4-A1 cross-case/legacy-authority gate` |
| A0-M5-P01 | M5 / closeout package owner | exact 92-file package manifest, full receipt, semantic calibration evidence and stable digest rules | all external=0; fixed approval store write=0 | mutate covered source/test/result, timestamp/UUID field, receipt package identity or approval state → `package_digest_mismatch` / `receipt_not_exact_or_stable` | `M5-A1 package-receipt stability verifier` |
| A0-M5-P02 | M5 / scheduler-recovery owner | child-process worker-loss/crash fixtures, lease/fencing, checkpoint/artifact and SQLite snapshots | network/tool/model=0; production write=0; isolated temporary store writes require A1 | same-process reopen presented as child crash, stale worker commit, partial transaction/reconciliation mismatch → `process_evidence_invalid` / `stale_write_fenced` / `partial_transaction_detected` | `M5-A1 child-process/crash-recovery gate` |
| A0-M5-P03 | M5 / security-budget-HITL owner | persisted grant, reservation, HITL registry/receipt, checkpoint scope and expiry/revocation snapshots | all external=0; production write=0 | revoke after admission, replay/forge HITL receipt, expiry race, budget artifact-before-consume crash → `grant_revoked_or_expired` / `hitl_receipt_not_authoritative` / `budget_reconciliation_required` | `M5-A1 transaction-bound admission/HITL/budget gate` |
| A0-M5-P04 | M5 / context-observability owner | immutable snapshot/delta/rebase receipt, trace/alert cursor and injected temporary-store test context | network/tool/model=0; fixed/production write=0 | stale snapshot/replay, ambiguous receipt spoof, cursor duplication, raw secret/reasoning persistence or ambient fixed-store access → `snapshot_or_receipt_mismatch` / `observability_redaction_violation` / `test_runtime_isolation_violation` | `M5-A1 replay-observability-isolation gate` |

## 5. 每个 milestone 的结论判定规则

| A1 closeout result | 可写状态 | 影响 |
| --- | --- | --- |
| all required probes independently pass，输入/计数/authority 均精确 | `historical_claim_retained_after_adversarial_reaudit` | 保留原有**限定范围** claim；不扩大权限。 |
| 输入或覆盖不足，但未发现 owned correctness/security defect | `historical_claim_provisional_pending_evidence_repair` | 不撤销实现；停止进入后续 milestone，先补独立证据。 |
| self-certification、authority bypass、transaction/replay/rollback defect 或 test access violation | `reject_and_repair_<earliest_owned_layer>` | 将该 milestone 置为 reject-and-repair；修最早 owned artifact，新增回归，重新申请该 milestone A1。 |

任何 `retained` 都不等于生产授权，也不影响 Point 01 的 final M6/M7 closeout 要求。

## 6. 固定审计顺序与 stop rule

```text
M1-A1 independent adversarial audit
  -> stop; total reviewer disposition
  -> M2-A1 independent adversarial audit
  -> stop; total reviewer disposition
  -> M3-A1 independent adversarial audit
  -> stop; total reviewer disposition
  -> M4-A1 independent adversarial audit
  -> stop; total reviewer disposition
  -> M5-A1 independent adversarial audit
  -> stop; total reviewer disposition
  -> only then reconsider M6.3R.3 authorization
```

每一段回传必须至少列出：exact snapshot/package/manifest/receipt/store digests；probe IDs；changed files；targeted/broader regression；network/tool/model/production-store/business-Case/legacy-authority/temporary-store write counts；typed stops；remaining gaps；下一段是否仍 blocked。禁止一次性把 M1–M5 全部标绿。

严格顺序的单行审计锚点：`M1-A1 -> stop -> M2-A1 -> stop -> M3-A1 -> stop -> M4-A1 -> stop -> M5-A1 -> stop`。

## 7. A0 closeout 条件

A0 仅在下列静态条件都满足时可提交总 reviewer：

- 机器可读 matrix 与本文件的 claim、probe、owner、snapshot、count、typed-stop、gate 一致；
- 覆盖 oracle leakage、digest/package binding、fixture/runtime gap、test-induced production access、retry/multi-attempt、transaction/idempotency、stale write/fencing、snapshot/replay、HITL revocation/expiry、rollback/kill-switch、cross-case calibration、legacy authority；
- 对每个 M1–M5 先保留/后判定的状态已明确；
- 固定 `M1 -> M2 -> M3 -> M4 -> M5` 且每段 stop；
- 本轮无 runtime/test/database/network/tool/model/mutation 执行。

满足 A0 条件也只表示 `design_frozen_pending_total_reviewer_audit`，不授权 M1-A1 或任何 R3/下游执行。
