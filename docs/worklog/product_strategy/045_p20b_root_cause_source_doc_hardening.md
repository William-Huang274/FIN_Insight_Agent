# P20b Root-Cause / Source-Doc Hardening

## 背景

用户要求先回头扫已实现需求和功能，把之前内容做扎实再继续往下跑。触发点是 P20 DeepSeek dogfood 后，金额单位错误和 investment-quality 坏输出不应只靠新增 gate / fallback 拦住；如果问题能在项目内部上游定位，必须记录并修根因。

## 本轮判断

P20 可以保留为真实模型 dogfood + gate repair closeout，但不能再被表述为“金额单位和 investment-quality 根因已全部闭环”。本轮把 P20b 明确为继续硬化项：

- `P20b-D01-ambiguous-currency-scale-root`
- `P20b-D02-numeric-display-lineage`
- `P20b-D03-memo-logic-plan-quality-root`
- `P20b-D04-source-doc-status-correction`

## 已完成

1. 源文档状态修正：
   - 更新 `docs/architecture/agent_graph_vnext/36_r53_r60_unified_demand_backlog_execution_plan.zh-CN.md`，新增 P20 / P20b 边界和根因修复通过条件。
   - 更新 `docs/worklog/00_internal_master_checklist.md`，把 P20 从“全根因已修复”改为“dogfood/gate repair 已完成”，新增 P20b open item。
   - 更新 `docs/worklog/product_strategy/044_p20_deepseek_real_llm_dogfood_gate_repair.md`，追加用户复核后的状态修正。
   - 更新 `docs/worklog/README.md`，避免 README 把 P20 gate containment 误写为完整 root-cause fix。

2. 金额单位根因前移：
   - 更新 `src/sec_agent/reconciliation_ledger.py`。
   - 大额裸 `usd` / `$` / `dollar(s)` 的 currency fact 不再进入 reconciliation approved group，而是在 candidate 阶段标记为 `excluded_ambiguous_currency_scale`。
   - 这使 `77658.0 usd` 这类 source-scale 金额在 reconciliation 层被排除，memo selector 的拦截只保留为回归保险。

3. 回归测试：
   - 更新 `tests/test_metric_product_ontology_reconciliation.py`，新增 reconciliation 层大额裸 USD 排除测试。
   - 运行 `python -m pytest tests\test_metric_product_ontology_reconciliation.py tests\test_d_series_fact_selection.py -q` -> `20 passed`。
   - 运行 P20 扩展回归组合 `python -m pytest tests\test_multi_agent_contracts.py tests\test_multi_agent_real_llm_chain_eval.py tests\test_d_series_fact_selection.py tests\test_multi_agent_memo_llm_repair.py tests\test_multi_agent_activation_plan.py tests\test_metric_product_ontology_reconciliation.py -q` -> `159 passed`。
   - 运行 `python -m compileall -q src\sec_agent scripts\eval_multi_agent tests` -> pass。

## 仍未闭环

- `P20b-D02-numeric-display-lineage`：还需要补 renderer / writer 层的 numeric display lineage 回归，证明缺 scale lineage 的金额不会出现在最终 rendered memo。
- `P20b-D03-memo-logic-plan-quality-root`：还需要继续把 investment-quality 从“事后 gate”前移到 Research Lead / Supervising Analyst / MemoLogicPlan 的输入质量，确保 writer 拿到的是 answer-first、dimension-linked、citation-backed plan。

## 后续原则

后续如果 gate 发现内部错误，必须按以下顺序处理：复现症状、定位最早 faulty artifact、修 parser / normalizer / reconciliation / planner / writer 输入、保留 gate 做回归保护、补 deterministic test、更新源文档和 checklist。不得用新增 gate / fallback 替代根因修复。
