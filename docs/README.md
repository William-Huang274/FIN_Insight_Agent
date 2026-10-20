# FinSight 文档

当前0.1.4研究runtime开发与测点顺序见[按Agent流转的分段资格路线](engineering/runtime_flow_qualification.zh-CN.md)。

Lead初步判断的依据边界、具体任务依赖和分阶段模型试验见[初步判断与模型选择](engineering/lead_reasoning_and_model_routing.zh-CN.md)。

专家底稿与 Lead 成文实际使用的行文方法、支撑记录与正文分工见[投研写作方法](engineering/research_writing.zh-CN.md)。

专家接续时的原件保留、准确回读、目录条目投影和工作笔记替代见[研究上下文生命周期](engineering/research_context_lifecycle.zh-CN.md)。

FinSight Agent 是支持资料查询、来源追溯、多角色研究和人工修订的本地金融研究工作台。

| 文档 | 内容 |
| --- | --- |
| [历史案例应用验收](engineering/historical_application_scenarios.zh-CN.md) | 固定 runtime 基线，复用旧案例验证 Java/Python 资料、向量与知识库路径；只读缓存、逐场景证据和待接权限边界 |
| [组织授权混合检索](engineering/organization_hybrid_retrieval.zh-CN.md) | 已准备向量与 BM25 的授权前置、固定版本、执行范围缓存、历史真实向量的跨组织验收；不调用提供方 |
| [Java / Python 共同版本](engineering/java_python_integration.zh-CN.md) | 业务受理与新版研究配置整合、修订到接续的配置继承、旧请求兼容及分层静态验收 |
| [Java 到原生队列生命周期](engineering/java_native_lifecycle.zh-CN.md) | 真实BFF/Java/持久队列的无模型资格、重启回读、停止竞态与确定性研究图边界 |
| [组织首次运行与准入](engineering/organization_native_start.zh-CN.md) | 固定启动命令、唯一原生运行、响应未知核对与组织工厂；当前页面入口见组织研究浏览器操作 |
| [组织研究读取权限](engineering/organization_research_reads.zh-CN.md) | 项目与全部固定来源的当前读权限、事件/报告/引用快照/导出；项目成果只读入口 |
| [组织预研究显式接续](engineering/organization_native_continuation.zh-CN.md) | 独立持久命令、前序运行与 checkpoint 绑定、未知回执核对；浏览器按原发起人权限提供操作 |
| [产品导览](public/demo-and-engineering.zh-CN.md) · [English](public/demo-and-engineering.en.md) | 从研究问题到报告交付的界面与操作 |
| [快速开始](public/quickstart.zh-CN.md) · [English](public/quickstart.en.md) | 环境准备、运行命令、测试和升级 |
| [系统架构](public/architecture.zh-CN.md) · [English](public/architecture.en.md) | 执行、资料检索、计算和存储的职责 |
| [评测报告](public/technical-evaluation.zh-CN.md) · [English](public/technical-evaluation.en.md) | 数据集、方法、结果及适用范围 |
| [v0.1.3 版本说明](product/version_0_1_3.zh-CN.md) | 已有功能与使用条件 |
| [路线图](product/roadmap.zh-CN.md) | 后续研究能力的开发方向 |
| [Java 项目研究接入](engineering/java_research_intake.zh-CN.md) · [产品范围](product/java_research_intake.zh-CN.md) | 项目工作区、资料库按项目筛选；第一阶段 A 持久业务任务、明确启动及未知提交核对，可选启用 |
| [组织资料空间](engineering/resource_spaces.zh-CN.md) | 统一空间/类型入口、组织内个人区、团队成员、固定版本发布及授权阅读；实时团队数据库和共享研究待接入 |
| [组织项目与成员](engineering/organization_projects.zh-CN.md) | Java 项目归属、角色、版本冲突与静态验收案例；团队研究仍待接入 |
| [项目关联空间资料](engineering/project_resource_links.zh-CN.md) | 项目资料入口、按组织项目筛选、项目与源权限分别核验、固定版本和撤权 |
| [组织研究输入准备](engineering/organization_research_inputs.zh-CN.md) | 不可变问题/版本清单、全部依赖当前权限、原件校验及未知提交恢复；尚不创建团队运行 |
| [组织研究浏览器操作](engineering/organization_research_browser.zh-CN.md) | 项目内准备、启动、确认接续、未知结果核对与事件展示；静态模型验收，未切换既有部署 |
| [组织研究真实服务业务验收](engineering/organization_business_delivery.zh-CN.md) | 浏览器直连 BFF/Java/数据库/原生队列，静态报告四格式交付、五服务重启、响应丢失核对与撤权；不评估金融质量 |
| [组织执行绑定与资料工具](engineering/organization_execution_access.zh-CN.md) | 独立运行身份、逐次核权、固定资料 MCP、原文引用/计算适配；尚未接入完整团队运行 |
| [组织研究原生草稿](engineering/organization_native_drafts.zh-CN.md) | 固定身份与配置、一次派发、未知回执核对、真实服务重启；不创建团队 run |
| [Java 请求生命周期与故障恢复](engineering/java_intake_recovery.zh-CN.md) | 幂等、未知回执、进程故障与旧运行事件隔离；合成执行验证及未验收边界 |
| [v0.1.4 PRD](product/fin_0_1_4_prd.zh-CN.md) · [技术方案](architecture/fin_0_1_4_technical_design.zh-CN.md) · [执行路线](engineering/fin_0_1_4_execution_roadmap.zh-CN.md) | 开发中；局部功能已实现，整版未验收或发布 |
| [项目资料版本与更新](engineering/project_asset_versions.zh-CN.md) | 0.1.4 开发分支的版本差异、直接依赖提示、明确选版与适用范围 |
| [研究问题体系](product/research_question_system.zh-CN.md) · [行业方法与执行合同](architecture/research_method_execution.zh-CN.md) | 六类免费来源如何组合成研究问题、行业步骤、动态委派与有界诊断；非完整研究质量认证 |
| [专题团队运行时设计](architecture/research_team_runtime_design.zh-CN.md) | 专题负责人和专业执行者的代码接入、快照澄清、版本通信、用户裁决与实施工作包；设计未实现 |
| [六维来源分层测试](engineering/six_source_qualification.zh-CN.md) | 先基础知识与数据处理，再简单/复杂组合与困难题；逐题分类、归因、修复复验及GraphRAG接入测点 |
| [资产工作区与交接协议](architecture/asset_workspace_protocol.zh-CN.md) | 知识库/财务库/项目资料统一界面、研究侧栏、版本与记忆交接、项目库恢复及边界 |
| [AI 行业数据基座](architecture/ai_industry_data_foundation.zh-CN.md) | 两轮公司扩展、SEC/API 采集、SQL 原文与数据、来源关系检索、Qwen 索引及公司光谱界面；逐公司覆盖缺口独立记录 |
| [原文子块与向量检索](architecture/library_chunks_and_vectors.zh-CN.md) | 有界子块、父原文引用、图边证据关联、正文 embedding、持久索引及失败请求恢复边界 |
| [知识库与数据库检索优化方案](architecture/retrieval_optimization_review.zh-CN.md) · [执行记录](architecture/retrieval_query_execution.zh-CN.md) | 已批准、实施中：图辅助混合检索、SQL与读取优化、关系遗漏审计、工具边界及分阶段验收 |
| [Lead 图辅助研究规划](product/lead_graph_research.zh-CN.md) · [工具与测试设计](engineering/lead_graph_planning_evaluation.zh-CN.md) | 已接入预研究、非阻塞反馈与意见卡片，完成一例正式 runtime 开发试跑；独立质量评测与外部取证授权仍待验证 |
| [当前研究运行契约](engineering/current_research_contract.zh-CN.md) | 任务身份、方法/MCP 绑定、通用能力、旧记录兼容与历史数据边界 |
| [Lead 图导航、时间与引用](engineering/lead_graph_navigation_and_citations.zh-CN.md) | 正式资料空间序列化、局部图入口、资料日期范围、原文摘录定位与 DS max 开发观察 |
| [Java 与 Python 研究资料接口](architecture/java_research_service_contract.zh-CN.md) | 已初步对齐：业务/研究职责、七类查询能力、授权/快照/数值合同及付费与事件恢复；未实现 |
| [指标工作区](architecture/metric_workspace.zh-CN.md) | 指标日期合同、独立数据卡、趋势与多公司比较、同源工具及行业数据导入 |
| [指标工作区 r18 交付](architecture/metric_workspace_r18_delivery.zh-CN.md) | 核心20家公司首批行业指标、发布边界与逐公司缺口 |
| [行业指标 r19 补查](architecture/metric_workspace_r19_delivery.zh-CN.md) | 22项原缺口逐字段复核、新观测、比较规则与同源查询 |
| [行业指标 r20 历史补查](architecture/metric_workspace_r20_delivery.zh-CN.md) | 后续比较列补漏、已核实历史序列、订阅单位修正与逐字段边界 |
| [数据与报告说明](public/sharing-scope.md) | 示例数据、研究结果和使用范围 |
| [代码目录](architecture/repository/naming_and_entrypoints.zh-CN.md) | 模块职责和开发入口 |
