# FIN 0.1 S3-T09 Research Lead conflict fact-presence scope decision

The authorized zero-call review selected one exact owner for `conflict_adjudications[].fact_presence_summary`: the direct `support_fact_ids` of the Claim Cards named by that conflict's `involved_claim_ids`.

The deterministic truth table is:

- every involved Claim has at least one direct supporting Fact → `facts_present`;
- no involved Claim has a direct supporting Fact → `no_facts_present`;
- some but not all involved Claims have direct supporting Facts → `mixed_fact_presence`.

Global Specialist Fact count was rejected because an unrelated Cell changed the live conflict-local result. Involved-Cell Fact count was also rejected because a Fact can belong to the same Cell without supporting the involved Claim. Free-text interpretation and removing the field were rejected because Claim Cards already expose a deterministic direct-support relation.

The review found two owned defects. Research Lead-v2 advertises the enum but does not validate its truth table before assembly. The canonical validator then uses a global three-Cell `total_facts` heuristic for each conflict and reports the same generic error used for Cell-head mismatch.

Restricted replay did not turn the failed answer into a success. The three observed summaries were `no/mixed/no`; direct-support truth was `no/no/no`, because all involved-Claim support counts were zero. The first and third conflicts were falsely rejected by the global heuristic, while the second remains a real semantic mismatch.

The selected future repair is a versioned `fin01.s3.bounded_agent.research_lead_owner_grade:v3` transport with one shared direct-support helper across the Provider contract, local validator, and canonical validator. Historical Lead-v2, Specialist-v5, canonical output-v3 shape, consumed admissions, terminal Runs, token limits, and byte limits remain immutable. The repair must add content-free semantic subtype/count telemetry and adversarial truth-table, unrelated-Fact, restricted-replay, parity, historical-regression, and six-node/nine-Artifact fake-Provider fixtures.

This task made no runtime code change, issued no admission, called no model/Provider/network/source/tool, created no Run or Artifact, and performed no comparison or Human Review. RC-P36-041 and T09 remain blocked. The next item is only the separately authorized Lead-v3 zero-call implementation.

Verification passed the scoped Project OS preflight with zero open blockers for the authorized decision scope and 53 focused current/historical contract tests covering the decision, live result, Lead-v2, Specialist-v5, issuance, and prior root-cause progression.
