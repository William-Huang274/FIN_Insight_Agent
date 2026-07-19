# 114 P34 Scoped Memo Writer Projection

## Prompt

用户询问 writer 前节点状态，并允许在 P34 已通过 bounded source-runtime audit 后继续推进。Project OS 明确只允许 `P34-9 scoped paid Memo Writer node + renderer/final verifier/Workbench projection`，禁止 broad full-chain、模型对比、case expansion 和 release eval。

## Reasoning

本轮不能再用 full-chain 发现问题。P34-6 已证明 20 个 AI/Semis evidence slots 均有真实 route attempts 或 attempt-backed typed gaps，且 `5/7` judgment chains pass、`2/7` bounded partial。正确动作是把这些 live rows 和 typed gaps 编译成 writer-ready bounded payload，再只跑 Memo Writer 节点和 deterministic projections。

## Work Completed

- 新增 P34 scoped writer payload builder，把 P34 live route rows / no-paid audit / typed gaps 编译成：
  - `supported_claims`
  - `JudgmentCards`
  - `MemoLogicPlan`
  - `verified_judgment_plan`
  - `supervising_analyst_pack`
  - `ProductIntelligenceGraph` projection
  - `bounded_gap_register`
- 新增 no-paid preflight runner：`scripts/eval_multi_agent/run_p34_scoped_memo_writer_payload_preflight.py`。
- 新增 scoped Memo Writer node runner：`scripts/eval_multi_agent/run_p34_scoped_memo_writer_node.py`。
- 修复 writer prompt compact projection：`required_item_answer_plan` 的 `answer`、`cannot_infer`、`what_would_change_view` 不能在进入 writer 前被丢弃。
- 修复 final verifier projection：当 memo claim id 已匹配 verified supported claim 时，verifier projection 不能只保留 memo 明文交集 refs，否则会把 verified claim 的核心支撑 refs 剪掉。
- 修复 Workbench projection：除维度 section 外，增加 `required_item_answers`、`investment_implications`、`what_would_change_view`、`evidence_gaps_but_actionable` 等 reviewer surfaces。
- 更新 P34 source document、Project OS capability ledger、root-cause ledger。

## Result And Evidence

### No-paid payload preflight

Command:

```powershell
python scripts/eval_multi_agent/run_p34_scoped_memo_writer_payload_preflight.py --strict
```

Result:

- `gate_status=pass`
- `seven_judgment_claims_present=true`
- `seven_required_items_present=true`
- `dell_margin_gap_preserved=true`
- `market_price_in_gap_preserved=true`
- `full_chain_not_allowed=true`
- `memo_logic_validation_pass=true`

Artifact:

- `eval/sec_cases/outputs/p34_ai_semis_scoped_writer_runs/p34_scoped_memo_writer_payload_preflight_20260707_120554/p34_ai_semis_scoped_writer_case_v0_1/p34_scoped_memo_writer_payload_preflight_summary.json`

### Scoped paid Memo Writer node

Command:

```powershell
python scripts/eval_multi_agent/run_p34_scoped_memo_writer_node.py --memo-router deepseek --strict
```

Result:

- `gate_status=pass`
- `memo_route.status=pass`
- `attempt_count=1`
- `repair_attempts=0`
- `total_tokens=16,441`
- `finish_reasons=["stop"]`
- `deterministic_salvage_used=false`
- `direct_answer_chars=650`
- `dimension_analysis_count=5`
- `memo_claim_count=6`
- `dell_margin_boundary_preserved=true`
- `market_price_in_boundary_preserved=true`
- `full_chain_not_run=true`

Artifact:

- `eval/sec_cases/outputs/p34_ai_semis_scoped_writer_runs/p34_scoped_memo_writer_node_deepseek_20260707_120609/p34_ai_semis_scoped_writer_case_v0_1/memo_writer_node_summary.json`

### Projection replay

Command:

```powershell
python scripts/eval_multi_agent/run_p33_memo_projection_replay.py --memo-writer-node-result "eval/sec_cases/outputs/p34_ai_semis_scoped_writer_runs/p34_scoped_memo_writer_node_deepseek_20260707_120609/p34_ai_semis_scoped_writer_case_v0_1/memo_writer_node_result.json" --projection-json docs/project_os/p34_single_case_projection_replay_v0_1.json --projection-md docs/internal/vnext_20260610/p34_single_case_projection_replay_v0_1.zh-CN.md --multi-case-json docs/project_os/p34_multicase_goldset_readiness_v0_1.json --multi-case-md docs/internal/vnext_20260610/p34_multicase_goldset_readiness_v0_1.zh-CN.md --strict
```

Result:

- `single_case_projection_status=pass`
- `renderer_status=pass`
- `final_verifier_status=pass`
- `workbench_status=pass`
- `rendered_answer_chars=6,105`
- `citation_label_count=14`
- `known_evidence_ref_count=15`
- Workbench counts: sections `9`, claims `6`, gaps `1`, gates `2`, artifacts `2`, events `4`

Artifacts:

- `docs/project_os/p34_single_case_projection_replay_v0_1.json`
- `docs/internal/vnext_20260610/p34_single_case_projection_replay_v0_1.zh-CN.md`

### Tests

```powershell
python -m py_compile src/sec_agent/p34_lane_quality_runtime.py src/sec_agent/memo_llm.py src/sec_agent/p33_memo_projection_replay.py scripts/eval_multi_agent/run_p34_scoped_memo_writer_payload_preflight.py scripts/eval_multi_agent/run_p34_scoped_memo_writer_node.py
python -m pytest -q tests/test_p34_scoped_memo_writer_payload.py tests/test_p34_ai_semis_live_route_attempts.py tests/test_p34_ai_semis_no_paid_quality_audit.py
python -m pytest -q tests/test_p33_memo_projection_replay.py tests/test_p34_scoped_memo_writer_payload.py
```

Results:

- py_compile: pass
- P34 adjacent tests: `10 passed`
- Projection/payload tests: `6 passed`

## Boundaries

- This is not full-chain.
- This is not model comparison.
- This is not case expansion or release eval.
- This is not human-accepted gold workpaper.
- RC-P33-019 remains open until human review accepts the rendered workpaper or produces a root-cause repair item.

## Next

Human-review the rendered P34 workpaper against the humanmade gold answer. If accepted, plan limited Workbench dogfood. If rejected, repair the earliest owned artifact: writer payload, JudgmentCard, ProductIntelligenceGraph projection, MemoLogicPlan, or source rows. Do not rerun broad full-chain to hide a quality failure.
