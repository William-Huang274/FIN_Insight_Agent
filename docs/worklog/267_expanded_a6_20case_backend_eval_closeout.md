# 267 Expanded A6 20-Case Backend Eval Closeout

## Prompt

用户询问新云端是否卡住，并要求继续 A6 backend / eval 测试。新云端为 60GB RAM + 4090D，数据和环境已迁移；当前目标是用 Workbench backend、resident SEC/Milvus worker、DeepSeek real LLM 和 expanded 603-company assets 收口 A6 20-case scope-decision / gap-escalation / full-chain eval。

## Decision

- 云端进程未卡死：Workbench backend `127.0.0.1:8775` 和 resident worker `127.0.0.1:8765` 均健康，resident 已缓存 Milvus client、BGE reranker/model 和 SEC manifest。
- 不做一次性 all-20 重跑：`/autodl-fs/data` 仅剩约 `6.3GB`，重复生成完整 artifacts 风险高；改用 accepted baseline + targeted rerun 的 roll-up。
- 第 20 个 non-US supply-chain gap case 的质量失败不是 RAG/Universe 判断失败，而是 Memo Writer LLM normalize 路径没有把 `judgment_plan.evidence_gap_requests` 结构化透传到 `memo_answer.evidence_gap_requests`。

## Work Completed

- 修复 `src/sec_agent/memo_llm.py`：
  - `_normalize_memo_llm_output(...)` 强制从 deterministic memo base 合并 `evidence_gap_requests`，即使模型输出空 list 也保留 Judgment / Specialist 的 gap escalation contract。
  - 新增 `_merge_memo_evidence_gap_requests(...)`，按 request type、owner、source family、blocking level、ticker、metric 去重。
- 新增单测：
  - `tests/test_multi_agent_memo_llm_repair.py::test_memo_writer_llm_preserves_judgment_evidence_gap_requests_when_model_omits_them`
- 本地验证：
  - `python -m pytest -q tests\test_multi_agent_memo_llm_repair.py tests\test_multi_agent_contracts.py tests\test_multi_agent_real_llm_chain_eval.py tests\test_workbench_expanded_a6_eval.py`
  - 结果：`77 passed in 4.18s`
- 云端同步：
  - `src/sec_agent/memo_llm.py`
  - `tests/test_multi_agent_memo_llm_repair.py`
- 云端 targeted rerun：
  - `20260608_a6_20case_backend_w08r1_scope_nvda_non_us_gap_memo_gapfix_expanded_a6_full_chain_main`
  - `fin_full_scope_nvda_non_us_supply_chain_gap_zh` passed `1/1`
  - `scope_gap_contract.gap_requests_preserved_to_memo=true`
  - `performance.case_elapsed_ms_lte=true`
- 云端 sector-depth hot-cache rerun：
  - `20260608_a6_20case_backend_w09_sector_perf_hotcache_pair_expanded_a6_full_chain_main`
  - `fin_full_sector_banking_depth_zh` and `fin_full_sector_utilities_power_depth_zh` passed `2/2`

## Result

A6 20-case accepted roll-up is now `20/20 pass`.

- Accepted case count: `20/20`
- Max accepted case elapsed: `331.1s` (`fin_full_sector_healthcare_depth_zh`)
- Average accepted case elapsed: `155.3s`
- Total accepted LLM tokens: `905,931`
- Average tokens per case: `45,296.55`
- Exact lookup cases use deterministic bypass and report `0` LLM tokens.
- Deep sector cases remain token-heavy but pass current gates under warm resident/cache conditions.

## Accepted Artifact Set

- 4-case baseline: `20260608_expanded_a6_4case_prewarm_device_fixed_smoke_v0_14`
- Exact/focused/standard remaining runs:
  - `20260608_a6_20case_backend_w01c_exact_jpm`
  - `20260608_a6_20case_backend_w01c_focused_amzn`
  - `20260608_a6_20case_backend_w02_focused_lly`
  - `20260608_a6_20case_backend_w02r1_standard_jpm_bac_hotcache`
  - `20260608_a6_20case_backend_w03r2_standard_xom_cvx_active_skip_fix`
  - `20260608_a6_20case_backend_w03_standard_wmt_tgt`
  - `20260608_a6_20case_backend_w04_english_msft_googl`
- Multi-turn accepted runs:
  - `20260608_a6_20case_backend_w05_mt_semis_pair`
  - `20260608_a6_20case_backend_w06r1_mt_banking_pair_focused_fix`
- Sector/scope closeout runs:
  - `20260608_a6_20case_backend_w07_sector_healthcare`
  - `20260608_a6_20case_backend_w08_scope_nvda_supply_chain`
  - `20260608_a6_20case_backend_w08r1_scope_nvda_non_us_gap_memo_gapfix`
  - `20260608_a6_20case_backend_w09_sector_perf_hotcache_pair`

## Follow-Up

- A6 expanded path can be treated as an accepted backend diagnostic gate, but not yet as default production route until Git/worktree scope is staged and mainline merge strategy is decided.
- Milvus Lite remains resident but CPU-index based; do not claim CUDA vector-search acceleration until Milvus GPU server or FAISS-GPU sidecar is evaluated.
- Cost/latency work remains valuable: sector-depth cases consume `60K-78K` tokens each and are sensitive to provider latency and cache warmth.
- No secrets or raw LLM responses were saved.
