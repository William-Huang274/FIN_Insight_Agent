# Model Run: 20260723 FIN 0.1 S3-T09 DeepSeek owner-grade transport-v4 live validation r1

## Summary

- Purpose: consume the fresh transport-v4 exact admission once, preserve every final assistant answer, and test the complete six-node, nine-Artifact owner-grade path.
- Status: terminal failed while assembling the first Specialist's three individually valid segments; admission consumed; no retry, fallback, repair or rerun.
- Run type: bounded paid inference on branch `codex/layered-data-source-expansion`.

## Exact Contract

- Admission: `fin01-s3-t09-three-cell-deepseek-owner-grade-v3-segmented-transport-v4-exact-admission-r1`, digest `e85202b8adfa28274c7c90a78eb2a7c2c95518b74aeef83b657fe475fc332b62`.
- Case: `case_ac6fce120bf27977a1b45832:v1`, as-of `2026-07-21T00:00:00Z`.
- WorkUnit / Attempt / Run: `wu_p02_5_1f79a5619b9c67327f90ab4f` / `attempt_fin01_a8cd885b1ae7a2338453d622` / `research_run_fin01_0e2b6e9698ebbf61288708a9`.
- Input / preparation digest: `c25ecb0d92343be1e7ed07676c72b00ac4e2a92c1afb0c6450729c7635c3dc85` / `51ba6967f043df47d076f786989707b78811318ca2fd2b091a6f8ed86ec7e442`.
- Transport / output: `fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v4` / `fin01.s3.bounded_agent_three_cell_output:v3`.
- Output capture: explicitly bound to `fin01.s3.provider_output_capture.assistant_final_text_only:v1`.
- Maximum calls `12/12/12`, aggregate output cap 16,200, cost cap USD 0.10; retry/fallback/rerun all zero.

## Preflight

The scoped Project OS preflight passed with zero open blockers. The exact runner preflight verified credential presence without reading or persisting its value, retry zero, exact admission digest, current Case/input/preparation parity, unused target identity, and unchanged logical execution counts `7/7/7/13`. It made zero model, Provider, network, source-network or external-tool calls.

## Result

- Canonical WorkUnit, Attempt and ResearchRun all terminal `failed`; 0 Artifact, 7 events, no orphan.
- Three DeepSeek `deepseek-v4-pro` requests all returned `finish_reason=stop`, one transport attempt each.
- Usage: 9,881 input + 1,665 output = 11,546 tokens; estimated cost USD 0.00552593; summed receipt latency 19.981 seconds.
- All three Demand Specialist segments passed HTTP, JSON parse, segment shape, Cell binding, local segment constraints and transport-v4 Claim Card state-machine validation.
- Failure code: `s3_bounded_segmented_specialist_assembly_invalid:demand_authenticity_and_sustainability:s3_bounded_specialist_output_byte_budget_exceeded:demand_authenticity_and_sustainability`.

Restricted zero-call replay measured canonical segment sizes of 1,166, 1,519 and 3,445 UTF-8 bytes. Their assembled output is 6,010 bytes against the existing 6,000-byte Specialist budget, an excess of exactly 10 bytes. This is not an HTTP, JSON, segment-schema, context-authority or epistemic-state failure. The directly observed mismatch is project-owned: each segment can pass its own 6,000-byte gate while their valid assembly can exceed the same whole-output gate.

The executor stopped before the second Specialist, third Specialist, Lead, Writer, Verifier and every Artifact commit. Terminal inspection made no additional model, Provider or network call.

## Durable Answer Capture

All three exact final assistant texts were persisted as content-addressed restricted objects and successfully read back through `RuntimeFacade.read_research_run_provider_output_captures(research_run_fin01_0e2b6e9698ebbf61288708a9)`. Their object digests are:

- `4bf51db4f0d35d0233fa7919dfbd5bf059b99f7b9c1bd0eabfd1413453ebad8b`
- `6482538efa4285ff771706131ee6a8c4798096b7bbbc3aaae0dfcf6a30929288`
- `6b6fe21c21d0e840ed1d55bec0443d0f9ec6049e74bffec48f3e0ee456eba643`

The terminal event and tracked release result contain only typed metadata, lineage and object digests. They do not contain the answer bodies, raw HTTP envelope, headers, prompt, private reasoning or credential material.

## Product And Governance Assessment

- Pass: exact-once admission consumption, retry-zero first-failure stop, consistent terminal truth, no orphan, and replayable original-answer capture.
- Fail: transport-v4 Artifact proof and owner-grade research-product proof. No Evidence, Numeric, Judgment, Report or Alpha deliverable was committed.
- Not performed: byte-budget repair, rerun, paired comparison, owner acceptance, Human Review, T10, S4, release or production.

The next item is a separately governed zero-call result/root-cause decision for the segment-to-assembly byte-budget mismatch. This run must not be reused or repeated.
