# SEC Agent Multi-Turn Full-Chain Scope Revision Eval On 4090D

## Prompt
- User asked to run one complete multi-turn scenario after the cloud instance changed to an RTX 4090D node.
- Selected scenario: `multiturn_tool_scope_revision_001` / `continuous_scope_revision`.
- Target chain: `start_memo_analysis` -> `revise_memo_scope` -> `inspect_coverage` -> `explain_evidence`.

## Reasoning And Decisions
- This scenario is higher-signal than a reformat-only case because it exercises a new memo run, a follow-up scope revision, stale artifact invalidation, no-rerun coverage inspection, and evidence explanation in the same session.
- The 4090D instance had host driver `570.124.04` / CUDA `12.8`, while the base Python environment used `torch 2.11.0+cu130`; BGE CUDA reranking failed with `The NVIDIA driver on your system is too old`.
- The host NVIDIA driver is mounted into the container, so upgrading the driver inside the container would not replace the host kernel module. Instead, a separate venv was created at `/root/autodl-tmp/envs/sec-agent-cu128` with `torch 2.11.0+cu128` and `torchvision 0.26.0+cu128`.
- The full-chain runner uses that venv Python for both the controller wrapper and graph subprocesses, while DeepSeek remains API-only.

## Work Completed
- Added/used the full-chain scenario runner:
  - `scripts/cloud/run_sec_agent_multiturn_full_chain_scenario.py`
- Patched harness/controller behavior needed by the scenario:
  - `src/sec_agent/tool_harness.py`
    - `revise_memo_scope(..., graph_args=...)` now passes graph args into the re-executed memo DAG.
    - session active scope now prefers `query_contract.focus_tickers` / `query_contract.years` over graph-state retrieval universe.
    - follow-up scope revision query is rewritten as an independent revised-scope prompt so stale years/tickers from the prior turn are not inherited.
  - `src/sec_agent/tool_controller.py`
    - fills evidence ordinal such as "second growth driver" into `driver_index` when the model omits it.
    - falls back to deterministic heuristic routing when the tool-call API returns an error or no tool calls.
- Built a 4090D-compatible CUDA environment:
  - Python: `/root/autodl-tmp/envs/sec-agent-cu128/bin/python`
  - PyTorch: `2.11.0+cu128`
  - Torchvision: `0.26.0+cu128`
  - CUDA probe: `torch.cuda.is_available() == True`
  - BGE smoke: `CrossEncoder('/root/autodl-tmp/modelscope_cache/BAAI/bge-reranker-v2-m3', device='cuda')` loaded and scored sample pairs.

## Final Result
- Final cloud run:
  - Remote: `/root/autodl-tmp/FIN_Insight_Agent/reports/quality/cloud_multiturn_full_chain_scope_revision_20260523_r2_4090d_cu128/summary.json`
  - Local copy: `reports/quality/cloud_multiturn_full_chain_scope_revision_20260523_r2_4090d_cu128/summary.json`
- Metrics:
  - `turn_count=4`
  - `tool_pass_count=4`
  - `dispatch_pass_count=4`
  - `failure_count=0`
  - `all_pass=true`
  - `elapsed_sec=382.7851`
- Turn-level results:
  - `t1 start_memo_analysis`: pass; true graph execution; active scope `NVDA, AMD / 2024, 2025`; elapsed `217.1859s`.
  - `t2 revise_memo_scope`: pass; true graph execution; active scope `NVDA / 2024`; elapsed `160.7258s`.
  - `t3 inspect_coverage`: pass; no-rerun artifact read; elapsed `2.472s`.
  - `t4 explain_evidence`: pass; no-rerun artifact read; elapsed `2.3934s`.
- No deterministic fallback was needed in the final r2 run.
- Secret scan over fetched report files found `0` private-key matches.

## Earlier Failed/Diagnostic Attempts
- Previous cloud ports were interrupted by instance shutdowns.
- A 5090 rerun exposed two real harness issues before the final fix:
  - using graph-state `selected_tickers` as session scope leaked retrieval universe into scope revision;
  - appending the prior query to the revision prompt let the planner inherit stale year `2025`.
- A 4090D run using base Python failed in BGE CUDA because `torch 2.11.0+cu130` required a newer host driver than `570.124.04`.
- A DeepSeek route transient in an earlier run returned `RemoteDisconnected`; controller fallback was added so coverage/evidence turns can still route through deterministic tools.

## Follow-Up
- Reformat-only execution remains request-recording only in harness v0; a separate synthesis-only reformat execution path is still open.
- A broader 5-scenario full-chain suite would require completed fixture seeding or more graph executions; current evidence proves one complete continuous scope-revision scenario end to end.
