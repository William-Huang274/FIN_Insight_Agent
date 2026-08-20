# FIN 0.1.3 S3 — R9 协调容量失败与 R10 检查点下游续跑

日期：2026-08-20
状态：`R9_terminal_failure_preserved / six_workpapers_and_Lead_coordination_bound / R10_targeted_engineering_pass`

## 1. R9 到底完成了什么

R9 没有重跑 R3 的六份 Specialist plan、R6 Lead plan 或 R8 前五份工作底稿。它从 R8 Counter 残稿恢复同一模型对话，完成缺失分析并通过 strict submission。至此六个专业 Agent 均有真实模型生成、合同通过且 capture-bound 的工作底稿。

Research Lead 随后消费六份底稿和 challenge catalog，连续两次返回同一业务分流：

- 接受 Demand Quality 修订；
- 接受 Cash Conversion 修订；
- 接受 Supply／Relationship 修订；
- 延期 Value Capture 修订，因为当前要求需要新增 Evidence，不能在无新权威时补写。

这证明至少在当前 DELL 资料边界内，专业角色差异、独立 Counter 挑战和 Lead 局部路由已经自然发生。它尚未证明修订质量、Evaluator、Writer 或最终报告。

## 2. 为什么 R9 仍然失败

Lead 两次协调理由分别约为 2,013 和 1,799 字。旧 Tool Schema／Validator 把 rationale 固定为最多 1,200 字，并把失败映射为 `multi_agent_lead_coordination_identity_invalid`。模型没有选错角色、challenge 或下一状态；第二次压缩后仍保持相同分流。

因此 RC-AR-010 的最早责任层是 S0 Harness 合同容量和错误分类：

- 不是 S1 数据／检索／排序；
- 不是 Provider transport 或网络；
- 不是 DeepSeek 不理解任务；
- 不是 Agent 编排没有发生；
- 不是内容 Evaluator 拒绝报告，因为 Evaluator 尚未启动。

R9 authority、public result、terminal result、全部 capture 和 attempts 保持不可变，不能改写为成功。

## 3. R10 的结构修复

协调 rationale 的容量改为从 challenge 数编译：`min(4000, max(1200, 600 + 400 × challenge_count))`。本案四条 challenge 得到 2,200 字，保留 401 字余量。Schema、Validator、Prompt 约束和测试使用同一个 compiler，不再各写一个常量。

新 `LeadCoordinationCheckpoint` 绑定：

- R9 authority／public result／terminal result；
- R9 Counter continuation／submission attempts 和 payload digest；
- R9 Lead accepted attempt 的 request／response capture sha256 与 digest；
- 六份 workpaper digest；
- 四条 challenge、三条 accepted、一条 deferred 和 coordination decision digest；
- Session checkpoint／resume policy。

任何 terminal、capture、challenge、workpaper 或 digest mutation 都 fail closed。

## 4. R10 运行边界

R10 禁止重跑六份 plan、Lead plan、六份 workpaper和 Lead coordination。第一新节点只能是 accepted challenge repair，目标分别为 Demand Quality、Cash Conversion 和 Supply／Relationship。之后最多两轮独立 Evaluator、两次 evaluator 指定的局部 repair 和一个条件式 Writer，总新模型节点上限为八。

延期的 Value Capture challenge 不进入本轮，因为它要求新的 Evidence，而 R10 明确是 0 外源网络、0 Candidate promotion 的同输入下游续跑。这个延期不是漏题，而是对权限和资料边界的正确遵守。

## 5. 当前验证

- coordination capacity 编译与 max+1 mutation 通过；
- exact Counter／Lead capture recovery 通过；
- terminal digest 和 Lead response capture mutation 被拒绝；
- R10 authority schema／Project OS 历史 scope 回归通过；
- 定向四组共 88 tests passed；
- 全仓 879 tests passed，仅保留本地向量库 SWIG 类型的两条既有弃用 warning；
- `compileall`、active baseline `184 Python／8 frontend／5 detectors／27 Runtime／0 forbidden`、8 份 Project OS JSONL、7,419-file secret scan 和 `git diff --check` 全部通过。

干净提交／push、Project OS preflight 和真实 R10 尚未完成，因此当前只记 engineering／zero-call gate，不得声称 Preview 或 S3 通过。

## 6. 下一步

1. 精确暂存、提交并推送当前工程包；
2. 在 clean／synced commit 上运行 Project OS preflight；
3. 签发唯一一次 R10 execution authority；
4. 执行 R10 下游 live；
5. 成功后独立做 L1、八维质量、paired gain 和 qualified-human 内容验收。

普通 Provider 连通性或局部合同失败按最早责任层保留新 attempt 并有界修复；只有产品范围、付费数据／采购、模型路线、跨单元新 L1 或进入 S4／S5 的实质变化才需要 Owner 决策。
