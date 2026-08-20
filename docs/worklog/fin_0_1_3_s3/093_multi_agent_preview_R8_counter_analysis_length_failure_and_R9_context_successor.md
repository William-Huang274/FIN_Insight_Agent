# FIN 0.1.3 S3 — R8 Counter 分析截断与 R9 上下文 successor

日期：2026-08-20
状态：`R8_terminal_failure_preserved / analysis_fragment_checkpoint_bound / R9_zero_call_successor_pass`

## 1. R8 真实表现

R8 绑定提交 `7601ffac32cb43e09a5079d7cd8f73e5de27192a`，复用六份 Specialist plan、一个 Lead plan 和五份 capture-bound workpaper，只从 `AGENT::COUNTEREVIDENCE::WORKPAPER_R1` 开始新调用。前五份底稿没有重跑，外源网络、Candidate 晋升和发布调用均为 0。

Counter 的模型视图有 6 条 reviewed Evidence、3 个 NumericFact、2 个 typed gap；不是空资料或检索失败。真实请求为 26,365 prompt token，响应消耗 16,000 completion token，其中 reasoning 15,774，只留下 918 个可见字符，以 `finish_reason=length` 结束，0 Tool Call、0 submission。HTTP 响应完整，request／response capture 和 usage 均已保存。

## 2. 最早责任层

该失败登记为 RC-AR-009，归 S0 Agent Runtime 的上下文连续性与任务特定 token 分配：当前角色分析仍被当成 one-shot，模型把几乎全部输出预算消耗在内部推理后，Runtime 只能终止，不能基于已保存对话继续缺失部分。

它不归 S1 数据、内外源检索、排序或网络；也不归 strict submission，因为 submission 尚未发生。继续提高全局 token 上限会重复此前逐节点扩容问题，不能作为结构解法。

## 3. R9 结构处置

R9 创建通用 `AnalysisFragmentCheckpoint`，绑定：

- R8 authority／public result 和原始 request／response capture；
- 完整原始 system／user 消息；
- 918 字符 assistant 残稿及 digest；
- 已部分形成的 `thesis`；
- 仍缺失的 confidence、claims、mechanism、alternatives、counterarguments、gap refs、WWC、cross-role challenges 和 stop reason；
- 只允许一次 continuation、禁止新事实和重复已完成部分的策略。

Runtime 续写时重新构造真实同一对话：原始 system、原始 user、已保存 assistant 残稿、missing-output-only user feedback。续写使用 low reasoning／4,000 token；依据是只补九项已知输出，而不是重新研究。随后由既有 non-thinking strict submission 交卷，Harness 不写观点。

## 4. 零调用 successor 证明

R9 proof 复用六份 Specialist plan、一个 Lead plan 和五份 workpaper；Counter 初始分析新调用数为 0、analysis continuation 上限为 1。current S1/S2 物化摘要仍为 12 个 EvidenceRequest、192 个候选、44 个 typed fact request、87 个 NumericFact、六个非空角色视图。

总下游节点上限保持 10：Counter continuation＋submission 合成一个 analyzed node，随后最多一个 Lead coordination、三次 challenge repair、两轮 Evaluator、两次 evaluator repair 和一个条件式 Writer。前缀复用不获得新的 token 预算。

## 5. 当前边界与下一动作

R8 永久保持 terminal failure，不追认为成功。当前工程包只证明 capture-bound 上下文恢复设计和权限范围；尚未证明 Counter 完成、Lead 协调、Evaluator、Writer、完整报告内容质量或 S3。

下一步必须先完成 runner／Project OS 定向和全仓复证、干净提交与远端同步，再签发绑定该提交的 R9 authority。真实 R9 即使形成报告，也仍需独立 L1、八维内容质量、同输入 paired gain 和 qualified-human 内容验收；S1、S3、泛化、Workbench 发布和 release 均保持 false。

## 6. 工程复证

R9 原始对话恢复、旧 successor 兼容和 Project OS 范围门共 79 项定向测试通过；全仓 870 项测试通过。Python compileall、活动基线 `184 Python／8 frontend／27 Runtime／0 forbidden`、7,412 文件密钥扫描、8 份 Project OS JSONL 解析和 diff check 均通过。以上过程为 0 模型、0 网络、0 Provider、0 付费调用。

工程门现为通过；仍需先提交并同步这一实现，再运行 repository-aware Project OS preflight、签发一次性 R9 authority 并执行真实 successor。工程通过不等于 Counter 内容、完整 Multi-Agent Preview 或 S3 通过。
