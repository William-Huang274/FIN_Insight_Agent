# Model Run: 20260518_sec_benchmark_reviewed3_text_qwen9b_gold_synthesis

## Summary
- Purpose: Run true Qwen3.5-9B gold-context synthesis on the three newly reviewed text-heavy SEC benchmark cases: `SNOW_RISK_2023_2025_001`, `NVDA_DATACENTER_2023_2025_001`, and `MSFT_AI_CLOUD_2023_2025_001`.
- Status: diagnostic-only, passed case-filtered true-Qwen and hard post-gates.
- Run type: inference + evaluation gates.
- Timestamp: 2026-05-18 afternoon/evening, Asia/Shanghai.
- Environment: cloud RTX 4090 24GB, HF per-case backend using `/root/miniconda3/bin/python` and `data/models_private/modelscope/Qwen/Qwen3___5-9B`.

## Code And Command
- Entry point: `scripts/run_sec_benchmark_eval.py` with `--synthesis-backend external_command`.
- Backend: `scripts/run_sec_eval_synthesis_qwen9b_backend.py`.
- Important backend changes:
  - Added no-ledger text-summary rule: when a case has no Exact-Value Ledger rows, Qwen may write qualitative SEC evidence synthesis but must not output percentages, money amounts, comma-separated large numbers, multiples, customer concentration percentages, or R&D amounts.
  - Increased per-row SEC `text_excerpt` from 900 to 2200 characters, after MSFT OpenAI disclosure was found beyond the old excerpt window.
  - Added cross-year / named-item contract: multi-year answers must preserve material year-specific changes and named products, architectures, partnerships, regulations, or risk mechanisms.
  - Added deterministic named-evidence citation repair: if a driver/key point mentions an English named entity and current evidence IDs do not include source text containing that token, append a matching evidence ID; duplicate `evidence_id` text fragments are merged before matching.
- Final reproduce command on cloud:

```bash
cd /root/autodl-tmp/FIN_Insight_Agent
PY=/root/miniconda3/bin/python
OUT=eval/sec_cases/outputs/run_20260518_reviewed3_text_gold_qwen9b_hf_32768_strict_prompt3_excerpt2200_namedrepair2
$PY scripts/run_sec_benchmark_eval.py \
  --mode gold_context \
  --gold-context-dir eval/sec_cases/reviewed_gold_context \
  --output-dir "$OUT" \
  --case-id SNOW_RISK_2023_2025_001 \
  --case-id NVDA_DATACENTER_2023_2025_001 \
  --case-id MSFT_AI_CLOUD_2023_2025_001 \
  --synthesis-backend external_command \
  --synthesis-command "$PY scripts/run_sec_eval_synthesis_qwen9b_backend.py --input {input_json} --output {output_json} --model-path data/models_private/modelscope/Qwen/Qwen3___5-9B --max-model-len 32768 --max-tokens 3000 --disable-fallback"
```

## Inputs
- Cases: reviewed text-heavy SEC benchmark cases only.
- Gold context:
  - `eval/sec_cases/reviewed_gold_context/SNOW_RISK_2023_2025_001.jsonl`，9 rows.
  - `eval/sec_cases/reviewed_gold_context/NVDA_DATACENTER_2023_2025_001.jsonl`，12 rows.
  - `eval/sec_cases/reviewed_gold_context/MSFT_AI_CLOUD_2023_2025_001.jsonl`，11 rows.
- Reviewed gold facts: all three cases have `reviewed_approved_no_numeric_facts`, with no target exact-value facts.
- Exact-Value Ledger: `reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json`, 17 rows from the reviewed numeric cases; these three text cases have 0 ledger rows.
- Leakage guard: gold-context mode uses reviewed SEC-only evidence rows; no seed rows or seed facts promoted.

## Outputs
- Final Qwen output: `eval/sec_cases/outputs/run_20260518_reviewed3_text_gold_qwen9b_hf_32768_strict_prompt3_excerpt2200_namedrepair2/`.
- Final cloud log: `reports/logs/20260518_reviewed3_text_gold_qwen9b_hf_32768_strict_prompt3_excerpt2200_namedrepair2.log`.
- Final post-gates: `reports/quality/cloud_reviewed3_text_gold_qwen9b_hf_32768_strict_prompt3_excerpt2200_namedrepair2_post_gates/sec_benchmark_post_gates_summary.json`.
- Earlier diagnostic failure: `eval/sec_cases/outputs/run_20260518_reviewed3_text_gold_qwen9b_hf_32768/` showed `SNOW=answered_qwen9b`, while `NVDA/MSFT=answered_qwen9b_ledger_repair` due to ledger-text contract violations from non-ledger percentages/amounts.

## Results
- Final run:
  - `trace_count=3`, `agent_output_count=3`.
  - `answer_status`: 3/3 `answered_qwen9b`.
  - `qwen_answer_ratio=1.0` with `min_qwen_answer_ratio=1.0`.
  - `qwen_ledger_repaired=0`, `fallback_answered=0`, `failed_eligible_outputs=0`.
  - `answer_ledger_gate_pass=true`; exact value hit count `0`.
  - `metric_role_term_gate_pass=true`.
  - `ledger_unit_gate_pass=true`; reviewed ledger still `17/17` pass.
  - Mean diagnostic score remains `0.84` because backend-scored outputs currently use fixed backend scores; manual review is the meaningful quality signal for this run.

## Manual Review
- SNOW: Good coverage of consumption-based revenue model, usage variability, macro/customer optimization risk, technical-efficiency-lower-consumption caveat, repeated analyst misunderstanding risk, and 2025 AI/Data Cloud adoption uncertainty. Output correctly avoids customer-count/retention inventions and avoids non-ledger percentages.
- NVDA: Improved after cross-year contract. It now distinguishes 2023 inventory/export-control context, 2024 DGX Cloud / CSP demand, 2025 Blackwell and China/export-license strategy, and continuing product-defect/software-vulnerability risks. It still compresses Hopper into the broader AI/generative AI driver rather than naming Hopper in the final answer, but it covers the main year-specific growth/risk path without product-revenue invention.
- MSFT: Improved after extending evidence excerpts. It now covers Azure/cloud/AI infrastructure, operating cost and margin pressure, datacenter/server/GPU constraints, and 2025 OpenAI partnership. Named-entity citation repair now adds the 2025 Item 7 evidence ID containing the OpenAI disclosure to the relevant key point.

## Experiment Governance
- Hypothesis: For no-numeric-fact text-summary cases, true Qwen9B can produce useful qualitative SEC synthesis if prompt contract forbids non-ledger exact values while preserving enough source text and named year-specific evidence.
- Decision target: 3/3 `answered_qwen9b`, no ledger repair/fallback, no answer-ledger exact-value failures, and manual coverage of required text-heavy gold points.
- Baselines: initial HF run failed 2/3 via ledger repair; reviewed4 numeric cases already passed resident-vLLM qwen-only and pipeline gates.
- Ceiling / upper bound: gold-context mode tests synthesis only, not retrieval quality; full benchmark remains blocked until more cases have reviewed gold and pipeline-context retrieval is evaluated.
- Decision label: diagnostic-only proceed.
- Mainline decision: These three reviewed text-heavy gold-context cases can be used as a synthesis smoke boundary. They do not yet prove pipeline-context performance.

## Runtime Efficiency
- Wall time: each HF per-case run took several minutes for 3 cases because the backend loads the model per case.
- GPU: RTX 4090 utilization observed during generation; peak memory around 21.8GB in most polls.
- Bottleneck diagnosis: HF per-case model loading is inefficient for repeated benchmark runs. Resident vLLM should be preferred for broader evaluation once prompt/repair behavior is stable.
- Serving implication: This backend is acceptable for diagnostic smoke only, not serving or large benchmark throughput.

## Caveats And Next Step
- Not run: pipeline-context retrieval for the three text-heavy cases was not run in this step; trap cases were skipped in this case-filtered run.
- Known risks: named-evidence citation repair is lightweight and English-token based; it helps with OpenAI/Blackwell/Azure-style terms but is not a full unsupported-claim validator.
- Next decision: move from gold-context synthesis smoke to reviewed7 pipeline-context testing, then run the combined reviewed7 non-trap + trap bundle with true-Qwen ratio, answer-ledger, metric-role-term, ledger-unit, and gold-vs-pipeline gates.
