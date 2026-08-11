# FIN 0.1 S4-T05 TaskClaimLinkPolicy fresh exact admission 签发

日期：2026-07-27

## 结论

frozen fresh-proof 中的 R3 prospective payload 已原样物化为 exact admission，并完成 issued/unconsumed 零调用签发。没有消费 admission、没有创建 WorkUnit/Attempt/ResearchRun、没有启动模型或 Provider，也没有进入 paired assessment。

RC-P36-059 当前状态推进为：

`fresh_exact_admission_issued_unconsumed_execution_authority_pending`

DELL R2 仍未证明。

## 签发前复验

在 admission 文件存在前，fresh-proof generator 连续运行两次：

- 两次 canonical output digest 均为 `4ae37a6f16edb3f2bf474467710c5ee0d07a51c2b771d6a20712feb354e407ed`；
- 两次输出完全相等；
- 与 frozen proof 中记录的 digest 一致；
- 单次前后目标 canonical database physical SHA 不变；
- frozen proof SHA256 仍为 `cc5de889fff7a708afb000d4baae42cefed571cb2f0eb5fdd624f81676bf2b5d`。

因此签发没有重新生成或改写历史 proof，而是只消费其中已经冻结的 payload。

## Issued admission

- admission ID：`fin01-s4-t05-dell-task-claim-link-policy-fresh-exact-admission-r3`
- execution mode：`exact_live_s4_dell_task_claim_link_policy_r3`
- admission digest：`4be4fa99479da78547bfc9266c708478aa524d459db97c7341799b2724a7f29d`
- WorkUnit：`wu_p02_5_4e861814210bbc43c8632e22`
- Attempt：`attempt_fin01_ed9ba7af7a2805527b0d7cb1`
- ResearchRun：`research_run_fin01_8905466e65d6259e54d42f6c`
- explicit capability：`task_claim_link_policy_ref=fin01.s3.task_claim_link_policy:v1`

admission 文件逐字段等于 frozen proof 的 prospective payload；Pydantic schema、profile admissibility、canonical digest、runner load 和 executor factory 均通过。factory 验证没有触发 Provider callback。

## 未消费与只读证明

签发后只读检查确认：

- 新 WorkUnit、Attempt、ResearchRun 均不在 canonical snapshot；
- 两个历史失败 Run `research_run_fin01_2eced17671df87082b95db9a` 与 `research_run_fin01_9756044e7d7f23b3ff9fb395` 均仍存在；
- target object tree SHA256 仍为 `60305e957d0e6a2893015fa7fbf2399b4ae8633341acf10651ace7b9fef1ec1b`；
- target logical snapshot digest 仍为 `b63e5447fdf89bf9ccf9bba2b4b379c9ef033a63460459a10456334665359405`；
- issued=true，consumed=false，execution_started=false；
- model / Provider / network / source / external tool / new Run / business Artifact / target execution write 均为 0。

SQLite physical SHA 继续只作为单次验证前后不变检查，不作为跨 invocation 的业务 identity。

## 回归治理

新增 issuance contract suite，并把历史 proof 测试改为可识别“proof 已被后续签发消费，但 proof 文件本身仍保持冻结”的状态。若 admission 已存在，历史测试不再错误重跑要求 admission absent 的 pre-issuance generator，而是验证 issued payload 与 frozen payload 完全相等。

同时修正少量历史阶段测试：它们不再把全局 `next_action` 和持续增长的 canonical runtime 总计数当作历史 S3/S4 决策的不可变字段；历史 issuance/decision 自身的 authority、digest、trace 和 stop boundary 仍保持精确断言。这只是回归时序解耦，没有改变产品合同或重新进入旧序列。

验证结果：

- issuance + frozen-proof 专项：`11 passed`
- S4-T04/T05 相邻回归：`91 passed`
- ClaimFactLink、cross-Cell scoped identity、role mapping 与 TaskClaimLink compatibility：`115 passed`
- JSON / JSONL parse：通过
- Python compile：通过

## 单序列边界

本轮没有重入：

- deterministic locally assembled task identity；
- complete typed WWC failure taxonomy；
- cross-stage unified Claim/Task identity redesign。

这些事项继续按既有合同传递至 S4-T10→S5 或更后阶段。本轮也未授权 exact-live、retry/fallback/rerun、paired assessment、MU、NVDA、Human review、S5、release 或 production。

## 产物与下一步

- admission：`configs/releases/fin_ia_0_1_s4_t05_dell_task_claim_link_policy_fresh_exact_admission_r3.json`
- issuance：`configs/releases/fin_ia_0_1_s4_t05_task_claim_link_policy_fresh_exact_admission_issuance_v1_0.json`
- issuance SHA256：`74667c005dd2aeefc3b8a6d92368ed0631caacd3b7a516e8a40b21eb0a241b6a`
- verifier：`scripts/releases/issue_fin_ia_0_1_s4_t05_task_claim_link_policy_fresh_exact_admission.py`
- contract suite：`tests/contract/test_fin_0_1_s4_t05_task_claim_link_policy_fresh_exact_admission_issuance.py`

下一项仅为：

`S4-T05-DELL-TASK-CLAIM-LINK-POLICY-R3-EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-ASSESSMENT-AUTHORITY-DECISION`

下一项需独立授权。只有 exact-live 达到 coherent terminal success 并生成完整九 Artifact，才允许执行 paired assessment。
