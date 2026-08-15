# FIN 0.1.3 S3 — full-fragment Chat R2 relation-role failure

## Outcome

R2 ran on clean/synced commit `bffb6591...` and consumed four of six allowed DeepSeek calls with complete captures and zero retry. The thesis passed surface contract v1.1 and became the first accepted fragment. The mechanism then returned one bounded Tool Call but stopped at local validation with `finance_loop_micro_required_authority_missing`.

This is not a repeat of R1 and not a connectivity failure. The model used the earnings-call transcript as support, classified the broad 8-K as context, selected `CR::DELL::MULTI_DRIVER_CONTEXT`, and explicitly denied a product-to-segment/company allocation or causal bridge. The relation card nevertheless encoded both documents as mandatory support.

## Zero-call replay finding

Changing the 8-K role from context to support is not a valid fix. Replay exposed a second project defect immediately afterward: a non-thesis fragment was required to accept the thesis-level `supported` status, even though the mechanism itself selected `bounded_inference` and the terminal compiler already lowers the aggregate status conservatively.

The bounded repair is therefore one provider-neutral package:

1. separate relation-required support from optional context/counterevidence;
2. let each non-thesis fragment validate its own inference authority;
3. keep final status aggregation in the canonical terminal compiler;
4. replay the saved R2 Tool Calls, negative role mutations and a full fake sequence before any R3;
5. generate the next authority timestamp from the local clock rather than hand-entering it.

R2 authority, public result and raw captures remain immutable. Dynamic Research Truth Spine, five-unit execution, generalization and S3 acceptance remain false.
