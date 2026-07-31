# FIN 0.1 S4-T01 manifest consumption 与 three-case entry

日期：2026-07-26

## 用户决策与权限

用户在收到 S4 整体打法、DELL→MU→NVDA 顺序、预期、成本边界与 Human 依赖后回复“认可”。此前已明确说明下一步只执行：

- 零调用 S4 Entry Decision；
- 详细任务拆解；
- S3→S4 manifest consumption；
- 不直接运行模型。

因此本轮只完成 S4-T01。S4-T02 至 T10、模型、Provider、网络、来源、外部工具、新 Case Run、业务 Artifact、qualified-senior attestation、S5、Alpha、release 和 production 均未授权。

## 交付结果

新增 S4 entry decision：

- `configs/releases/fin_ia_0_1_s4_entry_manifest_consumption_and_three_case_transfer_decision_v1_0.json`
- SHA256：`097e9bcc5578a80abb04da02686498c73356e8a05c58c7ce7d7063cc27179179`

新增 S4 detailed backlog：

- `configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json`
- SHA256：`9d54045aa8091d4338d5b4e9460442b1bb5a9d6c2046a683f25ac6d18b38ede3`

新增 S4 源执行计划：

- `docs/architecture/repository/FIN_0_1_S4_THREE_CASE_TRANSFER_AND_HUMAN_CALIBRATION_EXECUTION_PLAN_20260726.zh-CN.md`

S3→S4 manifest SHA256 `0b429dea6e796cfbc5e9de847396d48f16b64969cd7e93e307a6c4ff84e72108` 已验证相等并由 S4-T01 消费，frozen manifest 未改写。八个能力域的 S4 处置为：

- `reuse_as_is`：2；
- `extend`：2；
- `revalidate_for_new_case_or_candidate`：4；
- defer/supersede：0。

详细 backlog 冻结 S4-T01 至 S4-T10。Case 顺序为 DELL→MU→NVDA；DELL 作为最大距离 transfer test 优先暴露 accelerator/NVDA hardcode，MU 验证 HBM/半导体周期机制，NVDA 最后生成 post-transfer R3 candidate。

## 方法与上游 readiness

登记 `RC-P36-055-s4-dell-mu-case-pack-and-financial-method-to-runtime-gap`：

- DELL/MU 已进入产品与架构范围；
- 尚无冻结的 S4 exact Case Pack；
- 尚无 OEM/HBM 方法达到 `runtime_injected + node_level_consumed` 的 S4 证明；
- 这是项目内上游 readiness gap，不是模型质量问题；
- 在 S4-T02/T03 关闭前，禁止 paid canary、admission 和 full-chain。

## 预算与停止规则

规划参考：

- 单 Case S3 NVDA exact：12 calls、61,492 tokens、USD 0.02643915；
- 三 Case 参考：36 calls、184,476 tokens、USD 0.07931745；
- S4 初始规划上限：40 calls、225,000 tokens、USD 0.15，包含任何另获授权的 canary。

规划预算不构成执行授权。paid canary 默认关闭；每个 Case exact-once，transport retry=0，禁止自动 paid retry/replay/relaunch/rerun，首个可信失败停止当前 Case。

## 同步文件

- `configs/releases/fin_ia_0_1_cross_slice_early_delivery_carry_forward_contract_v1_0.json`
- `configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json`
- `docs/architecture/repository/FIN_0_1_PROGRAM_EXECUTION_PLAN_DRAFT_20260719.zh-CN.md`
- `docs/project_os/current_context_pack.zh-CN.md`
- `docs/project_os/capability_status_ledger.jsonl`
- `docs/project_os/root_cause_issue_ledger.jsonl`
- `docs/worklog/README.md`

## Verification

- S4-T01、cross-slice、S3-T10 与相邻 T09/T08 合同回归：`39 passed in 16.99s`
- JSON 解析：4 个通过
- JSONL 全文件解析：2 个通过
- manifest、S4 detailed backlog SHA256 绑定：通过
- 本轮 model/provider/network/source/tool/new Run/new business Artifact/Human Review：`0/0/0/0/0/0/0/0`

## 当前状态与下一步

- S4：`started_entry_only`
- S4-T01：`pass_zero_call`
- S4-T02：`pending_separate_authority`
- DELL R2、MU R2、NVDA R3：未开始
- S4 pass、S5 readiness、Alpha/release/production：未认定

当前唯一下一项：

`S4-T02-DELL-MU-CASE-PACK-AND-FINANCIAL-METHOD-TO-RUNTIME-CONTRACT-DECISION`
