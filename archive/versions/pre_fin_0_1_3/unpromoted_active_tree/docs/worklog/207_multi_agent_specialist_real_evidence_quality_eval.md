# 207 Multi-agent Specialist Real Evidence Quality Eval

日期：2026-05-30

## Prompt

用户确认“把 specialist 质量评测切到真实 evidence rows”的方向后，继续推进实现。

## Decision

本轮先完成真实 evidence rows 的 materialization 和 Specialist 质量评测入口，不把真实证据全文复制进 fixture。

设计原则：

- fixture 只声明 artifact path、source type、filters 和质量期望；
- runner 运行时从已生成的真实 run artifact / processed evidence 中抽取 bounded rows；
- Specialist 仍只能看 bounded rows，不能直接调用工具；
- quality gate 不只检查 schema pass，还检查真实 row 来源、source family、evidence ref、unsupported/conflict 行为和 direct tool call 禁止。

## Work Completed

- 新增真实 evidence Specialist 质量 eval runner：
  - `scripts/eval_multi_agent_specialist_real_evidence_quality.py`
  - 支持 source types：
    - `runtime_ledger_json`
    - `market_evidence_jsonl`
    - `industry_evidence_jsonl`
    - `coverage_matrix_json`
    - `relationship_graph_lookup`
  - 支持 `--materialize-only`，可在无 API key 环境下先验证真实 row 抽取。
- 新增 fixture：
  - `tests/fixtures/multi_agent_specialist_real_evidence_cases_v0_1.jsonl`
  - 4 个 Specialist 真实证据质量用例：
    - Fundamental：JPM 真实 ledger rows，覆盖 net interest income / deposits / loans / revenue。
    - Market-Valuation：JPM 真实 market snapshot row，覆盖 3M return、relative return、drawdown、valuation fields。
    - Industry/Supply-Chain：sector-depth relationship rows + FRED industry macro rows，要求 relationship 只作为 hypothesis / scope。
    - Risk/Counterevidence：JPM credit-risk ledger rows + coverage matrix `operating_income` gap，要求把 unsupported operating-income offset claim 标出来。
- 新增单测：
  - `tests/test_multi_agent_specialist_real_evidence_eval.py`
  - 覆盖 real row materialization、unknown evidence ref rejection、expected unsupported/conflict acceptance。

## Verification

- Compile:
  - `python -m compileall -q scripts/eval_multi_agent_specialist_real_evidence_quality.py`
  - result: pass
- Targeted tests:
  - `pytest tests/test_multi_agent_specialist_real_evidence_eval.py tests/test_multi_agent_specialist_llm.py -q`
  - result: `14 passed`
- Materialize-only real row gate:
  - `python scripts/eval_multi_agent_specialist_real_evidence_quality.py --materialize-only --run-id codex_specialist_real_evidence_materialize_v0_3 --strict`
  - result: `4/4 passed`
  - materialized input rows: `28`
  - output: `eval/sec_cases/outputs/multi_agent_specialist_real_evidence_quality/codex_specialist_real_evidence_materialize_v0_3/specialist_real_evidence_quality_eval.json`

## Current Block

已解除。用户提供 DeepSeek key 后，本轮只通过临时进程环境变量注入并执行真实 Specialist LLM 质量跑分；命令结束后移除当前 shell 环境变量，未写入 `.env`、文档或输出文件。

## Real LLM Gate

```text
python scripts/eval_multi_agent_specialist_real_evidence_quality.py --run-id codex_specialist_real_evidence_deepseek_v0_1 --strict
```

结果：

- run id: `codex_specialist_real_evidence_deepseek_v0_1`
- output: `eval/sec_cases/outputs/multi_agent_specialist_real_evidence_quality/codex_specialist_real_evidence_deepseek_v0_1/specialist_real_evidence_quality_eval.json`
- gate status: `pass`
- cases: `4/4`
- materialized input rows: `28`
- total latency: `77725 ms`
- total tokens: `16574`
- direct tool call count: `0` for all cases
- api key saved: `false`
- raw LLM response saved: `false`

Case 结果：

- `fundamental_analyst`: `14` primary SEC filing rows；`5` supported observations；`3` unsupported/caveat claims；正确保留 revenue / period comparability caveat。
- `market_valuation_analyst`: `1` market snapshot row；`6` supported observations；只使用 `market_snapshot` source family。
- `industry_supply_chain_analyst`: `4` relationship graph rows + `2` industry snapshot rows；`2` supported observations；`2` unsupported claims；relationship rows 保持 hypothesis/context 边界。
- `risk_counterevidence_analyst`: `6` credit-risk ledger rows + `1` coverage gap row；`4` supported observations；`1` unsupported claim；`1` conflict；正确标出缺失 operating-income support。

## Gate

真实 LLM gate 通过标准：

- `case_count=4`
- `pass_count=4`
- `forbidden_direct_tool_call_absent=true`
- `evidence_refs_known=true`
- `all_rows_marked_real=true`
- `input_required_source_families_present=true`
- relationship / industry case 必须保留 hypothesis/context 边界；
- risk case 必须输出 unsupported 或 conflict，不允许把缺失的 operating-income support 当成已证实事实。

本轮以上 gate 全部通过。

## Safety Notes

- 未保存 API key。
- 未保存 raw LLM response。
- fixture 不包含 raw private filing 全文，只包含 artifact path、filters 和质量期望。
- 生成的 `eval/sec_cases/outputs/...` 属于 diagnostic output，不作为默认 tracking candidate。

## Next Step

- 把该 runner 接到 Step17 full-chain eval 的 Specialist layer，区分“route 成功”和“真实 evidence 质量通过”。
- 扩展真实 evidence cases 到 AI infra、banking、healthcare、energy、utilities 等 sector-depth packs。
