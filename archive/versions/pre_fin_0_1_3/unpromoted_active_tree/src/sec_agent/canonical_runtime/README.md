# Canonical Runtime

This package currently contains two classes of code:

1. reusable canonical runtime primitives, including models, store/facade protocols, planning, scheduler, checkpoints, budgets, permissions, evidence requests, candidate bundles, parser/numeric, evidence gate and repair contracts;
2. Point 01 proof and closeout support, including `m1_*`, `m2_a1_*`, `m6_*` and `p01_g2_*` modules.

The second class is not the preferred long-term package layout. It remains path-stable because Point 01 manifests and audit artifacts bind exact package/file identities. Moving it during ordinary cleanup would invalidate historical proof without adding product capability.

New product code should depend on reusable primitives through explicit public interfaces. Do not add another milestone-specific package family here. A future migration may split `proof_support/` only after a versioned digest/path migration maps old artifacts to historical/superseded status.

The current path classification is recorded in `../../../configs/releases/fin_ia_0_1_code_mainline_manifest_v1_0.json`.
