# Agent Graph vNext G11 Full-chain Workbench Gate

日期：2026-06-13

## 触发

用户要求对当前已升级的 Agent Graph / Skill 做 G11 全链路验收，测试必须走 Workbench 后端，使用 DeepSeek API 路由，真实 evidence operators 本地执行。云端 Milvus 存在旧向量库，但本轮先不把 Milvus 下载成本地兜底；如果 G11 通过或修复后通过，再决定是否更新 Milvus。

## 通过条件

- Workbench eval id：`agent_graph_vnext_g11_full_chain`
- Fixture：`tests/fixtures/fin_agent_vnext_g11_cases_v0_1.jsonl`
- Case 数：`12`
- 覆盖：
  - exact lookup
  - focused answer
  - standard memo
  - sector-depth deep research
  - multi-turn scope revision
  - product/public evidence boundary
  - web/Milvus runtime boundary
  - bounded gap / no weak proxy fallback
  - graph barriers / specialist / memo / verifier contract
- Gate 不允许：
  - 用 public proxy 证明 exact company product sales / market share / sell-through。
  - 用 unavailable Milvus 当 exact authority。
  - 用 commercial tracker gap 的弱 proxy 兜底。
  - 用 raw private path / API key / runtime handle 写入 summary。

## 修复记录

本轮不是一次性通过，先后暴露并修复了这些 root cause：

- LLY focused case：pre-memo governance filter 已经拦截 stale / blocked facts，但 `memo_thesis_pack` 没有同步刷新，Memo Writer 仍可能复制被 blocked 的 claim。
  - 修复：治理过滤后刷新 `memo_outline`、`memo_thesis_plan`、`memo_thesis_pack`、claim card stats 和 source agent ids。
- AAPL consumer electronics：Research Lead 把 `company_product_evidence_graph` / `public_source_context` 这类 source family 名称误放进 `evidence_routes`。
  - 修复：把 source family 名称从 route 字段迁到 source family 字段，并按可执行 route 对齐 activation。
- CRM / SNOW SaaS：LLM 未给 web scope policy 却激活 live web / web operator。
  - 修复：没有显式 `web_scope_policy_ids` 时，把 live web 降为 bounded `public_source_context`，并移除 web operator。
- JPM / BAC、WMT / TGT：public source context 或 JSON key 中的 product 字样误触发 `product_technology_analyst`。
  - 修复：产品专家激活必须来自真实 product source family 或明确产品/技术意图；避免把字段名、`production`、commercial tracker gap 误判成产品任务。
- Milvus unavailable：fixture 允许 `milvus_semantic` source family，但本地 runtime 没有绑定云端或本地 Milvus。
  - 修复：当 source inventory 显式标记 Milvus unavailable 时，Research Lead 从 activation / evidence payload 移除 `milvus_semantic` route/source，并在 vNext contract 中保留 runtime boundary；Milvus 不进入 exact authority。
- AAPL relationship overroute：evidence payload 对齐后又把 `relationship_graph` / `universe_relationship` 加回非 relationship scope 请求。
  - 修复：relationship scope normalization 在 evidence alignment 后再次执行。
- Sector AI infra：产品专家被激活，但没有产品/public/live bounded rows 时，specialist quality gate 缺 product-owned input。
  - 修复：当 product/public/live source family 被请求但没有可物化行时，`AgentDataView` 暴露 bounded gap rows，而不是用 SEC/market proxy 填补。
- CRM / SNOW SEC search：本地 CUDA BGE reranker OOM 造成 `sec_search_filings` 空结果。
  - 修复：Workbench G11 eval 显式使用 CPU BGE rerank；仍要求真实 BM25 candidate、BGE rerank、context rows 和 runtime ledger rows，不放宽检索 gate。
- Multi-turn T2：Research Lead 的 evidence requirement 同时声明 product/public context source family 和 SEC/8-K operator routes，validator 把 context-only source 误判成 route-backed source mismatch。
  - 修复：`validate_multi_agent_evidence_requirement_plan()` 允许 `company_product_evidence_graph` / `public_source_context` 作为 context-only requirement source，但仍要求它们在 activation allowed sources 内；market/industry/relationship/Milvus 等 route-backed source mismatch 继续 fail。

## 最终结果

最终 Workbench run：

- Run id：`20260613_agent_graph_vnext_g11_full_chain_workbench_deepseek_v0_10`
- Trace：`trace_2cd0a5709e6a4764a270b920`
- Workbench summary：`reports/quality/workbench_eval/20260613_agent_graph_vnext_g11_full_chain_workbench_deepseek_v0_10_agent_graph_vnext_g11_full_chain.json`
- Output dir：`eval/sec_cases/outputs/multi_agent_vnext_g11_full_chain_eval/20260613_agent_graph_vnext_g11_full_chain_workbench_deepseek_v0_10`
- Result：`12/12` pass
- Workbench status：`completed`
- Elapsed：`875000 ms`

Case-level status：

- `fin_g11_exact_msft_capex_zh`: pass
- `fin_g11_focused_lly_product_cycle_zh`: pass
- `fin_g11_standard_nvda_amd_product_market_zh`: pass
- `fin_g11_standard_aapl_consumer_electronics_zh`: pass
- `fin_g11_standard_crm_snow_saas_zh`: pass
- `fin_g11_standard_jpm_bac_bank_zh`: pass
- `fin_g11_standard_xom_cvx_energy_zh`: pass
- `fin_g11_standard_tsla_f_auto_zh`: pass
- `fin_g11_standard_wmt_tgt_retail_zh`: pass
- `fin_g11_sector_ai_infra_deep_zh`: pass
- `fin_g11_mt_semis_scope_t1`: pass
- `fin_g11_mt_semis_scope_t2`: pass

## 测试

- `pytest -q tests\test_workbench_job_runner.py tests\test_workbench_backend.py`
  - `49 passed`
- `pytest -q tests\test_multi_agent_evidence_requirements.py tests\test_multi_agent_research_lead_llm.py`
  - `56 passed`
- Workbench full-chain G11：
  - `12/12` pass
- `python -m py_compile src\sec_agent\research_lead_llm.py src\sec_agent\multi_agent_runtime.py src\sec_agent\multi_agent_contracts.py src\sec_agent\d_series_fact_selection.py src\sec_agent\langgraph_orchestrator.py scripts\eval_multi_agent\eval_multi_agent_real_llm_chain.py src\sec_agent\workbench\job_runner.py`
  - pass
- Targeted regression：
  - `pytest -q tests\test_multi_agent_research_lead_llm.py tests\test_multi_agent_evidence_requirements.py tests\test_multi_agent_contracts.py tests\test_d_series_fact_selection.py tests\test_multi_agent_langgraph_routing.py tests\test_workbench_backend.py tests\test_workbench_job_runner.py tests\test_multi_agent_real_llm_chain_eval.py tests\test_multi_agent_operator_permissions.py tests\test_multi_agent_reflection_second_pass.py tests\test_multi_agent_specialist_llm.py`
  - `264 passed`
- Full regression：
  - `pytest -q`
  - `904 passed`
- `git diff --check`
  - pass

## Milvus 边界

本轮没有从云端下载或重建 Milvus，也没有把旧云端 Milvus 当本地 runtime 使用。G11 验证的是：

- Milvus runtime capability 能以 unavailable 状态进入 source inventory / vNext contract。
- unavailable Milvus 不会被 Research Lead 当作 evidence route 执行。
- Milvus semantic recall 不具备 exact-value authority。
- 本地缺 Milvus 不能被弱 proxy 或 public context 填补。

后续如果决定启用云端或拉本地 Milvus，需要单独跑 vector / graph memory parity gate，再决定是否重建最新 603 家公司向量库。
