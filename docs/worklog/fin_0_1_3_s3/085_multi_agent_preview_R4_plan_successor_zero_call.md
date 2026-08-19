# FIN 0.1.3 S3 — Multi-Agent Preview R4 计划续跑零调用证明

日期：2026-08-20

状态：`R4_successor_zero_call_pass / six_R3_plans_reused / live_not_executed / S1_and_S3_false`

## 1. 这轮真正解决了什么

R3 已经证明六个 Specialist 能分别提出需求、经营、价值获取、现金转换、供应／关系和反方研究计划，但 Research Lead 把“分析问题”和“按严格格式交卷”塞在一次 max-thinking 调用里，最终把两次 4,500 token 都耗在推理而没有提交结果。本轮没有重跑六个成功角色，而是把六份通过合同的计划及其 request／response digest 编译成不可变 checkpoint，从 Research Lead 恢复。

所有后续 Agent 节点现在被分成两个阶段：第一阶段只形成模型可见的分析草稿；第二阶段使用 non-thinking profile，把草稿映射为唯一 Tool Call。两阶段分别记录 TokenBudgetBasis。分析草稿不能成为 Evidence、NumericFact、Judgment 或报告内容，也不能改变事实权限。

## 2. 零调用时暴露的更早责任层

这次没有把所有失败继续归因给 DeepSeek，而是发现并关闭了四个项目内问题：

1. 六份自然计划合计产生 13 个有效 facet，但 Research Lead schema 和 validator 都把 12 写成固定上限。这个限制会在协调前静默删除有效研究方向。
2. 通用 planning policy 把“允许模型提出多少方向”和“本轮最多执行多少 EvidenceRequest”都写成 12。现在两者分开：Preview 最多接收 20 个提案，确定性 selector 仍只执行 12 个，其余必须生成 deferred receipt。
3. 三条自然研究意图超过 EvidenceRequest 的 120 字符合同。现在由 provider-neutral compiler 按语义分隔符无损拆分，仍保持每个 facet 最多四个可执行意图；没有提高下游字符上限。
4. Material Evidence Runtime 的历史归一化只保留 ASCII，中文研究意图全部变成同一个空 key，使精确 request／narrative binding 看起来冲突。现在改为 Unicode-aware 归一化，并用不同中文意图的回归测试锁定。

Workbench service 增加调用级 planning-policy 注入，Preview overlay 不会修改或替换全局产品 policy，也不会改变 Evidence、NumericFact、来源或 Candidate 晋升权限。

## 3. 当前 proof 的业务形状

- 复用 Specialist 计划：6；新增 Specialist 模型调用：0。
- 自然提案：13；确定性选中并执行：12；明确延期：1。
- 编译 EvidenceRequest：12；本地 BM25＋Qwen 候选：192。
- S2 typed fact request：44；resolved 27；typed gap 17；NumericFact 87；冲突 0。
- 六个 Agent 的输入均非空，并各自保留两个工具执行回执。
- 后续最大新逻辑模型节点：16；每节点最多 1 次分析、2 次提交 attempt；0 网络、0 Candidate promotion、0 paid/model call（本 proof）。
- checkpoint 缺角色、checkpoint digest 漂移、submission 复制原始上下文等 mutation 均 fail closed。

零调用结果：`configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_R4_plan_successor_zero_call_result_v1_0.json`。

## 4. 验证与边界

定向回归 `75 passed`；全仓 `844 passed`。这只证明当前 checkpoint、两阶段节点、13→12 选择、S1/S2 物化和失败边界在不调用模型时一致。

它没有证明 Research Lead、六份工作底稿、跨角色挑战、Evaluator、Writer 或最终报告真实完成；也没有关闭 RC-S1-049 的上游动态召回问题，不证明开放式外源检索、S1、S3、跨公司泛化、qualified-human、Workbench 发布或 release。

下一步必须先把本 proof、planning overlay 和 scope decision 提交到干净远端基线，再做 Project OS preflight。只有 preflight 精确绑定该提交和全部摘要后，才能签发并执行唯一一次 R4 live。
