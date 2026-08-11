# 259 Research Lead / Universe Scope Contract Hardening

日期：2026-06-07

## 问题

上一轮已经加入跨 agent `evidence_gap_requests`，但继续按 A6 使用场景检查后，发现两个输出合同还可以更硬：

- Research Lead 的 `scope_decision` 需要把要先 inspect 的 catalog 类型和预算上限写成可审计字段，而不是只写自然语言 rationale。
- Universe / Relationship 对 included / excluded ticker 的输出需要明确 `available_source_families`、`relationship_strength` 和 `downstream_operator_owner`，否则 A6 很难判断它到底是专业选 universe，还是凭模型常识扩展。

## 决策

- Research Lead `scope_decision` 固定包含 `scoping_pattern`、`expansion_mode`、`why`、`catalogs_to_inspect`、`candidate_lenses`、`expansion_budget` 和 `stop_condition`。
- Universe / Relationship included ticker 固定包含 `included_ticker`、`candidate_lens`、`inclusion_rationale`、`available_source_families`、`relationship_strength`、`downstream_operator_owner` 和可选 `source_gap`。
- Excluded ticker 固定包含 `excluded_ticker`、`candidate_lens` 和 `exclusion_rationale`，防止模型把 plausible company 全部放进检索 scope。

## 完成

- 强化 Research Lead skill 的 scope decision 输出字段、catalog inspection 类型和 expansion budget 上限。
- 强化 NVIDIA / AI infrastructure 类问题的 lens：公司自身基本面、cloud capex demand、memory / foundry / equipment supply chain、server / networking / power downstream、export-control risk、market reaction。
- 强化 Universe / Relationship skill 的 per-lens candidate selection、per-ticker source coverage、relationship strength、operator ownership 和 source gap 处理。
- 将 `SKILL_SCHEMA_VERSION` 更新到 `sec_agent_research_skills_v0.5`。
- 补充 research skill 单测，断言上述字段不会在后续重构中丢失。

## 验证

- `python -m py_compile src/sec_agent/research_skills.py`
- `python -m pytest tests/test_research_skills.py -q`
  - 结果：`8 passed`
- `python -m pytest tests/test_research_skills.py tests/test_multi_agent_contracts.py tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_judgment_memo_verifier.py tests/test_multi_agent_agent_registry.py -q`
  - 结果：`85 passed`
- `git diff --check`

## 后续

- A6 eval case 需要直接检查 `scope_decision.catalogs_to_inspect`、`scope_decision.expansion_budget`、Universe included/excluded ticker 字段和 downstream operator owner。
- 如果真实模型输出字段缺失，优先修 parser/repair/schema，而不是用 memo 后处理猜测。
