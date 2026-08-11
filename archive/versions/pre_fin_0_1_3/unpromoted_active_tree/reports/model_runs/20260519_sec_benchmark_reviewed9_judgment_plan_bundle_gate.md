# Model Run: 20260519_sec_benchmark_reviewed9_judgment_plan_bundle_gate

## Summary

- Purpose: 将 Cloud / Platform 两个 complex reviewed case 的 Judgment Plan true-Qwen 输出合入 `reviewed9 + 2 trap` pipeline bundle，并用总 post-gates 验证 Answer Plan / Judgment Plan 路径是否能进入下一阶段。
- Status: diagnostic-only, passed current reviewed gate。
- Run type: inference artifact bundle + evaluation gate。
- Timestamp: 2026-05-19 Asia/Shanghai。
- Environment: 本地 Windows 执行 bundle / gate；Cloud / Platform 单 case true-Qwen 输出来自云端 RTX 4090 vLLM 运行。

## Code And Command

- Entry point: `scripts/run_sec_benchmark_post_gates.py`
- Judgment Plan seed builder / validators:
  - `scripts/build_sec_benchmark_judgment_plan.py`
  - `scripts/validate_sec_benchmark_judgment_plan.py`
  - `scripts/validate_sec_benchmark_answer_vs_judgment_plan.py`
- Synthesis backend changes:
  - `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
  - `scripts/run_sec_benchmark_vllm_synthesis_from_traces.py`
- Gate command:

```bash
python scripts/run_sec_benchmark_post_gates.py \
  --gold-run-dir eval/sec_cases/outputs/run_20260518_reviewed9_gold_reference_qwen9b_mixed \
  --pipeline-run-dir eval/sec_cases/outputs/run_20260519_reviewed9_judgment_plan_plus_traps_pipeline_gate_bundle \
  --output-dir reports/quality/local_reviewed9_judgment_plan_plus_traps_pipeline_gate_bundle_post_gates \
  --min-qwen-answer-ratio 1.0 \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v1_reviewed_complex2_judgment_plans_seed.json
```

- Git commit / dirty files: worktree dirty；本轮主要新增 Judgment Plan builder / validators / backend injection / post-gate wiring / run artifacts / worklog 记录。
- Seeds: deterministic artifact/gate path；无随机训练 seed。

## Inputs

- Gold run: `eval/sec_cases/outputs/run_20260518_reviewed9_gold_reference_qwen9b_mixed`
- Previous pipeline bundle: `eval/sec_cases/outputs/run_20260518_reviewed9_platform_strictadobe_plus_traps_pipeline_gate_bundle`
- Replacement true-Qwen outputs:
  - `eval/sec_cases/outputs/run_20260518_cloud_pipeline_qwen9b_judgment_plan`
  - `eval/sec_cases/outputs/run_20260518_platform_pipeline_qwen9b_judgment_plan`
- New combined bundle: `eval/sec_cases/outputs/run_20260519_reviewed9_judgment_plan_plus_traps_pipeline_gate_bundle`
- Judgment Plan seed: `reports/evidence_packs/sec_benchmark_v1_reviewed_complex2_judgment_plans_seed.json`
- Exact-value ledger: `reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json`
- Label / split boundary: reviewed9 SEC cases plus 2 trap refusal cases；trap cases excluded from qwen answer ratio。
- Candidate boundary / ID space: existing SEC benchmark trace/evidence IDs and reviewed exact-value ledger IDs。

## Model Parameters

- Model: Qwen3.5-9B via vLLM for the two replacement single-case outputs。
- Model path on cloud: `data/models_private/modelscope/Qwen/Qwen3___5-9B`
- Max model length: `32768`
- Max tokens: `5000`
- Structured JSON: enabled。
- Non-default prompt setting: `--judgment-plan-path` injected validated Judgment Plan constraints for Cloud and Platform complex reviewed cases。

## Outputs

- Combined run summary: `eval/sec_cases/outputs/run_20260519_reviewed9_judgment_plan_plus_traps_pipeline_gate_bundle/run_summary.json`
- Total post-gate summary: `reports/quality/local_reviewed9_judgment_plan_plus_traps_pipeline_gate_bundle_post_gates/sec_benchmark_post_gates_summary.json`
- Answer-vs-Judgment-Plan report: `reports/quality/local_reviewed9_judgment_plan_plus_traps_pipeline_gate_bundle_post_gates/sec_benchmark_answer_vs_judgment_plan_gate.json`
- Single-case post-gate summaries:
  - `reports/quality/cloud_judgment_plan_post_gates/sec_benchmark_post_gates_summary.json`
  - `reports/quality/platform_judgment_plan_post_gates/sec_benchmark_post_gates_summary.json`

## Results

- Bundle size: `trace_count=11`, `agent_output_count=11`。
- Answer status counts: `answered_qwen9b=9`, `answered_contract_fallback=2`。
- Qwen usage gate: `qwen_answer_ratio=1.0`, `qwen_ledger_repaired=0`, `fallback_answered=0`。
- Trap gate: pass。
- Gold-vs-pipeline gate: pass。
- Answer ledger gate: pass, `case_count=11`, `exact_value_hit_count=35`。
- Metric-role-term gate: pass。
- Named-fact support gate: pass, `pass_count=9`, `skip_count=2`, `unsupported_token_count=0`。
- Ledger missing consistency gate: pass, `missing_statement_count=5`, `false_missing_statement_count=0`。
- Abstract judgment gate: pass, `checked_case_count=9`, `required_dimension_count=37`, `covered_required_dimension_count=37`。
- Answer-vs-Judgment-Plan gate: pass, `checked_case_count=2`, `pass_count=2`, `skip_count=9`。
- Ledger unit gate: pass, `ledger_row_count=50`, `pass_count=50`。

Interpretation: Judgment Plan can currently be promoted as a gated planning/synthesis constraint for the two complex reviewed cases and can coexist with the reviewed9 + trap gate bundle. This does not prove full noisy benchmark generalization; the next meaningful check is adding more reviewed gold cases.

## Experiment Governance

- Hypothesis: BGE/Qwen verifier-filtered evidence can be used upstream to seed a deterministic Judgment Plan, and final synthesis constrained by that plan should preserve direct/proxy/caveat boundaries in complex SEC questions.
- Decision target: reviewed9 + 2 trap bundle passes all existing gates plus answer-vs-Judgment-Plan gate with `qwen_answer_ratio=1.0`, no ledger repairs, and zero answer-vs-plan failures.
- Ceiling / upper bound: only 2 cases currently have Judgment Plans, so answer-vs-plan coverage is 2/11; this is sufficient for a complex2 diagnostic, not for broad benchmark claims.
- Baselines to beat: previous reviewed9 + 2 trap bundle without Judgment Plan, plus rubric-only Cloud/Platform answers.
- Split and leakage guard: reviewed cases are manually approved diagnostic cases; trap refusals remain separate and excluded from qwen ratio. The two Judgment Plans are deterministic artifacts built from reviewed complex-case evidence packs, not from final-answer text.
- Stop conditions: any answer-vs-plan failure, qwen fallback on eligible cases, ledger repair, unsupported named fact, false missing ledger statement, or abstract judgment miss blocks promotion.
- Efficiency gate: true-Qwen Cloud case took about 156s and Platform took about 163s on single RTX 4090; acceptable for diagnostic batch, not yet a serving claim.
- Decision label: diagnostic-only / proceed to broader reviewed gold evaluation。
- Mainline decision: do not run full noisy benchmark yet；next step is to expand the reviewed gold set to test generalization.

## Runtime Efficiency

- Cloud single-case true-Qwen synthesis: model load `63.6566s`, total elapsed `155.9582s`。
- Platform single-case true-Qwen synthesis: model load `61.1203s`, total elapsed `163.2889s`。
- Local bundle gate wall time: not separately measured；post-gates are deterministic JSON/ledger validators and completed quickly on CPU。
- GPU memory / utilization: not captured in the local ledger；cloud run used single RTX 4090 vLLM path。
- Bottleneck: true-Qwen final synthesis latency dominates；gate time is not material at current reviewed size。
- Next optimization: if reviewed gold expands substantially, batch synthesis where possible and keep deterministic gates as post-processing.

## Safety Notes

- No cloud passwords, tokens, or private credentials are recorded in this ledger.
- Current result is diagnostic-only and case-filtered.
- Rollback: use the prior accepted bundle `eval/sec_cases/outputs/run_20260518_reviewed9_platform_strictadobe_plus_traps_pipeline_gate_bundle` and its post-gates if Judgment Plan artifacts need to be excluded.
- Next decision: add more reviewed gold cases before treating Judgment Plan as broadly generalizable.
