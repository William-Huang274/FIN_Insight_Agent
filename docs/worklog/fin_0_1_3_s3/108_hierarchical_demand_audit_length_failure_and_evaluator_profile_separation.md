# FIN 0.1.3 S3 — Demand 单角色审查截断与 Evaluator profile 分责

日期：2026-08-21

状态：`profile-separated live consumed / Demand audit valid / Operating reasoning-only exhaustion preserved / evaluator checkpoint and non-thinking responsibility full engineering gate pass / clean push preflight and continuation pending`

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

## 7. Profile-separated live 的真实结果

全新 authority 在 clean／synced implementation commit `08f1d3b6...` 和第二次 fresh Project OS preflight 后执行。旧研究计划、六份底稿、Lead coordination 和三条既有 repair 全部复用；没有网络、Candidate promotion 或上游研究重跑。

Demand 单角色审查首次完整通过：

- analysis prompt `5,379` tokens；completion `7,141`，其中 reasoning `6,434`；`finish_reason=stop`；
- strict submission prompt `1,781`、completion `561`，形成唯一合法 Tool Call；
- 三条 finding 均为非阻断：把“未纳入 non-cancelable backlog”误写成“存在可取消垫层”、把条件式渠道减单风险写成主动机制、增加了一句 authority 未支持的 graph 描述；
- `report_may_proceed=true`。这是一份有效、可复用的独立角色审查，不得在后继 attempt 中当作未完成重跑。

随后 Operating Performance 审查在同一 `thinking=enabled / reasoning_effort=low / max_tokens=8,000` profile 下失败：prompt `6,061`，completion 与 reasoning 均为 `8,000`，可见内容为空，`finish_reason=length`。Provider HTTP 200、响应完整，失败码为 `model_gateway_reasoning_budget_exhausted`。这不是资料缺失、对象化、S1 检索、NumericFact、Operating 底稿、网络或 strict submission 失败；最早责任层是 Evaluator 的模型职责与 Runtime 预算语义。

DeepSeek 官方 Harness 当前把 `low` 作为合法 thinking effort，但它仍是推理偏好，不是“为可见答案预留 token”的硬合同。本轮同一 profile 在两个相近规模角色上分别正常结束与 reasoning-only exhaustion，说明不能继续靠 `low`、增加 ceiling 或删金融 authority 获得运行可靠性。

## 8. 下一结构处置

后继不得直接重跑整个分层 Evaluator。需要同时完成两项：

1. 把 Demand 的 validated evaluation、analysis／submission capture、usage、工作底稿 digest 和上下文 digest 编译成不可变 Evaluator checkpoint；后继从 Operating 开始。
2. 把自动内容 Evaluator 明确降为“受限清单式裁判”：本地 L1 继续负责身份、期间、引用、精确数字和 absence；研究／repair Agent 保留 thinking；Evaluator 使用 non-thinking 可见审查和 strict submission，不能新增事实或重写底稿。先用 Demand 已验证三条 finding 做离线语义基准，再做一次自然 continuation。

若 non-thinking Evaluator 无法保留 Demand 已证明的材料边界判断，或在 Operating 上形成明显浅薄／误判 finding，停止继续调 DeepSeek profile，进入独立 Evaluator 模型选择或 qualified-human-first 决策。完整六角色评审、跨角色检查、Writer、报告、八维质量、paired、qualified-human、S1／S3、泛化、Workbench 和 release 仍未通过。

## 9. Demand 检查点与 Operating-onward 工程门

已完成通用 Evaluator 进度检查点，而不是再建一个 Demand 特例 runner：

- checkpoint digest=`569c641b395adf29375abf59b2302ed2f733f4788f850edfdc0dbaa5ecb202ae`；
- 精确绑定 Demand 的 analysis／submission 请求响应 capture、usage、finish reason、三条 validated finding、workpaper digest 与 context digest；
- 完成前缀只能是六角色规范顺序的连续前缀，缺节点、乱序、payload／terminal／context mutation 均 fail closed；
- 新 frontier schema v1.2 明确 `completed_role_evaluation_agent_ids=[AGENT::DEMAND_QUALITY]`，首轮新审查从 6 降为 5，最大新模型节点从 13 降为 12；Demand R1 重跑被合同禁止；
- 零调用 proof digest=`74ba9fda3fc613bb788cbcce1cd16b5218099a6d477956206f9e32a8c825e313`，同时证明缺角色、错目标、未解析 authority、排列／预算篡改、无关角色复审与已完成角色重跑均 fail closed。

自动内容 Evaluator 的职责被进一步收窄为“对既有底稿做可见的受限清单式判断”，使用 `thinking=disabled / max_tokens=10,000 / retry=0`；这不是把研究 Agent 改成 non-thinking。六个研究角色和收到 material finding 后的真实 role repair 继续保留 high-thinking，strict submission 继续只做合同映射。本地 L1 仍独立负责公司身份、期间、引用、精确数字和 absence，不把这些责任丢给模型。

真实 terminal 还暴露并修正了一个测试夹具漂移：运行时 node record 保存规范化 `validated_payload`，没有测试曾伪造的顶层 `validated_payload_digest`。检查点现按真实 payload 及其内建 evaluation digest 复证，避免“fake 能恢复、真实 capture 不能恢复”。

完整工程门：全仓 `918 passed`（仅既有 SWIG deprecation warnings）、compileall、Workbench TypeScript 与 Vite production build、active baseline `185 Python / 8 frontend / 5 detectors / 27 Runtime / 0 forbidden`、`770` 份 configs JSON、`8` 份 Project OS JSONL／`878` 行（写入本节前）、`7,490` 文件 secret scan／0 findings 和 diff check 均通过。0 模型、0 Provider、0 网络、0 Candidate promotion。

下一步只允许 clean commit／push、fresh Project OS preflight、全新 authority 和一次从 Operating Performance 开始的 continuation。若 non-thinking Evaluator 只是机械复述、遗漏实质边界或形成明显误判，不再调 ceiling／Prompt／DeepSeek profile；转独立 Evaluator 模型或 qualified-human-first 项目级决策。当前仍不能宣称六角色、跨角色、Writer、完整报告、S1／S3、泛化、Workbench 或 release 通过。
