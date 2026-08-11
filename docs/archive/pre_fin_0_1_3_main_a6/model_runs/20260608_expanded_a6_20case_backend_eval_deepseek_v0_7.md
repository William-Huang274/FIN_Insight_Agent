# Model Run: 20260608_expanded_a6_20case_backend_eval_deepseek_v0_7

## Summary

- Purpose: Close out Expanded A6 Workbench backend full-chain evaluation over the 20-case scope-decision / gap-escalation / full-chain fixture.
- Status: accepted diagnostic gate, `20/20` accepted cases pass.
- Run type: inference evaluation roll-up from accepted cloud artifacts plus targeted reruns.
- Timestamp: 2026-06-08, cloud run artifacts generated on new 4090D cloud.
- Environment: `/autodl-fs/data/fin_agent_milvus_bge_m3`, Workbench backend `127.0.0.1:8775`, resident worker `127.0.0.1:8765`, 60GB RAM, 4090D, Milvus Lite resident path, BGE reranker CUDA where applicable.

## Code And Command

- Entry points:
  - Workbench backend `/api/evals/run`
  - `expanded_a6_full_chain_main`
  - `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`
- Cloud targeted rerun job IDs:
  - `20260608_a6_20case_backend_w08r1_scope_nvda_non_us_gap_memo_gapfix`
  - `20260608_a6_20case_backend_w09_sector_perf_hotcache_pair`
- Local verification after patch:
  - `python -m pytest -q tests\test_multi_agent_memo_llm_repair.py tests\test_multi_agent_contracts.py tests\test_multi_agent_real_llm_chain_eval.py tests\test_workbench_expanded_a6_eval.py`
  - Result: `77 passed in 4.18s`
- Git state: dirty worktree on `codex/expanded-a6-workbench-eval`; this ledger records run evidence only and does not imply staging/commit.

## Inputs

- Case fixture: `tests/fixtures/fin_agent_full_chain_multiturn_cases_v0_1.jsonl`
- Data profile: expanded Tier1+Tier2 source assets, 603-company source inventory, combined ledger, expanded market/industry catalogs, relationship graph packs, Milvus typed semantic recall collection.
- LLM: DeepSeek API via transient runtime environment.
- Retrieval: SEC BM25/ObjectBM25/BGE rerank, exact-value ledger, market snapshot, industry snapshot, relationship graph, Milvus typed semantic recall for explicit route cases.

## Results

| # | case_id | category | status | elapsed_s | tokens | tools |
|---:|---|---|---:|---:|---:|---:|
| 1 | fin_full_exact_msft_capex_zh | exact_lookup | pass | 4.7 | 0 | 2 |
| 2 | fin_full_exact_jpm_credit_provision_zh | exact_lookup | pass | 4.8 | 0 | 2 |
| 3 | fin_full_focused_amzn_margin_management_zh | focused_answer | pass | 59.0 | 30510 | 2 |
| 4 | fin_full_focused_healthcare_lly_rnd_zh | focused_answer | pass | 129.7 | 20869 | 4 |
| 5 | fin_full_standard_nvda_amd_market_zh | standard_memo | pass | 84.9 | 46226 | 4 |
| 6 | fin_full_standard_jpm_bac_deposit_credit_zh | standard_memo | pass | 144.4 | 41621 | 4 |
| 7 | fin_full_standard_xom_cvx_energy_zh | standard_memo | pass | 148.4 | 41885 | 6 |
| 8 | fin_full_standard_wmt_tgt_consumer_zh | standard_memo | pass | 150.3 | 41197 | 6 |
| 9 | fin_full_sector_ai_infra_depth_zh | sector_depth | pass | 274.4 | 70086 | 11 |
| 10 | fin_full_sector_banking_depth_zh | sector_depth | pass | 248.7 | 60197 | 10 |
| 11 | fin_full_sector_healthcare_depth_zh | sector_depth | pass | 331.1 | 63777 | 10 |
| 12 | fin_full_sector_utilities_power_depth_zh | sector_depth | pass | 298.9 | 78533 | 12 |
| 13 | fin_full_english_msft_googl_ai_capex_en | standard_memo | pass | 170.3 | 52050 | 6 |
| 14 | fin_full_mt_semis_scope_t1 | multi_turn | pass | 87.3 | 31715 | 6 |
| 15 | fin_full_mt_semis_scope_t2 | multi_turn | pass | 193.2 | 70549 | 12 |
| 16 | fin_full_mt_banking_t1 | multi_turn | pass | 158.9 | 58225 | 5 |
| 17 | fin_full_mt_banking_t2 | multi_turn | pass | 96.6 | 31286 | 4 |
| 18 | fin_full_scope_nvda_basic_fundamental_zh | scope_decision | pass | 128.4 | 37125 | 6 |
| 19 | fin_full_scope_nvda_ai_supply_chain_readthrough_zh | scope_decision | pass | 217.4 | 66098 | 15 |
| 20 | fin_full_scope_nvda_non_us_supply_chain_gap_zh | scope_decision | pass | 174.7 | 63982 | 9 |

Aggregate:

- Accepted pass rate: `20/20`
- Max accepted case elapsed: `331.1s`
- Average accepted case elapsed: `155.3s`
- Total accepted LLM tokens: `905,931`
- Average tokens per case: `45,296.55`

## Fixes During This Run

- Fixed Memo Writer structured gap preservation:
  - `src/sec_agent/memo_llm.py` now merges `evidence_gap_requests` from deterministic memo base into normalized LLM memo output.
  - This fixed `scope_gap_contract.gap_requests_preserved_to_memo` for `fin_full_scope_nvda_non_us_supply_chain_gap_zh`.
- Verified hot-cache sector-depth performance:
  - `fin_full_sector_banking_depth_zh`: `248.7s`, pass.
  - `fin_full_sector_utilities_power_depth_zh`: `298.9s`, pass.

## Artifact References

- `reports/quality/workbench_eval/20260608_a6_20case_backend_w08r1_scope_nvda_non_us_gap_memo_gapfix_expanded_a6_full_chain_main.json`
- `reports/quality/workbench_eval/20260608_a6_20case_backend_w09_sector_perf_hotcache_pair_expanded_a6_full_chain_main.json`
- Prior accepted A6 artifacts:
  - `20260608_expanded_a6_4case_prewarm_device_fixed_smoke_v0_14`
  - `20260608_a6_20case_backend_w01c_exact_jpm`
  - `20260608_a6_20case_backend_w01c_focused_amzn`
  - `20260608_a6_20case_backend_w02_focused_lly`
  - `20260608_a6_20case_backend_w02r1_standard_jpm_bac_hotcache`
  - `20260608_a6_20case_backend_w03r2_standard_xom_cvx_active_skip_fix`
  - `20260608_a6_20case_backend_w03_standard_wmt_tgt`
  - `20260608_a6_20case_backend_w04_english_msft_googl`
  - `20260608_a6_20case_backend_w05_mt_semis_pair`
  - `20260608_a6_20case_backend_w06r1_mt_banking_pair_focused_fix`
  - `20260608_a6_20case_backend_w07_sector_healthcare`
  - `20260608_a6_20case_backend_w08_scope_nvda_supply_chain`

## Interpretation

The A6 expanded backend chain is now functionally usable as an accepted diagnostic gate. It demonstrates that Research Lead can decide scope, Universe can inspect bounded relationship/source inventory, explicit Milvus semantic recall can enter the chain, Specialists can emit gap escalation, and Memo/Renderer can preserve hypothesis-only and source-gap boundaries.

The result should not be overstated as serving-ready production performance. Sector-depth remains expensive and cache-sensitive, and current Milvus Lite is not a GPU ANN index. GPU Milvus server or FAISS-GPU sidecar remains a separate performance project.

## Safety Notes

- No API key, SSH password, raw LLM response, or secret was saved.
- Roll-up uses accepted artifacts instead of a single all-20 rerun because the cloud data disk was at about `97%` used with roughly `6.3GB` free.
