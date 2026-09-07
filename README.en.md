# FinSight Agent — FIN 0.1.3

**A financial-research workspace from question to an inspectable report.** Agents use real data tools to analyze business growth, profit and cash flow, with traceable sources, calculations and charts.

This branch contains the current dynamic workflow: a real frontend, nine research topics, cross-review and targeted author repair, synthesis, reporting, follow-up and export. A developed Dell case produced a v3 candidate with 42 citations and three charts, downloaded and rendered in four formats. One material workpaper/report inconsistency remains; final content acceptance is open.

**Version:** this README describes the development candidate on `codex/fin013-dell-s1-s2-product-bridge`. Runtime code on `main` is the historical fixed Evidence Pack workspace. Full research requires configured services, model credentials and prepared data. The [run guide](docs/public/quickstart.en.md) also provides checks that require no model calls.

## Current implementation

- Dynamic Lead DAG and independent multi-turn specialists. Nine research topics; concurrency two is not a two-specialist limit.
- Counter/Verifier, targeted author repair, Lead synthesis, independent research review, Writer, final review and human handoff have all executed with real models. Model review can still miss errors.
- MCP tools for SEC financial SQL, document structure/search/source windows, external search/page reads and source-bound calculation.
- LangChain / LangGraph, Agent Server, PostgreSQL, Redis and LangSmith. FIN owns research contracts, source authority and thin adapters.
- Bounded validation of old tool-output clearing, original evidence retention, source readback and local report edits. Automatic summarization remains disabled; no general cost-saving percentage is established.
- Real task creation, activity, source inspection, follow-up, revision, cancellation and guidance consumed at subsequent phase boundaries.
- Task-isolated uploads, mature parsing/chunking and on-demand Flash vision. One real MCP vision probe used 423 tokens; this is not an OCR accuracy benchmark.
- Source-bound charts and Markdown/PDF/Word/PowerPoint exports. File/visual checks are distinct from financial-content acceptance.

Current workspace: `http://127.0.0.1:8766/workspace/session`; native Agent Server: `http://127.0.0.1:18165`. Both are local-only. The case snapshot is 2026-09-02; financial SQL currently covers DELL/MU/NVDA, not every company. Fresh research reuses original data, not previous expert answers.

[Architecture and build/adopt split](docs/public/architecture.en.md) · [Run and test](docs/public/quickstart.en.md) · [Sharing scope and evidence claims](docs/public/sharing-scope.md) · [中文](README.md)

An independent source checkout passed 17 upload/export checks and generated four synthetic export formats on 2026-09-08, with zero model calls. It reused installed dependencies; fresh dependency installation and independent full-research startup remain unverified. The original developed Dell case used 265 requests, 264 with known usage, at an estimated CNY 28.09 including failures and revisions. Step-one remediation batches are separate; these figures are not short-Q&A prices or unassisted success rates. See the [evidence and sharing scope](docs/public/sharing-scope.md).

The repository is public. Uploads, databases, raw model context and private traces are excluded from the intended showcase; full report sharing requires a separate content review.

<details>
<summary>Historical fixed Evidence Pack workspace: compatibility, startup and baseline</summary>

## Legacy fixed-pack workspace

The 8765 commands below refer to the earlier read-only Evidence Pack interface, retained for compatibility/regression. They do not launch the new research workflow or prove multi-case agent performance.

### Run the legacy interface

```powershell
uv sync --locked
cd apps/workbench/frontend
npm ci
npm run build
cd ../../..
uv run --locked python scripts/dev/run_workbench_backend.py --host 127.0.0.1 --port 8765
```

Python dependencies are maintained only in `pyproject.toml` and pinned by the tracked `uv.lock`; do not add a second hand-maintained requirements file.

- Product: `http://127.0.0.1:8765/workspace`
- Operations: `http://127.0.0.1:8765/operations`
- Health: `http://127.0.0.1:8765/api/health`

The repository does not distribute the private reviewed-pack objects. Without a mount, the case catalog remains visible, detail buttons are disabled, and `/api/readiness` returns a typed HTTP 503. For full case review, set `FINSIGHT_DATA_ROOT` to a data root containing `workbench_private/fin_0_1_3_s1_six_case_local_evidence_pack/zero-call-r1/objects`. Keep all credentials in environment variables and out of Git.

### Verify the legacy baseline

```powershell
uv run --locked python scripts/engineering/verify_active_baseline.py --pretty
uv run --locked python scripts/engineering/build_archive_redirect_index.py --check
uv run --locked python -m pytest -q
```

See the [current code map](docs/architecture/repository/FIN_0_1_3_CURRENT_BASELINE_CODE_MAP_20260811.zh-CN.md) and [current context pack](docs/project_os/current_context_pack.zh-CN.md) for the exact product and repository boundary.

</details>
