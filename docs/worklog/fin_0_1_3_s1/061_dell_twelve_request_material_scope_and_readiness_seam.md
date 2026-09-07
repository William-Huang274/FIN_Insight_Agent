# FIN 0.1.3 S1：DELL 12 请求材料范围与 Readiness 接缝处置

日期：2026-08-22
状态：结构修复与完整工程门通过；正式 AI-free R2 尚待 clean commit／push 后执行。

## 为什么没有直接晋升 43 Evidence Pack

外源 R2 和 Evidence Gate 已将 DELL Pack 从 29 条增至 43 条，但用旧 ProductReadiness 重放时，结果仍只识别旧链的 7 条 reviewed Evidence。这不是新增 Evidence 没有价值，而是两套任务合同未接通：

- 旧 readiness 面向历史 8 个固定问题；
- 当前七命题执行面已经拆为 12 个 EvidenceRequest；
- 12 个请求中的自然 product intent 在通用 fallback 中保持 `unclassified`，所以 12/12 的 hard material scope 为空；
- 外源 14 条新增 Evidence 也没有进入旧内部 candidate seed union。

若继续沿用旧结果，系统会出现“Pack 数量变多，但 readiness 完全不变”的假链路。旧结果已保留为不可变负向证据，不能用于 current promotion。

## 本次结构修复

1. 七命题执行程序新增显式材料范围蓝图。12 个请求的 product intent 均来自 Owner 已审计划，因此在本计划内被编译为 hard material axes；通用 fallback 对陌生自然语言继续 fail closed。
2. 每个请求显式声明需要的证据角色：direct、bridge、context、counter。只有 direct／bridge 可绑定 metric intent；背景和反方不得冒充数字权威。
3. Workbench current Runtime 接受可选、request-bound 的材料蓝图，并保存 research-plan／scope-compilation digest。未知 request ID 会被拒绝。
4. API response schema 同步公开 `material_scope`，避免服务直调成功、经 Workbench 接口却因新旧 schema 漂移失败。
5. 测试覆盖 12 请求完整性、产品轴不丢失、显式 blueprint 编译、未知请求拒绝和 API 端到端返回。

## 验证

- 定向：`34 passed`。
- 全仓：`1030 passed`，仅 2 条既有 SWIG deprecation warning。
- compileall：通过。
- active baseline：`200 Python／8 frontend／5 detectors／28 Runtime／0 forbidden`。
- repository secret scan：`7,613 files／0 findings`。
- diff check：通过。
- 0 模型、0 网络、0 Provider、0 Candidate promotion。

## 下一步与门禁

1. clean commit／push 本结构修复。
2. 用同一 12 请求执行正式 `dell-proposition-internal-r2`，必须证明 12/12 都由显式蓝图编译；路线没有材料时保留真实 residual，不得改写为公开信息 gap。
3. 将 43 Evidence Pack 按 12 个 MaterialRequirement 做 reviewed mapping 和 polarity adjudication，建立新的 integrated EvidencePackReadiness；不得把外源 Evidence 塞回旧 candidate seed 伪造命中。
4. 只有新 readiness 通过，才原子晋升 DELL current Pack，并重编 S2 的 reported／derived／estimate／scenario／typed-gap surfaces。
5. 动态 DELL 单单元仍未获 authority；S1、S2、S3、qualified-human、Workbench publication 与 release 均为 false。
