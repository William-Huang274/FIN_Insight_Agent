# 208 Multi-agent Step17 Full-chain Real Retrieval Eval

日期：2026-05-31

## Prompt

用户要求把 Step17 full-chain eval 的 Specialist layer 接到真实 evidence runner，区分 route 成功和真实 evidence 质量通过，扩展 AI infra、banking、healthcare、energy、utilities sector-depth packs，并从主 agent 开始跑真实 full chain；同时检查 `sec_search_filings` 是否实际触发 BM25 / ObjectBM25 / BGE rerank，以及 BGE 是否走 CUDA。

## Decision

本轮继续保持 Step17 为 diagnostic-only，但把 gate 设计成真实链路 hard check：

- 主 agent 必须按 source contract 激活 `deep_research` / `universe_relationship` / relationship graph route；
- `execute_evidence_operators` 必须是 real mode，不接受 dry-run；
- `sec_search_filings` 必须实际产生 context rows、BM25 candidates 和 BGE rerank candidates；
- Specialist route pass 与真实 evidence quality pass 分开统计；
- runtime ledger / tool_call_ledger 必须能审计每个 node/agent/tool 的状态、输入摘要、输出 row count、错误、BGE runtime config；
- API key 不写入文件，raw LLM response 不保存。

## Work Completed

- 修复 SEC operator 参数边界：
  - 在 `src/sec_agent/multi_agent_runtime.py` 增加 SEC search source tier 归一化。
  - `relationship_graph` / `industry_snapshot` / `market_snapshot` 不再被传入 `sec_search_filings`。
  - `8k_commentary` 默认收敛到 `company_authored_unaudited_sec_filing`，其他 SEC 文本 route 默认走 `primary_sec_filing + company_authored_unaudited_sec_filing`。
- 提升 Specialist LLM 稳定性：
  - 在 `src/sec_agent/specialist_llm.py` 把默认 `SPECIALIST_MAX_TOKENS` 提高到 `2000`。
  - 收紧 Specialist prompt：输出必须是 compact `SpecialistMemolet` JSON，最多 3 条 observation / unsupported / conflict，禁止 markdown/prose。
  - `scripts/eval_multi_agent_real_llm_chain.py` 同步默认 specialist token budget。
- 修复 Research Lead sector-depth / relationship route 漏激活：
  - 在 `src/sec_agent/research_lead_llm.py` 增加 source-contract 后处理。
  - 当 query contract / source inventory 明确包含 `relationship_graph`，或 `industry_snapshot + sector-depth` 意图时，即使 LLM 返回 `standard_memo`，也会归一化为 `deep_research` 并激活 `universe_relationship`、SEC/8-K/market/industry operators、四类 specialists、memo/verifier/renderer。
  - Research Lead prompt 的 evidence route hint 补充 `relationship_graph`。
- 新增/更新测试：
  - `tests/test_multi_agent_operator_permissions.py`
  - `tests/test_multi_agent_research_lead_llm.py`
  - 相关 eval / specialist tests 继续通过。

## Verification

静态与单测：

```text
python -m pytest tests/test_multi_agent_operator_permissions.py tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_real_llm_chain_eval.py -q
result: 19 passed

python -m pytest tests/test_multi_agent_research_lead_llm.py tests/test_multi_agent_activation_plan.py tests/test_multi_agent_operator_permissions.py tests/test_multi_agent_real_llm_chain_eval.py -q
result: 31 passed

python -m compileall src/sec_agent/research_lead_llm.py src/sec_agent/multi_agent_runtime.py src/sec_agent/specialist_llm.py scripts/eval_multi_agent_real_llm_chain.py
result: pass
```

真实 DeepSeek + CUDA BGE full-chain：

```text
python -u scripts/eval_multi_agent_real_llm_chain.py --run-id 20260531_step17_full_chain_ai_infra_cuda_deepseek_v0_6 --case-id ma_real_sector_ai_infra_full_chain_real_retrieval --real-evidence-operators --bge-device cuda --specialist-max-tokens 2200 --strict
```

结果：

- gate: `pass`
- cases: `1/1`
- total tool calls: `10`
- real specialist evidence quality: `1/1`
- SEC search calls: `5`
- SEC search errors: `0`
- BGE candidates sent: `80`
- CUDA reported by runtime: `true`
- activated tool agents: `universe_relationship`, `sec_operator`, `eight_k_operator`, `market_operator`, `industry_operator`
- all specialists: `pass`

```text
python -u scripts/eval_multi_agent_real_llm_chain.py --run-id 20260531_step17_full_chain_sector_depth_cuda_deepseek_v0_2 --case-id ma_real_sector_banking_full_chain_real_retrieval --case-id ma_real_sector_healthcare_full_chain_real_retrieval --case-id ma_real_sector_energy_utilities_full_chain_real_retrieval --real-evidence-operators --bge-device cuda --specialist-max-tokens 2200 --strict
```

结果：

- gate: `pass`
- cases: `3/3`
- total tool calls: `30`
- real specialist evidence quality: `3/3`
- banking: `deep_research`, SEC calls `4`, SEC errors `0`, BGE candidates sent `52`, CUDA `true`
- healthcare: `deep_research`, SEC calls `6`, SEC errors `0`, BGE candidates sent `76`, CUDA `true`
- energy/utilities: `deep_research`, SEC calls `4`, SEC errors `0`, BGE candidates sent `60`, CUDA `true`
- all three cases activated `universe_relationship`, `sec_operator`, `eight_k_operator`, `market_operator`, `industry_operator`
- all required Specialist quality checks passed.

## Key Evidence Paths

- AI infra run summary:
  - `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/20260531_step17_full_chain_ai_infra_cuda_deepseek_v0_6/real_chain_eval_summary.json`
- Cross-sector run summary:
  - `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/20260531_step17_full_chain_sector_depth_cuda_deepseek_v0_2/real_chain_eval_summary.json`
- Case-level ledgers:
  - `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/20260531_step17_full_chain_ai_infra_cuda_deepseek_v0_6/*/real_chain_case_score.json`
  - `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/20260531_step17_full_chain_sector_depth_cuda_deepseek_v0_2/*/real_chain_case_score.json`
- Model run ledger:
  - `reports/model_runs/20260531_multi_agent_step17_full_chain_real_retrieval_deepseek_v0_1.md`

## Result

Step17 full-chain real retrieval / Specialist evidence quality gate 当前通过。BGE 不是未拉起；本轮真实 runs 的 runtime summary 显示 `bge_device=cuda`、`cuda_available=true`，且各 sector case 均有 `candidate_sent_to_bge > 0`。

## Follow-up

- 扩展真实 multi-turn 到 non-contiguous follow-up、artifact inspection、context compression 和 resumed graph state。
- 把 Step17 full-chain eval summary 的 runtime ledger 审计字段继续产品化到 Workbench UI。
- 后续若要把 diagnostic-only 提升为 mainline gate，需要冻结 fixture 版本、token budgets、source artifact versions 和 pass/fail 阈值。
