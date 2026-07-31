# Product Documentation Index

This folder is the product-management source of truth for FinSight-Agent.

Product docs answer:

- Who is the user?
- What problem are we solving?
- What workflow should the product support?
- What value should the user perceive?
- What should be in scope or out of scope?
- What acceptance criteria matter from the user's perspective?

Product docs should not be implementation plans. Technical contracts, APIs, schemas, runtime design, parser plans, eval runners, and delivery notes belong in `docs/architecture/`, `docs/eval/`, `docs/deployment/`, or a future `docs/engineering/` area.

## Current Product Docs

- [FIN 0.1 S0 To S4-T05 Global Product Audit And Forward Plan](FIN_0_1_S0_TO_S4_T05_GLOBAL_PRODUCT_AUDIT_AND_FORWARD_PLAN_20260728.zh-CN.md)
- [PRODUCT 2026-06-28 FinSight ToB / ToC Positioning And Product Line](PRODUCT_20260628_finsight_tob_toc_positioning_and_product_line.zh-CN.md)
- [PRD 2026-06-28 B2B Financial Research Workbench](PRD_20260628_b2b_financial_research_workbench.zh-CN.md)
- [PRODUCT 2026-07-17 Release Ladder And Cadence](PRODUCT_20260717_release_ladder_and_cadence.zh-CN.md)
- [FIN 0.1 Internal Alpha Feature Scope Matrix](FIN_0_1_INTERNAL_ALPHA_FEATURE_SCOPE_MATRIX_20260717.zh-CN.md)
- [FIN 0.1 Workbench UX Benchmark And Interaction Blueprint](FIN_0_1_WORKBENCH_UX_BENCHMARK_INTERACTION_BLUEPRINT_20260719.zh-CN.md)
- [FIN 0.1 PRD / Product Stage Review](FIN_0_1_STAGE_REVIEW_20260719.zh-CN.md)

## Governance

- Product docs own product direction, user workflows, packaging, and business-facing acceptance criteria.
- Technical docs own implementation contracts, runtime architecture, database/API/data-source details, eval gates, and delivery decisions.
- Worklogs own factual execution records: what changed, what ran, what passed, what failed, and what remains.
- Mixed discussions should first be summarized into a product doc, then translated into separate technical requirements or delivery docs.
- Historical mixed docs should not be bulk-moved only for cleanup; new and touched docs should follow this split.
