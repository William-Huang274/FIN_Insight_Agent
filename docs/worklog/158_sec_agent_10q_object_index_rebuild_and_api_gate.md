# 158 SEC Agent 10-Q Object Index Rebuild And API Gate Accounting

## Summary

- Date: 2026-05-24
- Scope: Stage 1 SEC 10-Q pilot follow-up after the multi-row table-header parser fix.
- Status: cloud 10-Q structured-object/object-BM25 rebuild complete; local API gate accounting fix complete; patched cloud rerun pending because the SSH endpoint became unreachable.

## Problem

The 10-Q source-scope contract fix in `157` corrected multi-row table header alignment so `Percentage Change` cells are no longer treated as period level values. Existing 10-Q structured objects and object BM25 records were generated before that fix, so future runs could still retrieve stale records unless the 10-Q object artifacts were rebuilt.

The follow-up DeepSeek resume also exposed a separate gate-accounting issue:

- The deterministic post-gate summary still used `qwen_answer_gate_pass` as the model-answer usage gate.
- That gate counted only `answered_qwen9b`, so a clean DeepSeek API answer would be treated as zero Qwen usage.
- A repaired or truncated API answer should remain visible and should not silently pass as a clean model answer.

This is a chain-accounting issue, not an answer fallback issue.

## Cloud Rebuild

Cloud repo:

- `/root/autodl-tmp/FIN_Insight_Agent`

Inputs:

- Evidence JSONL: `/root/autodl-tmp/FIN_Insight_Agent/data/processed_private/evidence_objects/sec_tech_10q_pilot_evidence_2026.jsonl`
- Structured-object prefix: `sec_tech_10q_pilot`
- Object BM25 index: `/root/autodl-tmp/FIN_Insight_Agent/data/indexes/bm25/sec_tech_10q_pilot_objects`

Commands run on cloud:

```bash
cd /root/autodl-tmp/FIN_Insight_Agent
/root/autodl-tmp/envs/sec-agent-cu128/bin/python scripts/build_structured_objects.py \
  --evidence-path data/processed_private/evidence_objects/sec_tech_10q_pilot_evidence_2026.jsonl \
  --output-dir data/processed_private/structured_objects \
  --prefix sec_tech_10q_pilot
/root/autodl-tmp/envs/sec-agent-cu128/bin/python scripts/build_object_bm25_index.py \
  --structured-dir data/processed_private/structured_objects \
  --prefix sec_tech_10q_pilot \
  --output-dir data/indexes/bm25/sec_tech_10q_pilot_objects
```

Rebuild elapsed time: about `4 sec`.

Artifact counts remained stable:

- `evidence_count=275`
- `table_count=233`
- `metric_count=5003`
- `claim_count=1888`
- Object BM25 records: `7124`

Contract check:

- Checked object: `MSFT_2026_10Q_ITEM2_BLOCK_0004_PART_01_OF_04_METRIC_TABLE_9D476233`
- Before rebuild, this row was the stale gross-margin `17%` risk path because it had no column label and carried `cell_kind=period_value`.
- After rebuild, it remains as a valid percentage-change metric object:
  - `column_label=Percentage Change`
  - `metadata.cell_kind=change_value`
  - `metadata.cell_key=gross_margin__percentage_change`
  - `metadata.form_type=10-Q`
  - `metadata.source_tier=primary_sec_filing`
- Targeted stale-record check: `wrong_records=[]`.

The private generated data and index files were not copied into the Git worktree and should not be committed.

## DeepSeek Resume Result

Prompt:

```text
只基于2026年10-Q证据，比较MSFT和AMZN云业务最新季度表现，并说明证据边界。
```

Original run root:

- `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260524_150433_3cc2b2f480`

The first run failed at synthesis with provider `HTTP 524`. Graph-state inspection showed retrieval, ledger, coverage, and Judgment Plan artifacts were already complete, with `resume.next_ready_node=synthesize_memo`.

Resume command used a reduced evidence pack:

- `EVIDENCE_PACK_CONTEXT_ROWS=48`
- `--max-tokens 2500`
- Resume node: `synthesize_memo`

Resume output:

- State status: `completed_with_gate_failures`
- Completed artifacts: `query_contract`, `retrieved_context`, `runtime_exact_value_ledger`, `evidence_coverage_matrix`, `judgment_plan`, `evidence_pack`, `memo_answer`, `claim_verification`, `deterministic_gates`, `rendered_answer`
- Evidence pack rows: `48`
- Ledger rows: `64`
- DeepSeek latency: `320113 ms`
- Tokens: `input_tokens=38487`, `output_tokens=2500`, `total_tokens=40987`
- Finish reason: `length`
- Answer status: `answered_api_model_truncation_repair`

Deterministic gate detail:

- Ledger gate: pass.
- Metric role term gate: pass.
- Table cell gate: pass or skipped where no expected cells were defined.
- Named fact gate: pass.
- Ledger missing consistency gate: pass.
- Caveat claim gate: pass.
- Semantic contract gate: pass.
- Answer-vs-Judgment-Plan gate: pass.
- Metric source grounding gate: pass.
- Ledger unit gate: pass.
- Coarse model-answer usage gate: failed because the output was a truncation-repaired API answer and the old gate only counted `answered_qwen9b`.

Targeted postchecks:

- No false “protocol has no numbers” sentence.
- No MSFT `17%` gross-margin level row in the runtime ledger.
- No MSFT `$6.4 billion` or `$20.4 billion` operating-income growth amount admitted as level operating income.
- No rendered markers for the known bad gross-margin or operating-income paths.

This run is useful as a diagnostic resume validation, but it is not a clean all-green API run because the provider output hit the token limit and required truncation repair.

## Local Fix

Changed files:

- `scripts/run_sec_benchmark_post_gates.py`
- `scripts/cloud/sec_agent_interactive.py`
- `tests/test_sec_benchmark_post_gate_usage.py`

Changes:

- Added backend-neutral model-answer usage accounting:
  - `answered_qwen9b` and `answered_api_model` count as clean model answers.
  - `answered_api_model_*` repair statuses are tracked separately as repaired model outputs and do not count as clean answers.
  - The summary now records `model_answer_ratio` in addition to the legacy `qwen_answer_ratio`.
- Kept `qwen_answer_gate_pass` name for compatibility, but it now uses `model_answer_ratio` when available.
- Reduced default synthesis evidence-pack rows from API-specific `96` to `48` for all backends. This lowers the default API prompt size and avoids making DeepSeek consume a 90-plus-row pack unless explicitly requested with `EVIDENCE_PACK_CONTEXT_ROWS`.
- Added regression tests proving clean API model answers count for the model-answer gate while truncation-repaired API answers remain separate.

Local validation:

```powershell
python -m py_compile scripts/run_sec_benchmark_post_gates.py scripts/cloud/sec_agent_interactive.py
python -m pytest tests/test_sec_benchmark_post_gate_usage.py tests/test_sec_agent_10q_source_contract.py
```

Result: `11 passed`.

## Cloud Patch Rerun Status

The next intended step was to upload the local patch to cloud and rerun the same 10-Q DeepSeek prompt with a smaller synthesis pack, targeting a clean `answered_api_model` output:

- `EVIDENCE_PACK_CONTEXT_ROWS=32`
- `--max-tokens 4000`

However, the cloud SSH endpoint `connect.westb.seetacloud.com:25360` began rejecting connections before the patched files could be uploaded:

- Retry count: `3`
- Result: unable to connect to port `25360`

No secrets or API keys were written to repository files.

## Decision

Proceed with the object-index rebuild as complete. The stale 10-Q object index risk identified in `157` is resolved on the cloud artifacts that current manual tests use.

Keep the patched API gate accounting and compact evidence-pack default as the next committed code change. It fixes a real post-gate accounting bug and keeps truncation repair visible instead of treating it as a clean answer.

## Follow-Up

- When the cloud SSH endpoint is reachable again, upload the patched files and rerun the 10-Q DeepSeek prompt with `EVIDENCE_PACK_CONTEXT_ROWS=32` and `--max-tokens 4000`.
- Accept the rerun only if `answer_status=answered_api_model`, deterministic gates pass, and targeted bad-marker checks remain empty.
- Do not promote truncation-repaired API output as an all-green run.
