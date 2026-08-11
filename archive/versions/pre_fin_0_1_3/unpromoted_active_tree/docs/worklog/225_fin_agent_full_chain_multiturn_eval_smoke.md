# 225 Fin Agent Full-Chain / Multi-Turn Eval Smoke

日期：2026-06-01

## Prompt

用户要求先设计 `10-20` 个覆盖不同维度、公司、难度的 full-chain / multi-turn 测试用例，然后只用 `2-3` 个高信息量 case 真实跑 DeepSeek；若发现问题先修，不要直接跑完整集合浪费 token。本轮如果稳定，后续再考虑收口和 merge 主线。

## Design

新增 full-chain / multi-turn case fixture：

- `tests/fixtures/fin_agent_full_chain_multiturn_cases_v0_1.jsonl`
- 共 `17` 个 case，覆盖 exact lookup、focused answer、standard memo、sector-depth、英文输出、多轮 scope override。
- 行业覆盖：AI infra、banking、healthcare、energy、utilities、consumer、mega-cap AI capex。
- 难度覆盖：L1 单指标、L2 focused answer、L3 comparative memo、L4 sector-depth relationship / multi-turn deep research。

新增执行计划：

- `docs/eval/fin_agent_full_chain_multiturn_eval_plan_v0_1.md`
- 固定首批 smoke：`fin_full_exact_msft_capex_zh`、`fin_full_mt_semis_scope_t1`、`fin_full_mt_semis_scope_t2`。
- Gate 覆盖 Research Lead activation、真实 retrieval、SEC BM25/ObjectBM25/BGE、runtime ledger、Specialist quality、Memo/Verifier、response language、forbidden scope。

## Issues Found And Fixed

1. exact lookup 没有稳定 runtime ledger rows。
   - 修复 `ledger_first` 无 ledger store 时回退到真实 `sec_search_filings`。
   - 让 SQLite structured-object / ObjectBM25 rows 进入 runtime exact-value ledger。
   - deterministic lookup renderer 只渲染目标年份 / metric family。

2. T2 memo contract repair 误伤。
   - 将非 material numeric token 从 hard error 降为 warning。
   - relationship_graph claim type 归一到 `relationship_hypothesis`。
   - market snapshot synthesized thesis 不再被纯 market as-of-date gate 误伤。

3. 中文 memo gate 不稳定。
   - `Memo Writer` / verifier 增加 zh-CN user-facing prose normalization。
   - 当 DeepSeek 把英文 ClaimCard 直接带入中文 memo claim 时，添加 evidence-bound Chinese wrapper，避免最终输出混英文。

4. Research Lead 对无风险意图的 T1 过度激活 Risk。
   - `research_lead_llm` 增加 explicit-risk-intent pruning：没有 risk / counterevidence / credit / downside / uncertainty intent 时，移除 `risk_counterevidence_analyst` 并记录 skip reason。
   - T1 fixture 将 Risk 从 conditional 改成 forbidden，以检查精准激活。
   - 相关单测覆盖 risk prune / risk keep。

5. output-quality audit 对 exact lookup 的低 chars/token 误报。
   - `scripts/audit_multi_agent_output_quality.py` 不再对 `deterministic_lookup` 标记 `low_memo_chars_per_token`，因为 exact answer 应当短。

## Accepted Smoke Result

Accepted run:

- Run ID: `20260601_fin_agent_full_chain_multiturn_smoke_after_lead_prune_v0_1`
- Output: `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/20260601_fin_agent_full_chain_multiturn_smoke_after_lead_prune_v0_1`
- Cases: `3`
- Gate: `pass`
- Passed: `3/3`
- Total tool calls: `14`
- Real retrieval required cases: `1/1`

Case results:

| Case | Mode | Gate | Tool calls | Main observation |
| --- | --- | ---: | ---: | --- |
| `fin_full_exact_msft_capex_zh` | deterministic lookup | pass | 1 | SEC runtime ledger rows present; output is Chinese single-metric answer with evidence boundary. |
| `fin_full_mt_semis_scope_t1` | standard memo | pass | 4 | Risk Specialist no longer activated; Fundamental + Market + Memo/Verifier path passes. |
| `fin_full_mt_semis_scope_t2` | deep research | pass | 9 | Scope narrowed to NVDA; relationship lookup / industry / risk / market all active; AMD forbidden scope avoided. |

Output-quality audit:

- exact: no flags, `10,817` total tokens.
- T1: no flags, `41,905` total tokens, `9` claim cards.
- T2: `high_total_token_cost`, `80,293` total tokens, `16` claim cards.

Project layer-quality audit:

- Gate: `pass`
- Weighted score: `3.136`
- Sole remaining flag: `high_total_token_cost`
- Universe / Specialist stages are inferred from activated agents when fixture metadata is not carried into the case score.
- Memo Writer / Verifier stage scoring correctly skips deterministic exact lookup cases.

## Cost Experiment

T2 cost-tight diagnostic run:

- Run ID: `20260601_fin_agent_full_chain_t2_cost_tight_smoke_v0_1`
- Gate: `pass`
- Tokens: `88,893`
- Flags: `high_total_token_cost`, `low_claim_card_token_efficiency`, `low_memo_chars_per_token`

Decision: do not adopt this tighter CLI profile. Lowering top-k / output caps alone did not reduce cost; it increased Lead / Universe token usage and reduced conversion efficiency.

## Verification

- `python -m compileall src\sec_agent\research_lead_llm.py scripts\audit_multi_agent_output_quality.py scripts\eval_multi_agent_real_llm_chain.py scripts\cloud\sec_agent_interactive.py src\sec_agent\langgraph_orchestrator.py src\sec_agent\multi_agent_runtime.py src\sec_agent\mcp_tool_registry.py src\sec_agent\memo_llm.py src\sec_agent\multi_agent_contracts.py`
- `pytest tests\test_multi_agent_research_lead_llm.py tests\test_multi_agent_real_llm_chain_eval.py tests\test_multi_agent_langgraph_routing.py tests\test_multi_agent_memo_llm_repair.py tests\test_multi_agent_judgment_memo_verifier.py tests\test_multi_agent_contracts.py tests\test_sec_agent_langgraph_orchestrator.py -q`
- Result: `122 passed`
- Real DeepSeek smoke: accepted `3/3` pass.

## Decision

Functional smoke and project layer-quality audit are accepted, but this is not yet a full 17-case closeout.

Reason:

- Full-chain gates pass.
- Agent activation is now more precise on the T1 no-risk prompt.
- T2 deep-research output is useful and evidence-bounded, but token cost remains high and should be reduced before broad regression / mainline merge.

Proceed next with targeted cost/quality work before running the full 17-case set:

1. Add deep-research token budget gates per agent, not only aggregate run flags.
2. Reduce Universe Relationship from repair-prone 2-call output to one-pass compact relationship summary.
3. Compress Specialist input around claim slots and remove duplicate SEC rows before prompt assembly.
4. Add Memo/Verifier projection reuse so Verifier does not reread a large memo inventory.
5. Rerun the same 3-case smoke, then expand to banking / energy / healthcare / utilities only after T2 falls below the accepted cost threshold.

## Safety Notes

- Runtime credential was read from environment only.
- No API key, SSH password, private token, raw model response, or private path was written to this worklog.
