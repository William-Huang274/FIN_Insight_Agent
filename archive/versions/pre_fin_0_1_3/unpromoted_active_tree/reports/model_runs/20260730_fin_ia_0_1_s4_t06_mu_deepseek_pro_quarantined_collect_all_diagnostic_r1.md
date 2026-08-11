# FIN 0.1 S4-T06 MU DeepSeek Pro quarantined collect-all diagnostic R1

- Status: diagnostic complete; not formal exact-live acceptance.
- Source: immutable R6 failure plus four restricted capture-v2 interactions.
- Continuation: eight new DeepSeek Pro interactions, cached once and replayable.
- Totals: six logical nodes, 12 receipts, 12 unique interactions, 9 quarantined Artifacts.
- New usage: 147,880 input tokens, 4,252 output tokens, 152,132 total tokens, USD 0.06802704.
- Retry / fallback / source-network / tool / canonical-target write / business promotion: all zero.

## Findings

The model produced valid JSON at every newly observed stage. Eight of twelve interactions required no diagnostic repair. Four stages required ten field-level repairs:

1. The R6 value-and-profit Fact segment directly authored material numbers in three Numeric Fact statements and one explanation despite selecting correct request-local aliases.
2. The value-and-profit claim segment returned six candidates against a maximum of two. Naive truncation selected a mixed-scope Fact; the diagnostic selected two existing locally assemblable candidates.
3. The bottleneck Fact segment authored one unbound calendar year, one inventory measurement under Evidence support, and one percentage Numeric narrative.
4. The bottleneck WWC segment authored two percentage thresholds in free text.

Two project-owned cross-layer defects appeared after those outputs were repaired:

- Local exact numeric rendering produced three statements above the legacy 320-character Provider narrative limit; the longest was 490 characters.
- The pre-call budget projection priced UTF-8 bytes as tokens and blocked Verifier before the actual USD 0.10 hard cap was exhausted.

After diagnostic-only projections, Research Lead, Memo Writer and Verifier completed. The machine Verifier returned `accept_for_internal_review`, and the final identity was correctly MU. This is only L1 positive evidence after repairs. The report remained mechanically rendered, contained questionable conflict semantics, and had no paired baseline or owner review.

## Decision

Do not run one formal full chain per defect. Implement one L1 structural bundle: Provider returns aliases and finite judgment atoms; local runtime selects, orders and renders; prompt/schema/validator/fake/render-capacity/budget units compile from one contract. Prove deterministic changes with DELL/MU/NVDA mutation fixtures, use one natural-output node canary per changed contract family, then run one final fresh MU exact-live. Defer broader semantic and delivery calibration to T08-T10/S5.

Evidence: `configs/releases/fin_ia_0_1_s4_t06_mu_r6_quarantined_diagnostic_aggregate_defect_and_proof_strategy_result_v1_0.json`.
