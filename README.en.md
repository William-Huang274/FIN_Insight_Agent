# FinSight Agent — FIN 0.1.3

**A local financial-research workspace combining autonomous agents, real tools and traceable sources.** The objective is a useful, conditional research judgment connecting business growth to profit, cash realization and execution pressure—not a report dominated by disclaimers.

As of 2026-09-07, a fresh Dell growth-quality question has run from the real frontend through multi-agent research, reporting and a human-review checkpoint. The developed case includes preserved failures, native continuations and human-directed revisions; it is not an unassisted, error-free one-shot benchmark. The delivery version, measured costs and remaining findings are recorded in the worklog. Owner acceptance and public release remain separate decisions.

The current review candidate is v3: 7,281 narrative characters, 42 citations and three charts, downloaded and rendered in four formats. One material finding remains: an overstrong demand-workpaper inference was not synchronized with the corrected report. The session made 265 requests (264 with reported usage), estimated at CNY 28.09; additional paid execution is stopped. **Final quality acceptance is not claimed.** These development-and-revision costs are not a normal short-question price. See the [execution and cost record](docs/worklog/fin_0_1_3_s3/190_dell_cost_external_and_interactive_delivery.md).

## Current implementation

- Dynamic Lead DAG and independent multi-turn specialists. Nine research topics; concurrency two is not a two-specialist limit.
- Counter/Verifier, targeted author repair, Lead synthesis, independent research review, Writer, final review and human handoff have all executed with real models. Model review can still miss errors.
- MCP tools for SEC financial SQL, document structure/search/source windows, external search/page reads and source-bound calculation.
- LangChain create_agent / LangGraph, Agent Server, PostgreSQL, Redis and LangSmith—not a custom execution/checkpoint/queue platform.
- Real task creation, activity, source inspection, follow-up, revision, cancellation and guidance consumed at subsequent phase boundaries.
- Task-isolated uploads, mature parsing/chunking and on-demand Flash vision. One real MCP vision probe used 423 tokens; this is not an OCR accuracy benchmark.
- Source-bound charts and Markdown/PDF/Word/PowerPoint exports. File/visual checks are distinct from financial-content acceptance.

Current workspace: `http://127.0.0.1:8766/workspace/session`; native Agent Server: `http://127.0.0.1:18165`. Both are local-only. The case snapshot is 2026-09-02; financial SQL currently covers DELL/MU/NVDA, not every company. Fresh research reuses original data, not previous expert answers.

[Architecture and build/adopt split](docs/public/architecture.en.md) · [Run and test](docs/public/quickstart.en.md) · [Sharing scope and evidence claims](docs/public/sharing-scope.md) · [中文](README.md)

Repository preparation does not change visibility. Uploaded files, crawled source bodies, databases, raw model context and private traces are not redistributed by default. Model review is neither an oracle nor human acceptance; the product does not autonomously publish investment advice.

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
