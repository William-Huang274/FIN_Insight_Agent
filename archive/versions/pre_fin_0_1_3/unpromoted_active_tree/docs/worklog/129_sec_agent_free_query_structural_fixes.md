# 129 - SEC Agent Free-Query Structural Fixes

## Summary
- Date: 2026-05-21
- Scope: full30 constrained SEC free-query agent, broad AI industry prompt, 2023-2025 10-K inventory.
- Status: implemented locally, synced to cloud, and validated by DeepSeek full30 constrained inference.

## Problem
- The broad free-query semantic gate treated the run like a full peer-comparison survey and could fail when the final answer did not mention all 30 companies.
- Runtime ledger widening initially admitted noisy rows from tax, goodwill, assets, mixed profitability tables, and parser mistakes such as percentage-change rows classified as revenue.
- The synthesis/terminal layer capped visible insight too tightly: normalized drivers were limited to 3, the prompt asked for at most 4 drivers, and the terminal printed only summary plus key_points.

## Work Completed
- Semantic gate now uses Query Contract intent:
  - Broad free-query coverage is checked against `focus_tickers` and `decomposed_tasks`.
  - Full-company mention coverage is required only when the contract explicitly asks for all-company coverage or peer-comparison coverage.
  - Decomposed task coverage is diagnostic by default for free-query.
- Runtime ledger selection now supports broad insight prompts:
  - Query Contract `metric_families` and `decomposed_tasks.required_metric_families` are used to supplement ledger rows beyond retrieved context.
  - AI broad-query ledger selection is balanced by task/family and capped by `metric_family + ticker + fiscal_year` to avoid duplicate rows crowding out year coverage.
  - Ledger row filtering now requires family-level topical match, for example `AWS` only counts as cloud revenue in revenue/sales context, and `Data Center` only counts as data-center revenue in revenue/sales context.
  - Common structured extraction noise is rejected at the ledger boundary: tax/goodwill/acquisition/segment-asset rows, mixed revenue/profitability table rows, prior-period comparison values, parser artifacts like `-30%`, and non-total operating-income effects.
- Synthesis and rendering are widened:
  - Broad AI synthesis prompt allows up to 8 decision_drivers and 8 key_points.
  - Driver normalization now keeps up to 8 drivers.
  - Interactive terminal now prints `decision_drivers` with metric/evidence support before key_points.
  - Each future interactive run writes `qwen/input_output.md` with user query, final answer JSON, and raw model output.

## Validation
- `python -m py_compile` passed for:
  - `scripts/cloud/sec_agent_interactive.py`
  - `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
  - `scripts/validate_sec_benchmark_v2_semantic_contracts.py`
  - `src/sec_agent/claim_verifier.py`
  - `scripts/run_sec_benchmark_eval.py`
- `bash -n scripts/cloud/sec_agent_interactive.sh` exited 0 on WSL with a local WSL warning.
- Plan-only preview passed inventory injection:
  - inventory digest `e413b6c9ccd0`
  - companies `30/30`
  - years `2023,2024,2025`
  - forms `10-K`
  - task `ai_industry_financial_trend`
  - focus tickers `NVDA, AMD, AVGO, AMAT, MU, INTC, QCOM, MSFT, GOOGL, AMZN, META, ADBE, SNOW`
- Semantic gate replay on `eval/sec_cases/outputs/interactive_sec_agent/20260521_162939_b38c717195` passed:
  - `can_enter_gate=true`
  - `pass_count=1`
  - `fail_count=0`
  - active checks: `decomposed_task_coverage`, `proxy_as_direct_metric`, `source_policy_violation`
- Offline ledger replay on the same trace now produces 36 rows across multiple drivers:
  - `cloud_revenue=10`
  - `capital_expenditure_proxy=8`
  - `operating_income=7`
  - `data_center_revenue=6`
  - `semiconductor_systems=3`
  - `semiconductor_solutions=2`

## Follow-Up
- Add a sentence-level citation binding gate: the 2026-05-21 DeepSeek run passed current gates, but some prose sentences mention multiple companies while the displayed support arrays emphasize only part of the sentence.
- Compare the same post-fix broad prompt on Qwen9B after GPU/vLLM scheduling is clean, using the saved DeepSeek run as the quality reference.

## Cloud Rerun Update - 2026-05-21
- Synced structural fixes to the new cloud endpoint under `/root/autodl-tmp/FIN_Insight_Agent`; no secrets were written to project files or logs.
- First DeepSeek full30 run:
  - Output: `eval/sec_cases/outputs/interactive_sec_agent/20260521_180710_b38c717195`
  - Result: `qwen_answer_ratio=1.0`, semantic gate passed, but `answer_vs_judgment_plan_gate_pass=false`.
  - Root cause: broad-query Judgment Plan compaction kept only 4 company-level drivers and truncated evidence IDs, so valid ledger evidence could fall outside the compacted plan.
- Structural correction:
  - Broad AI Judgment Plan compaction now selects up to 8 drivers using decomposed-task / metric-family diversity before original rank.
  - Supporting evidence IDs are backfilled from each selected metric ID's ledger source evidence, so the plan remains compact without losing evidence grounding.
- Second DeepSeek full30 run:
  - Output: `eval/sec_cases/outputs/interactive_sec_agent/20260521_182029_b38c717195`
  - Model/backend: DeepSeek API `deepseek-v4-pro`, thinking disabled, 30-company scope, 2023-2025 10-K inventory.
  - Result: all post-gates passed, `pass=12`, `fail=[]`, `qwen_answer_ratio=1.0`.
  - Runtime: total elapsed `497.6225 sec`; DeepSeek synthesis latency `200.948 sec`; tokens `44,992 input`, `6,017 output`, `51,009 total`.
  - Runtime ledger: 36 rows; families `data_center_revenue=6`, `semiconductor_solutions=3`, `cloud_revenue=10`, `capital_expenditure_proxy=10`, `semiconductor_systems=3`, `operating_cash_flow=4`.
  - Judgment Plan: 8 drivers after compaction, covering `AVGO`, `GOOGL`, `AMD`, `NVDA`, `AMZN`, `AMAT`, `MSFT`, `ADBE`.
- Quality read:
  - Improvement: output expanded from a 4-driver semiconductor-heavy answer to an 8-driver answer covering AI hardware, cloud revenue, capex, cash flow, equipment, and software proxy evidence.
  - Remaining issue: current gates verify that numbers and named facts are inside the ledger/evidence set, but do not yet force every multi-company prose sentence to display all corresponding metric IDs and evidence IDs next to that sentence.
- Qwen9B A/B check:
  - Output: `eval/sec_cases/outputs/interactive_sec_agent/20260521_183136_b38c717195`
  - Same full30 prompt and task-balanced plan compaction, but local vLLM `qwen9b` with heuristic planner.
  - Result: `qwen_answer_ratio=0.0`, `answer_status=answered_qwen9b_ledger_repair`, failed gates `caveat_claim_gate_pass`, `answer_vs_judgment_plan_gate_pass`, `metric_source_grounding_gate_pass`, `qwen_answer_gate_pass`.
  - Interpretation: 9B remains useful for smoke/diagnostic routing, but under this broad free-query task it does not produce reliable structured synthesis even when the upstream evidence chain is improved.

## API Insight Mode Update - 2026-05-21
- Problem: DeepSeek full30 answer was grounded and gate-clean, but the opening summary was too audit-like and did not expose enough model reasoning.
- Change:
  - Only API synthesis backends (`deepseek`, `openai_compatible`) now receive `synthesis_profile=api_insight_v1` on broad AI free-query tasks.
  - In this profile, `summary` is prompted as a 5-8 sentence analyst thesis that explains what the metrics mean collectively.
  - Exact values remain restricted to ledger-backed `decision_drivers` and `key_points`.
  - Local Qwen/vLLM keeps the stricter audit-style summary prompt.
- Boundary reinforcement:
  - Drivers using `capital_expenditure_proxy` now receive a deterministic proxy caveat in normalization.
- Runs:
  - Diagnostic run `eval/sec_cases/outputs/interactive_sec_agent/20260521_185654_b38c717195` improved summary quality but failed `answer_vs_judgment_plan_gate_pass` due to a missing proxy caveat.
  - Final run `eval/sec_cases/outputs/interactive_sec_agent/20260521_190741_b38c717195` passed all gates: `pass=12`, `fail=[]`, `qwen_answer_ratio=1.0`.
- Quality note:
  - Summary now provides a clearer thesis: AI evidence is concentrated in semiconductors, cloud infrastructure, and capex, with uneven benefit timing and disclosure strength.
  - Remaining user-facing polish issue: named-fact sanitizer can produce awkward safe text such as `相关命名标签`; next step should improve sentence-level support binding and named-fact recovery rather than loosening safety gates.

## User Output + Named-Fact Polish Update - 2026-05-21
- Problem:
  - Interactive terminal runs were too noisy for user-facing inspection because stage logs, BGE subprocess output, and JSON diagnostics were mixed into the final answer.
  - The named-fact sanitizer was safe but too blunt: when a company/product token was not directly visible in support text, it could replace user-facing names with `相关命名标签`.
  - A quiet DeepSeek run exposed one v2 semantic gate false positive: `gross_margin percentage_rate` phrased as `63% -> 68%` was marked as `percentage_metric_used_as_amount` because the validator included the following operating-income phrase in the same local text window.
- Changes:
  - Added `--quiet` / `--user-output` to `scripts/cloud/sec_agent_interactive.py`; env aliases `USER_OUTPUT=1` and `QUIET=1` enable the same mode.
  - Quiet mode suppresses pipeline progress and BGE subprocess stdout while still writing `console_events.log` under the run directory.
  - Added shell usage note: `USER_OUTPUT=1 bash scripts/cloud/sec_agent_interactive.sh ask-deepseek "..."`.
  - Named-fact recovery now checks metric ledger support text and expanded ticker aliases before replacing unsupported names, so supported names like `博通`, `Applied Materials`, `微软`, and `亚马逊` survive when they are backed by metric IDs or evidence IDs.
  - The percentage semantic validator now treats comma / Chinese comma as local phrase boundaries for metric-id checks, preventing a following amount metric from contaminating a percentage-rate metric phrase.
- Validation:
  - Local and cloud `py_compile` passed for the touched Python files.
  - Quiet DeepSeek run path: `eval/sec_cases/outputs/interactive_sec_agent/20260521_194503_b38c717195`.
  - Logged query/output path: `eval/sec_cases/outputs/interactive_sec_agent/20260521_194503_b38c717195/qwen/input_output.md`.
  - Quiet stdout contained the final answer and footer only; detailed stage events are preserved in `console_events.log`.
  - Local and cloud post-gate replay on the same run passed all deterministic gates after the percentage phrase-boundary patch:
    - `answer_ledger_gate_pass=true`
    - `v2_semantic_contract_gate_pass=true`
    - `answer_vs_judgment_plan_gate_pass=true`
    - `metric_source_grounding_gate_pass=true`
    - `ledger_unit_gate_pass=true`
    - `qwen_answer_ratio=1.0`
- Decision:
  - Keep quiet mode as the default recommendation for human terminal inspection.
  - Treat the percentage phrase-boundary change as a root-cause validator fix, not a relaxation of the percentage-as-amount safety rule.

## Quiet Chat UX Hotfix - 2026-05-21
- Problem:
  - In `USER_OUTPUT=1 ... chat-deepseek`, after the user entered a prompt the terminal could appear frozen because quiet mode suppressed planner, retrieval, synthesis, and gate progress.
  - The first visible progress line previously occurred after Query Contract planning, so a slow LLM planner/API call had no immediate terminal feedback.
- Change:
  - Quiet mode now prints compact user-facing progress:
    - `[0/5] planning query scope ...`
    - `[scope] <n> companies; years=...`
    - `[1/5] retrieving and reranking SEC evidence ...`
    - `[2/5] building exact-value ledger ...`
    - `[3/5] building Judgment Plan ...`
    - `[4/5] asking <backend> ...`
    - `[5/5] running deterministic gates ...`
  - Detailed stage logs remain in `console_events.log`; BGE subprocess JSON/debug output remains hidden in user-output mode.
- Validation:
  - Local and cloud `python -m py_compile scripts/cloud/sec_agent_interactive.py` passed.
  - Cloud `bash -n scripts/cloud/sec_agent_interactive.sh` passed.
