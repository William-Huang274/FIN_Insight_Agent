# 175 SEC Agent P0 Latency And Observability Local/Cloud Pass

## Prompt

用户要求先做生产级缺口中的 P0，本地先改脚本和 smoke，等云端可用后再跑 full-source DeepSeek。

## Decision

本轮只处理不依赖云端和 DeepSeek 输出速度的 P0 项：

- 非 LLM 链路性能剖析。
- 每轮运行的数据/索引版本指纹。
- stage-level timing 观测。
- 同一进程内 runtime ledger structured-object records 缓存。
- 本地 latency profile smoke。

不改变业务兜底，不降低 evidence/gate 合同，不把 BM25-only 当成主线质量结论。

## Work Completed

- `src/retrieval/bm25_retriever.py`
  - 文本 BM25 增加 filter cache。
  - 有 filter 时改用 `get_batch_scores()`，避免每次全索引打分。
- `src/retrieval/object_bm25_retriever.py`
  - 为 `ticker` / `fiscal_year` / `form_type` / `source_tier` / `object_type` 等常用 filter 建内存倒排索引。
  - filtered search 不再为每个新 filter 逐次扫描 32 万 structured-object records。
- `scripts/run_sec_benchmark_eval.py`
  - 在 trace 的 `context_policy.timing_ms` 写入 candidate generation 和 BGE rerank 耗时。
  - 记录 `candidate_row_count_pre_rerank`。
- `scripts/cloud/sec_agent_interactive.py`
  - 暴露 BGE reranker knobs：
    - `--reranker-candidate-limit`
    - `--reranker-batch-size`
    - `--reranker-max-length`
    - `--reranker-doc-max-chars`
  - 每次 run 写入 `run_data_fingerprint.json`，记录 manifest/index/market evidence 的存在、大小、row count、metadata 和 runtime knobs。
  - 每次 run 写入 `run_performance.json`，记录 stage timing、artifact row count 和总耗时。
  - `SecAgentState.stages` 现在会填充 `started_at`、`finished_at`、`elapsed_ms`。
  - runtime ledger 的 object records 加 `lru_cache(maxsize=4)`，同一 session 进程内 follow-up/重复构建不再重复解析 32 万行 object records。
  - runtime ledger supplement 改为按 planner `decomposed_tasks.required_metric_families + required_tickers` 收缩扫描范围，避免 full30 broad scope 下对不相关 ticker/family 做完整表格解析。
  - ledger supplement 增加 record scope/prefilter cache，同进程重复构建可复用 scope 和 family prefilter 结果。
  - 表格 Change 列新增派生 `percentage_rate` ledger row：仅当 Change 数值与 `(current-prior)/prior` 匹配时生成，修复 JPM `Total net revenue +11%` 这类 SEC 表格增长率没有 metric_id 支撑的问题。
  - `plan_query` / `validate_query_contract` early stages 写入 timing；`run_performance.json` 汇总会从所有 `StageRecord.elapsed_ms` 收集 stage timing。
- `scripts/evaluate_sec_agent_latency_profile.py`
  - 新增本地非 LLM latency profile smoke。
  - 覆盖 BM25/ObjectBM25 初始化、候选生成、market context attach、runtime ledger 首次/缓存后构建、Coverage Matrix。
- `tests/test_bm25_retriever.py`
  - 覆盖 filtered BM25 走 batch scoring/cache，unfiltered 仍走 full-score 路径。
- `tests/test_sec_agent_p0_observability.py`
  - 覆盖 run fingerprint、stage timing、performance report stage aggregation、ledger supplement task scope、Change 列增长率派生。

## Local Validation

Commands:

```powershell
python -m py_compile scripts/cloud/sec_agent_interactive.py scripts/run_sec_benchmark_eval.py scripts/evaluate_sec_agent_latency_profile.py src/retrieval/bm25_retriever.py
python scripts/evaluate_sec_agent_latency_profile.py
python scripts/market/60_smoke_market_snapshot_main_chain.py --prompt "结合SEC财报和最近三个月market snapshot，比较NVDA、AMD、MSFT、AMZN、GOOGL的AI相关基本面、最新10-Q市场反应和估值是否一致，并标明证据边界。" --tickers NVDA,AMD,MSFT,AMZN,GOOGL --years 2023,2024,2025,2026 --manifest-path data/processed_private/manifests/sec_tech_primary_mixed_10k_latest_10q_manifest_fy2023_2027.jsonl --bm25-index-dir data/indexes/bm25/sec_tech_primary_mixed_10k_latest_10q_fy2023_2027 --object-bm25-index-dir data/indexes/bm25/sec_tech_primary_mixed_10k_latest_10q_fy2023_2027_objects --market-evidence-path data/processed_private/market/evidence_packs/20260525_market_yahoo_chart_full30_3m_fmp_valuation_v1_3m_market_evidence.jsonl --market-snapshot-id 20260525_market_yahoo_chart_full30_3m_fmp_valuation_v1 --market-as-of-date 2026-05-22 --output-root reports/quality/p0_local_market_main_chain_smoke --evidence-top-k 4 --object-top-k 4 --max-context-rows 150 --ledger-max-rows 90
python -m pytest tests/test_sec_agent_p0_observability.py tests/test_bm25_retriever.py tests/test_resume_closeout_readiness.py tests/test_market_snapshot_fixture.py tests/test_sec_agent_10q_source_contract.py -q
```

Results:

- `py_compile`: passed.
- Latency profile:
  - Report: `reports/quality/latency_profile/sec_agent_latency_profile_local_latest.json`
  - Status: `pass`
  - BM25 records: `10,323`
  - Object records: `325,189`
  - BM25 init: `0.9744s`
  - ObjectBM25 init: `13.8769s`
  - Candidate generation: `22.6399s`
  - Text BM25: `260` calls, `0.6278s`, `20` unique filters.
  - ObjectBM25: `460` calls, `21.9438s`, `20` unique filters.
  - Context rows: `1,412`
  - Runtime ledger first build: `18.5467s`
  - Runtime ledger second cached build: `3.2925s`
  - Ledger cache speedup: `15.2542s`
- Main-chain local smoke:
  - Run root: `reports/quality/p0_local_market_main_chain_smoke/20260526_124601_f7b01aec3a`
  - Status: `pass`
  - Elapsed: `49.3284s`
  - Context rows: `1,417`
  - Market rows: `5`
  - Ledger rows: `25`
  - `coverage_complete=true`
  - `primary_task_support_complete=true`
  - `market_snapshot_support_complete=true`
- Latest targeted P0 tests after cloud fixes:
  - `python -m py_compile scripts/cloud/sec_agent_interactive.py scripts/evaluate_sec_agent_latency_profile.py src/retrieval/bm25_retriever.py src/retrieval/object_bm25_retriever.py`
  - `python -m pytest tests/test_sec_agent_p0_observability.py tests/test_bm25_retriever.py -q`
  - Result: `9 passed`.

Latest local latency profile after ObjectBM25 filter index + task-scoped ledger:

- Report: `reports/quality/latency_profile/sec_agent_latency_profile_local_after_task_scoped_ledger.json`
- Status: `pass`
- Object records: `325,189`
- Candidate generation: `8.6170s`
- ObjectBM25: `460` calls / `8.3529s`
- Runtime ledger first build: `11.3969s`
- Runtime ledger second cached build: `0.7621s`

## Cloud Validation

Cloud node:

- Repo path: `/root/autodl-tmp/FIN_Insight_Agent`
- Python: `/root/autodl-tmp/envs/sec-agent-cu128/bin/python`
- GPU observed earlier in this P0 pass: NVIDIA GeForce RTX 5090 32GB class.

Targeted remote tests:

```bash
/root/autodl-tmp/envs/sec-agent-cu128/bin/python -m py_compile scripts/cloud/sec_agent_interactive.py
/root/autodl-tmp/envs/sec-agent-cu128/bin/python -m pytest tests/test_sec_agent_p0_observability.py tests/test_bm25_retriever.py -q
```

Result:

- `9 passed`
- No API key, password, or credential written to repo files.

Full-source non-LLM latency profile:

- Report: `/root/autodl-tmp/FIN_Insight_Agent/reports/quality/latency_profile/sec_agent_latency_profile_cloud_full_source_after_ledger_change_rate.json`
- Status: `pass`
- BM25 records: `10,687`
- Object records: `325,003`
- Candidate generation: `10.0073s`
- Text BM25: `900` calls / `0.6939s`
- ObjectBM25: `586` calls / `9.2441s`
- Context rows: `2,557`
- Runtime ledger first build: `11.7865s`
- Runtime ledger second cached build: `2.7976s`

Before this fix, the same profile class was:

- Candidate generation: about `24.9066s`
- ObjectBM25: about `23.7729s`
- Runtime ledger second cached build: about `12.4945s`
- Status: `warn`, reason `cached_ledger_over_budget`

Full-source real DeepSeek smoke after Change-rate ledger fix:

- Run root: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260526_142958_b06d3008e3`
- Source mix: `10-K + latest 10-Q + 8-K earnings release + market_snapshot`
- Prompt scope: `MSFT, NVDA, JPM, XOM`
- Gates: `ok=True`, `pass=12`, `fail=[]`
- Coverage: `complete=True`, `primary_complete=True`
- Ledger rows: `42`
- Context rows: `3,968`
- Elapsed: `130.79s`
- Root-cause fixed from prior failed smoke: JPM `Total net revenue +11%` now enters ledger as a derived `percentage_rate` row instead of leaving the answer ledger gate to match unrelated capital-ratio percentages.

Small-scope full-source DeepSeek smoke for stage timing:

- Run root: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260526_144656_49ea8f3167`
- Prompt scope: `MSFT, NVDA`
- Gates: `ok=True`, `pass=12`, `fail=[]`
- Coverage: `complete=True`, `primary_complete=True`
- Ledger rows: `70`
- Context rows: `305`
- Elapsed: `118.69s`
- `sec_agent_state.json` confirmed `plan_query` and `validate_query_contract` carry `started_at`, `finished_at`, and `elapsed_ms`.
- After this run, `run_performance.json` aggregation was patched so future runs include those early stages in `stage_timing_ms`; the aggregation behavior is covered by unit test.

## Current P0 Diagnosis

已修或已具备：

- BM25 文本检索不再是主要瓶颈。
- Local smoke 能直接暴露非 LLM latency。
- 每次正式 interactive run 会写数据指纹和 performance report。
- Ledger records 在同一进程内重复构建有明显缓存收益。
- ObjectBM25 filtered retrieval 已从逐次全量扫描切到 indexed filter path。
- Runtime ledger cached rebuild 已从云端约 `12.5s` 降到 `2.8s` 量级。
- Real full-source DeepSeek smoke 已验证 10-K/10-Q/8-K/market_snapshot 路径可全绿通过 deterministic gates。

仍是 P0 剩余项：

- ObjectBM25 仍是候选生成主瓶颈，但已降到云端 full-source `586` calls / `9.2441s`。
- Object index 初始化仍重：云端约 `11.1s`，本地约 `11-12s`。
- `scripts/run_sec_benchmark_eval.py` 仍作为子进程启动；interactive session 不能复用 BM25/ObjectBM25/BGE 实例。
- 本地 market smoke 仍是 BM25-only pre-synthesis diagnostic，不代表云端 BGE full-source latency。
- 生产并发还没有从 JSON store 切到事务化存储。
- Full-source real run 的 `retrieve_context/rerank_context` 仍约 `32s-43s`，主要来自 subprocess + BGE/model/index lifecycle；下一步应做 resident retrieval worker 或 in-process retrieval path。

## Next Step

1. 做 resident retrieval worker 或 in-process retrieval path，复用 BM25/ObjectBM25/BGE 实例，目标是把每 turn retrieval+rereank 的固定加载成本拿掉。
2. 把 `run_performance.stage_timing_ms` 的 early-stage 汇总补丁在下一次真实 full-source run 中复验。
3. 继续保留 answer ledger gate 的严格性；遇到 unsupported exact value 时优先补 ledger/extractor，而不是放宽 gate。
4. 后续质量层面需要单独处理 synthesis 的跨期间/跨单位比较措辞，例如 capex 的十亿美元/百万美元混排导致的读者误解，这不属于本轮 P0 latency blocker。

## Safety Notes

- 未写入任何 API key、密码或云端凭据。
- 生成的 `reports/quality/*` 为 runtime artifact，默认不纳入 Git。
- 本轮没有修改 source policy、Evidence Coverage Matrix 判定口径或 synthesis 业务兜底。
