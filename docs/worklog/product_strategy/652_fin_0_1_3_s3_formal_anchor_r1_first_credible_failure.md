# 652 — FIN 0.1.3 S3 formal Anchor R1 首个可信失败

日期：2026-08-06

## 执行结果

在 clean/synced commit `7e71e641969901013740ece9ea09f36f2466a9e4` 上签发并消费唯一 fresh admission。计划 9 个 DeepSeek Pro 受限 Specialist request；R1 在第 1 项 DELL demand 后终止：

- Provider/transport：成功，`finish_reason=stop`，1 次 transport；
- usage：562 input / 117 output / 679 total tokens；
- capture：1 份，先于校验保存；
- 后续 8 request：全部 skipped；
- retry/fallback/第二次 run：0/0/0；
- Claim/Lead/Workpaper/quality score/business Artifact：0。

## 真正失败原因

Provider 返回的是合法 JSON，不是 JSON 语法错误。DeepSeek 同时选择：

- `epistemic_state=cannot_infer`；
- `answer_direction=cannot_infer`；
- 非空 `support_aliases=[DELL_E01]`。

这违反 compact Specialist 合同：若结论为 `cannot_infer`，不能同时声明支持证据。因此真实 failure code 是 `s2_compact_output_cannot_infer_support`，属于本次自然输出的语义合同遵循失败。

Runner 另有一个本地缺陷：`S2ContextYieldError` 继承 `ValueError`，原异常顺序先把它捕获成 `provider_output_json_invalid`。历史 terminal 保持不可变；successor classifier 已调整异常顺序，并增加回归证明合法 JSON 的语义错误会被正确分类。

## 边界

R1 只能证明该请求的一次自然输出失败，不能推导 DeepSeek 的九个 request 全部失败，也不能把项目内分类缺陷当成模型失败。按预注册策略，本轮不自动签发 R2。下一项只能做零调用的 first-credible-failure root-cause/replacement disposition，决定是否修改 provider prompt/semantic normalization、缩减模型选择权限，或保持阻断。

## 验证

- formal runtime focused：8 passed；
- current canonical successor：242 passed / 1 historical assertion deselected；
- public failure record 只保存安全 alias/enum、digest、usage 和边界；raw capture 保持 Git 外。
