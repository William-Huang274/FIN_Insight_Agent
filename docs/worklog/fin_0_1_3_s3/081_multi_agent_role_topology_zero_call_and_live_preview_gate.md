# S3 多角色 Agent 拓扑、零调用复证与 Live Preview Gate

## 1. 本轮为什么不是继续跑旧五单元

旧 DELL 五单元由同一 Provider 按固定顺序完成五个研究节点。它证明五类研究问题可以被调用，却没有独立 `AgentSession`、角色计划意见、工具失败反馈、checkpoint/resume、Research Lead 挑战路由或 Writer Agent，因此不能再被称为真正 Multi-Agent 证明。

本轮先按产品责任把对象分成五类：真正 Agent、工具、Evaluator、纯路由标签和 Harness。真正 Agent 的最低条件是独立目标、会话、受限工具、工作底稿、可消费 `FeedbackReceipt` 并在受控范围内修正判断；工具只查找、读取、计算或渲染；Evaluator 只检查；标签没有自主状态；Harness 管理身份、期间、证据晋升、上下文、停止和审计但不写观点。

## 2. 当前角色和资料资格

Preview 激活 Research Lead、需求质量、经营表现、价值获取、现金转换、供应链／关系、独立反方和实验性 Writer。估值、资本和独立行业角色当前仍是标签，因为生产级 PIT 行情、行业主源和商业分配数据没有形成合格工具路线；用空角色凑数会把数据缺失错误归因成 Agent 无用。

当前 DELL Pack 可支持公司经营与现金、AI 订单／收入／backlog／客户数、部分供给背景和发行人反方。它不能证明 Dell 特定上游分配、取消和 backlog 账龄、产品利润桥、完整行业份额或 PIT 估值。以上边界在 Preview 中必须保留为 named gap 或工具状态，不得由模型补写。

## 3. 零调用过程中发现的最早责任层

### RC-S1-048：动态候选重选错误覆盖已审 Evidence

Hybrid candidate 结果曾完全替代 immutable snapshot candidate，导致 reviewed Evidence 明明存在却从角色视图消失。根因属于 Harness／候选合并，不是来源不存在，也不是 Agent 判断失败。当前已改为 candidate-only union；它不能晋升新 Evidence。

该修复以显式 successor policy v1.1 进入 Preview；历史 policy v1.0 继续保持 hybrid-only 回放语义。这样既修复当前产品链，又不改写旧 R6 等不可变 attempt 的输入摘要。

### 角色读取器和动态检索必须分开

继续审计发现，动态重选不应成为读取既有 reviewed Evidence 的唯一入口。真正拓扑现在暴露两个不同工具：

- exact reviewed Evidence reader：按 slot 读取当前已审权威；
- dynamic S1 retrieval：为新问题返回候选与执行回执。

后者失败不能擦掉前者，也不能自动生成 public gap。角色上下文以 exact reader 为权威，动态检索只附带工具执行回执。

### RC-S1-049：上游与关系动态召回仍弱

当前 reviewed Pack 中有 10 条 capacity／relationship Evidence，但冻结动态检索的上游目标没有进入候选池，`counterparty_direct_mention` 也没有叙事候选。这是 S1 query／object／recall／ranking 待修问题；Supply Agent 仍可用 exact reader 做当前 Preview，但该 Preview不能冒充动态外源或完整 Agentic Search 通过。

## 4. 零调用复证结果

`v1.2` 在 0 模型、0 网络、0 付费调用下通过：

- 12 个真实 EvidenceRequest；
- 192 个 hybrid selected candidate；
- 40 个 typed fact request，25 resolved、15 typed gap；
- 6 个专业角色均有非空权威视图；
- Demand 10 Evidence；Operating 2 Evidence／12 NumericFact／6 relation；Value 4／10／5；Cash 5／10／3；Supply 10 Evidence；Counterevidence 6 Evidence／1 NumericFact；
- Candidate promotion=0，S1 pass=false，S3 pass=false。

## 5. Live Preview 的真实运行合同

Live 不把旧五节点套壳，而是：六个专业 Agent 独立计划；Lead 合并；本地 S1/S2／Evidence reader 只执行一次；六个角色独立写底稿；反方提出结构化挑战；Lead 最多接受三项局部返工并把数据／Harness 缺陷退回原层；受影响角色 checkpoint/resume 后重写；独立 Evaluator 检查并最多触发两项角色修正；只有最终 `report_may_proceed=true` 才激活 Writer。

每个模型节点单独生成 `TokenBudgetBasis`。本轮最多 22 个模型节点、每节点最多一个有独立 Attempt ID 的 bounded successor、最多三次反方返工、两次 Evaluator 返工和两轮评估。任何 Provider／合同失败均先保存 request、assistant output、usage、finish reason 和 capture；不允许 candidate 晋升、外部来源网络调用、产品发布或 qualified-human 自签。

## 6. 当前 Gate

实现、合同和零调用复证已完成；定向 26 tests、全仓 831 tests、Python compileall、活动基线 `183 Python / 8 frontend / 27 Runtime / 0 forbidden` 和 7,355 文件秘密扫描均通过。公开结果会分开“声明的 Agent”与“本次实际激活的 Agent”，避免在 Writer 被内容门阻断时仍把它计作已运行。正式 Live 必须先在干净、已推送实现提交上另行签发一次 authority。Live 只评价当前 DELL 资料边界内的多角色规划、分工、反馈、修正、停止和成稿，不签发 S1、S3、泛化、Workbench 发布或 release。
