# P36 Node 11 Verifier / Workbench Review 手工运行记录

日期：2026-07-09

## 节点定位

本节点不重新跑 verifier runtime，也不启动 Workbench replay。它是 P36 Codex-as-paid-model manual dogfood 的手工审查节点，用来判断 Node10 产物能否被当前 verifier / Workbench 合理验收，以及哪些结论必须继续保持 runtime 边界。

本轮仍遵守：

- 不调用 paid LLM。
- 不运行 true runtime full-chain。
- 不做模型对比、case expansion 或 release eval。
- 不把 supervisor supplement 伪装成 accepted runtime rows。
- 不允许 writer 自己补源。

机器可读 review artifact：

- `docs/project_os/p36_verifier_workbench_review_v0_1.json`

## 审查对象

| 对象 | 文件 | 审查结论 |
|---|---|---|
| runtime-only writer material | Node01-09 + Node10 runtime-only assessment | 只能判 `bounded_partial_report`，不能判完整研究报告通过。 |
| supervisor-augmented report | `p36_ai_infra_manual_writer_research_report.zh-CN.md` | 可作为人工可读报告通过，但必须绑定 supplement ledger 边界。 |
| dogfood recap | `p36_codex_as_paid_model_dogfood_recap_report.zh-CN.md` | 复盘结论成立：问题是能力未编译成 decision surface。 |
| supplement ledger | `p36_supervisor_source_supplement_ledger_v0_1.json` | 分层正确，全部仍是 `supervisor_supplement_only`。 |

## Verifier 能力审查

已审阅的 runtime surface：

- `src/sec_agent/memo_llm.py::_verifier_minimal_projection`
- `src/sec_agent/memo_llm.py::_verifier_system_prompt`
- `tests/test_multi_agent_judgment_memo_verifier.py`
- `tests/test_multi_agent_memo_llm_repair.py`

当前 verifier 的强项：

- 能把最终 memo claims 和 referenced evidence 压成 minimal projection。
- 能检查 raw rows / tool calls / unsupported claims / source-boundary misuse。
- 对 blocked / bounded answer 有明确策略：如果 deterministic verification pass 且没有新增事实，不应因为没有完整 memo 而 fail。
- 能维护 writer 不得检索、不得补事实的边界。

当前 verifier 的缺口：

- 它审的是 memo claim / evidence ref / source family，不是五链条 decision cell。
- 它没有 `decision_surface_cell_id`、`chain_segment_id`、`evidence_quality_grade`、`numeric_sanity_status`、`official_or_estimate_flag`、`cannot_infer`、`what_would_change` 等矩阵字段。
- 因为上游没有 runtime `DecisionSurfacePack`，verifier 不能判断 report-first decision matrix 是否 coverage 完整。

因此，Node11 对 verifier 的判定是：`partial`。它足以维护边界，不足以验收 P36 完整五链条研究表面。

## Workbench 能力审查

已审阅的 runtime surface：

- `src/sec_agent/p33_workbench_artifact_review_surface_fixture.py`
- `src/sec_agent/r53_r60_workbench_frontdoor_drilldown.py`
- `apps/workbench/backend/app.py::R53R60ReviewActionRequest`
- `tests/test_p33_workbench_artifact_review_surface_fixture.py`
- `tests/test_workbench_backend.py`

当前 Workbench 的强项：

- S6/P33 surface 能展示 task、sections、ClaimCards、typed gaps、gates、artifacts 和 events。
- review action 已支持 accept / reject / supersede / request_repair / return_to_specialist / downgrade_claim / comment。
- review action 可写入 append-only workpaper events，不依赖前端 local state 或聊天记录作为最终审计源。

当前 Workbench 的缺口：

- review target 仍以 `claim_card`、`gap`、`judgment_state` 和 artifact/drilldown 为主。
- P36 需要的是 `decision_surface_cell` 级 review：每个 cell 可以标注 `accepted`、`needs_source`、`needs_parser`、`estimate_only`、`commercial_gap`、`rejected`。
- 当前 Workbench 不能逐格审 HBM / CoWoS / Server OEM margin / Semicap backlog / price-in / crowding 等 cell 的 source grade 和 numeric sanity。

因此，Node11 对 Workbench 的判定是：`partial_existing_claim_gap_artifact_review_ready_fail_for_p36_decision_cell_review`。

## Gate 结果

| Gate | 结果 | 说明 |
|---|---|---|
| no paid / full-chain | pass | Node11 只做手工 review，没有 runtime replay。 |
| writer no-self-source | pass | Node10 保留 writer 禁工具边界。 |
| supplement separate ledger | pass | 补源 rows 单独记录，未写成 runtime rows。 |
| runtime-only complete report | fail | runtime-only 只能 bounded partial。 |
| supervisor report human readability | pass_with_boundary | 报告可读，但依赖 supplement ledger。 |
| supervisor report as runtime proof | fail | 不能证明 runtime source hunter / parser / writer 已具备能力。 |
| verifier boundary review | partial | 可审 claim/ref/source boundary，不能审 decision-cell matrix。 |
| Workbench cell review | fail | 缺 `decision_surface_cell` review surface。 |

## 最终判定

1. Runtime-only writer：`pass_as_bounded_partial_only`，`fail_as_complete_report`。
2. Supervisor-augmented report：`pass_for_manual_human_reading_with_supplement_boundary`，`fail_as_runtime_capability`。
3. Verifier：`partial`，能守边界，但不能审五链条矩阵覆盖。
4. Workbench：`partial`，能审 claim/gap/artifact，但不能审 P36 decision cells。

## 根因判断

新增 root cause：

`RC-P36-031-verifier-workbench-can-preserve-boundary-but-lacks-decision-cell-review-surface`

具体表现：

1. Verifier 可以阻止 writer 越界补源和 unsupported claim 进入 memo，但没有 decision-cell schema。
2. Workbench 可以 review claim / gap / artifact，但没有五链条 cell review action ledger。
3. Node10 supervisor report 的质量可被人工认可，但不能被系统声明为 runtime pass。
4. 下一步不能直接 paid rerun 或模型对比，必须先做 deterministic DecisionSurfacePack / Workbench cell-review fixtures。

## 允许的下一步

- `DecisionSurfaceContract` fixture。
- `SourceHunterLoop` fixture。
- official press release / IR PDF parser fixture。
- supplement ledger to runtime row fixture。
- Product / Industry decision-surface projection fixture。
- Market / Capital decision-surface projection fixture。
- RiskMatrixPack fixture。
- DecisionSurfacePack to MemoLogicPlan projection test。
- Workbench `decision_surface_cell` review replay。

## 未运行

- paid LLM API
- true runtime full-chain
- verifier runtime replay
- Workbench runtime replay
- model comparison
- case expansion
- release eval
