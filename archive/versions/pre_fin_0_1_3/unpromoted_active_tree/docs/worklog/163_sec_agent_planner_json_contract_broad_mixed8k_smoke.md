# 163 SEC Agent Planner JSON Contract And Broad Mixed-8K Smoke

Date: 2026-05-25

## Problem

- The mixed 10-K/10-Q/8-K chain had one remaining instability after full30 8-K coverage: DeepSeek planner could occasionally return a valid JSON prefix that was truncated at `finish_reason=length`, causing the run to fall back to the heuristic planner.
- The correct fix is not a business fallback. The planner output contract itself needed to be smaller, bounded, and retried on length truncation.
- A broader cross-industry smoke was needed before considering the next source family, because prior successful runs were concentrated on AI/tech-adjacent prompts.

## Decisions

- Compress the planner schema:
  - Remove `evidence_gaps` from the requested planner JSON schema.
  - Cap `decomposed_tasks` at 5.
  - Cap each `question_zh` at 80 Chinese characters.
  - Cap caveats/forbidden-claim lists and short query lists.
- Increase normal planner token budget from `1800` to `3000`; add `PLANNER_RETRY_MAX_TOKENS=4000`.
- If planner parsing fails because output is length-truncated, retry once with the larger budget and the same planner prompt/schema.
- Add `PLANNER_FAIL_CLOSED=1` for tests/smokes where heuristic fallback would hide the planner-stability issue.
- Keep 8-K as explanation/management-commentary evidence with explicit `company-authored unaudited` boundary. Do not promote 8-K into audited/reviewed exact-value ledger authority.
- Fix final memo normalization to align with Judgment Plan strength:
  - Restore plan-aligned legacy `decision_drivers` if API memo field cleanup removes them.
  - Cap `direct_answer` / `investment_thesis` language when `main_judgment.strength` is `weak` or `medium`; avoid winner-style phrases that overstate the validated plan.

## Implementation

- `scripts/cloud/sec_agent_interactive.py`
  - Added planner defaults: `PLANNER_DEFAULT_MAX_TOKENS=3000`, `PLANNER_DEFAULT_RETRY_MAX_TOKENS=4000`, task/list/field-length caps.
  - Added `--planner-retry-max-tokens` and `--planner-fail-closed`.
  - Compact planner prompt/schema now instructs no `evidence_gaps`, at most 5 tasks, short questions/caveats, and no markdown/comments.
  - Planner normalization clamps tasks, caveats, forbidden claims, metric/qualitative queries, and retained evidence gaps from older/fallback paths.
  - Length-truncated planner parse failures trigger one same-prompt retry at the higher token budget before any fallback path.
  - Config summary now records planner retry/fail-closed settings.
- `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
  - Added `_ensure_plan_legacy_drivers(...)` to keep API memo v1 outputs gate-compatible after cleanup.
  - Added `_constrain_memo_language_to_judgment_plan_strength(...)` to enforce Judgment Plan strength in memo text and source limitations.
- `tests/test_sec_agent_8k_earnings_source.py`
  - Added planner prompt/schema regression.
  - Added planner output limit regression.
  - Added length-truncated planner retry regression.
  - Added synthesis regression for weak-plan memo language and restored plan drivers.

## Verification

Local:

```bash
python -m pytest tests/test_sec_agent_8k_earnings_source.py tests/test_sec_agent_10q_source_contract.py -q
python -m py_compile scripts/cloud/sec_agent_interactive.py scripts/cloud/sec_agent_context_session_cli.py scripts/run_sec_eval_synthesis_qwen9b_backend.py
```

Result:

- `73 passed`.
- `py_compile` passed.

Cloud:

```bash
/root/autodl-tmp/envs/sec-agent-cu128/bin/python -m pytest tests/test_sec_agent_8k_earnings_source.py tests/test_sec_agent_10q_source_contract.py -q
/root/autodl-tmp/envs/sec-agent-cu128/bin/python -m py_compile scripts/cloud/sec_agent_interactive.py scripts/cloud/sec_agent_context_session_cli.py scripts/run_sec_eval_synthesis_qwen9b_backend.py
```

Result:

- `73 passed`.
- `py_compile` passed.

## Broad Mixed-8K Smoke

Prompt:

```text
结合最新10-Q和8-K业绩新闻稿，比较JPM、CVX、PG、GE、LLY、WMT、TXN的最新业绩驱动、现金流或资本开支压力、管理层解释和证据边界；只使用SEC证据，不使用市场价格或外部预测。
```

Cloud run:

- Run root: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260525_164513_6f44469788`
- Log: `/root/autodl-tmp/FIN_Insight_Agent/reports/logs/20260525_planner_contract_broad_mixed8k_rerun.log`
- Scope: `JPM,CVX,PG,GE,LLY,WMT,TXN`, `YEARS=2026`, `forms=10-K,10-Q,8-K`
- Source policy: `SEC_PRIMARY_MIXED_WITH_8K_EARNINGS`
- Planner: `llm:deepseek:ok`
- Planner trace:
  - `status=parsed`
  - `finish_reason=stop`
  - `requested_max_tokens=3000`
  - `output_tokens=1182`
  - `retry=false`
- Evidence:
  - `runtime_evidence_pack.json` contains 8 `8K_EARNINGS::*` references.
  - Rendered answer mentions 8-K 4 times and cites JPM 2026 8-K earnings release Exhibit 99.1 as `company-authored unaudited`.
- Final gates:
  - `ok=True`
  - `pass=12`
  - `fail=[]`
  - `answer_vs_judgment_plan`: `pass_count=1`, `fail_count=0`
- Runtime:
  - `elapsed=136.63 sec`
  - `ledger rows=38`
  - `context rows=120`

## Interpretation

- The planner JSON-only path is stable for this broader mixed-source prompt without heuristic fallback.
- 8-K evidence is now used in the intended way: it supports management explanation and source-boundary context, while exact financial values remain controlled by the 10-K/10-Q ledger.
- The remaining conservatism in the answer is expected because the chain is still SEC-only: no market prices, valuation multiples, external consensus, macro data, or non-SEC news are available.

## Next Stage Candidate: Market Snapshot

Proceed only after planning the source contract first.

Recommended scope:

- Add a non-real-time `market_snapshot` source tier with explicit `as_of_date`.
- Snapshot fields may include price, market cap, returns, valuation multiples, analyst consensus, or macro/sector indicators only if fetched from a deterministic source and stamped with retrieval time.
- DeepSeek may reason over the snapshot, but facts must come from the snapshot artifact, not model memory.
- Gates must enforce:
  - every market/valuation claim carries `as_of_date`;
  - market snapshot claims are not mixed with SEC filing facts without source-boundary labeling;
  - no real-time or unstamped market assertions;
  - SEC ledger remains the authority for reported company financials.

## Safety Notes

- No API keys, passwords, or cloud credentials were written to this document.
- Cloud run artifacts and generated SEC/private data remain generated artifacts and should not be staged by default.
