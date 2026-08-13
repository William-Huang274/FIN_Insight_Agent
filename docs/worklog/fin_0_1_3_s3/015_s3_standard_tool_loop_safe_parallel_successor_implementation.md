# S3 标准 Tool Calls 有界兼容 successor 实现

日期：2026-08-14
状态：`clean_implementation_and_fresh_zero_call_R3_pass / one_replacement_single_cell_live_allowed / model_calls_zero`

## 目标

修复标准 Tool Calls R1 暴露的最早项目责任层，同时不把 DeepSeek 当前返回形态扩散成核心金融权限：精确归一化 wire `index`；只允许同一研究单元的 reviewed Evidence read 与 NumericFact read 成对并行；保留所有补证和 Judgment 串行；让同一步的多个 receipt 与失败 capture 可独立追溯。

## 实现

- Chat Completions transport 接受全有或全无、从 0 连续递增的非负整数 tool-call `index`，归一化后剥离；乱序、负数、混用和未知额外字段继续 fail closed。
- bounded-loop policy 新增 v1.1；v1.0 仍可只读加载且保持单工具语义，避免历史 proof 被新规则改写。
- 两工具 batch 必须名称集合恰为 Evidence read＋NumericFact read、同一 cell、不同 call id；重复 read、跨 cell、EvidenceRequest/Judgment 混合或任意第三个工具均拒绝。
- 预算继续按 tool call 计数，不因合并 assistant step 放大权限；single cell 仍最多 6 step/6 calls，五 cell 仍最多 24 step/24 calls。
- receipt 增加全程递增 sequence，同一步两份结果分别保存；Provider 归一化失败现在携带已原子保存的 response capture ref。
- zero-call runner 增加真实 R1 wire-shape replay、index mutation、安全并行和非法并行验证；current canary 只有新 clean proof 与 R1 disposition 同时满足时才接受 replacement authority。

## 当前验证

- 聚焦测试：30 passed（transport、core loop、canary runner）。
- 全仓：263 passed。
- Python compileall：pass。
- active baseline：115 Python／8 frontend／10 Runtime resources，0 forbidden reference。
- 全仓 secret scan：6,507 files，0 finding。
- 网络、模型、Provider、embedding 调用均为 0；没有生成或发布 Judgment。

## 干净零调用 R3

- authority：`FIN013-S3-BOUNDED-FINANCE-LOOP-ZERO-CALL-R3`，绑定已推送提交 `db14854e...`、R1 原始 Provider response capture、v1.1 policy 与当前 runner／transport／core digest。
- 两个 fresh process 字节等价；research input digest=`6505a58e...`，proof result digest=`7cfd83e2...`。
- single cell 为 3 assistant step／4 tool calls，five cell 为 10 assistant step／15 tool calls；调用预算仍逐 tool call 计算。
- 保存的 R1 wire response 已自然重放为同一 cell 的 Evidence＋NumericFact 安全读对；合法 `index` 被剥离，乱序、负数和 mixed-index mutation 均 fail closed。
- 重复 read、跨 cell、并行 Judgment／EvidenceRequest 均被 `finance_loop_parallel_tool_set_invalid` 拒绝；同一步 receipt 不再覆盖。
- 0 network、0 model、0 provider、0 embedding；R3 只证明项目实现与新鲜性，不证明 DeepSeek continuation 或研究内容质量。

## 边界与下一项

实现已在干净远端提交，fresh zero-call R3 也已通过。下一项只允许签发一个新的 DELL `value_capture` replacement live；R1 不重跑、0 retry。replacement 必须先完成真实 tool result continuation 与最终 Judgment 节点评估；五单元仍不自动授权。
