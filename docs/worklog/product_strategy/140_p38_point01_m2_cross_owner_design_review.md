# P38 Point 01 M2.0 Cross-Owner Design Review

日期：2026-07-12

状态：`user_confirmed_calibration_accepted / five_design_findings_resolved / m2_open`

## 审阅方式与边界

应用户要求，Codex 以 schema/contract、runtime/replay、authority/model admission、research/evidence policy、acceptance/calibration 五个职责视角对 M2.1-M2.10 做结构化审阅。该审阅由单一 Codex agent 进行 role separation，不是独立 human 或多人签字；当前线程 human reviewer 随后明确表示“接受，继续往下做”，该 user confirmation 现作为 M2.0 calibration disposition。

## 发现与修复

1. M2.2 使用 `PackResolution` 却未依赖 M2.3；现将 M2.2 的 full assembly 依赖补为 M2.1、M2.3-M2.7，并显式消费 pack、selection、composition、slot/policy/gap、legacy migration contracts。
2. M2.4 的 intent objects 原先没有生产者；M2.1 现在输出 `NormalizedIntentProfile`，M2.4 负责 `PackSelectionIntentClassifier`。
3. M2.6 需要 source-authority policy，但原图没有 owner；M2.3 现在输出 `ResolvedSourceAuthorityPolicySet`，M2.6 显式消费它。
4. M2.9 原先依赖 `ModelCompilationProposal`，而 M2.8 正确默认拒绝模型；现改为依赖 `ModelAdmissionDecision` 与 deterministic `DecisionSurfaceBundle`，denied admission 是显式 shadow route，不是隐式 fallback。
5. 初始 lint 只验证 owner/cycle；现增加 external-provider 声明、single output producer 和 transitive producer-to-consumer dependency closure。

## 证据与验证

- 审阅记录：`configs/engineering_handoff/point01_m2_cross_owner_design_review_v1_0.json`。
- 更新后的 manifest：10 个 unique owner、31 条无环 dependencies。
- `python scripts/engineering/run_point01_m2_design_lint.py`：pass。
- `python -m pytest -q -m fast_contract tests/contract/test_point01_m2_design_freeze.py`：`4 passed`。
- `python -m compileall -q scripts/engineering/run_point01_m2_design_lint.py tests/contract/test_point01_m2_design_freeze.py`：pass。

## 结论与后续

设计审阅结果为 `pass_with_resolved_design_findings_user_confirmed`，M2.0 calibration 已 accepted。它不实现 M2 child runtime，也不允许 M3/M4、模型、paid/full-chain、Evidence/Writer 或 authority cutover。下一工程实现点为 M2.1。
