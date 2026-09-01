# DELL 单案例完整纵切：数据与运行地基、首轮真实运行门

更新时间：2026-09-02
状态：`ENGINEERING_GATE_PASS / LIVE_START_PENDING_CLEAN_COMMIT`
产品范围：只做 `DELL_AI_INFRA_REFERENCE_VERTICAL`，不是恢复 R14，也不是扩展成通用研究平台。

## 1. 这次到底要证明什么

目标是用一个 DELL 案例演示接近产品最终形态的完整纵切：真实数据工具、动态任务 DAG、相互隔离的 Specialist、Evidence/Finance 并行取数、Counter 定向回派、Lead 综合、可暂停人工审核、可恢复渲染，并留下来源、token、调用、耗时和失败收据。

本轮不追求全市场、任意公司、100% 准确率或极限低 token。允许有清楚标注的不确定性；不允许候选资料伪装成 Evidence、工具失败伪装成公开信息缺口，或 current Q2 文字数字伪装成 S2 结构化事实。

## 2. 已冻结的数据面

| 数据层 | 当前内容 | Agent 权限 | 冻结身份 |
|---|---:|---|---|
| Local Knowledge | 18 份官方正文、597 个检索记录 | 只作为 `retrieval_candidate`；不可直接引用 | `records.jsonl` SHA-256 `47d518b9...bef9`；result SHA-256 `5d2014eb...9bf2` |
| Reviewed Evidence | base 55 条 + DELL FY27 Q2 case overlay 6 条 = 61 条 | 可引用、可进入 citation index | base projection digest `2d4e3d57...eccd`；overlay file SHA-256 `1479e49f...eb9`；composite digest `c91d5c58...7e7d` |
| S2 NumericFact | 11 家公司、4,586 observations、12 个直接指标和 3 个 executor 派生指标 | 只读 SQL 数值权威 | SQLite SHA-256 `9c962b1d...a656`；result SHA-256 `bc5830e9...0922` |
| Live public source | Exa hosted MCP discovery，DDGS 只作诊断 fallback；静态抓取后按需 Playwright | 新结果仍是 candidate，不能自动晋升 Evidence | 每次 MCP 调用独立 receipt；production crawler 仍为 `HOLD` |

当前季度边界：2026-09-01 提交的 Dell FY27 Q2 SEC Exhibit 99.1 已进入 6 条 Reviewed Evidence，所以 Agent 能引用发行人原文可见的 orders、revenue、backlog、分部和 guidance；但该 Exhibit 没有 inline XBRL，CompanyFacts 尚未出现对应 accession，因此 current Q2 仍不是 S2 NumericFact。比率、差额、PVM、转化率等 current-Q2 衍生计算继续保持 null，直到 10-Q/XBRL 或另一份合格结构化发行人数据进入 S2。

## 3. 研究问题和九个分支

正式问题固定为：

> 截至 2026 年 9 月 2 日，Dell 的 AI 基础设施业务增长到底有多大、多可持续、能否转化为收入利润和现金流；架构迭代、GPU 与内存供给、价格数量组合、客户需求及对华出口管制分别怎样影响兑现，最强反证和后续验证指标是什么？

Planner 必须覆盖九个分支：发行人事实、需求质量、units/ASP/PVM、架构量产、供应与价格、模型算力需求、出口管制与中国、竞争/价值池、反证与 what-would-change。共同研究方法已由 foundation JSON 一次性注入；它约束口径、时间点、公式和停止条件，但不注入题目答案。

## 4. 运行面：成熟底座和 FIN 自有边界

采用成熟底座：

- LangGraph：动态图、并行 fan-out/fan-in、interrupt、SQLite checkpoint 和 resume。
- 官方 MCP Python client/server：统一 Knowledge、Evidence、Finance、外源发现和抓取工具协议。
- Pydantic：结构化输入输出与 fail-closed contract。
- `langchain-deepseek`：DeepSeek structured output transport；provider 自动 retry 为 0。
- SQLite：本次本地资格运行的只读 S2 mart 和 checkpoint；PostgreSQL/pgvector 保留为部署目标，不为一个案例强行启动不稳定的本机 Docker。
- 现成 BM25 legacy reader：只作已冻结本地 candidate bridge；不再建设 cell 绑定壳、通用 GraphRAG 或自研向量数据库。

FIN 只保留薄的、确实属于产品的部分：

- 九分支金融研究方法和口径；
- Candidate / Reviewed Evidence / NumericFact 三层权威；
- DELL case foundation、MCP 薄适配和 citation index；
- current-Q2 文字证据与 S2 数值事实的权限隔离；
- 报告人工审核门和 Workbench 投影。

图的真实拓扑为：`bind → planner → Evidence/Finance 并行 → 9 个隔离 Specialist → Counter → 最多 1 个定向回派 → Lead → verify → HITL → resume → render`。这不是把固定 prompt 顺序包装成“multi-agent”：每个 Specialist 有独立输入、独立工具结果和独立 workpaper，Counter 只能选择一个分支回派，resume 不重跑已完成节点。

## 5. 有界运行合同

- 单公司 case；上下文公司只用于需求、供应、竞争和反证，不变成第二案例。
- 9 个 branch，最多 1 次定向回派。
- 最大图并发 3。
- 模型调用上限 13 次：Planner 1、初始 Specialist 9、Counter 1、可选返工 Specialist 1、Lead 1。
- provider transport 每个节点最多 1 次，自动 retry 0。
- 外源高重要性分支最多 2 轮搜索；每次最多 6 个结果；每分支最多抓 4 页；全 run 最多 24 个 live page。
- Planner 输入调用前保险线 120,000 字符。真实九分支 deterministic fixture 为 81,082 字符；不为压 token 删除必要研究方法。
- 第一次真实运行只允许 `start → HITL`；不会自动 approve、不会自动发布。

## 6. 首次真实运行的唯一身份

- attempt ID：`20260902-dell-reference-vertical-q1-a01`
- run ID：`dell-reference-vertical-q1-run-a01`
- data snapshot ID：`20260902-dell-a02-a04-reviewed-evidence-composition`
- research as-of：`2026-09-02T23:59:59+08:00`
- foundation SHA-256：`bf214a08...6d47`
- DeepSeek config SHA-256：`03115289...6fc8`
- 模型：`deepseek-v4-pro`，thinking disabled，structured output，0 retry。
- 唯一可执行 run authority：`scripts/research/run_dell_reference_vertical_q1_a01.ps1`。它固定上述身份、完整输入路径和 SHA、D 盘 `.venv` 及 API key 环境变量名；`-PreflightOnly` 与正式 start 使用同一参数集合，禁止临场改写参数。

正式 start 前必须同时满足：

1. 分支精确为 `codex/fin013-dell-s1-s2-product-bridge`；
2. 当前实现、测试、依赖和本文件进入一个 clean Git commit 并推送；
3. manifest 绑定 commit、tree、critical-source bundle、`pyproject.toml`、`uv.lock` 和 graph contract version；
4. focused offline gate 全绿；
5. 同一 attempt/run 目录和 checkpoint 均不存在；
6. zero-call preflight 在同一 clean commit 通过。

同一 attempt 永不覆盖。第一次真实运行不因模型格式、工具失败或内容不理想而偷偷重试；只有在保存失败证据、找到最早责任层并另行批准后，才允许新 attempt。

## 7. HITL 的人工验收

到 HITL 后先停，不生成“已通过”的对外结论。人工检查并另存 Z 盘审计 artifact：

- 是否真的生成 9 份 workpaper；是否只发生 0 或 1 次定向回派；
- Lead 是否先回答商业结论、数字、机制、时间和反证，而不是堆边界说明；
- 每个引用 ID 是否能在 citation index 定位到 Evidence/Fact URL、period、unit 和 digest；
- candidate 是否被洗成事实；current Q2 数字是否越过 S2 权限；
- generic hyperscaler capex 是否被误写成 Dell 份额；模型能力是否被误写成 Dell 采购；
- announcement、sampling、production、shipment、deployment、revenue 是否被混写；
- token、调用数、wall-clock、MCP 失败和 model journal 是否完整；
- 结论中的 material claim 是否由实际匹配的来源支撑。

只有人工 claim/source/numeric audit 通过，Owner 才另行决定是否在同一 clean commit 上 approve/resume。否则保持 immutable failure；不把“图跑完”写成产品通过。

## 8. 当前工程验证

- 关键图、真实数据组合、MCP 失败诊断、DeepSeek adapter、CLI/HITL 恢复、Q2 overlay、S2 data ports 和真实 MCP 数据：`67 passed`。
- 全部新增 DELL data/runtime 与 Workbench 相邻测试：`175 passed`；repository secret scan：`8,386 files / 0 findings`。
- 覆盖：调用前输入上限、模型 started/outcome journal、并发上限、aggregate external budget、citation index、S2 SHA TOCTOU、MCP semantic/transport failure、外源单点失败保留收据后有界降级、真正 fatal tool failure 在 Counter/Lead 前停止、terminal checkpoint 幂等恢复、approved→render 恢复、artifact drift、Git commit/tree/source SHA 与实际 Python module origin 双重绑定，以及唯一无密钥 run authority。
- 模型调用：0；外源网络调用：0（上述工程门）。

因此当前结论是：数据面和运行面已达到“clean commit 后进行一次受控真实试飞”的工程资格，不等于研究内容、公开演示、生产部署或产品验收已经通过。
