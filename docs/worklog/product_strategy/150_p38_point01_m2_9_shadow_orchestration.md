# P38 Point 01 M2.9 Shadow Orchestration / Replay

日期：2026-07-12

状态：`m2_9_full_implemented / calibrated_four_sector_shadow_replay / shadow_only`

## 完成

- 新增 `ShadowCompilerOrchestrator`、AttemptTrace、RepairProjection 与 ReplayReport，将 M2.2 envelope、M2.8 denied proposal 和 M1 WorkUnit/Attempt/event/artifact/readback/replay 连接起来。
- 成功 path 必须为 denied model admission、shadow mode、atomic artifact commit、readback pass 与 replay pass；否则产生 typed repair projection。

## 校准与验证

- AI/Semis、SaaS、Healthcare、Banks 四个 case 都通过 WorkUnit/Attempt/artifact/event/readback/replay。
- flag-off 不创建任何 canonical artifact；伪造 admitted model decision 会在写入前 fail-close。
- model/external call 为 0，后续 M2 专项 suite 纳入该路径。

## 边界与回滚

- orchestration 只消费 deterministic envelope，不能取证、补源、写 Writer、调用 provider 或改变 legacy authority。
- 失败 path 要求新 immutable Attempt 修复，不修改旧 Attempt/history。
