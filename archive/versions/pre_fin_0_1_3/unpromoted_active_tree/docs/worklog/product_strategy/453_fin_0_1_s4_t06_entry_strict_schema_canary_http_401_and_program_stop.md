# 453｜FIN 0.1 S4-T06 入口 strict-schema canary HTTP 401 与 program stop

日期：2026-07-28

## 结论

已按授权 exact-once 消费 `fin01-s4-t06-entry-openai-strict-schema-dell-demand-r1`。唯一请求在 Provider 身份认证阶段返回 `HTTP 401`，因此 terminal stop；没有 retry、换 Key、换 Provider、重新发起或进入完整链。

这不是模型输出失败，也不是 strict schema 已被 Provider 拒绝。请求没有进入 generation，故本轮不能评价 `gpt-5.6-sol` 的 schema 遵循、endpoint 对 exact wire 的接受、Provider atoms 或本地 semantic validator。

## 执行前证明

- authority SHA-256：`7789999fb9e00f353a00337ece72361d0a30fcdec5d239068e1695da83b79446`；
- result 在调用前不存在，canary ID 未消费；
- Project OS exact scope：pass，open full-chain blocker=`0`；
- `LLM_GATEWAY_TRANSPORT_RETRIES=0`；
- credential 仅确认存在，值未输出或持久化；
- input/request/schema/text/system/user/template 七项 digest 全部与 authority 一致；
- fake Provider 全链仍为 12 captures / 9 Artifacts，strict wire 与 local validator 通过；
- canary runner、authority 与 replacement 聚焦回归：`14 passed`。

terminal result、program disposition、backlog 单向迁移与 no-replay closeout 加入后，最终聚焦回归为 `17 passed`。

## 唯一 live 结果

- semantic/model/provider/network/transport attempts：`1/1/1/1`；
- terminal：`HTTP 401 / provider_error / terminal_failed_no_retry`；
- input/output/total tokens：`0/0/0`；
- estimated cost：USD `0.0`；
- retry/fallback/provider hopping/replay/relaunch/rerun：全部 `0`；
- source/tool/chat/WorkUnit/Attempt/Run/business Artifact：全部 `0`；
- strict parse/local validation：均未到达；
- raw response、Provider output、reasoning、credential、headers、stack：均未持久化。

脱敏结果：

`configs/releases/fin_ia_0_1_s4_t06_entry_shared_runtime_blocker_single_node_strict_schema_canary_exact_once_execution_result_v1_0.json`

SHA-256：

`96a5ee24b824bbdd392c735827d2103bb2de118b7535a63009bb9e5d28ae0a0e`

## 根因边界

可确认的是：本次复用的 `OPENAI_API_KEY` 未通过身份认证。由于 gateway 按既定安全合同只保留 HTTP 状态码，不能再区分 key 无效、过期、撤销、项目不匹配或其他 401 子类；也不能把它归因于模型能力。

因此新增外部边界 RC-P36-071。RC-P36-070 的 replacement static/fixture 证明仍有效，但 live endpoint evidence 未取得；RC-P36-067 的 semantic requalification 继续等待。RC-P36-069 保持关闭。

## Program disposition

按 anti-loop 纪律：

- consumed canary 不可重放；
- 不自动创建、替换或轮换 Key；
- 不自动签发第二 canary；
- 不修改 schema、Prompt 或 validator；
- 不 provider hopping；
- 不进入 MU T06；
- 不创建 DELL R12。

T05 仍 blocked/not passed/not owner accepted，DELL R2 未证明，T06 未进入，S5/release/production 继续 blocked。

下一项：

`S4-T06-ENTRY-OPENAI-CREDENTIAL-REQUALIFICATION-AUTHORITY-DECISION`

该项尚未授权。它只决定复用已更新凭据或安全创建新凭据；任何未来 canary 都必须使用新 ID、新 authority 和新 result ref，不能重用本轮 canary。

## Git

工作树在本轮前已有大量 mixed staged/unstaged/untracked 历史变更。本轮保留这些状态，不 stage、不 commit。
