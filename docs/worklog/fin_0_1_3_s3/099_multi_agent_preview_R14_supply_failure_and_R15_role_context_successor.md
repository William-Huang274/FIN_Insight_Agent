# FIN 0.1.3 S3 — R14 Supply 推理耗尽与 R15 角色上下文 successor

日期：2026-08-20
状态：`R14_terminal_failure_preserved / Demand_and_Cash_repairs_preserved / role_scoped_repair_context_full_engineering_gate_pass / R15_clean_commit_push_preflight_pending`

## 1. R14 实际完成了什么

R14 在 clean／synced commit `d6d8bc98...` 与 fresh Project OS preflight 下执行。它没有重跑 Specialist plan、Lead plan、六份初始底稿、Lead coordination 或已完成 Demand repair。

Cash repair 使用 R13 保存的原对话和分析片段，以显式 non-thinking continuation 补完缺失字段，并经过 strict submission。第一次 submission 因 claim binding 不完整被正常拒绝，第二次根据可行动反馈修正后通过。最终 Cash repair workpaper digest 为 `31c61429d51b...`。这证明分析 checkpoint、non-thinking 补齐、合同反馈和同角色修订链能够自然工作。

随后 R14 启动仍 pending 的 Supply／Relationship repair。该角色拥有 10 条 reviewed Evidence 和 4 个 typed gap，但没有 NumericFact；这一形状符合当前角色合同，不能把缺少 NumericFact 误判成 S1 数据失败。

## 2. Supply 为什么失败

Supply 请求共 32,271 prompt token，Provider 返回 HTTP 200 完整响应；12,000 completion token 全部被 reasoning 消耗，可见输出为 0，`finish_reason=length`。失败码为 `model_gateway_reasoning_budget_exhausted`。

失败的最早责任不是“公开资料没有”“检索没找到”或“Supply Agent 没用”。模型看到了该角色全部 10 条 Evidence 和 4 个 typed gap。真正问题是：

1. 一个局部修订节点仍收到 91,182 字符的完整 SpecialistContext；
2. 其中 whole-case truth catalog 约 40,655 字符，完整 Lead plan 约 7,119 字符；
3. 大量与 Supply 修订无关的全案目录重复进入输入；
4. 节点使用 `thinking=max`，最终将全部输出上限消耗在不可见推理。

责任因此拆为：Harness 的上下文选择是最早责任层，任务级 Provider profile 是贡献因素；S1 数据、角色价值和模型传输均不是本次最早故障。

## 3. 零调用结构处置

新增 provider-neutral 的 repair-scoped SpecialistContext。它保留：

- 本角色全部 Evidence、NumericFact／relation refs 和 typed gaps；
- prior workpaper、当前 challenge、可行动 FeedbackReceipt；
- 当前 Case／as-of、角色权限、角色计划与工具回执；
- 与本角色直接相关的全案 presence／gap／bridge；
- 被省略 whole-case alias 的数量与 digest，并明确“省略不代表不存在”。

它不保留与当前修订无关的完整全案目录和 Lead 长叙事，而是使用内容寻址的 projection／omission receipt。R14 的真实输入零调用重编后：

- SpecialistContext：91,182 → 53,041 字符；
- case truth：40,655 → 7,795 字符；
- Lead plan：7,119 → 1,096 字符；
- 10 条 Evidence、4 个 typed gap、12 个角色 presence alias 与 4 个 gap alias 均保持；
- 76 个省略 alias 以 digest 留痕，不能被解释为全案 absence。

新增任务级 DeepSeek repair profile 使用 `thinking=enabled / reasoning_effort=high / max_tokens=12000`。它没有提高 token ceiling，也没有改变核心金融合同；Provider 特殊执行语义仍隔离在 profile 层。

## 4. R15 唯一允许的执行范围

R15 必须：

1. 精确复用 Demand 与 Cash 两份已完成 repair；
2. 不再续写 Cash，不重跑任何完成节点；
3. 只从 Supply fresh analysis 开始；
4. Supply 使用 role-scoped repair context 与任务级 high profile；
5. 随后只允许既定 Evaluator、最多两次 evaluator 指定局部修订和 conditional Writer；
6. 最大新模型节点从 7 降为 6，analysis continuation 上限为 0；
7. 外源网络、Candidate promotion、产品发布、S1／S3／泛化和 qualified-human 权威继续为 0／false。

R14 authority、公开结果、terminal、请求与响应 capture 永久保持失败证据。R15 是新 attempt，不是覆盖或重试 R14。

## 5. 工程债与停止边界

当前 authority／scope validator 已出现多代 attempt-specific schema 分支。它们保证历史精确性，但已接近维护上限。R15 关闭前不再扩写一条 R16／R17 特例；若 R15 暴露同类 successor 编排问题，下一项必须是 S0 通用 successor authority compiler，而不是继续复制 attempt-specific 分支。

完整工程门已通过：综合定向 `105 passed`；全仓第一次运行因最新 RC-AR-002 行漏掉历史 scope allowance 而正确出现 7 个 Project OS fail-closed，追加累积许可更正后复跑为 `896 passed`；compileall、active baseline `184 Python／8 frontend／5 detectors／27 Runtime／0 forbidden`、738 份 configs JSON、8 份 Project OS JSONL／836 行、7,446-file secret scan 和 diff check 均通过。当前只剩 clean commit／push 与 fresh preflight；此前不得签发 R15 live。

Python 3.10 当前使用 isolated `_pth`，综合测试须显式把仓库根与 `src` 注入 `sys.path`；该入口隐式依赖记为 S0 工程债，不修改用户全局 Python 安装。全仓第一次失败同时证明 Project OS 历史许可必须累积保存，不能因最新 attempt 只写当前 scope 而遮掉历史 replay 权限。

即使 R15 最终形成报告，也仍须独立执行 L1、八维绝对内容质量、paired gain、qualified-human 和异质案例泛化；不能据此直接宣布 S3 或产品通过。
