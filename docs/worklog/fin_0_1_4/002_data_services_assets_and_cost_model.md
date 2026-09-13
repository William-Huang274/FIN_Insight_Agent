# 002：数据服务、用户研究资产与成本公式

2026-09-13。用户追加：建立并持续校准内部成本模型；RAG/SQL应兼容云服务和Wind等多来源，支持准确、高效、易维护、有权限和时效的导入/连接；用户成果与知识库/数据库贯通，前端围绕长期维护重构。

更新[现有产品规划](../../product/fin_0_1_4_research_plan.zh-CN.md)和公开路线图，不新建通用数据平台或另一套项目计划。内部计算口径独立放在[成本模型](../../architecture/economics/research_cost_model.zh-CN.md)。同一规划分支继续，未更改0.1.3包版本。

## 现状与外部参考

`data_library.py`/`public_library.py`为发布的本地公共快照与只读SQLite浏览；`working_notes.py`已有任务归属和版本编辑；`WorkspaceNavigation.tsx`将资料数据与研究成果分区，`DataLibrary.tsx`尚无自助外部连接管理。这些是可复用基础，不是已经完成的用户持久资产服务。

`usage_pricing.py`已有0.1.3历史公开价计算，保留原逻辑，不将其改成未经核实的现价。成本公式分离非重叠token、其他费用、固定分摊、未知、事前预测及事后校准。

参考于本次核实：[Wind官方API代码库](https://github.com/WindQuant/Official)、[Azure文档权限](https://learn.microsoft.com/en-us/azure/search/search-document-level-access-overview)、[Databricks联合查询](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-federated-queries)。只采用连接/权限同步/查询时授权/联合访问等成熟设计原则；未选择部署Azure/Databricks，未认定Wind账号或云端存储权益可用。Azure部分原生ACL功能属于preview且权限更新依赖同步，不能把采用服务当作权限即时生效保证。

## 可复算结果

通过Python标准库Decimal读取公开`evaluation-metrics.json`，校验每段input+output=total、cache_hit<=input、125请求和4.633069元总额；输出小型JSON绑定输入SHA。四阶段费用占比33.97%、23.57%、26.21%、16.25%；输入缓存命中72.85%。只将阶段用途与费用对应，不做无证的可节省比例归因。该样本含人工修改后继续，不是用户最新单case口径，不能作为未来任务价格模型的充分校准集。

执行既有计价和未知费用定向测试：`tests/test_usage_pricing.py`及BFF的未知费用测试，7 passed in 13.23s。7个候选文件链接无缺失、凭据模式无命中、输入SHA匹配、diff检查通过。一次性核算在命令中完成，没有把新一次性脚本加进仓库；生成产物只含已有公开聚合值。

## 下一可执行切片

一项目、一远程结构化数据路径、一文档/文件导入、一个可编辑成果，完成授权检索、同步新版本、源权限撤销和第二用户隔离。保留原件和用户覆盖层的区别，避免旧结论反复成为自我证据；索引异步更新期间应明确可用版本。复用现有UI组件和成熟数据服务，实际选型需能力/费用验证。

本次产品/工程实现增量为0；离线证据增量为历史用量核算及现有计价验证；文档增量为公式、范围和接续记录。无新模型调用、云服务购买、Wind认证、数据迁移或前端部署。阶段停止条件仍有效：后续进入可执行数据/运行切片，不继续只扩大连接器和平台规划。
