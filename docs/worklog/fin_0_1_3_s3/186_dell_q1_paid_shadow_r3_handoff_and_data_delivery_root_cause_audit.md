# Dell Q1 R3：真实工具循环已运行，底稿未交付；数据交付根因审计

日期：2026-09-05。FIN 0.1.3 / S3 / Wave 2 single-Specialist qualification。Q1 是研究分支 `Q1_ISSUER_TRUTH`，不是财务第一季度。

## 结果先行

- Owner 的“可以”只授权新的 R3 单次 paid shadow。既有 runner 恰好启动一次；没有 retry、resume、fallback、其他模型节点或实时外源调用。
- 工程增量：DeepSeek 的对象函数参数修复获真实验证；同一个 Specialist 自主执行 6 轮模型决策，4 次 Evidence 动作、1 次 Finance 动作，最后主动请求人工处理。Agent Server / PostgreSQL / Redis 和 LangSmith 均实际参与。
- 产品结果：`bounded_handoff`，不是研究 PASS。`final_submission=null`，没有工作底稿、完整报告或 multi-agent 验收。服务端 run=`success` 只表示执行正常终止，不能替代研究完成。
- 根因审计发现资料交付和任务合同不匹配：全库 top-k 后过滤造成已存在的指引漏召回；订单/积压材料被排除在 Q1 分支资格之外；模型将余额指标与季度流量混查，工具未返回可操作的期间类型纠正；当前季 Reviewed 路径不能覆盖旧年度 F1 和当前 F2 的组合要求。
- 本轮只运行和只读诊断，未改变产品代码、Owner 数据门、语料、S2 或完成校验。R3 已消耗，不可重用；没有 R4 authority/execution。纠正已有数据交付合同后才考虑下一次真实运行，不扩大 K0–K6。

## 1. 执行身份和证据

- implementation commit：`0c798101d7a14ff2b228fbc5c52e740ff20e60ae`。
- authority / clean pushed execution HEAD：`1b93d9c3f93135631f06df94cb4f759b4c8ba1fd`。
- authority：`configs/research/evals/fin_ia_0_1_3_s3_dell_q1_specialist_paid_shadow_r3_authority_v1_0.json`。
- execution：`20260905-dell-q1-specialist-paid-shadow-r3`。
- Compose project：`finsight-dell-q1-paid-f0dbe53eea9e`；loopback port `18170`；fresh volume `finsight-dell-q1-paid-f0dbe53eea9e_langgraph-data`。
- image：`sha256:07e6526741b2ad23f41597ba7e1a20e2d8428a063de08c28758bdfeff4c0d8a0`。
- server thread：`2e85e575-f3c8-5c07-9131-e568f42ec546`。
- server run / LangSmith root：`01a07072-36cf-7520-ad56-593f0b226ebe`；project `fin-insight-dell-reference-vertical`。
- artifact root：`Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/q1_specialist_paid_shadow/attempts/20260905-dell-q1-specialist-paid-shadow-r3/`。
- `terminal-receipt.json` file SHA：`358dfca48f65213697ce6975ef384c5bf5577acac0264b098d45703980771653`；receipt digest：`40e90241208c0185947d2f4f48a5736c7bf3d0de0b337ab7a4d685cd90dd12d5`。
- `model-call-events.jsonl` SHA：`d9246ec56e58948bc164d50a9181ef139d07c328c6b67c9527e02da2ed66cbcc`。
- `specialist-final-state.private.json` SHA：`16662dd59373f372cb62962ad0141f03133bcc633886b2130fae8c04b25c690e`。原始私有状态不复制入 Git。

R1、R2 原始失败不改写。R3 容器/卷保留，没有清理或重新构建；本轮构建经 Owner 的 `127.0.0.1:6696` 系统代理正常完成，未改代理。

## 2. 真实行为、时延和成本

| 轮次 | 模型选择 | 实际结果 |
| --- | --- | --- |
| 1 | 查 FY2027 Q2 发行人 Reviewed Evidence | 1 段事件范围说明；F1 metadata residual |
| 2 | 改成更具体的财务表和指引查询 | 2 段事件/公司摘要；F1、指引期间 residual |
| 3 | 再查指引和营运资本 | 仍是同两段 |
| 4 | 查询 10 个财务指标 | 6 个流量指标共 12 条当前/比较期 NumericFacts；4 个余额指标返回 typed gap |
| 5 | 再查指引和余额资料 | 仍是同两段 |
| 6 | 请求人工处理 | `required_route_unsatisfied_and_structured_gaps`；未提交底稿 |

实际底层 MCP 调用去重后 14 次：method=5、Reviewed search=4、ID read=4、financial query=1。模型决策不是 scripted，但也不是完整 multi-agent：只有一个 Specialist，Lead/Counter/Verifier 尚未运行。

- DeepSeek V4 Pro，thinking disabled，6 个 LLM spans 均 ended / 无 error；输入 73,312 tokens，输出 2,577，合计 **75,889**。
- 模型调用累计 **43.113 s**；Agent Server graph 执行 **50.019 s**；容器侧单次 runner（含准备/验证）**68.156 s**；Compose build/up **251.781 s**。这些不是全产品端到端延迟。
- LangSmith 六个 LLM spans 合计估算 **USD 0.027727654**，不是 DeepSeek 账单核销结果；实际账单未核对。
- 语义输入字符逐轮为 12,643 / 16,242 / 22,672 / 29,003 / 45,560 / 51,943。重复查询和反复携带观察确实有开销，但这次没有触及每轮 160,000 字符、10,000 输出 tokens、240 s 或 8 轮上限；不是预算截断失败。
- 模型展示了根据反馈换查询、转 SQL 和主动停止的能力；第 3/5 轮高度重复、余额查询用错 granularity，仍是实际行为缺陷，不能包装成完美 agentic。

## 3. 只读反例和最早责任层

### A. 检索先全库截断，后按范围过滤

`CurrentReviewedEvidenceReader.search` 对 56 条已批准 Reviewed items 全库 BM25 排序并先取 limit；`DellMCPToolLaneAdapter._execute_compiled_reviewed_target` 随后才用已计算出的 eligible 集合过滤。这不是成熟 BM25 库失效，而是我们调用顺序导致相关项在过滤前被截掉。

以原始 4 次模型 query 在相同 frozen case 上离线复算、未调用模型：

| query 轮次 | limit | 全年指引全库名次 | ISG 经营信息全库名次 |
| --- | --- | --- | --- |
| 1 | 8 | 29 | 21 |
| 2 | 12 | 16 | 13 |
| 3 | 12 | 18 | 26 |
| 5 | 12 | 25 | 29 |

这些内容存在且部分符合 Q1 元数据条件，却没有进入送给模型的结果。范围内只有少量资料时，正确修复候选是**先确定合规候选集合、再 BM25/top-k**，继续复用 `rank_bm25`；不是提高模型次数、换 embedding、上图检索或抬高 recall 总门槛。

### B. 分支资格与研究任务矛盾

Q1 objective 明确要求 orders/backlog，但已保存的 `DELL_Q2FY27_AI_SERVER_ORDER_REVENUE_BACKLOG` 元数据只允许 Q2/Q3 作为 minimum route，Q1 不在其中。文件内容和来源都在冻结 overlay 中；不能把它没有进入 Q1 结果称为公开信息缺口。

Q1 合法的 F1 Reviewed items 实际有 2 条，期间都是 FY2026；不是整个 F1 不存在。当前模型 4 次查询均要求 FY2027_Q2（后面还加了 Q3/full-year guidance 标签），故 F1 均产生 residual。完成适配器又只接受单份无 residual、覆盖 F1/F2 的 Reviewed receipt；Finance 结果不能贡献这条 Reviewed completion。模型可以改用历史期间查资料，但当前年度/本季混合研究需要什么输入、哪条路径满足什么要求，并未清楚交代。

指引原文已保存，但其 `period_refs` 只有发布事件 FY2027_Q2，而模型请求的是 FY2027_Q3_guidance / FY2027_full_year_guidance。发布期间与预测覆盖期间是两种含义；不能只凭字符串不匹配就暗示内容没有披露。

更改这些映射/完成判定会改变已批准的数据合同，因此本轮没有偷偷放宽 gate。修正应对齐任务与真实来源，不是删掉证据、公司、期间或引用校验来拿 PASS。

### C. 余额查成季度流量，反馈不可操作

模型在同一 Finance request 用 `granularity=quarter_discrete` 查询 revenue 等流量以及 accounts_receivable / inventory / accounts_payable / cash_and_equivalents 四个余额。

只读连接冻结 S2 mart（SQLite URI `mode=ro`、`PRAGMA query_only=ON`）确认，四个余额分别有 **24 / 30 / 24 / 30** 条 DELL `instant` observations，最新都是 2026-05-01。没有重建或写入 SQL。

最早错误是模型的参数类型选择；宿主工具也有责任：能力披露仅笼统说 `direct_observation`，未披露 metric 的期间角色，且错误反馈只有 `typed_fact_not_found_for_as_of_and_period`，没有指导“这四项要用 instant 单独查”。现有 `instant` 能力已经存在，优先补齐披露和类型错误反馈，不造自动修数引擎、不自动把季度金额转成余额。

### D. 工具可见面比产品数据面窄

本次 L0 只暴露 Reviewed query 和 Finance query。optional route inventory 依赖 disclosure，但 disclosure 当前不可用；因此未授权的 local RAG / 外源补查不能作为本次模型本应做到的能力。本地完整文档已经准备，不等于这个 Specialist 实际有阅读入口。

这些问题合并归入 `RC-S3-113-dell-q1-specialist-data-delivery-task-contract-mismatch`，不另外建立一套通用治理框架。R2 的 `RC-S3-112` 对象根类型问题获 R3 六轮成功调用的有界关闭证据。

## 4. 下一步和停止条件

建议 Owner 确认一个窄范围的数据交付纠正，保持同一产品、同一 Specialist 和成熟运行栈：

1. 已批准 Reviewed 集合内先过滤再检索；用本次真实 query 离线复验指引、ISG 是否进入候选，不新增语料或放行五个歧义项。
2. 使 orders/backlog 的可读范围与 Q1 任务匹配，区分事件期间/指引期间；把 F1 的 SQL/历史报表与 F2 的当季叙述按各自用途验收，避免强迫一条 Reviewed 查询包办全部工作。此项需明确的数据合同纠正，不静默改 Owner decision。
3. 使用既有 S2 metric 定义披露 instant/duration；混查时给模型可执行的纠错反馈，由模型重查。不要“自动补值”。
4. 同时明确这次是否仅验证 Reviewed+SQL，还是允许读取已经冻结的本地文档；若增开，只接现有只读入口，不引入通用 disclosure 协议、不自动 admission 外源、不改变 S2。

先做上述具体反例的离线验证，再申请/绑定一次新的同类 paid execution。R3 本身不重跑。没有必要为此全仓回归、换 LangGraph/LangSmith、重建 RAG、扩写 K0–K6 或先实现全套 HITL。

通过标准仍然是模型能取得真实相关输入并交出有来源、有业务内容的底稿，允许明确的不确定性；不是把 `bounded_handoff` 改名 PASS，也不是要求所有子项齐全、文字套模板或数字 100% 覆盖。

本轮无新代码测试和独立 reviewer 结论；前一修复的 67 个离线测试不冒充本次数据问题已修复。剩余 RC-S3-107、完整多 Agent、上下文压缩、HITL、前端和部署产品验收仍未完成。
