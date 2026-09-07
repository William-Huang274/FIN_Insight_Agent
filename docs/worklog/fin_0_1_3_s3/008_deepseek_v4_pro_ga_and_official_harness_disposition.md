# DeepSeek V4 Pro GA 与官方 Harness 处置

日期：2026-08-13
状态：`decision_recorded / no_new_model_call`

官方已发布 V4 Pro 正式版，但 API 模型名保持 `deepseek-v4-pro`。因此本项目不能依据旧 R1 的模型名把它追溯标记为 Preview 或 GA。新实验只比较请求 profile、transport 和合同形态，并如实记录 Provider 未返回 build identity 的边界。

采用：标准 API；thinking enabled；复杂研究使用 reasoning effort max；thinking 模式不发送无效 temperature/top_p；工具循环正确回传 transient `reasoning_content`；总 step、工具预算和 no-progress stop；完整 capture 与 typed terminal。

不采用：把 developer-preview `deepseek-ai/deepseek-harness` 整体导入 FIN；把 coding Agent benchmark 等同于金融研究质量；让 DeepSeek profile 分支进入 provider-neutral 金融合同；让 Beta strict tool 成为未验证的主链单点。

下一顺序：v1.1 clean proof → GA profile／四 typed tools → zero-call loop proof → DELL 单单元 JSON vs strict-tool paired canary → 传输选择 → DELL 五单元 bounded loop → L1、八维、paired、qualified-human 验收。

官方参考：

- https://api-docs.deepseek.com/zh-cn/news/news260813
- https://api-docs.deepseek.com/zh-cn/guides/thinking_mode/
- https://api-docs.deepseek.com/guides/tool_calls/
- https://github.com/deepseek-ai/deepseek-harness (审计 HEAD `47f943859bef60e4160492346772ded9b24f765a`)
