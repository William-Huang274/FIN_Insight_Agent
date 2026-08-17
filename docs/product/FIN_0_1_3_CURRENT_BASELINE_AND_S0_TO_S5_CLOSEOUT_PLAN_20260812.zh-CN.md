# FIN 0.1.3 当前基线与 S0–S5 收口计划

日期：2026-08-12
状态：`repository_baseline_complete / runtime_registry_R11 / S1_object_route_and_Dell_targeted_source_engineering_pass / S1_candidate_to_Evidence_product_open / S2_company_fact_mart_and_transcript_numeric_nonregression_pass / S2_operating_metric_and_product_bridge_open / fixed_pack_and_dynamic_single_cell_accepted / five_cell_R2_partial_two_valid_three_analysis_budget_failed / compact_partial_node_successor_under_engineering_qualification / natural_five_cell_and_generalization_pending / product_iteration_not_closed`
## 1. 这份文件拥有哪项真值

本文件是 FIN 0.1.3 唯一当前执行计划。它取代两份已经迁入版本归档的旧计划；旧文件只保留决策和失败历史，不再拥有当前进度或下一步权限。

FIN 0.1.3 的版本目标不变：形成 FIN 0.1 Internal Alpha 的可审计纵向研究闭环。当前仓库重定基只是为后续产品工作建立一条可读、可测、可维护的主线，不等于版本产品收口。

## 2. 当前真正可用的产品

- `/workspace` 展示 DELL、MU、NVDA 三个身份和摘要均绑定的 reviewed Evidence Pack。
- `/operations` 独立展示当前运行配置、来源包、准入数据构建和已保存运行；历史作业明确标记为仅供审计。
- 无数据挂载时仍可查看案例目录，但详情入口禁用且 `/api/readiness` 返回 typed HTTP 503；不得假装数据就绪。
- 挂载 reviewed pack 后可查看 Evidence、拒绝理由、来源边界和 residual gap。
- DELL 当前 Pack 已包含 SEC、Dell IR 和 TSM IR 官方来源（20 Evidence／14 gaps）；MU/NVDA 暂保留旧 Pack。Workbench reviewed 表面的结构化数值项仍为 0，但 private S3 `value_capture` R2 已真实消费 8 个 NumericFact 和 4 条同口径 relation。后续 FAS-R1 又证明：在同一 fixed Pack 上，片段专属上下文＋分析／交卷分离可以让 DeepSeek 自然形成一条 L1 合格的 thesis，并避免把 AI 产品归因为 ISG／公司利润。该结果仍未形成完整 Judgment、五单元或 Workbench 报告，补证请求也没有执行检索；因此不能声称完整多源研究、动态 Agentic Research 或完整报告已经完成。

## 3. S0–S5 责任与当前状态

| 阶段 | 只拥有的责任 | 当前事实 | 通过条件 |
| --- | --- | --- | --- |
| S0 | 产品/技术合同、身份、权限、版本、仓库与运行时基线 | G01–G12 已通过并合并远端 main | 单主干、单消费者、archive 隔离、secret/CI/container/clean-main 全绿 |
| S1 | 类型化 EvidenceRequest、内外源发现、解析、chunk/object、SQL/lexical/semantic/graph 路由、rerank、Evidence Role、来源覆盖 | 保存的自然 Planner atoms 已执行 8 个 request／128 个 Qwen＋BM25 候选并逐项归责；两个新 ranker 与 Evidence Role 均未晋升。TSM 与 Dell 官方 PDF 已经共用 parser/Gate 进入当前 DELL Pack，当前为 20 Evidence／14 gaps；MU/NVDA 未偷换。route policy 声明 `typed_relationship_graph`，当前 Runtime 尚无执行 handler | 三案及独立留出案例的 request-to-plan、required-slot target-in-pool、日期/实体/关系、route contribution 和 Evidence Role 正确；数值请求可靠路由到 S2 exact lookup，图路线只能在真实 handler 与来源权限通过后计为能力，外源只补真实 residual gap |
| S2 | 公司财务事实 mart、Evidence/NumericFact 编译、PIT、单位/期间、引用和冲突 | private mart 已从三案 SEC capture 建立，1,319 observations、24/24 精确事实查询及 mutation 通过；DELL 受控纵切为 7/7 typed request resolved、21 NumericFacts、0 gap/conflict | 数值事实从权威对象确定性入库和查询，跨案/错期/错单位 fail closed，typed exact lookup 返回 NumericFact 或可信 gap；自然 planner、研究消费和三案依赖回归证明产品价值 |
| S3 | 动态规划、工具使用、重裁决、研究综合、角色方法、单元级图上下文、Workpaper/Report | fixed-Pack 与 DELL `value_capture` 动态单单元已 accepted；五个 RoleMethodPack／current-case GraphContextPack 已通过正式零调用资格化。尚未自然执行五单元、跨单元综合、完整报告或跨案例泛化 | DELL 完整动态案例与异质跨案例泛化均通过 L1、八维绝对质量、paired gain 与 qualified-human 内容验收；每个 model-visible RoleMethodPack／GraphContextPack 可重建并有自然消费 receipt；逐案硬门不得被平均分掩盖 |
| S4 | 用户任务、Evidence/Gap/Workpaper/Review/Repair 产品闭环 | 只有只读 Evidence Workspace 和独立 Operations | 当前 S3 candidate 被真实 UI 消费；review/repair/lineage 可完成且不依赖旧产品面 |
| S5 | 发布、回滚、运行、成本、安全和 Owner acceptance | 未开始；本次仓库 merge 不是 S5 | RG1–RG5、clean deploy、回滚和 Owner 签署全部成立 |

失败必须回到最早责任阶段；不能在 S4 页面、Writer 或 renderer 用补丁掩盖 S1/S2/S3 缺陷。一次失败只产生新 attempt，不产生新版本。

## 4. 当前重定基完成后的执行顺序

1. **S0 仓库基线（已完成）**：G01–G12 已通过，远端 `main` 已从第二份 clean-main 工作树完成复证。
2. **S1-A 已完成——类型化本地检索纵切**：已建立 provider-neutral 金融内核、9 slot / 17 facet 查询、身份/截至日/source-role 约束和真实 Workbench 候选消费者；三案同核心迁移通过。它只证明工程纵切，不代表 S1 产品通过。当前历史候选库对 DELL/MU/NVDA 的 reviewed target 对照分别只命中 4/0/6，三案 PIT 行情角色均缺失。
3. **S1-B 已完成——current source/object 重建**：当前 store 为 28 parent / 1,805 child，含 NVDA 当前 10-Q、DELL/MU 当前 SEC、TSM 6-K 与三案 PIT market role；表边界、child 大小、身份和截至日硬门通过。Dell/Micron 官方法说 PDF transport、TSM 先进封装和新鲜估值仍为 typed gap，不阻断对象层工程关闭。
4. **S1-C successor 与请求入口已完成**：Owner 四条 successor 已另存应用，18/18 映射；缓存复跑 BM25=`17/18`、BGE-M3=`14/18`、RRF／旧规则=`16/18`。`EvidenceRequest → 按需 facet → QueryFacetPlan` 已进入当前 Runtime，固定 pack 继续作为部件回归。自然语言理解仍归 S3，交互仍归 S4。
5. **S1-C Cross-Encoder／Evidence Role shadow 已完成**：现成 BGE reranker 与 BM25 同为 `17/18`，MRR 有增益但逐题仍有严重反转，未晋升。规则角色门把三案显式错角色减少，却将 Recall 压到 `13/18`；留出正例约七成 abstain，禁止上线。第一版错误的 cross-slot 负例合同保留为失败证据，校正后留出 Cross-Encoder top3=`17/17`，角色门 top1 仍退化。
6. **S1-C 对象级角色数据合同已完成开发复核**：24 个源绑定 object／35 个 query relation 已明确 claim、metric table、parent context、多标签 role、fact state、directness 和 positive／hard negative／unjudged；标签与模型可见 surface 分离，三案例开发批次没有读取 ORCL／ASML／ANET 留出。固定模型复核为 pairwise `0.50`、top1 `0.60`，旧规则角色 F1=`0.507936`，故没有微调、训练或 Runtime 晋升。
7. **S1-C0 检索栈、数据库通道和 test-precut 治理（已完成）**：已冻结 SQL/typed exact lookup、BM25、BGE-M3 dense/learned-sparse/multi-vector、Qwen Embedding、typed graph、BGE/Qwen Reranker 和独立 Evidence Role 的分层边界；HPQ／AVGO／INTC issuer-time test-precut 已在新模型结果出现前绑定，ORCL／ASML／ANET 降为已观察 validation。当前没有模型、训练或 Runtime 晋升权限。
8. **S1-C1 query family、对象编译器与 typed fact route（已完成工程门）**：17 facet 已且仅映射到 11 类问题；混合请求拆成同 cell 的 narrative／fact sibling。1,805 个 current child 编译出 20,340 个去重 claim／metric-row／context 候选，2,425 个重叠切块重复已合并并保留 lineage；高管年龄表等 228 张非金融数值表已拒绝。标签回放进一步修复空表吞掉 TSMC claim、Micron 重复 Revenue 行缺少业务单元上下文，以及 8-K filing date／issuer reporting period 混用。24 类指标可路由到 typed fact request；mart 不存在时返回 S2 typed gap，存在时交给 S2 executor，始终不把表格行冒充 NumericFact。
9. **S1-C2 多检索器有界对照（已完成 shadow，无产品晋升）**：同 20,340 对象上，BM25、BGE-M3 三模式与 Qwen Embedding 已完成有界对照；Qwen 模型资产后续通过合格本地路线取得。Runtime Query Atom 中 Qwen 前十正例为 8/15、BM25 为 5/15，二者在真实 DELL results／cash 请求上表现互补，因此 provisional 产品方向修订为 `Qwen semantic + BM25 lexical candidate union`，不是 winner-take-all，也不是当前 endpoint 已晋升。
10. **S1-C3/C4 Runtime Query Atom 模型 shadow（已完成，无 Runtime 晋升）**：18 个原子问题上，BM25／BGE／Qwen Embedding 前十正例分别为 `5/15`、`0/15`、`8/15`，自然共享池为 `10/15`，未过 0.80 门。Qwen Reranker 受控 pairwise=`12/16`，但自然 top10=`7/15`，没有超过 Qwen Embedding；BGE Reranker=`8/16`。因此冻结 `Qwen Embedding provisional + BM25 fallback`，Qwen Reranker 仅 shadow。Evidence Role 正例 compatible=`10/16`、负例拒绝/abstain=`15/18`、F1=`0.5818`，禁止上线和微调。残缺片段及错误关系 qrel 保留为 S1 复核问题，不能通过改标签追分。
11. **S1-C 保存 Planner 输入审计完成、S1-D TSM 侧已贯通但 Dell 仍阻断**：10 条保存 atoms 稳定选择 8、延期 2；8 个真实 request 返回 128 个候选、19 resolved／9 typed gap／45 NumericFacts。共同 Source Intake、私有 raw CAS、自动/人工 driver 已接入 Workbench。Owner 关闭 TUN 后 TSM route 取得 22-page PDF；共用 parser／对象／Gate 只晋升第 10、20 页两条 bounded context，私有 DELL successor 为 17 Evidence／15 gaps，S2 不变。Dell 仍在 HTTP status 前 timeout，current Pack 未切换。Micron 与估值没有偷塞进本轮。
12. **S2 公司财务事实 mart（受控纵切 engineering pass）**：已从 2026-08-06 DELL／MU／NVDA CompanyFacts 与 Submissions 原始 capture 建立 1,319 条 observation，按 accession、accepted-at、vintage、期间角色、单位、taxonomy concept、source digest 和 supersession 保存；最近财年 9/9、当前 interim 15/15，PIT、跨案、季度/YTD、公式和 disclosure-cohort mutation 全过。DELL 受控纵切执行 7 个指标请求并全部 resolved，共返回 21 个 NumericFact、0 gap/conflict；private mart 仍不进入 Git，自然 planner、报告与前端消费未证明，故不宣称 S2 产品关闭。
13. **DELL S1/S2/S3 零调用纵切（已完成工程门）**：当前 Runtime 已把受控 Research Objective／planner atoms 编译为 5 个 EvidenceRequest；S1 使用 `Qwen semantic + BM25 lexical candidate union` 返回 80 个候选，S2 返回上述 NumericFact。该结果证明给定正确 atoms 时链路和数据库可协同运行，但没有证明 DeepSeek 能自然规划、候选已成为 Evidence 或研报质量通过。
14. **自然 Planner Canary R1（已执行并 terminal failed）**：DeepSeek Pro exact JSON、DELL 身份、5/5 required slot、10/10 facet 和全部 canonical metric/family 均正确，但返回 10 个 atoms，超过授权上限 8，故在 S1/S2 successor 前停止。没有 retry、fallback、手工裁剪或报告调用；这不是数据库失败。
15. **proposal/execution budget 分层处置（已完成）**：R1 10 条合法提案全部校验，本地按 required-slot 和 provider-neutral priority 稳定选择 8、延期 2；R1 失败 capture 保留，未重跑 Planner。
16. **保存 atoms 的 S1-C 产品输入审计（工程切片完成，产品门未关）**：Harness 已派生多 owner，owner-balanced 候选保护已实现；两个新 ranker 均因真实业务退化被拒绝，Evidence Role 仅 advisory。候选池可审计，但候选仍不是 Evidence。
17. **S1-D 本轮有界补源与 current Pack 提升（已完成）**：TSM 22-page PDF 晋升两条先进封装 bounded Evidence；Dell Q1 FY2027 14-page 官方托管 transcript 经绑定 route 人工入库，共用 parser/Gate 晋升三条 direct Evidence，覆盖 $24.4b AI orders、$16.1b AI server revenue、$51.3b backlog、需求大于供给、memory constraint、主动锁定基础设施以及 AI server 中个位数营业利润率目标。只有利润率 gap 被关闭；提前采购幅度/消化、ASP/PVM、供应分配、容量时点和估值继续可见。一次零调用 current composition 把 DELL 从 15／16 提升为 20／14，MU/NVDA 和留出案例保持原摘要与 digest；Runtime Registry R11、真实私有挂载和 Workbench 三案验收通过。
18. **S2 三案有限依赖回归（已完成）**：Dell/TSM transcript 只作为叙事 Evidence，没有获得 NumericFact 权限；公司事实 mart 保持 1,319 observations、SQLite SHA-256 `d05b0cc8...c585`，没有因补源改变数值真值。
19. **S3 当前 research consumer 纵切（v1.1 clean zero-call engineering pass）**：保留已经完成的 DELL Planner R1，不重复付费证明规划。当前活动树只有一份 provider-neutral `Evidence Pack + NumericFact → judgment/workpaper/report` consumer。v1.1 让 Harness 注入可信 envelope/gaps，明列枚举，以 cell-local card 阻断跨单元引用，并增加 `support/limit/context` Evidence use 与显式 inference authority。绑定干净远端提交的 R3 为 0 网络／模型／Provider，六类 mutation 全部 fail closed，旧 R1 继续被拒绝。模型负责引用选择、机制、反方、置信度与 WWC；本地控制面负责事实、身份、数值、日期、引用和结构。它是长期提交合同，不是 DeepSeek 专用补丁。
20. **DELL 自然综合 Canary R1（terminal failed）**：Provider HTTP/finish reason/exact JSON 和 5/5 cells 成立，但模型遗漏本地 envelope，并自创未在 model-visible view 中列出的枚举；另有跨 cell ref、复合 Evidence 二元角色冲突和自由数量级表述。零调用内容审计还发现 AI→EPS/分部利润、AI→营运资金、上游扩产→Dell 瓶颈缓解等越界归因。R1 0 retry、0 fallback、0 发布，且永久保持失败；由于官方 GA 沿用相同模型名，不能事后把 R1 标为 Preview 或 GA。
21. **DeepSeek GA Agent loop 资格路线（Chat／Responses 传输通过，内容 L1 未过）**：三个可替换 GA profile、capture-first tool-step transport 与 reviewed Evidence／NumericFact／EvidenceRequest／Judgment 四工具循环已建立。JSON R2 Judgment 通过本地合同与 L1/L2，节点适用维度 18/24；strict Beta 停放。标准 R1 的 wire `index`、安全只读并行、receipt 和 capture ref 项目缺陷已由 v1.1 successor 与 fresh zero-call R3 关闭。
    - 唯一 replacement R2 已真实完成 Evidence＋NumericFact 两个 read 并保存 receipt；随后模型针对 AI server unit volume 提出业务相关补证，但 Tool Schema 未公开 120-char/数组门，也未表达 facet→query family→metric 依赖，导致 Schema-valid／local-invalid。R2 永久失败，不追认。
    - 唯一 Tool Contract Compiler、typed proposal repair、三案 identity mutation，以及 Chat／Responses／Anthropic canonical projection 已通过绑定 `17bb0c5a...` 的 formal replay。Anthropic 仅 shadow；Chat control 与 Responses candidate 共用同一金融循环。
    - 绑定 `aafd8be3...` 的 DELL `value_capture` Chat/Responses 同输入 paired 已执行：两路均 5 step／6 receipts、0 retry/fallback/external retrieval；Responses 真实 continuation 通过，但总 token／耗时分别约为 Chat 的 1.36x／1.58x。
    - 内容层两路均未通过 L1：比较性叙事没有绑定 same-cadence Numeric relation；gap 提示允许行业数据但 request 实际只允许 SEC route。Responses 还更强地把多驱动利润改善归因于 AI 周期。Chat 保留 provisional primary，Responses 保留 shadow/candidate。
    - 旧角色 Skill／GraphPack 重新资格审计确认：方法内容大多仍有价值，但旧对象和运行接口过时。历史 paired request 没有注入这些上下文；后续 Research Context Closure 已只迁移 `value_capture` 所需方法与本案即时图上下文。
    - Research Context Closure R3/R4 与 replacement Chat R2 已完成：R2 正确消费 8 个 NumericFact、4 条同口径 relation、6 条 RoleMethod step 和 1 条当前 Graph edge，并保持 ASP／unit／PVM 为 open gap。最终仍把多因素公司／ISG 利润改善过强归因于 AI server，并加入未绑定的 semi-fixed cost 机制，故因果归因 L1 fail，五单元继续 blocked。
22. **角色 Skill／图谱／DeepSeek Harness 重新资格（只读审计已完成）**：旧 fundamental、industry/supply-chain、product、valuation、risk、lead、writer、verifier 方法选择性迁移；旧 renderer／aggregator 和重复版本不恢复。旧图数据不复用，完整 typed graph handler 留在 S1。官方 Harness 的 scoped Skill、progressive disclosure、context log 和 preset 只作为 provider-neutral pack 的可选 shadow 宿主，不接管金融 Evidence／NumericFact 权威。
23. **S1→S3 全链审计（只读完成、纵切方向已获 Owner 授权）**：审计确认当前主链的最早产品断点是 `candidate → EvidenceResponse` 未在 Agent loop 内闭合；S2 只对标准公司财务事实形成权威，订单／积压／销量／ASP／PVM／产品利润桥与估值仍缺 typed authority；S3 则缺 claim scope 与 causal bridge 强制门。原先单独的 S3 causal gate 仍有必要，但若不与 S1 Evidence 回流和 S2 operating-metric／bridge 纵切一起设计，只会得到更安全但可能更空的结论。Owner 已授权在完整 fixed-Pack 通过后闭合这条动态 Research Truth Spine；该授权不允许跳过 fixed-Pack 门或直接运行五单元。
24. **三层验收前两层与 S1 来源同步（已关闭）**：fixed Pack 只测试“给定合格资料时能否可靠分析”，不计作 Agentic Research；第二层 DELL `value_capture` 已自然经历 planner、当前 S1/S2、reviewed-only EvidenceResponse、三个 Judgment 片段和一次有界同片段修复，独立 L1 与适用内容质量 `21/24` 通过。`RC-S3-028` 已由 TemporalAuthority 和模型自有修正文关闭。随后三案全量回放关闭 `RC-S1-019`：Dell 与 TSMC 已审法说进入当前对象库和受控 slot 路由，三案 reviewed source 对象级缺失为 0；formal v1.4 普通 DELL demand request 可命中 Dell 法说且未审候选 0 晋升。该同步不等于 S1 排序／角色质量或 S3 产品通过。
25. **DELL 五单元动态完整案例（R6 四单元有效，Value repair successor 工程门已闭合）**：有限 S2 回归、五个 RoleMethodPack、本案即时 GraphContextPack 和稳定 runner 已资格化。R1–R5 继续作为不可变历史失败；R6 在 cell-local 合同下完成 5 个 analysis 与 5 个 submission，Demand、Operating、Cash、Counterevidence 四单元有效，Value 因旧合同重复要求 NumericRelation 端点、relation-required QF 和全局 Evidence 角色而失败，综合未执行。零调用结构包已把这些表面统一改为 provider-neutral 的依赖权威编译，保留模型 Judgment 与自由叙事所有权；日期／数字／引用门禁和产品利润桥 gap 不放宽。真实 R6 capture、四个有效 digest、失败 Value call、五单元 fake synthesis 和负向 mutation 已通过两个独立 126-test 进程。下一步只能在全仓、clean push 与 repository-bound preflight 后签发 fresh R7，最多执行一次 Value repair submission 与两次 synthesis 调用，0 retry；不得重跑 Planner、S1/S2、五个 analysis 或四个有效 Judgment。即使 R7 形成报告，也仍须依次验收身份／期间／来源／数值 L1、逐单元判断、跨单元综合、八维绝对质量、paired gain 和 qualified-human 内容；不得自动等同 DELL 或 S3 acceptance。
26. **S4 产品闭环**：提供真实任务输入、澄清、计划查看和人工修改界面，并把通过验收的研究结果接入当前 Workbench；补齐 human review、repair 和 artifact lineage。
27. **S5 release**：扩大案例与对抗测试，执行发布、回滚、成本和 Owner acceptance。

## 4A. 2026-08-15／16 Owner 连续执行授权

Owner 已把原三层验收扩展为同一 FIN 0.1.3 内的连续执行范围：完整 fixed-Pack Judgment、动态 Research Truth Spine、DELL 单单元、DELL 五单元，以及 MU／NVDA 同核心迁移和跨案例验收。执行仍受前置门约束：项目缺陷留在 S1／S2／S3 最早责任层修复；每个失败 attempt 保持不可变，修复后使用新 attempt／authority，不得在同一 attempt 隐式 retry 或把失败改写为成功。一次 live 未通过不再自动触发 Owner 返回点；只有产品范围、数据采购／授权、模型主路线、S4 publication 或 S5 release 的实质变化需要暂停决策。

当前第一项的最早责任层已推进到 `RC-S3-020`：不再增加 Prompt、token 或 Provider 分支，只把 defense-in-depth 从“全文关键词共现”改为“同一分句中的正向因果命题”，并识别明确否定。先保存 R4、完成 replay／mutation／全仓复证和 clean push，再由 Project OS 独立决定是否签发 0 retry FFJ-R5。R5 完整 Judgment 的 L1 与内容门通过前，不进入动态第二层。

2026-08-15 更新：上述接线与 preflight 已完成，但 natural Chat R1 在 mandatory reads 后因 16000 reasoning token 耗尽、零最终 tool call 而终止。该失败既不能算内容失败，也不能归咎为单纯 DS 不遵循；当前模型视图重复了 Claim／Method／Graph 卡，发送了完整审计 lineage 和零预算 EvidenceRequest schema，并要求模型逐原子重复七个已冻结的关系字段。第一项因此插入 provider-neutral 的 alias／compact-view successor，formal proof 通过前不得进入动态第二项。

2026-08-16 更新：FAS-R1 已证明片段专属上下文＋高推理分析／低推理交卷对单 thesis 有效。Owner 现授权先把同一模式零调用扩到 mechanism 和 counterargument／WWC，再做一次完整 fixed-Pack Judgment；若失败，允许在最早责任层修复并以新 attempt 续跑，不因普通 live failure 自动停下。网络错误必须区分本机代理／TUN／DNS／TLS／IncompleteRead 与业务合同失败，采用有界连通性恢复，不能把 transport 问题记成模型内容失败。

MU／NVDA 与留出案例验收必须先形成正式泛化评测设计和最终报告。开发案例、已观察 validation 和 test-precut／真正留出要分账；案例须覆盖不同产业、商业模式、来源形态、Evidence 充足度、期间与因果边界。验收至少逐案报告身份／期间／来源／数值 L1、EvidenceRequest 与 route 覆盖、Evidence 晋升与 abstain、NumericFact／bridge、动态补证、五单元内容、八维质量、paired gain、人工验收、成本和延迟。任何逐案 L1 失败不得被平均分掩盖，也不得只用几个与 DELL 相似的案例给“泛化通过”打标。

## 5. 防止再次膨胀的工程规则

1. 新能力必须先说明归属 S 阶段、真实用户消费者和替换对象；没有消费者的 runner/config/test 不进入活动树。
2. 同一合同只有一个编译源；Prompt、validator、fake、live、renderer 和 UI 不能各自维护一份结构。
3. 单次 run/attempt 的实现、admission、capture 和 proof 默认进入运行数据或版本归档，不能成为永久模块名。
4. Workbench 是常驻产品与验收入口；不得用一次性脚本代替最终用户链。
5. 测试分为确定性工程门、自然模型 canary、产品内容验收；不得为每个字段重复 live。
6. 新模型通过统一 profile/canary 获得不同自主权；provider 特殊拐杖不能进入核心金融合同。
7. 每个阶段结束时同步 PRD、当前计划、技术图、Project OS 和机器 manifest；当前投影保持短小，完整历史归档。
8. SQL/typed exact lookup、文本检索和关系图是并列通道：embedding 或 reranker 可以定位数值披露，但不能替代 S2 的事实 mart、期间/单位/PIT 和 NumericFact 权威。
9. Skill 只提供研究方法，Graph 只提供导航、作用域和机制假设；二者都不能成为 Evidence、NumericFact 或引用权威。所有 model-visible pack 必须版本化、内容寻址、可重建，并留下选择、压缩、注入和消费 receipt。
10. 官方或第三方 Agent Harness 只能实现同一 FIN 合同的宿主 adapter；不能因为框架新增 Skills、workflow 或 subagent 就复制金融控制面或恢复第二套 Prompt/Validator。

## 6. 明确不偷换的边界

- 仓库基线通过，只说明后续开发不再带着多主线和 attempt 债务；不说明研究质量已经通过。
- 三份 reviewed Pack 通过，只说明身份、摘要、来源和 gap 可以审阅；不说明 Evidence 完整或结论可靠。
- 数据构建脚本存在，只说明有受维护入口；不说明网络、授权、索引或数据已经就绪。
- S1/S2/S3 的历史 proof 仍可用于诊断，但只有当前 Runtime、当前数据和当前产品消费者的复证才能成为新能力证据。
- 固定 case 的 9 Slot／17 facet 查询包只证明下游检索部件；在 S3 自然语言规划与 S4 用户入口接通前，不得称为真实用户查询链。
