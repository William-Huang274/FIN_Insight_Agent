# P30 AI/Semis Full-Chain Product Experience Smoke

Date: 2026-07-01

Scope: after P30 Workbench product-surface redesign, run 1-2 AI/Semis full-chain cases with real evidence operators and DeepSeek-backed LLM calls. This log records actual product experience and surfaced defects. It is not a release acceptance record.

## Frontend Follow-Up Recorded Before Run

The following P30 frontend debts were added to `061_p30_workbench_product_surface_redesign_followup.md` and checklist:

- Dense real-task layout has not been validated with full-chain task data.
- Evidence / graph visualization is still missing.
- Inline annotation and review workflow remain prototype-level.
- Unified design system is not complete.
- Analyst-facing hierarchy and ops/admin drilldown still need separation with real artifacts.

## Cases Run

Dry-run first confirmed the two selected cases resolve correctly from `tests/fixtures/fin_agent_vnext_50_case_catalog_v0_1.json`.

### Case 1: NVDA / DELL AI Infrastructure

- Case id: `fin_deep_ai_infra_nvda_dell_capex_023`
- Run id: `20260701_ai_semis_p30_full_chain_nvda_dell_r0`
- Command mode: `--real-evidence-operators --strict`
- Runner result: `gate_status=pass`, `diagnostic_only=true`
- Elapsed: `544255 ms`
- Tool calls: `12`
- Evidence rows in run audit: `453`
- Claim cards in run audit: `39`
- Output quality audit flags: `high_total_token_cost`, `memo_writer_high_token_cost`, `low_rendered_claim_token_efficiency`, `low_claim_card_token_efficiency`, `low_memo_chars_per_token`
- Token count reported by audit: `243606`
- Main artifacts:
  - `eval/sec_cases/outputs/p30_ai_semis_full_chain_smoke/20260701_ai_semis_p30_full_chain_nvda_dell_r0/real_chain_eval_summary.json`
  - `eval/sec_cases/outputs/p30_ai_semis_full_chain_smoke/20260701_ai_semis_p30_full_chain_nvda_dell_r0/fin_deep_ai_infra_nvda_dell_capex_023/qwen/rendered_answer.md`
  - `eval/sec_cases/outputs/p30_ai_semis_full_chain_smoke/20260701_ai_semis_p30_full_chain_nvda_dell_r0/fin_deep_ai_infra_nvda_dell_capex_023/run_audit_materialization_report.json`

Observed product defects:

- `direct_answer` still leaks raw numeric facts such as `AMZN 的资本开支（151003、2026）` and `DELL 的收入（60.0、2026）`; later sections format some values as USD billions, but the opening is not user-ready.
- A key argument sentence says `DELL的AI优化服务器收入在2026财年达到 [C10]` with the value missing before the citation.
- Chinese rendering still has punctuation artifacts such as `将；NVDA` and `量化；NVDA`.
- The case passed readability and investment-quality gates even with the missing-value sentence and raw-number opening. Current gates are not strict enough for product-grade output.
- Typed gaps include `missing_required_ticker_claim_card` and a live public web context commercial/proxy gap. The report exposes some gaps, but the final answer still reads like a draft rather than an analyst-ready workpaper.

### Case 2: ASML / AMAT / LRCX / KLAC Semicap Cycle

- Case id: `fin_deep_semicap_asml_amat_lrcx_klac_cycle_025`
- Run id: `20260701_ai_semis_p30_full_chain_semicap_r0`
- Command mode: `--real-evidence-operators --strict`
- Runner result: `gate_status=pass`, `diagnostic_only=true`
- Elapsed: `437991 ms`
- Tool calls: `12`
- Evidence rows in run audit: `442`
- Claim cards in run audit: `24`
- Output quality audit flags: `high_total_token_cost`, `memo_writer_high_token_cost`, `low_rendered_claim_token_efficiency`, `low_claim_card_token_efficiency`, `low_memo_chars_per_token`
- Token count reported by audit: `212322`
- Main artifacts:
  - `eval/sec_cases/outputs/p30_ai_semis_full_chain_smoke/20260701_ai_semis_p30_full_chain_semicap_r0/real_chain_eval_summary.json`
  - `eval/sec_cases/outputs/p30_ai_semis_full_chain_smoke/20260701_ai_semis_p30_full_chain_semicap_r0/fin_deep_semicap_asml_amat_lrcx_klac_cycle_025/qwen/rendered_answer.md`
  - `eval/sec_cases/outputs/p30_ai_semis_full_chain_smoke/20260701_ai_semis_p30_full_chain_semicap_r0/fin_deep_semicap_asml_amat_lrcx_klac_cycle_025/run_audit_materialization_report.json`

Observed product defects:

- `direct_answer` leaks raw numeric facts: `AMAT 的资本开支（1281、2026）`, `KLAC 的收入（1743504.0、2026）`, `AMAT 的收入（14922.0、2026）`.
- The final memo says `ASML、LRCX 的财务数据缺失`, while `pre_memo_fact_selection.json` contains approved LRCX revenue/capex facts. This is a planner/writer evidence-selection mismatch, not a true public-source absence.
- ASML official issuer and 6-K filing presence are detected, but ASML financial/order/backlog facts do not enter the final memo. That is either non-US / FPI filing parser depth gap, route gating gap, or claim selection gap; it should not be hidden by a case-level pass.
- The case question explicitly asks orders/backlog, shipment cycle, customer concentration, export restrictions and competition. The answer mostly falls back to AMAT/KLAC financial/product rows plus relationship-scope hypotheses, then lists missing ASML/LRCX/order/export data. For this research task, that is materially incomplete.
- The case passes investment-quality gate despite high token cost, core ticker evidence absence, and missing semicap-specific thesis depth. The eval gate is too tolerant.

## Runtime / Workbench Integration Issue

Both cases materialized run-audit SQLite stores with complete tables, but the `--run-audit-db-path data/workbench_private/run_audit/...sqlite` argument was resolved under each case artifact directory:

- `.../fin_deep_ai_infra_nvda_dell_capex_023/data/workbench_private/run_audit/20260701_ai_semis_p30_full_chain_nvda_dell_r0_run_audit.sqlite`
- `.../fin_deep_semicap_asml_amat_lrcx_klac_cycle_025/data/workbench_private/run_audit/20260701_ai_semis_p30_full_chain_semicap_r0_run_audit.sqlite`

The intended repository-level paths under `data/workbench_private/run_audit/` were not created. This means the CLI eval run is auditable in its artifact folder, but it is not yet a clean Workbench runtime task projection path. Product experience still feels like "run a diagnostic script and inspect files", not "open Workbench and review a live task".

## Real Product Experience

What works:

- Full-chain AI/Semis cases can activate the upgraded graph: Research Lead, evidence operators, specialists, LeadReview-style repair, ClaimCards, JudgmentState, Memo Writer, verifier and renderer.
- Real evidence operators run, not dry-run placeholders.
- SQL audit artifacts are materialized with node, artifact, retrieval, tool, evidence, claim, gap, gate and model-call tables.
- Product intelligence runtime is enabled for both AI/Semis cases.

What is not product-grade yet:

- The CLI result says `pass`, but both runs are `diagnostic_only=true`; this must not be treated as PRD-level acceptance.
- Output quality still has visible analyst-facing defects: raw numbers, missing values, punctuation artifacts, weak opening judgment and semicap-specific evidence gaps.
- The evaluation system catches token inefficiency but does not fail obvious memo correctness/readability defects.
- Workbench P30 UI was not fed by these real task artifacts automatically. The user still cannot naturally start from the frontend, drill into this exact run, inspect evidence graph, annotate a claim, and approve/repair.
- Token cost is high for the amount of final insight: roughly `212k-244k` tokens per case with only `3k-6k` rendered answer chars. The system needs stronger dynamic routing, compression and writer input discipline before broad 20-50 case runs.

## Follow-Up Blockers Before Broader Full-Chain Eval

- `P30-FC01`: make run-audit DB path resolution absolute/repo-root aware or add a formal artifact-to-Workbench import step.
- `P30-FC02`: block raw numeric display in `direct_answer`; require display-value lineage before writer sees numeric facts.
- `P30-FC03`: add a missing-value sentence gate for claims like "收入达到 [C10]" with no amount.
- `P30-FC04`: fix semicap FPI/non-US/local disclosure route or claim-selection path so ASML/LRCX available filings/facts are not lost.
- `P30-FC05`: upgrade investment-quality eval to fail high-priority case outputs that miss core requested dimensions or over-rely on relationship-scope hypotheses.
- `P30-FC06`: project full-chain artifacts into Workbench P30 so dense-task layout, evidence graph, annotation and review can be tested on real tasks.

## Decision

Do not run broad 20-50 case full-chain yet. The next step should be root-cause repair on formatter/eval/evidence-selection/Workbench-projection issues using deterministic or one-case regression tests first.
