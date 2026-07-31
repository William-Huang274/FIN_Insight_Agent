# FIN 0.1 S2-T03 原生 JSON Schema 精确 live admission 决策

时间：2026-07-20

## 结论

`gpt-5.6-sol` 已通过当前 OpenAI project 的只读 Models API 可见性检查，选为下一次原生 JSON Schema live validation 的 exact model candidate；因此没有继续探测 GPT-5.5。本轮独立复核结论仍为 `changes_required_before_admission_issuance`：没有签发 admission，也没有执行推理。

## 凭据与调用边界

用户通过安全的平台流程创建新 key，并明确同意保存为仓库根目录 `.env` 中的 `OPENAI_API_KEY`。验证确认 `.env` 被 Git ignore、未被跟踪且未被暂存；密钥明文没有进入代码、合同、日志或命令输出。此前在聊天中粘贴的旧 key 未被使用。

本轮只发生一次 `GET /v1/models/gpt-5.6-sol` 元数据调用，用于核验当前 project 的模型可见性；结果为可用。模型推理/生成、execution network、external tool、新 admission 和 actual execution 均为 `0`。

确定性验证结果：S2-T01/T03 focused contracts `63 passed in 11.33s`，Project OS preflight `6 passed in 2.29s`，JSON/JSONL parse 与 `git diff --check` 通过。

## 候选绑定与预算

候选 exact binding 为 OpenAI Responses API、`openai:gpt-5.6-sol`、`https://api.openai.com/v1`、`fin01.bounded_agent.native_json_schema_response:v1` 与 closed v4 Specialist output contract。按官方公开价格，输入/缓存输入/输出分别为 `$5/$0.5/$30` 每百万 tokens；沿用 Specialist/Writer/Verifier `1600/1000/900` 的输出上限时，纯输出成本上界为 `$0.105`，建议总成本上限 `$0.25`。reasoning effort 暂定 `medium`。

以上身份、预算和 reasoning 仍是不可消费的 provisional candidate，不是 admission。它们必须先进入 admission digest，才能获得签发资格。

## 独立复核发现

当前 live runner 仍有两处 DeepSeek 硬编码：preflight 只接受 `deepseek-v4-pro` 与 beta base URL；应用工厂固定构造没有 native adapter 的 `DeepSeekBoundedAgentExecutor()`。同时，`BoundedAgentAdmission` 没有 `specialist_transport_ref` 或 `reasoning_effort` 字段；新 native adapter 目前只在测试里通过显式注入得到 fixture proof。

因此现在签发 OpenAI admission 会出现两种坏结果之一：在 provider 调用前被 runner 拒绝，或者由 admission digest 之外的代码选择 transport/reasoning。两者都不符合 exact admission 治理，所以本轮没有为了“向前一步”而签发不可安全执行的 admission。

## 下一项

下一项冻结为 `S2-T03-NATIVE-JSON-SCHEMA-ADMISSION-BINDING-AND-RUNNER-WIRING-REPAIR`，只允许零调用、确定性修复：以向后兼容方式把 transport 与 reasoning 纳入 exact admission；让 preflight/factory 根据精确绑定选择 native adapter；证明历史 v1-v4/r2 digest 不变、retry=0、默认应用无静默切换。该修复尚未获得本轮授权。

完成修复后，签发新 admission 仍是一次独立动作；实际执行还需要再次明确授权。T03 继续 failed，T04、S3、release 和 production 继续 blocked。

官方依据：[GPT-5.6 Sol model](https://developers.openai.com/api/docs/models/gpt-5.6-sol)、[OpenAI model guidance](https://developers.openai.com/api/docs/guides/latest-model)、[Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)。
