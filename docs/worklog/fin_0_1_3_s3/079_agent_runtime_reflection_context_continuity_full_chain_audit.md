# 079 Agent Runtime、反思与上下文连续性全链审计

日期：2026-08-19

状态：`audit_complete / source_docs_aligned / contract_frozen / runtime_not_implemented`

## 用户要求

完成以下五项：

1. 还原 Planner、S1、S2、五研究单元、Lead、Writer、Verifier 的真实消息和状态流；
2. 检查每类失败是否反馈给模型，以及模型收到后能否改变计划；
3. 区分固定 workflow、局部 repair 和真正自主循环；
4. 冻结 `AgentSession / FeedbackReceipt / PlanDelta / GraphDelta / ContextCheckpoint / StopDecision`；
5. 修订 PRD、技术文档、S1 最终验收和 S3 计划。

用户补充要求：基础设施、Harness 和 Agent 工作模式必须分账；检索、查询、重排、数据清洗先用无 AI 人工基线判断，人工也无法稳定找到正确结果即为工具 failure；Skill 与 Graph 属于 Harness 和 Agent 的交叉层，既要正确指导研究，也必须动态、按角色加载，不能机械固定注入。

## 执行范围

- 0 模型调用；
- 0 网络、检索、向量和付费工具执行；
- 0 Runtime 代码迁移；
- 只读审计活动代码、已保存运行、Project OS 和当前产品／技术源文档；
- 修改仅限架构合同、源文档、计划、清单和账本。

## 真实链审计结论

### 当前已经存在

- Planner 一次性生成 atoms；
- Harness 做身份／合同／预算校验和本地选择／延期；
- S1/S2 作为 typed tools 返回候选、EvidenceResponse、NumericFact、relation 或 gap；
- 五研究单元按固定拓扑分析和交卷；
- Synthesis 消费五个 Judgment；
- 本地编译底稿和内部报告；
- Verifier／评测终局检查；
- 单片段 Validation failure 可获得一次 typed repair；
- 失败 attempt 与成功前缀可以不可变复用到 successor。

### 当前尚不存在

- 统一 `AgentSession` 和 append-only SessionEvent；
- S1/S2／Verifier finding 通用路由到 owning Agent；
- Agent 基于失败修改研究计划的 `PlanDelta`；
- 随新披露更新 run-local 研究图的 `GraphDelta`；
- Skill／Graph 动态最小选择和自然消费 receipt；
- 跨 Agent 冲突回退、局部重裁决和 Lead 协调循环；
- 长上下文 checkpoint、compaction、resume 和 mutation 资格；
- 可区分充分完成、信息边界、预算耗尽和工具失败的统一 `StopDecision`。

因此当前系统应描述为“固定 workflow＋局部 repair＋不可变 successor”，不能描述成通用反思型 Multi-agent Runtime。

## 责任分账

### 基础设施／工具

source/capture、transport、OCR/parser、清洗、金融对象、index、query、recall、rerank、Evidence Role、SQL/NumericFact。正式判定先用人工／fixture typed request，不使用生成模型。人工也失败即为工具 failure，不能让 Agent loop 掩盖。

### Harness

身份、期间、单位、来源、lineage、Evidence／NumericFact／Gap 权限、合同、预算、exact-once、失败路由、事件、checkpoint 和 stop validation。Harness 不写研究观点。

### Agent 工作模式

目标理解、假设、反方、EvidenceRequest、充分性反思、replan、Judgment、综合和 WWC。Agent 可以提出 delta，不拥有事实晋升权。

### Skill×Graph

Harness 管 Pack 发现、版本、选择、作用域、digest、注入和 receipt；Agent 管实际方法消费、研究方向和关系增量。Skill／Graph 均不成为 Evidence。

## 冻结合同

机器合同：

`configs/research/fin_ia_0_1_3_agent_runtime_reflection_context_continuity_contract_v1_0.json`

状态明确为 `architecture_contract_frozen_runtime_not_implemented`。合同同时冻结：

- 四责任平面；
- 三种 workflow class；
- 六种运行对象；
- failure routing；
- role autonomy；
- Skill／Graph 加载；
- exact-once 与多轮的兼容规则；
- TokenBudgetBasis；
- S0–S5 阶段归属与验收门。

## 源文档同步

已更新：

- `docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md`：新增 16.46；
- `docs/product/FIN_0_1_3_CURRENT_BASELINE_AND_S0_TO_S5_CLOSEOUT_PLAN_20260812.zh-CN.md`：新增 4K；
- `docs/architecture/retrieval/FIN_0_1_3_S1_EVIDENCE_ACQUISITION_AND_PACK_QUALITY_PARADIGM_20260817.zh-CN.md`：新增 30；
- `docs/eval/FIN_0_1_3_S1_INDEPENDENT_DATA_RETRIEVAL_AND_EVIDENCE_READINESS_EVALUATION_STANDARD_20260817.zh-CN.md`：新增 19；
- `docs/architecture/research/FIN_0_1_3_S3_CURRENT_RESEARCH_CONSUMER_20260813.zh-CN.md`：新增 25；
- `docs/project_os/current_context_pack.zh-CN.md`；
- 当前主清单和工作记录索引。

完整审计：

`docs/architecture/research/FIN_0_1_3_AGENT_RUNTIME_REFLECTION_CONTEXT_CONTINUITY_AUDIT_20260819.zh-CN.md`

## 对当前计划的实际影响

1. S1 优先级不取消。先完成 AI-free 人工可操作资格、MU／NVDA 官方路线、候选准入和 replacement blind qualification。
2. S0 可并行进行零调用 Session／event／contract／checkpoint 骨架，但不能提前跑自然反思 live。
3. S1/S2 的 typed results 后续必须成为 `FeedbackReceipt`，而不是只有工程人员读日志。
4. 第一条自然反思链仍从 DELL `value_capture` 单研究单元开始；固定 Pack 只作模型分析单测。
5. 单单元通过后才扩到五单元、Lead、MU／NVDA 和异质留出；S4/S5 不提前。

## 主动反思

此前工程长期把“避免幻觉”主要解释为扩大 Harness 校验和确定性编译，得到的好处是真实性边界更强，但副作用是模型很少收到可行动反馈，也没有机会在同一会话中修正研究方向。这会产生两个错觉：一是调用多次就等于多轮 Agent；二是每次失败都需要工程师写 successor。

本次调整不是放松 Harness，而是把它从“终局挡板”升级为“可反馈控制面”：事实权限继续严格，本地 failure 必须先修工具；只有研究层错误才交给 Agent 反思。这样可以减少围绕单一模型的逐字段补丁，也给未来更强模型留下可扩展自主权。

另一个风险是把所有节点 Agent 化。该方案已明确拒绝：S1/S2、Renderer 和金融 Validator 保持确定性；只有对研究计划、证据充分性和跨单元综合有真实判断价值的角色进入有界循环。

## 当前状态与下一步

- `S1_qualified_stable=false`
- `generalized_reflection_loop=false`
- `dynamic_skill_graph_consumption=false`
- `context_continuity=false`
- `S3_acceptance=false`
- `S4/S5=false`

下一项仍是 S1 当前剩余资格和来源门；S0 Agent Runtime 只允许从零调用 schema／event／checkpoint／resume proof 开始。任何自然模型节点执行前必须单独形成 `TokenBudgetBasis`。
