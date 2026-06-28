# Exact Slot Gap Closeout

- schema_version: `finsight_exact_slot_gap_closeout_summary_v0_1`
- generated_at: `2026-06-25T03:11:08Z`
- status: `pass`
- company_count: `603`
- exact_gap_count: `25`
- closeout_row_count: `25`
- product_kpi_gap_count: `171`

## Closeout By Requirement

| requirement | count |
| --- | ---: |
| public_order_proxy | 25 |

## Closeout Classes

| class | count |
| --- | ---: |
| public_source_exhausted_gap | 25 |

## Closeout Reasons

| reason | count |
| --- | ---: |
| hk_local_tender_no_supplier_bound_award_or_no_structured_award_endpoint | 1 |
| jp_local_tender_no_supplier_bound_award_or_no_structured_award_endpoint | 2 |
| non_us_fpi_or_adr_local_tender_no_supplier_bound_award_or_no_structured_award_endpoint | 7 |
| non_us_possible_local_tender_no_supplier_bound_award_or_no_structured_award_endpoint | 1 |
| tw_local_tender_no_supplier_bound_award_or_no_structured_award_endpoint | 3 |
| usaspending_no_recipient_bound_award_or_api_fetch_gap | 11 |

## Policy

Every remaining L1/L2/L3 exact-slot gap is classified with attempts or source-boundary reason. Closeout rows are not evidence rows and must not be promoted by Research Lead, specialists, Memo Writer, or Verifier.
