# 133 - SEC Agent API Memo v1 Schema Scaffold

## Summary
- Date: 2026-05-22
- Branch: `codex/api-model-call-architecture`
- Purpose: 将 API synthesis 从 `summary + decision_drivers + key_points` 推进到投研 memo 角色输出，同时保留 legacy fields 给现有 deterministic gates 使用。
- Status: local schema/prompt/normalization scaffold completed; no official cloud DeepSeek rerun yet.
- Secret policy: no API key, SSH password, or temporary credential is stored.

## Change
Added `api_memo_v1` as an API synthesis profile.

The new profile asks the model to output memo role fields:

```text
direct_answer
investment_thesis
what_changed
why_it_matters
peer_readthrough
counterarguments
watch_items
source_limitations
```

It also requires legacy compatibility fields:

```text
summary
decision_drivers
key_points
not_found
limitations
```

This keeps existing post-gates working while allowing the terminal renderer and memo-quality scorer to use the richer memo structure.

## Code Changes
- `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
  - Added `api_memo_v1` prompt rules.
  - Added memo JSON output schema.
  - Added memo-field normalization.
  - Added legacy fallback generation from memo fields when `summary`, `decision_drivers`, or `key_points` are missing.
- `scripts/cloud/sec_agent_interactive.py`
  - API backends now default to `SYNTHESIS_PROFILE=api_memo_v1`.
  - Added memo-specific system prompt.
  - Added memo renderer sections:
    - direct answer
    - investment thesis
    - key changes
    - why it matters
    - peer/competition readthrough
    - counterarguments and risks
    - watch items
    - source limitations
- `scripts/validate_sec_benchmark_answer_ledger.py`
  - Extended exact-value locations to memo fields.
- `scripts/validate_sec_benchmark_named_fact_support.py`
  - Extended named-fact support locations to memo fields.
- `scripts/score_sec_agent_memo_quality.py`
  - Memo fields are now first-class signals for structure, counterarguments, and watch items.

## Validation
- Compile passed:

```powershell
python -m py_compile `
  scripts\run_sec_eval_synthesis_qwen9b_backend.py `
  scripts\cloud\sec_agent_interactive.py `
  scripts\validate_sec_benchmark_answer_ledger.py `
  scripts\validate_sec_benchmark_named_fact_support.py `
  scripts\score_sec_agent_memo_quality.py
```

- Synthetic normalization smoke:
  - `has_direct_answer=true`
  - `legacy_drivers=1`
  - `legacy_points=1`
  - `what_changed=1`
  - `watch_items=1`
  - `_qwen_output_status=valid_json`
- Re-scored the old official NVDA output with the updated scorer:
  - unchanged score: `mean_score_total=0.777`
  - expected because the saved old output does not contain memo fields.

## Current Limitations
- This is a local scaffold and synthetic smoke, not a new cloud API inference result.
- The next official test must rerun the NVDA prompt through cloud DeepSeek with `api_memo_v1`.
- The memo fields are now included in ledger and named-fact gate locations, but broader semantic-contract gates may still need memo-aware text extraction after the first real run.

## Next Step
Run the representative NVDA prompt with:

```bash
USER_OUTPUT=1 SYNTHESIS_PROFILE=api_memo_v1 \
TICKERS=ALL YEARS=2023,2024,2025 \
bash scripts/cloud/sec_agent_interactive.sh chat-deepseek
```

Acceptance target:

```text
deterministic gates: 12/12 pass
memo_quality_score >= 0.82
counterargument_coverage >= 0.75
watch_item_coverage >= 0.75
memo_structure >= 0.85
no unresolved placeholder text
no raw metric_id leakage in user-facing text
```

## 2026-05-22 Cloud Closeout

Problem:
- First `api_memo_v1` cloud run returned a long DeepSeek JSON, but `MAX_TOKENS=5200` truncated the legacy `key_points` tail and forced `parse_error_ledger_repair`.
- After compacting the schema, a later run parsed but still fell into ledger repair because memo fields contained unsupported derived percentages such as customer-concentration thresholds and informal aggregate percentages.
- A named-fact gate also flagged watch-list machine text (`SEC-only`) and anonymized customer labels in `watch_items`.

Root-cause decision:
- Do not require the API model to emit both memo fields and legacy gate fields. The model should emit memo only; local normalization derives `summary`, `decision_drivers`, and `key_points` for deterministic gates.
- Keep hard numeric and named-fact boundaries. The fix is to sanitize memo fields before final contract checks, not to weaken gates.
- Treat `watch_items.source_to_watch` as a controlled enum and keep future-watch text at metric-family level rather than named anonymous-customer labels.

Code changes:
- `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
  - `api_memo_v1` schema now emits memo fields only plus `not_found`/`limitations`.
  - JSON extraction now uses shape-checked `raw_decode` scanning, avoiding false parses from nested objects inside truncated JSON.
  - Exact-value sanitizer now covers `direct_answer`, `investment_thesis`, `what_changed`, `why_it_matters`, `peer_readthrough`, `counterarguments`, `watch_items`, and `source_limitations`.
  - `watch_items.source_to_watch` is normalized to `future_10k` or `not_available_current_policy`.
  - `Direct Customer A/B` style anonymous labels are removed from future watch items and rendered as major-customer/customer-concentration observations.
- `scripts/cloud/sec_agent_interactive.py`
  - DeepSeek/API memo system prompt now asks for memo-only output and controlled watch-item source enums.

Validation:
- Local compile passed:

```powershell
python -m py_compile scripts\run_sec_eval_synthesis_qwen9b_backend.py scripts\cloud\sec_agent_interactive.py
```

- Cloud compile passed after syncing the patch to `/root/autodl-tmp/FIN_Insight_Agent`.
- Official cloud DeepSeek run:
  - run id: `20260522_023937_60a9e00112`
  - command profile: `USER_OUTPUT=1 SYNTHESIS_PROFILE=api_memo_v1 TICKERS=ALL YEARS=2023,2024,2025 MAX_TOKENS=5200 BGE_DEVICE=cuda`
  - prompt: `你觉得nvda的增长势头主要是因为什么，同行业的主要竞争对手是谁`
  - model: `deepseek-v4-pro`
  - status: `answered_qwen9b`
  - API latency: `103366 ms`
  - total elapsed: `244.5641 sec`
  - tokens: `input=21222`, `output=3463`, `total=24685`
  - ledger rows: `28`
  - context rows: `120`
  - post-gates: `12/12` pass, `qwen_answer_ratio=1.0`, `qwen_ledger_repaired=0`
  - memo quality: `mean_score_total=0.8505` vs threshold `0.82`
- Final deterministic replay after the last wording-polish sanitizer:
  - replay output: `eval/sec_cases/outputs/interactive_sec_agent/20260522_023937_60a9e00112/qwen_replay_final`
  - replay gates: `12/12` pass, `qwen_answer_ratio=1.0`
  - confirmed watch-item wording no longer contains `Direct Customer A/B` or `SEC-only` free text.

Artifacts:
- Cloud/local run directory: `eval/sec_cases/outputs/interactive_sec_agent/20260522_023937_60a9e00112`
- Model run report: `reports/model_runs/20260522_sec_agent_api_memo_v1_deepseek_nvda_competitor_final.md`

Remaining limitations:
- Memo quality still has weaker `causal_depth=0.5` and `peer_comparability=0.6` on this single NVDA case, mainly because competitor financial data was not selected into the evidence pack for direct comparison.
- The next architecture step should improve evidence selection and planner task decomposition for peer-comparison questions, not add more deterministic fallback rules.
