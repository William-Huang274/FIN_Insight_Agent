# FIN 0.1 S4-T06：MU identity v2 replacement、fresh proof 与 R4 numeric L1 failure

日期：2026-07-29<br>
状态：R4 terminal failed；S4-T06 blocked；no R5

## 本轮授权与边界

用户授权按冻结顺序完成：

1. current-case-aware identity boundary v2 的唯一 zero-call replacement；
2. 独立 fresh-agent proof；
3. 全新 MU R4 admission；
4. 最多一次 R4 exact-live；
5. 仅当 L1 pass 且保留 Agent gain 时执行 paired assessment 与 owner acceptance；
6. 任一新 L1 立即停止，不进入 R5。

未授权 retry、fallback、replay、relaunch、微补丁、Provider hopping 或 T07。

## Zero-call replacement

新增合同：

- `fin01.s4.case_delivery_identity_current_case_aware_provider_boundary:v2`
- `fin01.s4.case_delivery_identity_registry:v1`

语义：

- exact current-case ticker 可在 Provider narrative 中作为非权威上下文出现；
- registry 中 registered nonlocal ticker 继续触发 typed L1 hard failure；
- title、workpaper、review、manifest、runtime identity 与最终 9-Artifact identity envelope 仍由本地确定性层拥有；
- v1 历史 admission/projection 与失败结果保持原语义。

验证：

- DELL/MU/NVDA 自然本案 ticker：每案 6 nodes / 12 callbacks / 12 captures / 9 Artifacts；
- Specialist、Research Lead、Writer、Verifier 四阶段 nonlocal mutation 均拒绝；
- 最终 delivery identity mutation 拒绝；
- canonical registered failure telemetry 不保存正文或 private reasoning；
- S4-T06 regression：`199 passed`。

## Independent fresh proof

proof generator 连续运行两次，每次使用独立 disposable Runtime clone，结果逐字段相同：

- target SQLite、object tree、logical snapshot 不变；
- model/provider/network/source/tool calls 全 0；
- MU exact input digest：`7887b5bb447fc6a844c410751f2038a04a1c0b04dbbe7e5bde41b040135a12e1`；
- prospective R4 admission digest：`a1e37a09d87250fc6c8cfd448cd3dabacea02a3041e68735448485257df4da04`；
- Lead v7、Specialist v7、numeric authority v1 与 identity boundary v2 均冻结。

## R4 preflight

- Project OS full-chain preflight：pass；
- runner zero-call preflight：pass；
- credential：presence-only，未输出或持久化；
- transport retry：0；
- budget：12 semantic/model/provider/network calls，USD 0.10；
- source network / external tools / business head writes：禁止；
- fresh WorkUnit / Attempt / ResearchRun：执行前均 absent。

首次 runner preflight 因 shell 未显式设置 `LLM_GATEWAY_TRANSPORT_RETRIES=0` fail-closed；没有调用。显式设置为 0 后通过，没有修改 admission 或 runtime。

## R4 exact-live

监督：

- supervision contract：v2；
- detached direct runner；
- parent timeout：无；
- monitor mutations / signals / retry / fallback / replay / relaunch：全 0；
- runner exit code：0；
- canonical terminal states：failed / failed / failed；
- orphaned run：false。

调用：

- provider/model：DeepSeek / `deepseek-v4-pro`；
- completed logical nodes：1；
- semantic/provider/network calls：4 / 4 / 4；
- receipts/captures/readbacks：4 / 4 / 4；
- input/output/total tokens：24,474 / 2,527 / 27,001；
- estimated cost：USD 0.01284468；
- 每次 transport attempts：1；
- 每次 finish reason：stop；
- Artifacts：0。

## First credible failure

- stage：`domain_specialist:value_and_profit_capture`
- segment：`facts_explanation_and_terminal`
- failure code：`s4_case_numeric_authority_provider_narrative_invalid`
- subtype：`provider_authored_numeric_token`
- field：`explanation_layer`
- failing item count：2
- acceptance layer：L1 hard integrity

Restricted telemetry 本身不保存 token 值或 narrative 正文；但本次运行另有四份受限 assistant final-output capture。2026-07-30 的零调用回放证明，`failing_item_count=2` 是两个叙事字符串命中，分别位于 `$.fact_layer[0].statement` 与 `$.explanation_layer[0]`，共同内容为报告期标签 `FQ3 2026`，不是两个财务金额或百分比。故“数字正误未知、模型 numeric narrative 不稳定”的旧解释由后续处置 supersede；R4 的 failed 三态、0 Artifact 和 no-R5 运行事实不变。

## 结论

- RC-P36-079：v2 fixture 与 live positive path 通过；R3 identity failure 未复发，第一 Specialist 完成。
- RC-P36-080：后续受限 capture 回放已更正为项目内 numeric classifier false positive；当前 broad digit regex 未区分报告期标签与 material financial value。runtime fix 仍未实现，因此 blocker 保持 open。
- RC-P36-067：numeric authority 已进入 live provider gate，但最终 local rendering 与 9-Artifact L1 未到达。
- RC-P36-068：provider identity v2 有正证据，但 Writer 与 final title/workpaper/review/manifest 未到达。
- paired assessment：不具备资格，未执行。
- owner acceptance：不具备资格，未执行。
- S4-T06：未通过。
- S4-T07：未进入。

下一项仅为：

该历史时点的下一项是：

`S4-T06-MU-R4-NUMERIC-NARRATIVE-L1-PROJECT-BLOCK-OR-SCOPE-REPLACEMENT-DECISION`

2026-07-30 已完成该零调用处置，当前下一项更新为：

`S4-T06-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-CLASSIFIER-MINIMUM-ZERO-CALL-IMPLEMENTATION`

该项必须是零调用项目级处置：阻断受影响 Agent delivery scope，或选择有界结构替换；不得自动进入 R5。
