# FIN 0.1.3 S3 — Demand 单角色审查截断与 Evaluator profile 分责

日期：2026-08-21

状态：`immutable natural failure preserved / evaluator profile separation implemented / full repository gate pass / clean commit push preflight and fresh live pending`

## 1. 这一轮真实发生了什么

分层 Evaluator 的第一次 replacement live 已越过 authority、execution binding 和全部 checkpoint 恢复，只启动了第一个自然节点：Demand Quality 单角色内容审查。六份 Specialist plan、Lead plan、六份工作底稿、Lead coordination 和 Demand／Cash／Supply 三条既有修订全部复用，没有重跑研究上游。

Provider 正常返回 HTTP 完整响应。该节点收到约 `5,458` prompt token，配置的 completion ceiling 为 `12,000`；其中 `11,289` token 被 reasoning 消耗，留下 `2,976` 字符可见审查，并以 `finish_reason=length` 截断。strict submission、其余五个角色审查、跨角色审查、Writer 和最终报告均未开始。公共失败结果、原始请求／响应 capture 和 private terminal result 保持不可变。

## 2. 可见内容说明了什么

虽然终态必须 fail closed，但可见审查不是空白或胡乱输出。它已经完成了五个主要维度：

- 判断纪律：通过；
- 经济机制：通过；
- 反方：通过；
- What Would Change：通过；
- gap／边界措辞：通过；
- `Role Content May Proceed`：`true`。

唯一已形成的 advisory 为 LOW：`$16.1B` 当季 AI server revenue 最多证明同季订单向收入转化，不应被写成更强的持续性或因果证明。输出只在最后一条说明句中截断。

因此，本轮不能被解释成：

- S1 没给材料；
- Demand Agent 的研究底稿不合格；
- DeepSeek 完全不会做金融内容评审；
- 分层 Evaluator 拆分无效。

最早责任层是 S0 Provider task profile 与 S3 Evaluator 编排：Runtime 把“评审一份已完成底稿”和“收到 finding 后重做一份研究底稿”错误复用了同一个 `high / 12,000` repair profile。对较短、收敛、只读的审查任务，高思考反而挤压了可见交付。

## 3. 结构性修复

当前实现把三类职责明确分开：

1. **Evaluator analysis**：只检查既有判断、机制、反方、WWC、gap 表述和责任归属；不新增研究事实，使用独立的低 reasoning 候选 profile。
2. **Role repair analysis**：只有 Evaluator 形成 blocking／material finding 后，原责任角色才在完整 repair context 下修改底稿；继续使用 high reasoning profile。
3. **Strict submission**：只把已经完成的分析映射为 Tool Call；继续使用 non-thinking submission profile。

本轮 DeepSeek GA 候选配置为：

- 单角色审查：`low` reasoning，节点 ceiling `8,000`；
- 跨角色一致性审查：`low` reasoning，节点 ceiling `10,000`；
- 实际角色 repair：`high` reasoning，节点 ceiling `12,000`；
- retry：`0`。

这些 ceiling 不是按省钱或速度倒推。单角色上一轮输入只有 5,458 token，主要输出是有限 finding 和是否放行；8,000 足以覆盖预期可见审查并保留 reasoning headroom。跨角色输入更大、需要检查六份审查摘要，故为 10,000。真实 repair 需要重新形成机制和边界，因此保留 12,000。每个节点仍会生成独立 TokenBudgetBasis；profile 名不能替代实际 usage、finish reason 和可见输出检查。

## 4. 为什么不是另造一个 Demand 特例 runner

Demand 仍是完整多角色 Preview 的第一个节点，不存在单独产品链。它只承担 canary 作用：

- 若 Demand 仍不能完整交付，当前 execution frontier 当场停止，其余五个角色不浪费调用；
- 若 Demand 完成，原 runner 继续运行 Operating、Value、Cash、Supply、Counter 六角色审查、跨角色审查、最多两处定向 repair／复审和条件式 Writer；
- 任何完成前缀继续按 capture／digest 复用，旧 attempt 不追认为成功。

## 5. 长期产品边界

核心金融合同仍是 provider-neutral 的角色评审、finding、责任路由和修订合同；DeepSeek 的 `low／high／non-thinking` 只存在于 Provider profile。未来模型能力升级时，允许通过统一 canary 调整 profile 或增加自主权，不需要改 Evidence、NumericFact、L1、Evaluator finding 或 Writer 权威边界。

若这次单角色低 reasoning canary 仍出现 reasoning-only exhaustion、无可见输出或内容明显退化，禁止继续逐字段裁剪权威、增加全局 token ceiling 或扩建 DeepSeek 专用 Prompt。下一项必须升级为 Evaluator 模型／profile／职责选择；必要时由另一稳定模型负责评审或结构提交，而 DeepSeek 保留研究分析职责。

当前仍未证明自然 Evaluator 全链、跨角色一致性、Writer、完整 DELL 报告、八维质量、paired gain、qualified-human、S1／S3、跨案例泛化、Workbench publication 或 release。

## 6. 零调用与完整工程门

- Multi-Agent／Runtime／successor／Project OS 定向复证：`125 passed`；
- 全仓：`916 passed`，只有既有 SWIG deprecation warnings；
- `compileall`：通过；
- active baseline：`185 Python / 8 frontend / 5 detectors / 27 Runtime / 0 forbidden`；
- configs：`763` 份 JSON 可解析；
- Project OS：`8` 份 JSONL／`875` 行可解析；
- secret scan：`7,483` files／`0` findings；
- `git diff --check`：通过。

该结果只证明实现、历史 replay、scope、profile binding、预算和仓库主线稳定。下一步仍须 clean commit／push、fresh Project OS preflight 和全新 authority，才能执行一次 profile-separated 完整 Preview successor。

第一次 clean／synced preflight 的总状态虽为 pass，但 `explicit_allow_issue_ids` 只列出旧的 RC-AR-002／020，没有列出本轮 RC-AR-023。原因是账本只写了描述性 successor 名，没有同时登记机器实际使用的 `run_scope_id=one_clean_authorized_compiled_multi_agent_successor`。这不会被当作“总状态已经绿所以可以忽略”：Project OS 现要求只要 scope 绑定新的 Evaluator profile，就必须显式取得 RC-AR-023 对同一 run scope 的 allowance；缺失时 preflight fail closed。该更正需要第二个小提交／push 和 fresh preflight，第一次 preflight 不用于签发 authority。

治理更正后的复证再次通过：generic successor／Project OS 定向 `83 passed`、全仓 `916 passed`、compileall、active baseline `185／8／5／27／0`、763 configs、8 份 Project OS JSONL／876 行、7,483-file secret scan 和 diff check 均有效。该小修只让当前根因成为机器必验前置项，不改变任何模型输入或执行预算。
