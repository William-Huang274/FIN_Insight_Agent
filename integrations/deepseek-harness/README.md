# DeepSeek Harness host boundary (qualification, not enabled in production)

`dispatch.mjs` uses upstream `llm/stream`, covering normal and compaction calls.
It does not implement a model loop, summary scheduler, finance validator, retry,
or task planner. One process belongs to one admitted FIN execution. Load it only
with an explicit loopback host endpoint and an environment credential reference.

The host service must implement the following **internal** contract. These are
not browser APIs and do not replace Java/BFF business command identities.

| Route | Request | Required host behavior |
|---|---|---|
| `POST /calls/reserve` | `requestId`, complete provider-neutral `request` | Authenticate the run binding; recheck current grant; attach host TokenBudgetBasis and dated price; durably reserve in the existing dispatch store before returning `status=reserved`. Reject unresolved predecessors and unauthorized recoveries. The model cannot supply the grant or raise its own allowance. |
| `POST /calls/settle` | `requestId`, unchanged `chunks`, `terminal`, `stopRequired` | Persist the response before acknowledgment. Distinguish received response, known usage, truncated/failed execution and accepted research. Settle complete wire usage with the pinned price, retain reservation when usage is unknown. Do not declare success from an ACP end_turn alone. |
| `POST /calls/unknown` | `requestId`, unchanged partial `chunks` | Persist partial output and mark unknown usage; retain the precommitted reservation. No automatic retry. |

After a failed/aborted/truncated request, the plugin stops forwarding subsequent
requests in that process, including fallback research after failed compaction.
Successful output is not rewritten. A terminal chunk is released only after host
acknowledgment. On process death, admission must inspect durable unfinished
reservations; a process-local stop flag alone is **not** recovery authorization.

`harness_usage.WireUsage` handles raw DS Messages / Qwen Chat usage differences.
DS Messages uncached input excludes cache reads; Qwen prompt input includes them.
Reasoning is part of output. ACP used/size is context occupancy, not billing.
`harness_provider_transport.HarnessProviderTransport` connects that meter to an
execution-private loopback provider route. It uses HTTPX and httpx-sse, preserves
raw event payloads outside Git, and never retries. Provider credentials stay in
the host; the upstream process receives only an opaque loopback credential.

`harness_dispatch_host.HarnessDispatchHost` now implements this contract with a
FastAPI router and the existing `ModelDispatchStore`. Composition must supply a
Java **run-admission** authority, server-owned owner/budget binding, a dated price,
validated `TokenBudgetBasis`, private receipt directory and a trusted raw-wire
usage observer. The router has no browser identity or model-controlled budget.
It is not yet mounted in production. Java/BFF lifecycle and business-tool
composition remain unqualified; do not enable it against stub grants or usage in
a paid run. Ordinary successful calls must not encounter a tiny fixed call cap;
continuous usage/progress monitoring belongs to the host. Native model capacity,
output capacity, financial authorization and cancellation still apply.

Request/response originals are fsynced before acknowledgment; the PostgreSQL row
holds a content-addressed reference, avoiding its 4 MB inline response limit.
The normal budget row lock also serializes unresolved requests within one harness
execution, while other authorized children can share the budget. An unknown cost
retains its reservation; a known-cost failed output retains its actual charge.
Both stop that execution durably across host restart. A new authorized execution
does not erase old financial holds. Duplicate settlement can acknowledge exactly
the same saved response; duplicate reserve cannot authorize a provider resend.
Revocation stops the next dispatch but cannot prevent saving an in-flight receipt.

The host can stop an upstream success when its wire usage is missing or its wire
terminal indicates truncation. The plugin saves that response then raises before
releasing a successful terminal; it must not report the task complete. No model
conclusion is rewritten. Unit/HTTP protocol tests use synthetic grants and an
in-memory store. The `--metered` process probe uses this actual HTTP host, wire
proxy and a real PostgreSQL database, with a nonprivileged worker role. Its
authority, prices and model responses are still synthetic; it does not claim
Java run admission or research-quality acceptance.

One reservation admits exactly one inference HTTP request. The host's existing
budget transaction serializes calls within the execution; an exclusive durable
wire-claim receipt prevents transport retries/replays. The serialized model and
output allowance must match the admitted request, including compaction. A model
adapter silently reducing output to one token is an execution mismatch, not a
valid way to satisfy a smaller budget. Raw wire receipts are flushed during the
stream and fsynced before terminal acknowledgment; every token delta does not
cause a separate fsync. Missing terminal/usage retains the unknown-cost hold.

Run the opt-in process probe with a new evidence directory and a fixed binary:

```text
python scripts/engineering/probe_dsh_acp.py --binary <dsh-binary> --output <new-directory>
python scripts/engineering/probe_dsh_acp.py --binary <dsh-binary> --output <another-new-directory> --protocol qwen
node --test tests/harness_dispatch.test.mjs
python scripts/engineering/probe_dsh_acp.py --binary <dsh-binary> --output <new-failure-directory> --fail-compaction
python scripts/engineering/probe_dsh_acp.py --binary <dsh-binary> --output <new-metered-directory> --metered
```

The probe isolates DSH_HOME, credentials and workspace. It replaces the shipped
SDK server with ACP through a profile overlay, disables shell/filesystem tools,
session-log upload, inventory upload and automatic retries, and mounts only the
four synthetic MCP tools. `--metered` requires operator-provisioned
`FIN_HARNESS_FIXTURE_WORKER_DSN` and `FIN_HARNESS_FIXTURE_PROVISIONER_DSN`, with the
existing 003/004 budget schema and roles. It creates a separately named synthetic
budget, not a new allowance for any research task. The full probe tests process
restart, multiple compactions, cancellation, and no post-failure forwarding.

The original 16k stress fixture could make pi-ai clamp an oversized input's
output allowance to one token, unnoticed by a fake accounting host. The metered
fixture declares 64k capacity and triggers compaction early at 20%, so its large
test input still fits the declared model. Both values are **qualification-only,
not FIN deployment defaults**. Production must use the chosen model's actual
capacity and suitable native pressure threshold. No financial conclusion or
real supplier compatibility is certified by a deterministic model response.

## Organization task composition (candidate)

`organization_harness_session.py` binds the existing signed Java run to the
official `agent-client-protocol` Python SDK. It uses native session/new and the
advertised session/resume (or load) capability; cancellation revokes dispatch
and tools before session/cancel. No FIN model/summary loop runs inside ACP.
An already completed predecessor response can be projected after an admitted
recovery without another model request. Unknown requests retain their receipts.

The host-only `harness_execution_bindings[thread_id]` selects the executable
path/SHA256, manifest, model/reasoning, protocol/endpoint, secret environment
name, TokenBudgetBasis and model/output/summary capacity. These must match the
admitted task and existing budget. `FINSIGHT_HARNESS_STATE_ROOT` is a private
persistent workspace, not a public document root. Provider keys never enter the
child environment. Public usage comes from metered wire receipts, not ACP
context occupancy. Ordinary calls and compaction share the original task budget.

`harness_business_tools.py` uses a maintained ToolNode and SQLite checkpointer
solely for business execution. Original observations, calculation identities,
working notes and report versions survive native history compaction. Its paged
directory and readback tools are reused from FIN; the old orientation/summary
middleware is absent. Draft repair and local report edits reuse existing source
binding and version validation. Saved does not mean delivered or independently
reviewed. Required independent review is explicitly unavailable in this candidate;
delegation is not yet qualified. It must not silently fall back to the old loop.

Qualification: `tests/test_organization_harness_session.py` tests the composition
with fixture peers. `FIN_TEST_DSH_BINARY=<fixed-binary> pytest
tests/integration/test_harness_business_process.py` runs the real ACP process,
MCP/ToolNode, calculation, note persistence, restart, compaction and cancellation
against deterministic provider responses. Both Windows and Linux 0.2.1rc2 passed.
The Linux wheel SHA256 is
`0a0a4eb85a22cd9339972e6a5ced77a27ec791353a5b220e3e10b8cdbbdeca39`.
This does not yet certify real Java/BFF queue lifecycle, paid NVIDIA compaction
faithfulness, or long-run business-checkpoint storage growth. Deployment status
and real acceptance remain separate from these tests.
