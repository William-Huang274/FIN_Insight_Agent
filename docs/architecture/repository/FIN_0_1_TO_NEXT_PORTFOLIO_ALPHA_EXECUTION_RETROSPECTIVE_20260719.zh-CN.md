# FIN 0.1 到下一 Portfolio Alpha 的执行复盘

日期：2026-07-19

状态：`retrospective_fact_baseline / discussion_input / no_execution_authority`

## 1. 目的

本文在下一阶段编码前，对 PRD、TECH、Point 01-07、纵向版本列车、当前代码主干和 FIN 0.1 产品结果做一次无归责执行复盘。它只回答：

1. 为什么 Point 01 曾围绕局部控制问题反复修复；
2. 为什么 Point 02-07 能较快形成可见产品链，却没有把核心 Agent 能力接入当前主线；
3. 哪些已有建设应保留，哪些执行方法必须停止；
4. 下一阶段在讨论六块目标矩阵和 S1-S5 前，必须先冻结哪些 Agent 设计决策。

本文不是新的 PRD、TECH owner 文档、ReleaseContract、FeatureScope、Point closeout 或执行授权。它不批准模型、网络、商业数据、真实业务 Case mutation、production cutover 或 release admission。

## 2. 权威输入与事实边界

复盘以以下材料为准：

- `docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md`；
- `docs/product/PRODUCT_20260717_release_ladder_and_cadence.zh-CN.md`；
- `docs/architecture/agent_graph_vnext/TECH_00_agentic_research_technical_index.zh-CN.md`；
- `docs/architecture/agent_graph_vnext/TECH_00A_prd_tech_runtime_product_surface_coverage_matrix.zh-CN.md`；
- `docs/architecture/repository/FIN_0_1_PRD_TECH_POINT_IMPLEMENTATION_BASELINE_20260719.zh-CN.md`；
- `docs/architecture/repository/FIN_0_1_CODE_MAINLINE_ARCHIVE_AND_DISCONNECTION_AUDIT_20260719.zh-CN.md`；
- `configs/releases/fin_ia_0_1_code_mainline_manifest_v1_0.json`；
- 当前 Git 主干、测试证据、capability ledger 和 root-cause ledger。

聊天记忆、旧 worklog 的完成措辞、单个 fixture、页面入口或某个类名不能覆盖上述事实。

## 3. 当前客观基线

### 3.1 已形成的产品纵向

当前主路径已经具备：

```text
React/Vite Workbench
  -> Case / 10-cell DecisionSurface
  -> local RAG / SQL / Graph / official assets
  -> deterministic numeric / repair / judgment / workpaper
  -> deterministic no-source Writer
  -> Report / Trace / Human Baseline surfaces
```

P36 当前候选包含 10 cells、31 local candidates、3 exact facts、2 derived margins、10 judgments 和 10 writer sections。该链对 UI、数值、证据 lineage、artifact 投影、rollback 和调试有真实价值，但不构成当前 Agentic Research 主链。

### 3.2 已形成但断连的 Agent 资产

历史代码中存在：

- LangGraph Research Lead、activation、reflection、second pass、specialists、judgment aggregation、Writer、Verifier 和 Renderer；
- 17 个 Agent 定义；
- 16 个 Skill 文件与 20 个角色绑定；
- bounded ReAct / Tool Controller；
- Relationship Graph / Research Graph；
- Agent information economy、模型调用和历史 trace 资产。

这些资产仍可复用，但当前 Workbench 不消费它们。历史 Agent、当前 deterministic product chain 和 standalone DeepSeek runner 分别拥有部分 planning、search 或 synthesis 逻辑。

### 3.3 已形成的平台与控制基础

Point 01 已以 `POINT01_FOUNDATION_ALPHA_CONTRACT_RUNTIME_PROOF_COMPLETE` 窄收口，提供 canonical models、store/facade、compiler、权限、预算、event、artifact、recovery 和 rollback 基础。它不是 production complete；单次 operational attempt 失败并已转入 RG1。

### 3.4 尚未形成的产品证据

- 当前 Workbench 发起的 Case 尚未进入唯一 Agent-capable `Fin01ResearchRuntime`；
- 真实 DeepSeek/model/provider 调用仍为 0；
- Agent、Skill、Tool、Graph 未被当前产品运行时共同消费；
- Human Baseline 仍使用独立 SQLite，exact canonical Human Senior Review 为 0；
- RG1、RG3、RG4 未关闭；
- 当前 deterministic report 是 fallback，不是最终 Lead synthesis。

### 3.5 当前仓库状态

代码主干已经形成五个 path-exact commits；当前分支领先远端 5 个提交。当前未提交内容为规划草稿和 worklog 索引，不再是此前 1300 余 path 混合暂存的状态。Git hygiene 已不再是下一阶段首要阻断。

## 4. 两类主要失速现象

### 4.1 Point 01：局部问题不断扩大为新修复循环

典型路径为：

```text
局部合同通过
  -> 后续审计发现新的 authority/package/receipt 条件
  -> 新增 repair 或 package freeze
  -> operational path 过晚执行
  -> entry-to-leaf 集成缺陷暴露
  -> 继续扩大审计和治理范围
```

这里既有真实代码缺陷，也有执行系统缺陷。真实缺陷包括 package identity、clean-child 传播和 terminal ordering；执行系统缺陷包括 acceptance 未提前完全冻结、纵向执行过晚、Foundation Alpha 与 production maturity 混淆，以及审核在验证现有标准时继续创造新标准。

### 4.2 Point 02-07：产品表面迅速贯通，核心 Agent 语义没有进入

纵向版本列车成功贯通了 Case、Evidence、Numeric、Workpaper、Writer、Review 和 UI，纠正了“按 Point 编号横向施工”的问题。但它主要验证的是 artifact/product vertical，而不是 Agentic Research semantic vertical。

当前 Gate 对 Case、artifact identity、numeric replay、Writer no-source、UI 和 rollback 有明确要求，却没有把下列条件设为同等强度的早期阻断项：

- Workbench 必须调用唯一 Agent Runtime；
- Research Lead 必须观察并动态调整计划；
- Agent/Skill Registry 必须被当前 Run 消费；
- Agentic Search 必须根据 observation 继续、换路、修复或停止；
- Graph 必须至少在一个受限场景中由 Agent 动态探索；
- Specialist 必须输出真实结构化 Judgment。

因此 deterministic substitutions 足以完成大部分 current-train Gate，临时替代没有被强制替换。

## 5. 根因树

| 根因 | 形成机制 | 直接后果 | 下一阶段约束 |
| --- | --- | --- | --- |
| 缺少 Program Execution 层 | PRD、TECH、Point 和 Release 各自完整，但没有跨 Point 的产品施工总图 | Point owner closeout 被误当成版本顺序 | 用一个 Program Plan 决定 release slice，Point 只保留 owner/source reference |
| Point 分解被当成产品规划 | Point 描述最终能力边界，不描述每版最小用户任务 | 局部能力很深，纵向产品语义不均衡 | 每个 slice 必须声明用户可见结果和六块最小贡献 |
| 完成状态轴混淆 | contract、fixture、runtime、mainline、human、release 混用“完成” | 已实现资产被误写为当前产品能力 | 统一使用 documented -> implemented -> mainline_consumed -> integrated_verified -> human_accepted -> release_qualified |
| 缺少 mainline consumption Gate | 代码存在或测试通过即可计入进度 | 历史 Agent/Skill/Graph 长期断连 | capability 必须有当前 Workbench consumer 和 exact Run 证据 |
| fallback 无退出合同 | deterministic chain 先解决展示和安全问题，但没有替换版本与 sunset 条件 | fallback 逐渐成为事实主线 | 每个 fallback 必须有 mode label、替换 Gate、保留理由和退出版本 |
| 最小真实纵向运行过晚 | 先做合同和局部证明，最后才运行 entry-to-consumer | 集成缺陷在高成本阶段暴露 | 第一个开发 slice 必须是 one-cell browser-to-agent vertical |
| 复用成本估计不足 | 把历史 Agent 视为已有能力，未单列状态模型和 adapter 迁移 | 复用任务不断后移 | 先裁决 retain/refactor/absorb/retire，再估算迁移，不以类名计完成度 |
| 需求变化没有 scope swap | UI、中文、治理和产品反馈加入当前周期时没有移出原任务 | 所有方向都有增量，核心路径仍未关闭 | 新需求必须写明替换任务、时间影响和 release claim 变化 |
| 评测介入过晚且不对称 | 工程合同测试很多，真实 model/human 质量证据很少 | 能快速证明“链存在”，不能证明“研究有用” | one-cell 后立即运行真实输出评测，不等全部功能完成 |
| 多个状态载体并存 | Point closeout、worklog、checkpoint、backlog 和 release evidence 各自报告阶段 | 当前状态需要人工拼接 | 只允许一个 machine backlog 拥有实时进度，其他文档只提供目标、owner 或证据 |

## 6. 不应被误判为根因的事项

### 6.1 项目规模大不是根因

金融研究、Agent、数据、图谱、数值、Workbench、review 和 memory 的组合有真实业务依据。问题不是项目“大”，而是没有按版本声明哪些能力必须现在消费、哪些只是未来接口。

### 6.2 用户反馈和方向调整不是根因

UI 后台化、缺中文、报告质量低和缺少真实 Agent 都是有效产品反馈。问题在于这些反馈进入当前周期后没有触发正式 rebaseline 和 scope swap。

### 6.3 平台治理不是无用工作

Case/Run/Artifact identity、permission、budget、numeric hard gate、Writer no-source、rollback 和 provenance 都是长期产品需要的基础。问题是其投入比例和成熟度目标曾超过当期用户能力增量。

### 6.4 deterministic fallback 不是错误

它提供可重复调试、浏览器开发、numeric/evidence 回归和模型失败回退。错误是未把它标成 fallback，且没有明确何时由真实 Agent path 取代核心语义。

### 6.5 历史 Agent 不是应删除的旧代码

历史实现包含可复用的角色、Skill、reflection、tool-use、writer 和 verifier 经验。它的问题是 SEC orientation、mutable graph state、合同漂移和与 canonical product identity 断连，需要迁移而不是简单删除或原样套壳。

## 7. 已有建设应保留的价值

| 已有资产 | 保留价值 | 下一阶段使用方式 |
| --- | --- | --- |
| Point 01 canonical runtime | 安全边界、版本、权限、事件、回滚 | 作为统一 Runtime 的基础，不继续横向扩大治理 |
| 当前 deterministic P36 chain | 可重复 fallback、数据和 UI 回归 | 迁入明确的 `deterministic_fallback` profile |
| 历史 LangGraph/Multi-Agent | Lead、Specialist、reflection、Writer/Verifier 行为资产 | 经 adapter 和状态迁移接入，不直接成为第二个产品入口 |
| Agent/Skill registries | 角色、能力和方法版本 | 升级为当前 Run 实际消费的配置合同 |
| 本地 RAG/SQL/Graph | 可重复、低成本的真实本地候选 | 作为 Agentic Search 的受限工具，不由 Specialist 私有化 |
| Numeric/Evidence Gate | 不受模型覆盖的事实和计算边界 | 保持独立业务 owner，Agent 只能请求和消费 |
| Workbench Next | 产品入口、运行观察、Artifact/Review surface | 只调用统一 Runtime，并明确展示 execution mode |
| Human Baseline | 计时、rubric、exact digest attestation | 迁入 canonical ReviewAction，不保留第二套产品事实主线 |

## 8. 下一阶段建设域

下一阶段采用以下六个长期并行建设域，但本复盘不冻结它们的版本目标矩阵：

1. 平台运行时与治理；
2. 数据、证据与机构记忆；
3. 金融研究、数值与建模；
4. Agentic Research 与编排；
5. 产品、Case 生命周期与协作；
6. 评测、人工审核与发布质量。

六块是 program workstreams，不替代 PRD 五个产品平面，也不改变 TECH_00 stable-object owner。一个 release slice 必须跨块形成完整用户任务，不能先分别“做完六块”再集成。

## 9. 下一阶段必须执行的流程修正

### 9.1 版本先冻结核心语义

公开版本必须先声明：目标 Case、支持范围、真实 Agent 行为、用户结果、Human Review 和明确非目标。页面数量、Point 完成数量和合同数量不能替代 release claim。

### 9.2 integration-first

第一项代码工作必须形成：

```text
Workbench Case
  -> one ResearchRuntime
  -> one real Agent cell
  -> Evidence/Numeric/Judgment
  -> Workpaper/Report/Trace
```

一个 cell 没有通过前，不扩更多 cells、Case、页面、provider 或 gate family。

### 9.3 计划采用 rolling-wave

Program Plan 冻结版本目标、六块目标和 S1-S5 依赖，但只详细拆当前 slice 与下一个 slice。禁止在真实 one-cell 结果出现前把全部远期任务拆成大量 execution points。

### 9.4 真实质量评测提前

one-cell 集成后立即运行 bounded model output 和 Human Review。真实质量不足时优先判断数据、上下文、Skill、Lead、Specialist 或 Writer 的最早缺陷，不先扩功能。

### 9.5 进度只按产品消费和成熟度汇报

每轮只报告：

- 本轮新增的用户能力；
- 哪个当前主链 consumer 开始使用它；
- 研究质量或运行质量怎样变化；
- 剩余关键路径；
- 新需求是否发生 scope swap。

## 10. Agent 设计讨论前不得预设的事项

现有 `FIN_0_1_NEXT_STAGE_PRODUCT_MAINLINE_EXECUTION_DRAFT` 和 `FIN_0_1_LAYER_2_AGENT_CORE_EXECUTION_DRAFT` 只是讨论输入。它们使用“层”的表达，并提前提出部分 profile、三-cell 和迁移顺序；这些内容在 Agent 设计讨论前不能自动升级为执行权威。

以下事项必须由下一轮讨论逐项决定：

1. Research Lead 的产品职责、动态权限和固定边界；
2. FIN 版本使用单图、分层图还是 supervisor/subagents-as-tools 编排；
3. 历史 17 个 Agent 哪些保留为真实角色，哪些降为 operator/skill，哪些退休；
4. Agent Registry、Skill Registry、Tool Registry 和 Workflow Policy 的运行时关系；
5. Agentic Search 的 plan/act/observe/replan/stop 最小闭环；
6. RAG、SQL、Graph、official web 和 parser 分别由谁调用、谁能重试；
7. Graph storage/query 与 Agentic Graph exploration 的边界；
8. Specialist 输出 Judgment、EvidenceRequest 还是自由文本；
9. Lead、Specialist、Writer、Verifier 的 context 和 memory 分配；
10. repair ownership、并发、版本失效和停止条件；
11. Writer/Verifier 是否保留为 Agent，以及 Writer no-source 的实现；
12. deterministic、agent shadow、bounded model 和失败模式如何在同一 Runtime 共存；
13. 哪些 Agent 行为必须进入 v0.1 milestone，哪些属于 multi-case v0.2；
14. 如何用三个真实 Case 证明编排不是硬编码；
15. Agent 质量、成本、延迟和 Human Review 使用什么 Gate。

## 11. 复盘后的正确文档顺序

```text
本复盘
  -> Agent 设计讨论与决策
  -> 六块目标矩阵
  -> S1-S5 跨块 release slices
  -> Point 01-07 absorption map
  -> 唯一 machine backlog
  -> execution
```

不能跳过 Agent 设计讨论，直接把旧分层草稿改名为 Program Plan；也不能在讨论期间继续扩展 runtime、UI、provider、Agent persona 或测试矩阵。

## 12. 本复盘完成条件

本复盘只有在以下事实被接受后才可作为 Program Plan 输入：

1. 当前主要问题是 program/integration/consumption 缺口，不是单纯缺代码；
2. Point 文档继续拥有技术来源价值，但不再决定产品施工顺序；
3. deterministic fallback 保留，但不能冒充 Agent 主线；
4. 历史 Agent 需要迁移裁决，不是直接删除或直接套壳；
5. 下一步先讨论 Agent 设计，再冻结六块目标和 S1-S5；
6. 真实 one-cell model/human evidence 必须早于多 Case 扩展；
7. PRD 长期范围保留，但下一公开版本只承诺 bounded-complete scope。

在用户确认本复盘与 Agent 设计决策前，不开始下一阶段代码实现。
