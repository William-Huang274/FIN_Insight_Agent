# D1/D2 Claim Evidence 与 Typed Gap Runtime Ledger

## Prompt

用户要求按 `07`、`08` 文档规划顺序继续做。当前顺序的第一步是 D1 Claim Evidence Ledger 和 D2 Typed Gap Ledger。

## Decision

先做 runtime/artifact-backed v0.1，而不是直接引入新的数据库迁移：

- D1/D2 的关键价值是让 Memo Writer、Verifier、审计脚本和后续 sub-agent 能读到同一份 claim/gap governance contract。
- 当前 graph 已经有 ClaimCard、Judgment Plan、bounded gap register 和 second-pass hard gate；最小正确改动是把这些运行时结构投影为稳定 ledger schema。
- SQL-backed append-only store、跨 run 去重和 research memory 仍留给 D11 / store 层，不在本轮混入。

## Work Completed

- 新增 `src/sec_agent/claim_evidence_ledger.py`：
  - `sec_agent_claim_evidence_ledger_v0.1`
  - `sec_agent_typed_gap_ledger_v0.1`
  - claim status：`supported`、`weakly_supported`、`contradicted`、`gap_exposed`
  - gap type：`not_disclosed`、`not_found`、`parser_failed`、`source_boundary_blocked`、`period_gap`、`unit_gap`、`alias_gap`、`commercial_gap`、`conflict_gap`、`staleness_gap`、`coverage_gap`
  - validator fail-closed：supported claim 必须有 supporting evidence；unknown gap type 不通过；commercial gap 必须暴露为缺口，不能走弱 proxy。
- 更新 `src/sec_agent/langgraph_orchestrator.py`：
  - `judgment_plan` 节点生成 governance ledgers，并把 Claim Evidence Ledger summary 接入 Claim Card Store Barrier。
  - multi-agent summary artifact 增加 D1/D2 摘要。
  - persist 节点写出 `claim_evidence_ledger.json` 和 `typed_gap_ledger.json`。
  - `artifact_refs` 新增 `claim_evidence_ledger` 和 `typed_gap_ledger`。
- 新增 `tests/test_claim_evidence_gap_ledgers.py`：
  - 测 commercial/parser gap normalization。
  - 测 supported/conflict/unsupported claim projection。
  - 测 validator fail-closed。
  - 测 graph run 写出 ledger state、summary 和 artifact files。
- 更新 `docs/architecture/agent_graph_vnext/08_legacy_planning_docs_absorption_and_data_governance_plan.zh-CN.md` 的 D1/D2 当前状态。

## Result And Evidence

本轮通过：

```text
python -m py_compile src\sec_agent\claim_evidence_ledger.py src\sec_agent\langgraph_orchestrator.py
python -m pytest tests/test_claim_evidence_gap_ledgers.py -q
python -m pytest tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_contracts.py -q
python -m pytest tests/test_multi_agent_activation_plan.py tests/test_multi_agent_evidence_requirements.py -q
```

结果：

- D1/D2 targeted unit tests：`4 passed`
- graph routing / contract regression：`39 passed`
- activation / evidence requirement regression：`40 passed`

## Boundary And Follow-up

- 当前是 artifact-backed v0.1，不是数据库最终态。
- Memo Writer 仍主要受原有 judgment/memo contract 控制；D1 ledger 已进入 barrier 和 summary，但后续还应让 Memo Writer 显式只消费 ledger-eligible claims。
- D3/D8 应作为下一步优先级：Entity / Security Master 与 Source Capability Router。没有统一 entity 和 source capability，D4/D5/D6 会变成多源数据堆积。
- 后续 D9 应把 claim support、source boundary、commercial gap、unit/period/numeric gate 写进 Gate Registry / Gate History，而不是只保存在每次 graph state 里。

