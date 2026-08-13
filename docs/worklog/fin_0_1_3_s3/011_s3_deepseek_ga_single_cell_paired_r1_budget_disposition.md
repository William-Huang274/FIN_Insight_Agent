# S3 DeepSeek GA 单单元 paired R1 预算耗尽处置

日期：2026-08-14
状态：`R1 immutable terminal failed / project-owned capacity root cause / one replacement pending`

## 实际发生了什么

DELL `CELL::value_capture` 的 JSON control 与 strict final-tool 两路使用相同业务输入，各执行一次，0 retry、0 fallback。两路均 HTTP 200，但都以 `finish_reason=length` 结束；每路 `completion_tokens=5,000`，其中 `reasoning_tokens=5,000`，最终可见正文为 0，strict tool call 也为 0。

因此历史公开结果中的 `content_empty`／`tool_step_empty` 只是当时网关的粗粒度终止码。真实首因是 GA profile 在 `thinking=max` 下仍沿用 5,000 token 输出预算，推理在提交最终答案前耗尽全部额度。这一轮没有产生 Judgment，不能评价 DeepSeek 是否遵循 v1.1 JSON 合同、strict schema 或金融内容边界。

## 处置

- R1 authority、公开结果和四份 capture 保持不可变，不补写成功；
- Provider gateway 增加 `reasoning_budget_exhausted` 与一般 `generation_budget_exhausted` 分类；
- 新建 JSON／strict profile v1.1，把单次上限有界调整为 16,000，保持 `thinking=enabled`、`reasoning_effort=max`；官方当前模型上限为 384K，本次没有接近该上限；
- replacement 仍绑定相同业务输入、每路一次、0 retry、0 fallback；
- replacement 再次耗尽预算或出现新 L1 时停止，不自动进入第三次 paired；
- 五单元 live 继续禁止，直到 paired transport、合同和内容审计通过。

机器可读处置：`configs/research/evals/fin_ia_0_1_3_s3_dell_ga_value_capture_paired_r1_disposition_v1_0.json`。
