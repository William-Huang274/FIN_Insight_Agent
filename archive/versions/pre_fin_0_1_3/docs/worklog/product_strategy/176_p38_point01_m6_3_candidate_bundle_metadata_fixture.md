# 176 P38 Point 01 M6.3 CandidateBundle Metadata Fixture

日期：2026-07-13

## 授权与审阅

用户已授权继续完成 M6 余下任务；本 slice 仍严格受 M6.0 authority boundary 限制。M6.3 design review 用 retrieval metadata、source/evidence quality、tool security/budget、parser/numeric、replay/acceptance 五个职责视角完成，并明确该审阅只是单 Codex 的结构化职责分离，不冒充独立 human/multi-person signoff。

## 完成内容

- 新增 `CandidateMetadataSnapshot`：只容纳 immutable、digest-bound、`fixture_only=true` 的 document/version/route/source-policy/authority/entity/period/section-or-table/content ref metadata，禁止 raw document content、extracted value 或 live retrieval 结果。
- 新增 `CandidateBundleCompiler`：绑定 exact `EvidenceRequest` 与同一 request id/digest 的 M6.2 nonexecuting `ToolSelectionPlan`；仅接受 planner selected route，校验 source policy、entity/period、minimum authority，并按 authority、metadata rank、candidate id 稳定排序。
- numeric fact policy 要求 top-K seed、neighbor section 和 table context；relationship context 只需 top-K/neighbor；缺任一 required kind 或没有 metadata 产生 typed `retrieval_exhausted`，commercial typed stop 产生 `not_attempted_typed_stop`。
- 无 CandidateBundle persistence、M5.4/M5.5 admission/reservation、ToolInvocationReceipt、RAG/SQL/graph retrieval、network/provider、document-content read、parser/numeric/promotion、judgment/context/Writer/full-chain 或 Case/legacy authority mutation。

## 验证

```text
python scripts/engineering/run_point01_m6_3_candidate_bundle_fixture.py
python -m pytest tests/contract/test_point01_m6_3_candidate_bundle.py -q
python -m compileall -q src/sec_agent/canonical_runtime scripts/engineering/run_point01_m6_3_candidate_bundle_fixture.py
```

fixture `pass`，focused suite `5 passed`。正例覆盖 issuer top-K/neighbor/table 与 relationship context-only；负例覆盖 request-plan lineage mismatch、non-fixture snapshot、route bypass、missing table 和 empty metadata。所有执行计数均为 0。

## 后续与边界

当前状态是 `skeleton_and_fixture_proven / deterministic_metadata_candidate_bundle`，不是 metadata-first RAG/DB runtime，也不是 recall/rerank/slot precision-recall calibrated。M6.4 可继续实现 RepairTicket/RepairAttempt 的 deterministic contract；真实 ToolGateway execution、live retrieval、source corpus 或 document-content parsing 必须先单独申请，不能由本 fixture 或 M6.2 plan 推断授权。
