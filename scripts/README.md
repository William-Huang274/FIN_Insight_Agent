# Script Surface

This directory is intentionally limited to scripts that support the current
FinSight-Agent full-chain workflow, local data preparation, evaluation gates,
MCP serving, or workbench startup.

## Stable Entrypoints

- `cloud/sec_agent_interactive.sh`: public one-shot and multi-turn demo wrapper.
- `cloud/sec_agent_interactive.py`: full-source SEC / 8-K / market agent runtime.
- `cloud/sec_agent_graph_runner.py`: LangGraph execution wrapper used by the
  CLI, tool harness, and workbench.
- `cloud/sec_agent_context_session_cli.py`: session-oriented context runner.
- `evaluate_sec_agent_resume_closeout_readiness.py`: local release-readiness
  aggregator for context, source, market, latency, and structural checks.

## Current Data Preparation

- SEC filings and manifests: `download_sec_filings.py`,
  `build_sec_manifest.py`, `build_sec_mixed_latest_manifest.py`,
  `build_sec_chunks.py`.
- 8-K earnings evidence: `download_sec_8k_earnings.py`,
  `build_sec_8k_earnings_manifest.py`, `build_sec_8k_earnings_chunks.py`,
  `merge_sec_source_gaps.py`.
- Evidence and indexes: `build_evidence_store.py`,
  `build_structured_objects.py`, `build_bm25_index.py`,
  `build_object_bm25_index.py`, `build_object_sqlite_fts_index.py`,
  `indexing/`, and `ledger/`.
- Market snapshots: `market/06_*` through `market/60_*`.
- Sector / relationship coverage: `industry/`,
  `build_sector_depth_expansion_configs.py`, and
  `probe_sector_depth_source_availability.py`.

## Current Evaluation Gates

- Multi-agent layer gates: `eval_multi_agent_*.py` and
  `audit_multi_agent_*.py`.
- Context and controller checks: `evaluate_sec_agent_context_*.py`,
  `evaluate_sec_agent_tool_*.py`, `benchmark_sec_agent_context_api.py`,
  and `evaluate_sec_agent_latency_profile.py`.
- Benchmark runtime and post-gates: `run_sec_benchmark_eval.py`,
  `run_sec_benchmark_post_gates.py`, `run_sec_benchmark_vllm_synthesis_from_traces.py`,
  `run_sec_eval_synthesis_qwen9b_backend.py`,
  `run_sec_eval_synthesis_contract_backend.py`, `score_sec_benchmark_outputs.py`,
  and `validate_sec_benchmark_*` gate scripts that are invoked by the
  post-gate runner.

## Serving and Workbench

- `mcp/`: MCP tool contract export, stdio server, invocation, and smoke checks.
- `workbench/`: local workbench startup and environment helper scripts.

Historical experiment builders, reviewed-gold construction scripts, one-off
retrieval probes, and obsolete demo runners are intentionally kept out of the
main script surface. Historical worklog files may still mention them as prior
development records, but new users should start from this README, the root
README, and `docs/deployment/local_custom_data_quickstart.zh-CN.md`.
