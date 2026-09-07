# S3 当前研究消费者零调用纵切

日期：2026-08-13
状态：`engineering_pass_zero_call / clean_reproof_pass / natural_canary_pending`

## 本轮完成

- 新增 provider-neutral `current_consumer`，把当前 DELL reviewed Evidence Pack、保存的 Planner R1 受控执行和 S2 NumericFact 编译为五个研究单元。
- reviewed transcript 只在已通过 Evidence Gate 的 Pack 内消费；不扩张开放检索 source whitelist，也不自动晋升数值权威。
- 将 45 个 request-level NumericFact 合并为 35 个经济事实，再按最新季度／财年／时点选择 25 个模型可见事实；完整 request 和 source lineage 留在私有审计结果。
- 模型视图保留来源原文、边界和权威数值，剥离内部 target/source ID、digest、request lineage 和 citation URL；输入由初始约 88,526 字符收敛为 48,380 字符。
- 模型只拥有判断、机制、反方、置信度、WWC 与结构化 ref 选择；本地只绑定身份、精确数字、日期、单位、引用和最终结构，不生成研究结论。
- fake DELL 判断成功生成 structured workpaper/report preview；未进入 Workbench 产品面。

## R1 观察

- Pack=`20 Evidence / 14 gaps`；模型可见 Evidence=`19`，其中 reviewed transcript=`5`。
- NumericFact=`45 request-level / 35 semantic unique / 25 model-visible`。
- 模型可见 gap=`10`，研究 cell=`5`。
- unknown ref、cross-cell number、自由数字叙事和缺 cell mutation 全部 fail closed。
- 调用预算：network/model/provider/embedding=`0/0/0/0`。
- 聚焦测试=`34 passed`；活动图=`109 Python / 8 frontend / 10 Runtime resources / 0 forbidden reference`。

## 业务含义

新法说证据已经允许研究节点讨论 DELL AI 订单与积压、需求高于供给、memory constraint、客户提前锁定基础设施和 AI server 盈利目标；但提前采购是否透支未来、取消/消化节奏、ASP/PVM、Dell-specific 供应分配、容量释放和估值仍是明确 gap。合格输出必须把这些边界变成反方和 WWC，而不是复述数字后宣布需求持续。

## 边界与下一项

R1 在未提交工作树执行，只是工程证据，不是 live authority。实现提交 `b4016469...` 推送后，R2 由 runner 强制验证 HEAD、upstream 和唯一未跟踪 authority，并复现相同 research input 与 deliverable digest；R2 result digest=`90574540...5974`。当前全量为 231 passed，活动图=`111 Python / 8 frontend / 10 Runtime resources / 0 forbidden reference`。下一项只允许一次 DeepSeek Pro 综合 canary；它不重跑 Planner/检索、不联网、不 retry、不发布 Workbench，成功后仍需 L1 和内容质量审阅，不能直接关闭 S3。
