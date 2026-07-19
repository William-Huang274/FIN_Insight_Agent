# 175 P38 Point 01 M6.2 Tool Registry 与 Bounded Planner

日期：2026-07-13

## 授权与审阅

M6.1 完成后 user 明确要求“继续”。M6.2 review 以 registry/source authority、M5 security/budget、research evidence quality、planner state machine、acceptance/calibration 五个职责视角审阅。记录明确说明为单 Codex role separation，不宣称独立 human/multi-person signoff；user 的继续指令仅授权 deterministic registry/selection-plan 实现。

## 完成内容

- `ToolRegistrySnapshot` 固定完整 Tool Registry entry：capability、input/output schema、source role/authority/rank、can/cannot support、cost/latency、failure/fallback、permission scope、forbidden claim、supported evidence/source-policy role 与 declared route。
- `BoundedToolPlanner` 消费 M6.1 `EvidenceRequest`，先按 evidence role 的最小 source authority 过滤，再按 cost rank 做稳定选择；issuer request 生成 primary + 至多一个 fallback plan step，relationship request 只生成 context route。
- commercial gap、tool-call budget=0、route exhaustion 和 declarative planning allowlist 不满足都返回 typed stop。每个 selected step 固定 permission snapshot、required capability 与 `required_m5_4_capability_check`，但没有进行 admission、reservation、network/provider/tool 调用或 receipt 写入。

## 验证

```text
python scripts/engineering/run_point01_m6_2_tool_planner_fixture.py
python -m pytest tests/contract/test_point01_m6_2_tool_planner.py -q
```

fixture `pass`、focused suite `5 passed`。正例覆盖 issuer authority-first primary/fallback、relationship context route、commercial gap stop、permission stop 与 replay digest；duplicate registry 与伪 execution authority context 负例 fail-closed。

## 边界与后续

当前能力是 `skeleton_and_fixture_proven / deterministic_nonexecuting_registry_planner`，不是 ToolGateway/Agentic Search runtime：ToolRegistrySnapshot/ToolSelectionPlan 都不持久化，`ToolInvocationReceipt` 不会在未执行时伪造，M5.4/M5.5 也不在本 slice 调用。没有 candidate retrieval、rerank、parser/numeric、Evidence Gate、judgment/context/Writer/full-chain、业务 Case mutation 或 legacy authority change。

下一步为 M6.3 CandidateBundle/RAG/DB metadata-first expansion；其实施仍需独立 scope 与门禁，不能把 M6.2 plan 当作 route-success/cost calibration。
