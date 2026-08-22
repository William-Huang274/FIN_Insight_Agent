# FIN 0.1.3 DELL 报告边界密度与信源充分性审计

日期：2026-08-22
性质：只读归因＋provider-neutral 零调用结构修复
不代表：重写历史报告、S1/S3 通过、跨案例泛化、qualified-human 验收或发布

## 一、结论先行

最新 DELL 报告的事实边界比旧稿可靠，但“边界说明太多”不是单一写作风格问题，也不能简单归咎于 DeepSeek。六条 remaining gap、八条 what-would-change、执行摘要和 confidence 中混入了四类不同状态：

1. **内部事实已经存在，但下游状态过期**：应收、库存、现金和融资应收已进入 source-bound NumericFact／presentation authority，旧 Cash workpaper 却仍称其未覆盖。
2. **研究方法尚未完成**：失效阈值应由研究者或用户冻结，不是公司应披露的事实，也不应作为 source gap。
3. **外部补源尚未真正跑完**：需求转化、产品经济性、AI 现金归属和供应关系仍缺材料，但 source-route truth 明确显示官方／外部路线未穷尽；只能称为“当前研究未闭合”，不能称为公开信息不存在。
4. **Writer 合同重复呈现同一边界**：同一 gap 被要求进入执行摘要、正文、remaining gaps、WWC 和 confidence，导致一份谨慎报告读起来像连续拒答。

当前 8 组边界陈述中：

- 4 组属于运行、状态同步、研究方法或成稿表面，应在进入客户报告前解决；
- 4 组属于本轮仍需补源的材料不确定性，可以在报告中各保留一句简洁说明；
- 0 组已经取得“公开信息真实不存在”的 GapEligibility 权威。

因此正确修复不是删除谨慎措辞，而是把错误边界退回最早责任层，再让真正的材料边界只出现一次。

机器可读逐项归因见：

- `configs/research/evals/fin_ia_0_1_3_dell_report_boundary_attribution_audit_v1_0.json`

## 二、当前稿具体哪里出了问题

| 报告表面 | 实际状态 | 最早责任层 | 处置 |
| --- | --- | --- | --- |
| 订单→backlog→收入、取消、账龄和消化 | 官方披露不足，但外部／后续官方路线未穷尽 | S1 外源补充与 GapEligibility | 保留一条当前不确定性，定向补源 |
| 应收、库存、现金、融资应收“source-visible but non-covered” | 数字已经有 NumericFact 和最终展示权威，但旧 evaluator finding 没有被新权威废止 | S2→S3 evaluator/Writer 视图同步 | 确定性废止该 finding；事实语义未变，不重跑 Cash Agent |
| AI 产品级现金和营运资金归属 | 公司级事实完备，AI 归属仍无直接披露；公开代理尚未穷尽 | S1 外部 context＋S3 bounded attribution | 保留一条归属限制，允许受控 proxy／estimate |
| AI 服务器 ASP、台数、PVM、单独利润 | 官方精确拆分缺失，但免费产品／行业代理未系统接入 | S1 行业／产品补源＋S2 估算＋S3 解释 | 不编造 exact fact；允许有假设和敏感性的估算 |
| Dell 特定供应分配、产能、良率、HBM | 当前候选多为泛行业 read-through，缺少 Dell 关系边 | S1 关系查询、对手方官方源、重排与 Evidence Role | 先补关系证据，行业材料只作 bounded context |
| “没有冻结 thesis 失效阈值” | 研究者参数未设置，不是 source gap | S3 Research Method | 由研究者／用户确认阈值，进入监控规则 |
| 边界在五个报告表面重复 | Writer schema 和 prompt 强制重复保存 | S3 Writer 合同＋S4 呈现 | 统一 Boundary Register，执行摘要最多一条综合不确定性 |
| Specialist 因 current cell 不可见而停止 | 本轮是 fixed-Pack preview，不是真正动态补证循环 | S3 Agent 工作模式 | material gap 必须生成 FeedbackReceipt／EvidenceRequest 或合法 StopDecision |

## 三、内部信源审计

### 3.1 本地不是“没有资料”

DELL 当前产品就绪结果包含 768 个候选和 7 条已接受 reviewed Evidence。四个请求被 `blocked_by_evidence_admission`，三个为 `partial_with_material_gaps`，一个只在当前范围就绪。所有正式 gap receipt 都显示：

- `eligible_as_true_public_information_gap=false`；
- `official_or_external_supplement_route_exhausted=false`；
- `source_non_disclosure_adjudicated=false`。

候选审阅包还能看到：

- Dell 10-Q／10-K 已有 AI 需求、营运资金、取消／延迟和库存风险材料；
- 当期财务表已经包含应收、库存、现金、融资应收和应付；
- 上游候选中也混有微软通用部件风险、美光单一光刻设备供应商风险等与 Dell AI 供给命题不直接对应的材料。

所以内部主要故障不是“库里空”，而是对象—命题绑定、Evidence admission、关系方向和受影响状态刷新不完整。

### 3.2 数字状态发生了真实漂移

`fin_ia_0_1_3_s2_dell_multi_agent_source_bound_numeric_review_v1_0.json` 已为应收、库存、现金、短期和长期融资应收给出 `bind_existing_numeric_fact`／source-bound 决策；最终 report authority catalog 也已具备对应 `NUM::*` 展示权威。进一步回看原始 Cash workpaper 后，底稿其实已经列出并分析这些数值，真正过期的是早于 source-bound review 生成的 `NUM_REF_UNRESOLVED_BALANCES` evaluator finding。Writer 同时看到了新目录和旧 finding，最后沿用了旧状态：

```text
S2 authority changed
  -> matching evaluator finding was not superseded
  -> Writer saw conflicting old/new control state
  -> Writer preserved a stale boundary
```

后续冻结：如果新权威只是给 Agent 已见、已分析的同一 claim 补齐引用／数值绑定，则确定性刷新 claim support、废止精确绑定的旧 evaluator finding，不重跑 Agent；如果新 Evidence、关系、期间或数值真的改变语义，才使受影响 workpaper context digest 失效并重裁决。不能让最终 Writer 独自判断哪个上游边界已经过期。

## 四、外部信源不是“官方或垃圾”二选一

官方发行人、监管和结构化数据仍是精确公司事实的主权威，但高质量研报还需要行业规模、竞争格局、客户部署、产品配置、渠道库存、供应链关系、机制与反方材料。产品应控制“某类来源能证明什么”，而不是一刀切只允许官方公司披露。

本轮新增 source-strength／claim-use 合同：

| 来源类别 | 可做什么 | 不可做什么 | 内化方式 |
| --- | --- | --- | --- |
| 发行人／监管／政府 primary | 公司精确事实、数值、管理层机制、风险 | 不能把管理层意图当实现结果 | versioned source object |
| 明名对手方／标准组织 primary | 证明该对手方说了什么、产品配置、关系背景 | 没有关系边时不能证明 Dell 获得多少分配 | versioned source object |
| 官方市场／行业 primary | 市场规模、行业出货、标准和宏观事实 | 不能直接创造 Dell 精确财务数字 | versioned source object |
| 可信媒体／行业协会／公开 analyst context | 机制、竞争、反方、交叉验证 | 不能单源晋升目标公司 exact fact；材料推断至少需独立交叉验证 | versioned context object |
| Search／RSS／GDELT／Common Crawl | 找原始 URL、发现事件和新实体 | snippet、排名和转载不能成为 Evidence | locator index，随后抓原文 |
| licensed／user-entitled | 按合同提供市场、共识、供应链等结构化事实或 context | 未绑定许可、PIT、保留与再分发权限不得使用 | license-bound object |

对应机器合同为：

- `configs/retrieval/fin_ia_0_1_3_s1_source_strength_and_claim_use_policy_v1_0.json`
- `src/retrieval/source_use_policy.py`

该合同不把可信媒体自动变成真相；它只明确允许其在机制、竞争和反方中发挥作用，同时继续禁止它生成 Dell exact financial fact。

## 五、免费公开源仍有明显提升空间

对 DELL 做反向免费源探测后，已经能确认以下公开材料类别具有增量价值：

- Dell 官方季度业绩、prepared remarks、演示和产品／客户页面；
- Dell 或供应商明确点名合作配置、内存／存储／加速器组合的官方文章；
- IDC、Omdia 等公开市场摘要和行业 press release；
- 客户官方部署案例、采购／招标、监管和标准组织材料；
- 后续季度披露，用于跨期验证 backlog、收入、利润和现金方向；
- 可信媒体和行业协会用于提出机制、竞争、渠道与反方，再回到 primary source 验证。

当前权威基线的生产 route 实际只有本地 snapshot、SEC、exact registered official document 和人工上传。issuer IR feed／sitemap、point-in-time market、industry primary 均是 `not_configured`，broad web 只是 diagnostic。旧 PRD 已设计完整 SourceHunter，但新干净基线没有把这些成熟能力真正接回 Runtime。这是明确的产品能力缺口，不是免费源天然无用。

免费源优化必须先证明：

1. 定向 Evidence Slot 的 target-in-pool 和 useful@10 改善；
2. 原始页面／文档先 capture，再解析和 Evidence Gate；
3. 日期、主体、speaker、期间、关系方向和 claim-use 正确；
4. 相同来源不会因多片段虚增独立证据数；
5. 新材料确实改变或收窄研报判断，而不是只增加网页数量。

只有经过这些门后仍存在稳定 residual gap，才有依据说明付费行业／供应链／市场数据能带来可量化生产增益。

## 六、本轮已经做的结构修复

1. Source route 现在区分：
   - `candidate_coverage_state`：本地候选是否覆盖当前材料要求；
   - `research_sufficiency_state`：现有 Evidence Pack 是否足以支持研究判断。

   即使本地候选“完整”，只要研究仍有 material gap，也会调度外部补源；不再把“本地候选够数”误当成“研究资料充分”。

2. Writer audit 新增非阻断质量 finding：
   - 执行摘要变成 gap inventory；
   - confidence 重复 gap；
   - customer gap register 超过建议密度；
   - 同一 gap 跨多个报告表面重复。

   对当前完整 draft 回放得到 `0 hard / 17 quality`，其中 12 条直接属于 boundary density。Harness 不自动改写正文，但下一次 Writer 必须消费这些反馈。

3. 建立 report boundary disposition contract，强制区分：
   - operations-only；
   - resolve-before-report；
   - current-run uncertainty；
   - proved information boundary。

   本地失败、Evidence admission、过期 NumericFact、未执行来源和研究者阈值不能冒充真实信息边界。

## 七、下一步执行顺序

1. **先修内部过期状态**：让 S2 authority 精确废止已解决的 evaluator finding；只在语义变化时触发 Agent 重裁决，移除“数字未覆盖”的过期边界。
2. **修 gap ontology**：把研究者阈值从 S1 source gap 移到 S3 method parameter。
3. **恢复免费外源纵切**：从 DELL 四个 material uncertainty 开始，依次接 issuer IR、named counterparty、official industry 和 trusted context；search 只做 locator。
4. **重新编译 Evidence Pack**：每条新材料必须经过 source-use policy、parser lineage、Evidence Role、Evidence Gate 和 S2 fact/estimate boundary。
5. **运行真正动态受影响单元**：Demand、Value、Cash、Supply 分别收到新 EvidenceResponse，允许再次提问或合法停止；不是换一份固定 Pack 重新 one-shot。
6. **最后才重写报告**：执行摘要给结论和主要驱动，只保留一个综合不确定性；四组材料边界进入统一 register，各写一次；operations ledger 只在 Workbench 运行视图显示。
7. **用 MU、NVDA 和异质留出案例复证**：证明 source strength、补源调度、状态失效和边界去重不是 DELL 特判。

新的 DeepSeek live 只有在前四步零调用／真实 source capture 通过后才有信息价值；否则继续调用只会稳定地产出同一份稀疏材料下的谨慎报告。
