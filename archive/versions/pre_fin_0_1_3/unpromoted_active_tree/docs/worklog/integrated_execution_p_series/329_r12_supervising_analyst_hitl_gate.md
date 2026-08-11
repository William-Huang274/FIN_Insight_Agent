# 329 R12 Supervising Analyst Pack / HIL Gate

## Prompt

用户指出当前 full-chain memo 虽然表面格式改善，但有用 insight 密度仍低；产品、投融资、财务分析、供应链关系图都偏浅，投资含义更像“教用户怎么判断”而不是 agent 自己形成判断。用户要求先修这些问题，再“把 Codex 替换成主 agent”，监督下游 agent 做一次 human-in-the-loop 测试，找出还有哪些问题以及怎么改。

## Work Completed

- Added `src/sec_agent/supervising_analyst.py`.
  - Builds deterministic `supervising_analyst_pack` before memo writing.
  - Converts existing approved public facts and verified ClaimCards into:
    - `financial_analysis_model`
    - `product_bridge_pack`
    - `capital_transmission_graph`
    - `research_lead_synthesis_plan`
    - `supervision_findings`
  - Keeps authority boundaries explicit: product pages/context can enrich taxonomy, but cannot promote sales/orders/share unless exact company-disclosed facts exist.
- Integrated the pack into `src/sec_agent/langgraph_orchestrator.py`.
  - Runs after Lead targeted repair and before `memo_writer`.
  - Persists `supervising_analyst_pack.json`.
  - Adds summary fields to `multi_agent_summary.json`.
  - Adds the state key to checkpoint/resume state.
- Updated `src/sec_agent/memo_llm.py`.
  - Memo Writer now receives a compact `supervising_analyst_pack`.
  - Prompt priority changed from MemoLogicPlan-first to ResearchLeadSynthesisPlan-first, then MemoLogicPlan, then verified ClaimCards.
  - Investment implications must state the agent's present judgment first, not a generic checklist.
- Updated `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`.
  - Adds a `supervising_analyst` eval layer for deep investment-quality cases.
  - Checks pack presence, financial model, product bridge, capital graph, synthesis plan, writer directives, and summary trace.
- Added `scripts/eval_multi_agent/run_supervising_analyst_hitl_audit.py`.
  - Reads completed case artifacts without invoking the model.
  - Rebuilds the supervising pack.
  - Writes per-case HIL reports and an aggregate audit summary.
  - Flags writer/downstream issues such as gap-dominant implications, missing rendered capital graph, unused derived ratios, missing balance-sheet backbone, and numeric display reconciliation needs.
- Added `tests/test_supervising_analyst_pack.py`.
  - Covers AI-infra capex/product readthrough and official product-context-only behavior.

## HIL Audit

- Input run:
  - `eval/sec_cases/outputs/multi_agent_vnext_r12_successor_12_eval/r12_product_output_web_repair_two_case_20260615_r22/`
- Output:
  - `reports/quality/supervising_analyst_hitl/20260615_r22_codex_supervisor/supervising_analyst_hitl_audit_summary.json`
  - `reports/quality/supervising_analyst_hitl/20260615_r22_codex_supervisor/supervising_analyst_hitl_audit_summary.md`
  - Per-case reports:
    - `eval/sec_cases/outputs/multi_agent_vnext_r12_successor_12_eval/r12_product_output_web_repair_two_case_20260615_r22/fin_deep_cloud_capex_msft_amzn_googl_supplier_026/codex_supervising_analyst_hil_report.md`
    - `eval/sec_cases/outputs/multi_agent_vnext_r12_successor_12_eval/r12_product_output_web_repair_two_case_20260615_r22/fin_deep_semicap_asml_amat_lrcx_klac_cycle_025/codex_supervising_analyst_hil_report.md`

## HIL Findings

- Both cases:
  - `investment_implication_not_judgment`: investment implications still read like procedural checklists, not current analyst judgment.
  - `capital_graph_not_rendered`: capital/supply-chain edges exist in the pack but are not rendered as a concrete relationship path/table.
  - `balance_sheet_missing`: Fundamental specialist did not promote balance-sheet rows into the financial backbone.
  - `numeric_display_choice_missing`: mixed period/unit rows need selected display values before writer.
- Cloud AI infra case:
  - `derived_financial_bridge_not_used`: DELL product mix/capex-to-revenue ratios are available but not used in the memo. The pack derived DELL AI-optimized server revenue at about 55.6% of Total ISG revenue from company-disclosed product rows; the rendered memo did not use this bridge.

## Verification

- `python -m py_compile src\sec_agent\supervising_analyst.py src\sec_agent\memo_llm.py src\sec_agent\langgraph_orchestrator.py scripts\eval_multi_agent\eval_multi_agent_real_llm_chain.py scripts\eval_multi_agent\run_supervising_analyst_hitl_audit.py`
- `pytest -q tests\test_supervising_analyst_pack.py tests\test_multi_agent_memo_llm_repair.py tests\test_multi_agent_real_llm_chain_eval.py tests\test_multi_agent_judgment_memo_verifier.py tests\test_multi_agent_contracts.py`
  - Result: `130 passed`.
- HIL script:
  - `python scripts\eval_multi_agent\run_supervising_analyst_hitl_audit.py --case-dir ...cloud... --case-dir ...semicap... --output-dir reports\quality\supervising_analyst_hitl\20260615_r22_codex_supervisor --write-pack-to-case-dir`
  - Result: `case_count=2`, status ok.

## Decision

- Research Lead should no longer be a one-shot dispatcher. It now has a deterministic pre-writer supervision object that can:
  - check whether downstream agent outputs satisfy the original research objective;
  - transform raw evidence/ClaimCards into analyst models;
  - provide the writer with a judgment-first plan;
  - expose targeted downstream repair needs before burning more full-chain tokens.
- The current issue is not only Memo Writer style. HIL shows upstream analyst pack quality gaps remain:
  - Fundamental specialist needs stronger three-statement and numeric-display reconciliation.
  - Industry/Supply-chain specialist needs explicit directed edge rendering contracts.
  - Product specialist must force product KPI/spec/mix/ordering evidence into the pack when publicly retrievable.

## Remaining

- Run a fresh 1-2 case smoke after Memo Writer consumes the new `supervising_analyst_pack` in a real model call.
- Add a renderer surface that can show `capital_transmission_graph.edges` as a compact relation path/table.
- Upgrade Fundamental specialist selector to prioritize balance sheet, cash flow, income statement, peer comparisons, and derived ratio display choices as normal output, not post-hoc audit.
- Extend Product specialist to emit a ProductBridgePack with product mix, product specs, order/backlog, and official product-context boundary.
