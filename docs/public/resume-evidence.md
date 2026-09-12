# FinSight 简历成果与证据

2026-09-12补充：产品规范名为 **FinSight Agent**（早期简历FinInsight对应同一项目）。0.1.3已按本地Internal Alpha结束，0.1.4仅规划。保留个人项目、AI辅助编码、方案设计/集成/验证等真实职责；不要把版本收口写成生产上线或无人干预金融分析通过。

### 最新可选成果

- 扩充跨公司/技术/市场资料并接入可视化资料库，最新70文档/66唯一URL、9253节点/12994块与五公司2274财务观察；通过AI内存投资案例完成四份角色底稿和分析师审阅报告。该案例native Writer未完成，不声称全自动交付。
- 基于实际请求审计区分工具可达、最终原文保留与金融语义纠偏问题；完成2题×2材料条件×4模型配置的16调用固定资料对照，发现错误草稿对现金流分类及单位判断的影响，保留未通过候选并维持生产默认。适合Agent评测/可靠性岗位，不包装成性能提升。
- 支持前端编辑研究方向、目标、方法和审查顺序，配置版本实际进入运行；不写任意图拓扑自编排。

### 对现有六条简历的指导

1. 平台条保留用户定义问题、设计、集成、验证及AI辅助实现的真实归属，避免“完全独立手写生产系统”。
2. 编排条可以强调真实配置消费与责任角色修订；“减少重复”不扩大为所有复杂研究已经高效。
3. 数据条保留37派生指标与来源绑定，最新资料规模和旧检索评测分母分开。
4. 记忆条4/4为经批准保存的原始对象回读，不是4题完整语义恢复；需要时用19真实回合替换，但须注明含恢复/交接。
5. 交付条保留人工审阅/版本化修订，不能省去人工而变成全自动投研正确。
6. 78.6%来自NVDA/MU同一小题41→9调用、506744→108491tokens的单次局部对照；独立复核后仍待人审，未证明复杂研究同质量节费。适合面试解释，篇幅紧可优先换成更稳的检索或状态恢复事实。

0.1.4的动态大小skill、规则自动更新、主动风险挖掘与按期研究收敛不能放入“已完成”简历。以上建议只更新项目证据，不覆盖任何已投递简历。


2026-09-11 · 仅使用可定位实测，不将计划写成成果。

[中文技术报告](technical-evaluation.zh-CN.md) · [English technical report](technical-evaluation.en.md)

## 中文简历可用版本

**FinSight 金融研究 Agent 工作台｜Python、LangGraph、React、SQL、Qwen、OIDC、Docker**

- 构建支持多轮研究、角色底稿、人工修订和 MD/PDF/Word 导出的 Agent 工作台；打通 checkpoint 接续与版本化工作记忆，在 19 个真实跨主题用户回合（含局部恢复及重启交接）中验证原始数据、撤回要求和人工报告版本回读。
- 实现 BM25、Qwen 向量与重排的混合检索及调用缓存；在 1,105 个资料片段、28 条开放标注查询的同资料评测中，24 个正例 Hit@5 从 BM25 的 50.0% 提升至 95.8%，验证组锚点 Recall@5 达 0.849。
- 统一研究 MCP 与对话 SQL 数据入口，维护覆盖 5 家公司的 2,274 条财务观测及标准派生指标；通过 10 批跨入口查询验证数值、期间和单位一致，修复分裂数据快照造成的研究阻断。
- 集成 OIDC/PKCE 登录、服务端资源归属校验和持久化提交回执；完成真实双用户 39 项资源隔离检查及 8 个并发读请求，并验证服务重启后重复提交仍对应同一任务。
- 接通前端审批、LangGraph 接续、受认证 MCP 与 Docker 隔离执行；完成 4 个真实前端权限场景，验证批准前零容器活动、拒绝零执行及执行后临时容器清理。

篇幅有限时优先采用前两条，再根据岗位选择数据或身份工程一条。数字不能脱离这里的分母与条件使用。

## English résumé version

**FinSight Financial Research Agent Workspace | Python, LangGraph, React, SQL, Qwen, OIDC, Docker**

- Built a research workspace with multi-turn agents, role-owned working papers, versioned human corrections and MD/PDF/Word exports; validated source-value, withdrawn-scope and report-version recovery across 19 real user turns, including targeted recovery and post-restart handoff.
- Implemented BM25/Qwen dense retrieval and reranking with completed-request caching; improved Hit@5 from 50.0% to 95.8% across 24 positive queries in a 28-query, 1,105-chunk open-label evaluation; achieved 0.849 validation anchor Recall@5.
- Unified research MCP and conversational SQL access to 2,274 financial observations across five companies and derived metrics; verified value, period and unit parity across ten issuer/year query batches.
- Integrated OIDC/PKCE, server-side resource ownership and durable submission receipts; qualified 39 real two-user isolation checks plus eight concurrent reads, and verified duplicate submission recovery across service restart.
- Integrated frontend approval, LangGraph resumption, authenticated MCP and isolated Docker execution; passed four real browser permission scenarios with no container activity before approval, zero execution after rejection and disposable-container cleanup.

## 面试时如何解释

| 表述 | 可以证明什么 | 不能扩大成什么 |
| --- | --- | --- |
| 95.8% Hit@5 | 24 个正例中 23 个在前五候选找到标注锚点；BM25 为 12 个 | 金融回答正确率 95.8%、行业基准领先或统计显著 |
| 19 个真实用户回合 | 原 12 个意图含 5 次局部恢复，再加 2 次交接；总计 81 请求/1,231,464 tokens/未知0 | 19 个独立案例全部首遍通过、无限长上下文 |
| 人工修订报告 | HPE v2/人工2次，角色和底稿全文差异、三格式导出、后续回读 | 模型零错误或全部审查 Agent 自动通过 |
| 5 公司/2,274 行 | 统一后的真实只读财务快照及 10 批入口一致性 | 全市场数据库、所有指标都有正确语义 |
| 双用户隔离 | 实际 Keycloak PKCE 和产品资源 owner 校验 | 已通过生产多租户安全认证、大规模并发压测 |
| 本地 Docker 产品接入 | 4 个真实前端场景，批准前零容器活动，拒绝不执行，执行后清理 | 生产托管、Hermes 已接入、任意文件操作安全保证 |

最值得解释的工程取舍是：采用成熟运行框架负责执行与持久化；把原始来源、数值凭证、工作底稿和用户意见分开；把修复放在最早出现错误的环节；模型不能可靠自行修正时，由用户介入并保留完整修改史。

## 证据定位

完整样本口径与故障处理见技术报告。仓库内详细执行记录为 `docs/worklog/fin_0_1_3_s3/208_product_acceptance_and_external_evidence.md`；不对外分享原始私有响应。

| 成果 | 受控本地证据目录或文件（相对于本轮证据根目录） |
| --- | --- |
| 检索指标 | `retrieval-development-a3-chinese/results.json`、`retrieval-validation-a2-chinese/results.json` |
| 长对话与成本 | `measured-dialogues.json`、`long-dialogue-a1` 至 `long-dialogue-a5`、`handoff-a1` |
| HPE 修订与导出 | `hpe-final-ui-a4`、`human-followup-live-a2` |
| MSFT人工交付 | `custom-final-manual-ui-a2`、`custom-final-export-a1`、`measured-custom-research.json` |
| 数据一致性 | `financial-route-parity-a3/result.json`、`unified-financial-mart-a1` |
| 实际身份 | `identity-resource-a1`、`identity-browser-a1` |
| 重启回执 | `submission-restart-a1/prepare.json`、`submission-restart-a1/replay.json` |
| 本地回归 | `final-ui-a2.xml`、`final-integrated-a2.xml`（104通过/5私有材料跳过），集合不相加 |

公开简历无需附私人绝对路径或访问凭据。面试可提供技术报告、可复现公开测试及经审阅的产品截图。
