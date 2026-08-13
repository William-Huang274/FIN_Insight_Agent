# S3 DeepSeek GA profile 与四工具有界循环实现

日期：2026-08-13
状态：`clean_zero_call_engineering_pass / paired_live_pending / model_calls_zero`

## 本轮目标

把已经修好的 v1.1 最终判断合同扩展成 provider-neutral 的最小研究循环，同时把 DeepSeek V4 Pro GA 的 endpoint、thinking 参数和 strict Beta 差异隔离到可替换 profile。没有恢复旧九调用 runner，也没有整体引入 developer-preview 官方 Harness。

## 已实现

- 四个 typed tool：按 cell 读取 reviewed Evidence、读取 NumericFact、提交 EvidenceRequest、提交 Judgment；
- EvidenceRequest 仅生成受当前金融内核和 route/planning policy 校验的补证提案，不执行检索、不关闭 gap、不晋升候选；
- 总上限 24 step／24 calls、并行 1、连续 2 次无进展停止，并按工具设置独立上限；
- standard、JSON control、strict Beta 三个 DeepSeek GA profile，统一 `thinking=enabled`、`reasoning_effort=max`，不发送无效 sampling 参数；
- capture-first tool-step transport：保存模型可见请求、工具参数、assistant/tool 输出、usage、finish reason、capture ref 与 digest；Provider 私有 `reasoning_content` 只用于运行内 continuation，不写入 capture 或 result ledger；
- v1.1 consumer 支持单 cell 投影，用于后续同 Evidence Pack 的 JSON／strict paired canary；
- closed strict schemas、gapless/numless cell、unknown/cross-cell/duplicate/no-progress mutation，以及单单元与五单元 fake 全链。

## 当前工程证据

- 定向测试：36 passed；
- 全仓回归：248 passed；
- active-baseline：114 Python／8 frontend／10 Runtime resources，0 forbidden reference；
- secret scan：6,483 files，0 finding；
- compileall 与 `git diff --check`：通过；
- fake 单单元可在 4 step 中读取 Evidence/NumericFact、提交补证提案和 Judgment；
- fake 五单元可在 15 step 中完成，不依赖固定 9 次调用；
- 当前模型、网络、Provider、检索和 embedding 调用均为 0。

实现已提交并推送为 `ae86d8bc90b23f6ee6d6c488f0762efa4768ebee`。绑定该提交的独立 zero-call R1 已通过：single-cell=`4` step，five-cell=`15` step，两次 fresh process byte-equivalent；EvidenceRequest 后 gap=`open`，0 retrieval、0 candidate promotion、0 network/model/Provider/embedding。结果为 `configs/research/evals/fin_ia_0_1_3_s3_bounded_finance_loop_zero_call_result_v1_0.json`。

下一门只允许实现并签发 DELL 单研究单元 JSON／strict final-tool paired canary。zero-call 没有资格证明 strict Beta 的真实 Provider transport，也没有证明自然金融研究质量、五单元循环、Workbench 或 S3 通过。
