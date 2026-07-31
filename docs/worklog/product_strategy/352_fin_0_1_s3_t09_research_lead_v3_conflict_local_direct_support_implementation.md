# FIN 0.1 S3-T09 Research Lead-v3 conflict-local direct-support implementation

The authorized zero-call implementation completed `fin01.s3.bounded_agent.research_lead_owner_grade:v3` without issuing or consuming an admission.

Lead-v3 keeps the Specialist-v5 transport, canonical output-v3 shape, 1800-token Lead cap, 16800-token aggregate cap, 6000-byte Provider segment cap, and 8192-byte assembled cap. Historical Lead-v2 routing, request contract, telemetry identity, consumed admissions, and terminal Runs remain unchanged.

One deterministic helper now owns `conflict_adjudications[].fact_presence_summary` for both local and canonical validation. It reads only the direct `support_fact_ids` of the Claim Cards named by the current conflict:

- all involved Claims have direct support → `facts_present`;
- no involved Claim has direct support → `no_facts_present`;
- some but not all involved Claims have direct support → `mixed_fact_presence`.

Global Facts, unrelated same-Cell Facts, and other Claims cannot change the result. Duplicate involved Claim ids, invalid enum values, truth-table mismatches, and explicit false global all-Cell narrative statements fail closed under versioned content-free telemetry. Cell-head fact-count mismatch and conflict-local fact-presence mismatch now have distinct canonical error identities.

The Lead-v3 Provider request exposes the exact scope and all/none/some truth table and requires self-checking before return. The local validator rejects semantic mismatch before deterministic head assembly. No normalization, coercion, silent repair, raw text, Claim/Fact id, digest, item index, arbitrary key, or private reasoning enters failure telemetry.

Deterministic verification covered the three truth states, supported and unsupported singleton conflicts, unrelated global and same-Cell Fact invariance, duplicate/unknown/invalid/mismatch negatives, explicit global narrative conflict, restricted live replay, local/canonical parity, historical v2 immutability, safe canonical failure persistence, release/backlog authority, and a full fake-Provider six-node/nine-Artifact path. The focused suites passed 35 tests. Restricted replay still produces exactly one mismatch, so the implementation does not relax the captured failed answer into a success.

Real model, Provider, network, source, and external-tool calls were all zero. No admission, canonical Run, Artifact, business Case write, retry, fallback, rerun, comparison, Human Review, T10, S4, release, or production action occurred.

RC-P36-041 is now fixture-proven but not live-proven. RC-P36-037 and S3-T09 remain blocked until a separately governed fresh complete Agent proof and subsequent product acceptance. The next item is only `S3-T09-OWNER-GRADE-V3-RESEARCH-LEAD-V3-FRESH-AGENT-PROOF-DECISION`, which is not yet authorized.
