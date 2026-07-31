# FIN 0.1 S4-T06 changed-contract 三家族 canary authority

日期：2026-07-30

## 结论

`S4-T06-MU-CHANGED-CONTRACT-FAMILY-SINGLE-NODE-NATURAL-OUTPUT-CANARIES-AUTHORITY-DECISION` 已通过。

本项只冻结未来 exact-once canary 的请求、预算、capture 和停止合同，没有读取凭据或调用 DeepSeek。三个家族按顺序运行，但 Claim 与 WWC 使用本地确定性 seed，不消费前一个 canary 的自然输出，因此结果可独立归因。

## 冻结请求

- Fact：request SHA=`f96285fd64912b39b57e7f3c104186e2941fd0e61cbcf40a0888fb4591c404e1`，max output=`1600`
- Claim/selection：request SHA=`405738388536cba288ddd46a3af5b51952bcc5f35adb76cc0b9241b4cc0cc24f`，max output=`1200`
- WWC：request SHA=`b643c574623d1ce4dfe4d0815d3f389b5b9ec0b8bf226a91e13c03818dc48f26`，max output=`1400`
- Provider：`deepseek / deepseek-v4-pro / https://api.deepseek.com/beta`
- Case/Cell：`MU / demand_authenticity_and_sustainability`

## 硬预算与停止

- 总上限：`3 model / 3 Provider / 3 network / 4200 output tokens / USD 0.03 / 360 sec`
- 每调用 transport attempt=`1`
- retry/fallback/replay/relaunch/provider hopping=`0`
- canonical WorkUnit/Attempt/Run 与业务 Artifact 写入=`0`
- 首个可信失败终止剩余调用
- 禁止逐字段补丁、prompt retry、失败后 full-chain 或 R7
- 任意结果之后必须单独做零调用 disposition

## 审计留存

capture-v2 必须在本地校验前原子保存 exact model-visible request 与 final assistant output，并保留 allowlisted inference arguments、usage、digest 与安全索引。凭据、Authorization/header、Cookie、Provider 私有推理和 raw Provider envelope不保存。失败输出只用于 restricted audit，不能晋升、重放或成为金融事实。

## 验证

authority artifact：

- `configs/releases/fin_ia_0_1_s4_t06_mu_changed_contract_family_single_node_natural_output_canaries_authority_decision_v1_0.json`
- SHA256=`e6f10a50d796d22bf03c48012442dbae1196be58984159cd4ef194053f124498`

合同测试：

- `tests/contract/test_fin_0_1_s4_t06_mu_changed_contract_family_single_node_canaries_authority_decision.py`
- SHA256=`60a67e45ea3ba84b09d8a7329458b67ee257dba09e491c512e8756212fb7c2b2`
- authority + fresh proof + implementation + disposition：`24 passed`
- next exact-once execution scope Project OS postflight：`pass / open blockers 0`
- postflight：`.codex_runtime/s4_t06_mu_changed_family_canary_execution_authority_postflight.json`
- postflight SHA256=`bfb8a827111a280826f6e712363efa8a235432c2696bd205f734672ea43f62a7`

本轮 credential read/probe、model/provider/network/canary/admission/exact-live/Artifact/paired/owner/T07 均为 0。T06 仍 blocked。

Git 仍位于 `codex/layered-data-source-expansion`，相对远端 ahead 5。工作树存在大量历史 staged、unstaged 与 untracked 混合变更；本项不暂存、不提交、不推送，避免混入用户既有工作。

## 下一项

`S4-T06-MU-CHANGED-CONTRACT-FAMILY-SINGLE-NODE-NATURAL-OUTPUT-CANARIES-EXACT-ONCE-EXECUTION`

future exact-once canary execution 已获授权。全部通过也只进入独立零调用 post-result disposition；R7 admission 与 formal exact-live 仍需各自独立权限步骤。
