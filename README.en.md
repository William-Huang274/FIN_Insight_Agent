# FinSight Agent — FIN 0.1.3

**A financial research workspace that turns a question into a traceable report and follow-up conversation.** Agents use financial SQL, source passages and source-bound calculations to examine business growth, earnings and cash conversion.

[中文](README.md) · [Run and verify](docs/public/quickstart.en.md) · [Architecture](docs/public/architecture.en.md) · [Three-minute demo](docs/public/demo-and-engineering.en.md) · [Evidence and sharing](docs/public/sharing-scope.md) · [Changelog](CHANGELOG.md)

## Capabilities

| Capability | Implementation and evidence boundary |
| --- | --- |
| Dynamic research | A Lead creates a task DAG; experts plan, call tools and submit workpapers. The Dell case exercised nine research areas with a concurrency limit of two. |
| Review and revision | Counter / Verifier, accountable authors, synthesis, research review, Writer, final review and human review. Failed attempts remain visible; model reviewers can miss errors. |
| Traceable evidence | MCP tools for financial SQL, document navigation/search/passages, external search, web reading and calculations. Expressions, operands, periods, units and provenance are retained; arithmetic validity is distinct from financial validity. |
| Interaction | New research, short and deep questions, local revisions, stop, report versions/diffs and source inspection. Saved guidance can be delivered to a later stage; delivery does not prove semantic adoption. |
| Context and costs | Clear old tool output from requests while retaining artifacts/checkpoints and ID-based retrieval; reuse saved calculations and edit locally. Aggregate all native runs with input/output/cache usage, elapsed time, estimated cost and explicit unknowns. |
| User material | Task-scoped documents and images, parsing/chunking and on-demand cached vision. Actual PDF/image questions were exercised, including an identified OCR error. |
| Delivery | Markdown, PDF, Word and PowerPoint from one report. Editable PPT charts and detailed source references in speaker notes. Export makes no model calls. |

The current **Dell report v4** is a development-reviewed candidate awaiting Owner content review: 54 citations, three charts, rendered PDF (15 pages), Word (20 pages) and PowerPoint (44 slides). **FIN 0.1.3** is the product version; report revisions and execution attempts are separate. This evidence is not an unassisted first-pass success rate or production certification.

Automatic summarization remains **HOLD and disabled by default**. Tool-output clearing, artifact retrieval and local edits have bounded qualification evidence; no general equal-quality token-saving percentage has been established.

The [itemized Owner review checklist (Chinese)](docs/product/FIN_0_1_3_OWNER_REVIEW_20260908.zh-CN.md) records the original five requirements, additions, costs and outstanding findings. A successful SQL query with no local facts can now expose a non-factual query receipt; this does not prove issuer non-disclosure. Work stops before Hermes evaluation.

## Runtime

React → FastAPI BFF → LangGraph Agent Server → Lead/expert DAG → review/revision → report → human review and export. PostgreSQL and Redis provide native persistence/execution infrastructure; MCP exposes tools, and LangSmith plus local call records support inspection. FIN owns research contracts, source authority and thin adapters. See [architecture and tradeoffs](docs/public/architecture.en.md).

## Run a zero-model check

```powershell
uv sync --locked --extra agent-runtime --extra external-search --extra workbench-delivery
uv run --no-sync python -m pytest tests/test_task_attachments.py tests/test_report_delivery.py -q
uv run --no-sync python -m scripts.qualification.research_delivery_smoke --output-directory D:/temp/finsight-delivery-smoke
```

The output directory must not already exist. Outputs are explicitly synthetic. Full research also requires Docker, provider/tool credentials, prepared financial data and service settings. The complete private qualification data is not distributed. `--fresh-only` starts without old reports or expert answers, but still requires source data. Follow the [quickstart](docs/public/quickstart.en.md) for frontend builds, deployment and limitations.

- Current research: `http://127.0.0.1:8766/workspace/session`; native API: `http://127.0.0.1:18165`.
- Historical fixed Evidence Pack UI: `http://127.0.0.1:8765/workspace`. Source-only health works; missing private evidence returns typed readiness 503 instead of fabricated reports.
- Services bind to localhost. Uploads and operations currently assume a trusted Owner, not public multi-tenant access.

## Review the evidence

Inspect source passages, calculation operands, report versions, failed attempts and unknown usage alongside successful outputs. The original Dell development research recorded 265 requests, 264 known usage outcomes and an estimated CNY 28.092715, including failures and revisions. Context repair, uploads, later report repairs and new questions are separate batches; this is not a normal single-question price.

The fixed case data cutoff is 2026-09-02; financial SQL covers DELL, MU and NVDA. A complete Dell case and bounded NVIDIA/Micron follow-ups are different qualification scopes. Neither proves general full-company research coverage.

## Documentation and history

This README and `docs/public/` describe the current implementation. [CHANGELOG](CHANGELOG.md) separates product milestones from report revisions. `archive/versions/` and Git retain historical baselines; worklogs retain contemporaneous decisions and failures.

This public repository is available for code and engineering review. User uploads, databases, raw model contexts and private traces are outside the default sharing scope; full-report sharing is reviewed separately. No repository-wide open-source license has been selected. Third-party components retain their own licenses.
