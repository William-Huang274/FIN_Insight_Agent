# P24 B04 Product Acceptance Gate

Supersession note: this checkpoint still had B04/B05 open. The later P25/B05 closeout closed B05; current P21 has only B04 open.

2026-07-01 B04 hardening note: B04 can no longer close from P24 summary fields alone. P24 must derive real acceptance from `r53_r60_p24_b04_real_reviewer_acceptance_evidence_v0_1.jsonl`, human evidence rows, defect closeout rows, decision rows, and gate rows; P21 validates those manifests before closing B04.

2026-07-01 evidence entrypoint note: reviewer evidence no longer needs manual JSONL editing. Use the Workbench `Product acceptance evidence` panel, `POST /api/r53-r60/product-acceptance/evidence`, `GET /api/r53-r60/product-acceptance/evidence`, or `scripts/engineering/record_r53_r60_p24_b04_reviewer_acceptance_evidence.py`; all entrypoints call the same validated runtime append contract and reject automation/incomplete rows.

## Context

Continue the post-P23 enterprise-grade closeout. P23 proved the automated Workbench API/product journey and frontend build/source contracts, but B04 remained open because real reviewer product acceptance cannot be replaced by automation.

P24's scope is the product-acceptance infrastructure layer:

- real-browser Workbench visual E2E with screenshots;
- reviewer acceptance protocol;
- real-human evidence requirements;
- defect closeout requirements;
- P21 B04 observed-evidence ingestion.

P24 intentionally does not close B04 without a real reviewer session, accepted/rejected deliverable decisions and defect closeout.

## Implementation

Added runtime artifacts:

- `src/sec_agent/r53_r60_product_acceptance_b04_gate.py`
- `scripts/engineering/build_r53_r60_p24_b04_product_acceptance_gate.py`
- `tests/test_r53_r60_product_acceptance_b04_gate.py`

Updated:

- `apps/workbench/backend/app.py`: added `FINSIGHT_WORKBENCH_REPO_ROOT` override for isolated browser E2E roots while preserving the default repo-root behavior.
- `src/sec_agent/r53_r60_pre_full_chain_blocker_gate.py`: P21 now reads P24 summary. B04 closes only if P24 records `accepted_by_real_human_review`, `closed_by_real_human_product_acceptance`, and zero pending human/defect evidence.

Generated artifacts:

- `configs/r53_r60/p24_b04_product_acceptance_gate_schema_v0_1.json`
- `data/manifests/r53_r60_p24_b04_product_acceptance_protocol_rows_v0_1.jsonl`
- `data/manifests/r53_r60_p24_b04_browser_e2e_rows_v0_1.jsonl`
- `data/manifests/r53_r60_p24_b04_human_evidence_requirements_v0_1.jsonl`
- `data/manifests/r53_r60_p24_b04_defect_closeout_requirements_v0_1.jsonl`
- `data/manifests/r53_r60_p24_b04_acceptance_decision_rows_v0_1.jsonl`
- `data/manifests/r53_r60_p24_b04_product_acceptance_gate_rows_v0_1.jsonl`
- `data/manifests/r53_r60_p24_b04_product_acceptance_summary_v0_1.json`
- `docs/internal/vnext_20260610/r53_r60_p24_b04_product_acceptance_gate_human_pending.zh-CN.md`

Screenshot evidence is generated under `reports/r53_r60_p24_b04_product_acceptance_browser_e2e/` and is not committed unless explicitly requested.

## Root-Cause Fixes During B04

1. Uvicorn subprocess import path failed to find `sec_agent`.
   - Root cause: child process did not reliably inherit the repo `src` path.
   - Fix: launch uvicorn through a Python wrapper that explicitly inserts repo root and `src`.

2. Playwright registry did not contain downloaded Chromium.
   - Root cause: `playwright.chromium.executable_path` pointed to a missing browser.
   - Fix: resolve browser executable from Playwright Chromium first, then system Chrome/Edge.

3. SPA visual E2E used `networkidle` and per-label serial waits.
   - Root cause: Workbench has background API requests; `networkidle` and serial waits made the test brittle and slow.
   - Fix: use `domcontentloaded`, one-time body-label polling, and a single browser session resized from desktop to mobile.

4. Browser-context API request to `/api/r53-r60/pilot/actions` stalled after visual rendering.
   - Root cause analysis: standalone uvicorn HTTP probe returns the endpoint in ~26ms, so the product API is not the failing layer. The stall was caused by the probe ordering / Playwright context interaction after a full page visual load.
   - Fix: split acceptance into pre-browser server HTTP API probe plus real browser visual E2E. This preserves product API verification without manufacturing a false API defect from the test harness.

## Result

Real repo P24 build:

- `status=pass_with_real_human_acceptance_blocked`
- `release_decision=P24_b04_product_acceptance_infrastructure_ready_human_review_pending`
- `closeout_level=L4_scope_pass_for_product_acceptance_infrastructure_only`
- `browser_e2e_status=pass`
- `browser_e2e_count=10`
- `browser_e2e_fail_count=0/10`
- `gate_fail_count=0/7`
- `gate_blocked_count=2/7`
- `human_evidence_pending_count=5`
- `defect_closeout_pending_count=8`
- `product_acceptance_status=pending_real_human_acceptance`
- `b04_status_after_p24=open_product_acceptance_required`

P21 rerun after P24:

- `blocker_count_open=1/5`
- B04 observed evidence includes P24 summary.
- B04 remains open because real human reviewer acceptance is still pending.

## Verification

- `npm` was not on PATH, so the frontend was built through bundled Node:
  - `node node_modules/typescript/bin/tsc -p tsconfig.json`
  - `node node_modules/vite/bin/vite.js build --config vite.config.ts`
- `python -m pytest tests/test_r53_r60_product_acceptance_b04_gate.py tests/test_r53_r60_product_dogfood_frontend_e2e.py -q` -> `10 passed`
- `python -m pytest tests/test_workbench_backend.py::test_workbench_backend_records_b04_product_acceptance_evidence -q` -> `1 passed`
- `python scripts\engineering\build_r53_r60_p24_b04_product_acceptance_gate.py --root .` -> `pass_with_real_human_acceptance_blocked`
- `python scripts\engineering\build_r53_r60_p21_pre_full_chain_blocker_gate.py --root .` -> `pass`, `blocker_count_open=1`

## Remaining Boundary

P24 is not real product acceptance. B04 still requires:

1. a real analyst / product reviewer session;
2. accepted or rejected deliverable decisions with artifact refs;
3. closeout for the 8 pending defect requirements through repair, regression coverage, or typed-gap acceptance;
4. record those five evidence types through the validated API/CLI/runtime entrypoint;
5. rerun P24 and P21 after those records exist.
