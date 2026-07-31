# 460｜FIN 0.1 S4-T06 入口 Sub2API API Key Mode 认证重分类与诊断边界

日期：2026-07-28

## 新证据

用户补充 Windows / API Key Mode 配置截图。与上一张兼容模式截图相比，关键变化是：

- `requires_openai_auth = false`；
- 存在一个由运营界面给出的固定 actor-authorization 客户端标识；
- base URL、Responses wire 和 `gpt-5.5` alias 不变；
- 配置保存后需要完全退出并重启 Codex Desktop/CLI，再新建 task。

截图中没有显示 API key 值，本轮也没有读取或持久化 header value。

## 重分类

API Key Mode 明确关闭 OpenAI Bearer authentication，因此上一轮“API key 会按 OpenAI auth 直接发往 HTTP endpoint”的结论不适用于该模式。官方 `OPENAI_API_KEY` 和此前 Sub2API key 都不应被当前 FIN Insight runner 读取或发送。

但 plain HTTP 的剩余边界仍存在：

- prompt 与 response 没有 TLS confidentiality；
- 无法通过 TLS 验证 server identity；
- response integrity 没有 TLS 保护。

因此当前地址可以在另行授权后执行一次仅含合成或公开数据、无 credential、无业务写入的 diagnostic canary；该结果只能诊断 `/responses + gpt-5.5 + strict-schema` 兼容性，不能关闭传输 blocker、不能作为 T06 主线验收、不能进入 full chain。

## 下一项

`S4-T06-ENTRY-SUB2API-PUBLIC-NON-SENSITIVE-DIAGNOSTIC-CANARY-AUTHORITY-DECISION`

它只冻结未来一次请求：

- public/synthetic fixture；
- no OpenAI Bearer、no API key read/write；
- 固定客户端标识；
- 1 request、retry=0；
- 0 WorkUnit/Attempt/Run/business Artifact；
- terminal diagnostic result；
- success 也不进入 T06。

本轮 model/provider/network call=`0/0/0`，runner/runtime change=`0/0`，diagnostic canary 未授权、未开始。

## Git

工作树继续保持历史 mixed state；本轮不清理、不 stage、不 commit。

## 验证

- 全部 S4-T06 contract tests：`81 passed`；
- Project OS diagnostic-authority 精确 scope 预检通过；
- JSON/JSONL 重复键、Python syntax、敏感凭据模式与 scoped diff 检查通过；
- model/provider/network call=`0/0/0`。
