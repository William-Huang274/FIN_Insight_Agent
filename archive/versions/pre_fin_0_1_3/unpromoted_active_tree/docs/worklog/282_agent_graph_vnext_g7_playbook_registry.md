# Agent Graph vNext G7 Playbook Registry

## Problem

G1-G6 已接入 product/public/live-web/Milvus source families 和产品专家，但 Research Lead 仍主要依靠 query 文本和少量 inventory hint 判断行业路径。这样对同一句“比较业务驱动”的问题，在银行、消费电子、医药、能源等行业下无法稳定分配不同 source family、specialist 和 gap policy，也无法把行业 forbidden claims 传给 reflection / verifier。

## Decision

- 新增机器可读 YAML playbook registry，Research Lead 不学习行业百科，只读取 playbook 的 routing contract。
- 首批 playbook 覆盖：
  - `semiconductors`
  - `consumer_electronics`
  - `software_saas`
  - `banks`
  - `energy_oil_gas`
  - `pharma_biotech`
  - `autos_ev`
  - `retail_cpg`
  - plus `generic_public_research`
- Inventory 负责把 manifest category 映射为 playbook candidates，并把 source policy / forbidden claims / commercial gap policy 压缩进 brief。
- Deterministic router 和 LLM Research Lead validation postprocess 共享同一套 playbook policy 应用逻辑。
- Plan Reflection 输出 `playbook_policy`，并把 playbook forbidden claims 作为 downstream verifier / specialist boundary。

## Work Completed

- Registry / loader:
  - `configs/industry_playbooks_v0_1.yaml`
    - 定义 playbook schema、common source-family policy、default source families、commercial gap policy、common failure modes、forbidden claims、specialist routing 和 web scope policy ids。
  - `src/sec_agent/industry_playbooks.py`
    - 新增 registry loader、normalizer、validator、candidate matcher、compact registry、selected playbook policy projection。
- Inventory:
  - `src/sec_agent/project_inventory.py`
    - 从 YAML registry 生成 `playbook_candidates`，替代旧 tuple alias 规则。
    - `inventory_brief(...)` 增加 `playbook_registry`，candidate 中保留 `default_source_families`、`source_family_policy`、`forbidden_claims`、`commercial_gap_policy`、`specialist_routing`、`web_scope_policy_ids`。
    - `inventory_prompt(...)` 的 playbook lines 现在展示 default sources、specialists、forbidden boundaries。
- Research Lead / Router:
  - `src/sec_agent/multi_agent_router.py`
    - 新增 playbook policy postprocess；在 `standard_memo` / `deep_research` 中按可用 source family 增加 source/agent，并写入 `metadata.selected_playbook_ids`、`metadata.industry_schema`、`metadata.playbook_policy`。
    - 同一句 generic query 在 `consumer_electronics` inventory 下会加入 product source/product specialist，在 `banks` inventory 下会加入 industry/market source policy。
  - `src/sec_agent/research_lead_llm.py`
    - prompt compact inventory 暴露 playbook registry/candidates/source boundaries。
    - validation 前套用同一 playbook policy postprocess，LLM 遗漏 playbook 时也能被补齐或被 reflection 检查。
- Reflection / downstream boundary:
  - `src/sec_agent/multi_agent_runtime.py`
    - `plan_reflection_gate(...)` 返回 `playbook_policy`。
    - 对 selected playbook id/schema 继续 fail closed；对 source family 跑出 selected playbook policy 给 warning 而不是 hard block。
    - 未匹配行业时输出 generic playbook coverage gap。
    - AgentDataView `source_family_bundle` 继承 `playbook_forbidden_claims` 和 `playbook_commercial_gap_policy`。
- Tests:
  - 新增 `tests/test_industry_playbooks.py`。
  - 更新 inventory、router、Research Lead、reflection、specialist data view tests。

## Result And Evidence

- `python -m pytest tests/test_industry_playbooks.py tests/test_project_inventory_source_inventory.py tests/test_multi_agent_routing_fixtures.py tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_research_lead_llm.py tests/test_multi_agent_specialist_llm.py -q`
  - `107 passed`
- `python -m pytest tests/test_multi_agent_activation_plan.py tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_operator_permissions.py tests/test_multi_agent_reflection_second_pass.py tests/test_sec_agent_retrieval_plan.py tests/test_sec_agent_mcp_contracts.py -q`
  - `103 passed`
- `python -m compileall -q src scripts/cloud scripts/eval_multi_agent`
  - pass
- `git diff --check`
  - pass
- `python -m pytest -q`
  - `817 passed`

## Boundaries

- Playbook 是 route/source/skill contract，不是事实来源。
- Playbook 不会把 public proxy 提权为产品销量、市占率、sell-through、库存、处方量或利润率事实。
- Unknown/uncovered industry 走 `generic_public_research`，同时暴露 `industry_playbook_not_matched` coverage gap。
- `live_public_web_context` 仍需要 G5 web scope policy 和 hard gate，playbook 只能提供 policy id 候选。

## Follow-Up

- G8：把 playbook policy 放入 Global context，把 role-specific source bundle 放入 Role context，并确保 Memo Writer 只消费 verified judgment / claim cards。
- G11：端到端 gate 需要覆盖至少 8 个首批 playbook 行业，验证 source policy 分化和 forbidden claims 不被 memo 绕过。
