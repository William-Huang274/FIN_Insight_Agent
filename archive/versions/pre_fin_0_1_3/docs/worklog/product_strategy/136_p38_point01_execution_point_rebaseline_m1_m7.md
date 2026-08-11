# P38 Point 01 M1-M7 Execution-Point Rebaseline

日期：2026-07-12

状态：`planning_governance_updated / no_runtime_change / milestones_m1_m2_open`

## 1. 原因

新执行窗口完成了 M1 lifecycle/read/replay 与 deterministic DecisionSurface planning skeleton，但采用最小可验证路线。审计确认测试 `39 passed`，同时发现粗粒度 M1/M2 容易让执行模型把类、fixture 或单 case 误记为 milestone complete。

## 2. 状态纠偏

- lifecycle/store/read/replay 归档为 M1.1/M1.2 `fixture_proven`；
- `retryable=true` 尚无 Attempt N+1 执行语义，M1.3 open，M1.5 closeout blocked；
- CompilerInput/shape validator 归档为 M2.1 `fixture_proven_shape_only`；
- deterministic seed assembler/commit/readback 归档为 M2.2 `fixture_proven`；
- 当前代码不做 query understanding、pack selection、cell composition 或 multi-sector calibration，M2.3-M2.10 open；
- count parity helper 仅为 M3.1 skeleton candidate，不是 shadow comparison pass。

## 3. 文档变更

Point 01 新增第 26 节：

- 双轴 maturity：design 与 implementation；
- skeleton / fixture / full / calibrated 的统一定义；
- M1/M2 重归档与完整 M2 execution matrix；
- M3.0-M3.8、M4.0-M4.8、M5.0-M5.9、M6.0-M6.10、M7.0-M7.9；
- 只有 M1.5/M2.10/M3.8/M4.8/M5.9/M6.10/M7.9 可宣布 milestone complete。

## 4. 验证与边界

本轮只审计既有代码并更新规划/状态文档。审计时重跑 focused/adjacent suite：`39 passed`。未修改 runtime、未运行 paid LLM、full-chain、model compiler、Evidence、Writer、cutover 或 migration。

下一工程动作必须是 M1.3 retry/multi-attempt；完成后按 M2.3-M2.10 逐点推进，不得直接进入 M3。
