# 203 Multi-agent Step 14 Universe Relationship Contract

日期：2026-05-30

## Prompt

用户要求继续沿 188 文档往下做。Step 13 完成后，继续推进 Step 14 的 Universe / Relationship 与 Industry / Supply Chain Analyst 合同。

## Decision

本轮先做可测的确定性合同，不接真实 relationship graph 工具：

- Universe / Relationship Agent 输出的是研究范围、关系假设和需要验证的证据需求，不输出财务结论。
- Relationship graph 只能支持 scope / hypothesis，不能支持收入、利润、现金流、资产负债表等公司披露财务事实。
- Relationship expansion 必须有 source inventory、预算、scope guard、relationship evidence refs 和 inclusion rationale。

## Work Completed

- `src/sec_agent/multi_agent_contracts.py`
  - `UniverseRelationshipPlan` 新增 `included_tickers`、`excluded_tickers`、`scope_guard`、`budget`、`evidence_requirements`。
  - relationship row 新增 `financial_link_type`、`metrics_to_check`、`evidence_source_needed`、`inclusion_rationale`、`claim_scope`。
  - `validate_universe_relationship_plan()` 新增 source inventory、expanded ticker evidence、relationship budget、claim scope 和 evidence source 校验。
  - 新增 `evidence_requirements_from_universe_relationship_plan()`，把 relationship hypothesis 转成 business-level evidence requirements，不包含 physical route、tool name 或路径。
- `tests/test_multi_agent_universe_relationship.py`
  - 新增 Step 14 gate，覆盖 included / excluded、scope guard、budget、source inventory、relationship evidence、claim scope 和 business-level evidence requirement。
- `tests/test_multi_agent_contracts.py`
  - 更新旧 valid relationship fixture，补 inclusion rationale，以符合 Step 14 合同。
- `docs/worklog/188_multi_agent_architecture_execution_plan.md`
  - 更新 Step 14 当前状态和验证结果。
- `docs/worklog/00_internal_master_checklist.md`
  - 勾选 Step 14 contract gate，追加 universe router graph 接入后续项。

## Verification

- `pytest tests/test_multi_agent_universe_relationship.py tests/test_multi_agent_agent_registry.py tests/test_research_skills.py -q`
  - `15 passed in 0.18s`
- `pytest tests/test_multi_agent_universe_relationship.py tests/test_multi_agent_contracts.py tests/test_multi_agent_agent_registry.py tests/test_research_skills.py -q`
  - `21 passed in 0.23s`
- `pytest -q`
  - `340 passed in 11.44s`

## Safety Notes

- 未运行真实 LLM 调用。
- 未接真实 relationship graph 数据源或外部网络。
- 未写入 API key、SSH 密码、private token 或 `.env`。
- 本轮没有执行 git stage / commit。

## Next Step

进入 Step 15：把 multi-agent full graph behind feature flag 接入 Workbench / CLI trace，重点验证旧 run 兼容、trace 不泄漏 raw evidence / private path / internal reasoning，并保持旧链路默认可回滚。
