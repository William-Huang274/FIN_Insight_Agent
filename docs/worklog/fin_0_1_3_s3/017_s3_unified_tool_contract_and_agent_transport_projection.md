# S3 统一工具合同与 Agent 协议投影

日期：2026-08-14
状态：`formal_clean_replay_pass / paid_Chat_Responses_pair_pending / paid_calls_zero`

## 为什么做

标准 Tool Calls R2 已证明 DeepSeek 能正确读取本单元 Evidence 与 NumericFact，也能识别“销量还是价格驱动收入”的真实补证方向。失败发生在项目合同：模型看到的是全局 facet／metric 和模糊的“concise”，本地却另有 120 字符及 facet→query-family→metric 约束。该状态会让一个 Schema 合法的动作在 Harness 内必然失败。

同时，DeepSeek V4 Pro GA 已提供 Chat Completions、Responses 和 Anthropic Messages 兼容协议。协议选择若继续散落在金融循环里，会把 Provider 协议差异和金融真实性控制面再次耦合。

## 本轮实现

1. 新建唯一 `FinanceToolContract` 编译源。它从当前 Case、Cell、visible gap、Evidence Slot、facet、关系方向、target entity、route family 和 metric route 编译四个工具；Schema、运行时 validator 和 repair surface 不再手工对齐。
2. EvidenceRequest 的数组数量、唯一性和文本长度现在对模型可见；每个 facet 只暴露本 family 可用 metric 和本案允许 target。DELL／MU／NVDA 的 `pricing_and_mix` 均只能指向各自主体。
3. proposal-only 的字段、facet、metric family 和长度错误返回 `rejected_not_executed`，不执行检索、不晋升 Evidence/NumericFact、不关闭 gap；模型只能在原 step／tool／no-progress 预算内修正。跨 Case/Cell、身份、引用、Judgment 和真实性错误仍 hard fail。
4. 新建 provider-neutral Agent 协议层：核心 Runtime 只保留规范化 message、tool definition、tool call 和 tool result；Chat、Responses、Anthropic 只负责外层投影。
5. Responses executor 使用无状态全历史重建；同一 loop 所需的 reasoning output item 只在内存继续传递，保存的 request／response capture 和公开结果均删除私有推理。Provider 静默忽略的 `max_tool_calls`、`parallel_tool_calls` 等字段禁止发送，本地预算仍是唯一权威。
6. Anthropic Messages 当前只有 schema/transcript shadow，dispatch 会以 typed failure 阻止它进入 live。Chat control 与 Responses candidate 共用 `execute_finance_loop_transport_lane`，没有复制第二套金融循环。
7. 新增永久零调用 replay runner 和同输入 Chat/Responses paired runner；后者仍要求 clean proof、fresh authority 和 exact-once Git boundary，不能因代码存在自动执行。

## 当前验证

- 聚焦协议／合同／runner 测试：30 passed；全仓：271 passed。
- active baseline：122 Python／8 frontend／10 Runtime resources，0 forbidden reference；两个新 runner 已进入正式 manifest。
- secret scan：6,526 files，0 finding。
- 本地零调用 R2 replay：旧 R2 proposal 先被安全拒绝，随后一个 facet-compatible repair 被接受并完成 Judgment；总计 4 step／5 receipts，旧错误请求没有成为 proposal、Evidence 或 NumericFact。
- DELL／MU／NVDA 跨案 target mutation 均以 `finance_loop_evidence_request_target_out_of_scope` hard fail。
- 同一 canonical tools／transcript 可投影到 Chat、Responses、Anthropic，并逐协议 round-trip 回同一 canonical contract。
- network/model/provider/embedding calls 均为 0。

绑定干净远端提交 `17bb0c5a...` 的正式 R1 已通过：research input digest=`6505a58e...89b4c`，当前合同 digest=`e4164404...d967a`，旧 R2 合同 digest=`2ead2aa4...e423`，result digest=`fe188a89...d5eb`。正式结果再次证明旧请求被 `rejected_not_executed` 后，合法 repair 可完成 Judgment；4 step／5 receipts，只有 1 个有效 proposal，错误请求 0 晋升。authority 额外绑定当前 Runtime Registry 与 Evidence Pack，避免通过未绑定运行时输入制造伪 clean proof。

formal authority/result 纳入后 secret scan 为 6,528 files／0 finding。

## 尚未证明

- Responses 的真实 DeepSeek Tool Use、长程 continuation 和自然内容质量尚未观察；
- Anthropic live 未资格化；
- DELL 五单元、完整八维报告、qualified-human、S3、Workbench 和 release 均未通过。

## 下一门

提交并推送正式 authority／result 后，签发 DELL `CELL::value_capture` 的 Chat control／Responses candidate 同输入 paired authority。两路各最多 6 step、总计最多 12 次 Provider 调用、0 retry/fallback/external retrieval。完成后先做合同与内容评估，再决定五单元是否值得运行；不得自动进入五单元。
