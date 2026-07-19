# 181 P38 Point 01 M6.3-M6.5 Receipt-Bound Terminal Chain

日期：2026-07-13

## 决策与范围

在既有 `approve_m6_2_5_real_bounded_sec_metadata_pilot_only` 范围内实现 M6.3-M6.5 的后续控制路径。该范围没有新增数据源、工具、host、调用次数或 runtime authority：唯一可能的上游输入仍是 isolation SQLite synthetic NVDA Case 中的 exact M6.2 single-call SEC metadata terminal receipt。

当前环境没有合规 `SEC_USER_AGENT`，因此没有 live receipt，也没有实际发出网络请求。本轮只通过 mocked、真实形状的 append-only receipt 链验证 downstream persistence；不能称为 real retrieval、SourceHunter、parser、numeric extraction 或 Evidence promotion。

## 交付

- M6.3 `ReceiptBoundCandidateBundleService`：核验 exact receipt 的 request/plan/tool/route/host/CIK/approval/digest，只写入 `retrieval_exhausted` CandidateBundle。它固定记录 period、neighbor section 和 table context 缺失；不产生 candidate、table、period 或 NumericFact。
- M6.4 `ReceiptBoundRepairTicketService`：消费 exact M6.3 bundle，并写入 `attempt_budget=0`、`terminal=true` RepairTicket。没有 RepairAttempt、fallback、retry 或第二次工具调用。
- M6.5 `ReceiptBoundParserNumericStopService`：消费 exact M6.3/M6.4/M6.2 lineage，写入 `not_attempted_typed_gap` stop。ParserCandidate、NormalizedNumericFact 和 NumericProgramTrace 的创建计数均为零。
- 三个 service 都在 mutation transaction 内重读 pinned version/digest，写 append-only canonical version + event，支持 idempotent replay，错误、缺失或非 exact version ref 均 fail-closed。

## 主要文件

- `src/sec_agent/canonical_runtime/receipt_bound_candidate_bundle.py`
- `src/sec_agent/canonical_runtime/receipt_bound_repair_ticket.py`
- `src/sec_agent/canonical_runtime/receipt_bound_parser_numeric_stop.py`
- `scripts/engineering/run_point01_m6_3_receipt_bound_candidate_bundle.py`
- `scripts/engineering/run_point01_m6_4_receipt_bound_terminal_repair.py`
- `scripts/engineering/run_point01_m6_5_receipt_bound_parser_numeric_stop.py`
- `configs/engineering_handoff/point01_m6_{3,4,5}_receipt_bound_*_policy_v1_0.json`
- `tests/contract/test_point01_m6_{3,4,5}_receipt_bound_*.py`

## 验证

```text
python -m pytest -q tests/contract/test_point01_m6_4_receipt_bound_terminal_repair.py
# 5 passed

python -m pytest -q tests/contract/test_point01_m6_5_receipt_bound_parser_numeric_stop.py
# 5 passed

$files = Get-ChildItem tests/contract -Filter test_point01_m6_*.py | ForEach-Object { $_.FullName }
python -m pytest -q $files
# 50 passed
```

未运行 provider、模型、real SEC request、Evidence/Writer、Domain Judgment、full-chain、业务 Case mutation 或 legacy authority change。

## 当前阻断与下一步

配置合规的 `SEC_USER_AGENT` 前，live M6.2 runner 必须继续 fail-closed，不能构造 placeholder identity。若以后执行该 single-call pilot 且得到 successful exact receipt，M6.3-M6.5 的三个 runner 才可依次读取该 receipt chain；但其唯一正向结果仍是 typed exhaustion/terminal stop，不能进入 M6.6 formal evidence 或 M6.7。任何扩大到 document/table download、live parser、repair route 或 evidence promotion 的提议都需要独立设计与人工审批。
