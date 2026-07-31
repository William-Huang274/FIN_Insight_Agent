# FIN 0.1 S3-T09 Research Lead v2 fresh Agent proof decision

## Outcome

The fresh proof contract is decided and frozen. This step issued no admission, consumed no admission, made no model, Provider, network, or external-tool call, and created no canonical execution state.

The next item is separately governed exact admission issuance. Live execution remains unauthorized.

## Frozen proof identity

- WorkUnit: `wu_p02_5_43be21c85a5aa7f48103fba2`
- Attempt: `attempt_fin01_7a048403efd7098be7e552a0`
- ResearchRun: `research_run_fin01_641650afe6bb1062f9ae135e`
- exact input digest: `86ad143c69b3ef146e64048fcf981e33e751f1fa41a9190b91449b511da1b232`
- preparation digest: `6803b538dd9e523cd1d0c903461a4a1d08a844ec72265e5f566b4cf99f2ae430`
- double-prepare payload digest: `8de65b26beb9aceb3b1c5b0ec1d6230954cd806bb54974319f61df3f71993071`

The identity is distinct from all nine prior Agent and deterministic-baseline Runs on the same Case and input head.

## Frozen prospective admission

- admission id: `fin01-s3-t09-three-cell-deepseek-owner-grade-v3-specialist-v5-research-lead-v2-exact-admission-r1`
- admission digest: `65a934d69766bfc4eff56b0decf2f986bba685d9cbbc3a68b781ce5202118cc0`
- Specialist transport: `fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v5`
- Research Lead transport: `fin01.s3.bounded_agent.research_lead_owner_grade:v2`
- canonical output: owner-grade v3
- output-token ceilings: Specialist `4200`, Lead `1800`, Writer `1400`, Verifier `1000`, aggregate `16800`
- model / Provider / network ceilings: `12 / 12 / 12`
- cost ceiling: USD `0.10`
- retry / fallback / rerun: `0 / 0 / 0`
- stop rule: terminalize on the first credible failure
- capture: restricted final-assistant text only, with tracked records limited to content-addressed references and safe telemetry

The prospective admission file is deliberately absent. The decision records what may later be issued; it is not itself an admission.

## Read-only proof

Two independent prepare passes produced the same payload. Before and after:

- WorkUnits / Attempts / Runs / Artifacts: `9 / 9 / 9 / 13`
- canonical database SHA-256: `87bbb325aeede067a823c02ad1d5ab46b56580ca279f077a6bdb698a6f498215`
- object tree SHA-256: `e49c2a7ff76a048dc75f0f5ddfd3d8df74e70cea754d36b154399874859cabdd`
- model / Provider / network / external-tool calls: `0 / 0 / 0 / 0`

Credential handling was presence-only. No credential value was read or persisted.

## Product boundary

This decision does not prove live Provider conformance or junior-analyst product quality. RC-P36-040 is fixture-repaired but not live-proven; RC-P36-037 and S3-T09 remain blocked until a fresh complete nine-Artifact Run passes downstream Writer and Verifier checks, paired comparison, and owner acceptance.

Current next item:

`S3-T09-OWNER-GRADE-V3-RESEARCH-LEAD-V2-FRESH-EXACT-ADMISSION-ISSUANCE`

It requires separate authority and may only issue the exact frozen payload. It may not consume the admission or execute the Agent.
