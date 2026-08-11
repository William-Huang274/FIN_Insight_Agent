# 457｜FIN 0.1 S4-T06 入口 credential-requalified strict-schema canary HTTP 429

日期：2026-07-28

> 后续更正：用户于同日澄清目标 Provider 是自建 Sub2API，而本轮 authority、runner 与 result 全部硬绑定 `https://api.openai.com/v1`。因此本文件中的 HTTP 429 仅作为官方 OpenAI 错误路由的历史事实，不再作为目标 Sub2API 的 rate/quota blocker。当前解释与下一行动以 `458_fin_0_1_s4_t06_entry_sub2api_route_correction_and_http429_reclassification.md` 为准。

## 结论

用户以“继续”消费已签发的 fresh canary：

`fin01-s4-t06-entry-openai-strict-schema-dell-demand-credential-requalified-r1`

执行前 Project OS、authority/runner/request digest、credential presence、retry=0、fresh result absent 和 fake wire/local validator 均通过。唯一 `/responses` 请求到达 OpenAI 后返回 HTTP 429，并在 generation 前终止。

本次不是 authentication 失败：此前 metadata probe 已证明新凭据认证和 `gpt-5.6-sol` 可见性。它也不是 schema rejection、模型输出不遵循或 local validator 失败，因为 generation、strict parse 和 local validator 均未到达。

## 实际计数

- semantic/model/provider/network/transport：`1/1/1/1/1`；
- input/output/total tokens：`0/0/0`；
- estimated cost：USD 0；
- retry/fallback/provider hopping/replay/relaunch/rerun：全部 0；
- WorkUnit/Attempt/Run/business Artifact：全部 0；
- latency：3536 ms；
- raw response/output/reasoning/credential/headers/stack：均未持久化。

fresh canary 已 consumed，不可重放。

## HTTP 429 分类

脱敏结果只保留 `HTTP 429`，没有保存 provider error code/message，因此不能可靠区分：

1. ordinary rate limit；
2. insufficient quota / credits exhausted；
3. project 或 organization spend/usage limit。

登记外部边界 RC-P36-072。不能因为是 429 就自动增加 credits，也不能按普通 rate limit 自动重试。

## 阶段边界

- RC-P36-071：closed，凭据认证与模型可见性保持有效；
- RC-P36-070：static/fixture/documented request proof 保持，但 live schema endpoint 仍未评价；
- RC-P36-072：open，HTTP 429 subtype unknown；
- T05：blocked/not owner accepted；
- DELL R2：未证明；
- T06：尚未进入；
- DELL R12、第三 canary、MU、S5/release/production：均未授权。

下一项需要独立授权，且必须是零调用 program disposition：

`S4-T06-ENTRY-OPENAI-HTTP-429-RATE-OR-QUOTA-PROGRAM-DISPOSITION-DECISION`

## 证据

- result：`configs/releases/fin_ia_0_1_s4_t06_entry_openai_credential_requalified_fresh_strict_schema_canary_exact_once_execution_result_v1_0.json`；
- result SHA256：`22cc6a236cda8a81e09f8283e266c7ec0fcf0135fb8417a57f876407474da27d`；
- disposition：`configs/releases/fin_ia_0_1_s4_t06_entry_openai_credential_requalified_strict_schema_canary_http_429_program_disposition_v1_0.json`。
- disposition SHA256：`e19572330af5bc8801202172b8639b46322c50c3d9a652340aa6129cb3e24ccd`。

## 零调用收尾验证

- HTTP 429 result、program disposition、历史 transition 合同：`68 passed`；
- 当前重点 closeout 子集：`24 passed`；
- Project OS 下一 program-disposition exact scope：`pass / open blocker=0`；
- JSON/JSONL parse 与 duplicate-key 检查：pass；
- Python compile：pass；
- 新增 closeout 证据 secret-pattern scan：pass；
- 未发起第二次 Provider、模型或网络请求。

## Git

工作树已有大量 mixed staged/unstaged/untracked 历史变更。本轮仅追加脱敏结果 closeout、模型运行记录和状态迁移，不清理、不 stage、不 commit；`.env` 保持 ignored/untracked。
