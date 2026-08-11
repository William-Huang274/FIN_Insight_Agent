# SEC Agent API Memo V1 5-Case Eval

## Problem
The representative NVDA `api_memo_v1` prompt passed deterministic gates, but it was still a single-case validation. The next required check was the full 5-case memo-quality eval set:

- NVDA growth and competitors
- AMZN AWS and capex
- META AI investment, R&D, capex, and profit quality
- JPM net interest income and credit risk
- LLY growth quality, R&D, product mix, and risk factors

## Run
- Environment: cloud `westd`, `/root/autodl-tmp/FIN_Insight_Agent`
- Run id: `20260522_api_memo_v1_5case_125123`
- Runner: `/tmp/run_sec_agent_5case_memo_eval.sh`
- Synthesis profile: `api_memo_v1`
- Model: `deepseek-v4-pro`
- Retrieval: BM25 + BGE-M3 rerank on CUDA
- Scope: `TICKERS=ALL`, `YEARS=2023,2024,2025`, 10-K sources
- Output root: `reports/quality/20260522_api_memo_v1_5case_125123`

No API key, SSH password, or temporary credential was written into repo files.

## Results

| Case | Artifact | Gates | Memo Quality | Status |
|---|---|---:|---:|---|
| `memo_nvda_growth_competitors_001` | `eval/sec_cases/outputs/interactive_sec_agent/20260522_125201_60a9e00112` | 12/12 | 0.8270 | pass |
| `memo_amzn_aws_capex_002` | `eval/sec_cases/outputs/interactive_sec_agent/20260522_125556_c52f12a630` | 11/12 | 0.9005 | named-fact fail |
| `memo_meta_ai_capex_rd_003` | `eval/sec_cases/outputs/interactive_sec_agent/20260522_125958_961ed825c6` | 11/12 | 0.8590 | named-fact fail |
| `memo_jpm_rate_credit_004` | `eval/sec_cases/outputs/interactive_sec_agent/20260522_130400_914dee0e50` | 11/12 | 0.9440 | named-fact fail |
| `memo_lly_growth_quality_005` | `eval/sec_cases/outputs/interactive_sec_agent/20260522_130827_ffe40ede99` | 12/12 | 0.8980 | pass |

Aggregate:
- Completed: `5/5`
- All deterministic gates green: `2/5`
- `qwen_answer_ratio`: `1.0` for every case
- Ledger repairs: `0`
- Mean memo quality: `0.8857`

## Failure Diagnosis
All deterministic failures were `named_fact_gate_pass`:

- AMZN: `peer_readthrough` introduced `Microsoft`, `MSFT`, `Google`, `GOOGL`, `NVIDIA`, `NVDA`, `Oracle`, `ORCL`, and `IBM` without cited evidence supporting those peer mentions. This is model overreach in peer readthrough when the Evidence Pack does not include peer-company context.
- META: one `why_it_matters` item mentioned `Reality Labs`; the cited evidence did not support that named fact. This is a source-boundary miss in memo reasoning.
- JPM: retrieval/ledger selection drifted into an employee diversity table (`JPMorgan Chase Senior level employees`, `White`) and the answer also mentioned unsupported peer banks and banking metric names in watch items. This is not just output phrasing; it indicates the planner/evidence coverage layer did not reliably target net interest income and credit-risk evidence.

## Decision
`api_memo_v1` is validated as a better synthesis interface than the earlier audit-style answer:

- It keeps all five runs in `answered_qwen9b`.
- It avoids parse fallback and ledger repair.
- It clears memo-quality threshold on all cases.

But it is not yet ready to claim full 5-case constrained reliability:

- Deterministic gate pass rate is only `2/5`.
- The main blocker is Evidence Pack / named-fact support for cross-company and financial-sector questions.
- Do not patch this by adding more fallback rules. The next fix should improve planner/evidence coverage and peer-readthrough source policy.

## Next Work
- For peer-readthrough, require cited peer evidence or render peer analysis as `insufficient current evidence`.
- For financial-sector questions, improve planner metric-family ontology and retrieval targets for `net_interest_income`, `credit_loss_provision`, `net_charge_off`, `allowance`, and `loan portfolio`.
- Add an Evidence Coverage Matrix failure mode that blocks confident synthesis when required task evidence is missing or contaminated by irrelevant tables.
- Tighten memo-quality scorer so unresolved sanitizer phrases such as `当前引用未保留的精确比例` and irrelevant evidence artifacts reduce `format_polish` and `evidence_usefulness`.
