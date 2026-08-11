# 174 P38 Point 01 M6.1 EvidenceRequest Compiler

日期：2026-07-13

## 授权与设计门控

M6.0 规定 M6.1 前须有 cross-owner review 和用户明确实现授权。当前线程 user 明确要求“继续做 M6.1”。`point01_m6_1_cross_owner_design_review_v1_0.json` 以 planning contract、evidence/research quality、parser/metadata、tool/security/budget、runtime/replay 五个职责视角完成结构化审阅；它清楚记录此审阅是单一 Codex agent 的 role separation，不伪称独立 human 或多人签字。用户的限定 M6.1 授权是 calibration disposition。

## 完成内容

- 新增 `EvidenceRequestCompiler`，只接收 exact `DecisionSurfaceContractVersion`、`DecisionSurfaceCellVersion`、`EvidenceSlotVersion`。它验证 Contract→Cell、Cell→Slot 的 tenant/project/case 与 parent version，拒绝任何 latest-read 或自由搜索词入口。
- `request_id`/`request_digest` 绑定 exact version refs、M6.1 policy、entity/period/metric、forbidden substitutions、metadata/numeric requirements、route/top-k/budget/stop contract。
- `issuer_metric` 只能生成 `numeric_fact` request，并声明 document/version/section-table/source-authority 和 row-label/unit/period/source-coordinate requirements；不会自行 parse、normalize 或 promote。
- `relationship_signal` 只能生成 context request；commercial tracker 只能是 gap evidence。M2 的 `acceptance_role` 与 TECH_02 `accepted_evidence_role` 被显式映射，不能混同。

## 验证

```text
python scripts/engineering/run_point01_m6_1_evidence_request_fixture.py
python -m pytest tests/contract/test_point01_m6_design_freeze.py tests/contract/test_point01_m6_1_evidence_request.py tests/contract/test_point01_decision_surface_planning.py tests/contract/test_point01_m2_evidence_policy.py -q
```

结果：M6.1 fixture `pass`；M6.1 focused suite `5 passed`；M2/M6 planning-policy extended suite `15 passed`；`compileall` 通过。四行业 issuer requests 具备 deterministic replay；relationship context-only request、parent mismatch、missing forbidden substitution、invalid source 与 wrong requester 均被 fail-closed。

## 边界与后续

本项不持久化 EvidenceRequest，`store_write_count=0`；route/top-k/budget 只是 M6.2 future planner 的 declarative contract。没有 Tool Registry lookup、capability admission、外部工具/网络/provider/模型调用、candidate retrieval、parser/numeric、Evidence Gate、judgment/context/Writer/full-chain、业务 Case mutation 或 legacy authority change。

下一项仍是 M6.2 Tool Registry + bounded planner，需另行完成其 own design/implementation gate；本 M6.1 不能替代该授权。
