# 260 Expanded A6 Scope / Gap Eval Contract

日期：2026-06-07

## 问题

A6 不能只检查最终 memo 是否有引用和是否通过 Verifier。603-company 扩容后，真正需要验证的是：Research Lead 是否能做专业 scope decision，Universe 是否能按 catalog/lens 构造 bounded universe，Specialist 是否能在证据不足时输出结构化 gap request，下游是否保留这些缺口，以及整条链路的 token / latency 是否在可接受范围内。

## 决策

- 将 A6 主 fixture 从 `17` 个 case 扩展到 `20` 个 case，新增三类 NVIDIA scope / gap 用例：
  - 单公司基本面：不应无故扩到全行业，但要说明 conditional expansion 的触发条件。
  - AI infrastructure supply-chain readthrough：需要 cloud capex、memory/foundry/equipment、server/networking/power、export-control risk、market reaction 的 scope decision 和 Universe contract。
  - 非美供应链 source gap：如果 Samsung / SK hynix / TSMC / Hon Hai/Foxconn 等当前只支持 hypothesis 或 source gap，必须结构化上报 gap，不允许模型用常识补全。
- 在 `score_case` 新增 `scope_gap_contract` layer，显式检查：
  - `scope_decision.scoping_pattern` / `expansion_mode` / `catalogs_to_inspect` / `candidate_lenses` / `expansion_budget` / `stop_condition`。
  - Universe included / excluded ticker contract。
  - `evidence_gap_requests` 是否出现并被 Judgment / Memo / Renderer 保留。
  - hypothesis-only / source-gap / coverage-boundary 是否在最终渲染中可见。
- 新增 `performance` layer，按 case 上限检查 elapsed time 和 per-agent token budget。
- Workbench A6 smoke 默认加入 `fin_full_scope_nvda_basic_fundamental_zh`，使 smoke 覆盖 exact lookup、scope decision、standard memo、sector-depth。

## 完成

- 更新 `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`：
  - 新增 `scope_gap_contract` layer。
  - 新增 `performance` layer。
  - aggregate metrics 增加 `total_llm_tokens`、`avg_llm_tokens_per_case`、`max_case_elapsed_ms`、`scope_gap_contract_failed_cases`、`performance_failed_cases`。
- 更新 Research Lead LLM schema hint / user prompt，要求真实模型把 `scope_decision` 写入 `activation_plan.metadata`。
- 更新 Universe LLM schema hint，加入 `included_ticker_contracts` / `excluded_ticker_contracts`。
- 更新 `normalize_universe_relationship_plan`，保留并机械补全 per-ticker scope contracts。
- 更新 `tests/fixtures/fin_agent_full_chain_multiturn_cases_v0_1.jsonl` 到 `20` case。
- 更新 `docs/eval/fin_agent_full_chain_multiturn_eval_plan_v0_1.md` 的 case matrix、hard gates、smoke 建议、stop/proceed 条件。

## 验证

- `python -m py_compile src/sec_agent/multi_agent_contracts.py src/sec_agent/research_lead_llm.py src/sec_agent/universe_relationship_llm.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py scripts/workbench/run_expanded_a6_eval.py`
- `python -m pytest tests/test_multi_agent_real_llm_chain_eval.py tests/test_workbench_expanded_a6_eval.py tests/test_multi_agent_research_lead_llm.py tests/test_multi_agent_universe_relationship_llm.py tests/test_multi_agent_contracts.py -q`
  - 结果：`67 passed`
- `python -m pytest tests/test_research_skills.py tests/test_multi_agent_contracts.py tests/test_multi_agent_universe_relationship.py tests/test_multi_agent_universe_relationship_llm.py tests/test_multi_agent_research_lead_llm.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_workbench_expanded_a6_eval.py tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_judgment_memo_verifier.py tests/test_multi_agent_agent_registry.py -q`
  - 结果：`145 passed`
- `git diff --check`

## 未运行

- 本轮没有跑真实 DeepSeek A6 smoke/main，没有消耗 provider token。
- 本轮没有生成 `reports/quality/workbench_eval/` 真实运行报告。
- 新的非美供应链 gap case 是有意设置的高信息量 hard gate；如果真实 A6 首跑失败，应优先看是 source catalog/relationship coverage 不足、gap request 未生成、还是下游未保留 gap。

## 后续

- 云端先跑 Workbench `expanded_a6_full_chain_smoke`，检查 4 个 smoke case 的 scope/gap/performance metrics。
- smoke 通过后跑 `expanded_a6_full_chain_main` 全 20 case。
- 如果 `scope_gap_contract_failed_cases` 非空，按失败层定位 Lead / Universe / Specialist / Memo / Renderer，不直接调最终文案。
