# 417 R43 ProductIntelligence Autoload Lane Policy

## 问题

PIG v0.1 已接入 Product Specialist / Supply-chain Specialist / Research Lead，但 runtime 默认不应盲目按 ticker 自动加载本地全量 PIG DB。缺口在 Research Lead / LangGraph 层：什么时候应该打开 `product_intelligence_runtime_autoload`，以及这个决策如何被 checkpoint、routing trace 和后续审计看到。

## 决策

- 不让下游 data view 自行兜底打开 PIG；由 Research Lead lane policy 在 `research_lead_plan` 和 `validate_activation_plan` 阶段决定。
- 触发条件必须可审计：Product Specialist 激活、relationship/supply-chain lane 带 product context、允许 `company_product_evidence_graph` / `public_source_context` / `live_public_web_context`、query 中出现 GPU / accelerator / AI server / Blackwell / H100 / B200 / MI300 / TPU / spec / architecture / benchmark / customer deployment / 竞品 / 供应链等真实投研问法，且有 ticker scope。
- 保留显式 override：如果上游明确传入 `product_intelligence_runtime_autoload=false`，validate 阶段不得重新打开。
- Product Specialist bounded rows 必须优先保留本轮检索/注入的产品 rows，再追加 PIG 扩展行，避免本轮高优先级证据被本地 pack 挤出。

## 完成

- 更新 `src/sec_agent/multi_agent_router.py`：
  - 扩展 product technology intent 词表，覆盖 GPU、AI server、架构、benchmark、客户部署、竞品等问法。
- 更新 `src/sec_agent/langgraph_orchestrator.py`：
  - 新增 `sec_agent_product_intelligence_runtime_policy_v0.1`。
  - `research_lead_plan` / `validate_activation_plan` 写入 `product_intelligence_runtime_autoload`、`product_intelligence_runtime_policy`，并放入 `multi_agent_routing_trace.product_intelligence_runtime`。
  - checkpoint state summary 暴露 autoload 布尔和 policy status。
- 更新 `src/sec_agent/multi_agent_runtime.py`：
  - Product Specialist 的 bounded evidence 排序改为先本轮 state rows，后 PIG autoload rows。
- 更新 `tests/test_multi_agent_langgraph_routing.py`：
  - 增加 Research Lead 自动开启 PIG autoload 的 lane-policy 测试。
  - 增加显式关闭 override 不被 validate 重新打开的测试。

## 验收

- `python -m py_compile src/sec_agent/langgraph_orchestrator.py src/sec_agent/multi_agent_router.py src/sec_agent/product_intelligence_runtime.py src/sec_agent/product_spec_pack.py src/sec_agent/multi_agent_runtime.py src/sec_agent/specialist_llm.py src/sec_agent/supervising_analyst.py`
- `python -m pytest tests/test_multi_agent_langgraph_routing.py -q` -> `28 passed`
- `python -m pytest tests/test_product_intelligence_graph.py tests/test_product_spec_pack.py tests/test_supervising_analyst_pack.py tests/test_multi_agent_specialist_llm.py tests/test_data_quality_release_eval_gate.py tests/test_multi_agent_langgraph_routing.py -q` -> `92 passed`
- Non-LLM AI/Semis smoke：
  - `ai_semis_nvda_blackwell_competition`：autoload `enabled`，Product Specialist request `24` bounded rows，Research Lead product bridge official context `16`、customer deployment `3`、relationship context `6`。
  - `ai_semis_memory_supply_chain_hynix`：autoload `enabled`，Product Specialist request `16` bounded rows，Research Lead product bridge 有 product KPI、technical spec、supply-chain、competitive context；customer deployment signal 公开源下未补出，保持边界。

## 后续

- 下一步应把 full-chain AI/Semis case 的 Research Lead planning、Product Specialist output、MemoLogicPlan 和 memo surface 逐节点检查，确认 PIG 不只是“可见”，而是能实际提升产品、供应链、竞品和客户部署分析密度。
- 如果 memo 仍浅，应优先检查 MemoLogicPlan 是否消费 `product_bridge_pack`，再看 writer skill，而不是继续扩泛化 web source。
