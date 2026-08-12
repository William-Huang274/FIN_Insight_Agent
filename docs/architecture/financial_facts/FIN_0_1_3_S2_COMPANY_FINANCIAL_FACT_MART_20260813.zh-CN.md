# FIN 0.1.3 S2 公司财务事实 Mart 与 PIT 精确查询

日期：2026-08-13
状态：`engineering_pass / DELL_vertical_runtime_integration_pending / S2_product_not_closed`

## 1. 为什么数据库是纵切前硬门

文本检索可以找到财报中的数字，但“找到一行数字”不等于取得金融事实权威。最终可交付数值还必须回答：哪个公司、哪个指标、哪个期间、何时公开、研究截至日当时是否可知、单位是什么、来自哪次申报、是否被后续申报修订。Embedding、reranker、PDF 表格片段或 Writer 都不能替代这些约束。

因此当前链路固定为：S1 把数值意图编译成 `TypedFactRequest`；S2 公司财务事实 mart 执行精确查询，并且只返回 `NumericFact`、`typed_gap` 或 `typed_conflict`；S3 只能分析或引用已授权的 `NumericFact`。叙事检索与 SQL/PIT 精确查询是并列路线，不是二选一。

## 2. 本轮替换的旧设计

旧 SQL 诊断只做到年度 `9/9`，current-quarter 为 `0/6`；旧表还会把一个 ticker／metric 压成一行，无法保存披露 vintage，并把 fact、signal、context 混在一起。该路线没有迁入当前实现。

新 mart 从三案 2026-08-06 已保存的 SEC CompanyFacts 与 Submissions capture 零网络构建：

```mermaid
flowchart LR
    A["SEC CompanyFacts capture"] --> C["source/capture digest 校验"]
    B["SEC Submissions capture"] --> C
    C --> D["company + accession + accepted-at 绑定"]
    D --> E["期间角色编译: instant / quarter / YTD / FY"]
    E --> F["all admitted vintages SQLite mart"]
    G["S1 TypedFactRequest"] --> H["PIT / identity / period / unit 查询"]
    F --> H
    H --> I["NumericFact | typed_gap | typed_conflict"]
```

“保存全部 vintage”严格指保存全部**已被当前 capture 绑定到 filing identity 的 vintage**。无法取得 `accepted_at` 或 accession 绑定的旧 CompanyFacts 行不会被猜测接纳；它们形成可审计的 source coverage 边界。

## 3. 当前事实模型

每条 `company_fact_observation` 至少保存：

- 公司身份：ticker、CIK、legal name；
- 指标身份：标准 metric、taxonomy、concept 与 concept priority；
- 数值身份：Decimal 文本、unit、unit family；
- 时间身份：period start/end、duration、instant／quarter-discrete／fiscal-YTD／fiscal-year、FY/FP；
- 披露时点：form、accession、filed-at、accepted-at、primary document；
- 血缘：CompanyFacts/Submissions ref、digest、capture time、citation URL；
- vintage：旧观测保留，并用 supersession 关系标记当前替代项。

当前直接指标共 12 类：收入、毛利、营业利润、净利润、稀释 EPS、经营现金流、资本开支、存货、应收、应付、现金及等价物、流通股数。毛利率、营业利润率和自由现金流由同期间、同 accession 的输入事实确定性计算，并保存 formula trace；不允许模型自由算术。

## 4. 期间与 PIT 规则

1. `research_as_of` 之前尚未 accepted 的 filing 一律不可见。
2. 明确历史期间请求，在当时可用的 vintage 中选择最新披露。
3. 开放式“当前季度＋最近财年”查询把 interim/instant 锁定在同一最新 10-Q accession，并单独选择最近 10-K；不能从不同 10-Q 拼出一个看似更完整的当前季度。
4. duration 事实严格区分 quarter-discrete 与 fiscal-YTD。Micron FY2026 Q3 的九个月 OCF 不得冒充单季度 OCF。
5. 同一最新 vintage 出现相同事实身份但数值冲突时返回 `typed_conflict`，不能任选一个。
6. 不支持的指标、缺失期间、错公司、错单位族均返回 typed gap，不从 narrative candidate 猜值。

实现时自然发现并修复了一项真实业务缺陷：第一版开放期间选择器按 period role 各自取最新，曾把 DELL/NVDA 最新 Q1 与上一财年的 Q3 YTD 混在一起。现在它按 disclosure cohort 选取，同一“当前季度”不会跨申报拼接。

## 5. 零网络工程结果

- SQLite：`data/workbench_private/fin_0_1_3_s2_company_financial_fact_mart/v1/company_financial_facts.sqlite`（private、不可提交）；
- 1,319 条 source-bound observation：DELL 390、MU 463、NVDA 466；
- period role：instant 386、fiscal year 217、quarter-discrete 406、fiscal-YTD 310；
- 591 条 superseded observation 仍被保留；
- 24/24 精确 qrel：最近财年 9/9，当前 interim 15/15；
- mutation 全通过：未来 filing 隔离、YTD/季度不混淆、跨案拒绝、同期间公式 trace、当前 disclosure cohort 不串期；
- 0 网络、0 模型调用。

DELL FY2027 Q1 例子：收入 `43,842,000,000 USD`、毛利 `7,782,000,000 USD`、经营现金流 `4,081,000,000 USD`、资本开支 `963,000,000 USD`；由同一 accession 确定性得到自由现金流 `3,118,000,000 USD` 和带输入 lineage 的毛利率。

机器结果见 `configs/financial_facts/fin_ia_0_1_3_s2_company_financial_fact_mart_result_v1_0.json`，当前 result digest 为 `e5c88e63...c0a8fb`。

## 6. 当前明确边界

- 这是 S2 数据库与查询执行器的 engineering pass，不是 S2 产品关闭。
- mart 尚未挂入 Workbench 当前研究 Runtime；下一次 DELL 纵切才是第一个真实消费者证明。
- 当前只覆盖三个案例和已绑定的近年 SEC 10-K/10-Q；缺少历史 filing identity 的旧行不接纳。
- `total_debt` 尚未进入当前标准指标；DELL 当前 capture 没有可接纳 shares outstanding，MU 没有可接纳 accounts payable，均保留 typed gap。
- 市场价格、估值和行业数据属于独立 PIT market/industry mart，不混进公司报表事实表。
- metric-row、PDF 表格候选和 embedding 命中仍不拥有 NumericFact 权威。

## 7. 下一门

下一项是 DELL S1/S2/S3 纵切：由 S3 产生真实 Research Objective／EvidenceRequest；S1 使用当前 `Qwen Embedding provisional + BM25 fallback` 召回叙事对象，并把数值请求路由到本 mart；S2 返回 source-bound NumericFact；S3 使用两路结果完成研究判断。该纵切要验证“数据库事实是否真正改善研报”，并暴露 S1 角色判断、S2 指标覆盖和 S3 研究规划之间的产品级残差。纵切前不把当前 private mart 宣称为用户可用能力。
