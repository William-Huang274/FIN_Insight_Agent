# P38 Point 01：Foundation Alpha 范围重定义与合同收口

日期：2026-07-18

状态：`POINT01_FOUNDATION_ALPHA_CONTRACT_RUNTIME_PROOF_COMPLETE`

## 产品裁决

用户选择将 Point 01 收口为 Foundation Alpha 的合同与 runtime proof，而不继续消耗 operational repair/attempt 预算。该决定不是 operational qualification pass、FIN 0.1 release 或 production admission。

- `P01-G2` 固定为 `failed_single_operational_attempt_consumed_and_deferred_to_REL_PROD_001_RG1`；唯一 receipt 已消费，永久禁止 replay、renewal、replacement 和 retry。
- 四轴状态：contract/runtime proof complete；`operational_qualification=not_qualified_deferred`；`production_readiness=not_admitted`；`legacy_global_authority=retained`。
- P02.0 仅获 fixture/shadow/internal development 准入；不得由此启动 operational runtime 或宣称 FIN 0.1 release。

## 新的机器合同

- active ReleaseContract：[fin_ia_0_1_release_contract_v1_2.json](D:/FIN_Insight_Agent/configs/releases/fin_ia_0_1_release_contract_v1_2.json)；v1.1 保留为 historical/superseded；
- active detailed backlog：[fin_ia_0_1_detailed_execution_backlog_v1_1.json](D:/FIN_Insight_Agent/configs/releases/fin_ia_0_1_detailed_execution_backlog_v1_1.json)；v1.0 保留为 historical/superseded；
- scope-closeout handoff：[point01_foundation_alpha_scope_closeout_decision_v1_0.json](D:/FIN_Insight_Agent/configs/releases/point01_foundation_alpha_scope_closeout_decision_v1_0.json)。

它们不改变 `FIN_0_1_INTERNAL_ALPHA_FEATURE_SCOPE_MATRIX` 的功能范围或版本。ReleaseContract v1.2 将 P07.5 前的 `RG1_vertical_path` 固定为不可绕过的发布硬阻断：必须证明 exact package entry→adapter→subprocess→clean-child identity、一条 bounded operational vertical run，以及 persisted actual/oracle/reviewer/Workbench 结果。

## 诚实的根因边界

静态路径审查确认：顶层 runner 接收 candidate-bound package，但 production clean-child leaf 仍通过 `PACKAGE_PATH` 使用 historical v2.10 manifest；此前 bridge 验收未覆盖端到端 identity propagation。已保留的 incident envelope 仅包含截断、脱敏 stderr，因此不能证明唯一的动态 exception root cause。该传播缺口被转入 `REL-PROD-001 RG1` hard debt，不在本轮修 runtime。

## 验证与未运行项

本轮只允许 JSON/Markdown/schema/digest/targeted contract checks。未运行 operational baseline、negative case、network/tool/model/provider、paid/full-chain、业务 Case mutation、production cutover，也未创建 authority/approval/receipt。
