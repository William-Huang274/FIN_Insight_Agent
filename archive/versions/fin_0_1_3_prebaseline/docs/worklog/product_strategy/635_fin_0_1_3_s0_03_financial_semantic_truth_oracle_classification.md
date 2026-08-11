# 635 FIN 0.1.3 S0-03 financial semantic truth-oracle 分类

日期：2026-08-06
状态：`S0_03_engineering_pass / S0_complete / current_DELL_truth_blocked / S1_01_next`

## 为什么属于 S0

此前 72 项相关测试全绿，却没有发现 DELL 把 91 天的 Q4 营收当成全年营收。问题不是测试数量不够，而是测试层级混在一起：schema、digest、cardinality 和 renderer 一致被误当成金融真值。本项先建立共同分类和早期门禁，不在页面层改数字，也不提前做 S1 数据修复。

## 实现

- 新增 deterministic financial semantic truth oracle，分为：
  - `shape_integrity`：合同、字段和基础类型；
  - `financial_truth`：entity、issuer、metric、period、duration、unit、scale、formula 和时间角色；
  - `analysis_quality`：公司专属机制、证据论证、Numeric 解释和研究综合，归 S2/S3；
  - `product_usability`：任务、repair、review 和交付可用性，归 S4。
- shape 与 financial truth 在进入 S1/S3 消费前 fail closed；analysis/usability 不冒充 truth failure，但仍在所属阶段与 S5 release-blocking。
- 为 DELL、MU、NVDA 建立 source-bound reviewed FY2025 revenue 对照，并保留当前 DELL 错误候选作为 expected block。
- 年度 duration 只接受 inclusive 330–380 天、季度接受 75–110 天；10-K/10-Q form 不能单独决定事实 duration，同一 period end 也不能推导相同 duration。
- `source_filed_at`、`published_at`、`as_of_date` 和 `snapshot_at` 分角色比较，禁止互相代填。
- derived formula 支持 add/subtract/multiply/divide 本地重算和 tolerance；无法重算或结果不符直接进入 financial truth finding。
- 生成 S0-03 machine decision 与 S0 active-suite R3 successor。

## 当前 DELL 的实际结果

- current Evidence Pack 的 revenue 仍为 `23,931,000,000 USD / FY2025-FY / source_filed_at=2026-06-23`。
- reviewed source row显示该值覆盖 `2024-11-02..2025-01-31`，共 91 天，应为 FY2025 Q4；真实 FY2025 annual revenue 是 `95,567,000,000 USD`，覆盖 364 天。
- oracle 对 current row 给出四个 financial truth finding：`fiscal_period_mismatch`、`period_role_mismatch`、`source_filed_at_mismatch`、`annual_duration_out_of_range`。
- 因此 current DELL product truth 仍为 false；S0 通过不是把错误改成通过，而是证明以后不能再被 72 个 shape test 掩盖。

## 验证

- 新 S0-03 contract/mutation：`15 passed`。
- S0-01 + S0-02 + S0-03 canonical active suite：`29 passed`。
- 加入 DELL current Evidence/产品面与旧 S3 financial pack 相邻回归：`51 passed`。
- mutation 覆盖 entity/issuer、annual/quarter/duration、unit/currency、scale/normalized value、formula、四类时间角色、shape/analysis/usability 路由。
- machine decision 与 active-suite digest 重算通过。
- 更新 living 研究质量 Rubric 后，旧 S0-01 测试曾按历史 SHA 要求当前文档永久保持旧字节而失败；按 S0-02 已冻结治理规则改为保留 S0-01 event-time digest，并由 S0-03 source binding 精确绑定当前 Rubric，未重写旧 baseline。
- 相邻旧 S3-T04 数值测试另有 1 项把 living 全局 backlog 的当前 next action 绑定为历史 S3-T09；最小修正为验证 T04 event 自身的 T05 handoff，未改写历史合同或扩大 S3 功能。
- model/provider/network/source/business run/Artifact/current data rewrite 均为 0。

## 产品和研究边界

S0 现已完成版本继承、secret-safe truth projection、shared exact-once admission、历史 receipt 治理和金融语义分类。它没有修复 staging/mart 中的 DELL duration，也没有提高 Evidence、Graph、Claim、Lead、Writer、报告或 Workbench。八维内容质量仅完成 S0 layer registry，S2–S5 的 evaluator、Verifier、页面与人工内容验收仍待实现。

## 下一步

进入 `013-S1-01`：在最早 structured fact/runtime-row/gold mart 选择逻辑中区分 annual、quarter、YTD 和 instant，修复 DELL FY/Q4 选择，并将 filed/published/as-of/snapshot 拆字段后重建 current 下游事实；先做零调用三案与对抗 fixture，不调用模型或 full-chain。
