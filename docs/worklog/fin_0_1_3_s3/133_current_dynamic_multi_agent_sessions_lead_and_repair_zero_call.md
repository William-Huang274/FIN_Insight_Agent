# FIN 0.1.3 S3 current 动态多 Agent 会话、Lead 与定向修订零调用复证

时间：2026-08-23

## 本轮回答的问题

本轮不再沿用旧的 fixed five-cell runner，也不把六份预制底稿称为多 Agent。目标是用 current DELL S1/S2 Runtime 证明以下真实编排骨架：

1. 六个 Specialist 分别拥有独立 `AgentSession`、任务范围、请求预算和局部上下文；
2. 每个 Specialist 实际执行自己负责的 S1/S2 请求并接收完整 `FeedbackReceipt`；
3. 模型可在本地预编译的请求集合中选路，但候选不能自动晋升 Evidence；
4. Specialist 形成可校验底稿，Lead 只协调冲突与回派，不能创作新事实；
5. Lead 的挑战能回到唯一责任角色，并在不增加 Evidence/NumericFact 权限的情况下完成定向修订；
6. checkpoint/resume 可在 Specialist 和 Lead 会话中重放。

本轮全部使用零模型 fixture；它验证 Harness／编排，不评价 DeepSeek 自然研究质量。

## 第一项结构问题：全案 ceiling 早于角色分工

旧路径先对全案套 12 条执行上限，再分配角色；当前规划有 13 个 material facet，因此 `counterparty_direct_mention` 可能在模型调用前被静默丢弃。这不是模型或信源问题，而是 S3 Planner 到角色执行的顺序错误。

修复后，13 个 facet 先按六角色编译为 `2／2／2／2／3／2`，再在各角色内部应用轮次和请求预算。系统同时验证 facet 不重叠、不遗漏，角色划分先于执行 ceiling。该问题登记为 `RC-S3-066`。

## R1 与 R2 零调用结果

- R1 完成六会话、12 个实际检索批次和 Lead 协调，但错误地把“请求目录耗尽”写成 `stop_sufficient`。R1 保持不可变，未被追认为正确证明。
- 修复停止语义后运行 R2：有剩余 gap 或 feedback 时必须是 `stop_no_progress`；只有没有下一请求、没有 gap、没有 feedback 才允许 `stop_sufficient`。
- R2 执行 13 条角色请求、12 个实际 retrieval batch；使用 current 48-Evidence Pack，未晋升任何 Candidate。
- 六角色合计看见 21 个唯一 reviewed Evidence、22 个唯一 NumericFact、10 个 residual gap 和 16 条 FeedbackReceipt。
- Demand／Operating／Value／Cash／Supply／Counterevidence 六个角色全部正确停止为 `stop_no_progress`。其中 Supply 只有 1 条 Evidence、0 NumericFact、3 个 gap，是当前 DELL 多 Agent 中最薄弱的业务角色；这属于后续自然研究与补证需要观察的真实边界，不由 Harness 伪装成充分。
- Lead 接受一条 `Counterevidence → ValueCapture` 挑战，进入 `continue_local_repairs`。
- CUDA receipt 证明 Qwen dense 使用 `cuda:0`、RTX 4060 Laptop GPU、FP16。

权威公开结果：

- `configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_zero_call_result_v1_0.json`
- private R2：`data/workbench_private/fin_0_1_3_s3_current_dynamic_multi_agent/dell-current-dynamic-multi-agent-zero-call-r2-20260823T071415Z/zero_call_full_result.json`

## 第二项结构问题：底稿摘要被二次摘要

首次 repair successor 在调用模型、网络或检索前，以 `dynamic_single_unit_repair_prior_workpaper_invalid` 失败。审计证明底稿正文、引用、身份和上下文均可重验；runner 在 Validator 已生成 `workpaper_digest` 后又对包含该 digest 的对象整体摘要一次，形成可精确重现的 legacy double hash。

处置没有改写 R2：

1. 对六份持久化底稿去除派生字段后重新执行同一 Validator；
2. 只有保存值严格等于“正确 digest 再被摘要一次”的已知缺陷形式时才允许迁移；
3. 为每份底稿生成 normalization receipt，明确 `content_changed=false`、`authority_refs_changed=false`；
4. 因 challenge ID 绑定 source workpaper digest，按相同语义字段重新生成 challenge，并保存旧新 challenge 的迁移凭证；
5. 新 runner 不再二次计算 Validator 已生成的 digest。

该问题登记为 `RC-S3-067`。失败的 repair R1 identity 保持 consumed；新 repair R2 复用了六会话和 12 个检索批次。

## 定向修订 successor 结果

`dell-current-dynamic-multi-agent-zero-call-repair-r2-20260823T073500Z` 全部门通过：

- 六份 legacy digest 均被精确重现并规范化；
- Lead 原挑战的语义、来源角色和目标角色不变；
- 仅 `AGENT::VALUE_CAPTURE` 底稿变化；
- 修订前后 Evidence、NumericFact、NumericRelation 和 gap ref 集合完全相同；
- repair context 明确禁止增加任何事实或数字权限；
- Specialist checkpoint/resume 成功；
- Lead 复核后进入 `proceed_to_evaluation`；
- 0 模型、0 网络、0 工具调用、0 新检索、0 Candidate 晋升。

公开结果：`configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_zero_call_repair_successor_result_v1_0.json`。

## 工程复证

- 定向动态 loop 测试：`13 passed`；
- 全仓：`1113 passed`，仅两条既有 SWIG deprecation warning；
- `compileall` 通过；
- Workbench TypeScript typecheck 与 production build 通过；
- active baseline：`210 Python／8 frontend／5 detectors／28 Runtime／0 forbidden`；
- config JSON：908 份有效；Project OS JSONL：8 份、986 行有效；
- secret scan：7,739 文件、0 finding；
- `git diff --check` 无内容错误，只有生成 manifest 的行尾提示。

## 当前真实边界与下一步

当前只证明六角色动态 Runtime、Lead 回派和会话连续性在确定性输入下可执行。它没有证明：DeepSeek 会自然选择好请求、正确反思、写出六份高质量底稿，Lead 会自然协调，或 DELL 完整报告内容合格。

下一门必须是干净提交／推送后的 Project OS preflight，再为同一个 canonical runner 签发一次 DELL 动态多 Agent live。Natural live 必须逐角色保存任务级 `TokenBudgetBasis`，失败节点可用 successor 复用，不能重跑已成功角色；完成 L1 与内容质量验收后才进入 Writer、MU／NVDA 和异质留出。

## 2026-08-23 live 传输接入与 R3/R4 复证

正式 live 没有新建另一套 runner，而是在同一 `run_s3_current_dynamic_multi_agent.py` 增加 authority-bound live mode：

- 六个 Specialist 各自从问题、公司、截至日期和角色本地工具目录开始，初始消息不含 Evidence；
- 每个角色最多两轮检索，模型选择 request，current S1/S2 返回 EvidenceResponse 和完整 FeedbackReceipt，模型再反思、改计划或停止；
- request/reflection/Lead 使用已验证的 DeepSeek GA `thinking=max` provider-neutral transport，明确不发送 thinking 模式不支持的 forced `tool_choice`；
- workpaper 和 role-local repair 使用独立 non-thinking 提交 profile，避免研究推理挤占严格交卷容量；
- 六个角色相互独立，一个失败不删除其他角色已经完成的 session、capture、检索或 workpaper；只有六份 workpaper 都有效时 Lead 才启动；
- Lead 最多两轮、最多接受三项 role-local repair；修订前后 Evidence、NumericFact、Relation 和 gap 权限集合必须完全相同；
- 最大 29 次 Provider attempt 来自 `6 × 4 specialist + 2 Lead + 3 repair` 的可解释拓扑上界，不是为了省钱随手设置的全局调用数。实际角色若首轮已充分会少于该值。

同时将 loop policy 从遗留 Chat profile 切换到已资格验证的 v1.1 transport，并增加 non-thinking submission profile。因此重新执行 R3 全链零调用：六会话、13 请求、12 个真实 CUDA S1/S2 batch、Lead 路由全部通过。R3 生成的 workpaper 已直接是 canonical digest；旧 successor 原本强制要求“六份都必须是 legacy double-hash”，在新正确输入上误判失败。该门已改为“canonical 或可精确重现的 legacy migration 均可”，R4 successor 随后通过，legacy normalization 数量正确为 0，研究内容和权限没有变化。该迁移门问题登记为 `RC-S3-068`。

新的 live scope decision 已绑定：R3 zero-call、R4 repair successor、两种 provider profile、13 请求／12 round／29 provider attempt ceiling、五类 task-specific TokenBudgetBasis，以及禁止外源网络、Candidate promotion、S1/S3 acceptance、Writer、Workbench publication 和 release 的边界。下一步是全仓验证、干净提交／推送、repository-aware preflight，再签发唯一自然 live authority。

正式门禁前又发现并关闭一项审计口径风险：旧计数器只在 Provider 成功返回后递增，传输失败可能少算一次已经发生的 attempt；repair 失败时，追加在临时事件副本中的 requested／failed 事件也可能无法进入终态。当前统一以 canonical `provider_attempt_requested` 事件计数，repair 直接续写本次 live 的角色事件流；失败路径测试证明一次失败仍被记为一次 attempt。该修复不改变模型输入、研究权限或 29 次拓扑上界。

本次 live 接入后的完整工程门为：定向 `82 passed`；全仓 `1118 passed`，仅两条既有 SWIG deprecation warning；Python compileall、Workbench TypeScript typecheck／Vite production build、active baseline `210 Python／8 frontend／5 detector／28 Runtime／0 forbidden`、`909` 份 config JSON、`8` 份 Project OS JSONL／`988` 行、`7,740` 文件 secret scan／0 finding 和 diff check 全部通过。该结果仍只授权干净提交、fresh preflight 和 exact-once live，不构成自然多 Agent 或 S3 内容验收。
