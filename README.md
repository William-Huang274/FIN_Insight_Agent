# FinSight-Agent

[中文版本](README.zh-CN.md)

FinSight-Agent is an evidence-grounded financial research agent for public-company analysis. It turns open-ended investment-research questions into a traceable workflow: define the research scope, retrieve source evidence, extract comparable financial values, build an analysis frame, call an API LLM for synthesis, and run deterministic checks before presenting the answer.

The first public demo focuses on SEC filings, company-authored earnings releases, and offline market snapshots. The same source model is designed to expand to additional research materials, such as earnings-call transcripts, industry news, analyst datasets, or internal research notes, without letting the model blur source boundaries.

The output is not a live trading signal or a generic chatbot answer. It is a research memo with explicit source tiers, fiscal-period roles, filing boundaries, market-snapshot dates, and follow-up session context.

## What It Is For

FinSight-Agent is useful when the question needs more than one piece of text from one filing. Typical tasks include:

- comparing AI, cloud, semiconductor, and platform companies across revenue growth, capex, RPO, data-center demand, or segment momentum;
- combining audited annual filings, latest quarterly filings, company-authored 8-K earnings-release commentary, and recent non-real-time market context;
- asking follow-up questions about one company, one metric, one evidence gap, or one section of a prior memo;
- checking whether a claim comes from audited filings, unaudited quarterly data, management commentary, or market-snapshot analytics.

## Why This Is An Agent

A single API call can write a fluent memo, but it cannot by itself prove which filings were used, whether QTD and annual figures were mixed, whether a market snapshot was stale, or whether a follow-up reused the right context.

FinSight-Agent separates responsibilities:

- the model understands the question, selects high-level actions, and writes the final memo;
- the tool chain retrieves filings and structured objects, computes exact-value ledgers, tracks fiscal-period roles, checks evidence coverage, and validates final claims;
- the session layer preserves the active answer, evidence references, and long-lived context for follow-up questions.

That separation is the core design choice: let the model reason over evidence, but let testable code own evidence handling and constraints.

## Core Flow

```text
User question
  -> constrained query planning
  -> optional tool/function-call routing for multi-turn sessions
  -> evidence retrieval and structured-object lookup
  -> runtime exact-value ledger
  -> evidence coverage check
  -> judgment plan
  -> API LLM synthesis
  -> deterministic gates
  -> rendered memo and session memory
```

`QUERY_PLANNER=llm` uses an API model through the project gateway, such as DeepSeek or another OpenAI-compatible provider. The planner does not return free-form prose; it returns a bounded query contract that is validated for tickers, years, filing types, source tiers, metric families, market-snapshot requirements, and output size.

Multi-turn sessions use OpenAI-compatible tool/function calls. The model selects high-level tools, such as starting an analysis, revising scope, inspecting coverage, explaining evidence, reformatting an answer, or resuming a partial run. The Python harness executes those tools and owns state changes, artifact references, and safety checks.

## Agent Runtime

| Layer | Responsibility |
| --- | --- |
| Query Contract Planner | Converts the user question into a bounded research contract: tickers, fiscal years, filing types, source tiers, metric families, and analysis intent |
| Tool-call Controller | Lets an API model choose high-level actions in multi-turn sessions; the model returns tool names and arguments, not direct file-system operations |
| Tool Harness | Executes the selected tools, manages session state, applies scope invalidation, and decides whether a graph stage must rerun |
| Retrieval and Objects | Searches filing text, structured financial objects, 8-K evidence, and market-snapshot evidence using BM25, ObjectBM25, and BGE reranking |
| Exact-Value Ledger | Extracts comparable financial values with ticker, fiscal year, filing type, period role, unit, and source object id |
| Coverage and Judgment Plan | Records evidence support and gaps, then builds a constrained analysis frame before synthesis |
| LLM Synthesis | Calls an API LLM to write the research memo inside the evidence and judgment-plan boundaries |
| Deterministic Gates | Checks source boundaries, numeric citations, market `as_of_date`, claim support, and forbidden unsupported conclusions |
| Context Manager | Stores session state, active answer ids, artifact references, and follow-up context |

The graph runner uses LangGraph as a lightweight orchestration boundary around the existing deterministic stages. The current graph writes state and artifact references that can be inspected or resumed; retrieval, ledger construction, coverage, synthesis, and gates remain separate modules.

## Example

A user can ask:

```text
Using SEC 10-K, latest 10-Q, 8-K earnings releases, and the last three months
of market snapshots, compare NVDA, AMD, MSFT, AMZN, and GOOGL across AI
fundamentals, management commentary, market reaction, and valuation divergence.
```

FinSight-Agent does not hand that prompt directly to a model. In a session, the API model first chooses a high-level tool call, typically `start_memo_analysis`, with a bounded scope. The harness then runs the evidence pipeline: retrieve 10-K/10-Q passages, structured financial objects, 8-K commentary, and market-snapshot rows; build the exact-value ledger; mark missing evidence such as companies that do not disclose standalone AI revenue; ask the model to synthesize only within that frame; and gate the final memo for source mixing, missing snapshot dates, and unsupported claims.

If the user then asks, "focus only on NVDA versus AMD," the session can reuse the prior scope, answer, and evidence references instead of starting from an unrelated prompt.

## Evidence Model

| Source tier | What it supports | Boundary |
| --- | --- | --- |
| `primary_sec_filing` | 10-K / 10-Q financial facts, business descriptions, risks, and MD&A | Annual and quarterly filings have different audit status; QTD, YTD, TTM, and annual values must not be merged |
| `company_authored_unaudited_sec_filing` | 8-K earnings-release commentary, management explanations, guidance, and operating narrative | Company-authored commentary cannot replace structured 10-K / 10-Q financial facts |
| `market_snapshot` | Non-real-time price performance, relative returns, event windows, and valuation context | Must carry `snapshot_id` and `as_of_date`; it is not a live quote |

## Repository Layout

```text
src/
  connectors/      SEC connectors and filing manifests
  ingestion/       SEC / 8-K parsers and section splitters
  retrieval/       BM25, ObjectBM25, dense retrieval, hybrid retrieval
  evidence/        evidence objects and structured financial data
  sec_agent/       query contracts, harness, context, gates, market snapshots

scripts/
  cloud/           interactive agent and session CLI entrypoints
  market/          snapshot download, normalization, analytics, evidence packs
  evaluate_*.py    planner, context, readiness, latency, and smoke checks
  build_*.py       manifests, chunks, ledgers, indexes, and structured objects

tests/
  source policy, 10-Q / 8-K contracts, market snapshots, context, observability
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

For large SEC collection runs, set a real SEC User-Agent contact in your environment. Keep `.env`, API keys, provider tokens, private filings, provider data, generated indexes, and run outputs out of Git.

Configure an API model route:

```bash
export LLM_BACKEND=deepseek
export MODEL_NAME=deepseek-v4-pro
export API_KEY_ENV=DEEPSEEK_API_KEY
export DEEPSEEK_API_KEY="<set-in-shell-only>"
```

For another OpenAI-compatible provider:

```bash
export LLM_BACKEND=openai_compatible
export BASE_URL="<provider-base-url>"
export MODEL_NAME="<model-name>"
export API_KEY_ENV=PROVIDER_API_KEY
export PROVIDER_API_KEY="<set-in-shell-only>"
```

## Demo

Full-source one-shot demo, assuming the data profile points to your local artifacts:

```bash
SEC_AGENT_PROFILE_ENV=.env bash scripts/cloud/sec_agent_interactive.sh ask-full-source-api \
"Using SEC 10-K, latest 10-Q, 8-K earnings releases, and the last three months of market snapshots, compare NVDA, AMD, MSFT, AMZN, and GOOGL across AI fundamentals, management commentary, market reaction, and valuation divergence."
```

Multi-turn session:

```bash
SEC_AGENT_PROFILE_ENV=.env bash scripts/cloud/sec_agent_interactive.sh session-full-source-api
```

Useful session commands:

```text
/state
/context
/answer
/exit
```

Start from `configs/sec_agent_full_source_demo.env.example` when wiring your own artifact paths:

```bash
cp configs/sec_agent_full_source_demo.env.example .env
```

Then update manifest, index, market-evidence, snapshot id, and model-route variables in `.env`.

More entrypoints:

- [Demo entrypoints](docs/demo/sec_agent_demo_entrypoints_v1.md)
- [中文自有数据快速接入](docs/deployment/local_custom_data_quickstart.zh-CN.md)

## Checks

Local structural readiness, no model key required:

```powershell
python scripts/evaluate_sec_agent_resume_closeout_readiness.py --timeout-s 600
python -m pytest tests/test_resume_closeout_readiness.py tests/test_sec_agent_context_source_policy.py tests/test_market_snapshot_fixture.py
```

With a completed full-source run, pass the saved run directory into the readiness aggregator:

```bash
python scripts/evaluate_sec_agent_resume_closeout_readiness.py \
  --saved-full-source-run-dir eval/sec_cases/outputs/<run>/<case> \
  --require-full-source-artifacts \
  --timeout-s 900
```

## Current Reproducibility Boundary

The first demo data product targets a `full30` technology / AI / cloud / semiconductor universe with FY2023-FY2025 10-K filings and the latest available FY2026 10-Q / 8-K evidence in the prepared artifact set. Market snapshots are offline and must display `as_of_date`.

The public repository does not include SEC source documents, provider outputs, generated indexes, API keys, or runtime artifacts. Use your own data to generate equivalent artifacts, then point `SEC_AGENT_PROFILE_ENV` to your local profile. If a company, period, filing type, or market field is missing from the manifest, the system should report a coverage gap instead of claiming coverage.

The current JSON-backed session store is suitable for demos and single-process evaluation. Multi-user serving should move session state to a database, Redis, or a locked state store.
