# FIN 0.1 S4-T05 TaskClaimLinkPolicy fresh-agent proof 决策

日期：2026-07-27

## 结论

`fin01.s3.task_claim_link_policy:v1` 的独立 fresh-agent proof 已在零调用边界内冻结。该 proof 证明当前实现、DELL source-grounded input、共享 role mapping/dispatch 和新的 R3 prospective admission 可以形成一致的下一次执行合同，但没有签发 admission、没有消费 Run，也没有运行模型或生成业务 Artifact。

RC-P36-059 当前状态推进为：

`fresh_proof_contract_frozen_admission_issuance_pending`

DELL R2 仍未证明。

## 双重独立证明

proof generator 在两个独立 disposable runtime clone 上运行，输出完全一致：

- canonical output digest：`4ae37a6f16edb3f2bf474467710c5ee0d07a51c2b771d6a20712feb354e407ed`
- fresh WorkUnit：`wu_p02_5_4e861814210bbc43c8632e22`
- fresh Attempt：`attempt_fin01_ed9ba7af7a2805527b0d7cb1`
- fresh ResearchRun：`research_run_fin01_8905466e65d6259e54d42f6c`
- input digest：`3499c03470c5bec5168dc87a2974802869da389f2ef588f41021731828d09e96`
- preparation digest：`be99a4cdcd8ddaf2ec7c59dfbfd341e4313ef4a9ff7d11f0798494561ab67b05`
- mapping/alignment/dispatch digests：`73284fd4...c812 / 9c35e534...9cfb / 8755c7cc...70bd`

两个历史失败 Run 均保留且未复用。clone 内 execution counts 在 prepare 前后均为 `2 WorkUnit / 2 Attempt / 2 Run / 0 Artifact`。

## Prospective admission

新的 prospective admission：

- ID：`fin01-s4-t05-dell-task-claim-link-policy-fresh-exact-admission-r3`
- execution mode：`exact_live_s4_dell_task_claim_link_policy_r3`
- digest：`4be4fa99479da78547bfc9266c708478aa524d459db97c7341799b2724a7f29d`
- 显式 capability：`task_claim_link_policy_ref=fin01.s3.task_claim_link_policy:v1`

旧 consumed R2 admission digest `058c5792...1af3` 保持不变且不含新 capability；R3 digest 已前向推进。prospective admission 文件仍不存在，issued/consumed/execution_started 均为 false。

## 只读与成功门槛

目标 canonical database、object tree 和 logical snapshot 在 proof 前后完全不变：

- object tree SHA256：`60305e95...ec1b`
- logical snapshot digest：`b63e5447...9405`

SQLite physical SHA 只用于单次 invocation 内的前后不变检查，不作为跨 invocation 的业务 identity；这样可避免只读 service 初始化造成 page/checkpoint 布局漂移时误判 fresh proof。

未来成功仍要求：

- terminal succeeded；
- 六逻辑节点、十二次 Provider 调用、九类 Artifact；
- 三个 WWC segment 全部消费 TaskClaimLinkPolicy；
- persisted request alias residue=0；
- unknown/cross-Cell task-to-Claim link=0；
- layered acceptance 通过后才能执行 paired assessment。

## 本轮边界

模型 / Provider / 网络 / source / external tool 调用为 `0 / 0 / 0 / 0 / 0`；admission issued/consumed、target canonical/object write、paired assessment、Human review 均为 0。

deterministic task identity、完整 WWC failure taxonomy 和跨阶段统一 identity 没有重入 T05，继续按原计划后传。

## 验证

- fresh-proof contract suite：`6 passed`
- TaskClaimLinkPolicy、ClaimFactLink、scoped identity、role mapping 与历史 admission/proof 兼容批次：`80 passed`
- S4-T04/T05 全量相邻回归：`86 passed`
- Python compileall：通过
- 下一 issuance scope 的 Project OS preflight：通过，open blocker=0

## 产物与下一步

- 决策合同：`configs/releases/fin_ia_0_1_s4_t05_task_claim_link_policy_fresh_agent_proof_decision_v1_0.json`
- SHA256：`cc5de889fff7a708afb000d4baae42cefed571cb2f0eb5fdd624f81676bf2b5d`
- generator：`scripts/releases/prepare_fin_ia_0_1_s4_t05_task_claim_link_policy_fresh_proof.py`
- 合同测试：`tests/contract/test_fin_0_1_s4_t05_task_claim_link_policy_fresh_agent_proof_decision.py`

下一项仅为：

`S4-T05-DELL-WWC-TASK-TO-CLAIM-CLOSED-IDENTITY-FRESH-EXACT-ADMISSION-ISSUANCE-DECISION`

下一项需独立授权，并且只允许把 frozen payload 物化为 issued/unconsumed admission；不包含 exact-live。
