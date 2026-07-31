# MU R6 DeepSeek Pro exact-live：material numeric narrative L1 failure

日期：2026-07-30<br>
Case：MU<br>
Model：`deepseek-v4-pro`<br>
Run：`research_run_fin01_9917f7499cd316d1cb506038`

## Terminal result

- WorkUnit / Attempt / ResearchRun：failed / failed / failed
- completed logical nodes：1
- Artifacts：0
- retry / fallback / replay / relaunch / rerun：0 / 0 / 0 / 0 / 0
- paired assessment / owner acceptance：not eligible / not performed

## Usage

- semantic / Provider / network calls：4 / 4 / 4
- input tokens：25,425
- output tokens：1,902
- total tokens：27,327
- estimated cost：USD 0.01061641
- latency sum：24,573 ms
- all calls：`status=ok / finish_reason=stop / transport attempts=1`

## First credible failure

Stage：

`domain_specialist:value_and_profit_capture:facts_explanation_and_terminal`

Code：

`s4_case_numeric_authority_provider_narrative_invalid`

DeepSeek returned valid JSON but directly wrote concrete revenue, margin, profit, cash-flow, capital-expenditure and inventory values in three Fact statements and one explanation item. The request explicitly required Numeric facts to select only request-local `N001..N020` aliases and prohibited Provider-authored amounts, percentages, measurements, currency, units and precision. Restricted capture review therefore establishes a real field-level instruction violation, not the R4 reporting-period classifier false positive.

The hard L1 boundary behaved correctly: none of the failed text was promoted to a business Artifact. This single run does not establish that DeepSeek is generally unusable; it establishes that this model/contract combination is not reliable enough to own the material numeric narrative surface.

## Audit evidence

- usage receipts：4
- capture-v2 objects：4
- full model-visible requests：4
- final assistant outputs：4
- content-address digest matches：4
- credential/private reasoning/raw Provider response persisted：0 / 0 / 0
- failed output promoted to Artifact：false

The R5 terminal-result observability defect did not recur. The runner materialized a typed terminal result with no post-terminal findings, exited 0 after recording the canonical failed states, and the supervision exit receipt exactly matches the final 299-byte stderr log.

## Disposition

R6 is consumed and immutable. No R7, retry, patch, paired assessment, owner acceptance or T07 operation was performed. RC-P36-082 can close on live evidence; RC-P36-067/068 remain open because final nine-Artifact L1 was not reached; RC-P36-080 remains a blocking live recurrence on the Agent-authored material numeric narrative surface.

Next:

`S4-T06-MU-R6-FIRST-CREDIBLE-FAILURE-PROJECT-BLOCK-OR-DETERMINISTIC-PLANNER-SCOPE-DISPOSITION-DECISION`

Evidence:

- `configs/releases/fin_ia_0_1_s4_t06_mu_temporal_authority_terminal_result_r6_exact_live_execution_failure_result_v1_0.json`
- `.codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1/s4_t06_mu_temporal_authority_terminal_result_r6_live_execution_result.json`
- `.codex_runtime/fin01-s4-t06-mu-temporal-authority-terminal-result-r6-supervision-r1/exit_receipt.json`
