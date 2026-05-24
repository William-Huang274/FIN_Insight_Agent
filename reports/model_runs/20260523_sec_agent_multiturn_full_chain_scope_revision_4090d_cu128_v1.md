# Model Run: 20260523_sec_agent_multiturn_full_chain_scope_revision_4090d_cu128_v1

## Summary
- Purpose: Validate one real multi-turn SEC agent chain with DeepSeek tool routing, harness dispatch, two true graph executions, and no-rerun artifact inspection.
- Status: completed
- Run type: inference evaluation
- Timestamp: 2026-05-23 Asia/Shanghai
- Environment: SeeTaCloud RTX 4090D, Ubuntu 22.04 container, host NVIDIA driver `570.124.04`, venv `/root/autodl-tmp/envs/sec-agent-cu128`.

## Code And Command
- Entry point: `scripts/cloud/run_sec_agent_multiturn_full_chain_scenario.py`
- Scenario: `multiturn_tool_scope_revision_001`
- Python: `/root/autodl-tmp/envs/sec-agent-cu128/bin/python`
- Command shape:

```bash
DEEPSEEK_API_KEY=<env> /root/autodl-tmp/envs/sec-agent-cu128/bin/python \
  scripts/cloud/run_sec_agent_multiturn_full_chain_scenario.py \
  --scenario-id multiturn_tool_scope_revision_001 \
  --output-dir reports/quality/cloud_multiturn_full_chain_scope_revision_20260523_r2_4090d_cu128 \
  --python /root/autodl-tmp/envs/sec-agent-cu128/bin/python \
  --llm-backend deepseek \
  --base-url https://api.deepseek.com \
  --chat-completions-path /chat/completions \
  --model deepseek-v4-pro \
  --api-key-env DEEPSEEK_API_KEY \
  --query-planner llm \
  --bge-device cuda
```

- Dirty files relevant to this run:
  - `src/sec_agent/tool_harness.py`
  - `src/sec_agent/tool_controller.py`
  - `scripts/cloud/run_sec_agent_multiturn_full_chain_scenario.py`
- Seeds: not applicable.

## Inputs
- Eval set: `eval_sets/sec_agent_multiturn_tool_harness_eval_reviewed_v1.json`
- Scenario ID: `multiturn_tool_scope_revision_001`
- Initial session: `s_tool_001`, user `u_research_001`, tenant `tenant_demo`
- Source boundary: `SEC_ONLY_10K`
- Data/indexes:
  - `data/processed_private/manifests/sec_tech_10k_manifest.jsonl`
  - `data/indexes/bm25/sec_tech_10k`
  - `data/indexes/bm25/sec_tech_10k_objects`
  - `/root/autodl-tmp/modelscope_cache/BAAI/bge-reranker-v2-m3`

## Model Parameters
- Controller/synthesizer/planner model: DeepSeek `deepseek-v4-pro`
- Controller temperature: `0.0`
- Planner: `--query-planner llm`
- Reranker: BGE `BAAI/bge-reranker-v2-m3`
- Reranker device: `cuda`
- PyTorch environment: `torch 2.11.0+cu128`, `torchvision 0.26.0+cu128`
- Local LLM: not used.

## Outputs
- Remote summary: `/root/autodl-tmp/FIN_Insight_Agent/reports/quality/cloud_multiturn_full_chain_scope_revision_20260523_r2_4090d_cu128/summary.json`
- Local summary: `reports/quality/cloud_multiturn_full_chain_scope_revision_20260523_r2_4090d_cu128/summary.json`
- Local runner log: `reports/quality/cloud_multiturn_full_chain_scope_revision_20260523_r2_4090d_cu128/runner.log`
- Local session state: `reports/quality/cloud_multiturn_full_chain_scope_revision_20260523_r2_4090d_cu128/session_state.json`
- Graph run roots:
  - t1: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260523_010719_87a75d82a6`
  - t2: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260523_011055_8318245185`

## Results
- Overall:
  - `turn_count=4`
  - `tool_pass_count=4`
  - `dispatch_pass_count=4`
  - `failure_count=0`
  - `all_pass=true`
  - `elapsed_sec=382.7851`
- Turns:
  - t1 `start_memo_analysis`: tool/dispatch/scope pass; graph returncode `0`; elapsed `217.1859s`.
  - t2 `revise_memo_scope`: tool/dispatch/scope pass; graph returncode `0`; elapsed `160.7258s`.
  - t3 `inspect_coverage`: tool/dispatch/scope pass; no graph rerun; elapsed `2.472s`.
  - t4 `explain_evidence`: tool/dispatch/scope pass; no graph rerun; elapsed `2.3934s`.
- Final session scope: `NVDA / 2024 / SEC_ONLY_10K`.
- No fallback routing was needed in the final run.

## Experiment Governance
- Hypothesis: A session-aware harness plus DeepSeek tool controller can preserve multi-turn context, rerun only when scope changes, and reuse artifacts for follow-up inspection/evidence questions.
- Decision target: one full continuous scope-revision scenario passes tool selection, dispatch execution, and active-scope checks on all turns.
- Ceiling / upper bound: this is a one-scenario end-to-end validation, not a broad reliability estimate.
- Baselines: earlier route-only eval passed `18/18`; fixture dispatch passed `5/5`; real resume replay passed from `synthesize_memo`.
- Split and leakage guard: SEC-only 10-K data; no external news/market data; user/session IDs fixed by runtime context.
- Stop conditions: any tool mismatch, failed graph dispatch, stale AMD/2025 scope after revision, or graph rerun on coverage/evidence turns.
- Efficiency gate: feasible on one 4090D with BGE on CUDA; local LLM not required.
- Decision label: proceed
- Mainline decision: Accept as the first real multi-turn full-chain scenario pass; broader multi-scenario full-chain and reformat execution remain follow-ups.

## Runtime Efficiency
- Wall time: `382.7851s`
- Stage timing:
  - t1 true graph: `217.1859s`
  - t2 true graph: `160.7258s`
  - t3 artifact read: `2.472s`
  - t4 artifact read: `2.3934s`
- GPU utilization: BGE reranker used CUDA; smoke allocated about `2175 MB`; full graph observed BGE usage around `3.7 GB`.
- Bottleneck diagnosis: graph turns are dominated by retrieval/reranking and DeepSeek API planner/synthesis latency; artifact reads are low-latency.
- Efficiency improvement: reuse loaded reranker in an in-process retrieval service for repeated graph turns; keep artifact tools no-rerun.
- Serving implication: multi-turn follow-up inspection/evidence turns are suitable for interactive latency; scope-changing turns remain batch-like unless retrieval/model calls are made persistent.

## Caveats And Next Step
- Not run: full 5-scenario full-chain suite; reformat synthesis-only execution.
- Known risks: venv uses `--system-site-packages`; this was chosen for speed and compatibility with existing repo dependencies. It should not be used for local vLLM without a separate compatibility pass.
- Reproduce: use the command shape above with the DeepSeek key provided via environment variable only.
- Next decision: add either a reformat-only execution path or a broader multi-scenario state/context stress run.
