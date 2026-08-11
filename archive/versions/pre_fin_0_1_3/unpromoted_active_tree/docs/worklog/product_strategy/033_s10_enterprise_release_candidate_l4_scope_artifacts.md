# 033 S10 Enterprise Release Candidate L4 Scope Artifacts

日期：2026-06-29

## 目标

把 R53-R60 的 S0-S9 scope pass 串成一个可审计的 controlled internal pilot release candidate。S10 不宣布全系统正式生产上线，而是验证 release candidate 范围内必须具备的企业级底座：tenant/RBAC、load/chaos/SLA、incident dashboard、release readiness report、online eval feedback lifecycle 和 release gate artifact。

## 本轮完成

- 新增 `src/sec_agent/r53_r60_enterprise_release_candidate.py`：
  - `Tenant` / `User` / `ProjectSpace` / `RoleAssignment` / `PermissionCheck`；
  - `DemandAcceptanceRecord`；
  - `LoadScenario` / `LoadTaskObservation`；
  - `ChaosEvent` / `SLAObservation`；
  - `IncidentRecord` / `IncidentDashboardProjection`；
  - `OnlineEvalFeedbackItem` / `RegressionCaseRecord` / `GoldPromotionRecord`；
  - `ReleaseReadinessReport` / `ReleaseGateResult`；
  - S10 gate rows / summary / closeout report。
- 新增 `scripts/engineering/build_r53_r60_s10_enterprise_release_candidate.py`，可从仓库根目录重建 S10。
- 新增 `tests/test_r53_r60_enterprise_release_candidate.py`，验证 schema、tenant/RBAC、cross-tenant deny、demand acceptance、load/chaos/SLA、incident dashboard、feedback lifecycle、release report 和 rerun append-only 行为。
- 更新 `docs/architecture/agent_graph_vnext/35_r60_eval_observability_incident_fallback_technical_plan.zh-CN.md`，记录 S10 runtime closeout。
- 更新 `docs/architecture/agent_graph_vnext/36_r53_r60_unified_demand_backlog_execution_plan.zh-CN.md`，写入 S10 closeout。

## 生成物

- `configs/r53_r60/s10_enterprise_release_candidate_schema_v0_1.json`
- `data/manifests/r53_r60_s10_enterprise_release_candidate_gate_rows_v0_1.jsonl`
- `data/manifests/r53_r60_s10_enterprise_release_candidate_summary_v0_1.json`
- `docs/internal/vnext_20260610/r53_r60_s10_enterprise_release_candidate_l4_scope_pass.zh-CN.md`
- 私有 runtime DB：`data/workbench_private/research_data/r53_r60_runtime_task_spine_v0_1.sqlite`（不提交 Git）

## 真实构建结果

输入：

- S0-S9 summary manifests；
- 当前 S1 runtime task spine；
- R59/R60 的 release candidate demand contract。

输出：

- dependency summaries：`10/10 pass`
- Tenant：`2`
- User：`4`
- ProjectSpace：`2`
- RoleAssignment：`4`
- PermissionCheck：`5`
- DemandAcceptanceRecord：`5`
- LoadScenario：`1`
- LoadTaskObservation：`20`
- ChaosEvent：`4`
- SLAObservation：`6`
- IncidentRecord：`6`
- IncidentDashboardProjection：`6`
- OnlineEvalFeedbackItem：`3`
- RegressionCaseRecord：`2`
- GoldPromotionRecord：`1`
- quality gate：`12 pass / 0 fail`
- release decision：`S10_L4_scope_pass_release_candidate_ready`
- full product release status：`not_l4_production_pass`

## 关键边界

- S10 是 controlled internal pilot release candidate，不是正式生产 `L4_production_pass`。
- Cross-tenant access 必须 fail-closed；tenant B 不能读取 tenant A artifact。
- Redis / queue 只作为 transient 协作层；SQL-final runtime DB 仍是最终审计源。
- Load / chaos / SLA 是本地 deterministic release-candidate gate，记录 p95 queue wait、p95 latency、recovery rate、SSE reconnect、token 和 cost；云端/生产 SLA 仍需后续 pilot 证据。
- Incident dashboard 必须能看到 parser、retrieval、tool、model、frontend、cost 六类 incident。
- Production failure / reviewer feedback 必须能进入 regression / gold lifecycle。
- Release readiness report 必须有 gate refs、known gaps、rollback plan、owner、user feedback entry 和 pilot scope。

## 验证

- `python -m py_compile src\sec_agent\r53_r60_enterprise_release_candidate.py scripts\engineering\build_r53_r60_s10_enterprise_release_candidate.py`
- `python -m pytest tests\test_r53_r60_enterprise_release_candidate.py -q`
- `python scripts\engineering\build_r53_r60_s10_enterprise_release_candidate.py --root .`

## 后续

- 运行 S0-S10 全量 deterministic regression。
- 对 release candidate 做更长时间的内部 dogfood / pilot case，积累真实 failure、gold、cost、latency 和 reviewer feedback。
- 后续如果要冲 `L4_production_pass`，必须补云端/生产 SLA、on-call/runbook、审计留存、真实多租户、权限继承、长期 online eval 和 rollback rehearsal。
