# FinSight Workbench — FIN 0.1.3 baseline

This directory is the only active browser product and operator runtime.

## Entrypoints

- Product: `/workspace`
- Operator console: `/operations`
- Backend: `backend/app.py`
- Product APIs: `backend/api/v1/research_workspace.py` and
  `backend/api/v1/research_evidence_packs.py`
- Operator API: `backend/api/operations.py`
- React/Vite root: `frontend/vite/src/main.tsx`

`/current`, `/next`, `/tasks` and `/cases` redirect to `/workspace`.
`/legacy` redirects to `/operations`.  Their old implementations are preserved
under `archive/versions/pre_fin_0_1_3/`; they are not loaded by this app.

## Honest product boundary

The product currently offers a read-only, identity-bound view of reviewed DELL,
MU and NVDA Evidence Packs. It shows evidence, source boundaries and typed
residual gaps. The current packs contain no structured numeric items, so
numeric-fact readiness is not claimed. It does **not** claim unrestricted dynamic
research, a complete valuation, autonomous report release, realtime commercial
market data or production multitenancy.

The reviewed objects are deliberately not distributed in Git. Without a
`FINSIGHT_DATA_ROOT` mount, the catalog remains readable, detail actions are
disabled and `/api/readiness` returns typed HTTP 503. A full local acceptance
mount must contain
`workbench_private/fin_0_1_3_s1_six_case_local_evidence_pack/zero-call-r1/objects`.

The operator surface manages profiles, source bundles, admitted data-build
steps, saved-run inspection and the active-baseline verifier.  Agent ask,
session continuation and native-checkpoint execution return HTTP 410 until a
provider-neutral successor is promoted through the current Runtime contract.

The authoritative code map is
`../../docs/architecture/repository/FIN_0_1_3_CURRENT_BASELINE_CODE_MAP_20260811.zh-CN.md`.
