# 252 Specialist Market / Industry Source Boundary vNext

日期：2026-06-07

## Prompt

承接 `251` 后继续按 `expanded_universe_retrieval_agent_framework_v0_1.zh-CN.md` 的下一步推进：更新 Specialist skill vNext，特别是 Market 和 Industry 的 source boundary，让它们消费 `source_family_bundle` 和 route-selection metadata。

## Work Completed

- 更新 Market Valuation Specialist skill：
  - Required input 增加 `source_family_bundle`。
  - 明确使用 `selected_source_families`、`context_only_source_families`、`forbidden_claim_scopes` 和 route-selection metadata。
  - 要求 Market rows 只能形成 market/valuation context，不能证明 company-reported revenue、margin、cash flow、balance-sheet 或 SEC exact-value facts。
  - company rows 只有在 bundle 允许且直接解释 market divergence 时才可用。
- 更新 Industry / Supply-Chain Specialist skill：
  - Required input 增加 `source_family_bundle`。
  - 明确 Industry / Relationship rows 只能支持 scope、context 和 hypotheses。
  - 禁止把 `industry_snapshot` / `relationship_graph` 写成 reported revenue、margin、customer/supplier fact、cash flow、capex 或 balance-sheet facts。
  - 如果 route-selection metadata 说明 `relationship_graph` 或 `industry_snapshot` 是 context route，输出必须保持 context/hypothesis-grade。
- 更新 Specialist LLM prompt 指令：
  - 在写任何 observation 前必须使用 `source_family_bundle` 执行 selected source families、context-only families、semantic-supplement limits 和 forbidden claim scopes。

## Verification

- 本地 targeted tests：
  - `python -m pytest tests\test_research_skills.py tests\test_multi_agent_specialist_llm.py -q`
  - 结果：`46 passed`
  - `python -m pytest tests\test_multi_agent_research_lead_llm.py tests\test_sec_agent_retrieval_plan.py -q`
  - 结果：`36 passed`
  - `python -m pytest tests\test_multi_agent_evidence_requirements.py tests\test_multi_agent_operator_permissions.py -q`
  - 结果：`34 passed`
- 本地语法检查：
  - `python -m py_compile src\sec_agent\specialist_llm.py src\sec_agent\research_skills.py`
  - 结果：pass
- 云端同步：
  - 已同步 `specialist_llm.py`、Market / Industry skill 文本和 targeted tests 到 `/root/autodl-tmp/fin_agent_sp500_stage/workspace`。
  - 云端 `PYTHONPATH=src /root/miniconda3/bin/python -m py_compile ...` pass。
  - 云端 inline Specialist source-boundary skill check pass：`remote_specialist_source_boundary_skill_check: pass`。

## Decision

- Architecture 下一步第 6 项“更新 Specialist skill vNext，特别是 Market 和 Industry 的 source boundary”已完成到 skill / prompt contract。
- 本轮没有跑真实 full-chain；只完成分层 prompt contract 和 deterministic tests。

## Next

1. 先跑 A1-A5 分层 gate，不直接跑 full-chain。
2. 只有分层 gate 通过后，跑 10-20 case full-chain / multi-turn。
