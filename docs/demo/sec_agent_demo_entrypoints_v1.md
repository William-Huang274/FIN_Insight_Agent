# FinSight-Agent Demo Entrypoints

[中文版本](sec_agent_demo_entrypoints_v1.zh-CN.md)

This document explains how to try the project. It does not repeat the full architecture. For architecture, start from [Architecture docs](../architecture/README.md). For custom data setup, see [Local custom data quickstart](../deployment/local_custom_data_quickstart.zh-CN.md).

## What The Public Repository Can Run

The public repository includes source code, tests, sample configs, evaluation contracts, and documentation. It does not include private data, generated indexes, run outputs, or API keys. After cloning, users can run structural checks immediately. The full research chain requires local data artifacts and a model route.

Tracked public content includes:

- `src/`, `scripts/`, and `configs/`;
- `tests/`, `eval_sets/`, and `docs/`;
- small fixtures and credential-free config examples.

Private or ignored content includes:

- `data/raw_private/`, `data/processed_private/`, `data/indexes/`, and `data/models_private/`;
- `eval/`, `reports/quality/`, `reports/demo/`, and `reports/logs/`;
- `.env`, API keys, SSH passwords, provider tokens, and temporary run files.

## Local Structural Check

Run this first after cloning the repository. It requires no API key and no private SEC or market data.

```powershell
python scripts/evaluate_sec_agent_resume_closeout_readiness.py --timeout-s 600
```

For a faster local contract check, skip the main-chain suite, pressure check, and latency profile:

```powershell
python scripts/evaluate_sec_agent_resume_closeout_readiness.py `
  --skip-main-chain-case-suite `
  --skip-context-load-smoke `
  --skip-latency-profile
```

Outputs are written under `reports/quality/resume_closeout/`, which is ignored by Git.

## Configure The Full Chain

The full chain requires three things:

1. local data artifacts for SEC filings, 8-K material, and market snapshots;
2. retrieval and reranking indexes, such as BM25, ObjectBM25, and optional BGE;
3. an API model route, such as DeepSeek or another OpenAI-compatible endpoint.

Inject API keys through shell environment variables only:

```bash
export LLM_BACKEND=deepseek
export MODEL_NAME=deepseek-v4-pro
export API_KEY_ENV=DEEPSEEK_API_KEY
export DEEPSEEK_API_KEY="<set-in-shell-only>"
```

Copy the profile template into an ignored `.env`:

```bash
cp configs/sec_agent_full_source_demo.env.example .env
```

Then replace manifest, index, market-snapshot, and model-route paths with local artifact paths.

## One-Shot Demo

The one-shot entrypoint demonstrates the full flow from question to research memo.

```bash
SEC_AGENT_PROFILE_ENV=.env bash scripts/cloud/sec_agent_interactive.sh ask-full-source-api \
"Using SEC 10-K, latest 10-Q, 8-K earnings releases, and the last three months of market snapshots, compare NVDA, AMD, MSFT, AMZN, and GOOGL across AI fundamentals, management commentary, market reaction, and valuation divergence."
```

After the run, inspect whether:

- the system produced a query contract and research scope;
- SEC retrieval, ObjectBM25, and BGE reranking actually ran;
- numeric ledgers and coverage checks were created;
- the final memo kept source boundaries and market snapshot dates;
- the run directory contains inspectable state and ledger artifacts.

## Multi-Turn Session Demo

The session entrypoint demonstrates context reuse, scope narrowing, evidence follow-up, and saved-result inspection.

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

Suggested flow:

1. Ask for a company comparison or industry-theme memo.
2. Ask the system to keep only a subset, such as NVDA and AMD, or expand only the risk section.
3. Ask about a specific number, evidence row, or coverage gap.
4. Use `/state` and `/context` to check whether the correct session state and evidence were reused.

## Saved-Run Inspection

If a full-chain run directory already exists, pass it to the readiness checker.

```bash
python scripts/evaluate_sec_agent_resume_closeout_readiness.py \
  --saved-full-source-run-dir eval/sec_cases/outputs/<run>/<case> \
  --require-full-source-artifacts \
  --timeout-s 900
```

This does not replace reading the memo, but it checks whether state files, coverage matrices, numeric ledgers, market-snapshot boundaries, and required artifacts are present.

## Current Boundaries

- Full-chain quality depends on the user's local artifacts and indexes.
- Market snapshots are offline data, not live quotes.
- Industry and relationship data support research hypotheses, not confirmed contracts or customer facts.
- JSON session storage is suitable for demos, development, and single-process evaluation. Multi-user serving should use a database, Redis, or another locked state store.
- The verifier can block unsupported or out-of-boundary conclusions, but it cannot invent facts that upstream retrieval did not find.
