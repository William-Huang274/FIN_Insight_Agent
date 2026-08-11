# Agent Graph vNext G6 Product / Technology Specialist

## Problem

G1-G5 已把 `company_product_evidence_graph`、`public_source_context`、`live_public_web_context` 和 web snapshot 边界接入 source inventory / evidence fusion / second pass，但 Specialist 层仍没有独立的产品技术角色。结果是产品 taxonomy、公司披露产品 KPI、公开 proxy、商业 tracker 缺口容易被 Fundamental 或 Industry agent 混合处理，既不利于 memo slot 分工，也容易把公开 proxy 误写成产品收入、销量、份额、库存或利润率事实。

## Decision

- 新增 `product_technology_analyst`，只读取 bounded rows / coverage summary，不持有工具权限。
- 产品 KPI 事实只允许由 `company_product_evidence_graph` 中 `promotion_status=runtime_fact_allowed` 且 `exact_value_authority=true` 的行支撑。
- `public_source_context` 和 `live_public_web_context` 只能写成 public proxy / verification context / lead，不允许替代商业 tracker 或公司披露事实。
- 找不到 sell-through、market share、channel inventory、app revenue、prescription volume、ASP、tracker forecast 等公开免费权威数据时，必须进入 bounded gap / unsupported ClaimCard，不允许兜底成低置信事实。

## Work Completed

- Agent / skill:
  - `src/sec_agent/agent_contracts.py`、`src/sec_agent/agent_registry.py`
    - 新增 `product_technology_analyst`，默认 expert agent 集合包含该角色；focused/deterministic 模式继续禁用。
    - 合同要求产品专家激活时必须有 `company_product_evidence_graph`、`public_source_context` 或 `live_public_web_context` scope。
  - `src/sec_agent/research_skills.py`
    - 新增 `product_technology_analysis` skill mapping，并补齐 `web_evidence_operator` skill mapping。
  - `src/sec_agent/prompts/skills/product_technology_analysis_skill_v0_1.md`
    - 定义产品 taxonomy、产品 KPI、公开 proxy、commercial gap 的输出边界和失败处理。
- Routing / planning:
  - `src/sec_agent/multi_agent_router.py`
    - 标准/深研模式识别产品、SKU、platform、app、clinical/regulatory、public proxy、commercial tracker gap 需求后激活产品专家。
  - `src/sec_agent/research_lead_llm.py`
    - Prompt 和 postprocess alignment 会根据 product/public/live source family 或 route requirement 插入产品专家，并补齐 source family。
- Runtime / ClaimCard:
  - `src/sec_agent/multi_agent_runtime.py`
    - Specialist execution order 加入产品专家。
    - AgentDataView 为产品专家分配 product graph rows、public source rows、live web context rows。
    - 新增产品 required claim slots：`product_taxonomy_or_surface`、`company_disclosed_product_kpi`、`public_proxy_or_verification_context`。
    - 新增 counterclaim slot：`product_commercial_tracker_gap`。
  - `src/sec_agent/multi_agent_contracts.py`
    - 新增 product memo slot、source-family claim scope、product KPI / proxy claim type 归一化和 source boundary。
  - `src/sec_agent/specialist_llm.py`
    - 产品专家输出合同要求 product claim cards。
    - 后处理 salvage 会把没有 product graph exact-authority 支撑的产品 KPI observation 降为 unsupported/gap，而不是保留 supported fact。
- Evaluation support:
  - `scripts/eval_multi_agent/audit_fin_agent_layer_quality.py`
  - `scripts/eval_multi_agent/audit_multi_agent_output_quality.py`
  - `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`
    - 同步产品专家白名单、source family 质量审计和 audit 缩写，避免真实链路评测误判新增角色。

## Result And Evidence

- `python -m pytest tests/test_multi_agent_agent_registry.py tests/test_research_skills.py tests/test_multi_agent_activation_plan.py tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_contracts.py tests/test_multi_agent_routing_fixtures.py tests/test_multi_agent_research_lead_llm.py tests/test_multi_agent_output_quality_audit.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_fin_agent_layer_quality_audit.py -q`
  - `148 passed`
- `python -m pytest tests/test_multi_agent_operator_permissions.py tests/test_multi_agent_reflection_second_pass.py tests/test_sec_agent_retrieval_plan.py tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_evidence_requirements.py tests/test_sec_agent_mcp_contracts.py tests/test_project_inventory_source_inventory.py -q`
  - `118 passed`
- `python -m compileall -q src/sec_agent scripts/eval_multi_agent`
  - pass
- `git diff --check`
  - pass

## Boundaries

- 产品 taxonomy / 产品 surface 可以来自公司披露、官网/产品页、公开 proxy 或 live web context，但只能作为 taxonomy/context，不能自动变成产品 KPI fact。
- 产品 KPI fact 必须引用 `company_product_evidence_graph` exact-authority rows。
- 公开 proxy 可以用于“方向性验证/线索”，不能证明公司产品收入、真实销量、份额、库存、毛利率、处方量或 sell-through。
- 商业 tracker 缺口是显式 gap，不允许由低强度公开源填平。
- Milvus semantic context 后续仍只能补召回和语义线索，不能提升 exact-value authority。

## Follow-Up

- G7：把机器可读行业 playbook registry 接到 Research Lead planning，让 Lead 同时看到 inventory capability、source family boundary、行业 playbook 和缺口结构后再分派任务。
- G8：升级 AgentDataView 的 Global / Role / Private context 分层，避免下游 agent 共享过量原始证据。
