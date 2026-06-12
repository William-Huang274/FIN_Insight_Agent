# Full Suite 10-Q Parser And Session CLI Repair

## Problem

G6 targeted 和相关链路测试通过后，执行全量 `python -m pytest -q` 暴露 3 个非 G6 失败：

- `test_10q_splitter_uses_readable_ge_style_headings_before_cross_reference`
- `test_10q_splitter_handles_intc_style_reader_friendly_layout`
- `test_context_session_graph_args_forward_market_snapshot_contract`

前两个失败来自 10-Q section splitter 对 GE/INTC 风格 readable headings 的旧合并逻辑：正式 Item parser 只在 cross-reference/index 表里抓到 `1A`，fallback 找到了真实 `1/2/3/4` 语义标题，但合并时只补 `1/2`，导致真实 `3/4` 被丢掉，并保留了 index-like 的 `1A`。第三个失败来自 `scripts/cloud/sec_agent_context_session_cli.py` 的 `_graph_args(...)` 直接访问 `args.market_catalog_path`，测试中的旧 Namespace 未提供该字段。

## Decision

- 当 nontraditional 10-Q fallback 已覆盖 `Item 1` 和 `Item 2` 时，以 fallback 为主；只从正式 parser 结果中合并非 index-like 的缺失 item。
- 新增 `_section_looks_like_10q_index(...)`，过滤 cross-reference / item-number index 表里的伪 section。
- `_graph_args(...)` 对 optional args 使用 `getattr(..., None)`，保持旧 Namespace 和新增 market catalog 参数兼容。

## Work Completed

- `src/ingestion/section_splitter.py`
  - 调整 `find_10q_sections(...)` 的 fallback merge 策略。
  - 新增 `_section_looks_like_10q_index(...)`。
- `scripts/cloud/sec_agent_context_session_cli.py`
  - 修复 `_graph_args(...)` 对 optional source/market/API args 的属性访问。

## Result And Evidence

- 原失败测试：
  - `python -m pytest tests/test_sec_agent_10q_source_contract.py::test_10q_splitter_uses_readable_ge_style_headings_before_cross_reference tests/test_sec_agent_10q_source_contract.py::test_10q_splitter_handles_intc_style_reader_friendly_layout tests/test_sec_agent_context_source_policy.py::test_context_session_graph_args_forward_market_snapshot_contract -q`
  - `3 passed`
- 全量测试：
  - `python -m pytest -q`
  - `810 passed`

## Boundaries

- 这次没有改变 10-K/20-F/40-F splitter。
- 这次没有改变 G6 产品 KPI authority gate；只是修复全量测试暴露的 parser/CLI contract 问题。
