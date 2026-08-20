# FIN 0.1.3 S3 — 紧凑 Evaluator 真实失败与分层评审处置

## 本轮做了什么

在干净且已推送的实现提交 `633ecc6d65e412781536b64ea1e1ff83c7c4bd86` 上，Project OS fresh preflight 通过后，签发并消费了唯一一次 Evaluator successor authority。运行没有重做六份 Specialist plan、Lead plan、六份工作底稿、Lead coordination 或 Demand／Cash／Supply 三条已完成修订，只从独立 Evaluator 开始。

本轮仍禁止外部来源网络、Candidate promotion、产品发布和 qualified-human 自签。原 authority、公开结果、完整 terminal failure、模型可见请求与 Provider 响应均按不可变 attempt 保存。

## 真实结果

- 六份工作底稿、一次 Lead coordination 和三条已完成反馈修订全部按 capture-bound lineage 复用；
- 只启动一个新模型节点：`EVAL::L1_AND_CONTENT::EVALUATION_R1`；
- Provider 返回 HTTP 200，响应体完整且可解析，不是网络、代理、认证或传输截断；
- prompt 为 `24,591` tokens；completion 为 `16,000` tokens；其中 reasoning 为 `16,000`，最终可见内容为 `0`，`finish_reason=length`；
- strict submission、Evaluator finding、局部修订和 Writer 均未启动；
- 公开结果保持 `multi_agent_preview_terminal_failure_preserved`，失败码为 `model_gateway_reasoning_budget_exhausted`。

与上一轮 Evaluator 相比，claim-bound `EvaluationContentView` 已完整保留六份底稿实际使用的 28 条 Evidence、19 个 NumericFact、9 个 NumericRelation 和 11 个 typed gap，同时把原 31,732-token prompt 降到 24,591 tokens。失败形态完全相同，因此不能再把问题解释为“少删了几个字段”。

## 业务上说明什么

这不是 Dell 资料为空，也不是 Supply Agent 又把上游披露冒充 Dell 事实。三条 Lead 指定的修订已经完成，研究链真正推进到了独立评审。当前阻断是把六位研究员的全部底稿和已用权威一次性交给一个 max-thinking Evaluator，让它同时检查单角色判断、经济机制、反方、WWC、跨角色冲突和最早责任层。该任务跨度仍然过大，DeepSeek 在形成任何可交付评审前耗尽全部思考额度。

本轮不能评价最终报告，因为 Writer 从未启动；也不能把“Evaluator 无输出”写成研报内容不合格。它属于 S0 Evaluator 任务分解／profile 与 S3 评审编排的共同责任，不属于 S1／S2 数据基建或六个 Specialist 的本轮输出失败。

## 冻结的结构处置

不再继续逐字段裁剪全案权威，不提高全局 token ceiling，也不自动发出第三次同型 Evaluator live。后续评审改为四层：

1. **本地完整 L1**：继续使用完整 Case Truth 检查公司身份、期间、引用存在性、精确数字、数值关系、跨案污染和 case-level absence；0 模型调用。
2. **六个角色级内容审查**：每次只读取一份最终工作底稿及其实际引用的 Evidence／NumericFact／NumericRelation／typed gap，检查判断、机制、反方和 WWC；不得重写观点。
3. **一次跨角色审查**：只读取六份已审结论、必要的 claim／mechanism 摘要和 Lead coordination lineage，检查互相矛盾、重复计算、口径冲突和综合缺口；不再重复装载完整金融权威目录。
4. **有界局部修订**：只有 `agent_orchestration_and_role_design` 或 `model_judgment` 的阻断 finding 才回到最早责任 Agent，最多两处；修订后只重审受影响角色并做一次跨角色复核。数据／工具或 Harness finding 直接停止，不让模型修文掩盖上游故障。

Evaluator 分层调用使用既有 DeepSeek V4 Pro `high / 12,000` 角色级分析 profile 与独立 non-thinking strict submission；理由是任务已缩成单角色或跨角色一致性检查，而非再次完成整案研究。最大新逻辑节点按真实职责编译为：六次角色审查＋一次跨角色审查＋最多两次局部修订＋最多两次受影响角色复审＋一次跨角色复核＋条件式 Writer，共 13。该上限来自工作量与质量风险，不来自省钱或追求速度。

若任一单角色审查仍以 reasoning-only exhaustion 失败，则说明当前 DeepSeek profile 不适合独立评审职责；届时必须做模型／profile 选择，不得继续为它扩建字段级专用迷宫。

## 当前边界

- Multi-Agent 自然规划、六份底稿、Lead 协调和三条反馈修订：已发生；
- 分层 Evaluator：尚未实现或真实验证；
- Writer 与完整 DELL 报告：尚未运行；
- 独立 L1、八维质量、paired gain、qualified-human：尚未完成；
- S1、S3、泛化、Workbench 产品发布与 release：均未通过。

