# 224 Release Operating Model 与 FIN 0.1 Internal Alpha 计划

日期：2026-07-17
状态：`documentation_and_release_contract_frozen / no_runtime_execution`

## 问题

Point 01 的控制面实施和复核不断扩展，虽然提高了 authority、receipt、append-only 和 rollback 质量，但产品缺少稳定版本节奏，导致 TECH/Point 的局部完整性持续压过用户可见纵向结果。需要在不放弃上线治理的前提下，明确何时关闭 Foundation、何时进入真正产品版本，以及哪些风险阻断、哪些债务延后。

## 决策

1. 产品版本以纵向 Research Outcome Slice 为单位，不以 TECH 编号或 Point milestone 为单位。
2. 主产品采用四周列车；第 3-4 周只允许 hard blocker 修复、review、rollback 和冻结。
3. 状态拆为 release channel、L0-L4、R1-R4、capability maturity、production readiness，不再使用笼统 `complete`。
4. 每个产品版本最多五个 release-blocking gates；同一 blocker 最多两轮 bounded repair，之后必须 block/defer/stop 裁决。
5. Point 01 只服务 `REL-FND-001 / Foundation 0.1`，以 `POINT01_FOUNDATION_ALPHA_COMPLETE` 收口；production 仍 not admitted，legacy global authority retained。
6. 下一真正上线版本固定为 `REL-PROD-001 / FIN 0.1 Internal Alpha`，目标产品 L2、Anchor Case R2。2026-07-17 复审后明确：P36 六条 AI infrastructure 链只作为 mandatory cell families，不能代替完整产品 feature scope。
7. 下一面向试点的标准工作流为 Earnings Alpha；Review/Memory、跨行业和 Enterprise Pilot 后续逐版进入。

## 已完成

- 新增产品发布阶梯：`docs/product/PRODUCT_20260717_release_ladder_and_cadence.zh-CN.md`；
- 新增技术发布运行模型：`docs/architecture/repository/RELEASE_OPERATING_MODEL_20260717.zh-CN.md`；
- 新增 canonical Point 模板：`docs/architecture/repository/POINT_EXECUTION_PLAN_TEMPLATE.zh-CN.md`；
- 新增下一版本执行计划：`docs/architecture/repository/RELEASE_FIN_IA_0_1_EXECUTION_PLAN_20260717.zh-CN.md`；
- 新增机器可读 ReleaseContract v1.0；后续范围复审以 v1.1 supersede，旧版保留审计；
- 更新 PRD、TECH_00、TECH_10、下一阶段讨论草稿、Point 01 closeout contract、Product/Repository 索引和 Project OS。

## FIN 0.1 范围

Anchor 为 P36 AI infrastructure，accelerator、server OEM、foundry/packaging、HBM、semicap、cross-chain counterevidence/WWC 是六个 mandatory cell families；Lead 应动态编译 10-20 个实际 cells。完整产品链为：

```text
Dashboard / Task Center / ResearchCase / DecisionSurface planning review
 -> EvidenceRequest / retrieval / repair
 -> parser / numeric / Evidence Gate
 -> Workpaper / domain judgment / LeadReview / targeted repair
 -> Writer no-source
 -> Workbench / HTML / Markdown / Human Review / provenance
 -> internal dogfood / release
```

结构回归使用 Enterprise AI/SaaS 和 US Banks，但不继承 WorkBuddy 报告事实、数字、估值、排名、概率或搜索轨迹。

## 验证

- 本轮未运行 runtime、模型、网络、paid/full-chain、数据库 migration 或生产切换；
- ReleaseContract JSON 将通过本地 JSON parse 校验；
- Markdown 链接、diff whitespace 和候选文件秘密模式将在 closeout 前检查。

## 边界与后续

- 本轮是发布制度和执行合同落地，不证明 FIN 0.1 已实现；
- FIN 0.1 入口仍被 Point 01 P01-G5 阻断；
- Point 02-07 child plans 必须使用新模板，并由 `REL-PROD-001` 反推，不再横向实现 TECH_01-11；
- paid/model node、commercial data、真实客户数据和 production cutover 均需后续独立授权。

## 2026-07-17 产品范围纠正

原 v1.0 计划把 Anchor Case 的六个研究主题写得过像产品功能列表，低估了 PRD 中 B0/B2/B7 对产品壳、Workpaper、repair、review 和 trace 的要求。已新增 `FIN_0_1_INTERNAL_ALPHA_FEATURE_SCOPE_MATRIX_20260717.zh-CN.md`，冻结 `P001-F01`-`F15` 和七个必需 product surfaces；创建 `fin_ia_0_1_release_contract_v1_1.json` supersede v1.0。该修订仍是 docs/machine contract，不表示 runtime 或产品已实现。
