# Model Run: 20260521_sec_agent_interactive_runtime_ledger_qwen9b_5090_smoke

## Summary
- Purpose: Validate the free-prompt interactive SEC agent path, not bare Qwen chat.
- Status: completed
- Run type: inference smoke + deterministic gates
- Timestamp: 2026-05-21 Asia/Shanghai
- Environment: cloud, RTX 5090 32GB, resident vLLM Qwen9B server, BGE-M3 on CPU.

## Code And Command
- Entry point: `scripts/cloud/sec_agent_interactive.sh`
- Core script: `scripts/cloud/sec_agent_interactive.py`
- Command:
```bash
cd /root/autodl-tmp/FIN_Insight_Agent
TICKERS=NVDA YEARS=2025 EVIDENCE_TOP_K=1 OBJECT_TOP_K=1 MAX_CONTEXT_ROWS=24 RERANKER_TOP_K=24 LEDGER_MAX_ROWS=12 \
  bash scripts/cloud/sec_agent_interactive.sh ask "基于 NVIDIA 2025 10-K，概括数据中心收入、资本开支或供应风险对 AI 业务的含义；只使用 SEC 证据。"
```
- Config: runtime defaults plus scoped smoke overrides above.
- Seeds: deterministic retrieval/gate path; no random seed set for Qwen generation, `temperature=0.0`.

## Inputs
- SEC manifest: `data/processed_private/manifests/sec_tech_10k_manifest.jsonl`
- Evidence BM25 index: `data/indexes/bm25/sec_tech_10k`
- Object BM25 index: `data/indexes/bm25/sec_tech_10k_objects`
- Scope: `NVDA`, fiscal year `2025`, filing type `10-K`
- Candidate boundary: retrieved SEC evidence and structured objects only.
- Leakage guard: final exact values may only come from runtime exact-value ledger.

## Model Parameters
- Retrieval reranker: `/root/autodl-tmp/modelscope_cache/BAAI/bge-reranker-v2-m3`
- BGE device: `cpu`
- LLM: Qwen9B served by vLLM OpenAI-compatible API as `qwen9b`
- `MAX_TOKENS`: default script setting `2400`
- `temperature`: `0.0`
- Qwen thinking: disabled via `chat_template_kwargs.enable_thinking=false`

## Outputs
- Artifact root: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260521_012901_f1a4d86d5f`
- Trace: `trace/trace_logs.jsonl`
- Runtime ledger: `runtime_exact_value_ledger.json`
- Runtime Judgment Plan: `runtime_judgment_plan.json`
- Qwen outputs: `qwen/agent_outputs.jsonl`, `qwen/raw_model_outputs.jsonl`
- Post-gates: `post_gates/sec_benchmark_post_gates_summary.json`

## Results
- `gates ok`: true
- pass gates: 12
- fail gates: 0
- `qwen_answer_ratio`: 1.0
- `qwen_answered`: 1
- `qwen_ledger_repaired`: 0
- `fallback_answered`: 0
- ledger rows: 2
- context rows: 10
- elapsed: 80.92 sec

## Interpretation
- The interactive port is confirmed to use the constrained engineering path:
  SEC retrieval -> BGE-M3 rerank -> runtime exact-value ledger -> Judgment Plan -> Qwen9B -> deterministic post-gates.
- This is not a reviewed-gold case. The ledger is runtime-built and gate-checked, but not manually reviewed.
- Output quality improved after filtering low-signal `% of net revenue` rows and prioritizing `data_center_revenue` before generic `revenue`.

## Efficiency Notes
- The smoke was intentionally small, with `EVIDENCE_TOP_K=1`, `OBJECT_TOP_K=1`, and `RERANKER_TOP_K=24`.
- Wall time was dominated by CPU BGE-M3 rerank and end-to-end gate execution.
- BGE remains on CPU because Qwen9B occupies most available RTX 5090 VRAM while resident.

## Safety Notes
- No SSH password, token, or temporary credential is recorded here.
- The command is reproducible from the remote repo path while the resident Qwen9B server is available.
