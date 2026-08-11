# 307 Run Audit Store And vNext Full-Chain Smoke

Date: 2026-06-13

## Context

本轮目标是先补运行记录底座，再按升级后的 agent graph / skill / 数据覆盖重新设计 full-chain smoke 评测维度，先跑 1-2 个全链路激活 case 检查各环节。运行记录必须以 SQL store 作为最终审计源，Redis 只允许做异步协作状态。

## Implemented

- 新增 `sec_agent_run_audit_store_v0.1` SQLite store。
  - 表：`run`、`node_execution`、`artifact_ref`、`evidence_row`、`claim_card`、`gap`、`gate_result`、`model_call`。
  - 每张表都有 `run_id`、`case_id`、`node`、`input_digest`、`output_digest`、`code_commit`、`data_snapshot_id`、`artifact_uri`。
  - policy 固定为 `sqlite_is_final_audit_source_redis_coordination_only_v0_1`。

- 接入 graph persist。
  - `SecAgentGraphRuntimeState` 增加 `case_id`、`run_audit_db_path`、`run_audit_materialization_report`。
  - multi-agent 和 native persist 都会在落 artifact 时物化 run audit store，并写出 `run_audit_materialization_report.json`。
  - 修复 LangGraph state 丢失 `case_id` 后 audit report 用 `run_id` 推断 case 的问题。

- 接入 eval runner 和 Workbench backend。
  - `eval_multi_agent_real_llm_chain.py` 新增 `--run-audit-db-path`，并在 scoring 中加入 run-audit gate、dimension memo surface gate、analyst-depth gate。
  - Workbench 新增 `agent_graph_vnext_run_audit_smoke`，默认跑 2 个 full-chain activation cases，并写 `reports/quality/workbench_eval/*_agent_graph_vnext_run_audit_smoke.json`。

- 新增 2-case fixture：`fin_agent_vnext_run_audit_full_chain_cases_v0_1.jsonl`。
  - AI infrastructure sector-depth：要求 NVDA/DELL/ANET/VRT + MSFT/AMZN/GOOGL capex 背景，激活 relationship、SEC、8-K、market、industry、五类 specialist、memo/verifier/renderer，并按基本面、产品产线、投融资/资本开支、行业供应链、竞争位置、风险反证输出。
  - AAPL product tracker gap：要求 AAPL iPhone/Mac/Services 的公司披露产品证据与商业 tracker gap 边界，禁止 universe_relationship 和 industry_supply_chain_analyst。

## Fixes Found By Smoke

- `20260613_workbench_run_audit_smoke_latest_r0` 先跑出 `1/2 pass`。
  - run-audit store 全部通过。
  - 失败点是 AI infrastructure case 的 `analyst_depth.required_dimensions_present`：模型/证据组合只产出产品、行业、竞争、风险，没有把用户显式要求的基本面和投融资/资本开支作为维度 section。

- 修复方式不是放松 gate。
  - eval case 的 `required_dimension_ids` 进入 query contract。
  - graph 从 query contract / context / 用户文本中抽取 required dimensions。
  - `thesis_driver_pack` 对缺失的 required dimension 生成 `required_dimension_missing_verified_evidence` gap-only section，不制造 proxy fact。
  - verifier 对 `required_by_user` 的 section 做全量携带检查。
  - Memo Writer normalization 的 dimension 上限提升到 8，避免 deep/expanded case 的 6 个显式维度加综合项被截断。

## Latest Full-Chain Result

Workbench backend run:

- Run ID: `20260613_workbench_run_audit_smoke_latest_r1`
- Summary path: `reports/quality/workbench_eval/20260613_workbench_run_audit_smoke_latest_r1_agent_graph_vnext_run_audit_smoke.json`
- Source summary: `eval/sec_cases/outputs/multi_agent_vnext_run_audit_smoke_eval/20260613_workbench_run_audit_smoke_latest_r1/real_chain_eval_summary.json`
- Result: `2/2 pass`

Case results:

- `fin_run_audit_ai_infra_capex_dimension_zh`
  - Gate: pass
  - Tool calls: `12`
  - Memo dimensions: `capital_and_financing`、`competition_and_market_position`、`fundamentals`、`industry_supply_chain`、`product_and_production`、`risk_and_counterevidence`、`thesis_synthesis`
  - Rendered answer chars: `6463`
  - Run-audit counts: `run=1`、`node_execution=20`、`artifact_ref=23`、`evidence_row=395`、`claim_card=16`、`gap=11`、`gate_result=953`、`model_call=5`

- `fin_run_audit_aapl_product_tracker_gap_zh`
  - Gate: pass
  - Tool calls: `7`
  - Memo dimensions: `competition_and_market_position`、`fundamentals`、`product_and_production`、`risk_and_counterevidence`、`thesis_synthesis`
  - Rendered answer chars: `3894`
  - Run-audit counts: `run=1`、`node_execution=16`、`artifact_ref=23`、`evidence_row=144`、`claim_card=10`、`gap=11`、`gate_result=403`、`model_call=3`

Note: the subprocess was launched through Workbench. My temporary monitor process failed while printing a non-GBK event string, so the child evaluation process finished normally but the Workbench job row was left as `running`; I repaired that one row from the completed summary artifact. This does not affect the eval output artifacts or run-audit DB.

## Verification

- `python -m py_compile src/sec_agent/multi_agent_contracts.py src/sec_agent/langgraph_orchestrator.py src/sec_agent/memo_llm.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`
- `python -m pytest -q tests/test_multi_agent_contracts.py tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_judgment_memo_verifier.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_run_audit_store.py tests/test_workbench_job_runner.py tests/test_workbench_backend.py`
  - Result: `151 passed`

## Boundary

- Generated full-chain outputs, workbench reports, SQLite DBs, and private Workbench store rows remain runtime artifacts and should not be staged by default.
- Milvus remains a semantic recall supplement. This smoke does not require rebuilding the previous cloud Milvus collection and does not promote semantic rows to exact-value authority.
- The next step can move from 2-case smoke to a broader G11-style full-chain batch only after deciding the token/API budget for a larger run.
