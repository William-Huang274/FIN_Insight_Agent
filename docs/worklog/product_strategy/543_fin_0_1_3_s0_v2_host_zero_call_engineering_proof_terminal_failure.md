# 543 — FIN 0.1.3 S0 v2 host zero-call engineering proof 终态失败

日期：2026-08-01

结论：`terminal failed / unique v2 host run consumed / project-level disposition required`

## 1. 执行结果

已授权的唯一 v2 host zero-call engineering proof 从 clean/synced commit `cfbdbe7ab79b86fc71f04f609d193c01452043e0` 启动。仓外受限证据根为：

`D:/FIN_Insight_Agent_recovery/proofs/fin_0_1_3_s0_v2_host_zero_call_engineering_proof_20260801T101426Z_head_cfbdbe7a.failed`

`execution_started.json` SHA256=`d5a222549019dfff5971a6a73a542e2ba71d64dd7df8711359d829280b3aedd4`；terminal `verification.json` SHA256=`dd8b9eef8e95b56f61519cd3ca8cd92266b18e302f777c45d456583d0416f667`。证据根共有 6 个文件、766661 bytes；4 个 content-addressed objects 的路径与实际 SHA256 全部一致。

启动前 Project OS preflight 为 `pass / 0 missing files / 0 missing capabilities / 0 open blockers for this scope`。tracked repository readback 包含 4316 行，全部带 SHA256。失败后只读检查证明 branch、HEAD 与 upstream 未变化，worktree 仍 clean/synced。

## 2. 首个可信失败

运行在 `compile_repository_inventory(ROOT, active)` 终止：

- exception：`HermeticTestRunnerError`
- code：`hermetic_repository_reference_policy_boundary_invalid`
- proof manifest 值：`unknown_reference_behavior=fail_closed_collect_all`
- shared compiler 精确要求：`unknown_reference_behavior=fail_closed`

因此 application import、active collect、pytest、DELL/MU/NVDA full-fake 与 diagnostic Artifact 均未开始，计数为 `0/0/0/0`。这不是 DS 不遵循指令，也不是 Provider、reference-role 分类行为、金融 Runtime L1 或分析质量失败；它是 proof-specific manifest 与共享 compiler 的 policy enum 合同漂移。

## 3. 为什么执行前检查没有挡住

proof 包装阶段的 contract-only、validate-only 和选定 pytest matrix 都通过，但它们校验的是 digest、权限、测试选择与治理字段，没有在消费 run 之前调用与正式执行相同的 `compile_repository_inventory` 最早边界。换句话说，测试证明了“文件彼此绑定且静态合同成立”，却没有证明“这个 exact manifest 可以穿过正式 runner 的第一道编译门”。

这登记为 `RC-P36-095-fin-0-1-3-v2-host-proof-manifest-policy-enum-contract-drift`。工程学习是：固定预算 proof 的非消费预检必须穿过正式运行的同一最早边界；单独的 syntactic contract validator 不能代替 execution-boundary canary。

## 4. 止损规则执行

按 authority 与 execution manifest 已冻结的失败规则：

- 没有把 manifest 改为 `fail_closed` 后重跑；
- 没有将第二次运行包装为 retry、replacement 或新 proof；
- 没有修改共享 Runtime、reference-role、environment 或测试合同；
- 没有授权或执行 formal two-disposable proof；
- 没有模型、Provider、credential probe、network/source、admission、business Run 或 business Artifact。

v2 固定预算当前为 `maximum [1,1,1] / observed [1,1,0]`。旧 T03 的 `1/1` 失败和旧 T04 未执行事实保持不可变。

## 5. 项目与产品真值

RC-P36-090–094 没有获得 host/formal 行为证据，继续 open/full-chain blocker；新增 RC-P36-095。FIN 0.1.3 S0 为 terminal honest block，S1/S2 未进入，release 未通过；FIN 0.1.4 没有创建，FIN 0.2 Earnings Review Alpha 定义不变。本项没有用户可见金融研究能力增量。

机器收口：`configs/releases/fin_ia_0_1_3_s0_v2_host_zero_call_engineering_proof_terminal_failure_and_project_level_disposition_required_v1_0.json`

收口 SHA256：`5e452fdef23b8492feeabef994731a2997c3eee11b9ed0865ff6ec584d57f6b1`

当前投影：`configs/runtime/fin_ia_0_1_3_current_program_projection_v1_7.json`

当前唯一下一项：`FIN-0.1.3-S0-V2-HOST-PROOF-FIRST-CREDIBLE-FAILURE-PROJECT-LEVEL-DISPOSITION-DECISION`

## 6. 收口验证

- closeout、v1.7 projection、program backlog 与 S4 backlog 均可解析为 JSON；三个 Project OS ledger 全量 JSONL 可解析；
- proof 冻结选择矩阵加本次 terminal contract：`93 passed in 21.53s`；
- 当前唯一下一 scope 的 Project OS preflight：`pass / 0 missing files / 0 missing capabilities / 0 applicable open blockers`；
- 旧 authority snapshot 与旧 T03 immutable event contract 同时通过，没有用新终态改写历史证据。
