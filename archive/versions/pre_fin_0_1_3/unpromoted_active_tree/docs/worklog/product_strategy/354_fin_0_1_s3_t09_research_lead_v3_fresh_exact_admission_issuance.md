# FIN 0.1 S3-T09 Research Lead-v3 fresh exact admission issuance

The user authorized only exact admission issuance. The frozen decision payload
was copied byte-for-structure into a new durable admission; no admission
consumption or execution occurred.

The issued admission is
`fin01-s3-t09-three-cell-deepseek-owner-grade-v3-specialist-v5-research-lead-v3-exact-admission-r1`
with canonical digest
`f4fede4d86274bf099e801c8ec89ff0773a7cc9f66baa5365cbcf3ac39d3b080`.
It binds the fresh predicted WorkUnit, Attempt, and ResearchRun to the exact
NVDA Case/version/DecisionSurface/as-of input, Specialist-v5, Research-Lead-v3,
output-v3, and restricted final-assistant capture policy.

The execution envelope remains 12 semantic/Provider/network calls, 16800
aggregate maximum output tokens, USD 0.10, one transport attempt per call, and
zero retry, fallback, automatic repair, or rerun. Research-Lead-v3 retains the
conflict-local direct Claim support all/none/some truth table and historical
Lead-v2 immutability.

Schema, profile admissibility, digest, factory construction, and runner target
loading passed without invoking the Provider callback. The predicted execution
identity remains absent. Target counts stayed `10/10/10/13`; database digest
`3a4390ad...2458` and object-tree digest `42c30c3c...4784` were unchanged.
Credential handling checked only environment-variable presence and persisted no
secret value.

`LLM_GATEWAY_TRANSPORT_RETRIES` was unset during issuance. This does not block
issuance, but any future execution preflight must require it to equal `0`
before the execution command can consume the admission.

Observed counts were one new admission and zero admission consumptions, model,
Provider, network, source, external-tool, WorkUnit, Attempt, ResearchRun,
Artifact, business Case, comparison, Human Review, or paid-run actions.
RC-P36-041 and RC-P36-037 remain open, and S3-T09 remains blocked.

The next action is only
`S3-T09-OWNER-GRADE-V3-RESEARCH-LEAD-V3-FRESH-EXACT-LIVE-EXECUTION`.
It requires separate user authority and a fresh fail-closed preflight. The
future run must consume the admission exactly once and stop on its first
credible failure without retry, fallback, patch, or hidden rerun.
