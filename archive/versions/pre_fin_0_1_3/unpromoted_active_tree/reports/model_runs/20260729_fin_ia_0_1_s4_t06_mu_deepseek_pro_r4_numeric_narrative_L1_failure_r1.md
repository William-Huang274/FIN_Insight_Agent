# MU R4 DeepSeek Pro exact-live：numeric narrative L1 failure

日期：2026-07-29<br>
Case：MU<br>
Model：`deepseek-v4-pro`<br>
Admission：`fin01-s4-t06-mu-current-case-aware-delivery-identity-boundary-fresh-exact-admission-r4`

## Terminal result

- WorkUnit / Attempt / ResearchRun：failed / failed / failed
- completed logical nodes：1
- Artifacts：0
- retry / fallback / replay / relaunch / rerun：0 / 0 / 0 / 0 / 0
- paired assessment：not eligible
- owner acceptance：not eligible

## Usage

- semantic/model/provider/network calls：4 / 4 / 4 / 4
- input tokens：24,474
- output tokens：2,527
- total tokens：27,001
- estimated cost：USD 0.01284468
- all finish reasons：stop
- transport attempts per call：1

## First credible failure

- stage：`domain_specialist:value_and_profit_capture`
- segment：`facts_explanation_and_terminal`
- code：`s4_case_numeric_authority_provider_narrative_invalid`
- subtype：`provider_authored_numeric_token`
- field：`explanation_layer`
- failing count：2
- layer：L1 hard integrity

The content-free telemetry intentionally excludes the narrative and token values, but the separate restricted assistant-output capture remains replayable. A 2026-07-30 zero-call replay established that `failing count=2` means two narrative strings, not two financial values: `$.fact_layer[0].statement` and `$.explanation_layer[0]` both contained the reporting-period label `FQ3 2026`. No material amount, percentage or measurement mismatch was established by R4. The literal blanket no-digit contract was violated, while the owned root cause is the project's overbroad numeric classifier.

## Identity v2 observation

The R3 identity failure did not recur. The Demand Specialist completed all three segments, and four live outputs passed the current-case-aware identity gate before the numeric failure. This is live positive-path evidence for identity boundary v2, not proof of final Writer/title identity because no final Artifact was produced.

## Evidence

- Result record: `configs/releases/fin_ia_0_1_s4_t06_mu_current_case_aware_delivery_identity_boundary_r4_exact_live_execution_failure_result_v1_0.json`
- Runtime result: `.codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1/s4_t06_mu_identity_v2_r4_live_execution_result.json`
- Supervision: `.codex_runtime/fin01-s4-t06-mu-current-case-aware-identity-v2-r4-supervision-r1`

## Stop disposition

R4 is consumed and immutable. No R5, patch, provider switch, paired assessment, owner acceptance or T07 was performed. The zero-call disposition has reclassified RC-P36-080 as a project-owned classifier false positive and frozen `fin01.runtime.audit_evidence_retention_and_promotion_separation:v1`. The current next item is the single zero-call runtime audit-evidence v2 and material-numeric classifier implementation.
