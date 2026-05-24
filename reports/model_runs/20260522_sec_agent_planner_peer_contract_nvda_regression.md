# Model Run: 20260522_sec_agent_planner_peer_contract_nvda_regression

## Summary
- Purpose: Validate the planner/coverage fix for the NVDA growth + competitor free query.
- Status: diagnostic-only; original planner/retrieval bug fixed, final synthesis still has named-fact failures.
- Run type: inference + deterministic audit.
- Environment: cloud RTX 5090, `/root/autodl-tmp/FIN_Insight_Agent`.

## Code And Command
- Entry point: `scripts/cloud/sec_agent_interactive.sh ask-deepseek`.
- Prompt: `你觉得nvda的增长势头主要是因为什么，同行业的主要竞争对手是谁`
- Key settings: `USER_OUTPUT=1`, `PLANNER_MAX_TOKENS=2200`, `MAX_TOKENS=5000`, `TICKERS=ALL`, `YEARS=2023,2024,2025`, `LLM_BACKEND=deepseek`, `MODEL_NAME=deepseek-v4-pro`.
- Changed files:
  - `scripts/cloud/sec_agent_interactive.py`
  - `scripts/run_sec_benchmark_eval.py`
  - `src/sec_agent/query_contract.py`
  - `src/sec_agent/coverage_matrix.py`

## Results
- Planner-only smoke:
  - `planner=llm:deepseek:ok`
  - `task=company_comparison`
  - generated peer task with `AMD`, `INTC`, `AVGO`, `QCOM` and related semiconductor peers.
- Full-chain final run: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260522_142539_60a9e00112`
  - Coverage: `complete=True`, `primary_complete=True`, `answer_status=complete`
  - Support: `{'medium': 1, 'strong': 2}`
  - Ledger rows: `35`
  - Context rows: `120`
  - Gates: `pass=11`, `fail=['named_fact_gate_pass']`

## Interpretation
- The planner false-fallback bug is fixed. The chain now records valid planner output and produces a peer-aware Query Contract instead of falling back to a single NVDA-only trend task.
- Peer evidence is no longer completely pruned by BGE rerank; the runtime ledger now includes peer rows and coverage can verify peer tasks.
- The remaining failure is downstream synthesis: DeepSeek can still introduce unsupported product/category names in memo prose. This should be handled by a deterministic named-entity verification/sanitization pass or a two-step verified-claims renderer, not by more broad allowlists.

## Artifacts
- Planner/coverage/ledger diagnostic run with peer pruning issue: `20260522_140103_60a9e00112`
- Peer-reservation run with named-fact failure: `20260522_141138_60a9e00112`
- Named-product prompt constraint run with answer-vs-plan failure: `20260522_141910_60a9e00112`
- Latest run: `20260522_142539_60a9e00112`

## Safety Notes
- API key was passed through environment variable only and was not written to repo files.
- This run is diagnostic-only because one deterministic gate remains red.
