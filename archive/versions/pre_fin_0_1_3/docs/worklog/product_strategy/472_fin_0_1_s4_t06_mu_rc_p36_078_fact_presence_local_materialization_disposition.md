# FIN 0.1 S4-T06 MU RC-P36-078 本地确定性摘要处置

日期：2026-07-29<br>
状态：零调用 root-cause/scope disposition 完成；实现未授权<br>
当前下一项：`S4-T06-MU-RESEARCH-LEAD-CONFLICT-FACT-PRESENCE-LOCAL-DETERMINISTIC-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION`

## 问题

MU R1 的 9 个 Specialist segment 均完成，Research Lead Provider 调用也以 `ok/stop` 返回，但本地 `closed_research_lead_output:v3` 因 `conflict_adjudications.fact_presence_summary` 与 involved Claim Cards 的直接 `support_fact_ids` 推导结果不一致而 fail-closed。

本轮只被授权做零调用根因或范围处置；没有授权修改 runtime、签 admission、调用 DeepSeek、执行 paired assessment 或进入 T07。

## 最早 owned fault

代码审计确认当前 Research Lead-v5 存在双 owner：

1. Provider required-output schema 要求输出 `fact_presence_summary`；
2. v5 本地 row assembly 原样保留 Provider 值；
3. 本地已有 `_expected_conflict_fact_presence_summary()`，能从 involved Claim Cards 的直接 `support_fact_ids` 唯一生成 `facts_present / no_facts_present / mixed_fact_presence`；
4. v5 semantic validator 和 canonical output validator 都会重新计算并硬比较。

历史 RC-P36-041 修复的是 conflict-local 作用域错误，并建立了正确 truth table；但当时仍保留 Provider 生成责任。本轮 RC-P36-078 是同一字段的 ownership 缺口在 MU 上复发，不重新打开 RC-P36-041 的作用域语义结论。

## 决策

选择 `fin01.s3.research_lead.conflict_fact_presence_local_materialization:v1`：

- 模型继续选择 `involved_claim_ids` aliases，并负责 conflict 的判断叙事；
- Provider wire 不再要求且禁止输出 `fact_presence_summary`；
- 本地在 aliases 完成合法性校验和 Claim Card 解析后，用现有 direct-support helper 唯一生成摘要；
- canonical output-v4 继续要求该字段；
- semantic/canonical validators 继续 fail-closed；
- 不接受 Provider 值后静默覆盖，因为那会隐藏冲突，而不是消除双 owner。

未来 transport 选择 `fin01.s3.bounded_agent.research_lead_owner_grade:v7`，明确以 Lead-v5 wire 为基线，只增加本地摘要 materialization。Lead-v6 gap-atom projection 不并入本轮，Specialist、Writer、Verifier、金融证据、Graph、method、provider、model 和预算均不改变。

## 拒绝方案

- 继续 Provider 生成＋本地硬比较：会继续用付费全链发现确定性错误；
- 加强 Prompt 或扩大 token：现有 Prompt 已包含完整 truth table，且本轮不是容量问题；
- 删除、忽略或把摘要降为 quality finding：会削弱 L1 conflict auditability；
- 接收后静默修复 Provider 值：会掩盖模型合同不一致；
- 直接停止/替换 T06：暂不选择，因为存在一个不扩展研究范围的有界本地修复。

## 实现边界

只允许一个另行授权的最小零调用 implementation bundle：

- v7 wire schema 删除并禁止 Provider `fact_presence_summary`；
- request builder 必须由同一 versioned ownership policy 编译，不能用脆弱的 Prompt 字符串覆盖；
- aliases 必须先通过 nonempty、unique、kind、scope 和 existence 校验；
- 本地 materialization 后继续运行 v3 semantic 与 canonical validators；
- 保持 v1–v6 行为和 consumed R1 immutable；
- 通过 all/none/some、无关 facts、invalid aliases、historical parity 和 MU `6 nodes / 12 callbacks / 9 Artifacts` full-fake。

若一个 bundle 不能通过，T06 保持 blocked，转入独立 stop/scope-replace 决策；不得自动追加第二实现包。

## 非膨胀边界

- 本轮 model/provider/network/source/tool calls=`0/0/0/0/0`；
- admission issuance/consumption=`0/0`；
- canonical Run/Artifact=`0/0`；
- paired/Human=`0/0`；
- MU R1、历史 admissions 和 terminal truth 未改写；
- 未恢复 strict-schema transport；
- 未进入 T07–T10 或 S5。

## 证据与验证

- 决策：`configs/releases/fin_ia_0_1_s4_t06_mu_research_lead_fact_presence_summary_mismatch_root_cause_scope_disposition_v1_0.json`
- 决策 SHA256：`cb7e5210909f69c34038ba41a0ee4f668bd94d5d09e26fc8f07e8c3a9945b8f4`
- MU R1 failure result SHA256：`ac048a27964330f776e0452f0fe7fff3d064805b5e6fadccb695d2460ee5a930`
- 历史 RC-P36-041 decision SHA256：`2e65f783258e4be353d154c1cd61445f1b9385434ed2e5911ae77551f0c6d57b`
- runtime owner SHA256：`6dcd64f18c695e8f27173ba4d0e61f51223efb24de62d82faada16e754af3890`
- focused/current：`24 passed`
- S4-T06：`139 passed`
- 下一实现范围 Project OS preflight：`pass / open blockers 0`

本 worklog 记录的是决策，不是实现或 live proof。
