# 223 Fin Agent Memo Profile v0.6 Eval

## Problem

用户要求放开当前偏短的 Memo Writer contract，并用不同行业、不同覆盖面、不同难度的多个测试用例验证输出质量。

上一轮 S6-S8 的 Memo Writer 虽然安全，但 `direct_answer` 常在约 350 chars，最终输出更像 bounded research memo，而不是有用的投研回答。核心问题不是 LLM 不能写，而是合同固定短、输出字段过少、profile 不区分 focused / standard / deep research。

## Decision

本轮不全局放开，而是新增 `memo_profile = compact | standard | expanded | deep_research`：

- `compact`: focused / evidence-thin case，保留短答和强边界。
- `standard`: 标准 memo 的中等长度合同。
- `expanded`: ClaimCard 密度足够的 standard memo。
- `deep_research`: sector-depth / relationship case，允许更长 direct answer、更多 memo claims 和 action fields。

同时新增 surface quality gate，避免“放长但没质量”：

- 禁止 direct answer 出现 internal `ClaimCard` / `Synthesized thesis` / pipe-joined claims。
- 禁止 direct answer 重复句。
- `standard / expanded / deep_research` 必须包含 `investment_implications`、`what_would_change_view`、`monitoring_items`。
- S6-S8 gate 检查 profile 是否匹配 case 深度、direct answer 是否在 profile 约束内、memo_claim_count 是否达标。

## Work Completed

- `src/sec_agent/memo_llm.py`
  - 新增 `MemoProfileSpec` 和 profile selector。
  - `build_shared_memo_context` 输出 `memo_profile`。
  - Memo prompt 从固定 compact contract 升级为 profile-driven v0.6 contract。
  - expanded/deep profile 会向 Memo Writer 暴露更多精选 ClaimCards。
  - 新增 `investment_implications`、`what_would_change_view`、`monitoring_items`、`evidence_gaps_but_actionable` 输出字段。

- `src/sec_agent/multi_agent_contracts.py`
  - Aggregator synthesized thesis 不再生成 internal `Synthesized thesis from bounded ClaimCards` 前缀。
  - Memo verifier 新增 direct-answer surface gate 和 profile action-field gate。

- `src/sec_agent/langgraph_orchestrator.py`
  - Renderer 支持 profile-aware memo claim 渲染上限。
  - Renderer 展示 investment implications、view-change、monitoring、actionable gaps。

- `scripts/eval_multi_agent_judgment_memo_gate.py`
  - 新增 profile-depth gate、direct-answer profile length gate、profile metrics。
  - Artifact-reuse runner 在 activation metadata 缺失时补齐 case execution mode，避免 sector-depth case 被误判为 expanded。

- `configs/fin_agent_quality_rubric_v0_1.json`
  - Memo Writer gate 增加 `memo_profile_matches_case_depth` 和 `memo_direct_answer_profile_length`。

- 文档更新：
  - `docs/eval/fin_agent_layered_quality_execution_plan_v0_1.md`
  - `docs/eval/fin_agent_s1_s8_agent_quality_case_matrix_v0_2.md`
  - `reports/model_runs/20260601_fin_agent_s6_s8_memo_profile_v0_6_deepseek_eval.md`

## Real DeepSeek Evaluation

| Case | Industry / depth | Gate | Profile | Direct chars | Memo claims | Ref count | Repairs | Tokens |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| `ma_nvda_amd_market_standard` | semiconductors / comparative standard | pass | `expanded` | 1126 | 5 | 5 | 0 | 18,190 |
| `ma_energy_capex_commodity_standard` | energy / standard with source gaps | pass | `expanded` | 1186 | 5 | 3 | 0 | 14,873 |
| `ma_banking_deposit_credit_standard` | banking / standard | pass | `expanded` | 1142 | 5 | 4 | 0 | 17,356 |
| `ma_utilities_power_load_deep` | utilities / sector-depth | pass | `deep_research` | 1754 | 8 | 9 | 0 | 21,485 |

Audit outputs:

- `reports/eval/20260601_fin_agent_s6_s8_memo_profile_v0_6_nvda_amd_audit.md`
- `reports/eval/20260601_fin_agent_s6_s8_memo_profile_v0_6_energy_audit.md`
- `reports/eval/20260601_fin_agent_s6_s8_memo_profile_v0_6_banking_audit.md`
- `reports/eval/20260601_fin_agent_s6_s8_memo_profile_v0_6_utilities_audit.md`

All four audit gates passed with weighted score `3.322` and no quality flags.

## Result And Evidence

- Fixed-short memo contract has been replaced for standard/deep cases.
- Final pass runs used `0` memo repairs.
- Memo output now includes thesis-led direct answer, memo claims, implications, what-would-change-view, monitoring items, and actionable source gaps.
- Verifier still blocks unsupported/raw/tool leakage and now also blocks bad direct-answer surface patterns.

## Remaining Boundaries

- Energy still depends on local data coverage: commodity snapshot and CVX filing rows are usable, but XOM hard rows, management commodity outlook, and external supply/demand/regulatory evidence remain incomplete.
- Utilities sector-depth can cite relationship evidence and reason about indirect power-load transmission, but still cannot prove direct customer/supplier/contract links to NVDA/MSFT/AMZN.
- Healthcare was not covered in S5-S8 profile eval because current healthcare fixture is focused answer and does not activate Specialist layer.
- Token cost is now more productive, but still high for S6-S8 profile runs; next optimization should be profile-aware payload budgeting rather than shortening the memo contract again.

## Verification

- `python -m compileall src\sec_agent\memo_llm.py src\sec_agent\multi_agent_contracts.py src\sec_agent\langgraph_orchestrator.py scripts\eval_multi_agent_judgment_memo_gate.py`
- `pytest -q tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_judgment_memo_verifier.py tests/test_multi_agent_contracts.py tests/test_fin_agent_layer_quality_audit.py`
- `pytest -q tests/test_multi_agent_real_llm_chain_eval.py tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_operator_permissions.py`

## Follow-up

- Add healthcare standard/deep test case.
- Add profile-aware token budget policy and renderer product-surface eval.
- Continue full-chain eval after S1-S8 layer gates remain green.
