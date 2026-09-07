# FIN 0.1.3 DELL／MU／NVDA 证据获取尸检与跨案业务故障图

日期：2026-08-17

状态：`read_only_audit_complete / owner_repair_decision_pending`

范围：仅审计既有 artifacts；0 代码、0 模型、0 Provider、0 网络、0 检索重跑、0 索引重建、0 Evidence 晋升。

## 1. 结论先行

本次审计否定了两个过于简单的解释：

1. **不能把当前研报偏弱都归因于 DeepSeek。** DELL 的 20 条 reviewed Evidence 最终只有 8 条进入五单元模型视图，而且全部是 DELL 自身材料；Pack 中已有的发行人风险、TSM 封装瓶颈、MU 供给背景和 NVDA 供应依赖没有进入本次模型证据卡。营运资金、发行人反方和上游反方三个动态请求即使检索到候选，也返回 0 条 accepted Evidence。
2. **也不能把当前失败都归因于 S1 材料不足。** DELL 的 AI 订单 244 亿美元、当季 AI server revenue 161 亿美元和 backlog 513 亿美元已经进入模型可见 Evidence。需求单元正确使用了它们，经营单元和反方单元却又声称相关事实未披露，综合层进一步制造了一个不存在的跨单元冲突。这是独立的 S3 消费与真值一致性失败。

三个案例目前不是同一种成熟度：

| 案例 | 当前真实状态 | 不能宣称的内容 |
|---|---|---|
| DELL | 已有一条自然 Planner → 当前 S1/S2 → 五单元 → 报告链；Pack 部分命题充分，但动态晋升、反方补证和跨单元消费仍失败 | 不能宣称完整 Agentic Research、DELL 内容验收或 S3 通过 |
| MU | 有 16 条静态 reviewed Evidence 和 13 个 gap；只有一个工程形状的 `margin_and_incremental_profit` 请求，0 accepted Evidence | 不能宣称做过等价动态研究，也不能据此评价模型对 MU 的研究能力 |
| NVDA | 有 14 条静态 reviewed Evidence 和 13 个 gap；同样只有一个工程形状请求，0 accepted Evidence | 不能宣称做过等价动态研究或跨公司泛化 |

因此，当前最早需要修的不是“再换一个 Embedding”或“再跑一次完整报告”，而是 S1 的 **命题覆盖、动态 Evidence 晋升和有信息增量的第二轮补证闭环**。但 DELL 已可见事实被否认仍必须留在 S3，不能用 S1 修复替它洗白。

## 2. 审计口径与权威链

文件名只读盘点命中 622 个包含 DELL／MU／NVDA 的活动树 artifacts。大量文件是历史 attempt、capture、重复物化对象或中间证明，不能被当成 622 份独立产品证据。本次按 lineage 收敛到以下当前权威链，并用历史失败作为根因证据：

- current Evidence Pack：`configs/runtime/fin_ia_current_research_evidence_pack_result_v1_1.json`；
- claim anchor catalog：`configs/runtime/fin_ia_0_1_3_current_reviewed_claim_anchor_catalog_v1_0.json`；
- S1 查询／排名尸检：`data/workbench_private/retrieval_autopsy/20260809_three_case/AB_sparse_qrels_comparison.json`；
- 外源 capture replay：`data/workbench_private/retrieval_autopsy/20260809_three_case/D_external_capture_replay_assessment.json`；
- DELL Planner residual audit：`configs/retrieval/fin_ia_0_1_3_s1c_planner_residual_gap_audit_result_v1_1.json`；
- dynamic truth spine：`configs/research/evals/fin_ia_0_1_3_s3_dynamic_truth_spine_zero_call_result_v1_4.json`；
- DELL R7 private full result：`data/workbench_private/s3_dynamic_five_cell/FIN013-S3-DELL-DYNAMIC-FIVE-CELL-R7/full_result.json`；
- R7 独立内容验收：`configs/research/evals/fin_ia_0_1_3_s3_dell_dynamic_five_cell_R7_content_assessment_v1_0.json`；
- S1／S2／S3 当前工作记录和 Project OS。

审计逐命题回答六件事：研究想知道什么、S1 找到了什么、材料在哪一层丢失、是否补过证、模型实际看到了什么、最终属于哪个最早责任层。

## 3. 三案 Pack 不是同一种“有材料”

### 3.1 数量与可引用精度

| 案例 | accepted Evidence | issuer direct | ecosystem context | exact reviewed claim anchor | broad source segment | residual gap |
|---|---:|---:|---:|---:|---:|---:|
| DELL | 20 | 12 | 8 | 11 | 9 | 14 |
| MU | 16 | 12 | 4 | 2 | 14 | 13 |
| NVDA | 14 | 10 | 4 | 8 | 6 | 13 |

这里最重要的不是总数，而是精度差异。MU 的 16 条 Evidence 中只有 2 条是 exact claim anchor，另外 14 条仍是较宽的 source segment；它们能证明“文档里有相关材料”，不能自动证明“某条命题已经获得精确、稳定、可引用的证据”。Pack 中的 `rejected_items=0` 也不能解释为晋升精度 100%，因为动态链的 111 条未审候选根本没有进入 Pack 的 rejected 集合。

### 3.2 资料面的真实边界

- DELL 的补源最完整：手工入库 Dell Q1 FY2027 法说，取得订单、收入、backlog、主动锁单和 AI server profitability target；另入库 TSM Q2 2026 法说，取得封装和 tester 瓶颈。
- MU 已取得 current 10-Q 和 current 8-K，但没有等价的 MU prepared remarks／法说补源来闭合 HBM 产品收入、客户订单、分配、良率和先进封装问题。
- NVDA 主要依赖 current 8-K／10-Q，加 Dell、Microsoft、Micron、TSM 的有限 read-through；没有 NVIDIA-specific capacity release、yield、order/backlog/RPO 或产品量价桥。
- 当前三案 Pack 基本由 SEC／官方法说组成，不包含足以闭合估值、行业份额、渠道库存、独立客户验证等命题的成熟外部数据层。

历史外源回放也没有证明生产能力：12 个 required external case-slot 中只选出 4 个，全部来自同一种 regulatory filing source family；Tencent 同矩阵为 0/6 target-in-pool，Firecrawl 历史 control 为 5/6 但日期准确性为 0，二者都保持 diagnostic-only。

## 4. DELL：逐命题证据链尸检

DELL 的自然 Planner 提出了 10 个研究原子，但执行预算只选 8 个；`guidance_and_outlook` 与 `pricing_and_mix` 在第一次执行前就因预算耗尽被推迟。这不是小的工程细节：判断 backlog 可持续性和价值获取时，展望、ASP、组合与 attach 本来就是重要命题。

### 4.1 八个实际请求发生了什么

| 请求 | 候选 | accepted reviewed | 未审候选 | 真实业务结果 |
|---|---:|---:|---:|---|
| orders and backlog | 16 | 4 | 13 | 找到当季订单、收入、backlog、需求非线性；同时保留 fact mart 无订单指标 gap |
| conversion and durability | 16 | 2 | 14 | 找到订单／出货非线性与宽口径结果，但没有取消率、持续时间、pull-forward 定量证据 |
| reported results | 16 | 2 | 13 | 公司当季结果可用 |
| margin and incremental profit | 16 | 1 | 14 | 只接纳历史 AI mix 压低毛利率；产品利润桥仍不成立 |
| cash generation | 16 | 2 | 11 | 公司 OCF／FCF 表格可用；另有 reviewed item 因 slot 不匹配被拒 |
| working capital risk | 16 | 0 | 15 | Pack 和候选池实际存在 AI 大单、采购、信用期、取消和库存风险材料，但因 request-slot 绑定不一致返回 0 Evidence |
| issuer counterevidence | 16 | 0 | 15 | Pack 中的 Dell 自身大客户、订单波动、取消和毛利风险没有进入 EvidenceResponse |
| upstream／demand counterevidence | 16 | 0 | 16 | Pack 中的 TSM、MU、NVDA 背景没有被动态接纳，也没有产生后续定向补证 |

合计 128 个候选、111 个未审候选、8 个唯一 accepted reviewed Evidence、12 个 typed gap、0 个动态晋升。检索不是完全没找到资料，但当前动态链只允许与既有 reviewed Pack 精确绑定的对象成为 Evidence；新找到的候选无论多相关都不能在本轮被资格化。这是一个 **closed-world reviewed join**，不是完整 Evidence acquisition loop。

### 4.2 DELL 重要命题状态

| 命题 | 已找到并可用 | 丢失或仍缺 | 补证情况 | R7 模型实际消费 | 当前判断 |
|---|---|---|---|---|---|
| AI 需求规模真实 | 244 亿美元订单、161 亿美元当季 AI server revenue、513 亿美元 backlog、pipeline／客户广度 | 无取消率、订单承诺强度 | Dell 法说已补 | Demand 正确使用；Operating／Counter 又错误否认 | 证据 ready；S3 跨单元消费 fail |
| 需求可持续性 | 客户主动锁定、需求／出货非线性、大客户集中与取消风险 | pull-forward、消化期、backlog duration、取消／推迟量化 | 没有针对 residual gap 的第二轮检索 | Demand 能形成有界判断 | `partial_with_material_gaps` |
| 公司经营表现 | 当季收入、利润、利润率、现金流和可比关系 | AI 与传统基础设施的完整分拆 | current 8-K／S2 已有 | Operating 使用公司数字，但误称 AI 当季收入不存在 | 公司层 ready；产品层 partial；S3 fail |
| AI 价值／利润获取 | AI mix 历史压低毛利率；法说称 AI server profitability 达 mid-single-digit operating income target | 产品收入→成本→利润桥、ASP、units、PVM、attach | 法说补到 target，未补成审计级桥 | Value 只看到历史 mix Evidence 和公司数值，保守通过 | `blocked_by_numeric_or_bridge_authority` |
| 公司现金转换 | OCF、FCF、capex、现金和营运资本表格 | AI 订单到存货／应收／应付／现金的产品桥 | 无第二轮产品营运资金补证 | Cash 公司层判断基本可用 | 公司层 ready；AI 现金桥 blocked |
| 供给瓶颈 | TSM packaging／tester 瓶颈、MU ramp、NVDA third-party reliance、Dell memory 约束 | Dell-specific allocation、capacity release、yield、交付时点 | TSM 与 Dell 法说已补 | R7 的 8 条模型 Evidence 全是 DELL，供应链上下文没有进入模型证据卡 | Pack partial；动态投影 fail |
| 反方与 WWC | Dell 大客户、订单波动、取消、working-capital、毛利压力；NVDA export risk | 可观察阈值、独立客户／行业反证 | 无真正反驳驱动的第二轮搜索 | Counter 只得到宽口径 Dell 8-K 和少量 NumericFact，继而错误否认订单／backlog | Pack 有料；S1 动态接纳 fail；S3 消费 fail |
| 估值 | 无成熟 PIT valuation Evidence | 价格时点、倍数、情景／敏感度 | Alpha Vantage 等工作未进入当前 Pack 权威链 | 未进入五单元主问题 | blocked；完整研报不可宣称估值完成 |

### 4.3 模型真正看到的不是 20 条 Pack

R7 的五单元模型输入只编译了 8 条 Evidence：

- Demand：4 条；
- Operating：2 条；
- Value：1 条；
- Cash：2 条；
- Counterevidence：1 条；
- 去重后共 8 条，全部 `issuer_direct_source`。

因此，“DELL Pack 有 TSM／MU／NVDA 供给和反方材料”并不等于“模型在本轮看到并能使用这些材料”。当前 Pack、EvidenceResponse 和 cell-local projection 之间缺少一张命题覆盖账，材料会在不显眼的位置静默消失。

### 4.4 R7 的独立 S3 错误

R7 首次完整物化五单元报告，但金融真值验收失败：

- Operating 称 AI narrative 只有 guidance，没有当季 AI revenue；它自己的 selected Evidence 明确写了当季 161 亿美元 AI server revenue。
- Counterevidence 称没有单列 AI orders／backlog；当前 Evidence 明确写了订单与 backlog。
- Synthesis 把上述 false absence 升级成 demand 与 counter 之间的“冲突”。

R7 L1/L2 因此失败，八维只能给 diagnostic 21/32，不能给正式通过分。这里的最早责任层是 S3 `cell visibility ≠ case absence` 和跨单元真值协调，不是 S1。

## 5. MU：逐命题证据链尸检

MU 当前 Pack 的业务材料并非空白，但精确对象和动态验证明显不足。

| 命题 | 当前材料 | 主要缺口／误差 | 补证与模型消费 | 状态 |
|---|---|---|---|---|
| HBM／AI 需求 | MU 说 AI 推动需求超过行业供给能力；战略客户 price-band agreements；Dell／Microsoft read-through | 没有 Micron-specific HBM 订单、backlog、客户 volume 和 pull-forward 证据 | current 10-Q 已入库，但未发起自然动态请求；模型未等价消费 | partial |
| 当期经营 | current 8-K 结果、current 10-Q 业务单元和表格 | 14/16 Evidence 是 broad segment，精确命题定位弱 | 没有完整动态 run | 材料存在，产品链未证明 |
| 量价与价值获取 | DRAM／NAND ASP 与 bit shipment 方向；客户 price bands | 不是 HBM-specific 产品收入／利润桥，也没有 HBM units／yield bridge | 未做 residual-gap 驱动补证 | partial，S2 bridge blocked |
| 供给与执行 | DRAM／HBM 扩产、需求大于供给、capex；TSM context | 缺先进封装、真实代工／组件依赖、客户分配、利用率／良率、die-size／stack yield | 没有 MU prepared remarks／法说定向补源 | partial_with_material_gaps |
| 现金与资本 | capex、adjusted FCF、客户 deposits／commitments | HBM-specific cash／return bridge 不存在 | 没有动态判断 | 公司层材料可用，产品层 blocked |
| 反方 | underutilization／ramp cost、客户集中、数据中心建设延迟、出口管制 | 没有把支持与反方组成同一命题覆盖状态 | 未运行反驳循环 | Pack 有料，动态链未证明 |
| 估值 | 无 PIT 估值事实 | price-in、倍数、情景／敏感度 | 未补 | blocked |

MU 的 dynamic truth spine 只有一个为测试形状准备的 `margin_and_incremental_profit` 请求：16 候选、0 accepted、16 unreviewed、1 typed gap、0 模型调用。这不是 MU 动态研究失败，而是 **MU 动态研究尚未真正执行**。

## 6. NVDA：逐命题证据链尸检

| 命题 | 当前材料 | 主要缺口／误差 | 补证与模型消费 | 状态 |
|---|---|---|---|---|
| AI 需求与部署 | current revenue／Data Center result、outlook、管理层 AI factory buildout、自有客户集中风险；Dell／Microsoft read-through | 没有订单、backlog／RPO、units、ASP 或需求转换链；管理层宏观表述不等于订单耐久性 | 无 NVDA 动态 research run | partial |
| 当期经营 | current 8-K 结果与 outlook，S2 有公司财务事实 | 结果仍多为 broad source segment；产品量价桥不足 | 未做自然模型消费 | 公司层较强，产品桥不足 |
| 供给与执行 | third-party manufacture／package／test reliance；MU／TSM read-through | NVIDIA-specific advanced packaging capacity、release timing、allocation、yield 不存在 | 共享 read-through 未在动态链验证 | partial_with_material_gaps |
| 现金与资产负债表 | 财务表格与 H20 库存／purchase-obligation charge | Pack 仍登记 capex-to-FCF gap，但 current S2 可能已能给公司层公式，存在 S1 gap 与 S2 能力状态漂移 | 需要先做状态对账，不应直接补网页 | contract drift suspected |
| 反方／监管 | architecture transition、channel inventory、客户集中、出口管制、China foreclosure、H20 charge | 独立需求反证和可观察阈值仍弱 | Pack 材料较强，尚未动态组织 | partial |
| 估值与量价 | 无成熟 PIT valuation、ASP／units／PVM | 全部为 material gap | 未补 | blocked |

NVDA 同样只有一个工程形状的利润请求：16 候选、0 accepted、15 unreviewed，另有一条 reviewed item 因 slot 不匹配被拒。没有自然 Planner、补证循环、五单元模型消费或报告，所以不能拿它给“跨案例泛化”打通过标签。

## 7. 跨案例业务故障图

| 故障层 | 三案中的真实表现 | 最早责任层 | 为什么不能用别层代偿 |
|---|---|---|---|
| 研究请求完整性 | DELL 10 个问题因固定预算丢掉 guidance／pricing；MU／NVDA 没有等价自然计划 | S3 Planner → S1 request boundary | 检索器无法找一个从未被请求的问题 |
| 来源覆盖 | 历史外源只覆盖 4/12 required slots、单一 source family；DELL 主要靠人工官方 PDF 补强 | S1-D source acquisition | reranker 无法从 0 个有效来源中救回资料 |
| 对象精度 | DELL／MU／NVDA exact anchor 分别 11/20、2/16、8/14；大量宽 source segment | S1 object compiler | 更强 Embedding 也不能把宽段自动变成经审 claim |
| 头部排序 | DELL issuer results target 曾在 rank 12/13；MU current result 可到 rank 7；过期应收、费用表、风险共现会压过真正命题 | S1-C query／ranking | 但 union candidate ceiling 已较高，不能把所有问题都归成召回不足 |
| Evidence 晋升 | DELL 111 unreviewed、0 promotion；known working-capital／counter Evidence 因 slot mismatch 返回 0 | S1 Evidence Role／Gate／binding | 模型不能引用没有进入 EvidenceResponse 的候选 |
| 命题覆盖账缺失 | Pack 有材料、动态 response 没材料、cell view 又更少，当前没有统一 CoverageState 解释丢在哪 | S1 Pack Readiness contract | Evidence 总数无法显示某个命题为何 partial／blocked |
| 第二轮反驳／补证缺失 | 8 个 DELL 请求一次并行完成后即停止；没有依据第一轮 gap 产生更窄请求；MU／NVDA 更未执行 | S1 loop＋S3 orchestration | 手工入库几份 PDF 不等于 Agentic Research |
| 数值／因果桥 | 产品收入→成本→利润、AI working capital、PIT valuation 普遍缺失 | S2 | 文本相似度或模型叙事不能创造权威桥 |
| 模型消费与真值 | DELL 可见的 revenue／orders／backlog 被不同 cell 否认 | S3 | 补更多资料不能修复“已经看见仍否认” |
| 泛化评测不对称 | 只有 DELL 走过自然 Planner 和五单元；MU／NVDA 只是静态 Pack＋工程请求 | eval／release governance | 三个 Pack 文件不等于三个完整案例 |

## 8. 对“是不是检索模型不够好”的审计答案

BM25、BGE、Qwen／reranker 的确有排序不稳，尤其会把主题相近但证据角色错误的内容推到前列。但现有证据不支持把下一步定义为全面调 Embedding 或重建所有向量：

- 早期同一 18 题评测中，监督查询使 source target top-10 从 16/18 提到 17/18；BM25＋BGE candidate union 在更宽候选池可到 18/18。
- 但 reviewed exact object coverage 仍只有 6/14；说明“来源进池”与“可引用命题证据”不是一回事。
- DELL 动态链即使得到 128 个候选，仍然 0 动态晋升；这是晋升和 coverage contract，不是 Embedding 能独立解决的问题。
- 已知 working-capital／counter 材料已在当前库中，却因 slot 绑定和 reviewed join 丢失；重建向量不会自动修复。

所以 Embedding／reranker 仍应保留为后续受同一 proposition eval 约束的候选层，但不是本次审计识别出的第一处结构性断点。

## 9. 当前 Pack Readiness 判定

Pack Readiness 必须逐命题给出，不能给公司一个永久总分：

- **DELL**：需求规模、公司经营、公司现金为 `ready_for_current_scope`；需求耐久、供给、反方为 `partial_with_material_gaps`，且存在 `blocked_by_evidence_admission`；产品利润／AI 现金／估值为 `blocked_by_numeric_or_bridge_authority`。完整正式研报不 ready。
- **MU**：公司经营、周期量价和部分供给材料为 partial；HBM 产品需求、分配／良率、产品利润、估值仍 material blocked；动态 Pack Readiness 未被执行链验证。
- **NVDA**：公司经营、监管反方较强；需求耐久、供给时点／良率、量价、估值为 partial／blocked；动态 Pack Readiness 未被执行链验证。

## 10. Owner 决策前的建议，不等于实施授权

基于最早责任层，我建议下一修复决策按下面顺序评审：

1. **先做 S1 最小闭环，不先换模型。** 建立 proposition-level CoverageState；把 candidate 的 accepted／rejected／unjudged／needs-review 连成同一账；修复 reviewed Evidence 的 slot/facet 绑定；允许 capture-bound、受审计的新候选在本轮晋升。
2. **再做一次真实的第二轮补证。** 先用 DELL 的 working capital、issuer counter、upstream counter 三类失败命题证明“第一轮 gap → 更窄请求 → EvidenceDecision → 信息增量／停止”。
3. **然后用同一内核跑 MU 与 NVDA。** 必须从自然问题开始，不再用一个利润请求代替完整案例；结果用于判断 source／object／query／ranking 的剩余问题。
4. **S2 独立补桥。** 产品利润、PIT、AI working capital 等不能塞回文本检索。
5. **最后回到 S3 修消费。** DELL R7 的 false absence／false conflict 使用原 Evidence 重放，不依赖新增材料；通过后才把 S1 改善后的 Pack 用于动态研究与灵活报告结构。

不建议现在做：全面重建向量库、直接微调 Embedding／reranker、无目标扩大 broad web search、再次固定 Pack 全报告 live、或让 MU／NVDA 直接进入“泛化通过”评测。

本报告只完成只读审计与责任分账。代码修复、索引重建、Provider 采购、补源 live、模型调用和 S3 successor 均等待 Owner 下一步决策。
