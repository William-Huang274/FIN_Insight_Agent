# FIN 0.1 S4-T05 Evidence Role Group Mapping 零调用实现

日期：2026-07-26

## 权限与边界

用户以“继续”授权：

`S4-T05-DELL-EVIDENCE-ROLE-GROUP-MAPPING-AND-ACTUAL-DISPATCH-PREFLIGHT-ZERO-CALL-IMPLEMENTATION`

本轮允许修改共享 Runtime、EvidenceService、S4 binding/schema、exact preflight 与测试；不允许 replacement admission、真实模型/Provider/网络/数据源调用、第二次 DELL exact-live、paired assessment、Human review 或 S4-T06 以后任务。

## 实现

新增两个闭合合同：

- `fin01.s4.case_evidence_role_group_mapping:v1`
- `fin01.s4.case_evidence_slot_alignment:v1`

mapping 从 `S4CaseRuntimeBinding.program_cell_contracts.required_evidence_roles` 派生，不按 ticker 手写。跨 Case 轴为 `program_cell_id`，Canonical slot 仍按同 Cell 的 exact `evidence_role` 解析。DELL、MU 都保持 `[4,5,5]` 共 14 个 role，要求 exact-once、同 owner、同 acceptance role、同 issuer scope。

新增 `compile_profile_evidence_dispatch` 作为实际 Runtime 和 exact preflight 的唯一派发入口：

- legacy S3/NVDA 继续使用原三路 fixture evidence plan；
- S4 只生成 role-group mapping 与 Canonical slot alignment receipt；
- 两条路径互斥，S4 不允许进入 `_s3_fixture_candidate_sets`；
- S4 Runtime plan、alignment receipt、prepared input 和 manifest 都携带可核验 digest。

同时修正一个潜伏的身份混淆：S4 bounded executor 不再错误要求 Canonical DecisionSurface ref 等于 Case profile ref。Case profile、DecisionSurface 和 admission input digest 分别保留各自身份职责。

## 验证

- 专项实现与负例：`14 passed`
- 首轮邻近 S3/S4 回归：`32 passed`
- 扩展 claim-policy/S3/S4 回归：`30 passed`
- 历史 S4-T04 非 code-hash 项：`5 passed`
- compileall：`pass`
- Project OS implementation preflight：`pass`

专项覆盖：

- DELL/MU 均解析 14/14 exact roles；
- missing、extra、duplicate、unknown/wrong Cell、wrong owner、wrong entity scope、duplicate Cell owner、mapping digest tamper 全部 fail-closed；
- disposable clone 中 exact preflight 与实际 Runtime 在进入 executor 前得到相同 mapping/alignment/dispatch digests；
- DELL 本地 fake Provider 达到 6 logical nodes、12 callbacks、12 captures、9 logical Artifacts；
- 真实 model/provider/network/source/tool 调用均为 0，目标 Runtime 无写入。

历史 S4-T04 code-hash 锁定项正确检测到本次授权实现已改变代码字节；没有重写历史 admission 或 consumed Run。旧 live-runner 回归在本机两次超时且没有测试结果，登记为 inconclusive，不计作 pass 或 fail。

## 当前结论

RC-P36-058 的实现已 fixture-proven，但仍需 fresh-agent proof 才能关闭 full-chain engineering blocker。DELL R2、九个真实 Artifacts、paired assessment、MU/NVDA、Human、S4 pass、S5、release、production 均未证明。

下一项：

`S4-T05-DELL-EVIDENCE-ROLE-GROUP-MAPPING-REPAIR-FRESH-AGENT-PROOF-DECISION`

该决策通过后，仍需另行授权 fresh replacement admission；本轮没有签发或执行。
