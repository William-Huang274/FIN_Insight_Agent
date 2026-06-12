# D3/D8 Entity Master 与 Source Capability Router Runtime Projection

## Prompt

用户要求继续按 `07`、`08` 文档执行顺序推进。D1/D2 后的下一组是 D3 Entity / Security Master 与 D8 Source Capability Router。

## Decision

本轮继续采用 runtime/artifact-backed v0.1，而不是直接上完整数据库治理层：

- D3 先解决“本次 run 内 ticker / CIK / external id / alias / query scope 的统一引用”，让后续 claim、source、gap 可以接同一 entity id。
- D8 先解决“每条 physical retrieval route 是否允许、是否 context-only、是否 unavailable gap”的显式决策，避免 source boundary 只散落在 prompt 和 playbook 里。
- 品牌、子公司、product owner、ADR/share class、ticker change、跨 run entity warehouse 仍留给 D3.1。
- 按 query_intent / industry / metric_type / claim_type 的完整 policy table 仍留给 D8.1，并应与 D7 Metric / Product Ontology 联动。

## Work Completed

- 更新 `src/sec_agent/project_inventory.py`：
  - `companies` 保留 `cik`、`issuer_id`、`lei`、`figi`、`isin`、`cusip`、`sedol`、`legal_name`、`aliases`。
- 新增 `src/sec_agent/entity_master.py`：
  - `sec_agent_entity_security_master_v0.1`
  - 从 `project_inventory.companies` 与 query scope 构建 per-run entity master。
  - 输出 `entities`、`alias_registry`、`unresolved_references`、summary 和 validation。
  - query `companies` 中的自然语言公司名只进 alias resolver，不被误当 ticker。
- 新增 `src/sec_agent/source_capability_router.py`：
  - `sec_agent_source_capability_router_v0.1`
  - 从 activation allowed sources、inventory availability / authority、retrieval routes 生成 route decisions。
  - decision status：`allowed`、`blocked`、`gap`。
  - claim authority：`exact_authority`、`limited_exact_authority`、`context_only`、`no_claim_authority`。
  - validator 阻断 context-only exact authority 和 unavailable allowed route。
- 更新 `src/sec_agent/langgraph_orchestrator.py`：
  - `compile_retrieval_plan` / `compile_evidence_requirements` 后生成 D3/D8 state。
  - persist 写出 `entity_security_master.json` 和 `source_capability_router.json`。
  - `artifact_refs`、multi-agent summary 和 checkpoint summary 暴露 D3/D8。
- 新增 `tests/test_entity_master_source_capability_router.py`：
  - 测 inventory identifiers 进入 Entity Master。
  - 测 alias resolver 不把 company name 当 ticker。
  - 测 source router 的 exact/context/blocked/gap decisions。
  - 测 graph persist 写出 D3/D8 artifacts 和 summary。
- 更新 `08_legacy_planning_docs_absorption_and_data_governance_plan.zh-CN.md` 的 D3/D8 当前状态。

## Result And Evidence

本轮通过：

```text
python -m py_compile src\sec_agent\entity_master.py src\sec_agent\source_capability_router.py src\sec_agent\project_inventory.py src\sec_agent\langgraph_orchestrator.py
python -m pytest tests/test_entity_master_source_capability_router.py -q
python -m pytest tests/test_project_inventory_source_inventory.py tests/test_entity_resolution_contract.py tests/test_entity_master_source_capability_router.py tests/test_claim_evidence_gap_ledgers.py -q
python -m pytest tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_contracts.py tests/test_multi_agent_activation_plan.py tests/test_multi_agent_evidence_requirements.py -q
```

结果：

- D3/D8 targeted unit tests：`3 passed`
- D1-D3/D8 + inventory/entity regression：`14 passed`
- graph routing / contract / activation / evidence requirement regression：`79 passed`

## Boundary And Follow-up

- D3 当前是 per-run projection，不是完整 Entity Warehouse。
- D8 当前是 route/source-family capability layer，不是完整行业/metric/claim policy table。
- 下一步按 `08` 的顺序应推进 D4 + D5：Raw Source / Provenance Store 与 As-of / Vintage Layer。
- D4/D5 前应避免继续扩大数据源，否则 fact provenance 和时间语义会继续散落在各类 artifact 里。

