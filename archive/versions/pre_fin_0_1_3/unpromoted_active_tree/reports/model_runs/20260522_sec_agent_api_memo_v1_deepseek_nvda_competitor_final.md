# Model Run: 20260522_sec_agent_api_memo_v1_deepseek_nvda_competitor_final

## Summary
- Purpose: Validate `api_memo_v1` DeepSeek synthesis for a free-query NVDA growth and competitor prompt under the full SEC RAG chain.
- Status: completed
- Run type: inference + deterministic audit + memo-quality evaluation
- Timestamp: 2026-05-22
- Environment: cloud RTX 5090 container, repo path `/root/autodl-tmp/FIN_Insight_Agent`

## Code And Command
- Entry point: `scripts/cloud/sec_agent_interactive.sh ask-deepseek`
- Command profile: `USER_OUTPUT=1 SYNTHESIS_PROFILE=api_memo_v1 TICKERS=ALL YEARS=2023,2024,2025 MAX_TOKENS=5200 BGE_DEVICE=cuda`
- User prompt: `你觉得nvda的增长势头主要是因为什么，同行业的主要竞争对手是谁`
- Model route: `deepseek-v4-pro` through API synthesizer role.
- Secret handling: API key and SSH credentials were used only at runtime and were not written to repo files.

## Inputs
- Universe: 30 SEC companies, 2023/2024/2025, 10-K sources.
- Retrieval: BM25 + BGE-M3 rerank on CUDA.
- Runtime ledger: `eval/sec_cases/outputs/interactive_sec_agent/20260522_023937_60a9e00112/runtime_exact_value_ledger.json`
- Judgment Plan: `eval/sec_cases/outputs/interactive_sec_agent/20260522_023937_60a9e00112/runtime_judgment_plan.json`
- Evidence coverage matrix: `eval/sec_cases/outputs/interactive_sec_agent/20260522_023937_60a9e00112/runtime_evidence_coverage_matrix.json`

## Model Parameters
- Synthesis profile: `api_memo_v1`
- Max output tokens: `5200`
- API response tokens: `input=21222`, `output=3463`, `total=24685`
- API latency: `103366 ms`
- Total chain elapsed: `244.5641 sec`

## Outputs
- Official run directory: `eval/sec_cases/outputs/interactive_sec_agent/20260522_023937_60a9e00112`
- Raw model output: `eval/sec_cases/outputs/interactive_sec_agent/20260522_023937_60a9e00112/qwen/raw_model_outputs.jsonl`
- Terminal-facing output: `eval/sec_cases/outputs/interactive_sec_agent/20260522_023937_60a9e00112/qwen/input_output.md`
- Final deterministic replay after wording polish: `eval/sec_cases/outputs/interactive_sec_agent/20260522_023937_60a9e00112/qwen_replay_final`
- Memo quality report: `eval/sec_cases/outputs/interactive_sec_agent/20260522_023937_60a9e00112/memo_quality_report.json`

## Results
- Answer status: `answered_qwen9b`
- Ledger rows: `28`
- Context rows: `120`
- Post-gates: `12/12` pass
- `qwen_answer_ratio`: `1.0`
- `qwen_ledger_repaired`: `0`
- Memo quality: `0.8505` versus pass threshold `0.82`
- Quality dimensions:
  - thesis_clarity: `0.95`
  - causal_depth: `0.50`
  - evidence_usefulness: `1.00`
  - counterargument_coverage: `1.00`
  - watch_item_coverage: `1.00`
  - peer_comparability: `0.60`
  - source_boundary: `1.00`
  - memo_structure: `1.00`
  - format_polish: `0.45`

## Experiment Governance
- Hypothesis: A memo-only API schema plus deterministic memo normalization can preserve exact-value/source gates while improving user-facing investment-memo structure.
- Decision target: One representative NVDA competitor prompt must pass all deterministic gates, avoid ledger repair, and score at least `0.82` on memo-quality rubric.
- Baseline: prior `api_memo_v1` cloud run truncated or fell into ledger repair; prior `api_insight_v2` passed gates but lacked explicit memo sections.
- Stop conditions: Any parse fallback, ledger repair, named-fact failure, or `memo_quality < 0.82` blocks promotion.
- Decision label: proceed for representative-case validation.
- Mainline decision: `api_memo_v1` is viable for the interactive API path, with next work focused on planner/evidence coverage for peer-comparison depth.

## Runtime Efficiency
- End-to-end wall time: `244.5641 sec`
- API synthesis latency: `103.366 sec`
- Retrieval/rerank and deterministic artifact build accounted for the remaining time.
- Serving implication: API synthesis avoids local vLLM GPU residency but still has high total latency due to retrieval/rerank plus large evidence prompt size.

## Caveats And Next Step
- This is a single representative prompt, not the full 5-case memo eval set.
- The final wording-polish sanitizer was verified by raw replay (`qwen_replay_final`) rather than a second paid API call.
- Causal depth and peer comparability are still weaker than desired because peer financial evidence was not selected into the final evidence pack.
- Next decision: run the 5-case memo eval set and improve Evidence Coverage Matrix selection for competitor/peer questions before broad production claims.
