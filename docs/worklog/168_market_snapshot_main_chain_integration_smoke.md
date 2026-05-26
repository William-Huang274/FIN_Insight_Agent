# 168 Market Snapshot Main Chain Integration Smoke

Date: 2026-05-25

## Problem

`market_snapshot` 已完成 DuckDB/parquet 底座、event-window analytics、Query Contract validator 和 planner contract，但还没有进入交互主链路。真实投研问题需要在 SEC/8-K retrieval 之后，把带 `snapshot_id/as_of_date` 的市场快照证据作为独立 source tier 注入 Evidence Coverage Matrix、Judgment Plan、synthesis、claim gates 和 renderer，且不能和 SEC ledger 的财务事实混权。

## Decision

- `market_snapshot` 不是 SEC filing，也不是 fallback；只有 Query Contract 请求 market source tier 时才从本地 evidence JSONL 加载。
- 注入位置固定在 `retrieve_context` 之后、`build_runtime_ledger` 之前，这样后续 Coverage Matrix、Judgment Plan、Evidence Pack、synthesis 和 renderer 都能看到同一批 context rows。
- 市场证据只支持 market / valuation / return / drawdown 类 claim。SEC Exact-Value Ledger 仍然是 filed fundamentals 的唯一精确财务事实来源。
- Graph state 允许记录可选 artifact `market_snapshot_context`，但该 artifact 不作为 SEC-only run 的必需 resume output。

## Work Completed

- `scripts/cloud/sec_agent_interactive.py`
  - 增加 `--market-evidence-path` / `MARKET_EVIDENCE_PATH`。
  - 增加 `attach_market_snapshot_context` 阶段，把匹配 ticker / snapshot / as_of / fields 的 market evidence rows 注入 `trace["context_rows"]`。
  - 写出 `market_snapshot_context_rows.jsonl`，并把 `market_snapshot_context` 写入 graph state artifact refs。
  - Judgment Plan 在 market coverage 完整时追加 `market_snapshot_context` driver，避免 claim verifier 把市场证据当成未映射证据。
  - Renderer 对 `MARKET_SNAPSHOT::...` evidence id 显示 ticker、window、as_of、snapshot_id 和 non-real-time 边界。

- `src/sec_agent/coverage_matrix.py`
  - 增加 market snapshot coverage 汇总。
  - task row 记录 required / covered / missing market fields、market tools、snapshot ids、as_of dates 和 sample field refs。
  - market rows 不再受 SEC filing type 过滤影响，但只在 task 或 contract 明确需要 market evidence 时提高 support level。

- `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
  - Prompt 暴露 compact market fields、snapshot_id、as_of_date。
  - Evidence selection 在 coverage 需要 market 时优先保留 market rows。
  - Normalizer / exact-value gates 允许“已引用 market evidence id”的 market 数值和百分比，不允许它覆盖 SEC filed fundamentals。

- `src/sec_agent/query_contract.py`
  - market source policy 下移除 stale `SEC-only evidence boundary` 和旧的 `Do not use market prices...` 禁令。
  - `query_contract_validation.selected_scope.source_tiers` 反映最终 source tiers，包括 `market_snapshot`。

- `src/sec_agent/graph_state.py` / `src/sec_agent/graph_nodes.py`
  - 增加可选 artifact key `market_snapshot_context`。
  - Resume report 不把该可选 artifact 记为 SEC-only run 的缺失项。

- `tests/test_market_snapshot_fixture.py`
  - 增加 Coverage Matrix、interactive market context loader、renderer boundary、stage attach artifact、planner stale SEC-only cleanup、synthesis normalizer market numeric support 测试。

## Verification

Commands run:

```powershell
python -m py_compile src/sec_agent/graph_state.py src/sec_agent/graph_nodes.py src/sec_agent/query_contract.py src/sec_agent/coverage_matrix.py scripts/cloud/sec_agent_interactive.py scripts/run_sec_eval_synthesis_qwen9b_backend.py
python -m pytest tests/test_market_snapshot_fixture.py -q
python -m pytest tests -q
python scripts/cloud/sec_agent_interactive.py --plan-only --query-planner heuristic --tickers NVDA,MSFT --years 2025,2026 --market-evidence-path reports/market_snapshots/pilot.jsonl --prompt "Compare NVDA and MSFT fundamentals with recent 3M market reaction and valuation context"
```

Results:

- Market snapshot targeted suite: `8 passed`.
- Full local suite: `97 passed`.
- Planner CLI smoke: validation `pass`; `source_policy=SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT`; final `source_tiers=["primary_sec_filing","market_snapshot"]`; no stale `SEC-only evidence boundary`; validation report selected scope includes `market_snapshot`.

## Smoke Boundary

- 本地没有真实 `reports/market_snapshots/pilot.jsonl`，所以这轮没有声称完成 7-company fixture 或 DeepSeek API full-chain run。
- 主链路连接点通过阶段级测试覆盖：`attach_market_snapshot_context` 会读取 synthetic evidence JSONL、注入 context rows、写 `market_snapshot_context_rows.jsonl`，并登记 `market_snapshot_context` graph artifact。
- CLI smoke 覆盖 planner / validator / source policy / source gap 表达；因为 evidence 文件不存在，market source gaps 仍正确提示缺少 `snapshot_id/as_of_date`，不让模型猜。

## Remaining Work

- 准备 7-company 本地 market snapshot fixture，并用真实 evidence JSONL 跑一次端到端 interactive full chain。
- 在 7-company smoke 通过后，接入 real DeepSeek/API synthesis smoke，观察市场证据是否能稳定进入 memo 的市场反应、估值语境、分歧判断和证据边界。
- 实现 `fundamental_market_divergence` analytics：需要 SEC/8-K driver 输出稳定后，把 fundamental driver 与 market reaction view 做确定性对齐。
