# 251 Research Lead Cost-Aware Route Selection

日期：2026-06-07

## Prompt

承接 `250` 后继续按 `expanded_universe_retrieval_agent_framework_v0_1.zh-CN.md` 的下一步推进：更新 Research Lead prompt/skill，让它按成本和问题类型选择 SEC、Milvus、market、industry 和 relationship routes。

## Work Completed

- 更新 Research Lead LLM prompt contract：
  - EvidenceRequirementPlan schema hint 新增 `milvus_semantic`。
  - 每条 requirement 应输出 `route_selection_reason`、`route_cost_tier` 和 `route_selection_policy=cost_and_query_type_aware_v0_1`。
  - 新增 Route choice policy，明确：
    - `ledger_first` 是 exact-value low-cost 主权威。
    - `filing_text` / `8k_commentary` / `risk_text` 是 SEC 文本 medium-cost routes。
    - `milvus_semantic` 是 high-cost typed SEC semantic recall supplement，不能替代 `ledger_first`。
    - `market_snapshot` / `industry_snapshot` 是 context-only medium-cost routes。
    - `relationship_graph` 是 high-cost scope/hypothesis route，只在显式关系/供应链/传导问题激活。
- 更新 `research_lead_planning_skill_v0_1.md`：
  - 增加 Route Selection Policy 小节。
  - 明确 Lead 要选择 cheapest sufficient route set，并记录 route reason/cost/policy。
- 更新 route metadata 保留链路：
  - `retrieval_plan.build_evidence_requirement_plan(...)` 保留或派生 `route_selection_reason`、`route_cost_tier`、`route_selection_policy`。
  - physical retrieval route 和 retrieval task 也携带 route-selection metadata。
  - `build_multi_agent_evidence_requirement_plan(...)` 的 multi-agent contract 标记 `route_selection_policy=cost_and_query_type_aware_v0_1`。
  - `route_intents` 新增 per-route `route_cost_tier`。
  - Specialist task-card compact requirement 保留 route selection reason/cost/policy。
  - operator tool argument summary 保留 route selection metadata，方便 runtime ledger 审计。

## Verification

- 本地 targeted tests：
  - `python -m pytest tests\test_multi_agent_research_lead_llm.py tests\test_research_skills.py tests\test_sec_agent_retrieval_plan.py -q`
  - 结果：`41 passed`
  - `python -m pytest tests\test_multi_agent_evidence_requirements.py tests\test_multi_agent_operator_permissions.py tests\test_multi_agent_specialist_llm.py -q`
  - 结果：`74 passed`
- 本地语法检查：
  - `python -m py_compile src\sec_agent\research_lead_llm.py src\sec_agent\multi_agent_runtime.py src\sec_agent\retrieval_plan.py`
  - 结果：pass
- 云端同步：
  - 已同步 Research Lead / runtime / retrieval plan / skill / targeted tests 到 `/root/autodl-tmp/fin_agent_sp500_stage/workspace`。
  - 云端 `PYTHONPATH=src /root/miniconda3/bin/python -m py_compile ...` pass。
  - 云端 inline route-selection contract check pass：`remote_research_lead_route_selection_check: pass`。

## Decision

- Architecture 下一步第 5 项“更新 Research Lead prompt/skill，让它按成本和问题类型选择 route”已完成到 prompt / skill / normalized route metadata / retrieval route ledger contract。
- 本轮没有跑真实 full-chain，也没有扩大默认 routes；Lead 仍必须按 query intent 显式选择 costly semantic、industry、market 或 relationship routes。

## Next

1. 更新 Specialist skill vNext，特别是 Market 和 Industry 的 source boundary。
2. 先跑 A1-A5 分层 gate，不直接跑 full-chain。
