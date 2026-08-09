# 780 — FIN 0.1.3 DELL 金融 source/object 纵切与本地 Candidate Pack

日期：2026-08-09

归属：FIN 0.1.3 / S1

状态：`DELL_vertical_engineering_pass / product_pack_incomplete / MU_NVDA_transfer_next`

## 1. 为什么做这一项

三案例尸检表明，旧链路主要衡量“某个目标片段是否进 top-k”，没有回答一份金融研究需要的多个证据面是否共同闭合。用户批准先冻结通用金融研究合同，再用 DELL 做完整纵切；只有纵切和迁移证明通过后才决定 sparse／dense、外源补源和 DeepSeek 综合。

本项使用现有本地资料真实执行，但明确禁止网络、Provider、模型、embedding、rerank 和 Evidence promotion。

## 2. 实际执行

- 编译 `23` 条 typed query lane，覆盖经营、需求、price-volume-mix、产能投入、现金转换、关系归因、监管、反证和 optional valuation。
- 运行现有 parent BM25、object BM25 和 current official supplemental BM25，合计返回 `265` 个 candidate row。
- qrels／reviewed binding 只在所有候选生成后加载；查询中不含 target ID 或标准答案 URL。
- 对 `23` 个预先审阅目标核对 target、parent source、主体、source reporting period、research as-of、关系方向、正文摘录、facet、citation 与 lineage。
- `15` 个 parent source 被装配成 source-object bundle；完整正文留在原始 source store，公开结果只保留 preview、ref 和 digest。

## 3. R1、R2、R3

R1 immutable failure：`22/23` qualified。唯一失败是 Dell Q1 官方发布稿的审阅摘录写成 `Dell Technologies announces...`，而原文在公司名与动词间含 `(NYSE: DELL)`；候选实际 rank 1，属于预期摘录过严，不是检索失败。

R2 使用 digest-bound amendment，不改查询、候选池、预算或通用内核：

- 将关系自述摘录收窄为原文连续短语；
- 把确实存在的 AI server revenue、AI orders、component dependency、capex-to-FCF、customer read-through、export control 映射到 Industry Pack facet；
- 把没有证据的 facet 补成 typed residual gaps，而不是扩大已有片段含义。

R3 在 Runtime 再加入 relationship fail-closed 与 evaluator rejection gate 后重新物化。最终：

- status=`engineering_pass_product_pack_incomplete`；
- `23/23` reviewed candidates qualified；
- candidate contract rejection=`0`；
- Evidence promotion=`0`；
- result digest=`31c3f7c98eb40850087837ed7307af0552772b9ae5acf1f2ddbb520d3f574df7`。

## 4. DELL 业务上已经能看见什么

现有官方资料已经能够形成以下候选事实链：

- Q1 FY2027 revenue `43.8B USD`、cash flow from operations `4.1B USD`、AI orders `24.4B USD`、AI-optimized server revenue `16.1B USD`、FY2027 AI server revenue expectation `60B USD`、shareholder return `2.1B USD`；
- 结果表给出 revenue `43.842B`、operating income `3.656B`、AI-optimized server revenue `16.132B`、ISG revenue `29.009B`、ISG operating income `3.055B` 和 margin `10.5%`；
- Dell 自述 customer readiness 与 component transitions 会造成需求和出货间的非线性；大客户／cloud-provider 集中会带来定价压力、更大营运资金承诺、取消和库存过时风险；
- AI server mix 上升压低 gross-margin percentage，但没有披露 AI server 自身利润率；
- Microsoft 能证明自身继续投资 AI infrastructure 和使用量增长，但不能自动归因为 Dell 订单；
- NVIDIA 能证明第三方制造／组装／封装／测试依赖，以及出口管制会波及服务器使用的 networking products，但没有 Dell 分配量；
- Micron 当前候选涉及 DDR5、SOCAMM2 和 SSD ramp，没有 HBM 产能／良率；TSMC 候选涉及 2nm ramp，没有 CoWoS 容量；
- Dell 资产负债表、现金流和 free-cash-flow reconciliation 可核对 AR、inventory、AP、OCF、capex 与 FCF，但不能量化其中多少由 AI 大单吸收。

## 5. 诚实 residual gaps

必需 slot 尚有 `13` 个未覆盖 facet，全部已声明 gap：

- demand：本季 pull-forward／digestion；
- pricing/value capture：AI server ASP、出货量、price-volume-mix bridge、AI product margin；
- capacity：utilization/yield、capacity release timing、HBM supply、advanced packaging capacity；
- cash：AI working-capital attribution；
- relationship：supplier capacity 到 Dell 的特定 read-through／allocation；
- counterevidence：observable invalidation threshold 与 observable quarterly threshold。

optional valuation 另缺 market PIT valuation basis、scenario/sensitivity 与 price-in boundary。声明 gap 只让执行可终态化，不会把 Pack 改成 complete。

## 6. 新暴露的对象层问题

1. Q1 summary 被 subsection classifier 误标为 disclaimer，claim splitter 因而漏掉最关键的 AI orders／revenue 句；
2. Q1 results table 继承错误的 `Capital Return` subsection；
3. metric child 丢失完整表头和报告期，单独看会把 FY2027 Q1 误读成 `2026`；
4. object SQLite 缺 direct object-id lookup，诊断时会退化为昂贵全表扫描；
5. 因此 parent、table、claim、metric 必须组成 bundle，child 不能单独承担事实权威。

这些问题将作为对象重建输入保留到 sparse／dense decision，当前不提前建索引，也不逐个以 rerank 补丁掩盖。

## 7. 边界与下一步

DELL 纵切任务可以关闭为 engineering pass，因为真实本地数据、查询、候选、source bundle、三层期间、关系和全部 gap 已被端到端物化。DELL 产品 Evidence Pack 仍不完整，也没有经过 Evidence Gate、模型研究或报告验收。

下一项严格为 `S1_MU_NVDA_CORE_UNCHANGED_TRANSFER`：冻结通用 contract、core fingerprint、plugin/module digest 与 evaluator；MU／NVDA 只能更换 case config、资料绑定和 gap。若迁移需要 ticker-specific 核心条件，则迁移失败并回到通用边界一次性处置。迁移通过后才选择三个 blind held-out identities。

关键结果：

- R1 failure：`configs/releases/fin_ia_0_1_3_s1_dell_financial_source_object_vertical_result_v1_0.json`
- current R3：`configs/releases/fin_ia_0_1_3_s1_dell_financial_source_object_vertical_result_r3_v1_0.json`
- policy amendment：`configs/runtime/fin_ia_0_1_3_s1_dell_financial_source_object_vertical_policy_amendment_r2_v1_0.json`
- generalization proof successor：`configs/releases/fin_ia_0_1_3_s0_s1_financial_research_generalization_zero_call_proof_v1_1.json`
