# Model Run: 20260522_sec_agent_api_insight_v2_deepseek_nvda_competitor_quality_v1

## Summary
- Purpose: 用 DeepSeek API `api_insight_v2` synthesis profile 复测 NVDA 增长驱动 + 竞争对手自由命题，验证在 BGE-M3 retrieval、runtime Exact-Value Ledger、Evidence Coverage Matrix、Judgment Plan 与 deterministic gates 约束下，API 模型是否能输出更有分析价值的答案。
- Status: completed，官方云端运行 all-green；运行后又做了一处用户输出清理补丁，尚未对该补丁做新的官方 API rerun。
- Run type: free-query inference + deterministic audit + quality scoring.
- Timestamp: 2026-05-22 01:00 Asia/Shanghai.
- Environment: cloud RTX 5090 path `/root/autodl-tmp/FIN_Insight_Agent`，local synced artifacts under `D:\FIN_Insight_Agent`.
- Secret policy: credentials were supplied only through runtime environment or interactive shell; no API key, SSH password, or token is stored in this report.

## Code And Command
- Branch: `codex/api-model-call-architecture`.
- Entry point: `scripts/cloud/sec_agent_interactive.sh chat-deepseek`.
- Synthesis backend: DeepSeek API, model `deepseek-v4-pro`, profile `api_insight_v2`.
- Retrieval path: full 30-company SEC universe, 2023/2024/2025, 10-K only, BM25 + BGE-M3 rerank on CUDA.
- Command shape:

```bash
USER_OUTPUT=1 SYNTHESIS_PROFILE=api_insight_v2 \
TICKERS=ALL YEARS=2023,2024,2025 \
bash scripts/cloud/sec_agent_interactive.sh chat-deepseek
```

- User query:

```text
你觉得nvda的增长势头主要是因为什么，同行业的主要竞争对手是谁
```

- Important dirty files in this iteration:
  - `scripts/cloud/sec_agent_interactive.py`
  - `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
  - `scripts/validate_sec_benchmark_named_fact_support.py`
  - `scripts/validate_sec_benchmark_v2_semantic_contracts.py`
  - `scripts/score_sec_agent_free_query_quality.py`

## Inputs
- Query Contract:
  - `task_type=company_comparison`
  - `focus_tickers=NVDA, AMD, INTC, AVGO`
  - `search_scope_tickers=30` companies
  - `years=2023,2024,2025`
  - `filing_types=10-K`
  - decomposed tasks:
    - `nvda_growth_drivers`
    - `competitor_identification_comparison`
    - `competitive_risk_analysis`
- Evidence Coverage Matrix:
  - `task_count=3`
  - support counts: `{'medium': 1, 'strong': 2}`
  - `coverage_complete=true`
  - `primary_task_support_complete=true`
- Runtime ledger:
  - `ledger_rows=62`
  - filtered out percentage-basis and change-column rows that should not be rendered as period exact values.
- Retrieved context:
  - `context_rows=120`

## Outputs
- Remote artifact root:
  - `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260522_010002_60a9e00112`
- Local synced artifact root:
  - `D:\FIN_Insight_Agent\eval\sec_cases\outputs\interactive_sec_agent\20260522_010002_60a9e00112`
- Key artifacts:
  - `query_contract.json`
  - `runtime_evidence_coverage_matrix.json`
  - `runtime_exact_value_ledger.json`
  - `runtime_judgment_plan.json`
  - `qwen\input_output.md`
  - `qwen\agent_outputs.jsonl`
  - `post_gates\sec_benchmark_post_gates_summary.json`
  - `free_query_quality_report.json`

## Results
- Deterministic gates:
  - `gates ok=True`
  - `pass=12`
  - `fail=[]`
  - `qwen_answer_ratio=1.0`
  - `answer_ledger_gate_pass=true`
  - `named_fact_gate_pass=true`
  - `v2_semantic_contract_gate_pass=true`
  - `answer_vs_judgment_plan_gate_pass=true`
  - `metric_source_grounding_gate_pass=true`
  - `ledger_unit_gate_pass=true`
- Semantic warnings:
  - `one_sided_peer_comparison_support=2`
  - These are warnings, not failures; they indicate peer comparison remains partly constrained by SEC disclosure comparability.
- Runtime:
  - `elapsed=289.48 sec` in the cloud interactive run.

## Free-Query Quality Score
- Report: `D:\FIN_Insight_Agent\eval\sec_cases\outputs\interactive_sec_agent\20260522_010002_60a9e00112\free_query_quality_report.json`
- `mean_score_total=0.9033`
- Dimension means:
  - `summary_thesis=1.0`
  - `driver_depth=0.82`
  - `evidence_binding=1.0`
  - `peer_role_coverage=1.0`
  - `caveat_quality=0.6`
  - `format_polish=1.0`
- Interpretation:
  - Compared with the earlier all-green baseline `20260521_234353_60a9e00112` (`mean_score_total=0.8575`), the API insight v2 profile improved thesis quality and driver depth while preserving deterministic gate safety.
  - The main remaining weakness is caveat quality and peer-comparison nuance, not raw citation grounding.

## Output Assessment
- Strong points:
  - The answer now gives a real thesis instead of only listing ledger values.
  - It connects NVDA growth to Compute & Networking revenue, margin expansion, operating cash flow, and R&D reinvestment.
  - It answers the competitor half of the query by separating direct GPU competitors, ASIC/networking competitors, CPU/foundry/platform competitors, and cloud self-developed-chip pressure.
  - Exact values are mostly attached to ledger-backed metric IDs and evidence IDs.
- Weak points:
  - The official run still contained one user-facing key point with `当前引用未保留的精确金额` for an AMD comparison. A post-run display-cleanup patch now drops such key points, but that cleanup has not yet been rerun as the official API result.
  - The answer is materially better than Qwen9B but still not a full professional equity research note: it lacks richer second-order synthesis such as sustainability, supply-chain bottlenecks, customer concentration, demand durability, and scenario-style counterarguments unless those are explicitly surfaced by retrieved SEC evidence.
  - The SEC-only boundary is working as intended, but it naturally limits market-share, valuation, pricing, and post-period claims.

## Decision
- Decision label: proceed with API-first RAG direction.
- Reason:
  - The DeepSeek/API synthesis route reaches better insight quality under the same evidence constraints than the local 9B path.
  - Deterministic artifacts remain useful as audit and source-boundary controls.
  - Further effort should shift from adding fallback rules to:
    - planner ontology/eval improvements;
    - broader free-query quality eval set;
    - coverage/ledger selection quality;
    - API synthesis prompt/schema iteration.
- Safety note:
  - Do not promote the post-run display-cleanup patch as verified by this official run until a fresh API rerun is completed.
