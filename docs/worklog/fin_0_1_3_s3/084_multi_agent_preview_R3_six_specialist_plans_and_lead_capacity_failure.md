# FIN 0.1.3 S3 — Multi-Agent Preview R3 六角色规划与 Lead 容量失败

日期：2026-08-20

状态：`R3_terminal_failure_preserved / six_specialist_plans_valid / Research_Lead_not_completed / no_S1_or_S3_acceptance`

## 1. R3 实际跑到了哪里

R3 使用干净、已推送提交 `e887418d...` 和 fresh authority `v1.2`。DeepSeek V4 thinking 请求已不再发送不受支持的 `tool_choice`，因此 R2 的 HTTP 400 没有重现。六个 Specialist 均建立独立 AgentSession 并形成通过本地合同的规划意见：

- Demand Quality：订单、backlog、收入、出货、终端消耗以及 pull-forward／取消／推迟；
- Operating Performance：公司、分部、产品三级同口径业绩与指引；
- Value Capture：产品收入到分部／公司利润的因果桥、定价与 mix；
- Cash Conversion：经营现金流、营运资金、应收／存货／应付和 AI-specific attribution 边界；
- Supply Relationship：上游产能、披露主体、Dell-specific allocation／timing／yield；
- Counterevidence：发行人反方、上游／需求反方与可观察 WWC。

六角色合计覆盖 12 个互不重复的 facet。它们不是六份相同摘要，也没有在规划阶段把 cell-local 未加载冒充全案未披露。

## 2. 失败的准确位置

Runner 共启动 7 个逻辑模型节点、保留 11 个 Provider attempt。六个 Specialist 最终都通过，但 Operating、Value、Supply 的第一次请求各在 `3,500` completion ceiling 处截断，第二次 bounded successor 才完成严格 Tool Call。Research Lead 收到六份规划后，user message 为 `19,240` 字符、prompt 为约 `6.9k` token；两次请求都返回 HTTP 200 和完整 JSON 响应，但 `4,500/4,500` completion token 全部是 reasoning，零可见 content、零 Tool Call，因而以 `model_gateway_reasoning_budget_exhausted` fail closed。

这不是网络、API 协议、S1 召回、数据缺失或金融内容 L1 失败。最早责任层是 Multi-Agent node 将“形成分析”与“映射严格合同”塞进同一个 max-thinking Tool Call，同时 TokenBudgetBasis 没有依据六份独立计划的输入规模和 Lead 综合职责提供足够 headroom。简单把 `4,500` 改成更大常数会重复已经在 fixed-Pack 阶段证明无效的模式。

## 3. 正确 successor 边界

R3 authority、公开 terminal result、11 份 request/response capture 和六份 validated plan 保持不可变。下一次不得重跑六个成功 Specialist 规划。应先零调用生成摘要绑定的 plan checkpoint，然后从 Research Lead 处恢复：

1. 高推理调用只形成可见、受控的 Lead／workpaper／coordination／evaluation 分析草稿；
2. non-thinking 调用只把草稿映射到当前唯一 Tool Contract；
3. 分析与交卷各自具有 task-specific TokenBudgetBasis；草稿只作私有模型数据，不能晋升为 Evidence、Judgment 或报告；
4. submission 合同失败最多一个新 successor，反馈只允许修合同，不得扩展事实权限；
5. R4 只从 R3 validated plans 恢复，外源网络、Candidate promotion、产品发布、qualified-human、S1／S3／泛化／release 仍为 false。

该 successor 先做 fake、mutation、checkpoint digest 和失败回放，再经 clean push／Project OS preflight 取得 fresh authority。它的目标是完成一次诊断性真实 Multi-Agent Preview，并分别评价数据基建、Harness、Agent 编排／角色、模型判断和 Evaluator；不是为了追认 R3 或宣告 FIN 0.1.3 完成。
