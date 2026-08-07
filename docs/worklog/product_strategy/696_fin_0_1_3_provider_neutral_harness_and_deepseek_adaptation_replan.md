# FIN 0.1.3 Provider-neutral Harness 与 DeepSeek 适配重排

日期：2026-08-07

状态：`documented_and_contract_translated_runtime_not_implemented`

## 1. 反思结论

当前 Harness 同时包含两类性质不同的控制：金融产品长期需要的 truth/provenance/permission/promotion 内核，以及为 DeepSeek 当前合同遵循能力增加的 schema、Prompt 和字段补偿。若继续混合，每次模型失败都会扩大共享 Runtime，未来换模型时形成高迁移成本。

本轮正式拆成三层：稳定金融控制内核、版本化 ModelCapabilityProfile、按 contract family 授权的 Adaptive Autonomy。每条限制必须标为 permanent invariant、adaptive gate 或 provider workaround；后两类必须有复测、降级、shadow 和删除条件。

## 2. DeepSeek 当前证据

- 已自然观察通过：JSON/envelope、case identity、protected numeric ref。
- 已自然观察失败：evidence-role semantics、correction closure self-attestation、analyst-threshold discipline。
- 当前撤销：corrected whole-node authoring 与 formal DELL full graph。
- 该结论只绑定 DeepSeek v4 Pro＋当前 contract family，不外推到 Flash、未来 Pro 或其他 Provider。

## 3. 下一步适配

不再直接修完整输出，改为 `DS-A1/A2/A3`：

1. 冻结 family 级 capability profile 和最大 autonomy tier。
2. DeepSeek 输出 evidence-role、claim、mechanism、counter-thesis、gap、WWC typed atom；Harness 根据验证后的 atom 计算 closure，模型不得自报 closed。
3. atom 通过后再由 DeepSeek 生成 protected narrative，本地仅 render material span；用 paired 八维质量证明没有模板化退化。

一个 family 每轮最多一次结构修订；仍失败则降级权限或比较其他模型，不继续扩 Prompt。逻辑两阶段当前可分两次调用，未来模型若组合 canary 稳定通过可合并。

## 4. 文档同步

- PRD 新增 7.10。
- 跨域合同 38 新增三层结构、能力 profile、自主权等级、约束退役、DeepSeek profile 和适配/停止规则。
- TECH_00/00A 登记 `ModelCapabilityProfile / AutonomyGrant / ConstraintRetirementDecision` 与当前成熟度。
- FIN 0.1.3 计划新增 7A.6，并把 `DS-A1/A2/A3` 作为 S3-06/07 前置子包；S1-06/07/08 顺序不变。

## 5. 边界

本轮只修改产品、技术、计划和 Project OS 文档；Runtime、模型、Provider、admission、canary 和测试均为 0。它不证明 DeepSeek 已适配，也不授权正式 DELL、MU/NVDA 或 Experiment B。
