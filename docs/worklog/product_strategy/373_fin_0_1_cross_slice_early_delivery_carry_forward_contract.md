# FIN 0.1 跨 Slice 提前交付传递合同

时间：2026-07-24

## 用户要求

用户要求：若 S3-T09 通过，T09 超前承担的后续任务、已完成进度和结果必须进入后续 S 任务的持久记录，避免 S4、S5 不知道前序已经完成什么而重复建设。

本轮只授权规划、backlog、交接和机器合同更新；不授权 T09 修复、模型调用、admission、rerun、comparison、owner review、T10、S4、release 或 production。

## 决策

新增 `fin_ia_0_1_cross_slice_early_delivery_carry_forward_contract_v1_0`，把跨 Slice 传递拆成两个生产节点和两个消费节点：

- T09 acceptance：生成 S3→S4 manifest 草稿；
- T10 owner review/closeout：冻结 manifest 和 digest；
- S4 entry：逐项标记原样复用、扩展、新 Case 重验、后置或有理由取代；
- S5 entry：核对 S3 提前交付与 S4 消费结果，区分沿用证明、candidate 重验和 roadmap 缺口。

manifest 每项必须记录原计划归属、当前成熟度、精确状态、证据、root cause、known gaps、remaining acceptance、复用指令和 later disposition。成熟度严格区分 `documented`、`contract_translated`、`fixture_proven`、`live_partial`、`live_complete`、`owner_accepted` 和 `release_qualified`，禁止把局部或 fixture 证明冒充完整产品。

## 当前边界

T09 当前仍因 Lead-v5 per-field narrative length 失败而 blocked，所以 carry-forward manifest 尚未到生成时点，不能提前伪造完成清单。当前唯一 next action、RC-P36-047 状态和模型调用授权边界均未变化。

本轮 model/provider/network/source/tool calls 均为 0；未新建 WorkUnit、Attempt、Run、Artifact、comparison 或 Human Review。

## 文件

- `configs/releases/fin_ia_0_1_cross_slice_early_delivery_carry_forward_contract_v1_0.json`
- `configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json`
- `docs/architecture/repository/FIN_0_1_PROGRAM_EXECUTION_PLAN_DRAFT_20260719.zh-CN.md`
- `tests/contract/test_fin_0_1_cross_slice_early_delivery_carry_forward_contract.py`
- `docs/project_os/current_context_pack.zh-CN.md`
- `docs/project_os/thread_handoff_20260719_fin_0_1_s1_program_execution.zh-CN.md`
- `docs/project_os/capability_status_ledger.jsonl`

## 验证

- 新合同、S3 entry/T08 历史边界和相邻 Lead-v5 proof/issuance/result 合同：`31 passed`；
- JSON/JSONL 全量解析：通过；
- Program Plan 当前 SHA-256 与 backlog frozen digest：一致；
- T09 当前 status、next action 和未授权边界：未改变；
- 两条历史测试原先把可变 backlog 固定为旧 T09 瞬时状态，已改为只验证不可变 S3 entry/T08 合同和依赖关系；
- 首次直接组合命令受本机 Python `isolated=1` 影响，旧测试导入不到 repo-root `apps`；在测试进程显式加入项目根路径后同一组断言全部通过，未修改业务代码。
