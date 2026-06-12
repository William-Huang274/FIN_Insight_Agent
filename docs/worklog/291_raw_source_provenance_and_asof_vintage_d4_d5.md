# D4/D5 Raw Source Provenance 与 As-of Vintage Runtime Projection

## Prompt

用户要求先整理工作树并提交 G1-G11 及上一轮改动，然后继续按 `07`、`08` 文档规划推进 D4、D5。

## Decision

本轮继续采用 per-run runtime/artifact-backed v0.1，而不是直接上完整数据库治理层：

- D4 先解决“本次 run 的 evidence / artifact 能反查来源、路径、document id、parser version、citation span”的问题。
- D5 先解决“本次 run 的 SEC period、filing date、market as-of、macro vintage、retrieved / parser time 不混用”的问题。
- 这两层不做事实提权，不替代 D6 Reconciliation Ledger，也不把 public proxy 或 run artifact 当成 company claim authority。
- SQL / object store backed provenance、materialized checksum、license/robots registry、macro vintage store、market as-of table、filing amendment lineage 和 staleness/time-mismatch gate 留给 D4.1/D5.1/D9。

## Work Completed

- 新增 `src/sec_agent/provenance_vintage.py`：
  - `sec_agent_raw_source_provenance_store_v0.1`
  - `sec_agent_asof_vintage_layer_v0.1`
  - 从 runtime ledger rows、context rows、market / industry / product / public rows、tool observations、artifact refs 和 project inventory filings 投影 provenance / vintage records。
  - validation fail-closed 于必填 id；duplicate、raw locator missing、SEC document id missing、URL access method missing、time anchor missing 等作为 warning 暴露。
- 更新 `src/sec_agent/langgraph_orchestrator.py`：
  - `persist_session_state` 先声明 artifact refs，再生成 D4/D5，确保 run artifact 也进入 provenance。
  - 写出 `raw_source_provenance_store.json` 和 `asof_vintage_layer.json`。
  - multi-agent summary 暴露 D4/D5 schema、record count、source family、record type、time basis 和 validation status。
  - checkpoint summary 暴露 D4/D5 record count 和 validation status。
- 新增 `tests/test_provenance_vintage_layers.py`：
  - 测 D4 source locator、document id、file type、citation span 和 artifact refs。
  - 测 D5 fiscal / market / macro time basis。
  - 测 graph persist 写出 D4/D5 artifacts、summary、artifact_refs 和 checkpoint summary。
- 更新 `08_legacy_planning_docs_absorption_and_data_governance_plan.zh-CN.md` 与 `00_internal_master_checklist.md`，标记 D4/D5 v0.1 已落地，并新增 D4.1/D5.1 后续项。

## Result And Evidence

本轮通过：

```text
python -m py_compile src\sec_agent\provenance_vintage.py src\sec_agent\langgraph_orchestrator.py
python -m pytest tests\test_provenance_vintage_layers.py -q
python -m pytest tests\test_claim_evidence_gap_ledgers.py tests\test_entity_master_source_capability_router.py tests\test_provenance_vintage_layers.py -q
python -m pytest tests\test_multi_agent_langgraph_routing.py tests\test_multi_agent_contracts.py tests\test_multi_agent_activation_plan.py tests\test_multi_agent_evidence_requirements.py -q
python -m pytest -q
git diff --check
```

当前结果：

- D4/D5 targeted tests：`3 passed`
- D1-D5/D8 artifact regression：`10 passed`
- graph routing / contract / activation / evidence requirement regression：`79 passed`
- full pytest：`835 passed`
- diff check：pass

## Boundary And Follow-up

- D4 当前是 per-run JSON projection，不是跨 run provenance warehouse。
- D5 当前是 per-run vintage projection，不是完整 macro / market / amendment vintage database。
- 下一步按 `08` 的顺序应推进 D6 Reconciliation Ledger 与 D7 Metric / Product Ontology；D6/D7 需要消费 D4/D5 的 source_id / time basis，但不能把 D4/D5 当事实冲突解决器。
