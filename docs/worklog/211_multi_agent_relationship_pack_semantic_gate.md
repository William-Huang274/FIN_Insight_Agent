# 211 Multi-agent Relationship Pack Semantic Gate

日期：2026-05-31

## Prompt

用户要求补上 relationship-pack semantic relevance gate：sector-depth relationship evidence 必须匹配用户查询的 sector pack；只有当 query 明确要求 data-center power 或 AI-infrastructure demand transmission 时，energy / utilities case 才允许引用 AI-infra pack 的 cross-sector relationship refs。

## Diagnosis

`210` 的真实 full-chain rerun 中，energy / utilities case 的 Industry Specialist 已经能看到并引用 relationship evidence，但引用的是 `technology_ai_infrastructure_depth` refs。该行为说明原有 gate 只检查“是否引用 relationship evidence”，没有检查 relationship pack 是否与 case sector 匹配。

同时，`query_relationship_graph()` 的 sector-depth pack selection 会在 query 包含 `power` / `电力` 时把 AI-infra pack 当成 query-term match。由于 AI-infra pack 位于配置前部，relationship budget 可能被 AI-infra rows 填满，挤掉 energy / real-estate-utilities scope rows。

## Work Completed

- 在 `scripts/eval_multi_agent_real_llm_chain.py` 增加 relationship pack relevance gate：
  - case fixture 可声明 `expected_relationship_pack_ids`。
  - case fixture 可声明 `allowed_cross_sector_relationship_pack_ids`。
  - gate 自动抽取 `sector_depth_pack:<pack_id>:<ticker>` 里的 pack id。
  - sector-depth relationship case 下，Industry Specialist 的 available refs 和 cited refs 都必须落在 expected pack 内。
  - 只有 query 同时包含 AI/data-center 语义和 power/load/transmission 语义时，才把 cross-sector pack 纳入有效 allowlist。
- 在 `tests/fixtures/multi_agent_real_llm_chain_cases_v0_1.jsonl` 为四个 real sector-depth cases 增加 expected pack contract：
  - AI infra: `technology_ai_infrastructure_depth`
  - Banking: `financial_services_depth`
  - Healthcare: `healthcare_life_sciences_depth`
  - Energy / utilities: `energy_infrastructure_depth`, `real_estate_utilities_depth`
  - Energy / utilities 仅在显式 AI/data-center power transmission query 下允许 `technology_ai_infrastructure_depth` cross-sector pack。
- 在 `src/sec_agent/relationship_graph.py` 收窄 pack selection：
  - 先选择 ticker scope 命中的 pack。
  - 如果已有 scope pack 命中，则默认不再把 query-term-only pack 加入结果。
  - 只有 query 明确出现 AI/data-center + power/load/transmission 语义时，才追加 query-term cross-sector pack。
  - 多个 scope pack 命中时按 pack 做 round-robin selection，避免第一个 pack 填满 relationship budget 后挤掉后续 sector pack。

## Verification

Targeted gate tests：

```text
python -m pytest tests/test_multi_agent_real_llm_chain_eval.py tests/test_relationship_graph_lookup.py -q
result: 10 passed
```

Related regression：

```text
python -m pytest tests/test_multi_agent_universe_relationship.py tests/test_multi_agent_universe_relationship_llm.py tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_specialist_real_evidence_eval.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_relationship_graph_lookup.py -q
result: 44 passed
```

Compile：

```text
python -m compileall scripts/eval_multi_agent_real_llm_chain.py src/sec_agent/relationship_graph.py
result: pass
```

Actual config smoke：

```text
query: energy infrastructure + real estate utilities, OXY/HAL/SRE/XEL, power/load context
result: status=ok, relationship_count=24, has_ai_pack=false, has_energy_pack=true, has_utilities_pack=true
```

## Not Run

- No real DeepSeek full-chain rerun was executed in this slice. The change is a deterministic eval / relationship lookup contract update.
- Next real run should rerun the four Step17 sector-depth cases and verify that energy / utilities now cites `energy_infrastructure_depth` and/or `real_estate_utilities_depth`, not AI-infra refs unless the prompt explicitly asks for data-center / AI-infra power transmission.

## Follow-up

- Add numeric runtime-ledger row requirements for cases whose rubric expects numeric financial metrics.
- Rerun Step17 real DeepSeek sector-depth full-chain once the next API eval budget is available.
