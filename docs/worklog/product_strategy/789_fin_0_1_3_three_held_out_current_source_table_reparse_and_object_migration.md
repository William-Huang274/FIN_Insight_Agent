# 789 — FIN 0.1.3 三个留出案例 current-source 表格复原与对象迁移

日期：2026-08-09

阶段：S1／留出案例对象形状泛化

状态：工程通过，独立 clean proof 待执行；不等于 Evidence Pack 或产品研报通过

## 1. 为什么做这一项

ORCL、ASML、ANET 的官方截至期资料已经 capture-first 保存，但旧解析会把表头、日期、币种、行列和父表语境拆散。若直接重建 sparse／dense，错误对象会被向量索引放大。本项只使用不可变原始 capture，统一完成 table-preserving reparse、Metric／Claim 对象化和 `FinancialCandidateBundleV2` 投影；网络、Provider、模型、embedding、rerank、Evidence promotion 与索引写入均为 0。

## 2. 真实工程发现与修复

1. ASML Q2 2026 6-K exhibit 的“Figures in millions of euros”曾被默认成 USD；Q1／Q2 表头数字、系统销量、联系人电话也会被误认成货币 metric。现按实际响应 MIME＋正文签名选择 parser，并分别保留 EUR、count、percent 与 per-share 单位。
2. Oracle 债务表由两层表头组成：`2026／2025` 下面还有 `Amount／Effective Interest Rate`。旧逻辑把债券发行年或到期年当成列期间，并因行名含 `%` 把金额列也标成 percent。现组合两层坐标，得到 `Amount 2026`、`Effective Interest Rate 2026` 等真实列语义，并按原始单元格判定金额或利率。
3. 初次机器结果虽通过数量门，却在人工业务复核中把 Oracle 债务利率分到现金／风险 Slot；原因是路由读取了整张表的 context。随后又发现 ANET“有价证券到期回款”被 `maturities` 误分到债务、数值表中的 `Customer relationships` 实为无形资产而非客户关系证据。现 metric 路由只使用该行自身语义，并把现金回款、债务／利率、无形资产分别归到正确通用 Slot。
4. 选择示例曾因每个对象继承 source-level period end 而把 2025 行排在 2026 行之前。现 current-period 排序只使用单元格列名与 cell period，不再借用父文档期间制造“当前期”假象。
5. 缺 table／row／column／period／unit、解析不唯一、lineage 不一致或 currency authority 缺失的对象保留为 typed reject，不做默认填充。

## 3. 预冻结诊断没有被冒充成功

本项在提交前执行了人工业务复核。以下 working-tree materialization 均未冻结为正式产品结果；其私有 CAS 对象继续保留，digest 与处置在此登记：

- `51f4725b...f555c`：数量门通过，但 whole-table context 造成 Slot 污染；退回。
- `fca7011f...1601e5`：行级路由已修，但债务表多层表头与金额／利率单位仍错位；退回。
- `fcd4c510...2b5132`：坐标修复后，仍发现 current-period 示例选择借用了父期间；退回。
- `83cf8b1a...a6dfe0`：公开业务摘要已补齐，但 current-period 排序仍未纠正；退回。

这些不是四次模型或外网试跑；均为同一零调用实现包的预冻结回放。最终结果使用新的内容 digest，不覆盖任何已经提交或已授权 live 结果。

## 4. 最终本地结果

正式 materialized result digest：`a2184a963597a4f2bc355faf1f911796ed12af8abe8f5e2f11c83b80f942603c`。

| 案例 | 表格 | 准入 table metrics | typed rejects | projected bundles | projected Slots |
|---|---:|---:|---:|---:|---:|
| ORCL | 87 | 1,132 | 353 | 27 | 8 |
| ASML | 2 | 18 | 0 | 13 | 5 |
| ANET | 43 | 470 | 238 | 27 | 7 |

三案 unsafe numeric bundle admission 均为 0；9 项 mutation 全部通过。人工抽查的当前期业务样例包括：

- ORCL：FY2026 unpaid capex `USD 5,279m`、2026 有效债务利率 `2.36%`、收入税现金支付 `USD 3,704m`、客户预付款导致的递延收入增加 `USD 4,592m`；
- ASML：Q2 2026 cash＋short-term investments `EUR 7,582m`、Installed Base Management sales `EUR 2,762m`、新光刻系统销量 `86` 台；
- ANET：2026 PP&E gross `USD 577.2m`、debt securities `USD 11,053.1m`、上半年现金净增加 `USD 326.3m`、三个月 gross margin `62.9%`。

## 5. 产品边界与下一步

本项只证明同一通用 parser／object／bundle 合同能处理美国 10-K、non-US 6-K exhibit 与美国 10-Q 的当前源，并安全拒绝不完整对象。它没有证明 narrative claim 的研究质量；公开样例中仍可看到法律／前瞻性套话，因此下一索引 manifest 只能消费经过明确选择的 CandidateBundle，不能把全部自动 claims 无差别写入主索引。

当前可记为 `object-shape generalization engineering pass`，但 `held_out product generalization=false`、Evidence Pack=false、外源补源=false、DeepSeek research=false、release=false。下一步先做一次 clean Git archive／fresh-process 独立复证；通过后才重定基 sparse/dense manifest，并沿用已资格化的 Ubuntu WSL Milvus 路径。索引成功后才以本地 residual gaps 驱动外源补源，最后再让 DeepSeek 做动态追问和研究综合。
