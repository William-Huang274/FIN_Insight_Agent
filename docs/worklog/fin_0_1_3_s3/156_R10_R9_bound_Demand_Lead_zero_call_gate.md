# R10：R9-bound Demand＋Lead 零调用 successor 门

## 结论

R9 继续保持不可变的“结构合同通过、内容 L1 失败”证据，Writer 没有解冻。本轮没有发起任何模型、Provider、网络、检索或外源调用；只把独立复评留下的一个跨角色 cohort 错误编译为一条精确 Demand `FeedbackReceipt`，并证明未来 successor 的首个新节点只能是 Demand analysis，完整上限只能是 Demand analysis／submission 与 Lead analysis／submission 共 4 次。

零调用公开证明为：

- `configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_content_reassessment_resume_zero_call_result_v1_0.json`
- `result_digest=edc80958342f25754ce1ef0389d2bc8c23500a875f7536aabc5c33f6193280c2`
- `sha256=969e1380c27bc5ff04ac83d3819d452eef60352d2a1d90f97fbf7d3d3b822528`
- 首个 fresh frontier：`demand-quality-repair-r6-draft`
- `model_calls=provider_calls=network_calls=retrieval_calls=0`

## 最早责任层与处置

R9 的原七项 finding 已关闭 6 项。剩余问题不是数据、S1/S2、检索、Provider 或 transport：Demand 的 thesis 与 `strongest_counterarguments[1]` 仍把同季 `$24.4B` 订单和 `$16.1B` 已确认收入写成同一批订单已部分转化，而同一底稿又承认没有 order cohort。R9 Lead 也把这项 recheck 误判为已满足。

最早项目责任层是跨角色 semantic repair coverage：原 finding 只路由给 Operating，通用“同期间共现不等于 cohort 转化”规则没有重新覆盖复用 Demand 的全部叙事字段。该残余继续由 `RC-S3-075` 阻断，并登记为 `RC-S3-087`。

## 上下文连续性修复

R9 Demand 的持久化上下文是 repair-context schema，不能再直接嵌套一层 repair；若简单退回 R5 base context，又会丢失 R9 已消费的独立内容反馈，可能修复 cohort 时回归 pull-forward 边界。

当前实现先验证 R9 repair context 可由 rebound base context、原 prior workpaper 和新增反馈逐字节重编译，再只把已验证的反馈历史滚回 base-context schema：

- base feedback：2 条 S1/S2 feedback；
- R9 后 feedback：3 条，新增 1 条独立内容反馈；
- R10 模板：在这 3 条历史之后加入唯一的新 cross-role feedback，模型可见共 4 条；
- Evidence、NumericFact、Relation、gap、graph、case 与 authority 输入不变；
- 新 feedback 的 `created_at` 固定绑定 R9 独立 assessment 的 `2026-08-24T03:06:38+08:00`，因此 live 必须精确复现零调用 `repair_context_digest=8e21e00c...b56f`，不能因运行时间重新编译出另一上下文。

## 精确挑战与拓扑

挑战只接受：

- source workpaper digest：`147e1aca...f912`；
- target：`AGENT::DEMAND_QUALITY`；
- surfaces：`thesis`、`strongest_counterarguments[1]`；
- parent issue：`RC-S3-075`；
- residual issue：`RC-S3-087`；
- requested action：`repair_cross_role_same_period_cohort_conversion`。

其余 Cash、Counterevidence、Operating、Supply、Value 五份 R9 workpaper 必须逐字节复用。四节点 fake Provider seam 已验证真实运行分支的调用顺序为：

1. Demand analysis；
2. Demand strict submission；
3. Lead analysis；
4. Lead strict submission。

任何 transport、length、schema、authority、context-digest 或本地验证失败都终止当前 attempt，0 retry／fallback；Writer 始终为 false。

## Project OS 与历史授权边界

新 scope decision 为：

- `configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_content_reassessment_resume_scope_decision_v1_0.json`
- scope：`one_R9_bound_Demand_cross_role_cohort_repair_then_Lead_recheck`
- max Provider calls：4；
- 0 S1/S2、retrieval、external source、promotion、retry、fallback、Writer、publication、release；
- 四类节点各有一份 task-specific `TokenBudgetBasis`。

R10 扩展 runner 后，已消费的 R9 scope decision 会按其原 runtime SHA 正确失效。旧决策与 R9 authority 均不改写，也不放宽 hash；回归测试明确区分“不可变历史证据”与“当前可签新 authority 的决策”。只有新的 R10 decision 可以进入当前 preflight。

## 当前验证

- content-repair／Project OS 综合定向：`115 passed`；
- R10 真实四节点 fake seam、完整 R9 authority／public／private／assessment validator、surface／workpaper／feedback-lineage mutation 均通过；
- 全仓：`1155 passed, 2 warnings`，仅两条既有 SWIG deprecation warning；
- `compileall`、`pyflakes` 与 `git diff --check` 通过；
- active baseline：`211 Python／8 frontend／5 detectors／28 Runtime／0 forbidden`；
- 948 份 configs JSON 与 8 份 Project OS JSONL／1,058 行全部可解析；
- repository secret scan：7,803 files／0 findings；
- working-tree preflight 已走到唯一预期失败：`project_os_repository_not_clean`，说明 decision、artifact、scope、credential 和 TokenBudgetBasis 验证已先通过；
- clean commit／push、repository-aware fresh preflight、fresh R10 authority 与 live 均仍待完成。

## 不得误报

零调用证明与 fake seam 不证明自然 Demand 修复质量、Lead 质量、独立 L1／L2、内容质量、Writer 报告、S3、产品接受、异质泛化、Workbench publication 或 release。即使未来 4 次调用合同通过，也必须再次独立复评，不能直接进入 Writer。
