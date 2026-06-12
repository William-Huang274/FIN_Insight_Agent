# 2026-06-12 Knowledge Graph / Sub-agent / Product Edge Framework

## Prompt

用户补充了投研工作流知识图谱框架，并进一步明确：公开采购视角是像终端用户、采购员或经销商调研人员一样查询公开产品规格、售价、库存、交期和订货信息，不是黑客行为、权限绕过或身份冒充。用户要求把外部文档内容、专家 agent 升级为次级 agent、产品边细化讨论融合成新的升级框架。

## Decision

新增一份 architecture vNext 文档，而不是修改 G1-G11 runtime 文档。原因是 G1-G11 已经定义 graph runtime 机制；本轮内容是下一阶段投研工作流 KG 对象层、source hierarchy、次级 agent 职责和产品规格/渠道证据合同，应作为增量框架进入 `agent_graph_vnext`。

## Work Completed

- 新增并在后续重整为 `docs/architecture/agent_graph_vnext/07_investment_research_workflow_knowledge_graph_framework.zh-CN.md`。
- 更新 `docs/architecture/agent_graph_vnext/README.zh-CN.md` 的文档索引。
- 框架按 `投研工作流知识图谱框架.docx` 的主线重排：对象优先、来源边界、投融资四分法、核心 schema、source hierarchy、两张主图谱、P0-P4 落地顺序、禁止错误和 K1-K8 工程拆分。
- 框架明确三层 KG：`Operating Knowledge Graph`、`Capital / Ownership / Financing Graph`、`Claim Evidence Layer`。
- 框架把 specialist 升级为 sub-agent，并定义 Fundamental、Product/Technology、Industry/Supply Chain、Capital/Ownership、Risk/Counterevidence 五类次级 agent 的职责和禁止项。
- 框架在 Business Operating Graph 的 P0 层新增 ProductFamily、ProductModel、ProductSpec、ProductGenerationEdge、CompetitiveComparableEdge、ChannelOffer、FieldInquiryNote。
- 框架新增 `public_buyer_observer` 公开采购视角边界：允许公开网页/公开目录/公开报价调研，禁止身份冒充、绕权限、虚假表单、实际下单或把 channel signal 提权为 sales/share/ASP。

## Result And Evidence

- 本轮是架构文档更新，没有改 runtime 代码。
- 没有运行测试或实验；不声明任何新 KG/sub-agent 能力已经进入默认 runtime。

## Follow-up

- K1：落 KG Matrix Registry。
- K2：落 Product Spec ontology 和行业规格维度。
- K3：落 public buyer observer source policy。
- K4：升级 Product / Technology sub-agent skill。
- K5：落 Capital & Ownership Graph。
- K6：落 Macro Exposure 和 vertical official adapters。
- K7：补 Verifier / Reflection gates。
- K8：跑跨行业 KG sub-agent end-to-end gate。
