# FIN 0.1 S3-T05：bounded Graph / Product / Market / Risk 三 Cell 投影

日期：2026-07-21

## 问题与授权

用户以“继续”授权当前唯一下一项 S3-T05。范围只包括零模型、零网络、零外部工具的确定性 Graph 投影、测试、Project OS 和暂存；不授权 T06、真实 SourceHunter、Evidence promotion、业务 Case 写入、付费执行、S4、release 或 production。

T05 的五项验收要求是：三个 Cell 各有一个 typed bounded Graph use case；edge type、authority、source、as-of、boundary 与 followup refs 可见；裸边、过期边、推断边、冲突边不可成为 Evidence；Graph 不分配财务数字、不把机制路径变成事实；Market price-in 与 Risk 行只能是 bounded context 或 typed gap。

## 根因与决策

历史 Graph、ProductIntelligenceGraph、Market/Capital 和 Risk 资产虽然存在，但没有进入 exact 三 Cell RuntimePlan。最早缺口不是“图数据不够多”，而是缺少一个按 Cell 投影、保存权威与时点、并能阻止关系路径越权的运行时对象。

实现决定：不新增 Graph runtime、store、registry 或读取。`P36LocalResearchService.analysis_preview` 已经做一次 local read-only Research Graph query；T05 只复用其输出契约，并与 T03 route、T04 Financial pack 交叉校验后编译 pack。

独立复核发现并修复三项问题：

1. T05 实际消费 T03/T04，因此 backlog 依赖从原 T01/T02 修正为 T01-T04。
2. Graph edge 初版摘要没有覆盖 Pydantic 默认的无权威字段，导致消费重算正确失败；现摘要从编译起覆盖 inferred/conflict/direct-Evidence/Numeric/fact/writer 全边界。
3. 反序列化后的嵌套 tuple/list 具有相同 canonical JSON 语义但 Python 对象不相等；recompile 对比改用完整 JSON 形态，未跳过任何字段或摘要。

## 完成内容

- `src/sec_agent/research_graph_store.py`
  - 新增 T05 typed pack、三类 Cell edge、Market price-in、Risk context、Cell receipt 和四类 edge-admissibility probe。
  - 编译器核验 T02/T03/T04/analysis lineage、同一 Run、单次既有图读取和所有零调用/零写入边界。
  - consumer 全量重编译并校验 nested digest，任何边界或 lineage 改动 fail closed。
- `src/sec_agent/product_intelligence_graph.py`
  - 把 T03 candidates 与 T04 availability 投影为三个 Cell-specific Product/Industry inputs。
  - 明确 technical signal 不是 financial fact，Graph/Product 没有 Numeric 或 direct Evidence authority。
- `src/sec_agent/research_skills.py`
  - 将 Product/Industry、Market、Risk 角色的 reviewed Skill 定义和方法 ID 编译成 content-addressed T05 合同。
  - authority grants 为空；model/network/business write 均未授权。
- `apps/workbench/backend/application/local_research_service.py`
  - 将原 Case `as_of` 保留到 analysis preview，供 Graph/Market 时点边界使用。
- `apps/workbench/backend/application/research_runtime.py`
  - T05 pack 与三份 consumption receipt 写入同一 deterministic ResearchRun Artifact，并在持久化前和读回验证时重算。
- `tests/contract/test_fin_0_1_s3_t05_bounded_graph_decision_cell_projection.py`
  - 覆盖 Runtime/Run lineage、三 Cell use case、edge authority/source/as-of/followup、四类负向边、零 Numeric allocation、Market/Risk typed gap、方法生命周期与 tamper fail-close。

## 实际效果与边界

三个 Cell 现在都有结构化 Graph 输入：

- Demand：官方披露/客户语境只形成 demand durability 检查，不证明持续终端需求，也不把客户 capex 变成 NVDA revenue。
- Value：T04 公司整体利润率是精确输入，但 Product-to-profit attribution 仍是缺口；Graph 不能分配 accelerator margin、incremental AI profit 或 cross-chain economics。
- Counterevidence：NVDA→TSM packaging 只是一条 navigation hypothesis，必须回到 issuer/official-policy source followup 才能进入 Evidence classification。

Market price-in 三行全部是 same-as-of typed gap；没有伪造 consensus、valuation、price reaction、ownership、crowding 或 volatility。Risk 三行保存 mechanism、boundary 与 WWC，但 probability 和 financial impact 全部 typed cannot-infer。

方法生命周期只推进到 `runtime_injected + node_level_consumed`。T06 Specialist/Lead 未运行，paid artifact 和 owner acceptance 均未证明。RC-P36-024/026/027/028 与 P35 均保持 full-chain blocker。

## 验证

- T05 functional（不含机器合同）：`5 passed in 28.48s`
- S1 compatibility + T05：`8 passed in 31.27s`
- Focused：`49 passed in 84.04s`
- Expanded（S1-S3、Workbench、Gateway/Registry、Research Graph、PIG、Skills）：`177 passed in 181.45s`
- 最终 T05 contract + Project OS：`12 passed in 31.15s`
- 模型、provider、execution/source network、external tool、live business write、Evidence promotion、Graph→Evidence、Graph Numeric allocation、admission、paid run：全部 `0`。

## 下一步与回滚

下一项仅为 `S3-T06-SPECIALIST-LEAD-CROSS-CELL-SYNTHESIS-CONTEXT-AND-TARGETED-REPAIR`，必须单独授权。回滚只需移除 T05 pack 编译/验证、三个 owner 模块中的 T05 helper、T05 contract/test/worklog，并把 backlog 恢复为 T05 ready；T02-T04 Artifact contract 不需要改写。
