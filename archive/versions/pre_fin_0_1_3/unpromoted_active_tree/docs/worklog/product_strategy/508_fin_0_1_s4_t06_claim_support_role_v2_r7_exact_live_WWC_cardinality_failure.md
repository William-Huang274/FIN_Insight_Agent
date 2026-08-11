# FIN 0.1 S4-T06 Claim support-role v2 R7 exact-live WWC cardinality failure

日期：2026-07-30

## 结论

唯一 R7 admission 已在 supervision-v2 下 exact-once 消费并终态失败。失败不是 DeepSeek 忽略 model-visible cardinality，而是项目本地 WWC assembler 把 Provider candidate 上限与最终 selected 上限混为一体。

- WorkUnit / Attempt / Run：`failed / failed / failed`
- completed nodes：`0`
- model / Provider / network：`3 / 3 / 3`
- receipts / capture-v2 / Artifacts：`3 / 3 / 0`
- input / output / total tokens：`13,108 / 1,120 / 14,228`
- cost：`USD 0.00667638`
- retry / fallback / replay / relaunch / rerun：`0 / 0 / 0 / 0 / 0`
- paired / owner / T07 / R8：`0 / 0 / 0 / 0`

## First credible failure

Stage：

`domain_specialist:demand_authenticity_and_sustainability:actionable_what_would_change_tasks`

Code：

`s4_compiled_wwc_atom_shape_invalid`

restricted capture-v2 的 exact request/output 对账结果：

1. assistant output 可解析为 native JSON；
2. 顶层键严格为 `program_cell_id` 与 `what_would_change_atoms`；
3. 6 个 atom 均具有预期九字段 shape；
4. model-visible `output_constraints.provider_candidate_maximum=6`；
5. Provider 正好返回 6 个 candidate；
6. executed local `_assemble_wwc` 却以 `fact_selected_maximum=3` 作为输入列表上限；
7. shape rejection 发生在本地 validity-aware selection 之前。

所以模型符合它看到的候选数量合同。最早错误是项目内：

`provider candidate maximum 6 != local accepted/final selected maximum 3`

同时当前 WWC path 缺少“先验证最多 6 个 candidate，再本地稳定筛选最多 3 个最终任务”的阶段分离。这是 RC-P36-083 的 live semantic-parity recurrence。

## 审计与安全

- 三份 model-visible request 与 final assistant output 均按 capture-v2 内容寻址保存；
- capture digest readback=`3/3`；
- credential/private reasoning/raw Provider response persisted=`0/0/0`；
- failed output promoted to Artifact=`false`；
- typed terminal result 已物化且 `runtime_materialization_findings=[]`；
- supervisor exit code=`0`，无 signal、retry 或 relaunch；
- final stderr digest 与 exit receipt 一致。

## 证据

- result：`configs/releases/fin_ia_0_1_s4_t06_mu_claim_support_role_v2_r7_exact_live_execution_failure_result_v1_0.json`
- result SHA256：`02bcc68fb93e51dfa62bacb889cd589734377e8c7baa3bf3cc6834c3ef328a18`
- test：`tests/contract/test_fin_0_1_s4_t06_mu_claim_support_role_v2_r7_exact_live_execution_failure_result.py`
- test SHA256：`ed719b4d1d8ebd8cbd7b8b42b44299c7ed7f7766994f2901e14a7d29216b2725`
- focused tests：`5 passed`
- runtime result：`.codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1/s4_t06_mu_claim_support_role_v2_r7_live_execution_result.json`
- runtime result SHA256：`c2cc409f8e4c249d160a189ee0996225b4be9ed63d788c9d892f053f3a112ff6`
- exit receipt：`.codex_runtime/fin01-s4-t06-mu-claim-support-role-v2-r7-supervision-r1/exit_receipt.json`
- next disposition Project OS preflight：`.codex_runtime/s4_t06_mu_r7_wwc_cardinality_failure_disposition_scope_preflight.json`
- next disposition preflight SHA256：`938480067ea4ca519279b64a4585b1994e505aacb21b8b00eade971540e60237`

## Postflight

- result focused tests：`5 passed`
- execution lifecycle authority/proof/issuance/result：`23 passed`
- current Claim/Canary/R7 chain：`55 passed`
- Project OS next disposition scope：`pass / open blockers 0`
- 旧 proof/authority/issuance tests 已改为 lifecycle-aware：执行前验证 identity absence，执行后验证同一 frozen identity 的 failed terminal lineage；未修改旧 proof、authority、admission、issuance 或 runtime result bytes
- JSON / JSONL parse：pass
- Python compile：pass
- refined secret-shape scan：0
- `git diff --check`：pass
- admission / issuance / execution authority SHA 保持不变
- 当前仓库仍为历史累计混合 worktree（status rows=`1058`，pre-existing staged paths=`799`）；本轮未 stage、commit 或 push，也未修改 staged set

## 停止与下一步

R7 已消费且不可重跑。按 authority，本轮没有 paired assessment、owner acceptance、T07 或 R8，也没有修改 Runtime。

下一项：

`S4-T06-MU-R7-FIRST-CREDIBLE-FAILURE-PROJECT-BLOCK-OR-DETERMINISTIC-PLANNER-SCOPE-DISPOSITION-DECISION`

该项必须是零调用项目级决策，只裁决 WWC surface 的确定性所有权与 candidate/selected cardinality 分层；不得直接补字段、重跑 R7 或扩大 T06。
