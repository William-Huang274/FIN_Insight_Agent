# FinSight 文档

当前0.1.4研究runtime开发与测点顺序见[按Agent流转的分段资格路线](engineering/runtime_flow_qualification.zh-CN.md)。

FinSight Agent 是支持资料查询、来源追溯、多角色研究和人工修订的本地金融研究工作台。

| 文档 | 内容 |
| --- | --- |
| [产品导览](public/demo-and-engineering.zh-CN.md) · [English](public/demo-and-engineering.en.md) | 从研究问题到报告交付的界面与操作 |
| [快速开始](public/quickstart.zh-CN.md) · [English](public/quickstart.en.md) | 环境准备、运行命令、测试和升级 |
| [系统架构](public/architecture.zh-CN.md) · [English](public/architecture.en.md) | 执行、资料检索、计算和存储的职责 |
| [评测报告](public/technical-evaluation.zh-CN.md) · [English](public/technical-evaluation.en.md) | 数据集、方法、结果及适用范围 |
| [v0.1.3 版本说明](product/version_0_1_3.zh-CN.md) | 已有功能与使用条件 |
| [路线图](product/roadmap.zh-CN.md) | 后续研究能力的开发方向 |
| [Java 项目研究接入](engineering/java_research_intake.zh-CN.md) · [产品范围](product/java_research_intake.zh-CN.md) | 项目工作区、资料库按项目筛选；第一阶段 A 持久业务任务、明确启动及未知提交核对，可选启用 |
| [v0.1.4 PRD](product/fin_0_1_4_prd.zh-CN.md) · [技术方案](architecture/fin_0_1_4_technical_design.zh-CN.md) · [执行路线](engineering/fin_0_1_4_execution_roadmap.zh-CN.md) | 开发中；局部功能已实现，整版未验收或发布 |
| [项目资料版本与更新](engineering/project_asset_versions.zh-CN.md) | 0.1.4 开发分支的版本差异、直接依赖提示、明确选版与适用范围 |
| [研究问题体系](product/research_question_system.zh-CN.md) · [行业方法与执行合同](architecture/research_method_execution.zh-CN.md) | 六类免费来源如何组合成研究问题、行业步骤、动态委派与有界诊断；非完整研究质量认证 |
| [专题团队运行时设计](architecture/research_team_runtime_design.zh-CN.md) | 专题负责人和专业执行者的代码接入、快照澄清、版本通信、用户裁决与实施工作包；设计未实现 |
| [六维来源分层测试](engineering/six_source_qualification.zh-CN.md) | 先基础知识与数据处理，再简单/复杂组合与困难题；逐题分类、归因、修复复验及GraphRAG接入测点 |
| [资产工作区与交接协议](architecture/asset_workspace_protocol.zh-CN.md) | 知识库/财务库/项目资料统一界面、研究侧栏、版本与记忆交接、项目库恢复及边界 |
| [AI 行业数据基座](architecture/ai_industry_data_foundation.zh-CN.md) | 两轮公司扩展、SEC/API 采集、SQL 原文与数据、来源关系检索、Qwen 索引及公司光谱界面；逐公司覆盖缺口独立记录 |
| [原文子块与向量检索](architecture/library_chunks_and_vectors.zh-CN.md) | 有界子块、父原文引用、图边证据关联、正文 embedding、持久索引及失败请求恢复边界 |
| [知识库与数据库检索优化方案](architecture/retrieval_optimization_review.zh-CN.md) | 待审阅：图辅助混合检索、SQL与读取优化、关系遗漏审计、工具边界及分阶段验收 |
| [Java 与 Python 研究资料接口](architecture/java_research_service_contract.zh-CN.md) | 已初步对齐：业务/研究职责、七类查询能力、授权/快照/数值合同及付费与事件恢复；未实现 |
| [指标工作区](architecture/metric_workspace.zh-CN.md) | 指标日期合同、独立数据卡、趋势与多公司比较、同源工具及行业数据导入 |
| [指标工作区 r18 交付](architecture/metric_workspace_r18_delivery.zh-CN.md) | 核心20家公司首批行业指标、发布边界与逐公司缺口 |
| [行业指标 r19 补查](architecture/metric_workspace_r19_delivery.zh-CN.md) | 22项原缺口逐字段复核、新观测、比较规则与同源查询 |
| [行业指标 r20 历史补查](architecture/metric_workspace_r20_delivery.zh-CN.md) | 后续比较列补漏、已核实历史序列、订阅单位修正与逐字段边界 |
| [数据与报告说明](public/sharing-scope.md) | 示例数据、研究结果和使用范围 |
| [代码目录](architecture/repository/naming_and_entrypoints.zh-CN.md) | 模块职责和开发入口 |
