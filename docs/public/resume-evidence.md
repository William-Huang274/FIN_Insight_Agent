# FinSight 简历成果与证据

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
