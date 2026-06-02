# 216 - Multi-agent Post-P6 Global Issue Register And P7 Plan

Date: 2026-06-01

Branch: `codex/api-model-call-architecture`

Locked baseline commit: `a956505 Add thesis pack memo projection gates`

Sensitive-data note: real model runs use API keys from the shell environment only. No key is written to repo files or artifacts.

## 1. Current Baseline

Post-P6 real DeepSeek smoke:

- Run: `20260601_sector_depth_p6_thesis_pack_smoke_deepseek_v0_3`
- Case: `ma_real_sector_ai_infra_full_chain_real_retrieval`
- Gate: pass
- Retrieval: real MCP / SEC search / BM25 / ObjectBM25 / BGE rerank, BGE `cuda`
- Tool calls: `9`
- Context rows: `174`
- Runtime ledger rows: `63`
- Specialist real-evidence quality: pass
- Supported ClaimCards: `15`, memo slots supported: `5/5`
- Memo Writer: pass, `2` attempts, first finish `length`, `18,709` tokens
- Verifier: pass, `8,739` tokens
- Final rendered memo: `3,468` chars, `4` memo claims, evidence refs visible
- Audit flags: `high_total_token_cost`, `memo_surface_says_evidence_thin`

P6 fixed the previous high-impact quality issue: the final surface is no longer a short bounded summary. Remaining work should optimize cost and decision quality without loosening source boundaries.

## 2. Remaining Issues By Layer

### Orchestration / Scheduling

- `deep_research` still activates all four specialists when the query explicitly asks for fundamentals, industry transmission, market reaction, and risk. This is often semantically correct, but current supporting specialists receive near-primary context budgets.
- `supporting` currently means “run normally” in `specialist_activation_decisions`; it does not yet reduce prompt or data-view budgets.
- Market and Risk are useful lenses, but should have narrower payloads unless they are the primary research objective.

### Retrieval / RAG / Chunk Flow

- Real retrieval is working and BGE uses CUDA, but sector-depth cases still retrieve hundreds of rows before specialist compression.
- The current SEC search runtime policy improved mode-aware caps, but repeated route families can still produce broad evidence packs for specialists that only need top discriminating rows.
- Current audit reports tool rows and BGE candidates, but not enough per-specialist prompt-row budget telemetry.

### Data View / Context Handling

- Risk Specialist data view sees up to `32` rows in deep research, then Specialist prompt caps to `24`; this is still expensive for a supporting stress-test role.
- Industry/Supply-Chain receives relationship evidence correctly, but it remains the most expensive specialist (`14,664` tokens in the baseline). Relationship rows should stay protected; generic non-relationship rows should not grow unchecked.
- Memo Writer now consumes `memo_thesis_pack`, but still needs one repair after first `length`; input compression helped but did not eliminate the retry.

### Specialist Layer

- Specialists understand upstream task cards and evidence boundaries. The issue is not comprehension.
- Token conversion is uneven: `15` supported ClaimCards cost about `43.8k` specialist tokens. This is acceptable for diagnostic deep research, too high for an interactive Fin Agent default.
- Supporting specialists should be budgeted as lenses: enough to produce 1-3 high-value claims, not a full parallel memolet.

### Aggregator / Memo / Verifier

- Aggregator now creates `memo_thesis_pack`, which improved final memo density.
- Verifier is still an expensive safety gate (`8,739` tokens) and sees a broad verified inventory. It should verify final rendered/memo claims against a minimal ref inventory, not re-read most of the judgment inventory.
- Final memo now exposes claims and refs, but the surface still uses evidence-thin language because the model overweights source-boundary caveats like missing audited annual filings.

### Multi-turn / Product Behavior

- P6 was validated on one sector-depth single-turn smoke. The non-contiguous multi-turn and artifact-resume behavior still need a post-P6 regression.
- The current agent is closer to a useful Fin Agent, but it still behaves like a full evidence factory for some interactive requests.

## 3. Hypotheses

- H1: Priority-aware specialist data-view and prompt budgets will reduce total tokens without lowering real-evidence quality, because supporting Market/Risk agents can produce useful claim cards from fewer rows.
- H2: Verifier can consume a memo-claim/ref projection instead of the broad judgment inventory, reducing verifier tokens while preserving safety.
- H3: Source-boundary caveats need severity tagging. “Unaudited 8-K” and “missing audited annual filing” should not automatically make the final memo read evidence-thin when latest quarterly/company-authored evidence is acceptable for the user task.
- H4: Token-per-ClaimCard and token-per-rendered-claim should become first-class eval metrics, otherwise future fixes can pass gates while wasting model budget.
- H5: Multi-turn quality will depend more on context invalidation and artifact reuse than on adding more specialists.

## 4. P7 Execution Order

### P7.1 Priority-aware Specialist Payload Budget

Implement first.

- Add priority-aware data-view row caps:
  - primary deep research: keep current `32`
  - supporting deep research: lower default budget
  - conditional / low: lower further
- Add priority-aware Specialist prompt row caps:
  - primary deep research: keep current `24`
  - supporting deep research: lower default prompt cap
  - preserve Industry relationship minimum rows when relationship graph evidence is required
- Emit priority and budget policy in `input_budget`.

Gate:

- Unit tests prove primary fundamental deep-research budget remains unchanged.
- Unit tests prove supporting Risk deep-research budget is lower and source-balanced.
- Existing Specialist / Step17 eval tests remain green.
- One real AI infra smoke should keep route / real evidence quality / rendered memo refs passing and should reduce supporting specialist tokens.

### P7.2 Verifier Minimal Projection

- Build a compact verifier input from final `memo_claims`, evidence refs, source families, and only the source-boundary notes needed to validate those refs.
- Add a verifier token threshold diagnostic.

Gate:

- Verifier deterministic safety tests remain green.
- Real smoke keeps claim verification pass and reduces verifier tokens.

### P7.3 Source-boundary Severity

- Tag missing evidence / unaudited evidence as `blocking`, `confidence_caveat`, or `watch_item`.
- Renderer should surface blocking gaps differently from normal recency/source caveats.

Gate:

- Final memo should not say evidence is broadly thin when all required source families are present and verifier passes.

### P7.4 Cost-quality Eval Metrics

- Add tokens per supported ClaimCard, tokens per rendered memo claim, memo chars per token, and repair-token ratio to output-quality audit.

Gate:

- Audit markdown makes cost regressions visible without reading raw JSON.

### P7.5 Multi-turn Post-P6 Regression

- Run focused multi-turn and sector-depth follow-up cases after P7.1/P7.2 to ensure context reuse and specialist gating still behave.

Gate:

- No forbidden stale ticker carryover.
- Rendered memo claims and refs remain visible.

## 5. Immediate Action

Proceed with P7.1 only in this slice. Do not change retrieval caps or Memo Writer prompt again until priority-aware specialist payload budgets are measured.

## 6. P7.1 Implementation Result

Implemented:

- Added priority-aware data-view caps:
  - primary deep research remains `32`
  - supporting deep research defaults to `20`
  - supporting standard memo defaults to `16`
  - conditional / low priorities have lower default caps
- Added priority-aware Specialist prompt caps:
  - primary deep research remains `24`
  - supporting deep research defaults to `16`
  - supporting standard memo defaults to `12`
- Specialist `input_budget` now reports `agent_priority` and priority-aware budget policy.
- Risk rows remain source-balanced after the lower supporting budget.

Deterministic gates:

- `python -m pytest tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_specialist_llm.py -q` -> `38 passed`.

Real DeepSeek smoke:

| Run | Gate | Tool calls | Context rows | Ledger rows | Specialist tokens | Memo tokens | Verifier tokens | Total tokens | Rendered chars | ClaimCards |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| P6 v0.3 `20260601_sector_depth_p6_thesis_pack_smoke_deepseek_v0_3` | pass | 9 | 174 | 63 | 43,780 | 18,709 | 8,739 | 82,974 | 3,468 | 15 |
| P7.1 `20260601_sector_depth_p7_priority_budget_smoke_deepseek_v0_1` | pass | 11 | 192 | 69 | 43,139 | 16,768 | 7,853 | 79,688 | 3,293 | 16 |

Specialist details:

- Fundamental primary: `32` rows, `11,574` -> `11,227` tokens.
- Industry primary: `32` rows, `14,664` -> `15,054` tokens.
- Market supporting: `4` -> `8` rows, `6,674` -> `7,894` tokens. This rose because this run retrieved more market rows, not because of the cap.
- Risk supporting: `32` -> `20` rows, `10,868` -> `8,964` tokens.

Decision:

- Keep P7.1. It is directionally positive and preserves all safety / real-evidence / rendered-ref gates.
- Do not rely on P7.1 alone for cost control. Total token cost remains high, and the audit still flags `high_total_token_cost`.
- Next highest-leverage step is P7.2 Verifier minimal projection, followed by P7.4 cost-quality metrics.

## 7. P7.2 Implementation Result

Implemented:

- Added `sec_agent_verifier_minimal_projection_v0.1`.
- Verifier LLM now receives `verifier_projection` instead of the broad `verified_judgment_inventory`.
- The projection contains only:
  - compact final `memo_answer`
  - memo-claim referenced ClaimCards
  - allowed evidence refs
  - final memo unsupported-excluded items
  - source-boundary notes relevant to memo source families or blocking notes
  - deterministic verification summary
- Deterministic `verify_multi_agent_memo_draft` remains the hard safety gate before Verifier LLM; the LLM verifier still cannot override deterministic failures.
- LangGraph summary and Step17 `agent_audit.verifier.input_projection` now expose projection stats for later cost-quality audits.

Deterministic gates:

- `python -m pytest tests/test_multi_agent_memo_llm_repair.py -q` -> `17 passed`.
- `python -m pytest tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_multi_agent_langgraph_routing.py -q` -> `33 passed`.

Real DeepSeek smoke:

| Run | Gate | Tool calls | Context rows | Ledger rows | Specialist tokens | Memo tokens | Verifier tokens | Total agent tokens | Rendered chars | Memo claims |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| P7.1 `20260601_sector_depth_p7_priority_budget_smoke_deepseek_v0_1` | pass | 11 | 192 | 69 | 43,139 | 16,768 | 7,853 | 79,688 | 3,293 | 4 |
| P7.2 `20260601_sector_depth_p7_verifier_projection_smoke_deepseek_v0_1` | pass | 10 | 192 | 69 | 43,405 | 19,201 | 5,214 | 79,711 | 3,820 | 4 |

Decision:

- Keep P7.2. Verifier token cost dropped by `2,639` tokens while claim verification, Specialist real-evidence quality, rendered memo claims, and evidence refs stayed green.
- P7.2 does not reduce total cost by itself because Memo Writer still used `2` attempts and spent more tokens in this run. Total agent tokens were effectively flat (`79,688` -> `79,711`).
- Next step should be P7.4 cost-quality metrics and then a Memo Writer retry/length root-cause pass, not another Verifier prompt change.

## 8. P7.4 Cost-quality Metrics Result

Implemented:

- Extended `scripts/audit_multi_agent_output_quality.py` with `cost_quality_stats`:
  - total tokens per supported ClaimCard
  - Specialist tokens per supported ClaimCard
  - total tokens per rendered memo claim
  - memo chars per total token
  - Memo Writer and Verifier token share
  - Memo Writer attempt / repair-attempt ratio
  - Memo Writer repair-token ratio when per-call token diagnostics are available
- Markdown audit table now shows `Cost/claim` and `Chars/token`.
- Added flags and hypotheses for:
  - `low_rendered_claim_token_efficiency`
  - `low_claim_card_token_efficiency`
  - `low_memo_chars_per_token`
  - `memo_writer_retry_cost_present`

Deterministic gate:

- `python -m pytest tests/test_multi_agent_output_quality_audit.py -q` -> `7 passed`.

Offline audit on P7.2 real smoke:

- Command: `python scripts\audit_multi_agent_output_quality.py eval\sec_cases\outputs\multi_agent_real_llm_chain_eval\20260601_sector_depth_p7_verifier_projection_smoke_deepseek_v0_1\real_chain_eval_summary.json --artifact-root eval\sec_cases\outputs\multi_agent_real_llm_chain_eval\20260601_sector_depth_p7_verifier_projection_smoke_deepseek_v0_1`
- Total tokens: `79,711`
- Supported ClaimCards: `16`
- Rendered memo claims: `4`
- Tokens per supported ClaimCard: `4,981.94`
- Tokens per rendered memo claim: `19,927.75`
- Memo chars per total token: `0.04792`
- Memo Writer token share: `0.24088`
- Verifier token share: `0.06541`
- Memo Writer attempts: `2`, repair-attempt ratio `0.5`
- New quality flags: `low_rendered_claim_token_efficiency`, `low_memo_chars_per_token`, `memo_writer_retry_cost_present`

Decision:

- Keep P7.4. It does not change chain behavior, but it makes cost/quality trade-offs visible from saved artifacts.
- The next engineering target should be Memo Writer retry/length reduction and rendered memo density, because Verifier is no longer the dominant downstream cost after P7.2.

## 9. Memo Writer Max-token Diagnostic

Diagnostic change tested but not kept:

- Hypothesis: raising the Step17 / Memo Writer output budget to `3400` tokens could let DeepSeek close the first MemoDraft JSON and avoid the `length -> repair` cycle.
- Test run: `20260601_sector_depth_p7_memo_writer_3400_smoke_deepseek_v0_1`
- Gate: pass
- Tool calls: `11`
- Memo Writer: still `2` attempts, `length,stop`
- Memo Writer tokens: `20,043` versus P7.2 baseline `19,201`
- Verifier tokens: `4,616` versus P7.2 baseline `5,214`
- Total agent tokens: `79,986` versus P7.2 baseline `79,711`
- Rendered chars: `3,565` versus P7.2 baseline `3,820`

Decision:

- Do not keep the `3400` max-token bump. It did not remove the retry and increased Memo Writer / total token cost.
- The retry root cause is not only output budget. Next fix should make the first Memo Writer output schema smaller and more deterministic, likely by emitting a minimal structured memo skeleton first and moving optional prose expansion/rendering to a separate bounded renderer step.
