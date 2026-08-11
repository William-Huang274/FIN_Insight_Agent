# FIN 0.1 S4-T06 MU RC-P36-078 fresh-agent proof

日期：2026-07-29<br>
状态：独立零调用 fresh proof 通过；R2 admission 签发待单独授权<br>
当前下一项：`S4-T06-MU-RESEARCH-LEAD-CONFLICT-FACT-PRESENCE-LOCAL-MATERIALIZATION-FRESH-EXACT-ADMISSION-ISSUANCE-DECISION`

## 问题与边界

上一项只证明 Lead-v7 的本地 `fact_presence_summary` ownership 在 fixture 与 MU full-fake 中成立，尚未证明当前 canonical Case、当前代码和一个未复用 execution identity 能稳定生成同一份 exact admission。本轮只做 fresh-agent proof，不允许 admission issuance、消费、DeepSeek 调用、exact-live、paired assessment、T07 或 strict-schema transport。

## 完成内容

新增独立 generator：

- `scripts/releases/prepare_fin_ia_0_1_s4_t06_mu_research_lead_fact_presence_local_materialization_fresh_proof.py`

generator 每次：

1. 重算 implementation SHA 和 4 个 exact code bindings；
2. 验证 Lead-v5 历史行为与 Lead-v7 local-materialization policy；
3. 复制当前 runtime 到 disposable clone；
4. 对同一 MU source-grounded Case/DecisionSurface 和全新 R2 identity 连续 prepare 两次；
5. 验证 clone execution counts 不变；
6. 从已消费 R1 admission 构造只改变 admission identity、execution mode 与 Lead-v7 binding 的 prospective R2 admission；
7. 构造 executor，但 Provider callback 必须保持 0；
8. 验证目标 SQLite、object tree 与 logical snapshot 前后不变。

`build_decision()` 完整执行上述 proof 两次，并要求两个输出逐字段一致。

## 冻结结果

- fresh WorkUnit：`wu_p02_5_43322e55457b647277d2297a`
- fresh Attempt：`attempt_fin01_217f2f2aaaa051080a540f2a`
- fresh ResearchRun：`research_run_fin01_1920b03b8205e9861dfb5676`
- input digest：`7887b5bb447fc6a844c410751f2038a04a1c0b04dbbe7e5bde41b040135a12e1`
- preparation digest：`0c4a7979e7b8d1fa38d1f11945684a20ed68fe3b8750f857fd8ac2dad0f6b159`
- prospective admission digest：`55fb08cac25b3a03109b13ae645d858b90b2074873f5355e6ed47ac93c6cd65c`
- proof artifact：`configs/releases/fin_ia_0_1_s4_t06_mu_research_lead_fact_presence_local_materialization_fresh_agent_proof_decision_v1_0.json`
- proof SHA256：`25178880022a502fad3e368033f009c852f7e503d032365e5c8b7a08f46f30f5`

prospective admission 文件没有创建。R1 failed WorkUnit/Attempt/Run 保持存在且未复用，R1 failure truth 没有重分类。

## 验证

- focused fresh proof：`6 passed`
- 完整 S4-T06：`156 passed`
- 两次完整独立 proof：输出一致
- target SQLite/object/logical state：全部 unchanged
- 下一 admission issuance scope Project OS preflight：`pass / open blockers 0`
- preflight ref：`.codex_runtime/s4_t06_mu_fact_presence_local_materialization_fresh_exact_admission_issuance_project_os_preflight.json`
- model/provider/network/source/tool：`0/0/0/0/0`
- admission issued/consumed：`0/0`
- target canonical/object writes：`0/0`
- paired/Human：`0/0`

第一次完整 S4-T06 回归出现 15 个历史 next-action compatibility 失败；这些测试只允许推进到旧 DeepSeek preparation。修复仅将新的 fresh R2 admission issuance decision 注册为合法后继，没有修改语义校验、L1 hard gate、Provider schema 或运行时行为。重跑后 `156 passed`。

## 后续与安全

下一步必须是独立 admission issuance decision，并且只能原样物化 proof 中的 payload。该动作仍不能消费 admission 或执行 exact-live。若后续 exact-live 成功，才可生成 9 Artifacts 并进入 success-only paired assessment；若出现首个可信 L1 failure，应停止并做范围处置，不能自动新增第二个修复包或 R3。
