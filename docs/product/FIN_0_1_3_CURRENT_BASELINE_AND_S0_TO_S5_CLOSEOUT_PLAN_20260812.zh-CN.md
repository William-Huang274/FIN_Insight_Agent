# FIN 0.1.3 当前基线与 S0–S5 收口计划

日期：2026-08-12
状态：`repository_baseline_complete / S1_VS1_to_VS3_and_DELL_MU_NVDA_VS4_vertical_slices_integrated / VS5_all_positive_frozen_holdout_and_qualification_open / S2_company_fact_mart_pass / S2_product_bridge_open / fixed_pack_and_dynamic_single_cell_accepted / DELL_R7_complete_five_cell_report_contract_pass_truth_reconciliation_fail / reflective_agent_runtime_contract_frozen_not_implemented / full_product_chain_blocked_until_S1_qualified / product_iteration_not_closed`
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
| S0 | 产品/技术合同、身份、权限、版本、仓库与运行时基线；AgentSession、事件、checkpoint、resume/compaction 基础 | G01–G12 已通过并合并远端 main；反思型 Runtime 六合同已冻结但会话／上下文连续性尚未实现 | 单主干、单消费者、archive 隔离、secret/CI/container/clean-main 全绿；长期任务事件可重放、checkpoint/resume mutation 通过 |
| S1 | source/capture、HTML/PDF/OCR/table 解析清洗、chunk/object、版本化 index、类型化 EvidenceRequest、SQL/lexical/semantic/graph/official/external 路由、recall/rerank/金融精排、Evidence Role/Gate、Coverage/补证/gap 和 replay | 已有对象、候选、排名 shadow、Source Intake、Dell/TSM PDF、reviewed Pack 和第一修复方向；但完整 S1-A–S1-J 标准只有文档，OCR/cleaning/chunk/index/rank/fine-rank 独立资格、gold/split、新异质留出和稳定性均未完成。DELL/MU/NVDA 只作开发/回归，不是 S1 交付物 | 当前主线逐层通过独立 S1 L0–L5：source/capture、OCR/parser、chunk/object、query/route、candidate ceiling、recall、rerank、金融精排/Evidence admission、Coverage/gap、下游 ceiling、稳定性/资源；新异质留出逐案通过硬门且无 case patch，随后才允许产品资格完整真实链 |
| S2 | 公司财务事实 mart、Evidence/NumericFact 编译、PIT、单位/期间、引用和冲突 | private mart 已从三案 SEC capture 建立，1,319 observations、24/24 精确事实查询及 mutation 通过；DELL 受控纵切为 7/7 typed request resolved、21 NumericFacts、0 gap/conflict | 数值事实从权威对象确定性入库和查询，跨案/错期/错单位 fail closed，typed exact lookup 返回 NumericFact 或可信 gap；自然 planner、研究消费和三案依赖回归证明产品价值 |
| S3 | 动态规划、工具使用、反思／重裁决、研究综合、角色方法、run-local 图上下文、Workpaper/Report | fixed-Pack 与 DELL `value_capture` 动态单单元已 accepted；DELL R7 已自然执行五单元并形成首份完整内部报告，但 false absence／false conflict 使 L1/L2 未通过；当前仍是固定 workflow＋局部 repair，没有统一 FeedbackReceipt→PlanDelta／GraphDelta 循环 | DELL 修复后的完整动态案例与异质跨案例泛化均通过 L1、八维绝对质量、paired gain 与 qualified-human 内容验收；Skill／Graph 动态选择与自然消费可重放；失败能回到 owning Agent 改变计划并形成合法 StopDecision |
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
25. **DELL 五单元动态完整案例（R7 完整物化，Case Truth natural R3 未通过）**：R7 复用 R6 上游，只执行 Value repair 和两次 synthesis，共 3 次调用、0 retry，首次形成五个 Judgment、综合和完整内部报告。合同、身份、期间、数值、引用与产品利润桥边界通过，但 Operating／Counterevidence 错误否认当前 Case 已有的 AI revenue、orders、backlog，综合又制造 false conflict，故内容 L1/L2 失败。claim-polarity formal R4 的 capture replay、三案／留出与 mutation 已通过；随后唯一 natural R3 四次调用均完成，并正确识别 Counter 的 orders／backlog false absence 与两单元真实 cross-cell cash claim，但未命中 Operating AI revenue 和 typed profit bridge，且暴露 unresolved causal hypothesis 无法由现有 fact/gap 三态表达。R3 natural semantic extraction 正式拒绝，不自动进入 R4/R5。下一步先做项目级 verifier 架构处置；受影响 Judgment／Synthesis、DELL L1／八维／paired／qualified-human 均继续 blocked。
26. **S4 产品闭环**：提供真实任务输入、澄清、计划查看和人工修改界面，并把通过验收的研究结果接入当前 Workbench；补齐 human review、repair 和 artifact lineage。
27. **S5 release**：扩大案例与对抗测试，执行发布、回滚、成本和 Owner acceptance。

## 4A. 2026-08-15／16 Owner 连续执行授权

Owner 已把原三层验收扩展为同一 FIN 0.1.3 内的连续执行范围：完整 fixed-Pack Judgment、动态 Research Truth Spine、DELL 单单元、DELL 五单元，以及 MU／NVDA 同核心迁移和跨案例验收。执行仍受前置门约束：项目缺陷留在 S1／S2／S3 最早责任层修复；每个失败 attempt 保持不可变，修复后使用新 attempt／authority，不得在同一 attempt 隐式 retry 或把失败改写为成功。一次 live 未通过不再自动触发 Owner 返回点；只有产品范围、数据采购／授权、模型主路线、S4 publication 或 S5 release 的实质变化需要暂停决策。

当前第一项的最早责任层已推进到 `RC-S3-020`：不再增加 Prompt、token 或 Provider 分支，只把 defense-in-depth 从“全文关键词共现”改为“同一分句中的正向因果命题”，并识别明确否定。先保存 R4、完成 replay／mutation／全仓复证和 clean push，再由 Project OS 独立决定是否签发 0 retry FFJ-R5。R5 完整 Judgment 的 L1 与内容门通过前，不进入动态第二层。

2026-08-15 更新：上述接线与 preflight 已完成，但 natural Chat R1 在 mandatory reads 后因 16000 reasoning token 耗尽、零最终 tool call 而终止。该失败既不能算内容失败，也不能归咎为单纯 DS 不遵循；当前模型视图重复了 Claim／Method／Graph 卡，发送了完整审计 lineage 和零预算 EvidenceRequest schema，并要求模型逐原子重复七个已冻结的关系字段。第一项因此插入 provider-neutral 的 alias／compact-view successor，formal proof 通过前不得进入动态第二项。

2026-08-16 更新：FAS-R1 已证明片段专属上下文＋高推理分析／低推理交卷对单 thesis 有效。Owner 现授权先把同一模式零调用扩到 mechanism 和 counterargument／WWC，再做一次完整 fixed-Pack Judgment；若失败，允许在最早责任层修复并以新 attempt 续跑，不因普通 live failure 自动停下。网络错误必须区分本机代理／TUN／DNS／TLS／IncompleteRead 与业务合同失败，采用有界连通性恢复，不能把 transport 问题记成模型内容失败。

MU／NVDA 与留出案例验收必须先形成正式泛化评测设计和最终报告。开发案例、已观察 validation 和 test-precut／真正留出要分账；案例须覆盖不同产业、商业模式、来源形态、Evidence 充足度、期间与因果边界。验收至少逐案报告身份／期间／来源／数值 L1、EvidenceRequest 与 route 覆盖、Evidence 晋升与 abstain、NumericFact／bridge、动态补证、五单元内容、八维质量、paired gain、人工验收、成本和延迟。任何逐案 L1 失败不得被平均分掩盖，也不得只用几个与 DELL 相似的案例给“泛化通过”打标。

## 4B. 2026-08-17 R7 后的当前执行顺序

1. R7 保持不可变：五个 contract-valid Judgment 和完整 report 只能作为待修 candidate，不进入 Workbench 产品面。
2. 当前最早责任层仍为 S3，但不是再补一个 Prompt 字段。先建立 case-level reviewed fact presence catalog、cell visibility matrix 和 typed absence authority，综合 conflict 必须与全案事实目录一致。
3. 零调用回放已完成：R7 三条错误、合法产品利润 gap、DELL／MU／NVDA、排列／跨案及异质留出 mutation 全部通过；实现不含本案短语表或模型专用金融分支。
4. 15-surface semantic R1 与两单元 R1 的 reasoning exhaustion 均保持不可变；claim-polarity formal R4 已零调用通过，唯一 natural R3 也已消费四次调用。R3 解决了可见输出与容量，却因相邻 alias resolution、unresolved causal hypothesis ontology 和重复 alias shape 仍未通过。不得再自动签发 R4/R5；先做项目级 verifier 架构处置。剩余三 cell、Judgment／Synthesis 修复、DELL 验收与泛化继续 blocked；Demand、Value、Cash、Planner、S1/S2 与五个原研究 analysis 保持不可变。
5. 修复 candidate 仍需重新执行 L1/L2、正式八维、同输入 paired 和 qualified-human。DELL 通过前不运行 MU／NVDA 或留出 live；通过后才按预注册异质评测报告验证同核心泛化。
6. 本轮不改变 FIN 0.1.3、S 阶段或产品范围；这是 S3 首份完整报告暴露出的所属阶段缺陷，不创建新版本。

## 4C. 2026-08-17 S1 证据地基与动态研究结构的先后顺序更正

Owner 接受“通用研究内核＋动态 ResearchBlueprint＋多形态 DeliveryPlan”的产品方向，但明确拒绝在当前 S1 资料面尚未形成质量闭环时直接开始代码泛化。该更正不否定 S3 已完成的 fixed-Pack、单单元和 R7 证据，也不把 R7 的 false absence 错归到 S1；它重新定义了完整产品验收的上游先决条件。

当前顺序改为：

1. **先冻结产品与技术范式，不改代码。** PRD 16.38–16.39 定义稳定研究内核、动态交付方向，以及 S1 `证据获取—反驳—补证—充分性验收` 产品链。
2. **只读审计现有三案：已完成。** 当前报告位于 `docs/architecture/retrieval/FIN_0_1_3_S1_DELL_MU_NVDA_EVIDENCE_ACQUISITION_AUTOPSY_20260817.zh-CN.md`。DELL 已证明 Pack、动态晋升与 S3 消费存在不同故障；MU／NVDA 尚未走过等价动态研究链，不能计作泛化。
3. **建立 task-relative Pack Readiness：等待 Owner 修复决策。** 审计已按 proposition 区分 source access、candidate coverage、retrieval quality、Evidence admission、numeric／bridge authority 和 S3 consumption；下一步不得在 Owner 选择实现范围前自动改 Runtime。
4. **按最早责任层设计 S1 实现包。** source、parser、query、ranking、Evidence Role／Gate、S2 数值桥和 S3 consumption 分开处置；不预先假定需要重建全部索引、微调模型或购买数据。
5. **S1 门通过后再迁移研究结构。** DELL 五单元作为兼容 blueprint 保留；随后才实现 Generic Cell Runtime、Answer Projector 和 Memo Compiler，并用 MU／NVDA 和新冻结异质案例证明泛化。

本顺序下，S3 `RC-S3-043` 继续真实存在，但在 S1 只读审计和架构处置期间不自动签发新 live。S1 不充分主要解释报告覆盖、密度和证据桥不足；模型忽略已经可见事实仍由 S3 单独负责。

## 4D. 2026-08-17 S1 第一修复包、gap 资格与节点预算治理

Owner 已接受有界第一修复方向，并补充两条不可退化的产品要求：S1 必须把本地数据处理故障、可检索但链路／工具／模型执行失败、真实公共信息边界分开；从现在起所有模型节点 token 预算必须有任务依据，不能再只按省钱或速度设置。

当前实施顺序因此冻结为：

1. 为每个 material proposition 建立 `EvidenceCoverageState` 和三层 `FailureProvenanceRecord`；空结果不能直接成为 gap。
2. 让所有 candidate 进入 accepted／rejected／unjudged／needs-human-review 账本，修复 reviewed Evidence 的 slot／facet／objective binding。
3. 实现 capture-bound 受控晋升；只有不可变来源、身份、期间、引用和 Evidence Gate 通过才能成为 Evidence，模型或 rank 不能单独授权。
4. 用 DELL working-capital、issuer-counter、upstream-counter 分别验证本地数据／绑定、发行人检索／晋升和跨公司关系／外源路线，完成一次真正的第二轮补证。
5. DELL 闭环成立后，MU／NVDA 从自然问题重新规划并执行同核心；没有等价运行深度不得称为泛化。
6. 每个模型节点执行前保存 `TokenBudgetBasis`，执行后用实际 usage、required-output coverage 和内容质量校准；预算不足必须 typed 终止或显式延期，不能静默删题。

公共信息 gap 只有在本地 capture／对象／索引／SQL、适用检索路线、候选决策和来源可达性全部留下凭证后成立。`source_temporarily_unreachable`、`not_yet_searched`、`budget_insufficient_for_required_route` 均不能冒充真实 gap。

本次仍不授权全面索引重建、Embedding／reranker 微调、无界外源采购或模型 full-chain。实现只处理审计已证明的最早断点；后续新证据可以调整包内顺序，但必须先更新 Project OS 并说明业务影响。

## 4E. 2026-08-17 S1 最终完成定义与完整真实链顺序更正

Owner 进一步更正：4D 的 CoverageState、候选账本、binding 和 capture-bound promotion 只是 S1 的第一修复切片；DELL／MU／NVDA 只是用来测试切片和整条 S1 链的案例。不能在三个案例局部可用后直接写成 S1 结束，也不能跳过 OCR、解析、chunk、对象化、索引、召回、重排和金融精排等上游环节，只验收 Evidence Pack 终态。

后续 S1 计划改为“责任分层、纵向交付、持续集成”。S1-A–S1-J 只用于定位最早责任层，不能作为十个按顺序各自收口的小项目。每个 release slice 都必须复用当前唯一 canonical artifact spine，从真实／冻结 source 或 Evidence Need 贯穿到 CandidateDecision、CoverageState、Evidence Pack 和 Workbench／冻结 consumer probe；未改层参加回放，不能在最后一次性拼装。

1. **spine／覆盖矩阵／评测程序基础、VS1／VS2／VS3 与三案例 VS4 Runtime 迁移已完成，隐藏资格集仍开放。** machine-readable spine、A–J 矩阵和开发资产已进入当前 R19 Runtime；DELL／MU／NVDA 都已消费 capture-bound successor lineage，但它们仍是开发／回归案例。valid／frozen test／heterogeneous holdout 必须另行预注册，不能把已观察案例改名为隐藏集。R16 的 result-local ref 门继续有效；旧 R14／R15、VS3 v1.6／v1.7 及 VS4 各失败 query／ranking／materialization attempt 均保持历史证据，不被原地改写。
2. **VS1：当前数字原生官方资料纵切已达到 `vertical_slice_integrated`。** DELL pricing/mix 真实路径产生 55 个 canonical envelopes，当前 Workbench 与 Evidence Pack 消费同一 lineage；6 个候选形成 2 accepted／4 needs-review，另有 2 条 reviewed Evidence 未召回、3 条 gap 因补源未执行而禁止认定公开信息不存在。0 网络、0 模型、0 新晋升、0 index rebuild；当前 successor 只补齐可解引用 payload，不改变业务结论。
3. **VS2：复杂文档与数表纵切已达到 `vertical_slice_integrated`。** IFX 2025 官方年报仅作 train-internal 开发样本，不加入产品案例。当前 parser／object 路径保留 5 个复杂表区、56 个 metric-row、1 个脚注、1 个重述上下文和 1 个真实跨页关系；官方页栅格 OCR mutation 保留预注册 material anchors，但没有自然扫描资料资格。4 个 reviewed 目标只有 1 个进入前 20；分部总计行、脚注和跨页续表对象都存在但未被召回，因此最早未闭合层已转到 VS3。S2 sibling 保持 typed gap，任何表格数字均未获得 NumericFact 权威。
4. **VS3：多路线检索与金融排序纵切已达到 `vertical_slice_integrated`。** 33,085 个对象上的有界候选池召回 15/15 开发正例，路线顺序扰动稳定率 1.0；金融审阅前十为 15/15、确认 hard negative 为 0。VS1 两个历史对象均可追溯，VS2 四个复杂目标均进入最终审阅面。1,912 个候选全部持久决策，0 hard-negative/source-only false accept。BGE／Qwen／typed route 与 reranker 仍是组合输入，不存在单模型产品晋升；Candidate、Evidence、NumericFact 权限继续分离。
5. **VS4：DELL／MU／NVDA 三案纵切已完成。** 三案均走完 residual proposition→route→CUDA candidate→Evidence Role→capture-bound decision→successor Pack→Coverage delta→Workbench，未增加 ticker 专用核心分支。DELL 为 `22 Evidence / 14 gaps`，MU 为 `11 / 15`，NVDA 为 `19 / 13`；旧宽 Evidence 分别退役 3／16／14 条，新增精确 claim 5／11／19 条，gap 窄化 1／2／3、关闭 0，MU 另增加 2 个 S2 bridge typed gap。三案 Candidate／NumericFact 越权与 hard-negative false accept 均为 0。通用 reranker 仍不合格，当前开发纵切由确定性金融短名单提供候选视图；它证明当前 capture 上的有界二轮补证，不等于开放网络补源或 S1 通过。
6. **持续集成而非最终集成。** 每个切片合并前必须同时通过局部门、相邻合同门、真实纵切门、业务影响门、跨案／错期／mutation 非回归和 artifact 迁移／回滚门。局部只记 `component_engineering_pass`；贯穿当前消费者才记 `vertical_slice_integrated`。任何 parser／chunk／index／ranker 变更至少重跑一条 golden vertical replay。
7. **VS5：独立 S1 资格。** DELL／MU／NVDA 只作开发／回归；已观察 ORCL／ASML／ANET 不作最终隐藏集。当前 10/10 只代表每个命题至少有一条有效目标进入前十，仍有 4 个 reviewed positive 未进入 candidate union；因此 VS5 必须另测 all-positive material-facet coverage。最终使用预注册新异质留出，逐案通过来源、OCR／parser、chunk／对象、query／route、candidate ceiling、recall／rerank、金融精排、Evidence 晋升、Coverage／gap、下游 ceiling、稳定性／效率硬门与性能门。所有向量／Cross-Encoder 计算只允许 CUDA／FP16，CUDA 不可用即 fail closed，不得以 CPU 回退制造不可比结果。
8. **达到 `S1_qualified_stable` 后才进入完整真实链。** 当前 Runtime／Workbench 可观测、确定性 replay 稳定且无 case-specific 分支后，才运行 `用户问题 → S3 → S1 → S2 → S3 报告 → S4`。此前只允许明确标记为 deterministic、shadow、node canary 或 diagnostic 的局部验证。

S1 结束的必交付物不是一张指标表，而是：一份当前权威标准范式；一套可执行、可版本化的主线实现；一组带 train／valid／frozen-test 边界的 gold／hard-negative／mutation 评测资产；一份逐层资格报告；Workbench 运维／审计消费者；以及对未通过项和真实外部边界的 typed closeout。任何单一 Recall、MRR、网页数、Evidence 数或案例报告均不能替代；“每个问题至少命中一条正例”也不能替代“所有 material facet 的已审正例覆盖”。

独立评测源：`docs/eval/FIN_0_1_3_S1_INDEPENDENT_DATA_RETRIEVAL_AND_EVIDENCE_READINESS_EVALUATION_STANDARD_20260817.zh-CN.md`。S1 当前状态为 `VS1_to_VS3_and_three_case_VS4_vertical_slice_integrated / VS5_all_positive_and_independent_qualification_pending`，不授权 full-chain product qualification。

## 4F. 2026-08-18 VS5 资格人口与 CUDA 执行边界

VS1–VS4 的当前开发能力不再扩大。VS5 已预注册 COST temporal、JPM／CAT frozen test、NVO／SHEL／0700.HK heterogeneous holdout；所有案例在活动代码／评测中此前均未出现。DELL／MU／NVDA 与 ORCL／ASML／ANET／IFX.DE 只做开发／回归，禁止改名为隐藏资格。

后续顺序固定为：提交预注册时间边界 → official capture-first 来源获取 → evaluator-only gold 与 runtime input 物理分离 → valid temporal → 配置冻结 → frozen test／heterogeneous holdout 各一次 → 双 clean replay／Workbench consumer → S1 逐门资格报告。test／holdout 结果可用于归责，不能用于同轮调阈值后重跑追认。

向量、dense／multi-vector 和 Cross-Encoder／reranker 一律 CUDA FP16，CUDA 不可用即失败，不允许 CPU fallback。CPU 只承担 BM25、SQL、分词、硬过滤、账本和确定性编排。该要求不能替代 all-positive／material-facet／required-role、Evidence 权限、gap 资格与自然扫描等产品硬门。

## 4G. 2026-08-18 COST valid-temporal R1／R2 失败与停止线

COST R1 是当前 VS5 的第一次正式 valid-temporal 候选资格。它通过 CUDA／FP16、exact-once、capture／对象存在性和执行合同门，但产品质量未过：5 个命题 any-hit 为 `0.8`，20 个已审正例只命中 12 个，material-facet／required-role coverage 均为 `0.642857`；尤其同口径销售比较为 `0/4`，跨期变化为 `2/5`。全部 20 个目标对象都已在官方对象库，因此不能归因为公开信息缺失、模型没有调用或 GPU 执行失败。

最早责任层是 S1-C／S1-G：命题级业务词被通用 facet 稀释，同口径年份没有形成候选组，有限审阅头又被重复的泛化会计与风险文本占用。现已建立 versioned v2 successor，将 typed request、精确未映射业务词、同口径跨期关系和 facet-balanced review 编入同一候选合同；旧 v1 代码、输入和 R1 失败保持不可变。零调用全仓结果为 `629 passed`，只记 `engineering_pass`，没有改动当前 Evidence Pack／Workbench 产品指针。

预注册明确允许 valid-temporal 最多两次执行，因此此前“必须先增加新 temporal case 才能复验”的建议过严，现已纠正。R2 已按 exact-once 完成：5 个命题、113 个命题级 need、每个 reranker 1,440 对，learned execution 全部为 CUDA／FP16，0 CPU vector fallback／network／generation model／retry。分离评价使用原 reference 和门槛，结果由 R1 的 12/20 提升到 15/20；any-hit、material facet 和 required role 通过，但 all-positive object recall 为 `0.75 < 0.90`，故仍失败。

剩余五条 miss 不是同一问题：汽油替代解释、毛利表格和同口径现金流表格均排在第 21，说明单对象 top-k 没有保证完整研究材料组；另外两条会员经营对象并不属于该 EvidenceRequest 冻结的 revenue／gross-margin／operating-cash-flow metric 集，说明 provisional reference 与请求存在待人工裁决的不一致。两次 valid-temporal 已消耗，禁止 COST R3 和隐藏集执行。下一步先冻结 request-bound evidence-set／temporal-pair 评测合同，在开发／回归案例验证后预注册新的 unseen temporal valid case；R1／R2 历史分数不改写，S1 与 FIN 0.1.3 均未通过。

随后一次范围过宽的仓库搜索披露了现有 JPM／CAT 和 NVO／SHEL／腾讯 hidden reference 的部分标签；没有 hidden run 或据标签调参，但盲性已经破坏。现有 hidden 文件保留不可变，只可在 Owner 后续决定后作为 disclosed regression，不能再承担 FIN 0.1.3 泛化资格。replacement qualification 必须使用 Git 外的受控 label store 和独立 adjudication；这属于 S1 评测程序修正，不创建产品新版本，也不允许绕过新 valid 直接进入 S3。

## 4H. Request-bound Evidence Set 零调用合同与当前剩余门（2026-08-18）

材料组 successor 已完成 `contract_translated_and_development_fixture_proven`：运行前 plan 只接受请求公开的 case／entity／metric／product／facet／role／period；候选审阅先保留 direct／counter／bridge／context／同口径 temporal bundle，再按原排名补满；错误公司候选不进入本案审阅；plan 和 selection 均有内容摘要；事后 reference 必须与 plan requirement IDs 和 digest 完全一致。DELL／MU／NVDA／COST 四种 synthetic 业务形态共 10 组通过，同一核心无 ticker 分支；mutation 和全仓 `646 passed`。

该结果尚不是 current Runtime 纵切。下一步先做 COST reference consistency 的 qualified-human review pack，再补当前 candidate metadata→material group adapter 和自然 ResearchBlueprint→material requirements 编译入口；随后用当前开发纵切回放，才允许预注册新的 unseen temporal valid。现有 COST 禁止 R3，已披露 hidden 资产禁止作为 blind，S1 与完整真实链继续 blocked。

## 4I. Material Evidence Runtime v1.1 回放与下一责任层（2026-08-18）

当前 candidate metadata→material group adapter 与统一零调用回放已经完成，不再停留在 synthetic fixture。v1.1 保留 facet／role／metric／product／period／basis 的相关绑定，支持非跨期的集合轴覆盖，并把材料 reservation 放在普通 review top-K 之前；旧 v1.0 合同和历史 COST R1／R2 不改写。

四案真实已保存候选回放共覆盖 18 个请求、40 个材料 requirement，全部材料组可完整保留且排列稳定。这个数字不能直接写成质量通过：MU 4／4、NVDA 6／6 请求的当前范围可由 deterministic contract 完整解释；COST 只有 2／5、DELL 0／3。其余请求包含会员价值、可比销售驱动、毛利压力、AI 服务器客户集中、营运资金机制和上游封装约束等复合研究主题，fallback 不具备替用户决定硬产品／机制边界的权限，已留下 `explicit_blueprint_required_for_full_product_scope`。

因此下一项不再继续改 ranker、扩大 review_k 或为 DELL／COST 添本体词。当前最早责任层是自然 `ResearchBlueprint → MaterialEvidenceRequirementPlan v1.1`：让上游根据真实研究问题明确 material scope，再调用现有 S1 selection；随后才做 EvidenceDecision／Gate、S2 数值关系和 Pack Readiness 回放。并行治理项仍是 COST qualified-human request／reference 一致性签署，以及新的 Git 外 replacement blind program。任何一项未完成前，`S1_qualified_stable=false`、现有 COST R3／失盲 hidden execution／完整产品资格链均保持禁止。

## 4J. 自然材料范围与当前产品消费者（2026-08-18）

自然材料范围已实现为 provider-neutral 的两步产品合同，而不是 DELL／COST 专用 Prompt：首次 Workbench 受控计划只使用确定性范围；无法完整分类时返回需要模型解释的请求索引和 plan digest。自然节点只能选择 request-visible metric／product／role／period 枚举，不可见候选、对象、qrel、reference 或答案 URL；本地随后校验全请求覆盖、hard product／metric／role 轴、固定分类和 digest，并把通过结果送回同一 Hybrid Candidate Runtime。

材料保护现发生在完整 BM25＋Qwen 候选并集之后、来源配额和 review truncation 之前。只有 requirement receipt 明确绑定的候选可硬保留；其他材料候选仍受来源配额，避免提高材料覆盖时退化成单一来源堆叠。旧调用者不提供 material contract 时保持兼容。

DELL 当前真实受控计划已证明产品消费者 seam：8 个请求均有候选，S2 同步返回 58 个 NumericFact，但 8 个复合研究范围均诚实要求自然 scope。这个结果只授权一次候选盲、0 网络、exact-once 的自然 scope canary；不授权报告、Evidence 自动晋升、COST R3、hidden 或 S1 资格。canary 通过后依次回放 CUDA 候选、CandidateDecision／Evidence Gate、S2 权威与 Pack Readiness，再决定新的 unseen temporal preregistration。

## 4K. 2026-08-19 Agent Runtime／反思／上下文连续性审计后的顺序

Owner 指出当前系统长期围绕单轮／伪多轮和确定性编译建设，尚未证明模型能在收到 Harness failure、证据不足或错误研究方向后反思并修改计划；长任务上下文压缩和各 Agent 独立研究能力也未进入统一 Runtime。全链审计确认当前真实形态是固定 workflow＋一次片段 repair＋不可变 successor，不是通用反思型 Multi-agent 系统。

审计轮只冻结架构和合同；当前 successor 已完成零调用 Runtime 基础实现。统一六合同继续以 v1.0 为语义基线，v1.1 增加 append-only `SessionEvent`、checkpoint 扩展和 resume receipt；它不改变 Evidence、NumericFact、Gap 或发布权限。

后续顺序修订为：

1. **S1 当前主线继续，不被 Agent Runtime 议题替代。** 先以人工／fixture typed requests、0 生成式模型证明 source、清洗、对象、query、召回、重排、Evidence Role／Gate 和 gap 归责。人也无法查准即为工具 failure；不得让模型补分。
2. **完成 S1 当前剩余门。** 来源资产对账已证明 MU／NVDA 所需当期官方披露在本地快照中；不再重复下载。后续只修复对象／query／recall／ranking／Evidence Role 的真实覆盖损失，完成 16 请求／22 条候选绑定的 qualified-human admission，并由外部隔离流程完成 replacement blind qualification。达到 `S1_qualified_stable` 前不做产品资格 full-chain。
3. **S0 零调用 Runtime 基础已工程通过。** append-only SessionEvent、六合同 validator、checkpoint／resume 和事件／状态 mutation 通过；不修改 Evidence、NumericFact、Gap 或发布权限。
4. **S1/S2/Verifier FeedbackReceipt 编译已工程通过。** 工具 failure、已有来源但未召回、Evidence admission、数值 gap／conflict 和 Verifier finding 已能分别回到最早责任节点；候选文本不因反馈而获得权威。自然 Agent 是否会消费反馈并改变计划仍待 S3 证明。
5. **S3 先做一个 DELL 单单元反思纵切。** 只给用户问题、Case／as-of 和工具权限；模型自行规划、执行、反思、提交受验证 PlanDelta／GraphDelta 并 Stop。固定 Pack 继续只作模型分析单测。
6. **再扩到五单元与 Lead。** Verifier finding 返回 owning cell，只重跑受影响节点；Skill／Graph 按角色、Objective、gap 和 Plan 动态最小加载并留下消费 receipt。
7. **最后做 MU、NVDA 和异质留出，再进入 S4/S5。** 泛化必须覆盖跨公司、跨行业、跨来源形态、跨期和不同 failure，不以相似案例或平均分冒充通过。

Skill／Graph 位于 Harness 与 Agent 工作模式的交叉层：Harness 管选择、版本、作用域、digest 和权限，Agent 负责实际使用方法和提出图关系增量；全部 Pack 固定注入、图边冒充事实或模型直接修改稳定本体均被禁止。

该顺序不意味着 S1 与 Runtime 必须完全串行。S1 独立资格可继续推进，S0 只允许零调用合同／事件骨架并行；任何自然反思 live 必须等其依赖的 S1/S2 工具响应达到当前任务所需资格。当前 `S1_qualified_stable=false`、`generalized_reflection_loop=false`、`context_continuity=false`、S3/S4/S5 均未通过。

## 4L. S1 人工可操作、admission／blind 门与 S0 反馈基础（2026-08-19）

- 24 个开发请求已形成无生成式 AI 的人工可操作预检；每条都有业务问题、失败类、最早责任和合法下一动作。
- 当前对象快照对账后，原认为需执行来源路线的 MU 4 条、NVDA 3 条已更正为“当期官方资产已存在，候选材料未被正确找到或定角”。新增官方资产请求为 0；这不说明 MU／NVDA 覆盖已通过。
- qualified-human admission 私有审阅包已编译 16 个请求、22 条候选—命题绑定，候选仍非 Evidence。外部 blind handoff 已准备，但案例和标签必须由当前实现上下文之外的角色隔离保管，尚未执行。
- S0 v1.1 及 31 条 S1／S2／Verifier FeedbackReceipt 已完成零调用回放；全仓 817 测试通过。这只关闭事件、恢复和失败路由的工程基础，不关闭自然反思、Skill／Graph 消费、S1／S3 资格或 release。

## 4M. Multi-Agent Preview 分析片段 checkpoint successor（2026-08-20）

- 六份 R3 Specialist 计划继续作为不可变成功前缀复用。R4 Research Lead 形成 9,932 字可见分析后在协调问题处达到长度上限；该结果保持 terminal failure，不能直接晋升为 Lead plan。
- 当前已实现一次 provider-neutral 分析片段续跑：受限 checkpoint 绑定原始 capture／digest 和章节完成度，FeedbackReceipt 只授权同一 Agent 补齐剩余协调问题、信息边界和停止条件，禁止重做已完成部分。
- continuation 最多一次；仍截断、缺字段、重复完成项或 checkpoint 漂移即停止。只有合并后的完整草稿才进入既有严格 submission，Harness 不补写观点。
- 该零调用工程门只授权一次 R5 live，不改变 S1 当前优先级和 S1／S3／泛化／人工／发布状态。后续 Multi-Agent 节点仍按数据基建、Harness、Agent 编排、模型和 Evaluator 分层归责。

## 4N. R5 完整分析 checkpoint 与 R6 submission successor（2026-08-20）

R5 已自然完成 Research Lead 剩余分析内容，但被本地 partial／missing 标记合同误拒绝。该 attempt 不追认为成功；其原始响应与 terminal result 保持不可变。最早责任层已在 S0 Harness 关闭：partial 原地补完与 wholly missing 标题物化分开校验，并由真实 capture replay 证明。

当前顺序只增加一个有界 R6，不改变 FIN 0.1.3 阶段规划：

1. 将 R4 fragment＋R5 continuation 固化为不可变 `AnalysisCompletionCheckpoint`；
2. 通过零调用 fake／mutation 和 Project OS scope gate；
3. R6 只执行 Lead 严格 submission，Lead 分析调用为 0；
4. submission 通过后，按既有 Preview 继续 Specialist workpaper、挑战／反馈、Evaluator 和条件式 Writer；
5. 所有结果继续按数据基建、Harness、Agent／模型、Evaluator 分层归责；
6. 不以 R6 的工程完成签发 S1、S3、泛化、qualified-human、S4 或 release。

若 R6 下游出现普通节点失败，保留 attempt 并只修最早责任层；不得因此重做已经成功的六份 Specialist 计划或 Lead 分析。只有产品范围、数据采购、模型职责或跨单元 L1 需要改变时才升级为项目级决策。

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
