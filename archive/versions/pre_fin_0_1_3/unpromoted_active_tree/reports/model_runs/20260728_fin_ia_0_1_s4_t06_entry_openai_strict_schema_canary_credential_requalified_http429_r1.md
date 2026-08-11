# Model Run: 20260728_fin_ia_0_1_s4_t06_entry_openai_strict_schema_canary_credential_requalified_http429_r1

> Subsequent route correction: the user clarified that the intended target was a self-hosted Sub2API. This immutable run targeted `https://api.openai.com/v1`, so its HTTP 429 is official-OpenAI wrong-route evidence and does not classify the intended Sub2API rate, quota, model mapping, or schema capability.

## Summary

- Purpose: verify one exact OpenAI Responses strict-schema request after credential requalification.
- Status: terminal failed before generation.
- Run type: inference canary.
- Timestamp: 2026-07-28T22:38:39+08:00.
- Environment: local Windows workspace, OpenAI API.

## Code And Command

- Entry point: `scripts/releases/run_fin_ia_0_1_s4_t06_entry_credential_requalified_strict_schema_canary.py`.
- Command: runner with `--execute` and `LLM_GATEWAY_TRANSPORT_RETRIES=0`.
- Authority: `configs/releases/fin_ia_0_1_s4_t06_entry_openai_credential_requalified_fresh_strict_schema_canary_authority_decision_v1_0.json`.
- Authority SHA256: `bb9df485efda0ffacd6ed2a6b496470bca0ed6cb7e56356e7184a9615a1ef27d`.
- Git: dirty historical mixed worktree; no commit created for this run.

## Inputs

- Case/cell: DELL / `demand_authenticity_and_sustainability`.
- Surface: `facts_explanation_and_terminal`.
- Input digest: `f023c6b2139b288bf0637db25e64a40587c3bf6824c154c7eecffc32a584dacf`.
- Request template SHA256: `b92911d0bb9755c3e46fc0d4cac87cb0d07486d8fba8177ca69f2785ee443d7e`.
- Server schema SHA256: `24cdd015fd3c6b393c1d1013ffa065eb0a2a266c691720e981c01e6db9004938`.
- Candidate boundary: one provider-contract canary only; no research WorkUnit or business Artifact.
- Leakage guard: no raw provider response, output text, reasoning, credential, headers, or stack persisted.

## Model Parameters

- Provider/model: OpenAI / `gpt-5.6-sol`.
- Endpoint: `/responses`.
- Response contract: strict JSON Schema.
- Reasoning effort: none.
- Max output tokens: 512.
- Timeout: 120 seconds.
- Retry: 0.

## Outputs

- Result: `configs/releases/fin_ia_0_1_s4_t06_entry_openai_credential_requalified_fresh_strict_schema_canary_exact_once_execution_result_v1_0.json`.
- Result SHA256: `22cc6a236cda8a81e09f8283e266c7ec0fcf0135fb8417a57f876407474da27d`.
- Program disposition SHA256: `e19572330af5bc8801202172b8639b46322c50c3d9a652340aa6129cb3e24ccd`.
- Business Artifacts: none.

## Results

- Sanitized terminal result: HTTP 429.
- Provider/network/transport attempts: `1/1/1`.
- Input/output/total tokens: `0/0/0`.
- Estimated cost: USD 0.
- Latency: 3536 ms.
- Strict parse/local validator: not reached.
- Interpretation: rate-limit or quota/credit/spend-limit rejection before generation; sanitized evidence cannot distinguish the exact 429 subtype.

## Experiment Governance

- Hypothesis: the requalified credential allows the exact strict-schema request to reach generation and local semantic closure.
- Decision target: one completed response that passes strict parse and local rendering.
- Ceiling: one request, 512 output tokens, USD 0.05.
- Stop condition: first credible failure.
- Decision label: stop.
- Mainline decision: blocked; no retry or third canary.
- Zero-call closeout validation: 68 S4-T06 contract tests passed; Project OS exact next-scope preflight passed with zero open blockers.

## Runtime Efficiency

- Wall time: approximately 3.5 seconds provider latency.
- Throughput: not applicable.
- Resource use: no local GPU workload.
- Serving implication: none; request was rejected before generation.

## Caveats And Next Step

- The result does not evaluate schema acceptance or model behavior.
- It does not invalidate the prior credential metadata success.
- Next: separately authorize a zero-call rate-or-quota program disposition after inspecting Platform billing, usage, and limits.
