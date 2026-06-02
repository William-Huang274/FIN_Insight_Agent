# Model Run: 20260531_multi_agent_step17_relationship_skill_v0_2_full_chain_deepseek_v0_1

## Summary

- Purpose: verify the Step17 full-chain behavior after adding the Industry/Supply-Chain balanced relationship row selector, explicit `relationship_summary` prompt payload, relationship evidence citation gates, and Specialist role-specific skill v0.2.
- Status: accepted for diagnostic Step17 relationship-evidence gate.
- Run type: inference evaluation.
- Timestamp: started `2026-05-31T07:30:47.205379+00:00`; elapsed `1103396 ms`.
- Environment: local Windows / PowerShell workspace, DeepSeek API, in-process retrieval runner, BGE rerank configured for CUDA.
- Owner / agent: Codex.

## Code And Command

- Entry point: `scripts/eval_multi_agent_real_llm_chain.py`
- Command shape:

```powershell
$env:DEEPSEEK_API_KEY="<redacted>"
python scripts/eval_multi_agent_real_llm_chain.py `
  --category sector_depth `
  --real-evidence-operators `
  --strict `
  --run-id 20260531_step17_relationship_skill_v0_2_full4_rerun_cuda_deepseek_v0_1 `
  --llm-backend deepseek `
  --base-url https://api.deepseek.com `
  --model deepseek-v4-pro `
  --api-key-env DEEPSEEK_API_KEY `
  --context-runner in_process `
  --bge-device cuda
```

- Config / summary output: `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/20260531_step17_relationship_skill_v0_2_full4_rerun_cuda_deepseek_v0_1/real_chain_eval_summary.json`
- Git state: dirty worktree with ongoing multi-agent source, eval, and worklog changes; API key and raw LLM responses were not saved.
- Seeds: no random seed configured; deterministic gates inspect persisted runtime artifacts.

## Inputs

- Cases: `tests/fixtures/multi_agent_real_llm_chain_cases_v0_1.jsonl`
- Selected category: `sector_depth`
- Case scope: AI infrastructure, banking, healthcare, energy / utilities.
- Retrieval boundary: real evidence operators enabled; `sec_search_filings` used real BM25/ObjectBM25/BGE rerank through the in-process context runner.
- Relationship boundary: `relationship_graph_lookup`, sector-depth packs, `UniverseRelationshipPlan`, and `relationship_graph_observation` fallback.
- Specialist boundary: bounded agent data views plus compact `relationship_summary`; Specialist LLMs must cite known evidence refs only.

## Model Parameters

- Provider/model: DeepSeek `deepseek-v4-pro`.
- API key handling: read from `DEEPSEEK_API_KEY` environment variable only; no plaintext key persisted.
- BGE config: `bge_device=cuda`, `bge_model_ref=953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`, candidate limit `160`, top-k `32`, batch size `8`, max length `512`.
- Raw LLM response saved: false.

## Outputs

- Summary JSON: `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/20260531_step17_relationship_skill_v0_2_full4_rerun_cuda_deepseek_v0_1/real_chain_eval_summary.json`
- Persistent model-run report: this file.
- Worklog summary: `docs/worklog/210_multi_agent_relationship_data_view_and_skill_v0_2.md`

## Results

Primary metrics:

| Metric | Value |
| --- | ---: |
| Case count | 4 |
| Passed | 4 |
| Failed | 0 |
| Pass rate | 1.0 |
| Total tool calls | 39 |
| Real retrieval required cases | 4 |
| Real Specialist quality required cases | 4 |
| Real Specialist quality passed | 4 |

Case-level runtime and evidence checks:

| Case | Gate | Tool calls | SEC search calls | SEC errors | Context rows | BGE candidates | Industry relationship gate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| AI infrastructure | pass | 11 | 6 | 0 | 96 | 96 | pass |
| Banking | pass | 9 | 4 | 0 | 52 | 52 | pass |
| Healthcare | pass | 8 | 4 | 0 | 57 | 57 | pass |
| Energy / utilities | pass | 11 | 5 | 0 | 72 | 72 | pass |

Agent status:

- Research Lead: activated `deep_research` in all four cases.
- Universe / Relationship: LLM invoked, validation passed, relationship lookup called, relationship lookup status `ok`.
- Evidence Operators: expected SEC / market / industry / relationship operators were called; SEC search errors were `0`; BGE candidate counts were positive.
- Specialist layer: route success and real evidence quality are tracked separately; both passed for all four cases.
- Industry/Supply-Chain Specialist: input source families included both `industry_snapshot` and `relationship_graph` in all four cases; observed source families also included `relationship_graph`; relationship evidence refs were cited.
- Memo Writer / Verifier: memo status `draft`, specialist verification `pass`, claim verification `pass` in all four cases.

Relationship citation refs by case:

- AI infrastructure: `sector_depth_pack:technology_ai_infrastructure_depth:ANET`, `DELL`, `HPE`, `LRCX`, `MRVL`, `SMCI`, `VRT`.
- Banking: `sector_depth_pack:financial_services_depth:C`, `CB`, `COF`, `GS`, `SCHW`, `WFC`.
- Healthcare: `sector_depth_pack:healthcare_life_sciences_depth:ABT`, `AMGN`, `BMY`, `DHR`, `HCA`, `MDT`, `PFE`.
- Energy / utilities: `sector_depth_pack:technology_ai_infrastructure_depth:ANET`, `DELL`, `HPE`, `KLAC`, `LRCX`, `MRVL`, `SMCI`, `SNPS`.

## Experiment Governance

- Hypothesis: preserving relationship rows in the Industry/Supply-Chain data view and explicitly passing `relationship_summary` should make sector-depth Specialists use relationship evidence instead of generic industry rows.
- Decision target: Step17 sector-depth full-chain pass `4/4`; real retrieval enabled; Industry Specialist must see and cite `relationship_graph` evidence when relationship gates are required.
- Ceiling / upper bound: bounded to currently available sector-depth packs and relationship graph fixtures; not a claim of complete production universe coverage.
- Baseline: prior post-patch local unit tests passed, but the first real full-chain rerun exposed relationship drop / transport failure cases.
- Split and leakage guard: fixed eval fixture, real retrieval, no manual case editing between failed-case rerun and full four-case rerun.
- Stop conditions: fail if any case has missing relationship evidence citation, SEC dry-run retrieval, provider transport failure, unsupported Specialist refs, or claim verification failure.
- Efficiency gate: BGE must report CUDA availability and positive candidate counts; total run must complete without loop-budget or duplicate-call breaks.
- Decision label: proceed as diagnostic Step17 gate, with semantic-pack relevance caveats below.
- Mainline decision: relationship row selector, `relationship_summary` prompt payload, and v0.2 Specialist skill gates are accepted for the diagnostic multi-agent chain.

## Runtime Efficiency

- Wall time: `1103396 ms` for four cases.
- Per-case elapsed: AI infrastructure `225494 ms`, banking `249956 ms`, healthcare `292560 ms`, energy / utilities `335305 ms`.
- GPU / BGE evidence: runtime metadata reported `bge_device=cuda` and `cuda_available=true`; positive BGE candidate counts were observed for all cases.
- GPU utilization caveat: no external GPU load trace was persisted; this run relies on runtime metadata and positive BGE candidate accounting rather than a sampled utilization log.
- Bottleneck diagnosis: LLM latency dominates the full-chain runtime; BGE rerank appears active but is not the primary wall-time driver.
- Serving implication: four-case diagnostic batch is too slow for interactive serving without caching, narrower agent activation, or parallelized Specialist/LLM calls.

## Caveats And Next Step

- Raw LLM responses and plaintext API key were not saved.
- SEC search summaries for these text-heavy sector-depth cases returned real context rows, but numeric runtime ledger rows were not materialized in the per-tool summaries. If future cases require numeric metric claims, add a gate that requires ledger rows by metric-family.
- Energy / utilities passed the current relationship gate by citing AI-infrastructure depth-pack relationship refs. This is acceptable only for data-center power-demand transmission questions; add a semantic-pack relevance gate before treating utilities relationship coverage as complete.
- Next decision: expand real multi-turn evaluation and add stricter relationship-pack semantic matching.
