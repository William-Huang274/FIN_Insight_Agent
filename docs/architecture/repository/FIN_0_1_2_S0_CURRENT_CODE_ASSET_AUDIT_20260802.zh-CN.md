# FIN 0.1.2 S0 当前代码资产只读审计

日期：2026-08-02
审计起点：`b1b3df84e68d5e1b651f808b794d2642782ce67b`
状态：`audit complete / owner review pending / no implementation`

## 1. 总体判断

当前代码不是空白。原 FIN 0.1.2 与原 FIN 0.1.3 已累计形成一组可复用的共同 Runtime、三案例 fixture、资源清单、引用分类、环境路径处理和失败留存实现。但它们被多套历史 manifest、current projection、一次性 proof 决策和版本专用 runner 包住，导致“测试当前代码”与“验证历史决定”混在一起。

本次 focused 零调用测试结果为 `57 passed / 3 failed`。三项失败共同停在旧 current projection 与今天 backlog/next action 不一致，错误码为 `current_projection_next_action_drift`；没有证据表明本轮资源 registry、六类引用规则或 typed environment 单元行为出现新失败。这说明当前最早问题是测试/当前状态所有权，而不是继续增加资源字段。

## 2. 建议直接保留并重新验收

| 资产 | 主要位置 | 判断 |
| --- | --- | --- |
| 共同模型边界和本地真值合同 | `configs/runtime/fin_ia_0_1_2_common_runtime_contract_family_source_v1_0.json`、`apps/workbench/backend/application/fin_0_1_2_runtime_contract_binding.py` | 保留；S1/S2 再证明生产消费和模型边界 |
| 三案例真实 fixture/full-fake | `tests/fixtures/fin_0_1_2/`、既有 S1/S4 deterministic tests | 保留；S0 只作基础回归，S1 正式验收 |
| RuntimeResourceRegistry | `src/sec_agent/runtime_resource_registry.py`、`configs/runtime/fin_ia_0_1_3_runtime_resource_registry_v1_0.json` | 保留实现；文件名保留历史来源，当前 manifest 以 digest 复用 |
| 六类引用角色 | `src/sec_agent/reference_role_registry.py`、两份 reference-role registry | 保留；重新证明 current host/clean behavior |
| typed environment 与 semantic projection | `src/sec_agent/hermetic_test_runner.py`、typed-environment/semantic-parity configs | 保留通用实现；修复 current-state 耦合后重验 |
| capture 与 terminal result | `src/sec_agent/hermetic_test_capture.py` 及既有 capture-v2 路径 | 保留；继续保证失败先留原始安全证据 |
| Workbench 和九件套历史资产 | `apps/workbench/`、历史 S3/S4 artifacts/evidence | 保留为产品/诊断基线，不作为当前版本验收通过 |

## 3. 建议集中修复

| 问题 | 当前表现 | 修复方向 |
| --- | --- | --- |
| current truth 与历史 event 混合 | 旧 manifest 验证 mutable backlog、ledger tail 和 next action | current projection 独立拥有今天真值；历史测试只验证当时事件 |
| runner 硬编码版本状态 | `validate_host_current_program_projection` 包含旧状态白名单 | 改为版本中性 schema/transition 校验，不枚举每次计划文本 |
| proof control plane 过重 | 用户授权、预算、版本和 runner 状态互相锁死 | 缩减为一次运行的 planned/running/pass/fail 记录；产品授权保留在外部决策，不进入业务测试状态机 |
| version-specific manifests/scripts | 多份 `fin_0_1_3` manifest/runner 只能验证历史快照 | 新建一个 FIN 0.1.2 current manifest；旧文件保持 immutable audit |
| S0/S1 测试责任混杂 | 三案例逻辑失败反向改变 S0 历史状态 | S0 只管运行基础和可复现性；S1 管三案例确定性产品链 |
| 一次失败冻结版本 | proof budget 被用作产品版本停止器 | 保留 attempt 证据，根因修复后以新 attempt 重验，不增产品版本 |

## 4. 建议退出当前入口但不删除

- `configs/runtime/fin_ia_0_1_4_current_program_projection_v1_0.json`：保留为错误版本治理的历史快照，不再是 current；
- 原 FIN 0.1.2→0.1.3 与 0.1.3→0.1.4 版本处置：保留历史事实，由新合并决定 supersede 其当前效力；
- `run_fin_0_1_3_*proof*.py`：保留历史复现用途，不再作为新 S0 的执行入口；
- “一个失败 proof 自动耗尽整个版本”“同版本 no-v4 因而升级产品版本”：退出当前治理；
- 未执行的原 0.1.4 生命周期状态机 StagePlan：不继续实现，吸收其中 event/current 分离的有效思想，但不复制复杂状态机。

## 5. 阶段重新分配

- S0：RC-P36-090–096、资源/路径/隔离环境、current/event/test ownership；
- S1：三案例 deterministic 6/12/12/9、跨案/数字/日期/lineage mutation；
- S2：DeepSeek Flash stable/Pro preview 和 strict-schema/atom 边界；
- S3：NVDA exact-live、九件套、paired 与 owner；
- S4：DELL/MU transfer、NVDA regression、Workbench dogfood；
- S5：release/rollback/qualification。

## 6. 风险与建议

1. 不建议大规模重命名所有含 `0_1_3` 的代码和配置。重命名会破坏大量历史 digest 和引用，收益低；应以新的 current manifest 映射并逐步在新代码中采用版本中性名称。
2. 不建议先实现完整 proof lifecycle state machine。当前失败来自治理与 mutable truth 耦合，优先简化比增加状态更可靠。
3. 不建议一次运行整个历史合同库作为 S0 gate。应先建立 current suite，历史 suite 单独审计；否则历史 next-action 断言会持续制造假失败。
4. S0 修复完成前不应调用模型。当前三项失败可由本地代码和测试完全解释。

## 7. 当前下一步

请 Owner 审核本分类。批准后，先修 current/event ownership 与版本中性 runner，再集中处理 RC-P36-090–096；不自动进入模型或 exact-live。
