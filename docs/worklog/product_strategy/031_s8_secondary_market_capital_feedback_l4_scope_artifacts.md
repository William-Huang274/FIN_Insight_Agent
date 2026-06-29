# 031 S8 Secondary Market / Capital Feedback Pack L4 Scope Artifacts

日期：2026-06-29

## 目标

把 R54 的二级市场资金面、持仓、信用融资、资本动作、估值 price-in 和衍生品风险定价规划，落成 S1 SQL 主账本可消费的 `SecondaryMarket / Capital Feedback Pack`。本 slice 的重点不是新增实时行情，而是把已有公开/披露数据和真实缺口分清：

- market snapshot 只能做 delayed market / liquidity context；
- 13F / holder 只能做 lagged positioning context；
- debt / credit facility / working-capital rows 保留 filing / financial-statement exact authority；
- SEC offering / insider / 13D/G / proxy metadata 只能证明 filing-event existence；
- derivatives、credit spread、short / borrow、valuation denominator 等未物化字段必须进入 typed gap，不能用弱 proxy 假装补齐。

## 本轮完成

- 新增 `src/sec_agent/r53_r60_secondary_market_capital_feedback.py`：
  - `SecondaryMarketSourceRegistry`；
  - `CapitalFeedbackPack`；
  - `CapitalFeedbackSignal`；
  - `CapitalFeedbackGapItem`；
  - `CapitalFeedbackGraphEdge`；
  - `CapitalFeedbackQualityGate`；
  - S8 summary / closeout report / gate rows。
- 新增 `scripts/engineering/build_r53_r60_s8_secondary_market_capital_feedback.py`，可从仓库根目录重建 S8 pack。
- 新增 `tests/test_r53_r60_secondary_market_capital_feedback.py`，用临时 fixture 验证 source registry、issuer pack、bounded signals、typed gaps、graph edges、WorkpaperEvent 和 repeat build。
- 更新 `docs/architecture/agent_graph_vnext/36_r53_r60_unified_demand_backlog_execution_plan.zh-CN.md`，写入 S8 closeout。
- 更新 `docs/architecture/agent_graph_vnext/29_r54_secondary_market_capital_feedback_technical_plan.zh-CN.md`，把 R54 living registry 状态从规划推进到 S8 runtime closeout，并保留 R54.2-R54.7 backlog。

## 生成物

- `configs/r53_r60/s8_secondary_market_capital_feedback_schema_v0_1.json`
- `data/manifests/r53_r60_s8_secondary_market_capital_feedback_gate_rows_v0_1.jsonl`
- `data/manifests/r53_r60_s8_secondary_market_capital_feedback_summary_v0_1.json`
- `docs/internal/vnext_20260610/r53_r60_s8_secondary_market_capital_feedback_l4_scope_pass.zh-CN.md`
- 私有 runtime DB：`data/workbench_private/research_data/r53_r60_runtime_task_spine_v0_1.sqlite`（不提交 Git）

## 真实构建结果

输入：

- `data/manifests/market_liquidity_driver_context_rows_v0_1.jsonl`：`603` rows；
- `data/manifests/capital_funding_ownership_context_rows_v0_1.jsonl`：`13,185` rows；
- `data/manifests/sec_capital_market_event_context_rows_v0_1.jsonl`：`17,485` rows。

输出：

- issuer pack：`603`；
- bounded signal：`13,107`；
- typed gap：`2,443`；
- graph edge：`4,221`；
- source registry：`15`；
- quality gate：`10 pass / 0 fail`；
- release decision：`S8_L4_scope_pass`；
- next slice unlocked：`S9`。

按角色的 signal：

- `secondary_market_capital_flow`：`603`；
- `liquidity_and_positioning`：`3,413`；
- `ownership_and_holder`：`3,512`；
- `credit_funding`：`2,070`；
- `corporate_action`：`3,509`。

按角色的 typed gap：

- `valuation_price_in`：`603`；
- `derivatives_market_signal`：`603`；
- `credit_funding`：`603`，主要是 company bond spread / CDS / rating-history market data；
- `liquidity_and_positioning`：`603`，主要是 short-interest / borrow-cost / securities-lending；
- `ownership_and_holder`：`16`；
- `corporate_action`：`15`。

## Root-Cause Fix

第一次真实构建时，S8 pack 生成了 `822` 个 issuer，其中只有 `603` 个有 market snapshot。根因是 SEC event rows 的 `all_tickers` 会包含不在当前 runtime universe 中的关联 ticker / 其他证券代码，导致 secondary-market pack 范围被 SEC metadata 污染。

修复方式：

- S8 issuer universe 明确锁定为 market snapshot 中的 `603` 个 runtime issuer；
- capital / SEC event rows 只有 ticker 落在 runtime universe 内才进入 pack；
- universe 外 SEC event ticker 不进入 pack，只记录为诊断计数：`sec_event_tickers_outside_runtime_universe=6655`。

这个修复不是 fallback，而是范围合同修复：S8 的目标是给当前 603-company runtime universe 生成二级市场/资本反馈 pack，不是把 SEC metadata 中所有关联 ticker 都扩成 issuer pack。

## 验证

- `python -m py_compile src\sec_agent\r53_r60_secondary_market_capital_feedback.py scripts\engineering\build_r53_r60_s8_secondary_market_capital_feedback.py`
- `python -m pytest tests/test_r53_r60_secondary_market_capital_feedback.py -q`
- `python scripts\engineering\build_r53_r60_s8_secondary_market_capital_feedback.py --root .`

## 边界

S8 只证明 Secondary Market / Capital Feedback Pack 在自身范围达到 `L4_scope_pass`：

- source registry 有 authority、lag、lifecycle、commercial boundary 和 forbidden claims；
- 603 issuer pack 全部 SQL-final；
- signals 和 graph edges 都有 evidence 或 typed gap；
- holder / market / metadata rows 不越权；
- 缺失的 derivatives、credit market、short / borrow、valuation rows 被显式记录为 typed gap。

本轮不证明：

- 实时资金流；
- OPRA options feed；
- dealer gamma；
- live borrow cost；
- CDS / 完整债券价格；
- consensus NTM valuation；
- 正式投资建议。

## 后续

- S9：Research-to-Quant Lab，把 Workpaper / thesis driver 转为 FactorHypothesis，并加 human approval / PIT dataset / backtest smoke。
- R54 后续：补 valuation denominator、SEC source-specific capital-action parser、short interest / ETF / N-PORT、derivatives delayed proxy、cross-asset mapping，并接入 R60 forbidden-claim eval。
