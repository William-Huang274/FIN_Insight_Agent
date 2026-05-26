# FinSight-Agent Demo Entrypoints

[中文版本](sec_agent_demo_entrypoints_v1.zh-CN.md)

This page collects the public demo paths for FinSight-Agent. The commands are intentionally short: data paths and model routes should live in an ignored profile file, not in copy-pasted terminal blocks.

## Public Repository Boundary

Public:

- source code under `src/`, `scripts/`, and `configs/`;
- tests, small evaluation contracts, and public documentation;
- durable work logs or run ledgers that contain summaries and paths only;
- small synthetic fixtures with no private filings, raw provider output, or credentials.

Private or ignored:

- SEC source files and provider datasets under `data/raw_private/` and `data/processed_private/`;
- generated search indexes and model caches under `data/indexes/` and `data/models_private/`;
- runtime outputs under `eval/`, `reports/quality/`, `reports/demo/`, and `reports/logs/`;
- API keys, SSH passwords, provider tokens, `.env`, and temporary run files.

## Local Structural Check

Run this after cloning the repository or before changing the agent pipeline. It does not require an API key or private source data.

```powershell
python scripts/evaluate_sec_agent_resume_closeout_readiness.py --timeout-s 600
```

For a faster contract-only check:

```powershell
python scripts/evaluate_sec_agent_resume_closeout_readiness.py `
  --skip-main-chain-case-suite `
  --skip-context-load-smoke `
  --skip-latency-profile
```

Outputs are written under `reports/quality/resume_closeout/`, which is ignored by Git.

## Configure A Full-Source Demo

Start from the profile template:

```bash
cp configs/sec_agent_full_source_demo.env.example .env
```

Then update `.env` with your local artifact paths:

```bash
MANIFEST_PATH=data/processed_private/manifests/<your_manifest>.jsonl
BM25_INDEX_DIR=data/indexes/bm25/<your_text_index>
OBJECT_BM25_INDEX_DIR=data/indexes/bm25/<your_object_index>
MARKET_EVIDENCE_PATH=data/processed_private/market/evidence_packs/<your_market_evidence>.jsonl
MARKET_SNAPSHOT_ID=<your_snapshot_id>
MARKET_AS_OF_DATE=<YYYY-MM-DD>
```

Configure a model route in the shell. DeepSeek is one tested provider; any compatible route can be used if the gateway variables are set.

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

Check that the profile is readable:

```bash
SEC_AGENT_PROFILE_ENV=.env bash scripts/cloud/sec_agent_interactive.sh config-full-source-api
```

## One-Shot Memo Demo

```bash
SEC_AGENT_PROFILE_ENV=.env bash scripts/cloud/sec_agent_interactive.sh ask-full-source-api \
"Using SEC 10-K, latest 10-Q, 8-K earnings releases, and the last three months of market snapshots, compare NVDA, AMD, MSFT, AMZN, and GOOGL across AI fundamentals, management commentary, market reaction, and valuation divergence."
```

This path uses the same evidence pipeline as the session demo, but it is driven as a single fixed DAG: query planning, retrieval, exact-value ledger, coverage, judgment plan, synthesis, gates, and rendering.

## Multi-Turn Session Demo

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

The session path adds the tool/function-call controller. The API model chooses high-level actions; the Python harness executes them, updates session state, applies artifact invalidation rules, and decides whether a follow-up can reuse prior evidence or needs a rerun.

## Saved-Run Inspection

After a full-source run completes, the readiness aggregator can inspect the saved run directory:

```bash
python scripts/evaluate_sec_agent_resume_closeout_readiness.py \
  --saved-full-source-run-dir eval/sec_cases/outputs/<run>/<case> \
  --require-full-source-artifacts \
  --timeout-s 900
```

This check is useful when you want to verify that a run produced the expected query contract, retrieved context, ledger, coverage matrix, judgment plan, synthesis, gates, rendered answer, and session artifacts.

## Demo Story

A strong demo should make these boundaries visible:

- the user asks a free-form investment-research question;
- the query planner returns a bounded contract, not unstructured prose;
- in sessions, the API model chooses high-level tools through OpenAI-compatible tool/function calls;
- the harness owns actual execution, state changes, scope invalidation, and artifact references;
- retrieval and ledgers provide SEC, 8-K, and market-snapshot evidence separately;
- the final memo labels source tiers, period roles, market `as_of_date`, and coverage gaps;
- follow-up turns reuse the active answer and evidence references instead of starting unrelated runs.

## Current Non-Production Boundary

- JSON-backed session state is suitable for local demos and single-process evaluation, not multi-user serving.
- Full-source quality depends on private source data and generated indexes, which are not included in the public repository.
- API model latency is provider-dependent; local optimization focuses on retrieval, ledger, coverage, and session overhead.
- Market snapshots are non-real-time and must carry `snapshot_id` and `as_of_date`.
