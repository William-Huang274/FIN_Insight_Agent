# FIN 0.1 S3-T06：Specialist/Lead 跨 Cell synthesis 与定向返修

日期：2026-07-21

## 问题与授权

用户以“继续”授权当前唯一下一项 S3-T06。范围只包括零模型、零网络、零外部工具的确定性 Specialist/Lead 判断合同、测试、Project OS 和暂存；不授权 T07、真实补源、repair 执行、canonical Judgment head 写入、业务 Case mutation、付费执行、S4、release 或 production。

T06 的五项验收要求是：三份 `SpecialistJudgmentVersion` 保留事实、解释、判断三层；Lead 必须增加跨 Cell dependency、conflict 和 variant view，不能拼接文本；unsupported claim、numeric conflict、missing source 返回最早 owner；repair 必须改变输入、route、owner、hypothesis 或可验证产物且重复指纹停止；late/stale 并行输出不得提交到 current head。

## 根因与决策

历史 aggregate/judgment planner 能保留 supported/unsupported/conflict claims，但以通用 memo dimension 组织，不能自然形成 exact 三 Cell decision-surface adjudication。最早缺口位于 `src/sec_agent/langgraph_orchestrator.py`，不是 Writer，也不是增加一个 verifier gate。

实现决定：不改写历史 aggregate 主链，不新增 Runtime、Store、Registry、Writer 或 Gate family。在唯一 owner 中增加 T06 typed pack，由同一 `Fin01ResearchRuntime` 在 T02-T05 pack 之后确定性编译；消费端以相同上游输入完整重编译，任何 nested layer、repair owner 或 commit decision 改动均 fail-closed。

## 完成内容

- `src/sec_agent/langgraph_orchestrator.py`
  - 新增三份 Cell-specific `S3SpecialistJudgmentVersion`，分别保存 fact、explanation、decision layer。
  - Demand 与 Risk fact 层保持空事实；Candidate、Graph、Product、Market、Risk 只进入被标注的 context/gap。Value fact 层只保存 T04 三条 exact 来源与两项 company-total margin。
  - 新增 Lead cross-cell synthesis：3 条 dependency、3 个 conflict adjudication、1 个 bounded variant view；`text_concatenation_only=false`，不覆盖 Numeric 或 Evidence 边界。
  - 新增 unsupported claim、numeric conflict、missing source 三类 RepairTicket，分别路由 Judgment、Numeric、Evidence 最早 owner。
  - 新增 failure fingerprint admission：首次且有 changed dimension 才可形成 repair plan；相同指纹无新信息重复时停止。
  - 新增 matching/stale/late snapshot commit 判定；stale/late 均 quarantine，fixture matching 也不执行 canonical head mutation。
- `apps/workbench/backend/application/research_runtime.py`
  - 在同一 deterministic Artifact 内持久化 T06 pack 和 3×Specialist + 1×Lead consumption receipts。
  - 读回验证时重新消费并完整重编译 T06 pack。
- `tests/contract/test_fin_0_1_s3_t06_specialist_lead_cross_cell_synthesis.py`
  - 覆盖三层隔离、Lead 非拼接 synthesis、earliest-owner repair、重复指纹停止、stale/late quarantine、同 Run lineage 和 nested tamper fail-close。
- `configs/releases/fin_ia_0_1_s3_t06_specialist_lead_cross_cell_synthesis_v1_0.json`
  - 保存机器可读验收、零调用边界、方法生命周期和 T07 未授权状态。

## 独立复核

复核重点不是字段数量，而是研究语义是否越权：

1. Demand Candidate/Graph 没有被写进 fact layer。
2. T03 promotion=0，因此 Value 的 T04 来源引用单列为 `deterministic_numeric_source_refs`，`accepted_evidence_refs` 保持空；74.99%/62.42% 仍是公司整体利润率，没有变成 accelerator margin 或 incremental AI profit。
3. Risk mechanism 没有变成 current bottleneck、probability 或 financial impact。
4. Lead 的 variant view 同时消费三 Cell 并新增 dependency/conflict resolution，不是复制 Specialist direct answers。
5. Repair 返回最早 owner；Verifier/Writer 没有代替上游修事实或数字。
6. pack 自身可由 T02-T05 完整重编译，不依赖测试里的静态断言自证。

复核结论：T06 deterministic runtime/node-level scope 通过。P36-029 的 deterministic adjudication layer 已修，但 full-chain issue 不关闭，因为 model Specialist/Lead、T07 delivery、T09 paid artifact 与 T10 owner acceptance 尚未证明。

## 实际效果与边界

当前跨 Cell 结论为：NVDA 公司整体盈利能力有精确支持；持续的公司特定 AI demand 未证明；accelerator-specific value capture 未归因；packaging counterevidence 只有机制假设，概率与财务影响不可推断。因此当前输出是 bounded cannot-infer variant view，不是投资 Alpha。

方法生命周期推进到 `runtime_injected + node_level_consumed`。没有 Specialist/Lead 模型调用、没有新增事实、没有真实补源或 repair、没有 Writer/Workbench 交付、没有 owner 接受。

## 验证

- 上游 T05 兼容：`6 passed in 33.28s`
- T06 contract + functional：`7 passed in 41.59s`
- S3 entry 到 T06 focused：`42 passed in 121.17s`
- 扩展回归（S1-S3、共享 LangGraph/Runtime/contracts、Graph/PIG/Skills、Gateway/Registry、Workbench、Project OS）：`426 passed in 229.33s`
- 更广审计首轮为 `438 passed / 3 failed`：1 条是本轮 backlog next 已从 T06 前进到 T07后的 stale assertion，已修；另 2 条是既有 renderer 中文边界显示断言，和 T06 未暂存 diff 无交集。本轮没有借 Judgment 合同越权修改 presentation 行为，最终扩展集按 T06 实际影响面收口。
- Project OS deterministic tests：`6 passed in 0.21s`；broad full-chain preflight 按预期因 `RC-P30-002` 返回 blocked，本轮未请求 override、未执行 full-chain。
- 最终 T06 contract + Project OS + stable digest：`13 passed in 34.29s`；JSON/JSONL parse、credential-shaped secret scan、`git diff --check` 与 `git diff --cached --check` 通过（仅现有 CRLF normalization warning）。
- 模型、provider、execution/source network、external tool、live business write、Evidence promotion、canonical Judgment head write、repair execution、admission、paid run：全部 `0`。

## 下一步与回滚

下一项仅为 `S3-T07-THREE-CELL-WORKPAPER-REPORT-TRACE-GRAPH-DRILLDOWN-AND-REVIEW-SURFACE`，必须单独授权。回滚只需移除 T06 compiler/models、Runtime 中的 T06 compile/consume、T06 contract/test/worklog，并把 backlog 恢复为 T06 ready；T02-T05 pack 不需要改写。
