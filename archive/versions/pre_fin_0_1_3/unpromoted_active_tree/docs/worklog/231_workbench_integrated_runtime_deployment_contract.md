# Workbench Integrated Runtime Deployment Contract

Date: 2026-06-05

## Context

Workbench backend had separate lightweight Docker smoke coverage and a full-runtime Docker target, but the API did not yet expose a first-class deployment contract. That made it possible for a lightweight control-plane container to look healthy even though it could not run the full data-building and agent runtime stack inside the container.

## Changes

- Added deployment metadata for Workbench:
  - runtime profile: `control-plane` or `integrated`
  - image kind and release id from environment
  - full-runtime dependency readiness
  - immutable code roots and mutable data/config/report roots
  - data/script update interface inventory
- Added runtime maintenance action catalog:
  - `runtime_preflight`
  - `script_catalog_validate`
  - `data_build_catalog_validate`
  - `script_update_reserved`
- Added maintenance job launch endpoint so safe maintenance actions use the existing Workbench job runner, trace ids, event logs, cancellation, timeout, and concurrency controls.
- Updated Docker/Compose deployment metadata:
  - `compose.yaml` declares `control-plane`
  - `compose.runtime.yaml` declares `integrated`
  - Compose now has a `/api/health/ready` healthcheck
  - direct Docker helper mounts `configs/`, `data/`, and `reports/` instead of only `data/workbench_private/`

## Deployment Decision

Integrated deployment keeps `apps/`, `scripts/`, and `src/` immutable inside the image. Runtime state lives in mounted `configs/`, `data/`, and `reports/`. Script updates should be delivered by rebuilding the image, or later by a signed script-bundle mechanism through the reserved maintenance interface.

The backend intentionally does not expose an arbitrary "run shell command" or "git pull" endpoint. Data updates continue through whitelisted data-build jobs, which already support previews, path policy validation, trace logging, cancellation, timeouts, and source-bundle backfill.

## New API Surface

```text
GET /api/system/deployment
GET /api/system/maintenance/actions
POST /api/system/maintenance/run
```

Existing data update surface remains:

```text
GET /api/data-build/steps
POST /api/data-build/preview
POST /api/data-build/run
POST /api/source-bundles/validate
```

## Validation

Targeted tests added to `tests/test_workbench_backend.py` for:

- deployment contract and update interface inventory
- maintenance action catalog
- maintenance job launch through the runner
- reserved script update action rejection
