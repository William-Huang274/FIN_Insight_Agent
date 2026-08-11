# Model Run: 20260524_sec_agent_10q_pilot_deepseek_api_smoke_v1

## Summary

- Purpose: Validate the 2026 SEC 10-Q pilot through the real DeepSeek API synthesis path and inspect rendered user output.
- Status: completed diagnostic smoke.
- Run type: inference smoke.
- Timestamp: 2026-05-24.
- Environment: cloud `/root/autodl-tmp/FIN_Insight_Agent`, Python `/root/autodl-tmp/envs/sec-agent-cu128/bin/python`, BGE CUDA rerank, DeepSeek API backend.

## Code And Command

- Entry point: `scripts/cloud/sec_agent_interactive.py`
- Git state during run: dirty local/cloud scripts while iterating on 10-Q rendering and ledger filters.
- Command shape: same as `docs/worklog/156_sec_agent_10q_deepseek_api_smoke.md`; API key supplied only via `DEEPSEEK_API_KEY` process environment.
- Prompt: `只基于2026年10-Q证据，比较MSFT和AMZN云业务最新季度表现，并说明证据边界。`

## Inputs

- Manifest: `data/processed_private/manifests/sec_tech_10q_pilot_manifest_2026.jsonl`
- Evidence BM25 index: `data/indexes/bm25/sec_tech_10q_pilot`
- Structured object BM25 index: `data/indexes/bm25/sec_tech_10q_pilot_objects`
- Scope: `tickers=MSFT,AMZN`, `years=2026`, `filing_types=10-Q`.
- Source policy: SEC-only 10-Q pilot evidence; no market data, news, 8-K, earnings calls, or analyst consensus.

## Outputs

- Run root: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260524_125319_3cc2b2f480`
- Rendered answer: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260524_125319_3cc2b2f480/qwen/rendered_answer.md`
- Query Contract: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260524_125319_3cc2b2f480/query_contract.json`
- Runtime ledger: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260524_125319_3cc2b2f480/runtime_exact_value_ledger.json`
- Gate summary: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260524_125319_3cc2b2f480/post_gates/sec_benchmark_post_gates_summary.json`

## Results

- Total elapsed: `92.1937 sec`
- DeepSeek latency: `52892 ms`
- Total tokens: `57193`
- Runtime ledger rows: `66`
- Retrieved context rows: `120`
- Quality score: `mean_score_pct=0.88`
- Individual deterministic factual gates passed:
  - answer ledger
  - metric role term
  - named fact
  - ledger missing consistency
  - abstract judgment
  - caveat claim
  - v2 semantic contract
  - answer vs Judgment Plan
  - metric source grounding
  - ledger unit
- `qwen_answer_gate_pass=false`, with no scored failure types; claim verifier downgraded 6 candidate claims and rejected 0.

## Interpretation

The real API path is operational for the 10-Q pilot. The final rendered answer is suitable for manual inspection and no longer shows raw JSON or unresolved exact-value placeholders. The output properly labels the 10-Q evidence boundary and uses readable evidence refs.

The run remains diagnostic because it is a two-company 10-Q-only pilot and because the broader `qwen_answer_gate_pass` threshold still flags quality conservatism even when the deterministic factual gates pass.

## Safety Notes

- No API key, SSH password, or cloud credential was written to this report.
- Generated cloud artifacts remain under `eval/sec_cases/outputs/interactive_sec_agent/` and are not staged.
- Follow-up should add local regression tests before treating this as a stable 10-Q production path.
