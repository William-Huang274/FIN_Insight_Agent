# FIN 0.1 S3-T09 transport-v5 assembly repair

Date: 2026-07-23

The v4 live failure was replayed from its three restricted final-assistant captures. All three Provider responses passed HTTP, finish, JSON, exact segment shape, authority and epistemic-state validation. Their canonical sizes were 1166, 1519 and 3445 bytes; the merged seven-key Specialist object was 6010 bytes and failed the historical 6000-byte whole-output ceiling.

The earliest owned defect is a non-closing protocol invariant: each segment can independently occupy as much as 6000 bytes, but their union is required to fit the same 6000-byte envelope. This is not a repeated DeepSeek JSON problem and not merely a token-cap problem.

The selected repair versions only assembly capacity. Transport v5 keeps every segment at 6000 bytes, preserves the 320-character field limits, all cardinality, Evidence/Numeric authority, Claim Card epistemic-state, scope and actionable-WWC checks, and exposes the same Provider request as v4. Only the locally assembled v5 union receives an explicit 8192-byte bound. Historical v1-v4 and monolithic validators remain at 6000 bytes. No truncation, normalization, field deletion, retry or fallback was introduced.

Deterministic proof reconstructs a valid 6010-byte object without checking raw Provider text into Git. Historical validation rejects it, the v5 envelope accepts it, and a fake Provider node completes all three first-Specialist segments with three restricted captures. The focused v4/v5 suite is `16 passed`; Python compilation and `git diff --check` pass. Real model, Provider, network, admission, Run and Artifact counts remain zero for this repair.

This closes the local assembly defect only. It does not prove a complete owner-grade research deliverable. The next authorized sequence is a fresh v5 proof decision, exact admission issuance, paid preflight and one exact-once real Run. Any new credible failure must stop without hidden retry or rerun; paired comparison, owner acceptance, T10, S4, release and production remain outside the current authority.
