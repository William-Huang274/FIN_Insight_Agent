# D7/D6 Metric Product Ontology 与 Reconciliation Ledger Runtime Projection

## Prompt

用户要求继续按 D 系列往下做。上一轮已完成 D4/D5，并补充要求 D 系列收口前记得补 SQL / DB-backed stores。

## Decision

本轮按 D7 -> D6 的顺序落地：

- D7 先固定 metric / product KPI canonical ontology，否则 D6 只能做字符串级冲突检测。
- D6 基于 D7 ontology、D4 source provenance、D5 as-of / vintage layer 做 per-run reconciliation。
- 本轮仍采用 artifact-backed v0.1，不直接做 SQL / DB store；数据库化回补由 D12 closeout gate 承接。
- D6 当前接在 persist 阶段，不改变 Memo Writer 的事实输入路径；把 reconciliation 前移到 pre-Memo fact selection 留给 D6.1。

## Work Completed

- 新增 `src/sec_agent/metric_product_ontology.py`：
  - `sec_agent_metric_product_ontology_v0.1`
  - 内置 Financial Metric Ontology：revenue、gross_profit、operating_income、net_income、FCF、capex、debt、cash、shares、EPS。
  - Product KPI Ontology 吸收 `configs/data_sources/company_product_operating_metric_ontology_v0_1.yaml` 的边界，但不把 grouped positive examples 直接提升为 canonical alias，避免 bookings/backlog、MAU/DAU/ARPU 互相抢 alias。
  - 输出 canonical id、metric type、accepted/rejected aliases、unit family、period rule、allowed/exact source families、cannot_infer_from、required gates、observed mappings、summary 和 validation。
- 新增 `src/sec_agent/reconciliation_ledger.py`：
  - `sec_agent_reconciliation_ledger_v0.1`
  - 从 runtime ledger rows、product evidence rows、context/public rows 中筛出带 value 且具备 exact-value authority 的候选。
  - context-only / public proxy value rows 会进入 excluded candidates，不参与 preferred value。
  - 支持 `unit_conflict`、`period_conflict`、`taxonomy_conflict`、`segment_conflict`、`amendment_conflict`、`source_priority_conflict`、`rounding_conflict`。
  - `source_priority_conflict`、`amendment_conflict`、`rounding_conflict` 可在规则唯一时生成 `preferred_value`；unit / period / taxonomy / segment conflict fail closed，生成 `conflict_gaps`。
- 更新 `src/sec_agent/langgraph_orchestrator.py`：
  - persist 阶段顺序为 artifact refs -> D4/D5 -> D7/D6 -> record/write。
  - 写出 `metric_product_ontology_snapshot.json` 和 `reconciliation_ledger.json`。
  - `artifact_refs`、multi-agent summary 和 checkpoint summary 暴露 D6/D7。
- 新增 `tests/test_metric_product_ontology_reconciliation.py`：
  - 测 financial/product metric mapping、rejected alias、public proxy cannot-infer boundary。
  - 测 source-priority resolution、unit conflict fail-closed、taxonomy conflict gap 和 context-only candidate exclusion。
  - 测 graph persist 写出 D6/D7 artifacts、summary、artifact_refs 和 checkpoint summary。
- 更新 `08_legacy_planning_docs_absorption_and_data_governance_plan.zh-CN.md` 和 `00_internal_master_checklist.md`，标记 D6/D7 v0.1 已落地，并新增 D6.1/D7.1 后续项。

## Result And Evidence

本轮已通过：

```text
python -m py_compile src\sec_agent\metric_product_ontology.py src\sec_agent\reconciliation_ledger.py src\sec_agent\langgraph_orchestrator.py
python -m pytest tests\test_metric_product_ontology_reconciliation.py -q
python -m pytest tests\test_claim_evidence_gap_ledgers.py tests\test_entity_master_source_capability_router.py tests\test_provenance_vintage_layers.py tests\test_metric_product_ontology_reconciliation.py -q
python -m pytest tests\test_multi_agent_langgraph_routing.py tests\test_multi_agent_contracts.py tests\test_multi_agent_activation_plan.py tests\test_multi_agent_evidence_requirements.py -q
python -m pytest -q
git diff --check
```

当前结果：

- D6/D7 targeted tests：`3 passed`
- D1-D8 artifact regression：`13 passed`
- graph routing / contract / activation / evidence requirement regression：`79 passed`
- full pytest：`838 passed`
- diff check：pass

## Boundary And Follow-up

- D6 当前是 persist-time artifact，不是 Memo Writer 前的事实选择层。
- D7 当前是 code/config-backed ontology snapshot，不是可维护 registry / DB ontology。
- D6.1 需要把 reconciliation 前移到 pre-Memo fact selection，并把 unresolved conflict groups 接入 typed gap ledger / bounded gap register。
- D7.1 需要接行业 playbook KPI override、product spec ontology、manual alias review queue 和 D8.1 source policy table。
- D12 仍负责最终 SQL / DB-backed store、migration/backfill 和 artifact-to-database parity tests。
