# 636 FIN 0.1.3 S1-01 financial temporal truth 与时间角色修复

日期：2026-08-06
状态：`S1_01_engineering_pass / RC-P36-130_closed / S1_02_next`

## 结论

DELL 的错误不是模型生成，也不是 renderer 展示问题。最早错误发生在 SEC CompanyFacts 归一化：同一份 10-K 中，SEC 的 `fp=FY` 同时可能出现在全年事实和离散第四季度事实上；旧分类器只要看到 `FY` 就标 annual，导致覆盖 `2024-11-02..2025-01-31` 的 91 天营收 `23.931B` 冒充 FY2025 全年。Runtime 选择器、Gold Mart 和 SQL adapter 随后继续传播该错误，并把本地快照/研究截止时间混入 filing date。

S1-01 已从最早错误点修复并完成实际生成态重建。FIN 0.1.3 当前 SQL→Numeric 真值为：

- DELL FY2025 revenue：`95,567,000,000 USD`，`2024-02-03..2025-01-31`，364 天，filed/published=`2025-03-25`；
- MU FY2025 revenue：`37,378,000,000 USD`，`2024-08-30..2025-08-28`，364 天，filed/published=`2025-10-03`；
- NVDA FY2025 revenue：`130,497,000,000 USD`，`2024-01-29..2025-01-26`，364 天，filed/published=`2025-02-26`。

## 实现

- CompanyFacts period classifier 改为由 inclusive start/end duration 决定：annual 330–380 天、qtd 75–110 天、ytd 111–329 天、无 start 为 instant；`fp/form` 仅作 presentation hint。
- 10-K 内 raw `FY` 的离散季度事实按日期识别为 qtd，并在可证明时投影为 canonical `Q4`；保留 `raw_fiscal_period=FY` 供审计。
- Runtime selector 不信任旧 staging 的 `period_role`，读取时重新计算 duration；flow metric 先按 annual/ytd/qtd semantic authority 排序，再比较 fiscal year、form 与 filing date。
- Runtime row 与 Gold Mart v0.2 增加 period start/end/role/duration、raw/canonical fiscal period，以及四类时间字段。
- `source_filed_at` 是 filing receipt date，`published_at` 是 public availability，`as_of_date` 是研究请求截止，`snapshot_at` 是本地抓取/物化时间；禁止由 generated/as-of 反填 filing。
- SQLite migration 使用 `ALTER TABLE ADD COLUMN` 补齐旧库，保留既有数据和路径；随后完整 replace materialization 产生 current v0.2 rows。
- Exact SQL 只选择 cutoff 前、annual、exact-value-authority 的 revenue/gross profit/operating income；Numeric projection 保留全部期间和时间 lineage。

## 实际重建

- Runtime：`10,146 rows / 587 tickers / schema v0.2`，生成文件约 43.5MB。
- Gold Mart：`74,897 rows / 74,897 SQLite rows / 17 source rowsets / 0 missing`，SQLite 约 429.6MB。
- 三案例通过实际 canonical SQLite、ExactValueSqlSearchAdapter 与 Numeric projection，不是只使用内存 fixture。
- 生成态大文件保持本机忽略，不作为 Git payload；tracked summary、代码、测试、decision 和哈希证明进入仓库。

## 验证

- S0+S1 current focused：`46 passed / 1 deselected`。唯一 deselection 是 S0-02 对后来合法修改的 legacy-compatible T03 文件要求永久等于 event-time SHA；旧 decision 不重写。无法恢复四类时间的 legacy text-only numeric candidate 另有 fail-closed mutation。
- 相邻 T03–T05 functional：`19 passed / 2 deselected`。两项 deselection 分别是旧 T04 exact-input digest 与旧 T05-B materializer 对 living T04 source SHA 的历史断言。
- mutation 覆盖：10-K Q4 raw FY 伪装、future post-cutoff fact、annual/qtd/ytd/instant、旧 SQLite migration、snapshot/filed 污染。
- model/provider/network/source/business Run/Artifact=`0/0/0/0/0/0`。

## 阶段边界与反思

本轮没有手工替换 DELL 数字，也没有修改旧 0.1.2 Evidence Pack 或 acceptance。旧输入/data/source digest 变化后，旧 R2/R3 不能继承给 0.1.3。S1-01 只关闭期间与时间真值根因 RC-P36-130；material Numeric 覆盖和公式属于 S1-02，来源 exhaustion 属于 S1-03，Graph 属于 S1-04，检索 usefulness 属于 S1-05，研究内容仍属于 S2/S3。

本轮也再次证明：把 living code SHA 写进旧证明、再让以后阶段永远执行旧断言，会把正常演进误报成回归。当前 active suite 因此保留历史 event-time receipt，但只让 current semantic/functional test 建立 authority，不更新旧 SHA 来伪造连续性。

## 下一步

进入 `FIN-0.1.3-013-S1-02-MATERIAL-NUMERIC-PROGRAM-FORMULA-RECALCULATION-AND-TYPED-GAP-COVERAGE`：盘点三案例核心 Claim/表格需要哪些 material number，建立本地公式重算、entity/period/unit/scale/source 绑定与 typed gap；不提前做来源网络补齐、Graph、模型或 full-chain。
