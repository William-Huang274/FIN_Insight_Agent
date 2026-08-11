# P38 Point 02：Contract And Dependency Freeze

日期：2026-07-18

状态：`P02_0_CONTRACT_SET_CLOSURE_APPROVED / VT1_internal_development_only`

> 2026-07-18 独立复核更新：既有 T01-T09 产物保留审计，但 route action、canonical command/read model、OpenAPI operation/schema 和 owner set 尚未逐项闭合。原 closeout 不再作为当前批准状态；只允许在原 `P02.0` 内执行一次 bounded set-closure repair。修复通过前不得启动 `P02.1/P02.2`。

## 问题与裁决

在 Point 01 以 `POINT01_FOUNDATION_ALPHA_CONTRACT_RUNTIME_PROOF_COMPLETE` 窄收口后，P02.0 获得的只是 fixture/shadow/internal development 准入。本工作包只完成 T01-T09 的合同、schema example、API/route 设计、fixture/test profile、rollback ADR 与 dependency lock；不启动 P02.1/P02.2，不尝试消耗或替换已消费的 Point 01 receipt。

## 完成内容

- `point02_entry_preflight_v1_0.json` 将 Point 01 closeout、ReleaseContract v1.2、backlog v1.1、FeatureScope SHA 与 `REL-PROD-001-RG1` hard blocker 精确绑定；
- authority/rollback ADR 冻结 future `point02_new_lane` 的 default-off flag、projection store/object envelope 和 legacy-retained rollback；未创建 store、flag、authority 或 receipt；
- canonical object subset 确定 ResearchCase、Objective、DecisionSurface、WorkUnit 的版本字段、command owner/read-model owner 与 single-source-of-truth；
- route/API 合同冻结 8 个 browser surfaces、versioned action、typed error 和 `/api/v1` OpenAPI baseline；
- frontend dependency lock 只做 design pin，明确 router/query/OpenAPI/test 工具均未安装、未联网、未生成 client；
- fixture manifest 以 P36、SaaS、US Banks 覆盖 static/fixture/fast/component，operational/browser 明确 deferred；
- cross-owner review 无 unresolved conflict，P02.0 closeout 将 P02.1/P02.2 标为仅可在未来独立审批下开始的 fixture/shadow internal development。

## 证据与边界

所有 machine-readable artifacts 位于 `data/manifests/point02_*_v1_0.json` 和 `configs/releases/point02_*_v1_0.json`；T02 ADR 位于 `docs/architecture/repository/ADR_POINT02_AUTHORITY_ROLLBACK_20260718.md`。聚焦合同测试为 `tests/contract/test_point02_contract_dependency_freeze.py`。

未运行 operational/runtime baseline、browser profile、network/model/tool/provider、paid/full-chain、真实业务 Case mutation、store write、authority/approval/receipt 或 production cutover。`P01-G2` 仍为 failed/consumed/deferred；`operational_qualification=not_qualified_deferred`、`production_readiness=not_admitted`、`legacy_global_authority=retained`。

## 后续与回滚

本轮没有 runtime change，因此无需运行时 rollback。后续若授权 P02.1/P02.2，必须先复核这些 contracts 和 RG1 debt，并在新 execution point 内以 fixture/shadow internal scope 单独实施；P02.0 closeout 不可被用作 release 或 operational admission。

## 2026-07-18 Bounded Set-Closure Repair

状态：`P02_0_CONTRACT_AND_DEPENDENCY_FREEZE_SET_CLOSURE_REPAIRED_PENDING_PARENT_INDEPENDENT_REVIEW`

在独立批准的 VT0 overlay 所允许的唯一 P02.0 bounded repair 内，原 v1.0 artifacts 保留为 `historical_candidate_evidence_set_closure_not_approved`，没有被覆盖。新增 v1.1 只修复 route-action / canonical command-query-read-model / OpenAPI / owner 集合闭合：

- `AcceptPlanningCheckpoint` 与 `ReturnPlanningCheckpoint` 统一映射到 TECH_01 的 `PlanningCheckpointDecisionCommand`，但 request 必填 `decision=accept|return`、`expected_case_version`、`expected_decision_surface_contract_version` 与 `expected_checkpoint_version`，因此 wire semantics 可区分；
- `ResumeWorkUnit` 从 VT0 active actions 移至 `future_not_admitted`，future command owner 明确为 TECH_06，且没有 active OpenAPI operation；原因是 targeted resume/recovery 属于 VT2 的 P02.5，VT1 只要求 start/cancel/typed stop；
- OpenAPI v1.1 为 TaskCenterProjection、CaseWorkspaceProjection、DecisionSurfaceView、WorkUnitExecutionView、ActivityTraceView 提供 typed success responses，并为每个 active command 提供 versioned request schema；
- cross-owner review v1.1 为每个 active route action/read model 记录唯一 canonical owner、operation、request/response schema 与 OpenAPI contract owner；
- `tests/contract/test_point02_contract_dependency_freeze.py` 不再把 review disposition 或空 conflict list 当作 closure evidence，而是从 route surfaces、canonical lists、parsed OpenAPI paths/components 与 cross-owner mapping 派生并比较集合。

验证仅为静态/fixture contract：10 个 P02 v1.0/v1.1 JSON artifacts parse 成功；`python -m pytest -q tests/contract/test_point02_contract_dependency_freeze.py` 为 `6 passed in 0.20s`。未运行 runtime/operational/browser、network/model/tool/provider、authority/approval/receipt、store/object/real Case write 或 production cutover；RG1 hard blocker、`production_readiness=not_admitted` 与 legacy authority retained 均未改变。

待 parent independent review 后，才可按 overlay 的既有规则决定是否把 P02.1/P02.2 作为 fixture/shadow internal development 开始；本 repair 不授予 runtime、operational 或 release admission。

## 2026-07-18 Parent Independent Disposition

父级复算与只读独立审计均未发现 P0/P1。当前批准精确绑定 `data/manifests/point02_closeout_decision_v1_1.json` 的 `closeout_digest=ca44ed89e88c49144c67d2d1d1c188025a5ac1900cff783fdd8501e94b45892a`，处置为 `P02_0_CONTRACT_SET_CLOSURE_APPROVED_FOR_VT1_INTERNAL_DEVELOPMENT`。

本批准只解除 P02.1/P02.2 的 fixture/shadow/internal development 阻断；不修改 v1.1 closeout 候选合同，不新建 gate/package family，也不授予 runtime、operational 或 FIN 0.1 release admission。`REL-PROD-001-RG1`、`production_readiness=not_admitted` 与 `legacy_global_authority=retained` 继续有效。顶层历史状态歧义与对 pending-parent decision 的额外断言作为 P2 测试维护债务记录，不阻断 VT1。
