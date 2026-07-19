# 180 P38 Point 01 M6.2 Real Bounded SEC Metadata Execution Path

日期：2026-07-13

## 用户授权与严格范围

当前线程 human approver 批准 `approve_m6_2_5_real_bounded_sec_metadata_pilot_only`：只允许在隔离、临时 SQLite synthetic Case 中，对 NVDA（CIK `0001045810`）调用一次 `data.sec.gov/submissions/CIK0001045810.json`。唯一可执行工具是 `issuer_disclosure_metadata_tool`；不得 fallback 或 retry。

禁止 provider/model、其他 issuer/host、原始文件或 HTML 下载、Evidence promotion、Writer/Domain Judgment/full-chain、业务 Case mutation 与 legacy authority change。

## 已实现的控制路径

- `BoundedSecMetadataExecutor` 只接受 exact `EvidenceRequest` 与 M6.2 selected primary plan step；route/tool/capability/CIK/host/path 均固定。
- 调用前完成 M5.4 persisted capability admission、M5.5 exact one-call reservation 和 receipt `prepared` v1。
- 因 HTTP 无法与 SQLite 处于同一 ACID transaction，真正发送前会以当前时间重新读取 grant 并 admission。此时拒绝会写 `blocked_before_send` v2 并全额 refund；不会发网。
- 发送后成功写 `succeeded` v2；任何 transport/HTTP/JSON 不确定状态写 `outcome_unknown` v2，保守 consume 唯一预算，永不重试。
- receipt 只持久化 issuer 与 recent filing headers、response metadata digest 和控制面 refs，不持久化 raw SEC body，也不是 CandidateBundle/NumericFact/正式 Evidence。

## 已验证

```text
python -m pytest tests/contract/test_point01_m6_2_real_bounded_sec_metadata_execution.py -q
# 4 passed

python -m pytest tests/contract/test_point01_m6_1_evidence_request.py tests/contract/test_point01_m6_2_tool_planner.py tests/contract/test_point01_m6_3_candidate_bundle.py tests/contract/test_point01_m6_4_repair_ticket.py tests/contract/test_point01_m6_5_parser_numeric.py tests/contract/test_point01_m6_6_evidence_gate.py -q
# 30 passed
```

覆盖单次 mocked success、post-send transport uncertainty 的 no-retry、未批准 CIK 的发送前拒绝，以及 prepare 后 grant 被撤销时的 execute-time recheck/refund。

M6.0 design lint 为 pass；共享 SQLite schema 增加 append-only receipt table 后，M1 closeout 以临时输出复跑仍为 `pass / M1_complete`，未改写既有 M1 receipt。

## 当前阻断与后续

执行环境没有 `SEC_USER_AGENT`。live runner 在 `--execute-live` 下因此 `fail_closed`，`external_call_count=0`、`store_write_count=0`，没有使用伪造 contact identity，也没有发出 SEC 请求。

因此当前状态是 `implementation_verified_live_execution_blocked_missing_sec_user_agent`，不是 route-success calibration。待用户在执行环境设置合规的 `SEC_USER_AGENT` 后，只运行一次 live pilot；只有得到 exact successful receipt，才可把该 receipt 转入 M6.3 的 real metadata CandidateBundle 路径。M6.4-M6.5 的 real bounded execution 仍未开始。
