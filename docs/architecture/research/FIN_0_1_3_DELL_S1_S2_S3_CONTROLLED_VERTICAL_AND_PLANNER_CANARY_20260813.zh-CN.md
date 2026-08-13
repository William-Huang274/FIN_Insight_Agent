# FIN 0.1.3 DELL S1／S2／S3 受控纵切与 Planner Canary 决策

日期：2026-08-13
状态：`zero-call vertical engineering pass / natural planner R1 terminal budget failure / S3 product open`

## 1. 这轮真正接通了什么

同一个 DELL 研究问题已经由当前 Runtime 形成一条受控纵切：

```text
研究问题
  → Research Objective（本地绑定公司、截至日、范围和预算）
  → planner atoms（当前零调用证明由受控输入提供）
  → EvidenceRequest
  ├─ S1：BM25 + Qwen Embedding 联合候选
  └─ S2：SQL/PIT 公司财务事实 mart
       → NumericFact / typed gap / typed conflict
```

模型未来只能选择 `facet_id / target_entity / canonical metric_id / product_intent`。公司身份、研究截至日、来源类型、期间、预算、request/cell ID、lineage 和数值写入权均由 Harness 绑定。文本候选仍是 candidate，不是 Evidence；表格行仍没有 NumericFact 权限。

当前 Workbench 后端新增受控产品入口：

`POST /api/v1/research-cases/{case_key}/controlled-research-plans`

它不是完整 Agent 产品入口。它用于证明 Objective、S1 候选和 S2 数值事实能在一条当前链路中共同执行，同时保留每个子请求的结果和边界。

## 2. 数据库线没有被检索模型替代

DELL 零生成调用实跑包含 5 个 EvidenceRequest、7 个 typed fact request，结果为：

- 7/7 resolved；
- 0 typed gap；
- 0 typed conflict；
- 21 个 source-bound NumericFact；
- 0 网络、0 生成模型调用。

例如 FY2027 Q1：收入 `43,842,000,000 USD`、营业利润 `3,656,000,000 USD`、毛利 `7,782,000,000 USD`、经营现金流 `4,081,000,000 USD`、资本开支 `963,000,000 USD`。自由现金流 `3,118,000,000 USD` 与毛利率由同期间、同披露批次事实确定性计算，并保存公式输入 lineage。

这说明数据库是纵切中的独立 S2 权威线，不是 BM25/Qwen 的 fallback，也不是 Writer 最后拼数字的素材库。后续任何 embedding、reranker 或 DeepSeek 升级都不能取消该边界。

## 3. S1 实际业务表现

联合候选每个 facet 暂取 16 条，用于候选池而非直接交付模型：

- `orders_and_backlog`：找到了 AI-optimized server demand、elevated backlog 与订单可取消边界；
- `reported_results`：当前 FY2027 Q1 8-K 已能正确显示 reporting period=`2026-05-01`、FY2027，但年度 10-K 表格仍可能排在其前面；
- `margin_and_incremental_profit`：找到了 ISG 毛利率下降、产品组合与运营杠杆解释；
- `cash_generation`：同时找到了自由现金流定义、当期 8-K cash-flow 表以及 S2 精确事实；
- `issuer_counterevidence`：BM25 直接找到大客户订单波动、竞争/定价压力、营运资金与库存风险，Qwen 提供完整需求语境。

结论不是“Qwen 赢了”或“BM25 足够”。两者有互补收益，但 80 条跨 facet 候选仍含年度资料压当前资料、表格行压机制解释和相似语义噪声；必须由后续有界选择和 Evidence Gate 收敛，不能整包直接喂给模型。

## 4. 本轮修复的最早根因

旧 compiled object store 把 SEC filing/current-report 日期与 issuer reporting period 混用。DELL FY2027 Q1 8-K 因此可能携带 FY2026 与 `2026-05-28`，而不是业务期间 FY2027 与 `2026-05-01`。

当前建立共享 temporal projection，并让 candidate retriever、EvidenceObjectView、父级 context 和 compiled object 共同消费。v2 对象库仍为 20,340 个对象，其中 713 个对象的时间元数据得到校正，只有 16 个父级模型文本需要重新编码；其余 20,324 个 Qwen 向量安全复用，避免无意义全库重建。旧 v1 及其模型 shadow 保留为历史证据，不冒充 v2 产品评测。

## 5. 为什么值得做一次最小自然 Planner Canary

零调用纵切只证明“给定正确 atoms 后链路可运行”，没有证明 DeepSeek 能从真实问题选择合格 atoms。一次自然 planner canary 能回答一个当前无法由本地测试回答的问题：模型是否能在不拥有身份、日期、来源和数字写入权的前提下，覆盖需求、业绩、利润、现金和反方五个研究维度，并使用当前 canonical metric ID。

因此授权范围严格限定为：

- DeepSeek Pro；
- 1 次 Chat Completions；
- 1 次 transport attempt，0 retry、0 fallback；
- 输入只有当前 DELL Objective 与从活动合同编译的允许 facet/metric；
- 输出只有 planner atoms；
- 不访问检索、数据库或外网来源；
- 不选 Evidence、不做研究判断、不生成报告；
- 完整保存模型可见请求和最终 assistant 输出，凭据/Authorization 和 provider private reasoning 不保存；
- 输出必须先 exact JSON parse，再由同一个 `compile_research_plan` 语义校验；失败即终止，不做字段补丁。

Provider 特殊参数只存在独立 profile；核心 planner 与金融合同保持 provider-neutral。当前活动树原 LLM gateway 已在严格重定基时归档，因此本轮只恢复一个通用 capture-first、exact-once Chat Completions transport，不把历史 attempt runner 搬回主线。

## 6. 自然 Planner R1 结果

唯一一次授权调用已经执行并按规则终止。Provider 正常返回 exact JSON，DELL 身份、5/5 required slot、10/10 facet、所有 canonical metric ID 和 query-family compatibility 均正确；但模型返回 10 个 atoms，超过本次 objective 的 `maximum_atoms=8`，因此在任何 S1/S2 successor 之前以 `research_planner_atom_budget_invalid` 终止。没有 retry、fallback、手工裁剪或第二次调用。

该结果不应简单归为“DeepSeek 不会规划”：它给出的需求、转化、业绩、指引、定价、利润、现金、营运资本和两类反方维度具有实质研究价值。直接失败是没有遵守执行数量上限；系统问题则是当前合同没有分开模型的 research proposal ceiling 与本地实际 execution budget。下一项必须先做零调用结构处置，不能自动签发 R2。

## 7. 尚未通过

- 自然 planner R1 已执行但预算合同失败；
- 80 条候选尚未经过合格的 Evidence selection/Role/Gate；
- S3 尚未消费候选与 NumericFact 做研究判断；
- 没有 Workpaper、报告、L1、八维内容质量、paired 或人工验收；
- S1、S2、S3 产品门均未关闭。

R1 永久保持 failed。预算分层只能通过零调用 successor 消费其 immutable capture：模型可在 proposal ceiling 内提出比执行预算更多的 atoms，本地先保证 required-slot 覆盖，再按 provider-neutral 金融 facet 优先级选择实际 EvidenceRequest，并为每条未执行 atom 保存稳定舍弃理由。身份、日期、来源、外部调用和 NumericFact 权威继续是硬门。

该 successor 通过后不重跑 Planner。R1 的 10 条自然 atoms 将成为 S1-C 的真实产品输入，用于暴露已有对象上的结构约束丢失、当前期／官方来源／直接性排序和 Evidence Role 问题；S1-C 收敛后才由真实 residual gap 驱动 S1-D，最后回到 S3 消费合格 Evidence Pack 与 NumericFact。本次结果不自动授权完整报告或多轮 Agentic Research。
