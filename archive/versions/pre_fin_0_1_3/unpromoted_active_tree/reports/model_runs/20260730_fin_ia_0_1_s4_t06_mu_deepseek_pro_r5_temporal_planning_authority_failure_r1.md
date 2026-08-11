# MU R5 DeepSeek Pro exact-live：temporal planning authority failure

日期：2026-07-30<br>
Case：MU<br>
Model：`deepseek-v4-pro`<br>
Run：`research_run_fin01_0b20402c2f8d5e5674626760`

## Terminal result

- WorkUnit / Attempt / ResearchRun：failed / failed / failed
- completed logical nodes：0
- Artifacts：0
- retry / fallback / replay / relaunch / rerun：0 / 0 / 0 / 0 / 0
- paired assessment / owner acceptance：not eligible / not performed

## Usage

- semantic / Provider / network calls：3 / 3 / 3
- input tokens：14,122
- output tokens：1,406
- total tokens：15,528
- estimated cost：USD 0.00736628
- latency sum：23,526 ms
- all calls：`status=ok / finish_reason=stop / transport attempts=1`

## First credible failure

Stage：

`domain_specialist:demand_authenticity_and_sustainability:actionable_what_would_change_tasks`

Code：

`s4_case_numeric_authority_provider_narrative_invalid`

DeepSeek returned valid JSON but selected `2026-09-30` twice for `deadline_or_review_date`. The closed request allowed only `2026-06-24`, `2026-07-26`, `FQ3_2026`, and `Q1 2026`. This establishes field-level instruction noncompliance. It does not establish a false financial amount, general model noncompliance, transport failure, invalid JSON, or truncation.

The earliest project-owned cause is the contract shape: an exact planning deadline is mandatory free text owned by the Provider, while validation supplies only a financial/reporting-period numeric authority and no typed planning calendar or relative-time vocabulary. Natural ISO planning dates were also absent from the accepted fake fixtures.

## Audit evidence

- usage receipts：3
- capture-v2 objects：3
- full model-visible requests：3
- final assistant outputs：3
- content-address digest matches：3
- credential/private reasoning/raw Provider response persisted：0 / 0 / 0
- failed output promoted to Artifact：false

After canonical terminalization, the runner hard-coded the legacy capture-v1 policy and raised `s3_t09_provider_output_capture_policy_mismatch`, so no declared runtime-result JSON was written. The canonical failed states, receipts, capture-v2 objects and exact outputs remain independently reconstructable. The supervision exit receipt also captured only 299 stderr bytes before the final 1,073-byte traceback finished flushing.

## Disposition

R5 is consumed and immutable. No R6, retry, patch, paired assessment, owner acceptance or T07 operation was performed. One separately authorized zero-call scope replacement may introduce typed temporal planning authority and repair capture-v2 terminal-result materialization; it does not authorize another paid run.

Evidence:

- `configs/releases/fin_ia_0_1_s4_t06_mu_runtime_audit_evidence_v2_and_material_numeric_classifier_r5_exact_live_execution_failure_result_v1_0.json`
- `configs/releases/fin_ia_0_1_s4_t06_mu_r5_first_credible_failure_root_cause_scope_disposition_v1_0.json`
