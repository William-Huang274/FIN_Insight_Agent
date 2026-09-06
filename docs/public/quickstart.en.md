# Local run and validation

2026-09-07 · [中文](quickstart.zh-CN.md)

## Code-only checks

These checks need no API key, real financial data, Docker or archived report:

```powershell
uv sync --locked --extra agent-runtime --extra external-search --extra workbench-delivery
uv run --no-sync python -m pytest tests/test_task_attachments.py tests/test_report_delivery.py -q
uv run --no-sync python -m scripts.qualification.research_delivery_smoke --output-directory D:/temp/finsight-delivery-smoke
cd apps/workbench/frontend
npm ci
npm run typecheck
npm run build
```

Use a previously nonexistent output directory. The generated files are explicitly synthetic, not Dell benchmark results. Render Word/PPT with LibreOffice and inspect pages; XML checks are not visual acceptance. PDF export itself needs no Office installation.

## Full local deployment

The complete Dell case additionally requires the operator's qualified source files, SQL data and private deployment settings. This is not yet a clone-and-download-all-data distribution. Missing data must not be replaced with invented records or old expert answers.

Install Docker and verify the engine. Distinguish host loopback from container networking when diagnosing proxies; do not delete volumes to treat transient network errors. Keep DeepSeek/LangSmith credentials and database passwords in the local `.env`, never command-line logs or Git. LangSmith is required; there is no alternate tracing fallback.

Prepare the existing qualified settings directory with `host-settings.json` and `container-settings.json`, data mounts and preserved compatibility-report bindings. The BFF still initializes its legacy report-review entry from the saved bundle/report. This is a private deployment-packaging dependency, not fresh-model input; the fresh parent does not load old answers.

```powershell
# Substitute an existing controlled settings directory. Neither command starts a model task.
uv run --no-sync python -m scripts.deployment.dell_report_workbench up --settings-directory D:/private/finsight-session --enable-research
uv run --no-sync python -m scripts.deployment.dell_report_workbench serve --settings-directory D:/private/finsight-session --enable-research
```

Workspace: `127.0.0.1:8766`; native Agent Server: `127.0.0.1:18165`. Runtime configuration is `configs/research/runtime/research_session.json`; the case question is `configs/research/cases/dell_growth_quality.json`. A new question creates a native thread/run, not another Compose project, port or database volume.

## Use and verify

Create a research task, check as-of date/estimated cost, optionally upload files and explicitly start. Invalid parsing preserves a draft without starting models. Watch actual tasks and per-request calls/tokens/estimated cost. Concurrency two does not mean two topics. In-run guidance is consumed at later phase handoffs; confirm the delivery event.

Cancellation preserves completed records and does not retry unknown provider results. Inspect the owning node before deciding on a targeted correction. Model review is contestable, and human acceptance does not publish. Quick Flash Q&A and deep Pro follow-up are explicit modes.

Exports do not invoke a model or change the report. PPT uses editable charts/tables and paginated content, not an additional model-generated presentation narrative. Source-bound chart values still require period/semantic review.

Uploads support PDF/DOCX/MD/TXT/CSV/HTML/PNG/JPEG/WebP, limited to 20MiB per file, twelve files/80MiB per task and 200 PDF pages, plus expansion/text limits. Images/scanned pages may be sent on demand to DeepSeek vision. This is trusted-owner local input, not a public malicious-file sandbox.

```powershell
uv run --no-sync python scripts/eval_multi_agent/run_project_os_full_chain_preflight.py --decision configs/research/runtime/research_session.json --pretty
uv run --no-sync python -m pytest tests/test_research_session.py tests/test_research_session_bff.py -q
```

These are contract/wiring checks, not semantic or production certification. Evaluate actual workpapers, sources, reports and usage under the same thread/run. Keep feature probes, failures, full research and follow-ups separate; account billing is not one task's cost. Investigate data, tool, schema and network failures separately. Never clear data or weaken validators merely to turn a check green.
