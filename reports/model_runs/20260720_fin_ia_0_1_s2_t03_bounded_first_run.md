# FIN 0.1 S2-T03 Bounded First Run Ledger

- Status: `terminal_failed_no_automatic_rerun`
- Scope: `NVDA / demand_authenticity_and_sustainability / demand_signal`
- Case: `case_87682fa72e72d7d042dabba0:v1`
- Input digest: `ce6f5758ecb1e3f5d18d50028cf23214e2c1628ed00a99038c7a8bb5cec228ea`
- Provider/model: `deepseek / deepseek-v4-pro`
- Admission: maximum 3 semantic/provider/network calls, 1 transport attempt per call, retry 0, USD 0.05 cap
- Source network / external tool / commercial data / live business Case head writes: `0 / 0 / 0 / 0`

## Canonical execution truth

- WorkUnit: 1
- Attempt: 1
- ResearchRun: 1 (`research_run_fin01_9239b033666398bd8dece2a5`)
- Terminal state: `failed`
- Terminal reason: `bounded_agent_profile_error:ValueError`
- Artifact: 0
- Fallback: 0
- Rerun: 0

## Calls and cost

The failed run predated durable failure-receipt persistence. It stopped in the first bounded stage before the second semantic stage, but the exact pre-call/JSON/schema substage is not reconstructable. Model/provider/network/transport counts are therefore recorded as `0_to_1_not_reconstructable`; cost is not reconstructable but remains bounded by the USD 0.05 admission cap. This ledger must not be interpreted as zero calls or a successful model run.

The post-failure engineering repair now persists sanitized stage, call/token/latency/transport/cost receipts on future failures and excludes raw provider responses, private reasoning, and secrets. The consumed admission was not retried. Any later run requires explicit user direction and a new exact admission.
