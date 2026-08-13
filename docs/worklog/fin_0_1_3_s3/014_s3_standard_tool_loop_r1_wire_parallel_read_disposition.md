# S3 标准 Tool Calls R1 线格式与只读并行处置

日期：2026-08-14  
状态：`R1_immutable_terminal / project_root_cause_confirmed / zero_call_successor_required`

## 问题与证据

绑定干净远端提交 `2aab623d...` 的唯一 DELL `value_capture` 标准 Tool Calls R1 已执行。Provider 返回 HTTP 200、`finish_reason=tool_calls`、prompt/completion/reasoning=`2257/128/15`，并一次提交 `read_reviewed_evidence_for_cell` 与 `read_numeric_facts_for_cell`。这正是当前单元被要求先做的两类只读读取。

Harness 未执行任何工具：Chat Completions 归一化器拒绝 Provider tool call 上的合法非负 `index`；核心循环又只允许每轮一个调用。公开 terminal 还因异常发生在 step 形成前而漏掉已经保存的 response capture ref。R1 因此保留为 `terminal_failed_no_retry`，没有 accepted receipt、Judgment、内容验收或发布。

## 决策

这是同一 S3 transport gate 内的项目兼容缺陷，不是 DeepSeek 指令遵循失败，也不是扩大 Agent 自主权的理由。successor 只允许：精确容忍并剥离 wire `index`；把 Evidence read＋NumericFact read 作为唯一安全并行组合；所有 EvidenceRequest 和 Judgment 继续串行；修复 capture ref；先做 replay、mutation、fresh zero-call proof，再签发一个新 single-cell live。五单元继续阻断。

机器处置见 `configs/research/evals/fin_ia_0_1_3_s3_dell_value_capture_standard_tool_loop_r1_disposition_v1_0.json`；完整模型运行账本见 `reports/model_runs/FIN_0_1_3_S3_DELL_VALUE_CAPTURE_STANDARD_TOOL_LOOP_R1_20260814.md`。
