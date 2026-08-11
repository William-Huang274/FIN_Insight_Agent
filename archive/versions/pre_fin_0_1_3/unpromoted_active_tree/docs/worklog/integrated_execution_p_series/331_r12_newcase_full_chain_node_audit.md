# 331 R12 New Case Full-Chain Node Audit

## Prompt
- 用户要求用一个新 case 跑全链路，检查各节点效果。
- 选用 `fin_nonus_novo_lly_glp1_regulatory_046`，覆盖非美 issuer targeted repair、LLY SEC 财务表格、GLP-1 产品/监管/商业 tracker gap、Research Lead closed loop、specialist packs、memo/verifier、run audit。

## Fixes Before Accepted Run
- 修复 `financial_statement_analysis._infer_industry_id` 的行业匹配：优先读取 `industry_schema` / selected playbook，避免 `autos_ev` 的 `ev` 在 `revenue/evidence` 等词内误命中。
- 在 runtime SEC context 中补 table-to-ledger backfill：真实 SEC 表格 row 可以进入 `runtime_ledger_rows`，再进入 `FundamentalStatementPack`，不再只停留在 context rows。
- 修复 SEC 表格 period 解析：优先使用 table column / record period，避免 chunk fiscal year 把 2025 对比列误标为 2026。
- 修复 `FundamentalStatementPack.period_changes`：禁止对 `yoy_growth` 这种派生增长率继续二次计算 period change。
- 修复 LangGraph persist：把 `multi_agent_summary` payload 回填到返回 state，避免 eval 只能读文件、读不到 `supervising_analyst_pack` summary。
- 修复 eval runner：当 case 要求 `require_run_audit_store=true` 且 CLI 未显式传 `--run-audit-db-path` 时，默认给每个 case 注入 `data/workbench_private/run_audit/<run_id>.sqlite`。

## Runs
- `20260615_r12_newcase_novo_lilly_webrepair_r3_period_fix`: real evidence operators；只剩 `supervising_analyst.summary_tracks_pack` 失败；发现 summary state 未回填。
- `20260615_r12_newcase_novo_lilly_webrepair_r4_summary_state_period_change_fix`: 无效诊断；漏传 `--real-evidence-operators`，导致 SEC/market/industry operator 全为 `dry_run`，不作为质量结论。
- `20260615_r12_newcase_novo_lilly_webrepair_r5_realops_summary_state_period_fix`: real evidence operators；Research Lead / specialist / memo / supervising analyst 均通过，只剩 run audit 缺默认 DB path。
- `20260615_r12_newcase_novo_lilly_webrepair_r6_realops_audit_default_path`: accepted run；`gate_status=pass`。

## Accepted Run Evidence
- Run id: `20260615_r12_newcase_novo_lilly_webrepair_r6_realops_audit_default_path`
- Output root: `eval/sec_cases/outputs/multi_agent_vnext_single_case_eval/20260615_r12_newcase_novo_lilly_webrepair_r6_realops_audit_default_path/fin_nonus_novo_lly_glp1_regulatory_046`
- Overall: `1/1 pass`, `total_tool_calls=14`, elapsed about `332s`.
- Evidence rows: `context_row_count=30`, `runtime_ledger_row_count=309`, `market_snapshot_row_count=3`, `industry_snapshot_row_count=6`, `source_gap_count=4`.
- Research Lead: `core_question_answerable=true`; supported dimensions `4`; retrievable gap dimensions `2`; targeted repair attempted `2`, success `8`, bounded gap `1`.
- Fundamental pack: `35` line items, three-statement coverage, `12` period changes, `has_yoy_period_change=false`, industry policy `pharma_biotech_medtech`.
- Supervising analyst pack: pass; key line items `24`, product context `7`, capital edges `6`, writer directives `5`.
- Specialist real evidence: pass; fundamental analyst sees primary/company-authored SEC rows for LLY and records NVO source gaps; product analyst sees public/company product context; relationship/industry analyst uses healthcare sector-depth pack.
- Run audit: pass; SQLite DB materialized under case output; non-empty `run`, `node_execution`, `artifact_ref`, `evidence_row`, `claim_card`, `gate_result`, `model_call`; `redis_coordination_only=true`.
- Memo gates: surface readability pass; investment quality pass; gap sentence ratio `0.1154`.

## Manual Quality Finding
- Although the automated R12 gate passed, manual read of `rendered_answer.md` still finds memo-level issues that should not be considered fully research-grade:
  - Core judgment mixes source roles and says NVO product context “承接需求”，which overstates product-surface evidence.
  - Product section uses LLY operating/free cash flow as indirect product success evidence; this should be framed as financial confirmation, not product KPI proof.
  - Some key-argument sentences lose numeric values, e.g. revenue/capex wording becomes incomplete after rendering.
  - The memo can still sound like a bounded evidence report rather than a clear analyst judgment, even though it is much better than previous gap-ledger style outputs.
- Decision: current full-chain infrastructure and node connectivity are pass, but next memo/eval iteration should add stricter gates for incomplete numeric sentences, evidence-role misuse, and product-vs-financial proxy overreach.

## Verification
- `python -m pytest tests/test_financial_statement_analysis.py tests/test_multi_agent_runtime_sec_context_ledger.py tests/test_supervising_analyst_pack.py tests/test_multi_agent_real_llm_chain_eval.py::test_supervising_analyst_pack_gate_required_for_deep_investment_cases tests/test_multi_agent_real_llm_chain_eval.py::test_initial_state_adds_default_case_run_audit_path_when_required`
- Result: `9 passed`.
- Full-chain accepted command used real evidence operators and the 50-case catalog single-case selector; summary written to `reports/quality/workbench_eval/20260615_r12_newcase_novo_lilly_webrepair_r6_realops_audit_default_path.json`.

## Follow-Up
- Add memo/eval gates for:
  - incomplete numeric sentence rendering;
  - unsupported product causal bridge;
  - source-role language misuse such as treating issuer/product-surface context as sales proof;
  - claim text losing values during memo/render pipeline.
- Consider case-specific follow-up for non-US financial exact parser: NVO official sources are reachable, but exact financial/product KPI parsing remains bounded unless local exchange/company IR parser is implemented.
