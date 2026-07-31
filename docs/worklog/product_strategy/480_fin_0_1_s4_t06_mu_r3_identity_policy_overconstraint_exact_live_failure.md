# FIN 0.1 S4-T06 MU R3 identity policy overconstraint exact-live failure

日期：2026-07-29<br>
状态：fresh proof 与 admission 通过；R3 exact-live 首节点失败；paired/owner/T07 未执行

## 授权与执行顺序

用户授权连续执行 fresh-agent proof、全新 admission、MU exact-live、paired L1-L4、owner acceptance，并在满足门槛后关闭 T06/进入 T07。本轮遵守 success-only 条件：只有 exact-live coherent success 才允许后续 paired 与 owner write。

## Zero-call fresh proof

- 当前实现的 6 个冻结 SHA 全部重验一致。
- 同一 MU exact input 在 disposable clone 中两次 prepare 完全相同。
- 新 R3 WorkUnit/Attempt/Run 在目标 runtime 中均 absent。
- DELL/MU/NVDA 三案各自重算到 `6 nodes / 12 callbacks / 12 captures / 9 Artifacts`。
- missing marker、numeric projection、wrong title、nonlocal numeric、wrong review label、canonical numeric Fact 六类 mutation 全部被 L1 拒绝。
- prospective admission digest=`da4c91eb...32a5`，proof 阶段 model/provider/network/admission/canonical write=`0`。

## Admission 与 preflight

- R3 admission 已原样签发，safety pair 显式绑定。
- runner-load 通过，issued/consumed/execution=`true/false/false`。
- exact-live preflight 确认 credential presence、retry=0、`12/12/12 calls / 16800 output tokens / USD 0.10`，canonical counts 前后不变。

## Exact-live 终态

- supervision-v2 直接 runner 自行终态化，exit code=0。
- WorkUnit/Attempt/Run=`failed/failed/failed`，orphan=false，Artifact=0。
- 第一次 Demand Specialist segment 的 Provider 请求成功返回：`status=ok / finish_reason=stop`。
- calls=`1/1/1`，receipts/captures/readbacks=`1/1/1`。
- tokens=`3994/494/4488`，cost=`USD 0.00216717`。
- retry/fallback/replay/relaunch/rerun=`0/0/0/0/0`。
- typed failure=`s4_case_delivery_identity_provider_narrative_invalid`，subtype=`provider_authored_case_entity_token`。

## 根因判断

受限、只读、content-free 复核只统计身份 token：输出含正确本案 `MU` 四次，`DELL/NVDA` 均为零。因此没有观察到跨案例污染。

近因是模型在叙事中重复了正确 ticker，没有遵守“Provider 不得写任何 ticker”的刚性合同。最早可控项目根因是 `CaseDeliveryIdentityPolicy.provider_narrative_has_entity_token()` 把防跨案污染实现成对所有已知 ticker 的 blanket ban，连当前正确 ticker 也硬拒绝；正向 fake 又会清洗实体 token，未覆盖真实模型自然重复本案身份的路径。

这不是 credential、网络、transport、source pack、截断或 DeepSeek 普遍不能遵循 schema。它也没有到达 numeric final envelope，故不能据此宣称数值保护 live pass 或 fail。

## 停止与后续

按冻结 stop rule，本轮在首个新 L1 failure 处停止：

- 不执行 paired L1-L4；
- 不执行 owner acceptance；
- 不关闭 T06；
- 不进入 T07；
- 不启动 R4、微补丁、Provider hopping 或模型切换。

新增项目级 blocker：

`RC-P36-079-s4-t06-current-case-identity-token-policy-overconstraint-and-fixture-blind-spot`

下一项仅为零调用：

`S4-T06-MU-R3-CURRENT-CASE-IDENTITY-TOKEN-POLICY-OVERCONSTRAINT-AND-FIXTURE-BLIND-SPOT-PROGRAM-SCOPE-REPLACE-OR-BLOCK-DECISION`

## 结果物

- proof：`configs/releases/fin_ia_0_1_s4_t06_mu_mandatory_material_truth_identity_safety_closure_fresh_agent_proof_decision_v1_0.json`
- admission issuance：`configs/releases/fin_ia_0_1_s4_t06_mu_mandatory_material_truth_identity_safety_closure_fresh_exact_admission_issuance_v1_0.json`
- exact-live failure：`configs/releases/fin_ia_0_1_s4_t06_mu_mandatory_material_truth_identity_safety_closure_r3_exact_live_execution_failure_result_v1_0.json`
- model run ledger：`reports/model_runs/20260729_fin_ia_0_1_s4_t06_mu_deepseek_pro_r3_identity_policy_overconstraint_failure_r1.md`

## 收尾验证

- 新 R3 failure contract：`3 passed`。
- 完整当前 S4-T06 选择：`184 passed / 1771 deselected`。
- 首次完整回归的 21 个失败均为历史 next-action 或“最新 MU Run 必须仍为 R2 succeeded”断言；只增加 R3 disposition 合法后继和历史 Run 按存在性核验，没有改 runtime、schema、validator 或 Provider request。
- Python compile：pass。
- release JSON 与 Project OS JSONL parse：pass。
- `git diff --check`：pass，只有现有 CRLF normalization warnings。
- credential/plaintext secret 未写入新增 proof、issuance、result、worklog、model-run 或测试文件。
