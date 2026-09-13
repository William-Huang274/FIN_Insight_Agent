# FinSight: architecture and build/adopt boundary

2026-09-13 · FIN 0.1.3 frozen local Internal Alpha · [中文](architecture.zh-CN.md)

The [0.1.3 closeout](../product/fin_0_1_3_closeout.zh-CN.md) defines the current scope. Dynamic method applicability, rule updates, bounded expert delegation and deadline convergence remain planned for 0.1.4. One-off implementations have left the active tree; see [historical recovery](../../archive/README.md).

## Research flow

Question → dynamic Lead DAG → independent multi-turn specialists (dependencies, concurrency one or two, default two) → Counter/Verifier → responsible authors where needed → Lead synthesis → independent research review → Writer and source-bound charts → final review → human review, follow-up and export.

Agents choose their tools and research actions; the parent controls dependencies and artifact handoffs, not the answer. Nine topics may require multiple waves, with a current safety capacity of twelve tasks. Reviewers can be wrong. Authors can challenge findings using original evidence. Writing corrections do not restart unrelated research; data failures are not disguised as prose caveats.

| Layer | Adopted components | FinSight responsibility |
| --- | --- | --- |
| Product | React, Vite, Markdown, native streaming SDK | `apps/workbench`: interactions, activity and evidence views |
| Execution | LangChain create_agent, LangGraph/Send | `research_session*.py`, `research_convergence.py`: task contracts, handoffs and responsibility routing |
| Persistence/observability | Agent Server, PostgreSQL, Redis, LangSmith | Stable Compose deployment, isolated role histories; no custom queue/checkpoint/tracing platform |
| Tools | Official MCP client/server | Source, SQL, methods and calculation schemas |
| Documents | Qualified local document tree; pdfplumber, python-docx, BS4, LangChain splitters, BM25 for uploads | Task-owned originals, page/section locators; uploads are not claimed to have a dense/reranker index |
| Numbers | SEC structured data into SQL, simpleeval/Decimal | Company/period/unit and source-bound operands; arithmetic is not economic validation |
| External sources | Existing Exa MCP search/crawl, trafilatura | Source IDs, readable windows and source-quality distinctions |
| Vision/delivery | DeepSeek vision SDK, Matplotlib, ReportLab, python-docx, python-pptx | Original-image linkage, source-bound chart values, portable exports, no arbitrary generated-code execution |

`uv.lock`, the frontend lockfile and the base-image digest pin dependencies. LangChain supplies the mature agent loop; it does not reinstate the old bespoke evidence shell.

## Context and evidence

Each role keeps its own native message history. Handoffs carry tasks, public workpapers, references and concise explanations—not private reasoning transcripts. Initial context contains the question and capability/method catalogs; models progressively request methods, document outlines, source windows, SQL and calculations.

The host validates schema, observed-source references and arithmetic. It does not impose one natural-language report template or claim to decide semantic truth. Citations resolve submitted claims, observed PASSAGE windows, SQL NUMFACTs or CALC results. Unstructured financial data may support analysis but never silently becomes authoritative SQL data.

In-run guidance is saved in native thread metadata and consumed at subsequent research/review/convergence phase handoffs. It is not an instantaneous override of an in-flight completion. Uploads are task-owned copies; no model tool can edit arbitrary user files.

Old tool text is cleared only from the outgoing request projection; messages and artifacts remain in native checkpoints. Complete CALCs from saved answers are exposed through a task-scoped read-only tool view without reinserting entire citation trees into model messages. Missing, conflicting or cross-task records are rejected. Automatic summaries remain HOLD and disabled. The BFF paginates all native runs and uses run ID plus call ID for identity; unknown usage/cache/time remains explicit, with external imported-revision costs separate.

`--fresh-only` registers research_session without old answers and retains the fixed PostgreSQL/Redis deployment and source data. Vision is an on-demand read-only tool with caching; absent cache fields are unknown. MD/PDF/Word/PPT share one versioned report/source projection, with editable PPT charts and detailed sources in speaker notes. Historical v4 exports were rendered; the subsequent local revision v5 still awaits human review.

## Limits

The frozen version includes OIDC/PKCE with two users, 39 resource-ownership checks, 8 concurrent reads and 4 actual frontend approval scenarios. Approved operations resume natively through authenticated MCP into a Docker sandbox; rejection prevents execution. Tools follow their configured capabilities. These are local qualifications, not production multitenancy, comprehensive malicious-document security or HA certification. Empty retrieval does not prove non-disclosure.

Tasks have reached real reports and human review, with preserved failures, targeted revisions and bounded verification of restart handoff and submission deduplication. The 19 real user turns include recovery; they do not establish general-company financial quality or production P95. Still-used `dell_*` modules preserve graph, database and source identities; retired implementations have left the active tree.

Method availability is not proof of consistent use: six short methods are available; some roles read specific methods while others only requested the catalog. Stock-versus-flow, causal and formula errors still occurred after numeric/reference checks and needed model review and host inspection. These case answers were not converted into generic NLP rules. A model's zero-material-finding review is not a claim of perfect accuracy.

## From UI nodes to runtime operations

The research map projects actual report sections and citations into overview, topic and judgment/evidence levels. Navigation nodes expand content. Editable judgments carry a citation ID, baseline version, content digest and checkpoint into the existing research_revision path. The server checks the baseline before accepting a change.

Research Studio persists independent native Assistants snapshots through the FastAPI research_studio API. A task stores the selected snapshot ID; each run loads and fixes that configuration and digest. Role bindings feed agent prompts and MCP method reads. Specialist context is bound before the request digest is created. Review order changes native StateGraph edges, and concurrency changes the existing profile. Required checks cannot be deleted; this is not an arbitrary workflow-code editor.

| Layer | Source |
| --- | --- |
| Graph navigation and revision | `apps/workbench/frontend/vite/src/app/ResearchGraph.tsx` |
| Configuration editor | `apps/workbench/frontend/vite/src/app/ResearchStudio.tsx` |
| Persistence, application and run configuration | `apps/workbench/backend/api/v1/research_studio.py` |
| Configuration contract and role methods | `src/sec_agent/agent_runtime/studio_configuration.py` |
| Runtime consumption | `src/sec_agent/agent_runtime/research_session_runtime.py` |
| Public deployment command | `python -m scripts.deployment.research_workbench` |

The frontend uses Lucide icons, React Markdown/remark, the diff package and React Flow. Runtime views display recorded stages and public events. Replay reveals saved events in the client; it is not a second execution engine. Sidebar project groups are browser-local, while reports, checkpoints and configuration snapshots persist on the server.

A September 8 live short question verified that an edited method entered two model requests and changed answer organization without changing the report. Native synthetic graph tests cover specialist request validation and review order. This is not paid qualification of every role or company.
