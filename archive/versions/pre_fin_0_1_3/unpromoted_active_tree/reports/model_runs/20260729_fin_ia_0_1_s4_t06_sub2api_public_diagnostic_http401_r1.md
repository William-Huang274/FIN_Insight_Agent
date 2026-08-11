# Model Run: 20260729_fin_ia_0_1_s4_t06_sub2api_public_diagnostic_http401_r1

## Summary

- Purpose: evaluate one exact Sub2API route/model/Responses/strict-schema synthetic diagnostic.
- Status: terminal failed before generation; diagnostic-only.
- Run type: inference transport canary.
- Timestamp: 2026-07-29.
- Environment: local Windows, direct no-proxy HTTP.

## Code And Command

- Entry point: `scripts/releases/run_fin_ia_0_1_s4_t06_entry_sub2api_public_nonsensitive_diagnostic_canary.py`
- Command: runner with `--execute`.
- Config: authority and zero-call implementation artifacts under `configs/releases/`.
- Git state: `codex/layered-data-source-expansion`, historically mixed dirty tree.
- Seeds: not applicable.

## Inputs

- Data profile: fully synthetic public non-sensitive.
- Exact values: content intentionally omitted from this run ledger; request body SHA-256=`46d152134ccefa133dbd44d90a047d02d8a6a86fe57eed4daf458a49bbf36c06`.
- Company/private/financial data: none.
- Credential access: none.

## Model Parameters

- Provider family: self-hosted Sub2API.
- Model alias: `gpt-5.5`.
- Wire: Responses `/responses`.
- Strict JSON Schema: enabled.
- Maximum output tokens: 128.
- Timeout: 30 seconds.
- Retry: 0.

## Outputs

- Sanitized result: `configs/releases/fin_ia_0_1_s4_t06_entry_sub2api_public_nonsensitive_diagnostic_canary_exact_once_execution_result_v1_0.json`
- Result SHA-256: `aaba2e0396c264d5a071cc3532572ff87d9b2ea4a8415284574f38012e82d301`.
- Raw output/checkpoint/predictions: none persisted.

## Results

- HTTP status: 401.
- Latency: 321 ms.
- Tokens: input/output/total=`0/0/0`.
- Requests/attempts: semantic/provider/network/transport=`1/1/1/1`.
- Schema parse and local value validation: not reached.
- Interpretation: service access control rejected the independent client before model generation; model behavior and strict-schema capability remain unevaluated.

## Experiment Governance

- Decision label: diagnostic-only, terminal stop.
- Ceiling: exactly one synthetic request.
- Stop condition: first HTTP/provider/schema/parse/value failure.
- Stop condition observed: HTTP 401.
- Mainline decision: blocked; no T06 acceptance.

## Runtime Efficiency

- Wall time: 321 ms observed request latency.
- Throughput/GPU/RAM: not applicable; generation did not start.
- Bottleneck: service access-control boundary.
- Serving implication: raw FIN Insight client cannot use the supplied connection contract without additional provider-side access information.

## Caveats And Next Step

- No response body or auth subtype was persisted.
- Do not retry, vary headers, add credentials, or switch providers automatically.
- Next: zero-call post-result program disposition.
