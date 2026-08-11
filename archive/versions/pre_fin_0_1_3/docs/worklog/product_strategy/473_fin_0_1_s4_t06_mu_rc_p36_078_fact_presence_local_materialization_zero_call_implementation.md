# FIN 0.1 S4-T06 MU RC-P36-078 本地摘要零调用实现

日期：2026-07-29<br>
状态：最小零调用实现通过；fresh-agent proof 待单独授权<br>
当前下一项：`S4-T06-MU-RESEARCH-LEAD-CONFLICT-FACT-PRESENCE-LOCAL-MATERIALIZATION-FRESH-AGENT-PROOF-DECISION`

## 结果

唯一获准的 RC-P36-078 implementation bundle 已消费并通过。新增 Research Lead-v7：

- 基线严格为 Lead-v5；
- Provider 继续选择 involved Claim aliases、terminal state、resolution status 和 conflict narrative；
- Provider schema 删除并禁止 `fact_presence_summary`；
- 本地先验证 alias 的非空、唯一、大小写精确、Claim kind 和 scoped-surface membership；
- 再只根据 involved Claim Cards 的直接 `support_fact_ids` 生成 `facts_present / no_facts_present / mixed_fact_presence`；
- output-v4 canonical field、v3 semantic validator 与 canonical validator继续 fail-closed；
- Provider 若越权回传 runtime-owned 字段，按 shape error 硬失败，不做静默覆盖。

版本化 owner 为：

- policy：`fin01.s3.research_lead.conflict_fact_presence_local_materialization:v1`
- transport：`fin01.s3.bounded_agent.research_lead_owner_grade:v7`

Lead-v6 gap atom 没有并入 v7；Specialist、Writer、Verifier、金融证据、Graph、method、DeepSeek Pro 和预算均未改变。

## 验证

定向验证覆盖：

- involved Claims 全部有 direct Fact → `facts_present`
- 全部无 direct Fact、但 Specialist 仍存在无关 facts → `no_facts_present`
- 部分有 direct Fact → `mixed_fact_presence`
- unknown alias、wrong-kind alias、duplicate alias 均在 materialization 前硬失败
- Provider 注入 runtime-owned summary 按 item-schema 硬失败
- 重复本地 assembly digest 完全一致
- 编译 v7 前后 v5/v6 request digest 不变

MU 使用 R1 冻结的真实 source-grounded exact input（digest `7887b5bb...12e1`）完成完整 fake 链：

- 6 logical nodes
- 12 Provider callbacks
- 12 restricted captures
- 9 logical Artifacts
- 0 recoverable protocol finding
- canonical conflict summary=`facts_present`
- Provider request schema 不含 `fact_presence_summary`

测试结果：

- focused implementation：`11 passed`
- v3/v5/v6/disposition/v7 adjacent：`65 passed`
- 全部 S4-T06 contract：`150 passed`
- Python compile：pass
- Ruff 未安装，因此未执行

## 历史与范围

MU R1 保持 immutable terminal failure；没有修改 admission、capture、Run、Artifact 或 failure truth。旧 exact-code binding 通过新的 implementation supersession 解析，历史 JSON 没有被改写。

本轮实际：

- model/provider/network/source/tool calls=`0/0/0/0/0`
- admission issuance/consumption=`0/0`
- WorkUnit/Attempt/ResearchRun/business Artifact=`0/0/0/0`
- paired/Human=`0/0`

RC-P36-078 当前只关闭到“实现与零调用 fixture proof 完成”；尚未完成 fresh-agent proof、未签新 admission、未执行 MU R2、未做 paired assessment 或 owner acceptance，也未进入 T07 或 strict-schema 轨道。

## 证据

- source decision：`configs/releases/fin_ia_0_1_s4_t06_mu_research_lead_fact_presence_summary_mismatch_root_cause_scope_disposition_v1_0.json`
- implementation：`configs/releases/fin_ia_0_1_s4_t06_mu_research_lead_fact_presence_local_materialization_minimum_zero_call_implementation_v1_0.json`
- implementation SHA256：`be1538bf3a867a5df5ef3d01727d9d1f15c4eba6c70aed526545989a4b9a7c3f`
- focused test：`tests/contract/test_fin_0_1_s4_t06_mu_research_lead_fact_presence_local_materialization_zero_call_implementation.py`

下一步只能先做独立 zero-call fresh-agent proof decision；它通过后，仍需分别获得新 admission 与 exact-live authority，不能直接复用已消费的 MU R1。
