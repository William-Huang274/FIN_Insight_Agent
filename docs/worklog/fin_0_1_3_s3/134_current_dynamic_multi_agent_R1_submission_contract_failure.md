# FIN 0.1.3 S3 DELL current 动态多 Agent R1 提交合同失败

时间：2026-08-23

状态：`R1_immutable_terminal / current_S1_S2_executed / project_submission_seam_root_cause_confirmed / capture_bound_successor_required`

## 这次真实运行实际完成了什么

R1 是 current DELL 六 Specialist 动态多 Agent 的第一次自然运行，不是 fixed Pack 回放。六个 Specialist 都从公司身份、截至日期、角色问题和工具目录开始，自主选择第一轮请求；current S1/S2 随后真实返回 reviewed Evidence、NumericFact、关系和 FeedbackReceipt。

- 六个独立 Specialist session 全部创建；
- 12 个不重复 EvidenceRequest 在 6 个 CUDA/FP16 retrieval round 中实际执行；
- 14 次 DeepSeek GA Provider attempt 全部 HTTP 200、`finish_reason=tool_calls`，0 retry；
- 0 外源网络、0 Candidate promotion、0 fallback；
- Demand 看见 8 条 Evidence；Operating 看见 2 条 Evidence、12 条 NumericFact；Value 看见 3／10；Cash 看见 5／10；Supply 看见 1／0；Counterevidence 看见 5／3；
- 六个 Agent 都在提交 reflection 或 workpaper 时失败，因此 Lead 没有启动，不能形成完整多 Agent judgment，更不能进入 Writer。

公开结果：`configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_live_result_v1_0.json`。

受限完整结果：`data/workbench_private/fin_0_1_3_s3_current_dynamic_multi_agent/dell-current-dynamic-multi-agent-live-r1-20260823T171000Z/full_result.json`。原始模型可见请求和最终 assistant Tool Call 全部保存在 `.codex_runtime/model_runs/fin_0_1_3_s3_current_dynamic_multi_agent_live_r1/`，不保存凭据或 Provider 私有推理。

## 四个表象其实是同一个结构问题

### 1. 研究分析和严格交卷仍被当成一次动作

Demand 的 workpaper、Operating 的 reflection、Supply 的 reflection 都形成了完整 Tool Call，但参数字符串包含未转义引号或多余闭括号。模型已经做了研究，不代表该字符串已经是可验证 JSON。当前 Runtime 在 thinking-heavy 分析调用后直接把 Tool Call 当成最终合同，因此一个语法字符会否定整个角色。

### 2. 本地身份元数据仍错误地交给模型填写

Counterevidence 的 workpaper 有 8 条有引用的实质 claim，但漏了 `schema_version`。在不修改任何研究字段、只由本地注入已绑定 schema version 后，同一 payload 可通过完整 Validator，得到 canonical workpaper digest `c2c6fb3ae8bbe4f777f9b3bdf26a58c261d94a55927c7c11f49a47aff56ade74`。schema version、agent identity 和 lineage 属于 Harness envelope，不应成为模型研究能力测试。

### 3. Graph predicate 与研究叙事没有分面提交

Value 和 Cash 提交的图关系包含完整经济机制、数字和期间说明，超过 120 字符的 compact edge predicate 上限；这些信息本应进入 `research_use`。这不是应当放宽成任意长 Graph edge，也不是错误研究方向，而是 Tool Schema 没有把“关系原子”和“为什么值得研究”拆成清晰的提交视图。

### 4. 模型的停止建议与 Harness 的正式 StopDecision 漂移

zero-call 多 Agent 合同规定：没有下一请求但仍有 gap 或 FeedbackReceipt 时只能 `stop_no_progress`；只有无下一请求、无 gap、无 feedback 才能 `stop_sufficient`。live reflection Validator 却仍允许模型在有 gap／feedback 时提交 `stop_sufficient`，只在覆盖组不全时才晚一步拒绝。模型可以提出停止建议，但正式 StopDecision 必须由本地按 coverage、剩余可执行请求、gap 和 feedback 编译。

## 最早责任层与不应做的事

最早责任层是 S3 provider-neutral submission／control compiler，不是 S1 检索、S2 数值、外源信号不足或 DeepSeek 连通性。R1 甚至还没有进入可评价六份 workpaper 内容质量的状态。

因此不得：

- 重跑已经完成的 12 个 request 或 6 个 retrieval round；
- 把失败归因成“DeepSeek 不会研究”并继续扩写 Prompt；
- 逐字段提高字符上限或给每个 Agent 写专用补丁；
- 让 Harness 改写模型观点、经济机制或引用；
- 把 Counterevidence 的本地 envelope 修复冒充一次新模型成功。

## 有界 successor

下一包只实现一套共享的提交结构：

1. thinking 调用产生可见研究草稿，non-thinking submission profile 把草稿映射成严格合同；
2. schema version、agent/session/round identity 和 lineage 由本地 binder 注入；
3. Graph edge 只提交 compact predicate，解释保留在 `research_use`；
4. Harness 从模型建议、coverage、剩余请求、gap 和 feedback 编译正式 StopDecision；
5. successor 复用 R1 的 request selection、S1/S2 返回、FeedbackReceipt 和有效研究草稿，只从失败节点续跑；
6. Counterevidence workpaper 只做零调用 envelope requalification；Supply 若选择剩余第三条请求，只执行该新增请求，不重跑前两条；
7. 六份有效 workpaper 后才允许 Lead，Lead 仍最多两轮、最多三项 role-local repair，所有 repair 的事实和引用权限不变。

该 successor 先做 capture replay、fake 和 mutation；通过后才可签发新的 exact-once authority。它仍不构成 S3、Writer、Workbench、产品或 release 验收。
