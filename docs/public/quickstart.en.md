# Local run and validation

[中文](quickstart.zh-CN.md) · [Home](../../README.en.md) · FIN 0.1.3

## Choose a verification path

| Path | Requirements | What it checks |
| --- | --- | --- |
| Public source check | Python 3.11, uv | Attachments, exports, configuration consumption, targeted revision; synthetic reports in four formats |
| Browser interaction check | Node.js 22, npm, Chromium | Navigation, sources, diffs, configuration editing and replay at three widths, using synthetic API responses |
| Full research workspace | The above, Docker, model/tool credentials, source data and service settings | Actual threads, models, tools, reports, revisions and usage |

The first two paths need no private database and make no model calls. They do not establish financial correctness or replace the full backend. A downloadable, complete research data bundle is not currently distributed.

## 1. Check source and generate synthetic reports

From the repository root, in PowerShell or a typical POSIX shell:

```bash
uv sync --locked --extra agent-runtime --extra external-search --extra workbench-delivery
uv run --no-sync python -m scripts.dev.verify_public_checkout --output-directory .local/public-check-01
```

The check generates MD, PDF, DOCX, PPTX, a chart PNG and synthetic report JSON; test counts come from the current output. The output directory must not exist. Choose `.local/public-check-02` for another attempt; earlier results are not overwritten. Files are explicitly synthetic, not company research results. Inspect Word/PPT layout in Office or LibreOffice in addition to structural checks.

The script calls existing pytest tests and the exporter. It does not load local `.env`, deploy services or submit model tasks.

## 2. Check browser interactions

```bash
cd apps/workbench/frontend
npm ci
npm run typecheck
npm run build
npx playwright install chromium
npm run test:public
```

On Linux, use `npx playwright install --with-deps chromium` if browser system dependencies are missing. The public profile starts only local Vite, on port **4183** by default, without the source-only backend. Tests cover 1440, 1024 and 390 pixel layouts; counts come from the current output. Research APIs use explicit synthetic responses.

Use `npm run test:public -- --headed --workers=1` to watch the tests. Failure screenshots and traces are written under `apps/workbench/frontend/test-results/public/`; inspect a trace with `npx playwright show-trace <trace.zip>`. Playwright manages this results directory; copy failures elsewhere before another run if you need to preserve them.

If a port is occupied or reserved by Windows, set `FINSIGHT_E2E_FRONTEND_PORT` to another available port. The default `test:e2e` also starts the compatibility backend; `FINSIGHT_E2E_BACKEND_PORT` changes both its listener and the frontend proxy (PowerShell: `$env:FINSIGHT_E2E_BACKEND_PORT='18795'`). `test:public` needs no backend. Do not stop unrelated services to free a port.

## 3. Start full local research

The runtime uses LangGraph Agent Server, PostgreSQL, Redis and LangSmith. Prepare:

- A working Docker Engine.
- Local model, LangSmith and applicable tool credentials; see the root `.env.example`.
- Financial SQL, document trees and source materials conforming to the current data contracts.
- A settings directory containing `host-settings.json`, `container-settings.json` and data mounts; see [deployment](../../deploy/agent_server/README.md) and the [research runtime](../../src/sec_agent/agent_runtime/research_session_runtime.py).

`--fresh-only` omits old reports and expert answers but still requires source data. Omit legacy bundle/report paths from those settings. Replace the placeholder below with your prepared directory:

```bash
uv run --no-sync python -m scripts.deployment.research_workbench check --settings-directory /path/to/prepared-settings --enable-research --fresh-only
uv run --no-sync python -m scripts.deployment.research_workbench up --settings-directory /path/to/prepared-settings --enable-research --fresh-only
uv run --no-sync python -m scripts.deployment.research_workbench serve --settings-directory /path/to/prepared-settings --enable-research --fresh-only --ui-port 8793
```

On Windows, a path such as `D:/private/finsight-session` is valid. Build the frontend first. Open **http://127.0.0.1:8793/workspace**; the native API defaults to **18165**. The BFF runs in the foreground; Ctrl+C stops it. These commands do not submit a model task. The `up` command creates or updates services; do not rebuild during active research.

The `research_workbench` entry owns the deployment implementation. New questions use native threads and reuse existing services and data volumes. Before upgrading, stop old processes and back up data; see the [upgrade guide](../architecture/repository/local_record_upgrade.zh-CN.md).

## 4. Walkthrough for testers

1. **Research start:** select a suggested question, set the scope and attach material. Preparation and actual execution are separate; live execution incurs model costs.
2. **Research map:** open overview → topic → judgment and evidence. Check breadcrumb return, source context and calculation periods.
3. **Revision comparison:** expand and collapse again, including the bottom return button. Check the report version and baseline.
4. **Research Studio:** edit a Skill, save a new version, reload it, then apply it to an idle task. Browser project organization and backend configuration snapshots have different persistence scopes.
5. **Run history:** choose a past run, filter a stage and play/pause/seek. Replay makes no model calls. Live guidance is read at later phase handoffs.
6. **Optional live change:** in a configured environment, submit one small, explicit correction and inspect its target, result, diff and cost. Testing should not default to a full research rerun.

Report steps, expected/actual behavior, browser/viewport, code commit and public error text; include a run ID for execution issues. Do not attach credentials, raw model context, private traces or personal material. The repository includes a Bug report template.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Studio reports an unavailable runtime | Full functionality requires the research BFF and native API. Vite alone is not a research backend. |
| Readiness returns 503 without data | Historical source-only health/catalog can work while real data is unavailable. The service does not invent financial records. |
| Chromium executable is missing | Run the Playwright install command; check download proxies and OS dependencies. |
| Output directory exists | Choose a new name and keep the earlier result. |
| A model request has an uncertain outcome | Inspect the original run and audit before deciding on a new paid request. |

## Broader engineering checks

The full public Python suite needs additional dependencies:

```bash
uv sync --locked --extra agent-runtime --extra external-search --extra workbench-delivery --extra control-plane --extra qualification
uv run --no-sync python -m pytest -q
```

Private-data tests are skipped by default; use `--run-private-data` only with their original mounts. Historical Git proofs require full history, and Windows-specific tests require Windows. Full-suite checks, public interaction tests and live research are distinct evidence scopes.

v0.1.3 is a local preview for evaluation and development. Reports retain their own versions and review states; see the [evaluation report](technical-evaluation.en.md) for results and scope.
