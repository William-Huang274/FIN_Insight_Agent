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
The raw wire boundary still needs to be connected to the actual provider route;
upstream normalized defaults must not turn absent provider usage into zero cost.

Current qualification uses an authenticated loopback fixture for this contract.
The production HTTP handler, existing PostgreSQL dispatch store and Java/BFF run
admission are **not yet wired**. Do not enable this plugin against a stub host in
a paid run. Ordinary successful calls must not encounter a tiny fixed call cap;
continuous usage/progress monitoring belongs to the host. Native model capacity,
output capacity, financial authorization and cancellation still apply.

Run the opt-in process probe with a new evidence directory and a fixed binary:

```text
python scripts/engineering/probe_dsh_acp.py --binary <dsh-binary> --output <new-directory>
python scripts/engineering/probe_dsh_acp.py --binary <dsh-binary> --output <another-new-directory> --protocol qwen
node --test tests/harness_dispatch.test.mjs
python scripts/engineering/probe_dsh_acp.py --binary <dsh-binary> --output <new-failure-directory> --fail-compaction
```

The probe isolates DSH_HOME, credentials and workspace. It replaces the shipped
SDK server with ACP through a profile overlay, disables shell/filesystem tools,
session-log upload, inventory upload and automatic retries, and mounts only the
four synthetic MCP tools. Its 16k window exists to induce compaction cheaply in
a fixture; it is **not a FIN deployment default**. No financial conclusion or
real supplier compatibility is certified by a deterministic model response.
