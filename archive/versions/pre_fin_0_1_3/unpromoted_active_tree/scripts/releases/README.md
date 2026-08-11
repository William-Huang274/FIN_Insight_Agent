# Release Reproducibility Scripts

Scripts in this directory reproduce bounded FIN 0.1 candidate, structural-regression, rollback and model-package checks. They are not imported by the Workbench application runtime and do not create release authority.

Rules:

- keep each script bound to a versioned contract or candidate profile;
- write local run output under `.codex_runtime/`;
- promote only small reviewable decision evidence to `reports/release_evidence/`;
- never treat a successful standalone script as an integrated Workbench or canonical Case capability;
- network, model, paid or operational execution still requires its own explicit authority.

See `../../configs/releases/fin_ia_0_1_code_mainline_manifest_v1_0.json` for active and disconnected classifications.
