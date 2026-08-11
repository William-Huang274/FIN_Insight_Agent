# P38 Institutional Research Positioning Canonical PRD / TECH Refactor

日期：2026-07-12

状态：`documentation_contract_update_complete / no_runtime_change / no_paid_or_full_chain_run`

## 1. 问题

WorkBuddy 外部平台校准和仓库审计表明，通用 Deep Research、金融 Skill、网页搜索和漂亮 HTML 已成为 table stakes。FIN 的产品定位需要从“可审计金融研究工作台 / AI junior analyst layer”升级为机构研究控制与记忆系统，并确保 PRD、TECH owner、runtime boundary、产品 surface 和 eval 不断连。

## 2. 决策

按严格 upstream-first 顺序更新：

```text
PRD
 -> TECH_00 / TECH_00A owner constitution
 -> TECH_01 / TECH_06 + Point 01 compatibility
 -> TECH_02 / 03 / 04 / 05
 -> TECH_07 / 08 / 09 / 11 / 10
```

`InstitutionalResearchCase` 是 aggregate identity/ref graph，不是万能大表。每个 stable object 只有一个 business truth writer，可以另有 physical persistence owner 和 read/index/projection consumers。

## 3. 完成内容

- PRD：正式升级定位；增加 ResearchCase 生命周期、五个产品平面、Institutional Memory、Human-AI Accountability、机构配置治理、provider-neutral capability frontier 和 R1-R4 research outcome。
- TECH_00/00A：增加 stable aggregate、Owner Constitution、责任链对象和新定位 coverage/eval rows；消除 evidence/memory/approval joint ownership。
- TECH_01/06：分别定义 ResearchCase 研究业务状态与 durable execution/ActorSnapshot/AccountabilityEvent/OA hooks。
- Point 01：只增加 Case identity、Actor/Event/Artifact refs 和 longitudinal compatibility fixtures，不扩成完整 Memory/Review/OA/Monitoring runtime。
- TECH_02-05：固定 Evidence promotion、Memory address/PIT、Numeric hard gate/recompute 和 Judgment delta/supersession 的单一 owner 链。
- TECH_07-10/11：修正 Context 与 Memory 边界，增加 configurable Agent/Skill、DecisionAttestation/ArtifactProvenanceManifest、targeted refresh/stale propagation 和 R1-R4 eval。
- 两份定位/影响审计草稿标记为已吸收的历史材料，不再与 canonical 文档竞争 source of truth。

## 4. 验证

- 对所有触及 Markdown 执行 `git diff --check`。
- 扫描旧冲突表述：Evidence 共同拥有、TECH_07 长期 memory owner、TaskRun/Report aggregate root。
- 反查关键对象跨文档覆盖：InstitutionalResearchCase、ActorSnapshot、DecisionAttestation、ArtifactProvenanceManifest、MemoryWriteCandidate、ProviderPolicyVersion 和 R4 longitudinal outcome。

本轮只更新文档合同；未修改 runtime/schema/code，未运行 paid LLM、full-chain、retrieval/parser、Workbench、OA、SSO/SCIM 或 R1-R4 fixtures。所有新增能力仍为 `documented / contract_draft`。

## 5. 后续

下一步应基于更新后的 Point 01 做 M0 canonical schema/legacy mapping/ADR 复核，再进入实现。实现不得跳过 upstream contract，也不得把字段存在写成 runtime capability 已完成。
