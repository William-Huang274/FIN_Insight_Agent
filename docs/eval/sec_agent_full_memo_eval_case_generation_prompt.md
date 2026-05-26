# SEC Agent Full Memo Eval Case Generation Prompt

Use this document as a copy-paste prompt for GPT-5.5 or another strong model to generate the next memo-quality evaluation cases.

## Current Project State

We are building a SEC-only investment memo agent for `FIN_Insight_Agent`.

The current pipeline is:

- Query Contract planner selects companies, years, task type, peer scope, metric families, and source boundaries.
- Retrieval uses the local SEC 10-K corpus for 2023-2025.
- BGE-M3/reranker and structured-object retrieval build the evidence context.
- Runtime Exact-Value Ledger captures citation-grade metric and evidence rows.
- Evidence Coverage Matrix records covered and missing tickers, years, peer tickers, and metric families.
- Judgment Plan defines memo drivers and support evidence before final synthesis.
- DeepSeek API currently writes `api_memo_v1` answers through the LLM Gateway.
- Deterministic gates then check named facts, ledger grounding, semantic contract, answer-vs-Judgment-Plan support alignment, and memo quality.

The current formal memo eval set is only 5 cases:

- `memo_nvda_growth_competitors_001`
- `memo_amzn_aws_capex_002`
- `memo_meta_ai_capex_rd_003`
- `memo_jpm_rate_credit_004`
- `memo_lly_growth_quality_005`

The latest cloud run on these 5 cases passed all gates:

- `5/5` all-gates green
- each case passed `12/12` gates
- `mean_memo_quality=0.88312`

Recent fixes that should now be stress-tested rather than re-fixed by the eval design:

- `evidence_pack` is now a first-class graph artifact.
- Judgment Plan support IDs now include `source_evidence_id`, `evidence_id`, and `object_id`.
- Memo-derived legacy drivers are split into Judgment-Plan-aligned drivers when one prose driver maps to multiple plan drivers.
- Resume routing preserves the provider/model route from saved graph state.

## Goal

Generate 25 additional memo eval cases that can be appended to the existing 5-case set to form a `full30` memo-quality eval.

The goal is not to test whether the model can memorize facts. The goal is to expose whether the agent can:

- select the right SEC-only scope from a natural user query;
- handle single-company and peer-comparison investment memos;
- distinguish segment metrics from consolidated company metrics;
- cite evidence and ledger-backed facts without hallucinated named facts;
- preserve answer-vs-Judgment-Plan support alignment;
- avoid entity bleed between peers;
- state counterarguments, watch items, and source limitations explicitly;
- handle missing or partial SEC evidence without overclaiming;
- remain inside 2023-2025 10-K source boundaries.

## Allowed Data Universe

Use only these tickers and only fiscal years `2023`, `2024`, and `2025`.

```text
MSFT, AAPL, NVDA, GOOGL, META, AMZN,
AVGO, CSCO, INTC, AMD, QCOM, TXN, AMAT, MU,
INTU, ADP, ADBE, PANW, CRWD, SNOW,
JPM, V,
JNJ, LLY,
CAT, GE,
WMT, PG,
XOM, CVX
```

Use only SEC 10-K evidence. Do not require market prices, valuation multiples, analyst consensus, earnings calls, news, 10-Qs, 8-Ks, or web sources.

## Existing Case Schema

Each generated case must be one JSON object per line using exactly this shape:

```json
{
  "case_id": "memo_<short_topic>_<number>",
  "category": "single_company_memo | company_peer_memo | cross_company_memo | financials_memo | pharma_memo | industrial_memo | consumer_memo | energy_memo | software_memo | semis_memo | source_boundary_memo",
  "query": "Natural Chinese user query.",
  "expected": {
    "primary_tickers": ["TICKER"],
    "peer_tickers_any_of": ["OPTIONAL_PEER_TICKER"],
    "years": [2023, 2024, 2025],
    "source_policy": "SEC_ONLY_10K",
    "memo_question": "A sharper investment-memo question that the answer should resolve.",
    "required_memo_sections": [
      "direct_answer",
      "investment_thesis",
      "what_changed",
      "why_it_matters",
      "counterarguments",
      "watch_items",
      "source_limitations"
    ],
    "required_insight_terms": [
      ["term alternative A", "term alternative B"],
      ["another concept", "synonym"]
    ],
    "required_evidence_roles": [
      "core_facts",
      "management_explanation",
      "risk_or_counterevidence",
      "missing_evidence"
    ],
    "disallowed_sources": [
      "stock_price",
      "valuation",
      "analyst_consensus",
      "earnings_call",
      "news",
      "10-Q",
      "8-K"
    ],
    "watch_item_terms": [
      ["watch item concept", "synonym"]
    ],
    "counterargument_terms": [
      ["counterargument concept", "synonym"]
    ]
  }
}
```

For peer-comparison cases, include `"peer_readthrough"` in `required_memo_sections` and include `"peer_contrast"` in `required_evidence_roles`.

Do not add new top-level fields unless explicitly requested. Do not output comments inside JSONL.

## Coverage Requirements For The 25 New Cases

Design exactly 25 new cases with IDs `memo_..._006` through `memo_..._030`.

Use this target distribution:

- 7 single-company memos across under-tested companies.
- 8 peer or cross-company comparison memos with 2-4 primary or peer tickers.
- 4 sector/domain memos that stress non-tech domains: banking/payments, pharma/healthcare, industrials, energy, consumer.
- 3 source-boundary or partial-evidence memos where a good answer must say what 10-K evidence cannot prove.
- 3 hard ambiguity cases where the query is natural and slightly underspecified, but still answerable by choosing a conservative SEC-only scope.

Include at least one case for each of these risk themes:

- cloud/AI capex versus margin or cash-flow pressure;
- semiconductor peer roles without mixing GPU, ASIC, CPU, memory, and equipment evidence;
- SaaS/subscription quality versus growth deceleration;
- cybersecurity growth quality and operating leverage;
- banking or payments quality without using stock/valuation data;
- pharma product concentration, pipeline/R&D, patent or regulatory risk;
- industrial backlog/order/demand durability;
- energy cash flow/capex/reserve or commodity-cycle caveats;
- retail or consumer margin/inventory/cash-flow quality;
- source limitation where SEC 10-K cannot answer market share, current quarter momentum, stock attractiveness, or exact AI revenue if not disclosed.

Avoid near-duplicates of the 5 existing cases. You may reuse a ticker only if the topic is materially different.

## Case Quality Rules

Each case should be hard enough to catch real failures but fair enough for a SEC-only agent.

Good cases:

- Ask for a judgment, not a fact lookup.
- Require causal interpretation, not only a metric table.
- Require at least one counterargument and at least two watch items.
- Can be evaluated using 2023-2025 10-K text.
- Use natural Chinese phrasing, including some casual user wording.
- Make source limits explicit when the user asks something SEC 10-K cannot fully answer.
- Keep peer scope bounded; avoid asking for all 30 companies in one case.

Bad cases:

- Require real-time facts, 2026 results, stock prices, market caps, current valuation, analyst estimates, or news.
- Require exact facts not likely present in 10-K filings.
- Depend on knowing a product launch date from outside SEC filings.
- Use too many companies, which turns the memo into a broad survey instead of an evidence-grounded memo.
- Force exact wording that would make the scorer brittle.

## Expected Field Guidance

`required_insight_terms` should be semantic concept groups, not exact answer sentences. Each inner list means "any of these terms is acceptable."

For example:

```json
[
  ["operating margin", "经营利润率", "operating income", "盈利能力"],
  ["capital expenditures", "capex", "property and equipment", "资本开支"],
  ["source limitation", "证据边界", "not disclosed", "未披露"]
]
```

`watch_item_terms` should name what a future analyst would monitor, such as:

- margin;
- capex;
- free cash flow;
- segment revenue;
- backlog;
- orders;
- inventory;
- customer concentration;
- allowance or credit losses;
- R&D;
- regulatory approval;
- commodity prices;
- reserves;
- product concentration.

`counterargument_terms` should name evidence that could weaken the memo thesis, such as:

- segment definitions are not comparable;
- growth is concentrated in one product or customer group;
- capex/depreciation may pressure free cash flow;
- customer concentration or demand pull-forward;
- commodity cycle or price sensitivity;
- regulatory/patent/pipeline risk;
- credit normalization or deposit funding pressure;
- inventory or margin pressure.

## Output Format

Return two sections:

1. A compact coverage table with 25 rows: `case_id`, category, primary tickers, peer candidates, risk theme.
2. A fenced `jsonl` block containing exactly 25 JSONL lines.

Before finalizing, self-check:

- all lines parse as JSON;
- all tickers are in the allowed universe;
- all years are exactly `[2023, 2024, 2025]`;
- all `source_policy` values are `SEC_ONLY_10K`;
- no case requires external sources;
- peer cases include `peer_readthrough` and `peer_contrast`;
- no case duplicates the existing 5 topics.

## Prompt To Use

Copy everything below into GPT-5.5.

```text
You are designing evaluation cases for a SEC-only investment memo agent.

Project state:
- The agent answers natural-language investment memo questions using only 2023-2025 SEC 10-K evidence.
- The pipeline has Query Contract planning, retrieval, BGE-M3 reranking, runtime Exact-Value Ledger, Evidence Coverage Matrix, Judgment Plan, DeepSeek API `api_memo_v1` synthesis, and deterministic gates.
- The current 5-case memo eval is already all-green: 5/5 cases, 12/12 gates per case, mean memo quality 0.88312.
- We now need 25 additional cases to append to the existing 5 and form a full30 memo eval.
- The new cases should stress generalization, not retest only the fixed 5-case failures.

Existing cases to avoid duplicating:
1. NVDA growth drivers and competitors.
2. AMZN AWS plus capex.
3. META AI investment, R&D, capex, and profit quality.
4. JPM net interest income and credit risk.
5. LLY growth quality, R&D, product mix, and risk.

Allowed tickers:
MSFT, AAPL, NVDA, GOOGL, META, AMZN,
AVGO, CSCO, INTC, AMD, QCOM, TXN, AMAT, MU,
INTU, ADP, ADBE, PANW, CRWD, SNOW,
JPM, V,
JNJ, LLY,
CAT, GE,
WMT, PG,
XOM, CVX

Allowed years: 2023, 2024, 2025.
Allowed source policy: SEC_ONLY_10K.
Disallowed source dependencies: stock prices, valuation multiples, analyst consensus, earnings calls, news, 10-Q, 8-K, current-quarter data, 2026 data.

Generate exactly 25 new cases with IDs `memo_..._006` through `memo_..._030`.

Use exactly this JSON shape for each JSONL line:
{
  "case_id": "memo_<short_topic>_<number>",
  "category": "single_company_memo | company_peer_memo | cross_company_memo | financials_memo | pharma_memo | industrial_memo | consumer_memo | energy_memo | software_memo | semis_memo | source_boundary_memo",
  "query": "Natural Chinese user query.",
  "expected": {
    "primary_tickers": ["TICKER"],
    "peer_tickers_any_of": ["OPTIONAL_PEER_TICKER"],
    "years": [2023, 2024, 2025],
    "source_policy": "SEC_ONLY_10K",
    "memo_question": "A sharper investment-memo question that the answer should resolve.",
    "required_memo_sections": ["direct_answer", "investment_thesis", "what_changed", "why_it_matters", "counterarguments", "watch_items", "source_limitations"],
    "required_insight_terms": [["term alternative A", "term alternative B"], ["another concept", "synonym"]],
    "required_evidence_roles": ["core_facts", "management_explanation", "risk_or_counterevidence", "missing_evidence"],
    "disallowed_sources": ["stock_price", "valuation", "analyst_consensus", "earnings_call", "news", "10-Q", "8-K"],
    "watch_item_terms": [["watch item concept", "synonym"]],
    "counterargument_terms": [["counterargument concept", "synonym"]]
  }
}

For peer-comparison cases:
- include `"peer_readthrough"` in `required_memo_sections`;
- include `"peer_contrast"` in `required_evidence_roles`;
- keep the peer scope bounded to 2-6 candidate peers.

Target distribution:
- 7 single-company memos across under-tested companies.
- 8 peer or cross-company comparison memos with 2-4 primary or peer tickers.
- 4 sector/domain memos that stress non-tech domains: banking/payments, pharma/healthcare, industrials, energy, consumer.
- 3 source-boundary or partial-evidence memos where a good answer must say what 10-K evidence cannot prove.
- 3 hard ambiguity cases where the query is natural and slightly underspecified, but still answerable by choosing a conservative SEC-only scope.

At least one case must cover each risk theme:
- cloud/AI capex versus margin or cash-flow pressure;
- semiconductor peer roles without mixing GPU, ASIC, CPU, memory, and equipment evidence;
- SaaS/subscription quality versus growth deceleration;
- cybersecurity growth quality and operating leverage;
- banking or payments quality without using stock/valuation data;
- pharma product concentration, pipeline/R&D, patent or regulatory risk;
- industrial backlog/order/demand durability;
- energy cash flow/capex/reserve or commodity-cycle caveats;
- retail or consumer margin/inventory/cash-flow quality;
- source limitation where SEC 10-K cannot answer market share, current quarter momentum, stock attractiveness, or exact AI revenue if not disclosed.

Return two sections:
1. A compact coverage table with 25 rows: `case_id`, category, primary tickers, peer candidates, risk theme.
2. A fenced `jsonl` block containing exactly 25 JSONL lines.

Self-check before final answer:
- all JSONL lines parse as JSON;
- all tickers are in the allowed universe;
- years are exactly [2023, 2024, 2025];
- source_policy is SEC_ONLY_10K;
- no case requires external sources;
- peer cases include peer_readthrough and peer_contrast;
- no case duplicates the existing 5 topics.
```

## After GPT-5.5 Returns Cases

Recommended review flow:

1. Save the JSONL block as a candidate file, for example `eval_sets/sec_free_query_memo_quality_eval_full30_candidate_v1.jsonl`.
2. Verify every line parses as JSON.
3. Manually review whether any case requires non-10-K facts.
4. Compare against existing 5 cases and remove near-duplicates.
5. Only then append the accepted 25 cases to the existing 5-case eval set.

Do not promote the generated cases directly to mainline without a human review pass. The generated cases define what the gates will reward, so brittle or unfair expectations will distort the next full30 result.
