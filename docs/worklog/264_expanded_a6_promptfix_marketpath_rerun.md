# 264 Expanded A6 Promptfix / Market Path Rerun

Date: 2026-06-08

## Prompt

继续复盘 A6 4-case smoke 的效率和链路质量问题，先修可确定的问题，再决定是否可以扩大到剩余 case 或并发跑。

## Changes

- 修复 `research_skill_prompt(..., max_chars=...)` 截断策略：共享 evidence boundary 变长后，Memo Writer 等角色的专属 skill 被截断掉；现在正常预算下会同时保留 shared boundary 和 role-specific skill。
- Memo Writer 在 deterministic gate 前清洗 `direct_answer` 中的内部标签，如 `Synthesized thesis`、`ClaimCard` 和 pipe-joined claim，避免可本地修复的表面问题触发整篇 memo LLM repair。
- Research Lead / Universe LLM route 增加 `repair_history` / `last_repair_failure`，并补到 LangGraph summary 和 eval `agent_audit`。
- 云端同步上述源码和测试，重启 resident MCP worker，并预热 Milvus/BGE cache。

## Verification

- Local:
  - `python -m py_compile src\sec_agent\memo_llm.py src\sec_agent\research_lead_llm.py src\sec_agent\universe_relationship_llm.py src\sec_agent\research_skills.py`
  - `python -m pytest -q tests\test_multi_agent_memo_llm_repair.py tests\test_multi_agent_research_lead_llm.py tests\test_multi_agent_universe_relationship_llm.py tests\test_research_skills.py` -> `75 passed`
  - A6/core regression set -> `113 passed`
  - Summary/audit routing tests -> `70 passed`
- Cloud:
  - `py_compile` passed for synced source files.
  - Prompt sanity check confirmed Research Lead / Memo Writer / Universe / Fundamental prompts include both shared boundary and role-specific skill.
  - Resident worker restarted as PID `20805`; Milvus/BGE first warmup took `223602 ms`, immediate hot repeat took `1648 ms`.

## Cloud Runs

### v0_3 full 4-case rerun

Run ID: `20260608_expanded_a6_multi_query_milvus_full_chain_smoke_promptfix_v0_3`

- Result: `2/4` pass.
- Total LLM tokens: `166154` vs previous postfix `206678`.
- Scope/gap contract failures: `0`.
- `fin_full_scope_nvda_basic_fundamental_zh`: pass, `131362 ms`; Memo Writer `1` call / `8668` tokens, fixing prior memo retry/token failure.
- `fin_full_standard_nvda_amd_market_zh`: fail only performance, `297621 ms`.
- `fin_full_sector_ai_infra_depth_zh`: fail due `market_rows_present=false` and `real_evidence_quality_pass=false`.
- Diagnosis: this run used a wrong `MARKET_EVIDENCE_PATH`; actual artifact is under `market/processed/evidence_packs/..._3m_market_evidence.jsonl`.

### v0_4 failed2 rerun with corrected market path

Run ID: `20260608_expanded_a6_failed2_marketpath_hotfix_resident_warm_smoke_v0_4`

- Result: `1/2` pass.
- `fin_full_standard_nvda_amd_market_zh`: pass, `100724 ms`, false checks `{}`.
- `fin_full_sector_ai_infra_depth_zh`: fail only `performance.case_elapsed_ms_lte`, `300469 ms` against the `300000 ms` gate.
- Market rows and Specialist real-evidence quality passed after correcting the market evidence path.
- Remaining trace:
  - Research Lead sector-depth: first call hit `model_output_truncated`, then repaired.
  - Universe sector-depth: first call failed validation on unknown sector-depth pack evidence refs, then repaired.
  - Standard: Research Lead first call omitted `coverage_reflection`, then repaired.

## Decision

Do not run the remaining A6 cases as a quality gate yet. The current path is functionally close, but sector-depth still misses the latency gate and Research Lead / Universe still spend one repair round in important cases. A low-concurrency diagnostic run is acceptable only if explicitly labeled pressure/observability, not promotion evidence.

## Next

- Reduce Research Lead output length or max-token pressure for deep-research activation.
- Normalize/whitelist sector-depth pack refs before Universe economic-link validation so the first call does not need repair.
- Make the Workbench/cloud A6 eval profile use the canonical market evidence pack path.
- Add resident SEC search/reranker prewarm, not only Milvus prewarm, before timing-sensitive smoke runs.
