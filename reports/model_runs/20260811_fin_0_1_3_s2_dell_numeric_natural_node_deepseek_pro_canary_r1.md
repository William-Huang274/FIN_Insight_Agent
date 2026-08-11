# Model Run: 20260811_fin_0_1_3_s2_dell_numeric_natural_node_deepseek_pro_canary_r1

## Summary

- Purpose: observe one current DeepSeek Pro demand-authenticity atom against the selected-Evidence numeric view.
- Status: formal terminal failed; substantive content passed offline audit except one exact English inflection.
- Run type: one exact-once live natural-node canary plus zero-call capture audit.
- Timestamp: 2026-08-11.

## Fixed scope

- Case/node: DELL / `dell_demand_authenticity_numeric_view_atom_canary_v1`.
- Evidence: E022 issuer disclosure, E018 HPE competitor read-through, E023 Dell pull-forward boundary.
- Model: `deepseek-v4-pro`, temperature 0, thinking disabled.
- Budget: 1 provider/model call, 1,800 output tokens, zero source/tool/retry/fallback/promotion.
- Admission and authority were separately issued, canonical, committed and preflighted before execution.

## Runtime observation

- Provider/model calls: `1/1`; transport attempts: `1`; retries/fallbacks: `0/0`.
- Usage: `3,110 input / 554 output / 3,664 total tokens`.
- Latency: `6,864 ms`; finish reason: `stop`.
- Profile-rate estimate: USD `0.0028078`; Provider did not return an actual cost field.
- Full request/response capture and terminal remain under the private Workbench runtime; only digests and a derived audit are versioned.

## Business-content audit

The model correctly used issuer Evidence E022 for support and cited all four authorized NUM refs: AI orders `$24.4 billion`, AI server revenue `$16.1 billion`, backlog `$51.3 billion`, and customer count above 5,000. It kept E018 as HPE read-through rather than Dell direct proof, treated E023 as unquantified pull-forward risk, and explicitly refused to infer cancellations, linear backlog conversion, equivalent Dell order digestion, or an ASP/margin bridge.

There was no free arithmetic, valuation, recommendation, wrong entity, wrong period, wrong unit or unsupported financial amount.

## Formal failure and root cause

The immutable terminal is `contract_validation / natural_node_canary_required_presentations_missing`. The policy required the literal phrase `customer count surpassed 5,000`; the model wrote the semantically equivalent `customer count surpassing 5,000` while citing the correct customer-count NUM ref. This is minor exact-surface noncompliance by the model, but making that grammatical inflection a hard financial L1 is a project-owned acceptance false negative.

A zero-call counterfactual changed only `surpassing` to `surpassed`; every remaining role, ref, numeric guard and boundary gate then passed. This replay does not relabel the live terminal and did not call the Provider.

## Decision

- Preserve the terminal and capture as failed immutable evidence.
- Do not retry or issue a second canary.
- Keep the issue in S2 under RC-P36-170.
- Next, make a provider-neutral zero-call decision between local grammatical rendering and bounded presentation-equivalence normalization; replay this immutable capture plus negation/below-threshold/entity/period/unit mutations.
- Do not add a DeepSeek-specific phrase whitelist or infer that a full DELL report now passes.
