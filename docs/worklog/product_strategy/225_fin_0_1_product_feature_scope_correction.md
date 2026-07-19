# 225 FIN 0.1 产品功能范围纠正

日期：2026-07-17
状态：`product_and_release_contract_corrected / implementation_not_started`

## 问题

`REL-PROD-001` 初版计划把 P36 的六个 AI infrastructure DecisionSurface cells 写成了版本的主要功能范围。这混淆了两层对象：

- 产品功能：用户如何创建、推进、补查、审阅和追溯一项研究；
- Anchor Case 内容：本次 P36 需要覆盖哪些产业链和判断机制。

若按旧计划执行，工程可能只得到一份带六格 matrix 的 P36 memo，却缺 Dashboard/Task Center、planning checkpoint、Workpaper、Repair Queue、Human Review 和可操作 Workbench，无法达到 PRD 的 `L2_internal_dogfood_pass`。

## 决策

1. FIN 0.1 正式消费 `B0 + B2 + B3 bounded subset + B7`，不是只消费 P36 内容主题。
2. 冻结 `P001-F01`-`F15`，覆盖产品入口、ResearchCase、动态 DecisionSurface、durable execution、Agentic Search、Evidence/Numeric、Workpaper、Repair、LeadReview、Deliverable、Human Review、Provenance、bounded follow-up 和 release feedback。
3. 首版必须有七个可操作 surfaces；JSON/API 只能作为 debug/replay，不能单独证明 L2。
4. P36 六项改为 mandatory `cell families`；runtime 动态编译 10-20 cells，目标 12-16。
5. Release 只保留三个 delivery workstreams，而不是限制为三个 TECH owners；每个 workstream 消费现有 TECH_01-10 的稳定 owner 合同。
6. ReleaseContract v1.1 supersede v1.0；旧版保留审计，不作为 Point 02-07 active input。

## 修改

- 新增 `docs/product/FIN_0_1_INTERNAL_ALPHA_FEATURE_SCOPE_MATRIX_20260717.zh-CN.md`；
- 新增 `configs/releases/fin_ia_0_1_feature_scope_matrix_v1_0.json`；
- 新增 `configs/releases/fin_ia_0_1_release_contract_v1_1.json`；
- 更新 PRD、产品 release ladder、Release Operating Model、FIN 0.1 执行计划；
- 更新 TECH_00、TECH_00A、TECH_10 的 release consumption/eval 关系；
- 更新 Point 后续讨论草稿和文档索引。

## 边界

- 本轮未实现 UI/runtime，也未运行模型、网络、paid/full-chain 或数据库 migration；
- Data Room、Monitoring/R4、Research-to-Quant、全行业 pack、企业身份和全格式一致性仍 deferred；
- Point 02 child plan 尚未冻结；其第一项工作必须把 `P001-F01`-`F15` 转成 feature/story/test backlog，而不是直接跑 P36 full-chain。

## 验证

- ReleaseContract 和 FeatureScopeMatrix JSON 可解析；
- PRD/TECH/Point/Release 的 Feature IDs 和 owner mapping 一致；
- v1.0 只保留为 superseded audit artifact；
- Git diff/JSONL/secret 检查在 closeout 执行。

## 2026-07-17 前端交付合同补充

用户指出原计划虽列出 product surfaces，但没有把前端建设拆成可执行工程轨。审计确认现有执行计划容易被误读为“Point 02-05 做后端，Point 06 再包装 UI”。本次修正为：

- FIN 0.1 必须交付可操作 React/TypeScript/Vite 内部前端；
- 复用现有 Workbench/FastAPI，不建立第二套产品壳或 API source of truth；
- 前端从 Point 02 开始，按 Point 03-06 逐步增加 Evidence、Numeric、Workpaper/Repair、Deliverable/Review/Trace；
- Point 07 做浏览器 E2E、可访问性、双 viewport 和 dogfood closeout；
- JSON/API-only、console-only failure 或继续把全部能力堆入单个 `main.tsx` 均不能通过 release gate。

本次仍为产品/执行合同修订，不表示 UI 已实现，也没有运行模型、网络、paid/full-chain 或生产 cutover。
