# FIN 0.1.3 S3 submission successor R3 部分成功与 R4 精确续跑零调用门

时间：2026-08-23

状态：`R3_terminal_preserved / three_workpapers_requalified / cash_frontier_exact / R4_authority_pending`

## R3 真实表现

R3 共发生 9 次 DeepSeek Provider 调用，全部 HTTP 200、0 retry。Demand、Operating、Value 三个 Specialist 已形成可重建、合同有效的工作底稿；Cash 的第一轮 reflection 也已完成。八份成功 request/response capture 均逐文件 SHA、canonical digest、Tool name 与 finish reason 验证通过。

第九次调用是 Cash workpaper 的自然分析节点：prompt `11,027` token，completion `16,000` token，其中 reasoning `16,000`，`finish_reason=length`，没有形成可提交的 Tool draft。该调用不具备晋升或重放资格。R3 public/private terminal result、九份 manifest 和全部原始 capture 保持不可变。

这不是 DeepSeek 不遵循 JSON 或研究指令，也不是 S1/S2、信源或网络失败。最早责任层是 S3 节点的 `TokenBudgetBasis` 与实际研究负荷不匹配：当时 thinking=max 的 profile 把生成预算固定为 16k，而官方接口定义中 `max_tokens` 同时约束推理和最终输出。官方资料也允许在上下文范围内配置更高输出上限：

- https://api-docs.deepseek.com/guides/thinking_mode/
- https://api-docs.deepseek.com/api/create-chat-completion/
- https://api-docs.deepseek.com/quick_start/agent_integrations/pi_mono/

## 续跑结构

新增 provider-neutral 的 partial-successor capture overlay：

- Demand 复用 R3 workpaper submission；
- Operating、Value 各复用 reflection submission、自然 workpaper draft 和 strict submission；
- Cash 只复用 reflection submission，失败的 workpaper draft 明确不可复用；
- Counterevidence 继续按 R1 capture 本地重建；
- Supply 尚未执行，继续保留唯一一个真实 S1/S2 request 的权限。

零调用 R4 复证重新运行了真实角色组装和 Validator，三个完成角色均以 `provider_calls=0` 形成相同合同工作底稿；Cash 的第一个、也是唯一允许的新 Provider 前沿精确落在 `cash-conversion-workpaper-draft`。没有生成新 Evidence、NumericFact、判断或报告。

公开 proof：

`configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_submission_successor_zero_call_result_v1_3.json`

result digest=`7f55d22b81457b6fcc50d613e83919d40f7841adb6cb12a4fe80b39816330161`。

## 新 TokenBudgetBasis

thinking 研究节点 profile 的 `max_tokens` 从 16k 调整为 32k，但不增加 retry。依据不是“多给一点试试”，而是：

- R3 Cash 已用完 16k，最终输出为 0；
- Operating 自然底稿实际需要 10,211 reasoning + 3,798 可见输出量级；
- Value 自然底稿实际需要 11,451 reasoning + 4,021 可见输出量级；
- 32k 为同类节点保留足够推理与完整交卷空间，同时仍由 0 retry、节点拓扑和无进展停止条件限制成本。

R4 剩余最坏拓扑为 17 次调用：Cash／Supply 两份自然底稿与 strict submission、Supply reflection 与唯一补证回合、最多两轮 Lead、最多三次原角色 repair。已完成节点不得重跑。

工程复证为定向 `14 passed`、全仓 `1126 passed`（仅 2 条既有 SWIG deprecation warning）、compileall、pyflakes、active baseline `210 Python／8 frontend／5 detectors／28 Runtime／0 forbidden`、922 份 config JSON、8 份 Project OS JSONL／1,002 行、7,762-file secret scan／0 与 diff check 全部通过。

## 边界

当前只证明 R4 可从正确前沿恢复。尚未证明六份底稿、Lead、L1、八维内容质量、Writer、MU／NVDA、异质留出、S3 或 release。新 authority 只能在全仓验证、干净提交／推送和 repository-aware preflight 后签发。
