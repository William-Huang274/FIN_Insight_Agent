# 008：E1 流式用量、当前价表与一次真实 DS 样本

2026-09-14，FIN 0.1.4 / E1，基于 `bf027724`。用户已授权合理范围 DS/Qwen 测试。本包实际仅发出一次 DeepSeek V4 Pro 非思考请求；公开价估算 0.001692 CNY，尚非供应商账单。未默认启用预算、未部署或修改包版本。

## 实际发现与修复

锁定的 langchain-deepseek 1.1.0 使用 OpenAI SDK 路径解析 SSE，未保留 DeepSeek 的 `prompt_cache_hit_tokens`，使有完整用量的流式响应仍无法结算。沿用现有 SDK 的传输、解析和聚合，只在已有子类补充原始 usage 和缓存命中映射。供应商缺少必需用量字段时保持占用，不接受 SDK 补零为真实计费证据。

SDK 在没有终止字段的干净 EOF 后可能返回部分 AIMessage。派发保护现在拒绝将其登记为已知完整响应，保留未知、不重发；CaseModelAudit 也拒绝缺少终止字段的流式输出。`length`、`aborted`、内容过滤和资源中止虽不通过接受检查，但若已有终止响应及完整 usage，则先保存和结算已知费用。这里新增的完整性接受检查针对 CaseModelAudit；不宣称所有供应商/同步适配器均已完成异常语义资格。

2026-09-14 重新核对 [DeepSeek 官方价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)：Pro 在该日后继续服务且计价不变，原代码预设的中午切换 Flash 价格已不成立。当前估算改用 Pro 价格；历史已保存审计不重写。空闲时段缓存命中/未命中/输出分别 0.15/4.5/13.5 元每百万 tokens，高峰翻倍。流式协议依据 [官方 Chat Completion 文档](https://api-docs.deepseek.com/api/create-chat-completion/)：测试覆盖终止 choice 同块 usage、缺用量、缺必需字段、截断、断流、提前 EOF、aborted。没有新建 provider transport 或运行引擎。

## 实测与失败保留

以下 attempt 均位于 `.local/fin014/`，日志及 JUnit 不覆盖：

| Attempt | 结果 | 说明 |
| --- | --- | --- |
| `20260914_e1_stream_a1` | 3 failed / 3 passed，10.74 秒 | 首次 SSE 测试复现缓存信息丢失导致无法结算，以及提前 EOF 被接受。 |
| `20260914_e1_stream_a2` | 26 passed，5.81 秒 | 修复后 7 个 SSE 模式、13 项派发保护和 6 项历史/当前计价测试通过。 |
| `20260914_e1_stream_regression_a1` | 1484 passed / 146 skipped，160.80 秒 | 完整默认离线回归；跳过项不计通过，保留既有 LangSmith 弃用警告。 |
| `20260914_e1_deepseek_stream_a1` | 1 failed，27.26 秒 | 一次真实请求及保存后节点恢复均已完成；最后的测试断言把 25.0% 与 25% 当作不同数值，判错。原失败保持不变。 |
| `20260914_e1_deepseek_stream_saved_review_a1.json` | 离线原响应复核完成，新增调用 0 | 修正数值等价断言后只读保存结果，收入增长 25%、利润率 10%/12%、增加 2 个百分点正确，合成标签存在；要求三行但实际四行的格式偏差保留。不是重新跑过的付费 pytest 全通过。 |
| `20260914_e1_stream_final_a1` | 26 passed / 1 skipped，3.76 秒 | 收口定向复测通过；真实付费入口在默认环境正确跳过，未新增供应商请求。 |

真实样本使用一个无真实公司信息的两期收入/营业利润问题。调用前 `paid_preflight.json` 已保存任务专属 TokenBudgetBasis、完整输入、501 UTF8 bytes 的 SDK payload、价格版本和预留场景。输出上限 1000 tokens、单请求超时 120 秒、SDK 重试 0；HTTP hook 限定官方端点且拒绝第二次请求，宿主与容器 tracing 均关闭。模型密钥只在宿主使用，不挂载 Docker 或写入证据。

根预算 0.10 元，交付预留 0.01 元；本请求预留 0.081864 元，来自最多 2000 payload bytes 加 4096 framing token 余量及 1000 输出的高峰未缓存价格场景。该余量是本小样本的保守依据，不是经过所有模型 tokenizer 证明的账单硬上限，也不是研究任务成本预测已校准。

北京时间 10:38 实际供应商调用返回 input 77 / output 37 / total 114，cache hit 0，约 1376.567 ms。公开价估算 `(77 × 9 + 37 × 27) / 1e6 = 0.001692 CNY`；PG 已知 1692 micro，held/unsettled 均 0，剩余 98308 micro。随后在响应保存后、节点 checkpoint 完成前主动抛一次测试异常，同一 LangGraph checkpoint 恢复发出一个 replay 事件，总 HTTP 请求仍为 1。此次 checkpoint 使用 InMemorySaver，响应/费用使用真实 PG；它不是付费进程重启或全研究图恢复实测，原生服务硬崩溃资格另见 005–007。

原响应 SHA256：`1ef834c63edd2000833b6efeb093a7ff4bd12546bdb0a0dbaeac6160413e799d`。`paid_result.json`、`paid_events.jsonl`、`paid_http_dispatches.json` 和最终 PG snapshot 互相核对；后续离线复核单独保存。容器已停止，原卷/网络/日志保留。fixture 环境字段改名为 `fixture_graph_model_calls`，其 0 只说明 Docker 合成图，不能用来否认宿主这一次真实付费请求。

## 增量与下一步

产品增量：现有 CaseModelAudit 流式入口拒绝不完整输出；可选预算路径获得流式用量结算与一次真实保存响应回放证据。工程增量：SDK 薄映射、终止状态检查和当前价表纠正。研究/资格增量：一个合成输入的真实 Pro 请求及原结果离线算术复核；没有新公司研究结论或金融质量通过。文档增量：同步技术、路线、成本口径及 Project OS。

E1 保持进行中。真实缓存命中、思考/工具流式、Qwen/Hermes、供应商账单、数据库角色/私有消息保留与恢复、跨研究公平性和正式部署许可未由这一次样本证明。下一小包优先以 PG 原生角色验证私有响应访问和保留/恢复边界，再进入已有路线的一份持久项目/资料/成果可见切片；不因本包一次样本扩建计费平台，也不把 E1 局部通过当成 0.1.4 发布。
