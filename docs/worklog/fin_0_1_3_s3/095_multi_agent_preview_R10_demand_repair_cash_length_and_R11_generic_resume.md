# FIN 0.1.3 S3 — R10 Demand 修订、Cash 分析截断与 R11 通用续跑

日期：2026-08-20
状态：`R10_terminal_failure_preserved / Demand_repair_valid / Cash_fragment_bound / R11_full_engineering_gate_pass`

## 1. R10 的真实业务进展

R10 没有重跑六份 Specialist plan、Lead plan、六份初始工作底稿或 Lead coordination。它直接从 R9 已接受的三条 challenge 开始。

Demand Agent 完成了第一条局部修订并通过 strict contract。相较旧底稿，修订后的业务变化是：

- 不再把订单和 backlog 当成需求可持续性的充分证明；
- `$16.1B` 只用于说明同季度订单向收入的转换，不外推未来持续性；
- 明确列出 buy-ahead、供给约束和客户集中可能造成的替代解释；
- 置信度由 high 调整为 moderate。

因此，当前至少证明了一次真实的 `Counter challenge → Lead 接受 → 原角色读取反馈 → 判断收窄`。这不是只生成 FeedbackReceipt 而业务内容不变。

## 2. 为什么 R10 仍失败

Cash Agent 随后开始处理第二条 challenge。模型可见请求为 30,202 prompt token；12,000 completion token 中 11,802 为 reasoning，最终只返回 815 字可见分析并以 `finish_reason=length` 结束。尚未进入 strict submission，Supply、Evaluator 和 Writer 均未运行。

该失败不应归因于：

- S1 没有返回任何材料；
- 网络或外源抓取失败；
- Lead 路由错误；
- DeepSeek 拒绝读取反馈；
- Cash 业务结论被 Validator 判错。

最早责任层是 S0 Agent Runtime：项目已有通用分析片段 checkpoint／resume，但此前只接入 Lead 与初始 Counter 路径，没有接入任意 downstream repair。登记为 `RC-AR-011`。R10 authority、公开结果、terminal、Demand 节点和 Cash request／response capture 全部保持不可变。

## 3. R11 的结构处置

新增 provider-neutral `DownstreamRepairProgressCheckpoint`，它不认识 Dell Cash 的业务字段，只认识：

- ordered accepted challenge IDs；
- 已完成且经过验证的 repair payload；
- pending challenge IDs；
- 当前 active `AnalysisFragmentCheckpoint`；
- source authority／public result／terminal result／Lead coordination lineage；
- 已完成节点禁止重跑、active fragment 仅续写一次的恢复策略。

R11 将 R10 Demand workpaper digest `3914ddf8...47e0` 标为已完成，把 Cash 和 Supply 保留为 pending，并把 Cash 原始 system／user 消息、request／response capture、815 字草稿和缺失四类修订输出绑定到 checkpoint。运行时复用 Demand，只从 Cash continuation 开始。

## 4. 零调用验收与预算依据

已完成的定向验收包括：

- 精确恢复 Demand validated payload；
- 精确恢复 Cash 815 字残稿和两条原始模型可见消息；
- 已完成 workpaper digest mutation fail closed；
- Cash capture digest mutation fail closed；
- accepted challenge 顺序 mutation fail closed；
- Project OS scope validator 重新核对 R10 authority、public／private terminal、三个 checkpoint、continuation profile 和历史 scope lineage。

定向合同、Runtime 与 Project OS 共 `80 passed`；全仓 `884 passed`，仅有本地向量依赖的 2 条既有 SWIG 弃用 warning。`compileall`、活动基线 `184 Python／8 frontend／5 detectors／27 Runtime／0 forbidden`、8 份 Project OS JSONL、7,426 文件 secret scan 和 `git diff --check` 全部通过。期间发现最新 RC-AR-002 账本行曾只保留 R11 scope、令七条旧 successor preflight 失去可重放资格；现已恢复累计历史 scope，同时保持 R11 新权限不变。

最大新逻辑节点为 7：Cash continuation＋submission 计一个 repair 节点，Supply 一个，最多两轮 Evaluator、两次 evaluator repair 和一个条件式 Writer。减少一节点的原因是 Demand 已完成，不是为了省 token。每个新分析／交卷阶段仍按输入规模、所需输出、合同负担、业务风险、历史运行、reasoning profile 和停止策略生成独立 `TokenBudgetBasis`。

## 5. 当前边界与下一步

当前已达到 full engineering gate。还需：

1. 精确提交并推送 clean engineering commit；
2. repository-aware Project OS preflight；
3. 签发绑定该提交的唯一 R11 authority；
4. 执行 R11，并根据完整链结果区分数据基建、Harness、Agent 编排／角色、模型判断和 Evaluator；
5. 若形成报告，再做独立 L1、八维内容质量、paired gain 和 qualified-human 验收。

R11 不能自动声明 S1、S3、泛化、Workbench publication、S5 或 release 通过。
