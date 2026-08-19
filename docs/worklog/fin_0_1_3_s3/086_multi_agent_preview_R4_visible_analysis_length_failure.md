# FIN 0.1.3 S3 — Multi-Agent Preview R4 可见分析截断

日期：2026-08-20

状态：`R4_terminal_failure_preserved / visible_Lead_analysis_partial / no_submission / S1_and_S3_false`

## 1. R4 实际发生了什么

R4 在 clean／synced 提交 `1c3a26a6...` 上通过 Project OS preflight 后执行。六份 R3 Specialist 计划从不可变 checkpoint 恢复，新增 Specialist 计划模型调用为 0；13 个自然提案、12 个执行名额和 1 个延期仍保持零调用 proof 的边界。

第一个新节点是 Research Lead 的 analysis phase。请求为 HTTP 200、完整响应，输入 6,848 token，输出上限 12,000 token。DeepSeek 使用 9,447 reasoning token，并生成 9,932 字符可见分析，正确列出了六个角色、13 个 facet、七个 Evidence Slot、已知事实与待证假设，以及至少 10 个跨角色协调问题。但输出在第 11 个协调问题中途达到长度上限，`finish_reason=length`。Runner 因分析未完整而 fail closed；submission、工作底稿、挑战、Evaluator 和 Writer 均未开始。

## 2. 与 R3 的区别

R3 的 Lead 两次都是 4,500 reasoning token、可见 content 为 0。R4 的“分析／交卷分离”确实让模型产生了大量可见、业务上有意义的 Lead 分析，所以该结构修复不是无效的。

但 R4 也暴露出一个更深的问题：当前 Agent analysis 仍被当作一次性 one-shot。只要可见草稿在末尾截断，Runtime 只能丢弃整个节点，不能把已保存的 9,932 字符作为 checkpoint，也不能把“你已完成哪些部分、还缺哪些部分”的 FeedbackReceipt 交给模型继续。因此最早责任层不是 S1 数据、Provider 连通、严格 schema 或 submission，而是 S0/S3 Agent Runtime 缺少分析片段续写与语义完成度检查。

## 3. 正确的下一处置

不能继续简单提高 completion 上限，也不能把截断草稿直接当作 Lead authority。下一 successor 应：

1. 将 R4 的可见 partial draft、request／response digest 和已完成章节保存为分析 checkpoint；
2. 本地只判断 required sections 的完成／缺失，不替模型补写观点；
3. 生成 FeedbackReceipt，让同一 Lead 只续写缺失部分，禁止重复前四节；
4. continuation 使用与任务相称的较低 reasoning profile 和明确可见长度目标，因为它只补齐剩余协调问题、信息边界和停止条件，不再重新综合六份计划；
5. 最多允许一个 continuation fragment；仍不完整则停止，不进入无限 successor；
6. 合并后的完整 draft 才能进入 non-thinking strict submission。

这是一条 provider-neutral 的真实多轮 Agent 能力：保存进度、接收失败反馈、修改下一步，而不是 DeepSeek 字段补丁。R4 authority、公开 result、完整 request／response capture 和 private terminal failure 均保持不可变。

## 4. 边界

R4 只证明六角色计划可以恢复、两阶段 analysis 能产出有意义的可见内容，以及当前 one-shot analysis Runtime 不足。它没有完成真正 Multi-Agent Preview，不评价最终研报质量，也不证明 S1、S3、泛化、qualified-human、Workbench 发布或 release。
