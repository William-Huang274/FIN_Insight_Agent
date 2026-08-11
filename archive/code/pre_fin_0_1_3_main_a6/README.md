# Pre-FIN 0.1.3 main A6 code archive

This directory preserves code introduced by the June A6 evaluation line that was still unique to `main` when FIN 0.1.3 was rebaselined.

It is not an active Python package, script entrypoint, test suite, or Workbench Runtime. The original paths and commit lineage are recorded in `configs/repository/fin_0_1_3_main_unique_semantic_merge_disposition_v1_0.json` and `configs/repository/fin_0_1_3_archive_redirect_manifest_v1_0.json`.

Why it is archived:

- the runners and resident worker are bound to the superseded A6 experiment shape;
- current S1 uses Candidate/Evidence Pack gates and current S3 uses a later dynamic-research contract;
- reactivating the old files would create a second eval/runtime contract rather than extend the current one.

Restoration requires moving the capability into an owned, version-neutral module, adding current tests, and updating the repository architecture inventory. Nothing under this directory may be imported by active product or operator code.
