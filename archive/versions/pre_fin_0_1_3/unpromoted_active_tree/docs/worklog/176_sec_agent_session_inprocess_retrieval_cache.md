# 176 SEC Agent Session In-Process Retrieval Cache

## Prompt

继续 P0 提效：在上一轮 BM25/ObjectBM25/ledger 优化后，继续处理 interactive/session 每轮重复启动检索 runner、重复加载索引和 BGE reranker 的固定成本。

## Decision

这次不改变检索质量合同、不改 source policy、不放宽 gates。只改运行生命周期：

- 普通 `chat/ask` 入口：新增 `context_runner=auto|in_process|subprocess`，默认在 DeepSeek/API 场景走 in-process context preparation。
- 真实 `session-*` 入口：默认 `graph_execution=in_process`，让 `SecAgentToolHarness` 在 session 进程内直接调用 `sec_agent_interactive.run_one()`，从而让 BM25/ObjectBM25/BGE cache 跨 follow-up turn 保留。
- 本地 Qwen + `BGE_FIRST=1` 默认仍保留 subprocess context runner，避免 BGE 常驻 GPU 后影响 Qwen vLLM 显存。

## Work Completed

- `scripts/cloud/sec_agent_interactive.py`
  - 引入 `run_sec_benchmark_eval.py` 的 `_prepare_trace/_run_synthesis_backend/_summary` 作为 in-process context runner。
  - 新增 `--context-runner`，默认 `auto`。
  - 新增 `_CONTEXT_RUNTIME_CACHE`，按 BM25 index、object index、BGE model/device/max_length 缓存：
    - `BM25Retriever`
    - `ObjectBM25Retriever`
    - BGE `CrossEncoder`
  - 新增 manifest index cache，按 manifest file stat 自动失效。
  - in-process runner 写回原有 benchmark-compatible artifacts：
    - `trace_logs.jsonl`
    - `agent_outputs.jsonl`
    - `claim_verification.jsonl`
    - `scores.jsonl`
    - `bad_cases.md`
    - `run_summary.json`
  - `SecAgentState` artifact/stage metadata 记录 `context_runner`、`context_cache_hit`、`context_cache_key`、资源加载耗时等信息。
  - `run_data_fingerprint.json` 和 `--print-config` 现在记录 requested/effective context runner。
- `src/sec_agent/tool_harness.py`
  - 新增 `graph_execution=in_process|subprocess`，默认 `in_process`。
  - `start_memo_analysis` / scope revision 的真实 DAG 执行可以不再每轮起 `sec_agent_graph_runner.py` 子进程。
  - in-process execution 复用同一个 loaded `sec_agent_interactive.py` module，因此普通 Python globals 里的 retrieval cache 可跨当前 session 的多轮问题保留。
  - 保留 subprocess 模式用于隔离式排障。
- `scripts/cloud/sec_agent_context_session_cli.py`
  - 新增 `--graph-execution`，默认读取 `SEC_AGENT_GRAPH_EXECUTION`，否则 `in_process`。
  - start banner 显示当前 graph execution 模式。
  - 新增并透传 `--market-evidence-path`、`--market-snapshot-id`、`--market-as-of-date`，使 session 主链路能够真正进入 SEC/8-K + market snapshot full-source 路径。
- `scripts/cloud/sec_agent_interactive.sh`
  - `chat/ask/session` wrapper 透传 `MARKET_EVIDENCE_PATH`、`MARKET_SNAPSHOT_ID`、`MARKET_AS_OF_DATE`，避免市场快照只在底层 Python 入口可用、session 入口不可用。
- `src/sec_agent/tool_controller.py`
  - 修复真实 DeepSeek follow-up 中的工具路由误判：泛化“继续分析/进一步说明/估值证据边界”不应被 `explain_evidence`、`resume_analysis` 或 `get_session_state` 吞掉。
  - 工具名先 `.strip()` 再 allowlist/guard，避免 API 返回带空白或变体工具名时绕过 guard。
  - heuristic 的“继续”语义收紧：只有“继续跑/恢复/中断/没跑完/简单继续”才走 `resume_analysis`；带比较、分析、估值、市场反应的追问继续走 `start_memo_analysis`。
- Tests
  - 覆盖 `auto` runner 在本地 Qwen+BGE-first 下选择 subprocess。
  - 覆盖 in-process context runner 写出 benchmark-compatible artifacts。
  - 覆盖 session harness 的 in-process graph execution 合同。
- Post-cloud fixes
  - `SecAgentToolHarness` 在真实 graph execution 中将 harness 推断出的 `selected_tickers` 透传到 `sec_agent_interactive.py --tickers`，避免 follow-up 在已有 session 下重新扩成 full30 检索。
  - Query Contract repair 增加显式市场数据否定约束：当 prompt 包含“不要引入股价/市场数据”等约束时，移除 `market_snapshot` block、`market_snapshot` source tier 和 task-level market requirement，而不是让 planner 的市场意图污染 SEC/8-K-only follow-up。

## Local Validation

Commands:

```powershell
python -m py_compile scripts/cloud/sec_agent_interactive.py scripts/cloud/sec_agent_context_session_cli.py src/sec_agent/tool_harness.py
python -m pytest tests/test_sec_agent_p0_observability.py tests/test_sec_agent_context_source_policy.py -q
python -m pytest tests/test_bm25_retriever.py tests/test_sec_benchmark_eval_mixed_context.py tests/test_sec_agent_8k_earnings_source.py -q
python scripts/cloud/sec_agent_context_session_cli.py --controller-backend heuristic --no-execute --prompt "比较MSFT和NVDA最近财报表现" --answer-preview-chars 0
```

Results:

- `py_compile`: passed.
- P0/session targeted tests: `16 passed`.
- Retrieval/mixed/8-K regression tests: `45 passed`.
- Combined rerun: `61 passed`.
- After ticker-scope forwarding and market-negation repair: targeted combined suite reached `71 passed`.
- Current closeout rerun on this working tree after market snapshot session argument forwarding and follow-up route fixes: `127 passed` across P0 observability, context source policy, BM25, mixed context, 8-K source, market snapshot fixture, 10-Q source contract, and resume closeout readiness tests.
- No-execute session CLI smoke: passed; banner showed `graph_execution: in_process` and no DAG execution.

## Expected Impact

For `session-mixed-8k-deepseek` and similar API-backed session runs:

- First turn still needs to load BM25/ObjectBM25/BGE once.
- Follow-up turns in the same session process should avoid reloading:
  - text BM25 index
  - object BM25 index
  - BGE reranker model
  - manifest index
- Retrieval still performs candidate generation and BGE scoring per query; this change removes lifecycle overhead, not semantic ranking work.

For local Qwen + BGE-first:

- Default remains subprocess-isolated to preserve GPU memory behavior.
- If needed, `SEC_AGENT_CONTEXT_RUNNER=in_process` can force the new path, but that should be treated as a memory-risk experiment.

## Cloud Validation

Cloud target: `/root/autodl-tmp/FIN_Insight_Agent`, `session-mixed-8k-deepseek`, DeepSeek API-backed synthesis, in-process graph execution.

Validated two real two-turn sessions:

- First session exposed two contract issues after cache landed:
  - turn 1/2 reused in-process runner and second turn reported `context_cache_hit=true`, but scope could expand beyond the intended MSFT/NVDA question.
  - a follow-up prompt with market-data negation could still inherit market snapshot intent from planner/repair.
- After root-cause fixes and resync, session `manual_session_20260526_164403` passed:
  - Turn 1 run root: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260526_164427_33283b7f8a`
  - Turn 2 run root: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260526_164641_12c1e1f556`
  - Both turns completed with `selected_tickers=["MSFT","NVDA"]`, `source_policy=SEC_PRIMARY_MIXED_WITH_8K_EARNINGS`, and no failed `SecAgentState` stages.
  - Both turns omitted `market_snapshot` from Query Contract when the prompt did not request it or explicitly excluded market/price data; `market_snapshot_context` stayed missing by design.
  - Turn 1 retrieval/rerank metadata: `context_runner=in_process`, `context_cache_hit=false`, `context_resource_load_ms=24968`, `retrieve_context/rerank_context elapsed_ms=38958`.
  - Turn 2 retrieval/rerank metadata: `context_runner=in_process`, `context_cache_hit=true`, `retrieve_context/rerank_context elapsed_ms=15969`.
  - Main deterministic gates passed on turn 2: answer ledger, metric role term, table cell, named fact, ledger missing consistency, abstract judgment, caveat claim, ledger unit, metric source grounding, answer-vs-Judgment-Plan, v2 semantic contract, and qwen-answer gate all passed. Trap/gold-vs-pipeline gates were skipped for this interactive smoke as expected.

Cloud test files inspected:

- `/root/autodl-tmp/FIN_Insight_Agent/reports/quality/manual_session_20260526_164403_context_session_turns.jsonl`
- `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260526_164427_33283b7f8a/sec_agent_state.json`
- `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260526_164641_12c1e1f556/sec_agent_state.json`
- `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260526_164641_12c1e1f556/post_gates/sec_benchmark_post_gates_summary.json`

Additional full-source market snapshot validation:

- Market evidence pack: `/root/autodl-tmp/FIN_Insight_Agent/data/processed_private/market/evidence_packs/20260525_market_yahoo_chart_full30_3m_fmp_valuation_v1_3m_market_evidence.jsonl`
- Snapshot: `snapshot_id=20260525_market_yahoo_chart_full30_3m_fmp_valuation_v1`, `as_of_date=2026-05-22`.
- The first attempted full-source session exposed controller follow-up route issues:
  - substantive follow-up could be misrouted to `explain_evidence`, `resume_analysis`, or `get_session_state`;
  - these were fixed in `src/sec_agent/tool_controller.py` with tool-name normalization and stricter follow-up intent guards.
- Final session `manual_session_20260526_181742` passed:
  - Turn 1 run root: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260526_181811_921e4ad89c`
  - Turn 2 run root: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260526_182016_e9ca76fb2b`
  - Both turns used `tool=start_memo_analysis`, `focus_tickers=["MSFT","NVDA"]`, and `source_tiers=["primary_sec_filing","company_authored_unaudited_sec_filing","market_snapshot"]`.
  - Both turns attached `2` market snapshot rows and had no missing artifacts.
  - Turn 1 metadata: `context_cache_hit=false`, `context_resource_load_ms=21448`, `retrieve_context elapsed_ms=35942`.
  - Turn 2 metadata: `context_cache_hit=true`, `retrieve_context elapsed_ms=10498`.
  - Both turns passed the 12 main deterministic gates and had no failed `SecAgentState` stages.

## Follow-Up

1. If BGE rerank itself remains the dominant cost after cache hit, tune `reranker_candidate_limit`, batch size, and prompt-context row caps with quality gates held fixed.
2. Promote the full-source two-turn market snapshot session prompt into a repeatable smoke/eval entry so controller route regressions are caught without manual cloud reruns.
3. Keep exact-value and named-fact gates strict; do not hide unsupported claims behind relaxed postchecks.

## Safety Notes

- No API keys, passwords, or cloud credentials were written to files.
- No generated `reports/quality/*` artifacts were promoted.
- This is a lifecycle/cache optimization, not a business fallback or evidence-policy change.
