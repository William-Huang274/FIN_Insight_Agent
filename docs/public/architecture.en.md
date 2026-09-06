# FinSight: architecture and build/adopt boundary

2026-09-07 · Local Dell development case · [中文](architecture.zh-CN.md)

## Research flow

Question → dynamic Lead DAG → independent multi-turn specialists (dependencies, concurrency two) → Counter/Verifier → responsible authors where needed → Lead synthesis → independent research review → Writer and source-bound charts → final review → human review, follow-up and export.

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

## Limits

Trusted local-owner pilot only: no public authentication, production multitenancy or process-sandbox qualification for malicious documents. The model has no shell, arbitrary file-write or escalation tool; that is not equivalent to end-to-end multi-tenant security. Empty retrieval does not prove non-disclosure.

The fresh question has reached a real report and human checkpoint, including preserved failures, native continuations and human-directed revisions—not unassisted one-shot success. General-company performance, crash recovery during paid calls, production concurrency and P95 latency are not inferred from one case. Tested `dell_*` adapters remain for compatibility; new session/upload/chart interfaces use generic names. Historical filenames are not mass-renamed for cosmetic reasons.

Method availability is not proof of consistent use: six short methods are available; some roles read specific methods while others only requested the catalog. Stock-versus-flow, causal and formula errors still occurred after numeric/reference checks and needed model review and host inspection. These case answers were not converted into generic NLP rules. A model's zero-material-finding review is not a claim of perfect accuracy.
