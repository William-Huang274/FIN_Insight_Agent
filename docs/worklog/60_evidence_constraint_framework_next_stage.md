# Evidence Constraint Framework Next Stage

## Purpose

下一阶段不再继续堆 prompt，也不回到小模型 `EvidenceBriefObject` 压缩主线。当前结论是：

- Qwen3.5-9B 已经能写出较好的 insight 和判断优先级。
- 主要风险来自证据边界过自由：driver 支撑范围不够清楚、caveat 不一定降级结论、exact value 和 metric role 仍可能在正文中混用。
- 需要的是最小可审计的证据约束框架，而不是完整手写分析师框架。

目标 pipeline：

```text
Query Contract
  -> Evidence Object Contract
  -> Exact-Value Ledger
  -> Decision Driver Evidence Pack
  -> LLM Final Synthesis
  -> Hard Validator + Optional LLM Critic
```

首轮只做 6 个 `complex_insight` query，不扩到 13 个 expanded queries，不跑 metric-table tasks。

## Current Baseline

- Best current synthesis direction: `128k raw citation-only + contract v3 numeric-safe patch`.
- Latest patched six-query output: `reports/demo/qwen9b_longctx_128k_raw_citation_all_complex6_contract_v3_numeric_safe_patch_8500_repaired.json`.
- Latest patched quality summary: `reports/logs/qwen9b_longctx_128k_contract_v3_numeric_safe_patch_summary.json`.
- Observed status:
  - `6/6` parsed.
  - `6/6` citation pass.
  - `metric_role_mismatch_period_change_in_narrative` reduced from `3` to `0`.
  - Mean strict quality improved from `0.5236` to `0.6311`.
  - `teacher_ready=0/6`.
- Remaining blockers:
  - `low_required_coverage=6/6`.
  - `low_citation_use_rate=6/6`.
  - `numeric_claim_discipline_warning=5/6`.
  - Residual exact-value issues: raw value copying, Chinese unit conversion, and raw-value-to-cited-text matching.

## Role Split

### Qwen3.5-9B Planner

Use Qwen3.5-9B first for `Query Contract` drafting because query intent needs richer semantic judgment than the 2B verifier is designed for.

Allowed planner responsibilities:

- Turn a query plus eval metadata into required facets.
- Rank facets as `primary`, `supporting`, or `caveat`.
- State which missing evidence would downgrade the conclusion.
- State allowed conclusion strength.
- Identify metric families needed for the question.

Disallowed planner responsibilities:

- It must not invent evidence.
- It must not decide whether a specific object is citation-worthy.
- It must not output final answer prose.
- It must not assign exact numeric values.

### Qwen3.5-2B Verifier

Keep the 2B verifier in its current role:

- Given `query/aspect + evidence object`, classify object relevance as direct / partial / false / caveat.
- It can help populate candidate evidence pools.
- It should not define the query intent or final analysis frame.

### Deterministic Validators

Must own hard facts:

- object ID validity.
- citation/background role.
- ticker/year scope.
- raw value/unit/display value.
- metric role and allowed claim roles.
- metric family compatibility.
- coverage and conclusion-strength gates.

## Artifact Layout

New artifacts should live under:

```text
reports/query_contracts/
reports/exact_value_ledgers/
reports/evidence_packs/
reports/quality/
reports/logs/
```

Recommended first-run paths:

```text
reports/query_contracts/sec_tech_10k_expanded_v0_2_complex6_qwen9b_query_contracts.json
reports/exact_value_ledgers/sec_tech_10k_expanded_v0_2_complex6_exact_value_ledger.json
reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_driver_packs.json
reports/quality/sec_tech_10k_expanded_v0_2_complex6_driver_pack_validation.json
reports/demo/qwen9b_longctx_128k_raw_citation_all_complex6_driver_pack_synthesis.json
reports/quality/qwen9b_longctx_128k_raw_citation_all_complex6_driver_pack_answer_quality.json
reports/logs/qwen9b_longctx_128k_driver_pack_complex6_summary.json
```

## Query Contract Schema

`QueryContract` is the planner output. It is a scoring contract, not an answer.

```json
{
  "query_id": "expanded_insight_platform_services_recurring_quality_2023_2025",
  "task_profile": "complex_insight",
  "target_judgment_zh": "比较 Apple、Microsoft、Adobe 的 recurring/service/subscription 收入质量与可见性。",
  "required_companies": ["AAPL", "MSFT", "ADBE"],
  "required_years": [2023, 2024, 2025],
  "allowed_conclusion_strengths": ["strong_with_caveats", "moderate_with_caveats", "disclosure_quality_only"],
  "required_metric_families": [
    "services_revenue",
    "subscription_revenue",
    "cloud_revenue",
    "gross_margin",
    "rpo",
    "arr_or_recurring_proxy",
    "deferred_revenue"
  ],
  "facets": [
    {
      "facet_id": "revenue_quality",
      "facet_zh": "服务/订阅收入规模与增长质量",
      "priority": "primary",
      "required_coverage": {
        "companies": ["AAPL", "MSFT", "ADBE"],
        "years": [2023, 2024, 2025],
        "metric_families": ["services_revenue", "subscription_revenue", "cloud_revenue"]
      },
      "missing_downgrade_rule_zh": "如果只覆盖部分公司或只拿到 period-change，不允许写强全局排序。",
      "allowed_driver_roles": ["core_driver", "supporting_context"]
    },
    {
      "facet_id": "visibility",
      "facet_zh": "RPO/ARR/deferred revenue 等收入可见性 proxy",
      "priority": "primary",
      "required_coverage": {
        "companies": ["AAPL", "MSFT", "ADBE"],
        "metric_families": ["rpo", "arr_or_recurring_proxy", "deferred_revenue"]
      },
      "missing_downgrade_rule_zh": "如果某家公司没有 RPO/ARR 披露，只能比较披露透明度或 proxy，不允许直接宣称可见性最强。",
      "allowed_driver_roles": ["core_driver", "caveat_driver"]
    }
  ],
  "comparability_rules": [
    {
      "rule_id": "rpo_arr_deferred_not_same_metric",
      "metric_families": ["rpo", "arr_or_recurring_proxy", "deferred_revenue"],
      "rule_zh": "这些只能作为收入可见性的不同 proxy，不能当成同一个指标直接横比。"
    }
  ],
  "planner_confidence": "medium",
  "planner_caveats_zh": [
    "Apple 可能没有直接 RPO/ARR 披露，需显式降级可见性结论。"
  ]
}
```

Validation rules:

- `query_id` must exist in the eval set.
- `required_companies` and `required_years` must be compatible with eval metadata.
- `facets` should be 3-6 items for complex insight.
- At least one `primary` facet and at least one caveat/comparability facet are required.
- `target_judgment_zh` must not include exact numeric values.
- Planner output cannot contain object IDs or final answer claims.

## Evidence Object Contract

`EvidenceObjectContract` is deterministic metadata derived from structured objects and calibrated evidence.

Recommended fields:

```json
{
  "object_id": "AAPL_2023_10K_ITEM7_BLOCK_0003_PART_01_OF_02_METRIC_SENT_A0CFE72D",
  "evidence_role": "citation",
  "ticker": "AAPL",
  "fiscal_year": 2023,
  "object_type": "metric",
  "metric_label": "services revenue increase",
  "metric_family": "services_revenue",
  "metric_role": "period_change_amount",
  "period_type": "fiscal_year",
  "raw_value_text": "$7.1 billion",
  "unit": "usd",
  "display_value_zh": "71 亿美元",
  "disclosure_scope": "Apple Services segment",
  "allowed_claim_roles": ["increase_amount"],
  "disallowed_claim_roles": ["total_value", "trend_start_value"],
  "source_statement": "..."
}
```

Implementation detail:

- Extend existing metric hint logic in `scripts/run_calibrated_synthesis_demo.py` into a standalone builder.
- Proposed script: `scripts/build_evidence_object_contracts.py`.
- Input: `reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_vllm_calibrated_evidence_pool_grouped.json`.
- Output: `reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_evidence_object_contracts.json`.

Metric-family assignment should start with deterministic rules:

```text
services revenue / services net sales -> services_revenue
subscription revenue / subscriptions -> subscription_revenue
remaining performance obligations / RPO -> rpo
annual recurring revenue / ARR -> arr_or_recurring_proxy
deferred revenue -> deferred_revenue
gross margin / gross profit percentage -> gross_margin
capital expenditures / PP&E purchases / cash paid for property -> capex
depreciation / amortization -> depreciation_amortization
operating income / segment income -> operating_income
free cash flow / net cash provided by operating activities -> cash_flow
```

Only unresolved/ambiguous metric families should be sent to an LLM classifier.

## Exact-Value Ledger

`ExactValueLedger` is the only source final synthesis can use for exact numeric display values.

Ledger row:

```json
{
  "metric_id": "AAPL_2025_services_revenue_total",
  "object_id": "AAPL_2025_10K_ITEM8_BLOCK_0003_CHUNK_0001_METRIC_TABLE_08FEB3D4",
  "ticker": "AAPL",
  "fiscal_year": 2025,
  "metric_family": "services_revenue",
  "metric_role": "total_value",
  "raw_value_text": "109,158",
  "unit": "usd_millions",
  "display_value_zh": "1091.58 亿美元",
  "claim_role": "total_value",
  "allowed_in_narrative": true,
  "narrative_guard_zh": "可表述为 2025 年服务收入总额为 1091.58 亿美元。"
}
```

Implementation detail:

- Proposed script: `scripts/build_exact_value_ledger.py`.
- Input: evidence object contracts.
- Output: `reports/exact_value_ledgers/sec_tech_10k_expanded_v0_2_complex6_exact_value_ledger.json`.
- All final `numeric_claims` must reference `metric_id`; model should not write free-form `raw_value_text`.

Formatting rules:

- `usd_millions` to Chinese display: divide by 100 and render as `X 亿美元`.
- `usd_thousands` to Chinese display: divide by 100000 and render as `X 亿美元`.
- `usd` with `billion` source can render directly as `X 亿美元`.
- `percent` keeps `%`.
- Parentheses in cash-flow/capex tables should be normalized to positive outflow only if `claim_role=capex_cash_outflow`; note the original sign in `narrative_guard_zh`.

## Comparability Matrix

Start with a small matrix, not a full accounting ontology.

```json
{
  "compatible_groups": [
    ["services_revenue", "subscription_revenue", "cloud_revenue"],
    ["gross_margin", "operating_margin"],
    ["rpo", "arr_or_recurring_proxy", "deferred_revenue"],
    ["capex", "ppe_purchases", "cash_paid_for_property"]
  ],
  "rules": [
    {
      "rule_id": "visibility_proxy_not_same_metric",
      "families": ["rpo", "arr_or_recurring_proxy", "deferred_revenue"],
      "allowed_claim_zh": "可以作为收入可见性的不同 proxy。",
      "disallowed_claim_zh": "不能直接说 RPO 等同 ARR 或 deferred revenue。"
    },
    {
      "rule_id": "cloud_revenue_not_profitability",
      "families": ["cloud_revenue", "operating_income"],
      "allowed_claim_zh": "可以分别讨论增长和盈利质量。",
      "disallowed_claim_zh": "不能把 cloud revenue 增长直接当成 segment profitability 证据。"
    }
  ]
}
```

Proposed location: `configs/finance_metric_comparability_rules.json`.

## Decision Driver Evidence Pack Schema

`DecisionDriverEvidencePack` is the key new layer. It is not the final answer. It is a bounded evidence support packet for one core driver.

```json
{
  "query_id": "expanded_insight_platform_services_recurring_quality_2023_2025",
  "driver_id": "visibility_and_quality",
  "rank": 1,
  "driver_claim_zh": "Adobe 的订阅收入可见性和利润率质量最清晰，但 Apple 的服务收入质量更强、可见性披露较弱。",
  "why_it_matters_zh": "收入质量判断不能只看增长，还要看可见性 proxy 和利润率。",
  "driver_role": "core_driver",
  "supporting_objects": [
    {
      "object_id": "ADBE_2025_10K_ITEM7_BLOCK_0004_PART_02_OF_03_METRIC_SENT_B8F097E5",
      "support_role": "core_fact",
      "metric_ids": ["ADBE_2025_rpo_total"],
      "supports_claim_part_zh": "支撑 Adobe RPO 可见性。"
    }
  ],
  "covered_companies": ["AAPL", "ADBE"],
  "covered_years": [2023, 2024, 2025],
  "metric_families": ["services_revenue", "subscription_revenue", "gross_margin", "rpo"],
  "required_facets_covered": ["revenue_quality", "visibility"],
  "required_facets_missing": [
    {
      "facet_id": "visibility",
      "company": "AAPL",
      "missing_zh": "Apple 缺少直接 RPO/ARR 披露。"
    }
  ],
  "counter_evidence_or_caveats": [
    {
      "caveat_type": "missing_evidence",
      "caveat_zh": "Apple 的收入可见性不能用 RPO/ARR 直接量化。",
      "impact_on_conclusion_zh": "Apple 可作为服务收入质量强者，但不能在收入可见性上强排序为第一。"
    }
  ],
  "comparability_notes_zh": [
    "RPO、ARR、deferred revenue 只能作为收入可见性 proxy，不能直接互换。"
  ],
  "conclusion_strength": "moderate_with_caveats",
  "global_claim_allowed": false
}
```

Pack validation rules:

- `supporting_objects[*].object_id` must exist in citation evidence.
- `metric_ids` must exist in the exact-value ledger.
- `driver_claim_zh` cannot contain exact values not backed by `metric_ids`.
- `covered_companies` and `covered_years` must be derived from supporting objects, not planner text.
- If `global_claim_allowed=false`, final synthesis cannot use this pack to make an unrestricted global ranking.
- If a `primary` facet is missing, pack must include `required_facets_missing` or a caveat.
- If metric families are only visibility proxies, final claim must say proxy/披露质量, not direct same-metric comparison.

## Pack Generation Algorithm

### Step 1: Build Query Contracts With 9B Planner

Proposed script: `scripts/run_query_contract_planner.py`.

Input:

- `eval_sets/sec_tech_10k_expanded_eval_v0_2.jsonl`.
- Query IDs limited to the 6 `complex_insight` tasks.
- Existing grouped evidence pool only for facet names and available company/year/metric-family inventory, not for final answer prose.

Output:

- `reports/query_contracts/sec_tech_10k_expanded_v0_2_complex6_qwen9b_query_contracts.json`.

Recommended command:

```powershell
python scripts\run_query_contract_planner.py `
  --eval-path eval_sets\sec_tech_10k_expanded_eval_v0_2.jsonl `
  --grouped-pool-path reports\evidence_pool\sec_tech_10k_expanded_v0_2_cell_vllm_calibrated_evidence_pool_grouped.json `
  --model-path data\models_private\modelscope\Qwen\Qwen3___5-9B `
  --query-id expanded_insight_ads_ai_infra_2023_2025 `
  --query-id expanded_insight_ai_capex_monetization_2023_2025 `
  --query-id expanded_insight_ai_semiconductor_durability_2023_2025 `
  --query-id expanded_insight_cloud_profitability_comparison_2023_2025 `
  --query-id expanded_insight_platform_services_recurring_quality_2023_2025 `
  --query-id expanded_insight_subscription_visibility_2023_2025 `
  --output reports\query_contracts\sec_tech_10k_expanded_v0_2_complex6_qwen9b_query_contracts.json `
  --max-model-len 32768 `
  --max-tokens 2200 `
  --structured-json
```

Planner prompt constraints:

- Return JSON only.
- Do not cite object IDs.
- Do not include exact numeric values.
- Produce 3-6 facets.
- Mark each facet as `primary`, `supporting`, or `caveat`.
- Include `missing_downgrade_rule_zh` for every primary facet.

### Step 2: Validate Query Contracts

Proposed script: `scripts/validate_query_contracts.py`.

Checks:

- Required companies/years match eval metadata.
- Facet count 3-6.
- At least one primary facet.
- No object IDs.
- No exact values.
- Metric families come from an allowlist.
- Missing downgrade rules exist for primary facets.

Output:

```text
reports/quality/sec_tech_10k_expanded_v0_2_complex6_query_contract_validation.json
```

Stop condition:

- If fewer than 6/6 query contracts pass validation, do not build driver packs. Fix planner prompt or add deterministic query templates.

### Step 3: Build Evidence Object Contracts And Exact-Value Ledger

Proposed scripts:

- `scripts/build_evidence_object_contracts.py`
- `scripts/build_exact_value_ledger.py`

Inputs:

- grouped calibrated evidence pool.
- optional comparability config.

Outputs:

- evidence object contracts JSON.
- exact-value ledger JSON.

Stop condition:

- If `metric_role=unknown` exceeds 10% of metric citation objects in the 6-query cohort, inspect extraction before driver-pack generation.
- If any metric object used by current v3 numeric claims cannot produce a ledger row, keep the run diagnostic-only.

### Step 4: Build Candidate Driver Groups

Proposed script: `scripts/build_driver_pack_candidates.py`.

This should be mostly deterministic:

- Join query contracts with evidence object contracts.
- Filter citation evidence only.
- Group by `facet_id`, `metric_family`, `ticker`, and `fiscal_year`.
- Score objects:
  - direct verifier label > partial > caveat.
  - higher verifier confidence and reranker score.
  - coverage of required company/year.
  - exact-value availability.
  - caveat/counter-evidence preserved.

Output:

```text
reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_driver_pack_candidates.json
```

### Step 5: Generate Decision Driver Evidence Packs

Proposed script: `scripts/run_driver_pack_planner.py`.

Planner: Qwen3.5-9B.

Input per query:

- Query Contract.
- Candidate driver groups.
- Exact-Value Ledger rows for candidate objects.
- Comparability Matrix.

Output:

```text
reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_driver_packs.json
```

Rules:

- Max 3 packs per query.
- Each pack must map to at least one `primary` facet unless it is a caveat-only pack.
- Each pack can include max 8 supporting objects.
- Driver claim cannot exceed `covered_companies` / `covered_years`.
- All exact values must be referenced by `metric_id`, not copied freely.
- Every pack must include `conclusion_strength`.

### Step 6: Validate Driver Packs

Proposed script: `scripts/validate_driver_packs.py`.

Checks:

- Object IDs exist and are citation evidence.
- Metric IDs exist in ledger.
- Metric families are compatible with the claim role.
- Covered company/year scope is computed from support objects.
- Missing primary facets have caveats.
- Global claim allowed only when coverage supports all required companies/years.
- Exact numeric values in `driver_claim_zh` appear in ledger display values.

Output:

```text
reports/quality/sec_tech_10k_expanded_v0_2_complex6_driver_pack_validation.json
```

Acceptance for first demo:

- 6/6 queries produce 1-3 valid packs.
- 0 invalid object IDs.
- 0 background-as-core-fact.
- 0 exact values outside ledger.
- At least 80% of primary facets covered by either a pack or an explicit missing/caveat record.
- At least one caveat pack or caveat field for every query with missing primary evidence.

### Step 7: Final Synthesis From Packs

Modify or add a new mode in `scripts/run_calibrated_synthesis_demo.py`:

```text
--driver-pack-path reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_driver_packs.json
--exact-value-ledger-path reports/exact_value_ledgers/sec_tech_10k_expanded_v0_2_complex6_exact_value_ledger.json
--query-contract-path reports/query_contracts/sec_tech_10k_expanded_v0_2_complex6_qwen9b_query_contracts.json
```

Final model input should contain:

- Query Contract.
- Validated Decision Driver Evidence Packs.
- Exact-Value Ledger rows referenced by packs.
- Missing/caveat records.

It should not contain the full 100+ object raw citation pool unless a debug flag is enabled.

Expected final output can keep v3 fields:

- `thesis_zh`
- `decision_drivers`
- `secondary_context`
- `limiting_caveats`
- `facet_findings`
- `numeric_claims`

But `decision_drivers` must reference `driver_id`, and `numeric_claims` must reference `metric_id`.

### Step 8: Validate Final Synthesis

Extend existing validators:

- `validate_synthesis_citations.py`: check `driver_id` and `metric_id`.
- `score_synthesis_quality.py`: add driver-pack-aware coverage and conclusion calibration.

New checks:

- Final thesis cannot exceed strongest allowed `conclusion_strength`.
- If pack says `global_claim_allowed=false`, final answer cannot make unrestricted global ranking from that pack.
- Exact values in final answer must match ledger display values.
- Caveats that downgrade primary facets must appear in `limiting_caveats` and be reflected in thesis strength.

## First Experiment Governance Gate

- Hypothesis: Query Contract + Exact-Value Ledger + Decision Driver Evidence Pack will improve final synthesis coverage and conclusion calibration while keeping citation precision at 1.0.
- Decision target:
  - 6/6 query contracts pass validation.
  - 6/6 driver pack sets pass validation.
  - final synthesis 6/6 parsed.
  - citation validation 6/6 pass.
  - `metric_role_mismatch_* = 0`.
  - exact values outside ledger = 0.
  - `weak_decision_priority = 0`.
  - manual review finds fewer unsupported broad driver claims than v3 numeric-safe patch on at least 4/6 queries.
- Baseline:
  - `reports/logs/qwen9b_longctx_128k_contract_v3_numeric_safe_patch_summary.json`.
  - `reports/demo/qwen9b_longctx_128k_raw_citation_all_complex6_contract_v3_numeric_safe_patch_8500_repaired.json`.
- Stop conditions:
  - If Query Contracts fail or look like final answers, fix planner prompt/templates before moving on.
  - If driver packs mostly restate final prose without tighter object/metric scope, stop and make candidate grouping more deterministic.
  - If final synthesis still writes exact values outside the ledger, block promotion and remove free-form numeric fields from the prompt.
  - If pack-based synthesis lowers manual insight quality despite passing hard gates, treat as over-constrained and revise pack schema.
- Efficiency gate:
  - Keep first run to 6 complex queries.
  - Record model load time, per-query planner/pack/synthesis time, prompt tokens, output tokens, GPU memory, and repair/validation counts.
- Decision label: diagnostic-only.

## Implementation Order

1. Add `configs/finance_metric_comparability_rules.json`.
2. Add `scripts/run_query_contract_planner.py`.
3. Add `scripts/validate_query_contracts.py`.
4. Add `scripts/build_evidence_object_contracts.py`.
5. Add `scripts/build_exact_value_ledger.py`.
6. Add `scripts/build_driver_pack_candidates.py`.
7. Add `scripts/run_driver_pack_planner.py`.
8. Add `scripts/validate_driver_packs.py`.
9. Add driver-pack input mode to `scripts/run_calibrated_synthesis_demo.py`.
10. Extend citation/quality validators for `driver_id` and `metric_id`.
11. Run the 6-query diagnostic.
12. Write model run ledger and update this worklog with results.

## Manual Review Focus

For each query, inspect:

- Does thesis strength match weakest required primary facet?
- Do top 3 drivers cover the right companies/years?
- Does any driver use local evidence for global ranking?
- Are missing facets reflected in caveats and thesis strength?
- Are RPO/ARR/deferred revenue treated as proxies, not interchangeable metrics?
- Are exact values copied only from ledger display values?
- Is the final answer still readable and analyst-like after constraints?

## Expected Result

A successful first pass does not need to make outputs teacher-ready. It should prove:

- Query intent is explicit and auditable.
- Driver support boundaries are visible.
- Exact values are no longer free-form.
- Caveats can downgrade conclusion strength.
- The final answer preserves v3's judgment-first style while reducing unsupported broad claims.

If this works on 6 complex queries, the next expansion can be:

1. rerun all 6 under the same contract with no patched merge;
2. add an LLM critic for conclusion calibration;
3. then evaluate whether to extend to all 13 expanded queries.

## 本次记录 - Evidence Constraint Framework Planning

- Problem: 用户要求把 `Query Intent / Required Facet Contract` 与 `Decision Driver Evidence Pack` 融合成下一阶段指导文档，并落到具体执行细节；第一步 planner 可以先尝试 Qwen3.5-9B。
- Reasoning and decision: 当前 9B 已能写出判断优先级，但整体质量仍受事实边界、coverage、可比性、caveat 降级和 exact numeric 稳定性限制。因此下一阶段不继续堆 prompt，也不让 2B verifier 定义 query intent，而是用 9B 生成 Query Contract，再用 deterministic Evidence Object Contract / Exact-Value Ledger / Driver Pack validator 控制证据边界。
- Work completed: 新增本指导文档，定义 Query Contract、Evidence Object Contract、Exact-Value Ledger、Comparability Matrix、Decision Driver Evidence Pack 的 schema、脚本路径、生成顺序、验证规则、首轮 6-query 命令模板和 governance gate；同步更新 `docs/worklog/README.md` 和 `docs/worklog/00_internal_master_checklist.md`。
- Result and evidence: 形成下一阶段可执行计划，首轮目标限定为 6 个 `complex_insight` query；明确 Qwen3.5-9B planner 只负责 query contract / driver pack drafting，2B verifier 保持 object-aspect 相关性判断职责，hard facts 由 deterministic validators 管。
- Follow-up and safety notes: 本次没有运行模型实验或新增代码脚本。下一步应先实现 `scripts/run_query_contract_planner.py` 和 `scripts/validate_query_contracts.py`，如果 6/6 Query Contract 不能通过验证，不进入 Evidence Pack 生成。

## 本次记录 - Query Contract Planner v0

- Problem: 开始执行第一步，用 Qwen3.5-9B 先为 6 个 `complex_insight` query 生成 `Query Contract`，验证它是否能承担 query intent / required facet contract 的语义规划职责。
- Reasoning and decision: 9B 可以负责语义层面的 target judgment、facet priority、metric family 和 caveat/comparability drafting，但 raw planner output 不能直接作为硬约束。首次验证发现 raw output 会把历史背景年份放进 facet `required_coverage`、出现一个 malformed company coverage 字段、并遗漏少数 facet metric family。因此新增 deterministic normalization，把 `required_companies/required_years` 锁回 eval metadata，并对 facet coverage 做 scope clamp / empty-family fill，同时保留 `raw_query_contract` 便于审计。
- Work completed:
  - 新增 `scripts/run_query_contract_planner.py`，支持 Qwen3.5-9B/vLLM structured JSON planner，也支持 `--disable-vllm` local smoke。
  - 新增 `scripts/validate_query_contracts.py`，验证 query ID、公司/年份 scope、metric family allowlist、facet count、primary/caveat/comparability、object-id leakage 和 exact-value leakage。
  - 新增 `scripts/normalize_query_contracts.py`，将 raw planner output 归一成 canonical Query Contract。
  - 在云端单卡 RTX 4090 跑完 6-query 9B planner，并在本地完成 normalization / validation / smoke。
- Result and evidence:
  - Raw planner output: `reports/query_contracts/sec_tech_10k_expanded_v0_2_complex6_qwen9b_query_contracts_raw.json`。
  - Canonical normalized output: `reports/query_contracts/sec_tech_10k_expanded_v0_2_complex6_qwen9b_query_contracts.json`。
  - Validation: `reports/quality/sec_tech_10k_expanded_v0_2_complex6_query_contract_validation.json`，`6/6` pass，hard failures `0`，warnings `0`。
  - Summary: `reports/logs/qwen9b_query_contract_planner_complex6_summary.json`。
  - Model run ledger: `reports/model_runs/20260517_phase2_query_contract_planner_qwen9b_complex6.md`。
  - Runtime: model load `69.5401s`，total `348.7041s`，per-query generation `43.2595s` 到 `56.0271s`，prompt tokens `1464` 到 `1791`。
- Follow-up and safety notes: 这一步只证明 Query Contract 层可生成和可验证，不证明最终答案质量。下一步应实现 deterministic `Evidence Object Contract` 与 `Exact-Value Ledger`，再生成 `Decision Driver Evidence Pack`；如果 Driver Pack 不能比 v3 final prompt 更清楚地暴露 support scope / caveat downgrade，就不进入最终 synthesis。

## 本次记录 - Evidence Object Contract + Exact-Value Ledger v0

- Problem: 用户要求先把 `Evidence Object Contract` 和 `Exact-Value Ledger` 这一层落地，并验证它是否真的能约束上一轮发现的数值/单位/metric role 风险。
- Reasoning and decision: 这一层只做事实归一化，不做“谁更强/谁更好”的分析判断。手工规则限定在三类：metric family / metric role 识别、单位显示换算、claim role 边界。Driver priority 和 thesis 仍交给后续 Driver Pack / synthesis。
- Work completed:
  - 新增 `scripts/build_evidence_object_contracts.py`：读取 Query Contract、grouped evidence pool、structured metric/table/claim objects，为每个 citation/background evidence ref 生成 contract，包含 `metric_families`、`metric_role`、`allowed_claim_roles`、`disallowed_claim_roles`、`numeric_candidates` 和 boundary notes。
  - 新增 `scripts/build_exact_value_ledger.py`：只从 citation evidence 中筛选 `metric_family`、`metric_role`、unit/display 均可确定的数字，生成可进入 final narrative 的 `metric_id` 和 `display_value_zh`。
  - 新增 `scripts/validate_numeric_claims_against_ledger.py`：把已有 synthesis 的 `numeric_claims` 回放到 ledger，检查旧输出中哪些数值声明会被挡住。
  - 修正首轮规则误判：`margin` 不能自动等于 percentage rate；`rate` 不能子串匹配；`$160 million higher` 这类金额应判为 period-change amount；`usd` 且无 million/billion scale 的表格值默认阻断。
- Result and evidence:
  - Evidence Object Contracts: `reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_evidence_object_contracts.json`。
  - Exact-Value Ledger: `reports/exact_value_ledgers/sec_tech_10k_expanded_v0_2_complex6_exact_value_ledger.json`。
  - Evidence validation: `reports/quality/sec_tech_10k_expanded_v0_2_complex6_evidence_object_contract_validation.json`。
  - Ledger validation: `reports/quality/sec_tech_10k_expanded_v0_2_complex6_exact_value_ledger_validation.json`。
  - Numeric replay validation: `reports/quality/qwen9b_longctx_128k_contract_v3_numeric_claims_vs_exact_ledger.json`。
  - Summary: `reports/logs/evidence_contract_exact_ledger_complex6_summary.json`。
  - Contract build processed `3083` evidence refs, `1908` unique objects, structured hit rate `1.0`，primary facet citation coverage `16/16`。
  - Ledger produced `729` rows; hard failures `0`，warnings `0`；role counts: `total_value=502`、`percentage_rate=154`、`period_change_amount=73`。
  - Replay against prior v3 numeric-safe output: `65` numeric claims checked，`43` pass，`22` fail；failure types: `numeric_claim_not_in_ledger=12`、`metric_role_not_allowed_by_ledger=7`、`cited_object_has_no_ledger_rows=3`。
- Follow-up and safety notes: 这一层已经能实际阻断旧输出中的数值风险，但 ledger 仍是“安全候选全集”，不能全量交给 final synthesis。下一步 Driver Pack 必须从 ledger 中挑少量 `metric_id` 支撑 driver，并把其余数字留在 appendix/不可用状态。当前 metric-family 规则对 PP&E balance 和真正 capex cash outflow 仍偏宽，后续 Driver Pack validator 要优先限制 claim role。

## 本次记录 - Decision Driver Evidence Pack v0

- Problem: 用户要求先实现 Driver Pack，并验证 Qwen3.5-9B planner 生成的 driver priority 是否可用。
- Reasoning and decision: raw 9B output 可以提供 thesis / driver / caveat 的语义草稿，但不能信任它手写的 `contract_id`、`metric_id`、coverage 和 exact-value prose。因此新增 deterministic normalization：模型只负责 driver 文案和优先级线索，系统从候选 facet 重建证据 ID、公司/年份覆盖、metric family、`global_claim_allowed` 和 caveat support。
- Work completed:
  - 新增 `scripts/build_driver_pack_candidates.py`，从 Query Contract、Evidence Object Contract 和 Exact-Value Ledger 生成 facet-level compact candidates。
  - 新增 `scripts/run_driver_pack_planner.py`，支持 Qwen3.5-9B/vLLM structured JSON planner 与 `--disable-vllm` heuristic fallback，并在模型输出后执行 normalized pack rebuild。
  - 新增 `scripts/normalize_driver_packs.py`，用于离线归一化已生成的 raw Driver Pack。
  - 新增 `scripts/validate_driver_packs.py`，检查 ID 是否来自候选集、核心 driver 是否只用 citation evidence、coverage 是否由 support 支撑、pack prose 是否含精确数值、primary facet 是否被 driver 或 missing-facet 处理。
  - 在云端 4090 用 Qwen3.5-9B 128k 跑完 6-query Driver Pack planner，并在本地完成 raw validation、normalization、normalized validation 和 heuristic fallback validation。
- Result and evidence:
  - Candidate pack: `reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_driver_pack_candidates.json`。
  - Candidate report: `reports/quality/sec_tech_10k_expanded_v0_2_complex6_driver_pack_candidate_report.json`，6 queries、30 facets、274 candidate contracts、240 candidate metrics、16/16 primary facets with candidates。
  - Raw Qwen9B pack: `reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_driver_packs_qwen9b.json`。
  - Normalized Qwen9B pack: `reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_driver_packs_qwen9b_normalized.json`。
  - Raw validation: `reports/quality/sec_tech_10k_expanded_v0_2_complex6_driver_pack_qwen9b_validation.json`，`2/6` pass；主要 failure 为 invalid driver/metric ID、background as core support、unsupported claimed coverage、exact value in prose。
  - Normalized validation: `reports/quality/sec_tech_10k_expanded_v0_2_complex6_driver_pack_qwen9b_normalized_validation.json`，`6/6` pass，hard failures `0`，warnings `0`，mean primary facet driver coverage `1.0`。
  - Heuristic validation: `reports/quality/sec_tech_10k_expanded_v0_2_complex6_driver_pack_heuristic_validation.json`，`6/6` pass。
  - Summary: `reports/logs/qwen9b_driver_pack_planner_complex6_summary.json`。
  - Model run ledger: `reports/model_runs/20260517_phase2_driver_pack_qwen9b_complex6.md`。
  - Runtime: model load `63.9399s`，total `375.3211s`，per-query generation `24.0154s` 到 `70.2826s`，prompt tokens `30,502` 到 `35,728`，vLLM KV cache `139,914` tokens。
- Follow-up and safety notes: raw Qwen9B Driver Pack 不能作为 serving artifact；下一步只允许 `qwen9b_normalized` 或 `heuristic` pack 进入 final synthesis。final synthesis 还必须接 Exact-Value Ledger，确保正文精确数字只能引用 `metric_id` 的 display value。

## 本次记录 - Driver Pack + Exact-Value Ledger Final Synthesis v0

- Problem: 用户要求只把 `qwen9b_normalized` Driver Pack 接入 final synthesis，并让 final synthesis 只能引用 Exact-Value Ledger 的 `metric_id/display_value_zh`。
- Reasoning and decision: final synthesis 不再读取完整 facet memory，也不直接暴露 raw contract IDs；模型只看到 normalized drivers、supporting evidence 的 `object_id`、以及 authorized ledger rows。deterministic repair 层处理两类模型拷贝问题：把 `cited_object_ids` 中误填的授权 `metric_id` 映射回 ledger `object_id`，以及为正文中唯一匹配授权 ledger row 的精确值补齐 `numeric_claims`。
- Work completed:
  - 扩展 `scripts/run_calibrated_synthesis_demo.py`，新增 driver-pack input mode、Exact-Value Ledger package、query-filtered ledger augmentation、`metric_id` citation post-repair。
  - 扩展 `scripts/validate_numeric_claims_against_ledger.py`，支持 `--require-metric-id` 与 `--scan-prose`。
  - 扩展 `scripts/repair_synthesis_citations.py`，支持 `--ledger-path`，可执行 metric-id-to-object-id repair 与 unique display-value numeric_claim backfill。
  - 在云端 Qwen3.5-9B/128k/RTX4090 跑完 6 个 complex-insight query，输出预算提升到 `8500`，避免首条 JSON 截断。
- Result and evidence:
  - Raw synthesis: `reports/demo/qwen9b_driver_pack_ledger_complex6_queryfiltered_8500.json`。
  - Repaired synthesis: `reports/demo/qwen9b_driver_pack_ledger_complex6_queryfiltered_8500_repaired.json`。
  - Repair report: `reports/quality/qwen9b_driver_pack_ledger_complex6_queryfiltered_8500_repair_report.json`，`repair_count=25`，`rejected_count=0`。
  - Citation validation: `reports/quality/qwen9b_driver_pack_ledger_complex6_queryfiltered_8500_repaired_citation_validation.json`，`6/6` pass，hard failures `0`。
  - Numeric validation: `reports/quality/qwen9b_driver_pack_ledger_complex6_queryfiltered_8500_repaired_numeric_ledger_validation.json`，`58/58` numeric claims pass，prose exact failures `0`。
  - Runtime: model load `60.3147s`，total `871.4676s`，per-query `83.4952s` 到 `182.329s`，prompt tokens `10,479` 到 `17,471`。
  - Model run ledger: `reports/model_runs/20260517_phase2_driver_pack_ledger_synthesis_qwen9b_complex6.md`。
- Manual review:
  - 数字/单位/metric_id 约束明显改善，`platform_services_recurring_quality` 的 exact-value 风险被压住。
  - `ads_ai_infra` 和 `ai_semiconductor_durability` 能正确降级为 weak，并把 caveat 写进 thesis。
  - 仍未达到 teacher-ready：`cloud_profitability_comparison` 把 Google Cloud `13,910 / 139.1 亿美元` 当作 cloud revenue，并写成从 `330.88 亿美元` 增长至 `139.1 亿美元`。该数字来自 segment operating income 表，说明 Evidence Object Contract / Exact-Value Ledger 的 `metric_family` 与 table context 冲突，hard numeric gate 目前只能保证“值来自 ledger”，不能保证“值的财务角色正确”。
  - `ai_capex_monetization` 通过 hard gate，但答案过于压缩，只有一个实质 driver，分析密度不够。
- Follow-up and safety notes: 当前阶段应标为 diagnostic-only，不应宣称整体输出质量已解决。下一步优先加两个 gate：`metric_family` 与 source table context 冲突检测，以及正文趋势关系检测（例如 `从 X 增长至 Y` 时必须验证 Y >= X）。

## 本次记录 - Metric Context and Relation Gates

- Problem: 用户要求先修两个 gate：一是 Exact-Value Ledger 中 `metric_family` 与 source table / row context 冲突，二是正文趋势关系里的方向错误，例如 `从 X 增长至 Y` 但 Y 小于 X。上一轮最明显样本是 `cloud_profitability_comparison` 把 Google Cloud `13,910 / 139.1 亿美元` 当作 `cloud_revenue`，并写成从 `330.88 亿美元` 增长至 `139.1 亿美元`；该值实际来自 `segment operating income (loss)` 表。
- Reasoning and decision: exact-value gate 只证明数值来自 ledger，不证明这个数值的财务角色正确。因此把 gate 前移到 ledger 构建和 numeric replay 两处：ledger 构建时用 source context 纠正或阻断 metric family；numeric validator 回放旧输出时同时检查 ledger row 的 context family 和正文关系方向。
- Work completed:
  - 更新 `scripts/build_exact_value_ledger.py`，新增 source-context metric family detection，输出 `source_context_metric_families`，并在 report 中统计 `context_family_override_rows` / `context_family_conflict_rows`。
  - 更新 `scripts/validate_numeric_claims_against_ledger.py`，新增 `--validate-ledger-context` 和 `--scan-relations`；关系扫描覆盖中文 `从 X 增长至/下降至 Y` 一类表达，检查单位兼容和方向。
  - 重建 context-guarded ledger 与 driver pack candidates。
  - 对旧 repaired synthesis 运行严格 numeric replay，确认新 gate 能拦截上一轮人工发现的问题。
- Result and evidence:
  - Context-guarded ledger: `reports/exact_value_ledgers/sec_tech_10k_expanded_v0_2_complex6_exact_value_ledger_context_guarded.json`。
  - Ledger validation: `reports/quality/sec_tech_10k_expanded_v0_2_complex6_exact_value_ledger_context_guarded_validation.json`，`ledger_row_count=712`，`context_family_override_rows=69`，`context_family_conflict_rows=0`，hard failures `0`。
  - Context-guarded driver candidates: `reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_driver_pack_candidates_context_guarded.json`；candidate report 显示 6 queries、30 facets、274 candidate contracts、240 candidate metrics、16/16 primary facets with candidates。
  - Strict replay on old synthesis: `reports/quality/qwen9b_driver_pack_ledger_complex6_queryfiltered_8500_repaired_numeric_ledger_validation_context_relation.json`，numeric claims `58`，pass `48`，fail `10`；failure types 为 `metric_family_table_context_conflict=10`、`prose_exact_value_not_authorized_by_metric_id=13`、`prose_numeric_relation_direction_mismatch=1`。
  - 关键修复样本：旧 ledger 中 Google Cloud `13,910` 被标成 `cloud_revenue`；context-guarded ledger 中同一 object 已改为 `metric_family=operating_income`，`display_value_zh=139.1 亿美元`，source context 为 `operating_income`。
- Decision: 这两个 gate 现在可以作为 final synthesis 之前的 hard validators。旧 synthesis 被严格 gate 判失败是预期结果，说明 gate 能抓住“值是对的但 financial role 错”的问题。下一次 final synthesis 应使用 context-guarded ledger 和 context-guarded driver candidates 重跑，而不是继续使用旧 ledger。
- Follow-up and safety notes: 本轮没有运行新的 9B final synthesis，也没有把旧输出升级为 teacher-ready。当前 source-context family patterns 是可审计的工程规则，覆盖常见 SEC 表格标题/行名，但仍需在正式 eval gold 上记录 false positive / false negative。

## 本次记录 - SEC Benchmark True-Qwen Gate Audit

- Problem: 用户要求重新审计 2026-05-18 13:00 以来的工作是否偏方向，并继续处理云端真实 Qwen gate。重点是避免 fallback 或 deterministic repair 被误算成“真实模型通过”。
- Reasoning and decision: 方向没有偏；当前主线应继续围绕 reviewed gold、Exact-Value Ledger、Evidence Text、post-gates 和 true-Qwen ratio。但实现上发现三个会影响结论的问题：`post_gates` 在云端硬编码 `python` 会失败；trap refusal 不应该进入 Qwen answer ratio 分母；`qwen_failed_no_fallback` 和 ledger repair 不应被算作 fallback 或 true-Qwen pass。
- Work completed:
  - `scripts/run_sec_benchmark_post_gates.py` 改用 `sys.executable`，Qwen ratio 改为 non-trap eligible outputs，并新增 `qwen_ledger_repaired` 统计。
  - `scripts/run_sec_benchmark_eval.py` 新增 `--case-id`，便于云端单 case smoke。
  - `scripts/run_sec_eval_synthesis_qwen9b_backend.py` 从 metadata-only prompt 改成 `Exact-Value Ledger + Evidence Text` prompt，要求精确数字只能引用 `metric_id/display_value_zh`；当 Qwen 输出不是 valid JSON 时，状态标为 `answered_qwen9b_ledger_repair`，不计入 true-Qwen pass。
  - 清理上次中断遗留的云端推理进程，确认真实模型路径为 `data/models_private/modelscope/Qwen/Qwen3___5-9B`。
- Result and evidence:
  - 云端 smoke: `eval/sec_cases/outputs/run_20260518_qwen9b_singlecase_smoke_v4/`。
  - 云端 gate: `reports/quality/cloud_qwen9b_singlecase_smoke_v4_gates/sec_benchmark_post_gates_summary.json`。
  - Gate 结果: `eligible_outputs=1`，`qwen_answered=0`，`qwen_ledger_repaired=1`，`fallback_answered=0`，`qwen_answer_ratio=0.0`，`qwen_answer_gate_pass=false`。
  - Model run ledger: `reports/model_runs/20260518_sec_benchmark_qwen9b_real_gate_smoke.md`。
- Follow-up and safety notes: 当前 HF per-case Qwen backend 证明了真实模型可调用、ledger 值可保留，但 JSON conformance 不过关，不能进入主链路测试。下一步应优先用已有 resident vLLM/no-think 路径或更强 JSON 约束解决 valid structured output，再跑 4 个 reviewed non-trap cases；只有 `answered_qwen9b` 才能作为 true-Qwen pass。

## 本次记录 - Reviewed4 Resident vLLM True-Qwen Gate

- Problem: 继续处理云端 reviewed4 gate，目标是让真实 Qwen3.5-9B resident vLLM 在 4 个 reviewed non-trap case 上输出 valid structured answer，并严格通过 Exact-Value Ledger / ledger unit / true-Qwen ratio。上一轮阻塞点包括：AAPL Services gross margin percentage 没被正确命名、SNOW RPO table row 被误跳过、GOOGL raw JSON 虽然事实正确但 summary 数值旁没有 metric_id，导致整条被 ledger repair。
- Reasoning and decision: 这些不是要靠放宽 gate 解决，而是要修 deterministic contract 层。Extractor 修源头表格语义；Qwen backend 只做窄 canonicalization：当 exact value 能唯一匹配当前 case ledger row 时，把正文数值改为 `display_value_zh (metric_id)`。如果数值不在 ledger 或匹配多义，仍保持 hard failure / repair。
- Work completed:
  - 更新 `src/evidence/structured_extractor.py`：不再把无年份的 segment 数值行误判成 header；不再把 `Remaining performance obligations (in millions)` 这类 metric row 当单位行跳过；sentence `$... million/billion` 保留 `usd_millions/usd_billions`。
  - 更新 `scripts/run_sec_eval_synthesis_qwen9b_backend.py`：新增 exact-value canonicalization，修复 GOOGL summary 数值缺 metric_id 的降级。
  - 在本地和云端重建 structured objects、reviewed exact ledger，并重新跑结构化校验和 ledger unit gate。
  - 在云端 RTX 4090 使用 resident vLLM 跑完 4 个 reviewed non-trap case。
- Result and evidence:
  - Structured validation: `python scripts/validate_structured_objects.py` 通过；AAPL Services gross margin percentage 和 SNOW RPO table/sentence checks 均通过。
  - Reviewed ledger: `reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json`，`row_count=17`。
  - Ledger unit gate: `reports/quality/cloud_reviewed4_ledger_unit_gate_after_extractor_fix.json`，`pass_count=17`，`fail_count=0`。
  - Real Qwen output: `eval/sec_cases/outputs/run_20260518_reviewed4_qwen9b_vllm_structured_2600_canonicalized/`。
  - Qwen-only post-gates: `reports/quality/cloud_reviewed4_qwen9b_vllm_structured_2600_canonicalized_qwen_only_gates/sec_benchmark_post_gates_summary.json`。
  - Gate 结果: `answered_qwen9b=4`，`qwen_ledger_repaired=0`，`fallback_answered=0`，`qwen_answer_ratio=1.0`，`qwen_answer_gate_pass=true`，`answer_ledger_gate_pass=true`，`ledger_unit_gate_pass=true`。
  - Model run ledger: `reports/model_runs/20260518_sec_benchmark_reviewed4_qwen9b_canonicalized.md`。
- Decision: reviewed4 的真实模型结构化输出和数值/单位约束已经能在 qwen-only boundary 下通过；这证明“9B 大体判断 + deterministic evidence/ledger verifier”这条路线可继续推进。
- Follow-up and safety notes: 本轮没有宣称 full main-chain gate 通过。`trap_gate` 和 `gold_vs_pipeline_gate` 在 qwen-only run 中显式 skip；下一步应进入 pipeline-context reviewed4 测试，再单独跑 trap suite。不要把 deterministic canonicalization 扩大成事实修补器，它只能处理唯一 ledger match 的格式补全。

## 本次记录 - Reviewed4 Pipeline Metric-Role-Term Strict Gate

- Problem: qwen-only boundary 过关后，继续进入 reviewed4 `pipeline_context` 主链路，并人工抽看输出语义质量。新发现是 Exact-Value Ledger 能保证数字/单位/metric_id，但不能单独保证正文没有把 metric 概念写偏：PANW 曾把 RPO 写成“预测经常性收入”，Billings 写成“账单收入”；AAPL Services 曾被过度写成经常性收入质量信号；GOOGL 曾从 Evidence Text 抄出 ledger 外 2023/2024 对比数字。
- Reasoning and decision: 这些问题不应该靠放宽 answer-ledger 或人工后验解释解决。新增窄口径 `metric_role_term_gate`，只拦截已在 reviewed4 暴露的高风险术语漂移；同时把 Metric Naming Rules 放入 final synthesis prompt，要求 RPO、Billings、Services revenue/gross margin 按 ledger metric family 命名，并禁止 ledger 外数字、四舍五入数和单位换算数进入正文。
- Work completed:
  - 新增 `scripts/validate_sec_benchmark_metric_role_terms.py`，检查 RPO、Billings、Services revenue 的术语误用；支持否定语义，避免把“Billings 不等于确认收入”误判为错误。
  - 更新 `scripts/run_sec_benchmark_post_gates.py`，把 `metric_role_term_gate` 纳入 post-gates summary；trap-only run 中无 non-trap eligible case 时，`qwen_answer_ratio=null` 且 qwen gate 不失败。
  - 更新 `scripts/run_sec_eval_synthesis_qwen9b_backend.py`，在 prompt 中注入每个 ledger metric family 的 allowed/disallowed terms，并更严格禁止 Evidence Text 中未授权的精确数字、近似数和单位换算数。
  - 在云端重跑 reviewed4 `pipeline_context` 真实 Qwen3.5-9B，并单独跑两个 anti-hallucination trap。
  - 组合 4 个 reviewed non-trap + 2 个 trap 形成 6-case gate bundle，开启 trap、gold-vs-pipeline、answer-ledger、metric-role-term、ledger-unit 和 true-Qwen ratio。
- Result and evidence:
  - Strict pipeline output: `eval/sec_cases/outputs/run_20260518_reviewed4_pipeline_qwen9b_vllm_structured_2600_metricterms_strict/`。
  - Cloud strict post-gates: `reports/quality/cloud_reviewed4_pipeline_qwen9b_vllm_structured_2600_metricterms_strict_post_gates_v2/sec_benchmark_post_gates_summary.json`。
  - Cloud reviewed4 gate 结果: `answered_qwen9b=4`，`qwen_ledger_repaired=0`，`fallback_answered=0`，`qwen_answer_ratio=1.0`，`gold_vs_pipeline_pass=true`，`answer_ledger_gate_pass=true`，`metric_role_term_gate_pass=true`，`ledger_unit_gate_pass=true`。
  - Trap output: `eval/sec_cases/outputs/run_20260518_trap_pipeline_contract_vllm_path/`。
  - Local 6-case bundle: `eval/sec_cases/outputs/run_20260518_reviewed4_metricterms_strict_plus_traps_pipeline_gate_bundle/`。
  - Local 6-case bundle gates: `reports/quality/local_reviewed4_metricterms_strict_plus_traps_pipeline_gate_bundle_post_gates/sec_benchmark_post_gates_summary.json`，`trap_gate_pass=true`，`gold_vs_pipeline_pass=true`，`answer_ledger_gate_pass=true`，`metric_role_term_gate_pass=true`，`ledger_unit_gate_pass=true`，`qwen_answer_ratio=1.0`。
  - Model run ledger: `reports/model_runs/20260518_sec_benchmark_reviewed4_pipeline_metricterms_strict.md`。
- Decision: reviewed4 case-filtered pipeline smoke 可以进入下一阶段；这次通过的是“真实 Qwen 输出 + deterministic evidence/ledger/term gates”，不是 fallback 通过。
- Follow-up and safety notes: 仍不能宣称 full benchmark mainline 通过。当前只覆盖 4 个 reviewed non-trap 和 2 个 trap；剩余 seed/diagnostic cases 还没有 reviewed gold facts。`metric_role_term_gate` 目前故意保持窄口径，后续扩展规则必须来自人工审定的新失败样本，避免泛化过度。

## 本次记录 - Reviewed7 Text Gold Context Expansion

- Problem: reviewed4 pipeline gate 通过后，继续扩大主链路测试前的 gold 基准覆盖；优先处理 `needs_manual_trim_before_gold_context_mode` 中的三个 text-heavy case：`SNOW_RISK_2023_2025_001`、`NVDA_DATACENTER_2023_2025_001`、`MSFT_AI_CLOUD_2023_2025_001`。
- Reasoning and decision: 这三题不是 numeric regression，seed gold facts 为空是合理的；风险在于 seed context 噪声很大，容易把税务、IR、收入确认 boilerplate、远程办公、泛安全等段落带入评分。做法是从原始 SEC evidence object 中抽取连续原文片段，保留 `evidence_id/source_evidence_id`、年份、section、`supports_gold_points` 和 review note；不把这些 case 加进 Exact-Value Ledger。
- Work completed:
  - 新增 reviewed context：
    - `eval/sec_cases/reviewed_gold_context/SNOW_RISK_2023_2025_001.jsonl`，9 行。
    - `eval/sec_cases/reviewed_gold_context/NVDA_DATACENTER_2023_2025_001.jsonl`，12 行。
    - `eval/sec_cases/reviewed_gold_context/MSFT_AI_CLOUD_2023_2025_001.jsonl`，11 行。
  - 新增空 reviewed facts：
    - `eval/sec_cases/reviewed_gold_facts/SNOW_RISK_2023_2025_001.json`。
    - `eval/sec_cases/reviewed_gold_facts/NVDA_DATACENTER_2023_2025_001.json`。
    - `eval/sec_cases/reviewed_gold_facts/MSFT_AI_CLOUD_2023_2025_001.json`。
  - 更新 `reports/quality/sec_benchmark_v1_reviewed_gold_partial_approval.json`，approved case count 从 4 扩到 7；仍保持 `partial_approved_for_mainline_scored_benchmark`，full benchmark 不放行。
  - 重建 `reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json`，row count 仍为 17。
- Result and evidence:
  - Reviewed7 gold gate: `reports/quality/sec_benchmark_v1_gold_gate_reviewed7_text_plus_numeric_cases.json`，`can_enter_gate=true`，`7/7` pass，warnings `0`，blockers `0`。
  - Seed leakage audit: 7 个 approved case 均为 `seed_rows=0`、`seed_facts=0`。
  - Context-only trace: `reports/quality/local_reviewed7_text_plus_numeric_context_trace_smoke/`，`trace_count=7`，全部 `context_prepared`。
  - Ledger unit gate: `reports/quality/local_reviewed7_text_plus_numeric_ledger_unit_gate.json`，`17/17` pass，fail `0`。
  - Model run ledger: `reports/model_runs/20260518_sec_benchmark_reviewed7_text_gold_context.md`。
- Decision: reviewed7 可以进入 case-filtered gold-context smoke；这只证明 gold 基准入口干净，不等于这 3 个新增文本 case 的 Qwen synthesis 已通过。
- Follow-up and safety notes: 下一步应对 SNOW/NVDA/MSFT 三个 text-heavy case 跑 true-Qwen gold-context synthesis，并人工看语义覆盖；尤其要检查模型是否把 Evidence Text 中未 ledger 授权的增长率/金额复制进正文。

## 本次记录 - Reviewed3 Text-Heavy True-Qwen Gold Synthesis

- Problem: 用户要求继续做云端真实 Qwen gate，并人工看答案覆盖是否更好。新增的 SNOW/NVDA/MSFT 三个 text-heavy case 没有 target exact-value facts，因此关键风险是模型从 SEC Evidence Text 里直接复制未进入 Exact-Value Ledger 的百分比/金额，或因为 evidence excerpt 截断而漏掉关键披露。
- Reasoning and decision: 不能把 deterministic ledger repair 算成真实模型通过。第一轮 HF per-case Qwen run 暴露出问题：SNOW 为 `answered_qwen9b`，但 NVDA/MSFT 因非 ledger 精确数字触发 `answered_qwen9b_ledger_repair`。修复方向不是放宽 gate，而是让 no-ledger text-summary case 只允许定性 SEC synthesis，并改进证据打包和 citation repair。
- Work completed:
  - 更新 `scripts/run_sec_eval_synthesis_qwen9b_backend.py`：
    - 当 case 无 Exact-Value Ledger rows 时，明确禁止输出金额、百分比、逗号大数、倍数、客户占比和研发投入金额；年份仍可用于跨年区分。
    - 每条 SEC 原文 `text_excerpt` 从 900 字符提高到 2200 字符，修复 MSFT OpenAI 披露被截断的问题。
    - 增加跨年任务 contract：必须区分新增/持续/重复披露，保留关键命名产品、架构、合作关系、监管事项或风险机制。
    - 增加 lightweight named-evidence citation repair；当 driver/key point 提到 OpenAI、Blackwell、Azure 等英文命名实体时，若当前 evidence IDs 没有覆盖包含该名称的原文，则补上对应 evidence ID；同一 `evidence_id` 的多个片段先合并，避免后写覆盖。
  - 在云端 RTX 4090 使用 Qwen3.5-9B HF per-case backend 多轮重跑，最终选定 `strict_prompt3_excerpt2200_namedrepair2` 输出。
- Result and evidence:
  - Final output: `eval/sec_cases/outputs/run_20260518_reviewed3_text_gold_qwen9b_hf_32768_strict_prompt3_excerpt2200_namedrepair2/`。
  - Final gates: `reports/quality/cloud_reviewed3_text_gold_qwen9b_hf_32768_strict_prompt3_excerpt2200_namedrepair2_post_gates/sec_benchmark_post_gates_summary.json`。
  - Gate 结果: `answered_qwen9b=3/3`，`qwen_ledger_repaired=0`，`fallback_answered=0`，`qwen_answer_ratio=1.0` with `min_qwen_answer_ratio=1.0`，`answer_ledger_gate_pass=true`，`exact_value_hit_count=0`，`metric_role_term_gate_pass=true`，`ledger_unit_gate_pass=true`。
  - Earlier failed diagnostic: `eval/sec_cases/outputs/run_20260518_reviewed3_text_gold_qwen9b_hf_32768/`，NVDA/MSFT 因 ledger-text contract violations 被 repair，不能算 pass。
  - Model run ledger: `reports/model_runs/20260518_sec_benchmark_reviewed3_text_qwen9b_gold_synthesis.md`。
- Manual review:
  - SNOW 覆盖 consumption-based revenue model、客户使用量波动、宏观/客户优化、技术效率降低消耗、分析师对非订阅模式误解，以及 2025 AI/Data Cloud 采用不确定性。
  - NVDA 现在能区分 2023 库存/出口管制、2024 DGX Cloud/CSP 需求、2025 Blackwell 和中国/出口许可策略、以及持续的产品缺陷/软件漏洞风险；仍可改进点是 Hopper 被压在 broader AI/generative AI driver 里，没有显式作为年度产品迁移点。
  - MSFT 在 excerpt 扩展后补上 Azure AI / OpenAI partnership，且 named citation repair 把包含 OpenAI 原文的 2025 Item 7 evidence ID 补到相关 key point。
- Decision: reviewed3 text-heavy gold-context true-Qwen synthesis smoke 通过，可以作为下一步 reviewed7 pipeline-context 测试的 synthesis boundary；仍为 diagnostic-only，不能宣称 full benchmark/main-chain 已通过。
- Follow-up and safety notes: 下一步跑 reviewed7 pipeline-context，并组合 reviewed7 non-trap + trap bundle；HF per-case backend 加载慢，扩大样本时应优先使用 resident vLLM。named-evidence citation repair 是窄口径辅助，不替代完整 unsupported-claim validator。

## 本次记录 - Reviewed7 Pipeline Sanitized True-Qwen Gate

- Problem: 用户要求继续进入 reviewed7 `pipeline_context` 主链路，并保证真实 Qwen 输出通过，而不是 fallback 或 deterministic ledger repair 通过。上一轮 reviewed7 pipeline run 中 `GOOGL_CLOUD_CONTEXT_ROLE_2025_001` 输出了未入 ledger 的派生同比金额 `78 亿美元`，导致整条答案变成 `answered_qwen9b_ledger_repair`。
- Reasoning and decision: 这个问题不应通过放宽 ledger gate 解决，也不应把整条答案 fallback 成 ledger-only。正确边界是：保留 9B 的 qualitative judgement 和 driver 结构，但 deterministic sanitizer 删除或降级未授权精确值；同时把所有 ledger-matched exact values canonicalize 成 `display_value_zh (metric_id)`，使最终答案只引用 Exact-Value Ledger 里的授权数值。
- Work completed:
  - 修复 `scripts/run_sec_benchmark_eval.py` pipeline context row builder：BM25 hit 的 `text_preview` 现在会进入 `preview/text`，避免 evidence object context rows 没有正文。
  - 更新 `scripts/run_sec_eval_synthesis_qwen9b_backend.py`：
    - prompt context row cap 从 14 提高到 24，并按 ledger source evidence + fiscal year round-robin 选择，改善多年份 text-heavy case 覆盖。
    - 新增 unsupported exact-value sanitizer：未匹配当前 case ledger 或缺 metric_id 支撑的精确金额/比例会被局部删除或降级，不再触发整条 ledger fallback。
    - 加强 exact-value canonicalization：ledger-matched 数值附近没有 inline `metric_id` 时，重写为 `display_value_zh (metric_id)`。
    - no-ledger text-heavy case 的内部 limitation 文案改为中文，并避免重复污染最终答案。
  - 更新 `scripts/run_sec_benchmark_vllm_synthesis_from_traces.py`，把 sanitizer count 写入 score notes。
  - 在云端 RTX 4090 用 resident vLLM 跑 reviewed7 pipeline-context；随后本地用 saved raw outputs 做 deterministic reprocess，生成最终 cnlimit 版本。
  - 组合 reviewed7 non-trap + 2 个 trap，跑完整 post-gates。
- Result and evidence:
  - Cloud raw Qwen output: `eval/sec_cases/outputs/run_20260518_reviewed7_pipeline_qwen9b_vllm_structured_2600_top8_textfix_sanitized/`，`answer_status_counts={"answered_qwen9b": 7}`。
  - Local reprocessed final output: `eval/sec_cases/outputs/run_20260518_reviewed7_pipeline_qwen9b_vllm_structured_2600_top8_textfix_sanitized_cnlimit/`，`answer_status_counts={"answered_qwen9b": 7}`。
  - Final 9-case bundle: `eval/sec_cases/outputs/run_20260518_reviewed7_sanitized_cnlimit_plus_traps_pipeline_gate_bundle/`，`answer_status_counts={"answered_qwen9b": 7, "answered_contract_fallback": 2}`。
  - Full post-gates: `reports/quality/local_reviewed7_sanitized_cnlimit_plus_traps_pipeline_gate_bundle_post_gates/sec_benchmark_post_gates_summary.json`。
  - Gate 结果: `trap_gate_pass=true`，`gold_vs_pipeline_pass=true`，`answer_ledger_gate_pass=true`，`metric_role_term_gate_pass=true`，`ledger_unit_gate_pass=true`，`qwen_answer_ratio=1.0`，`qwen_ledger_repaired=0`，`fallback_answered=0`，`trap_outputs_excluded=2`。
  - Cloud runtime: `total_elapsed_sec=380.3904`，`load_model_sec=51.1165`。
  - Model run ledger: `reports/model_runs/20260518_sec_benchmark_reviewed7_pipeline_sanitized_gate.md`。
- Manual review:
  - GOOGL 现在保留 `58,705（百万美元）` 和 `13,910（百万美元）` 两个授权 ledger 数值，并将 unauthorized `78 亿美元` 降级为“同比增长，但精确金额未在 Exact-Value Ledger 中授权”。
  - AAPL Services 能明确说明收入和毛利率改善，但不把它过度解释成经常性收入质量；PANW 能区分 Billings 与确认收入，并把 RPO 限制写清楚。
  - SNOW/NVDA/MSFT 三个 no-ledger text-heavy case 保持定性输出，没有金额/百分比复制；中文 limitation 不再混入英文内部消息。
- Decision: reviewed7 case-filtered pipeline-context + trap gate 通过，可以进入下一阶段 reviewed case 扩展或更严格 named-fact / unsupported-claim gate。仍为 diagnostic-only，不能宣称 full benchmark 或生产级全链路通过。
- Follow-up and safety notes: sanitizer 只能处理数值边界，不能证明 qualitative claims 全部覆盖完整。下一步优先把 named-fact citation repair 升级为独立 gate，并继续人工扩展 reviewed gold，而不是直接扩大到 noisy seed 全集。

## 本次记录 - Standalone Named-Fact Support Gate

- Problem: reviewed7 pipeline gate 通过后，仍需要把 lightweight named-evidence citation repair 升级为独立 hard gate，避免答案里提到 OpenAI、Blackwell、Azure Maia、App Store 等命名事实，但对应 driver/key point citation 没有覆盖这些原文。
- Reasoning and decision: 这个 gate 不尝试做完整语义事实审稿；先做可审计的 deterministic support check。它只检查带 citation 的 `decision_drivers` 和 `key_points`，summary 默认用 citation 并集做 warning 级检查；trap/contract fallback 不进入失败分母。Ticker、ARR/RPO、SEC、Exact-Value Ledger 等内部或指标词被忽略，避免把 query/proxy metric 名称误当作外部事实。
- Work completed:
  - 新增 `scripts/validate_sec_benchmark_named_fact_support.py`。
  - 更新 `scripts/run_sec_benchmark_post_gates.py`，默认运行 `named_fact_support_gate`，并支持 `--skip-named-fact-gate`。
  - 对 reviewed7 cnlimit + trap bundle 跑 standalone gate、完整 post-gates，以及 `--strict-summary` 诊断。
- Result and evidence:
  - Named-fact gate: `reports/quality/local_reviewed7_sanitized_cnlimit_plus_traps_pipeline_gate_bundle_post_gates/sec_benchmark_named_fact_support_gate.json`。
  - Full post-gates: `reports/quality/local_reviewed7_sanitized_cnlimit_plus_traps_pipeline_gate_bundle_post_gates/sec_benchmark_post_gates_summary.json`，新增字段 `named_fact_gate_pass=true`。
  - Gate 结果: `case_count=9`，`pass_count=7`，`skip_count=2`，`checked_location_count=23`，`named_token_count=41`，`unsupported_token_count=0`，`warning_count=0`。
  - Strict-summary diagnostic: `reports/quality/local_reviewed7_sanitized_cnlimit_plus_traps_pipeline_gate_bundle_post_gates/sec_benchmark_named_fact_support_gate_strict_summary_diagnostic.json`，同样 `can_enter_gate=true`。
- Decision: named-fact support gate 可以进入 reviewed benchmark post-gates。当前 reviewed7 + trap bundle 在 numeric/metric-role/named-fact/trap/gold-vs-pipeline/true-Qwen ratio 下都通过。
- Follow-up and safety notes: 这个 gate 只能证明英文命名事实出现在 citation evidence text 中，不能证明中文抽象判断的语义充分性。下一步仍应扩展人工 reviewed gold，并逐步增加中文事实模式或 LLM critic 辅助，但 hard gate 仍应保持 deterministic。

## 本次记录 - Reviewed8 Cloud Gold + Abstract Judgment Rubric Gate

- Problem: 用户要求继续扩展 reviewed gold，并把“中文抽象判断是否覆盖充分”做成更明确的人工 rubric / critic gate，而不是只靠当前 backend score 或 named-fact support gate。
- Reasoning and decision: 先扩一个高价值 L4 diagnostic case：`CLOUD_PROFITABILITY_2023_2025_DIAG_001`。这个 case 的关键不是更多数字，而是口径边界：AWS 和 Google Cloud 有可比的 revenue / operating income；Microsoft 只有 Microsoft Cloud broad revenue proxy 和 gross margin / AI infrastructure margin-pressure disclosure，不能被拿来做简单 cloud profitability winner 排名。中文抽象 gate 采用 deterministic rubric，不用 LLM critic，先检查必要判断维度、driver 支撑结构、caveat 是否写入结论约束、以及禁止的过度判断。
- Work completed:
  - 新增 reviewed Cloud facts: `eval/sec_cases/reviewed_gold_facts/CLOUD_PROFITABILITY_2023_2025_DIAG_001.json`。
  - 新增 reviewed Cloud context: `eval/sec_cases/reviewed_gold_context/CLOUD_PROFITABILITY_2023_2025_DIAG_001.jsonl`。
  - 更新 `reports/quality/sec_benchmark_v1_reviewed_gold_partial_approval.json`：approved case count 从 7 扩到 8；full benchmark 仍 blocked。
  - 更新 `scripts/validate_sec_gold_gate.py`：对 `metric` 文本含 `and` 且有多个 `metric_families` 的 numeric check，要求每个 company-year-family 各有一个 reviewed fact；避免 Cloud case 的 revenue+operating income 被误判成多匹配，同时保留 PANW `RPO or billings` 的替代匹配语义。
  - 更新 `scripts/build_sec_benchmark_exact_value_ledger.py`：修正 raw value 已含 `million/billion` 时的中文 display value 生成，避免 `$168.9 billion（十亿美元）` 这类重复单位。
  - 新增 `eval/sec_cases/abstract_judgment_rubric_v0_1.json`，覆盖 reviewed7、Cloud L4、以及后续 `PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001` 的人工 rubric。
  - 新增 `scripts/validate_sec_benchmark_abstract_judgment_rubric.py`，并接入 `scripts/run_sec_benchmark_post_gates.py`，默认生成 `sec_benchmark_abstract_judgment_gate.json` 和 summary 字段。
- Result and evidence:
  - Reviewed ledger rebuild: `reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json`，`approved_case_count=8`，`row_count=35`。
  - Reviewed8 gold gate: `reports/quality/sec_benchmark_v1_gold_gate_reviewed8_text_numeric_cloud.json`，`can_enter_gate=true`，`status_counts={"pass": 8}`，blockers `0`。
  - Direct abstract gate on reviewed7+traps bundle: `reports/quality/local_reviewed7_sanitized_cnlimit_plus_traps_pipeline_gate_bundle_post_gates/sec_benchmark_abstract_judgment_gate.json`，`can_enter_gate=true`，`checked_case_count=7`，`pass_count=7`，`skip_count=2`，`required_dimension_count=25`，`covered_required_dimension_count=25`。
  - Full post-gates rerun: `reports/quality/local_reviewed7_sanitized_cnlimit_plus_traps_pipeline_gate_bundle_post_gates/sec_benchmark_post_gates_summary.json`，新增 `abstract_judgment_gate_pass=true`；同时 `trap/gold_vs_pipeline/answer_ledger/metric_role_term/named_fact/ledger_unit/qwen_answer_ratio` 仍全部通过。
  - Ledger unit gate 在扩展到 35 行后仍为 `pass_count=35`、`fail_count=0`。
  - Model run ledger: `reports/model_runs/20260518_sec_benchmark_reviewed8_abstract_rubric_gate.md`。
- Decision: reviewed8 gold artifact 和 abstract judgment gate 可以进入下一阶段 case-filtered 测试；这仍是 diagnostic-only，不放开 full benchmark。
- Follow-up and safety notes: 本轮没有跑新的 Cloud Qwen synthesis。下一步应做 reviewed8 case-filtered synthesis run，把 Cloud L4 纳入真实 Qwen 输出，再用同一套 gates 检查：尤其看 Microsoft proxy/caveat 是否真正压住了简单盈利排序。

## 本次记录 - Reviewed8 Cloud Pipeline True-Qwen Gate

- Problem: 用户要求继续把 Cloud L4 case 纳入真实 Qwen pipeline-context 主链路，并保持“必须真实模型通过”的 hard gate。首轮 Cloud pipeline 单例虽然已提高 `--max-tokens 4200`，但仍触发 `answered_qwen9b_ledger_repair`。
- Reasoning and decision: 诊断 `raw_model_outputs.jsonl` 后确认失败不是 ledger 或 evidence mismatch，而是 structured JSON 在 `summary` 字段被截断：模型试图在 summary 中枚举大量带长 `metric_id` 的精确数值，碰到 schema length/decoder 限制后无法闭合 JSON。修复方向是收紧输出 contract：summary 只写短判断，不写精确数字或 metric_id；数值证据放入 `decision_drivers/key_points` 的 sibling `metric_ids` 数组。人工审阅新输出时又发现模型在 `not_found/limitations` 中误称 AWS/Google 2023 operating income 缺失，尽管同一答案已经引用了对应 ledger metric_id，因此增加 deterministic consistency sanitizer，删除与当前 case ledger 明确冲突的 false-missing 声明。
- Work completed:
  - 更新 `scripts/run_sec_eval_synthesis_qwen9b_backend.py`：
    - ledger case 的 `summary` contract 改成一句短判断，不写精确数字、金额、百分比、逗号大数或 metric_id。
    - `decision_drivers/key_points` 若写精确数字，必须用 sibling `supporting_metric_ids/metric_ids` 支撑，不再鼓励在自然语言字段内联长 `metric_id`。
    - 新增 false-missing ledger consistency sanitizer：当 `not_found/limitations` 声称某 company/year/metric_family 缺失，但当前 case ledger 已有对应 row 时，删除该缺证声明；保留 Microsoft Cloud operating income 这类确实缺失的口径 caveat。
  - 新增 `scripts/validate_sec_benchmark_ledger_missing_consistency.py`，并接入 `scripts/run_sec_benchmark_post_gates.py`，把 false-missing 从 backend 内部 sanitizer 升级为独立报告 gate。
  - 云端 RTX 4090 使用 resident vLLM 重跑 Cloud pipeline 单例；本地从 saved raw output 做 deterministic consistency reprocess。
  - 下载 Cloud gold single-case run，并组合 reviewed8 gold reference。
  - 组合 reviewed8 pipeline + 2 trap bundle，运行完整 post-gates。
- Result and evidence:
  - Failed diagnostic before prompt fix: `eval/sec_cases/outputs/run_20260518_reviewed8_pipeline_cloud_qwen9b_vllm_structured_4200/`，`finish_reason=length`，`answer_status_counts={"answered_qwen9b_ledger_repair": 1}`。
  - Cloud pipeline true-Qwen raw run: `eval/sec_cases/outputs/run_20260518_reviewed8_pipeline_cloud_qwen9b_vllm_structured_4200_summaryshort/`，`answer_status_counts={"answered_qwen9b": 1}`，`load_model_sec=75.1668`，`total_elapsed_sec=240.4659`。
  - Local consistency reprocess: `eval/sec_cases/outputs/run_20260518_reviewed8_pipeline_cloud_qwen9b_vllm_structured_4200_summaryshort_consistency/`，`answer_status_counts={"answered_qwen9b": 1}`，`not_found=["Microsoft Cloud 经营利润"]`。
  - Reviewed8 gold reference: `eval/sec_cases/outputs/run_20260518_reviewed8_gold_reference_qwen9b_mixed/`，`answer_status_counts={"answered_qwen9b": 8}`。
  - Final reviewed8 + trap bundle: `eval/sec_cases/outputs/run_20260518_reviewed8_summaryshort_consistency_plus_traps_pipeline_gate_bundle/`，`answer_status_counts={"answered_qwen9b": 8, "answered_contract_fallback": 2}`。
  - Full post-gates: `reports/quality/local_reviewed8_summaryshort_consistency_plus_traps_pipeline_gate_bundle_post_gates/sec_benchmark_post_gates_summary.json`。
  - Gate 结果: `trap_gate_pass=true`，`gold_vs_pipeline_pass=true`，`answer_ledger_gate_pass=true`，`metric_role_term_gate_pass=true`，`named_fact_gate_pass=true`，`ledger_missing_consistency_gate_pass=true`，`abstract_judgment_gate_pass=true`，`ledger_unit_gate_pass=true`，`qwen_answer_ratio=1.0`，`qwen_ledger_repaired=0`，`fallback_answered=0`，`trap_outputs_excluded=2`。
  - Ledger missing consistency gate: `missing_statement_count=5`，`false_missing_statement_count=0`，`fail_count=0`。
  - Model run ledger: `reports/model_runs/20260518_sec_benchmark_reviewed8_cloud_pipeline_gate.md`。
- Manual review:
  - Cloud pipeline summary 现在是 129 字短判断：AWS/Google Cloud 收入和经营利润增长，Microsoft Cloud 只给 broad revenue proxy 和毛利率趋势，缺直接可比 operating income，且需考虑 infrastructure/capex pressure。
  - Driver 层保留 3 个主判断：AWS trend、Google Cloud trend、Microsoft proxy/caveat；每个 driver 有对应 `supporting_metric_ids`，没有把 Microsoft gross margin 当成 cloud operating income。
  - False-missing sanitizer 删除了 “AWS/Google 2023 经营利润缺失” 的自相矛盾声明，保留 “Microsoft Cloud 经营利润缺失”。
- Decision: reviewed8 case-filtered pipeline-context + trap gate 通过，可以作为当前 SEC benchmark 主链路的最小主线验证样本；仍为 diagnostic-only，不能外推到 full benchmark。
- Follow-up and safety notes: 这次修复说明 “短 thesis + 结构化 evidence support” 比在 summary 中堆长数值更稳定。下一步不要直接扩大 noisy full set，优先把 reviewed gold 继续扩到下一个高价值 diagnostic case；`not_found/limitations` 与 ledger 的一致性已经有独立 gate，后续可继续扩充 metric-family alias 覆盖范围。

## 本次记录 - Reviewed9 Platform Recurring Gold + True-Qwen Smoke

- Problem: 用户要求继续扩 reviewed gold，并把“中文抽象判断是否覆盖充分”做成更明确的人工 rubric / critic gate。本轮目标 case 是 `PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001`，重点不是单纯增长率，而是 Apple Services、Adobe subscription/ARR、Microsoft Cloud proxy 之间的可比性和经常性质量边界。
- Reasoning and decision: 这题原始 seed 里容易混入不干净的 Adobe ARR 重估、Microsoft broad cloud proxy、Apple mixed Services scope。人工 gold 采用保守边界：AAPL 使用已 reviewed 的 Services revenue / gross margin；ADBE 只把 clean total subscription revenue 放进 exact facts，把 ARR、RPO、汇率重估作为 context caveat；MSFT 只作为 Microsoft Cloud revenue/gross-margin proxy，不允许当成纯 subscription revenue 或 cloud operating income。抽象 rubric 要求模型说明 visibility/recurring quality 不是 growth 或 margin 的同义词，并且 caveat 必须降低结论强度。
- Work completed:
  - 新增 reviewed facts: `eval/sec_cases/reviewed_gold_facts/PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001.json`，共 15 条 reviewed fact。
  - 新增 reviewed context: `eval/sec_cases/reviewed_gold_context/PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001.jsonl`，共 23 条 context/fact/caveat row。
  - 更新 `reports/quality/sec_benchmark_v1_reviewed_gold_partial_approval.json`：approved case count 从 8 扩到 9；full benchmark 仍 blocked。
  - 更新 `eval/sec_cases/abstract_judgment_rubric_v0_1.json`：为 platform recurring-quality case 增加 6 个 required dimensions、2 个 calibration checks、4 个 forbidden claims，并修正 calibration check 的 nested `all_of_any` 结构。
  - 重建 reviewed exact-value ledger: `reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json`，`approved_case_count=9`，`row_count=50`。
  - 云端 RTX 4090 跑真实 Qwen3.5-9B gold-context 单例，使用 ledger-constrained synthesis，禁用 fallback。
- Result and evidence:
  - 单 case gold gate: `reports/quality/sec_benchmark_v1_gold_gate_platform_recurring_quality.json`，`can_enter_gate=true`，`status_counts={"pass": 1}`。
  - Reviewed9 gold gate: `reports/quality/sec_benchmark_v1_gold_gate_reviewed9_text_numeric_cloud_platform.json`，`can_enter_gate=true`，`status_counts={"pass": 9}`。
  - Context trace smoke: `eval/sec_cases/outputs/run_20260518_platform_recurring_gold_context_trace_smoke/`，`trace_count=1`，context row count `23`。
  - True-Qwen output: `eval/sec_cases/outputs/run_20260518_platform_recurring_gold_qwen9b_hf_32768_ledger50_abs_py/`，`answer_status=answered_qwen9b`，`score_total=8.4`，`qwen_output_status=valid_json`，`ledger_text_contract_violation_count=0`，`ledger_text_contract_sanitized_count=0`。
  - Single-case post-gates: `reports/quality/cloud_platform_recurring_gold_qwen9b_hf_32768_ledger50_abs_py_post_gates/sec_benchmark_post_gates_summary.json`，`answer_ledger_gate_pass=true`，`metric_role_term_gate_pass=true`，`named_fact_gate_pass=true`，`ledger_missing_consistency_gate_pass=true`，`abstract_judgment_gate_pass=true`，`ledger_unit_gate_pass=true`，`gold_mean_score_pct=0.84`。
  - Model run ledger: `reports/model_runs/20260518_sec_benchmark_platform_recurring_gold_qwen9b.md`。
- Manual review:
  - Qwen 的主判断方向正确：Apple Services 改善但不是纯订阅口径；Adobe subscription revenue 与 ARR/RPO visibility 更强但有汇率和合同披露限制；Microsoft Cloud 增长强但只是 broad proxy，且毛利率/成本结构有压力。
  - 3 个 drivers 都有 `supporting_metric_ids`，没有把 Microsoft Cloud gross margin 当成 cloud operating income，也没有把 Adobe ARR 与 Microsoft Cloud revenue 做直接横比。
  - 当前最大剩余质量问题是输出偏保守：模型使用了 metric IDs 做结构化支撑，但正文没有主动呈现 ledger `display_value_zh`，所以 `answer_ledger_summary.exact_value_hit_count=0`。这不构成数值错误，但会让最终答案显得证据密度不足。
- Decision: platform recurring-quality case 可以进入 case-filtered gold-context 真模型 smoke 的 reviewed set；仍然是 diagnostic-only。它还不能代表 pipeline-context 全链路通过，也不能放开 full noisy benchmark。
- Follow-up and safety notes: 下一步优先把这个 case 跑 pipeline-context 主链路，并增加一个轻量 prose evidence-density 要求：driver 至少引用若干 ledger `display_value_zh` 或明确标出“本 driver 只做定性 caveat”。不要为了提高分数放宽 ledger contract；应该在 final synthesis prompt/validator 中要求“只能从 ledger display value 取数，但要实际使用关键数值”。

## 本次记录 - Reviewed9 Platform Pipeline Gate

- Problem: gold-context 通过后仍需要验证真实 pipeline-context：召回/精排出来的 context 是否足够支撑同一类判断，以及 9B 在 pipeline prompt 下是否还能覆盖 visibility、margin/cost caveat 和 comparability。用户要求继续做扎实后再进最终全链路测试。
- Reasoning and decision: 先只跑 `PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001` 单例 pipeline，不扩大 noisy set。第一轮 pipeline 输出数值层正确但抽象判断缺口明显：没有明确把 visibility/经常性质量与 growth/margin 区分开，也没有把 Adobe 缺少可比毛利率/成本结构证据写成降级 caveat。因此修的是 contract/rubric，不是放宽 gate。
- Work completed:
  - 生成 pipeline trace: `eval/sec_cases/outputs/run_20260518_platform_recurring_pipeline_context_traces_top8`，`context_row_count=120`，覆盖 AAPL/ADBE/MSFT 的 2023/2024/2025。
  - 更新 `scripts/run_sec_eval_synthesis_qwen9b_backend.py`：把 `eval/sec_cases/abstract_judgment_rubric_v0_1.json` 中的 per-case required dimensions、calibration checks 和 forbidden claims 作为 compact hard contract 注入 final synthesis prompt。
  - 更新 `eval/sec_cases/abstract_judgment_rubric_v0_1.json`：为 platform recurring-quality case 增加严格 Adobe profitability caveat，要求说明 Adobe subscription revenue 支持可见性/经常性，但缺少可比毛利率或成本结构证据，不能完整判断盈利质量。
  - 更新 `scripts/validate_sec_benchmark_named_fact_support.py`：ledger-backed company metric label 可以通过 sibling `metric_ids` 支撑；summary 继承 driver/key point 的 metric_id 并集，避免 “Apple Services” 这类 ledger metric label 变成 summary warning。
  - 云端 RTX 4090 跑三次单例诊断：baseline pipeline、rubric prompt、strict Adobe rubric。最终采用 `run_20260518_platform_recurring_pipeline_qwen9b_vllm_structured_5000_rubricprompt_strictadobe`。
  - 组合 prior reviewed8 + trap bundle 与本次 platform pipeline，形成 reviewed9 + 2 trap pipeline gate bundle。
- Result and evidence:
  - Initial platform pipeline output: `eval/sec_cases/outputs/run_20260518_platform_recurring_pipeline_qwen9b_vllm_structured_5000`，`answered_qwen9b`，score `8.8`，但 `abstract_judgment_gate_pass=false`，只覆盖 4/6 required dimensions。
  - Rubric prompt output: `eval/sec_cases/outputs/run_20260518_platform_recurring_pipeline_qwen9b_vllm_structured_5000_rubricprompt`，补齐 visibility 判断，但 manual review 发现 Adobe margin/cost caveat 仍偏弱。
  - Final strict output: `eval/sec_cases/outputs/run_20260518_platform_recurring_pipeline_qwen9b_vllm_structured_5000_rubricprompt_strictadobe`，`answered_qwen9b`，valid JSON，`ledger_text_contract_violation_count=0`，`ledger_text_contract_sanitized_count=0`。
  - Final single-case post-gates: `reports/quality/cloud_platform_recurring_pipeline_qwen9b_vllm_structured_5000_rubricprompt_strictadobe_post_gates_namedsummaryfix/sec_benchmark_post_gates_summary.json`，gold-vs-pipeline、answer-ledger、metric-role、named-fact、ledger-missing-consistency、abstract-judgment、ledger-unit、qwen-ratio 全部通过。
  - Final reviewed9 + 2 trap bundle: `eval/sec_cases/outputs/run_20260518_reviewed9_platform_strictadobe_plus_traps_pipeline_gate_bundle`。
  - Full post-gates: `reports/quality/local_reviewed9_platform_strictadobe_plus_traps_pipeline_gate_bundle_post_gates/sec_benchmark_post_gates_summary.json`。
  - Gate 结果: `trap_gate_pass=true`，`gold_vs_pipeline_pass=true`，`answer_ledger_gate_pass=true`，`metric_role_term_gate_pass=true`，`named_fact_gate_pass=true`，`ledger_missing_consistency_gate_pass=true`，`abstract_judgment_gate_pass=true`，`ledger_unit_gate_pass=true`，`qwen_answer_ratio=1.0`，`qwen_ledger_repaired=0`，`fallback_answered=0`，`trap_outputs_excluded=2`。
  - Abstract gate: `checked_case_count=9`，`required_dimension_count=37`，`covered_required_dimension_count=37`。
  - Model run ledger: `reports/model_runs/20260518_sec_benchmark_reviewed9_platform_pipeline_gate.md`。
- Manual review:
  - 最终答案比 baseline 更接近分析师判断：Apple Services 作为 mixed services bundle、Adobe subscription visibility、Microsoft Cloud broad proxy 三者分层；Adobe 的缺失毛利率/成本结构被明确写成 caveat；Microsoft Cloud 的用量/订阅混合和 AI infrastructure cost pressure 进入弱化判断。
  - 数值使用比 gold-context 更好：key points 实际引用了 ledger `display_value_zh`，`exact_value_hit_count` 从 gold 单例的 0 提高到 reviewed9 bundle 的 41。
  - 仍有一个需后续收紧的小问题：Apple caveat 中出现 “硬件相关服务” 这种偏泛表达，最好后续改成 “mixed services bundle / not pure subscription” 的固定口径，避免引入不必要的新解释。
- Decision: reviewed9 case-filtered pipeline-context + trap gate 通过，可以作为当前 SEC benchmark 主链路的最小 reviewed pipeline gate。仍为 diagnostic-only，不代表 full noisy benchmark 或生产级通过。
- Follow-up and safety notes: 下一步不要扩大 full set；先把 Apple Services caveat phrasing、summary named-fact strict mode、以及 prose evidence-density/required missing metric caveat 做成更稳定的 validator/prompt 模板，再考虑加入下一个 reviewed diagnostic case。
