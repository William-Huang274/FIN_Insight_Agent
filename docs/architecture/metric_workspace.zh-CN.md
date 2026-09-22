# 指标工作区：观测记录、数据卡与行业字段

指标工作区把前端浏览与研究工具建立在同一个只读查询服务上。现有财务点、计算记录、来源和引用编号保持兼容；新数据通过未发布 SQL 构建库导入，验收后发布不可变版本。不得修改已经发布的数据库。

## 时间与数值合同

一条记录代表一个公司、指标定义、业务范围、期间及来源版本下的观测，不能只用“公司＋指标名＋财年”识别。

| 字段 | 含义 |
|---|---|
| `id` / `record_type` | 稳定观测编号；原始披露或确定性计算 |
| `metric` / `definition` | 指标定义及版本；名字接近不代表可比 |
| `observation_kind` / `observation_date` | 财务/经营观测或市场估值；估值使用交易日 |
| `financial_basis` | 财務起止日期、经核实的公司财年/季度、期间类型及核定依据 |
| `period_kind` | 单季、累计、全年、期末时点、TTM、日频或事件；时点不抹去季度归属 |
| `value` / `unit` | 十进制字符串和明确单位；界面舍入不修改 SQL 原值 |
| `value_state` / `comparator` | 实际、计划、指引；精确、约数、上下限、文字分开 |
| `available_at` | 本版本可获知日期；不得把抓取日冒充发布日期 |
| `business_scope` / `qualifiers` | 分部、产品、计量范围和特殊条件 |
| `source_id` / `evidence_locator` | 原文出处及页、表或片段定位 |
| `inputs` / `formula_version` | 计算输入记录、公式及其版本，可继续追溯 |

`metric_observation_index` 将这些通用日期语义及记录投影存入 SQL；原始值仍在 `financial_points`、`derived_financials` 等来源表。行业定义、观测、逐公司核查范围分别存于 `industry_metric_definitions`、`industry_metric_observations`、`industry_metric_coverage`。新版本不会覆盖旧数据的引用身份。

## 浏览与比较

- **指标总览**：按盈利、现金流、偿债、效率、估值及行业业务分组，保留不同期间和业务范围。
- **财务与经营历史**：按实际报告期浏览；财年身份未核实时只显示日期，不按自然年假定公司财年。
- **估值走势**：以交易日筛选，可按周/月选取范围内最后一个有记录的交易日。末日缺项不会被前一个有效值偷偷替代。
- **公司对比**：最多十二家公司；实际日期或经核实的公司财务阶段对齐。阶段相同仍可能覆盖不同自然月份。不同单位、期间和实际/计划状态分组，没有同日/同期记录显示缺项。
- **趋势与列表**：趋势需先选择指标，不把所有不同量纲指标混画。缺失值不填零、不插值，长时间缺档断线。约数、上下限和文字保留在列表和数据卡，不画成精确点。计划与事件不连接为已实现经营趋势。
- **独立数据卡**：点击列表、总览或趋势点打开侧边卡。卡内显示口径、日期、状态、依据和记录版本；输入可逐项追溯，原文在上层窗口阅读，关闭原文后返回原数据卡。

百分比单位的 `percent` / `PERCENT` 与 `%`、人民币 `RMB` 与 `CNY` 可做已定义的等值别名统一，并保存原单位。跨币种、ADR、拆股、分部重组、有机增长、恒定汇率等不会由前端自动推断或换算。

## 正式工具用法

`read_source_document` 的 library/data 请求使用 `data_kind="metrics"`。该入口与前端 `POST /api/v1/data-library/metrics/query` 调用相同的 `query_metrics` 服务。

1. `metric_section="catalog"`，先读公司实际存在的指标 ID、单位和期间。
2. `metric_section="history"` 或 `"valuation"`，用 `query` 传准确指标 ID，使用 `date_start/date_end`、`metric_period_kind` 和 `metric_frequency`。估值不能按分母财年筛交易日。
3. `metric_section="compare"`，指定主 `entity_id` 与 `compare_entity_ids`，核对返回的比较口径及缺项。不同业务口径只能作为带限定的并列观察。
4. `metric_section="card"`，以 `metric_record_id` 读取单条完整依据，沿输入和来源定位继续核对。

上述步骤读取已经保存的值。新报告、修订报告或缺少输入时，先加载 `get_research_method(method_id="report_processing")`，定位完整表头、正文页和附注，再进入受控提取与验证流程。不能只凭检索片段或计算器结果写入正式数据。

## 可重用导入与验收

```powershell
python -m scripts.data_retrieval.import_industry_metrics --build <unpublished.sqlite> --pack <reviewed-pack.json> --validate-only
python -m scripts.data_retrieval.import_industry_metrics --build <unpublished.sqlite> --pack <reviewed-pack.json>
```

导入前检查实体、逐公司覆盖、来源引用、原文精确摘录、数值 token 与倍率、日期、实际/指引及业务范围。先验证再事务写入；同一包可重复执行且不重复增加记录。新材料正文和检索片段一起保存，但新增片段不自动意味着已完成新的向量索引或模型检索测评。

验收分别记录工程结果、资料覆盖与财务语义。接口和前端回读相同记录不代表研究模型已理解正确；本轮不以工程测试替代独立检索效果评估。

## 行业指标补查与使用规则

`industry_metric_reviews` 追加保存逐字段核查版本，包括核查日、具体材料及章节、已补记录 ID、仍缺内容、下一来源和比较规则。旧观测不改写。结果分为已补齐本项、核查范围内未找到、来源仍受阻、口径边界、披露精度限制；不能把后四种统一改称“未披露”。混合字段只补一部分时，原缺口不标为全量解决。

`query_metrics` 的目录、历史、比较及数据卡返回 `industry_reviews`，正式研究工具和前端使用同一结果。`affected_metrics` 采用实际指标 ID；规则支持明确日期/业务范围选择器，分别生成序列分组或 `points_only`，前端不会因名称相似合并。回顾披露若只给年份，单独保存 `reference_year`；不虚构年末测量日。价格变更公告保留 `effective_at` 的 UTC 时刻及公告日。

```powershell
python -m scripts.data_retrieval.import_metric_reviews --build <unpublished.sqlite> --reviews <reviewed-fields.json> --reviewed-at YYYY-MM-DD
```

工具导入先校验全部记录，再事务追加；已解决项必须关联同公司已存的观测，来源 ID 必须存在。核查版本只在其核查日之后返回，不把后来查明的限制隐含写进更早的查询。前端“行业指标核查”可展开查看具体限制和来源，数据卡同时展示适用规则。

导出的核查记录可以再次导入；存储生成的 `id` 和 `reviewed_at` 不参与内容重复判定，同一内容与核查日保持幂等。同日补查产生新内容时追加新版本，并保留原结论。绑定 `source_id` 时还须核对其 URL 与审核材料 URL 一致，防止有效编号跳转到不相干的原文。尚未取得的电话会全文等材料应保留获取受阻，不能因其他已读材料没有数值而自动关闭为“未披露”。

后期报告明确重列历史口径时，可使用 `canonical_series` 审核规则：列出准确 `record_ids`、序列键、可读名称和依据，导入检查这些记录属于同一公司、指标、单位、期间类型和实际/指引状态。它只改变查询返回的序列分组，不改写原始 `business_scope`、数值或可知日。`annual_same_quarter` 只允许经核实的相同财季跨年记录，前端以年度同期趋势呈现，不混入其他季度或期末口径。未列入审核名单的记录不会自动归组；不同公司的可比性仍需另行判断。

经原文核实的计数单位误标可通过 `unit_corrections` 按记录 ID 修正查询投影。当前只支持 persons → subscriptions 的标签修正，必须附原记录中存在的证据及理由；不换算数值或币种。原 SQL 记录不变，工具和数据卡同时返回 `stored_unit`、修正单位及依据；历史 as-of 查询不提前使用后续修正。
