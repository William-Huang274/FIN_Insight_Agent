# FIN 0.1 S3-T09 DeepSeek owner-grade transport-v5 live validation R1

Date: 2026-07-23

This was the single authorized exact-once execution of admission `fin01-s3-t09-three-cell-deepseek-owner-grade-v3-segmented-transport-v5-exact-admission-r1` with digest `ac79c81490572b43752e01a6fa05240ef6a12ec68753f1db8fafc867c8f64559`. It used `deepseek-v4-pro`, transport `fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v5`, output contract v3, restricted final-assistant capture, retry zero, no source network, no external tools and no live business Case-head writes.

The zero-call preflight passed with the fresh WorkUnit, Attempt and ResearchRun absent and canonical counts unchanged at `8/8/8/13`. The execution then made 10 model/provider/network calls. All nine Specialist segment calls across the three decision cells returned `finish_reason=stop` and passed their segment plus assembled owner-grade validation. This is the first real proof that the v5 8192-byte assembly envelope removes the v4 6010-versus-6000 local failure without relaxing the v4 authority or epistemic contract.

The tenth call, `research_lead`, reached exactly its 1200 output-token ceiling and returned `finish_reason=length`. The runtime stopped with `s3_bounded_node_output_truncated`. WorkUnit, Attempt and ResearchRun are consistently `failed`; Artifact count is zero and there is no orphaned Run. Writer and Verifier were not called.

Usage was 39,042 input tokens, 5,523 output tokens and 44,565 total tokens. Estimated cost was USD 0.02123611. Retry, fallback and rerun counts were all zero.

All ten final assistant texts, including the truncated Lead output, are persisted as Run-bound restricted content-addressed objects and were read back through `RuntimeFacade.read_research_run_provider_output_captures(research_run_fin01_1736461952f90e35f104f478)`. The release result records only stages, sequences and object digests; it does not contain raw assistant text, HTTP envelopes, prompts, credentials or private reasoning.

Conclusion: transport-v5 assembly repair passed live. The fresh Agent product proof still failed because Lead output capacity stopped the chain before Writer, Verifier and Artifact commit. The only observed failure in this exact Run is the Lead 1200-token budget, but it is not evidence that no later product-quality issue exists because downstream nodes never ran. No further repair or execution is authorized in this closeout.
