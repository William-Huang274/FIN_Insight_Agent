# 448｜FIN 0.1 S4-T06 入口 shared-runtime fresh engineering proof 与 Provider capability binding 决策

日期：2026-07-28

## 结论

本轮决定为 `block_before_canary`。

冻结实现的代码和 fixture 证据可独立复现，但当前 strict JSON Schema 请求不能按 OpenAI 官方文档的已支持子集完成 request-level capability binding。S4-T06 仍未进入，不执行 canary、不签 admission、不读取凭据、不进入 MU，也不允许第二个自动修复包。

机器决策工件 SHA-256：`84b1efd2ddd59daf8940beab713c1674df0f502ab75dd6c23b491351961a27f0`。

## 独立工程复核

- 实现工件 SHA-256：`7c4debbed32f952266110889fce69a4bf863daa750ba39c0baf7478471d175a3`；
- disposition SHA-256：`38aa09992a90b11092128e967ee3e7be591fe039baf75fe0eb025c84eef07489`；
- 冻结的 5 个代码/测试 binding 全部匹配；
- focused 独立运行两次：`18 passed in 22.29s`、`18 passed in 21.77s`；
- 组合回归：`52 passed in 90.81s`；
- 决策 contract：`3 passed in 2.11s`；
- 实现＋决策组合：`21 passed in 17.54s`；
- DELL/MU/NVDA schema 分别重算为：
  - DELL：`bb2962b...56f059`；
  - MU：`04d12c1f...690d4`；
  - NVDA：`25f104e2...563dc5`。

三案均满足 root/nested object 的 required 与 `additionalProperties:false`，并保留 `minItems/maxItems`。三案也都在同一路径包含：

`$.properties.fact_judgments.items.properties.counterevidence_aliases.uniqueItems`

## 官方能力核对

OpenAI Developer Docs MCP 在当前任务中未暴露，按技能要求尝试登记时因桌面包内 `codex.exe` 拒绝访问而失败；随后仅使用 OpenAI 官方域名。

官方当前模型解析结果为 `gpt-5.6-sol`。其模型页明确支持：

- `v1/responses`；
- `v1/chat/completions`；
- Structured Outputs。

Structured Outputs 指南明确给出 Responses 的 `text.format.type=json_schema + strict=true + schema`，要求所有 object 字段 required、所有 object 使用 `additionalProperties:false`；其列出的受支持 array 关键字为 `minItems` 与 `maxItems`，没有列出 `uniqueItems`。

因此可以冻结一个 prospective model-level candidate：

- provider：`openai`；
- base URL：`https://api.openai.com/v1`；
- model：`gpt-5.6-sol`；
- model ref：`openai:gpt-5.6-sol`；
- truth-kernel endpoint：`/responses`；
- remaining-node endpoint：`/chat/completions`。

但不能把它登记成 live capability binding：当前请求 schema 的官方兼容性未建立，credential/access 又按本轮边界未读取或探测。

## 根因与治理

新增 RC-P36-070：

`RC-P36-070-s4-t06-strict-schema-unsupported-uniqueItems`

这是项目拥有的 request-schema 合同缺口，不是模型不听指令、Provider 宕机或凭据故障。fixture fake 接受了本地 schema，但没有证明真实 strict endpoint 支持该关键词。

按已冻结的 anti-loop 规则，本轮不删除 `uniqueItems`、不增加一个补丁、不启动 canary、不换 Provider。当前门禁唯一下一项变为：

`S4-T06-ENTRY-SHARED-RUNTIME-BLOCKER-POST-PROOF-PROGRAM-SCOPE-REPLACE-OR-STOP-DECISION`

该项需要单独授权，只允许在“停止/保持阻断”与“以新的 program-level scope 明确替换合同”之间作一次决定，不能把局部修复伪装成当前 bundle 的延续。

## 未执行

actual model/provider/execution network/source/tool/credential probe/admission/WorkUnit/Attempt/ResearchRun/business Artifact/paired/Human 均为 0。DELL R12 仍禁止；S4-T05 仍 blocked/not passed/not owner accepted；S4-T06 未进入。
