# FIN 0.1 S3-T09 transport-v5 fresh live execution

Date: 2026-07-23

The fresh v5 admission was consumed exactly once after both Project OS and generic runner zero-call preflights passed. The target identity was absent beforehand, the credential was only checked for presence, transport retries were zero, and no Provider health probe was used.

The owned v4 assembly defect is now live-closed: all three Specialists completed all nine segments, each segment returned `stop`, and each full Specialist passed the unchanged output-v3 semantic, authority, scope, cardinality and actionability validators under the new bounded assembly envelope. The old first-Specialist 6010-over-6000 failure did not recur.

The chain then reached Research Lead. DeepSeek emitted exactly 1200 output tokens and `finish_reason=length`, so the runtime terminalized with `s3_bounded_node_output_truncated`. There was no retry, fallback, patch or rerun. WorkUnit, Attempt and Run are failed/failed/failed, event count is seven, Artifact count is zero and orphan count is zero. Writer and Verifier did not execute.

The Run used 10 calls, 39,042 input tokens, 5,523 output tokens, 44,565 total tokens and an estimated USD 0.02123611. Ten final assistant outputs are persisted in the restricted object store and successfully read back; tracked records contain only their digests and audit metadata. Post-terminal inspection was read-only and added zero model/provider/network calls.

This result means the token budget is the only failure actually observed in v5, specifically the Research Lead 1200-token cap. It does not prove that token budget is the only remaining end-to-end issue because Writer, Verifier and the nine Artifact families were never reached. S3-T09 therefore remains blocked. The next possible item is a zero-call Lead-truncation result/root-cause decision, but it is not authorized by the completed exact-run scope; no v6, cap change or new admission has been created.
