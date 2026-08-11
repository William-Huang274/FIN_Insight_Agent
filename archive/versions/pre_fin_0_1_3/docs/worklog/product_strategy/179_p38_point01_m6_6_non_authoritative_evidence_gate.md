# 179 P38 Point 01 M6.6 Non-authoritative Evidence Gate

日期：2026-07-13

## 批准范围

总 reviewer 批准 `approve_m6_6_deterministic_evidence_gate_contract_only`，并明确要求 M6.6 完成后交回审计，不得自动进入 M6.7。实现只接受 fixture-only、unpromoted、exact-lineage inputs。

## 完成内容

- `EvidencePromotionDecision` schema 排除 bare `accepted`，仅有 `fixture_accepted_for_gate_simulation`、`context_only`、`rejected`、`typed_gap`、`commercial_gap`。
- 所有 decision 强制 `decision_scope=deterministic_fixture_only`，且 runtime promotion、writer citation、domain judgment、persistence 都是 false；Lead/Human 恒为 `approval_required_not_executed`。
- hard gate 覆盖 entity、period、unit、scale、source authority、request/bundle/parser/fact/trace lineage、numeric trace、forbidden relationship substitution 和 conflicting table candidates。
- semantic classification 仅是不可 override 的 suggestion；relationship 不能变成 fact，commercial gap 不能由 public proxy 满足，Writer/DomainJudgment/Context 的 consumer firewall 全部 fail-closed。

## 验证

```text
python scripts/engineering/run_point01_m6_6_evidence_gate_fixture.py
python -m pytest tests/contract/test_point01_m6_6_evidence_gate.py -q
```

fixture pass，focused suite `4 passed`。没有模型、外部工具、网络、provider、source read、formal evidence persistence、Lead/Human approval、M6.7、Writer/full-chain 或 authority mutation。

## 审计回传边界

当前是 `skeleton_and_fixture_proven / deterministic_non_authoritative_evidence_gate`，不是 Evidence runtime。下一个动作只能由审计决定：先修 M6.2-M6.5 的 live bounded execution，或另行批准 M6.7 judgment contract；本 slice 不提供任何自动前进权限。
