# FIN 0.1 S4-T06 R7 WWC candidate/local-selection scope disposition

日期：2026-07-30

## 结论

R7 的第一可信失败已完成零调用项目级处置。选择：

`最多 6 个 Provider candidate -> 全量逐项验证 -> 本地确定性稳定选择最多 3 个 -> 本地渲染最终 WWC`

没有选择全面阻断 Provider-authored WWC surface。原因是当前 WWC wire 已经只允许 request-local Claim/Authority/Date aliases 与有限枚举，重要数值、日期、identity、最终 clauses 和 lineage 仍由本地系统拥有。当前最早故障只是 candidate-generation 与 final-selection 的 cardinality 被混用；删除整个表面会损失仍有价值的 claim-authority-trigger 判断，并把一个局部合同错误扩大成 T06 权限重构。

## 零调用审计

当前同一 compiled contract 的三条路径表现为：

- Fact：接受 `1..6` candidate，逐项验证后稳定选最多 3；
- Claim：接受 `1..6` candidate，逐项验证后稳定选最多 2；
- WWC：错误地在 selection 前用 `fact_selected_maximum=3` 拒绝输入。

R7 的 Provider 返回正好 6 个 candidate，符合 model-visible `provider_candidate_maximum=6`；因此不成立模型 cardinality 违约。transport、JSON、finish、截断、credential、unknown alias 或 cross-case fault 也未成立。

## 冻结的最小实现合同

下一实现只能有一个共享、provider-neutral 的零调用包：

1. Provider candidate 数量为 `1..6`；
2. selection 前验证所有 atom 的 exact shape、Claim/Authority/Date alias、枚举、duplicate 与 temporal authority；
3. 任一无效 candidate 直接 typed fail，不允许静默丢弃；
4. 通过验证后按冻结 tuple 稳定排序，最终最多选择 3 个；
5. task ID、Claim/Authority refs、日期、time window、decision rule、transition、stop text 与 lineage 全部本地生成；
6. prompt、wire schema、system instruction、validator、selector、renderer、fake、mutation、capacity 与 typed failure 从同一合同投影；
7. 覆盖 candidate count `0/1/3/6/7`、六项中一项无效、duplicate、cross-case、date alias、permutation stability，以及 DELL/MU/NVDA `6/12/12/9` full-fake；
8. 实现后必须另做独立 fresh-agent proof。

不允许把最终上限提高到 6，不允许取 Provider 前三项，不允许静默丢无效项，不允许削弱数值/日期/identity hard gate。

## 权限与停止边界

- 本轮 runtime code change=`0`
- model / Provider / execution network / source network=`0/0/0/0`
- admission / WorkUnit / Attempt / Run / Artifact=`0/0/0/0/0`
- paired / owner / T07=`0/0/0`
- R7 保持 immutable terminal failed，禁止 retry/replay/reclassification
- remaining formal MU exact-live ceiling=`0`
- R8 或 replacement live 未授权

本决策没有实现修复，也没有给未来 live 自动开绿灯。实现和独立 fresh proof 完成后，是否存在新的 replacement exact-live 必须再做项目级权限判断。

## 证据

- decision：`configs/releases/fin_ia_0_1_s4_t06_mu_r7_wwc_provider_candidate_local_selection_scope_disposition_v1_0.json`
- decision SHA256：`71dcead5069b8c8bb2a66e2806a26ddd242ddbc71909aa7cf0570b33019d0bf5`
- decision test：`tests/contract/test_fin_0_1_s4_t06_mu_r7_wwc_provider_candidate_local_selection_scope_disposition.py`
- source result：`configs/releases/fin_ia_0_1_s4_t06_mu_claim_support_role_v2_r7_exact_live_execution_failure_result_v1_0.json`
- source result SHA256：`02bcc68fb93e51dfa62bacb889cd589734377e8c7baa3bf3cc6834c3ef328a18`
- code audit：`apps/workbench/backend/application/deterministic_judgment_atom_contract.py`
- disposition preflight：`.codex_runtime/s4_t06_mu_r7_wwc_cardinality_failure_disposition_scope_preflight.json`
- preflight SHA256：`938480067ea4ca519279b64a4585b1994e505aacb21b8b00eade971540e60237`

## 验证

- disposition + immutable R7 result：`10 passed`
- current Claim / Canary / R7 / disposition chain：`60 passed`
- JSON / JSONL parse：pass
- touched Python compile：pass
- refined secret-shape scan：0
- `git diff --check`：pass
- DeepSeek / Provider / execution network job：未运行（按处置边界故意为 0）
- Git stage / commit / push：未执行；保留用户现有 mixed worktree 与 staged set

## 下一项

`S4-T06-MU-WWC-PROVIDER-CANDIDATE-VALIDATION-AND-DETERMINISTIC-FINAL-SELECTION-MINIMUM-ZERO-CALL-IMPLEMENTATION`

下一项尚未自动授权；不得在实现轮调用 DeepSeek、签发 admission、执行 R8、paired、owner 或 T07。
