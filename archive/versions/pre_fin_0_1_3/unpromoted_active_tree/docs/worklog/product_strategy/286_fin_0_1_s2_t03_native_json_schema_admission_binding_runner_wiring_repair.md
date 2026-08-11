# FIN 0.1 S2-T03 原生 JSON Schema admission binding 与 runner wiring 修复

时间：2026-07-20

## 授权与边界

用户授权执行 `S2-T03-NATIVE-JSON-SCHEMA-ADMISSION-BINDING-AND-RUNNER-WIRING-REPAIR`。本轮只允许本地零调用修复、确定性测试和独立复核；没有签发新 admission，没有模型推理、provider execution、外部工具、T04、S3、release 或 production 行为。

## 修复结果

1. `BoundedAgentAdmission` 新增 `specialist_transport_ref` 与 `reasoning_effort`。所有新的 execution-enabled admission 必须同时显式绑定两者；支持的 reasoning 值为 `none/low/medium/high/xhigh/max`。
2. admission 不再只靠 provider 名称推断 transport。`build_bounded_agent_executor_for_admission` 只根据 exact transport binding 构造 strict-tool 或 native JSON Schema adapter；executor 再做一次独立 binding/adapter 一致性校验。
3. runner preflight 同时校验 transport、provider、model_ref、base URL、credential env 与 reasoning，输出 exact transport/reasoning metadata；execute 使用同一个 admission-driven factory，不再硬编码 `DeepSeekBoundedAgentExecutor()`。
4. OpenAI native Specialist 的 Responses 请求收到 `reasoning={"effort":"medium"}`；Writer/Verifier 的现有 Chat Completions 路径收到同一 admission-bound `reasoning_effort`。没有新增 fallback、retry 或隐式 provider 切换。
5. 默认 `create_app()` 仍不自动装配 bounded admission/executor；只有 runner 显式传入完整 pair 时才启用，因此没有把 fixture proof 偷换成默认产品运行时切换。

## 历史兼容性

五份 v1/v2/v3/v4/v4-r2 历史 admission 仍允许读取；缺少新字段的兼容只对白名单历史 admission ID 生效。`digest_payload()` 仅在字段为 null 时移除新增字段，原 digest 全部逐个保持：

- v1 `48db7689...7ea0e`
- v2 `03cf4bfa...136ea`
- v3 `8e058866...3f710`
- v4 `61e9e210...39f6`
- v4-r2 `671ec47b...0adf`

独立复核进一步纠正了兼容 introspection：v1-v3 仍标识为历史 `deepseek_json_object:v1`，v4/r2 才是 strict-tool；json-object 不允许用于任何新 admission。consumed admission/work-unit guards 未改变，历史 provider 请求没有重放。

## 独立复核

复核覆盖新 admission 未绑定字段、未知 transport、strict/native adapter mismatch、OpenAI provider/model_ref/base URL/env binding、DeepSeek beta 历史 binding、reasoning wire payload、runner zero-call preflight 与 factory selection。结论为 `pass_after_backward_compatibility_and_wire_binding_verification`。

官方当前合同确认 `gpt-5.6-sol` 支持 Responses、Chat Completions 与 Structured Outputs，reasoning efforts 为 `none/low/medium/high/xhigh/max`，`medium` 是平衡起点；实现未采用 Pro、persisted reasoning、PTC、multi-agent 或其他未授权能力。

## 验证与下一项

gateway + S2-T01/T02/T03 扩展回归：`84 passed in 91.59s`；Project OS `6 passed in 0.22s`；Python compileall、JSON/JSONL parse 与 `git diff --check` 通过。本轮 model inference/provider execution/execution network/external tool/new admission/actual execution 均为 `0`；只进行了官方 OpenAI 文档网络核对。

项目内 admission-binding/runner-wiring blocker 已关闭，但 live provider compliance、closed v4 Agent Artifact 与研究质量仍未证明，T03 继续 failed。下一项冻结为尚未授权的 `S2-T03-NATIVE-JSON-SCHEMA-GPT-5-6-SOL-EXACT-ADMISSION-ISSUANCE-DECISION`；签发与实际执行仍是两次独立授权。

官方依据：[GPT-5.6 Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol)、[Model guidance](https://developers.openai.com/api/docs/guides/latest-model)、[Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)。
