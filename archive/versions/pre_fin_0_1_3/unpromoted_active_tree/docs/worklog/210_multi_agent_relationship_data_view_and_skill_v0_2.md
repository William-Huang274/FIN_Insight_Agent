# 210 Multi-agent Relationship Data View And Skill v0.2

日期：2026-05-31

## Prompt

用户指出 `industry_supply_chain_analyst` 的 data view 会把真实 relationship graph rows 挤掉，并要求：

- 给 `industry_supply_chain_analyst` 单独做 balanced row selector，保证 relationship graph rows 不被 `industry_snapshot` 截断。
- 把 `relationship_summary` 显式传入 Specialist LLM request / prompt。
- 在 eval 中增加门控：sector-depth / relationship case 下，industry specialist 必须看到并引用 relationship evidence。
- 不只修单个 agent，而是升级四个 Specialist 的 role-specific skill 到 v0.2：明确输入字段、分析步骤、必填输出结构、缺证处理和质量 rubric。

## Diagnosis

Step17 真实 4-case 运行中，relationship lookup 和 UniverseRelationshipPlan 已经执行，但 `industry_supply_chain_analyst` 的 data view 先拼 `industry_snapshot_rows`，再拼 relationship rows，最后统一截断到 16 行。行业 rows 足够多时，relationship rows 会在进入 Specialist 前被截掉。

同时，`build_agent_data_view()` 已生成 `relationship_summary`，但 `build_specialist_request_from_state()` 未把它写入 Specialist request，导致 prompt 层看不到 registry 允许的 relationship summary。

## Work Completed

- 在 `src/sec_agent/multi_agent_runtime.py` 增加 industry 专用 balanced selector：
  - `industry_snapshot` 与 `relationship_graph` 按 source family 平衡选入；
  - 默认最多 16 行；
  - 当 relationship rows 存在且输入超过 cap 时，至少保留 3 条 relationship rows。
- 在 `src/sec_agent/specialist_llm.py` 显式透传 `relationship_summary`：
  - `build_specialist_request_from_state()` 现在返回 compact `relationship_summary`；
  - prompt `Input JSON` 包含 `relationship_summary`；
  - `known_evidence_refs` 同时包含 bounded rows 和 relationship summary refs；
  - industry / risk prompt rows 都走 source-balanced compact。
- 在 eval gate 中增加 relationship evidence 质量检查：
  - `scripts/eval_multi_agent_real_llm_chain.py` 对 sector-depth / relationship case 自动要求 industry specialist 输入包含 `relationship_graph`、relationship summary 非空、观察中使用 `relationship_graph` source family，并且引用 relationship evidence ref。
  - `scripts/eval_multi_agent_specialist_real_evidence_quality.py` 增加 `required_observation_source_families` 和 `required_cited_source_families` gate。
  - `tests/fixtures/multi_agent_specialist_real_evidence_cases_v0_1.jsonl` 的 industry relationship cases 已要求引用 `relationship_graph`。
- 新增四个 Specialist role-specific skill v0.2：
  - `fundamental_analysis_skill_v0_2.md`
  - `industry_supply_chain_analysis_skill_v0_2.md`
  - `market_valuation_analysis_skill_v0_2.md`
  - `risk_counterevidence_skill_v0_2.md`
- `src/sec_agent/research_skills.py` 将四个 Specialist skill 映射到 v0.2，并把 skill schema version 提升到 `sec_agent_research_skills_v0.2`。

## Verification

Targeted tests：

```text
python -m pytest tests/test_multi_agent_universe_relationship.py tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_specialist_real_evidence_eval.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_research_skills.py -q
result: 32 passed
```

Compile / related regression：

```text
python -m compileall src/sec_agent/multi_agent_runtime.py src/sec_agent/specialist_llm.py src/sec_agent/research_skills.py scripts/eval_multi_agent_specialist_real_evidence_quality.py scripts/eval_multi_agent_real_llm_chain.py
result: pass

python -m pytest tests/test_multi_agent_contracts.py tests/test_multi_agent_agent_registry.py tests/test_multi_agent_judgment_memo_verifier.py tests/test_multi_agent_chain_performance_eval.py -q
result: 24 passed
```

Sensitive-info scan:

```text
rg -n "sk-|api[_-]?key|password|token|BEGIN PRIVATE KEY" <touched files>
result: only variable names / token metric fields; no plaintext API key, password, SSH credential, or private token found.
```

Real DeepSeek Step17 full-chain rerun：

```text
run_id: 20260531_step17_relationship_skill_v0_2_full4_rerun_cuda_deepseek_v0_1
entry: scripts/eval_multi_agent_real_llm_chain.py
mode: --category sector_depth --real-evidence-operators --strict --context-runner in_process --bge-device cuda
model: deepseek-v4-pro via DEEPSEEK_API_KEY environment variable only
result: gate_status=pass, passed=4/4, failed=0, pass_rate=1.0
total_tool_calls=39
real_retrieval_required_cases=4/4
real_specialist_quality_passed=4/4
output: eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/20260531_step17_relationship_skill_v0_2_full4_rerun_cuda_deepseek_v0_1/real_chain_eval_summary.json
```

Case-level evidence checks：

| Case | Gate | Tool calls | SEC search calls | BGE candidates | Industry input sources | Industry relationship citation gate |
| --- | --- | ---: | ---: | ---: | --- | --- |
| AI infrastructure | pass | 11 | 6 | 96 | `industry_snapshot`, `relationship_graph` | pass |
| Banking | pass | 9 | 4 | 52 | `industry_snapshot`, `relationship_graph` | pass |
| Healthcare | pass | 8 | 4 | 57 | `industry_snapshot`, `relationship_graph` | pass |
| Energy / utilities | pass | 11 | 5 | 72 | `industry_snapshot`, `relationship_graph` | pass |

All four cases reported `claim_verification=pass`, `specialist_verification=pass`, `universe_validation=pass`, `relationship_lookup_status=ok`, and BGE runtime metadata showed `cuda_available=true`.

The rerun also validated the prior failure fixes:

- AI infra no longer fails from provider transport errors after gateway retry hardening.
- Energy / utilities no longer accepts a Universe plan that drops relationship lookup rows; the fallback path preserves lookup relationships into `relationship_graph_observation`, and the Specialist quality gate sees and cites relationship refs.
- `industry_supply_chain_analyst` now receives both `industry_snapshot` and `relationship_graph` rows under the 16-row cap in all four sector-depth cases.

## Follow-up

- Completed in `211_multi_agent_relationship_pack_semantic_gate.md`: add a stricter semantic-pack gate so an energy / utilities case cannot satisfy the relationship-evidence gate with AI-infra relationship refs unless the query explicitly asks about data-center power or AI-infrastructure demand transmission.
- Decide whether text-heavy sector-depth SEC searches should require numeric runtime-ledger rows. This run had real SEC context rows and BGE rerank, but the SEC tool summaries for these cases did not materialize numeric ledger rows.
- Review final memo quality again after skill v0.2, especially whether industry observations now produce chain-map / transmission-mechanism language rather than generic sector context.
- Consider making `INDUSTRY_RELATIONSHIP_MIN_ROWS` configurable only if future token budgets require tuning.
