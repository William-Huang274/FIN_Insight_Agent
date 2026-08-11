# FIN 0.1 Code Mainline Cleanup and Disconnection Audit

Date: 2026-07-19

Status: `inventory_frozen_cleanup_applied_commit_slicing_pending`

## Scope

Stopped further product implementation and audited all code accumulated since the current Git HEAD/P26 baseline. Classified the current Workbench product runtime, reusable canonical foundation, historical Multi-Agent engine, Point 01 proof support, release reproducibility assets, durable evidence, design references and generated local output.

## Changes

- added `configs/releases/fin_ia_0_1_code_mainline_manifest_v1_0.json`;
- added the human-readable mainline/archive/disconnection audit;
- documented Workbench, canonical runtime, release scripts and release evidence ownership;
- ignored `.codex_runtime/` and `output/` without deleting local evidence;
- removed the untracked pnpm lock/workspace files because npm `package-lock.json` is the existing dependency authority;
- added focused manifest contract tests;
- recorded the dual-runtime integration debt as `RC-P38-042`.

## Findings

The current FIN 0.1 Workbench mainline is a bounded deterministic product vertical. The historical LangGraph Multi-Agent engine, shared research skill registry, graph planning/lookup and bounded ReAct controller remain implemented assets but are not consumed by the current FIN 0.1 execution path. The standalone DeepSeek three-cell runner and Human Baseline are also intentionally outside canonical Case runtime. These are retained and explicitly classified rather than deleted.

The representative historical Agent Registry suite returned `6 passed / 1 failed`: implementation includes `relationship_graph` for the Product/Technology Analyst while the test still asserts the older source-family list. This was recorded as contract drift and intentionally not repaired during repository cleanup.

## Git Boundary

The working tree began with roughly 1365 status entries and 1303 staged paths. This work did not reset the index, bulk stage, commit, delete unknown untracked files or move digest-bound Point 01 proof artifacts. The next repository operation must rebuild reviewable commits with path-exact staging after explicit approval.

## Authority

No model, network, provider, tool, paid, operational, commercial-data, canonical Case mutation, release or production authority was used or changed.
