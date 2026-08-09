# FIN 0.1.3 修复收口版范围与差量 S0–S5 计划

日期：2026-08-05；最近互校准：2026-08-08
状态：`FIN_0_1_3_active / S0_04G_current_next / S1_01_to_07_closed_S1_08_clean_deterministic_proof_pass_live_candidate_ceiling_pending / S2_experiment_complete_natural_correction_failed / S3_minimum_anchor_only_not_product_pass / S4_not_started_in_FIN_0_1_3 / S5_not_started / release_blocked / FIN_0_2_definition_unchanged`

> **2026-08-06 用户新增硬要求**：FIN 0.1.3 必须把研究内容输出质量作为 release-blocking 考核，不得再将 L3 的通用 Claim、弱综合、机械 Writer 或不可执行 WWC 降级为 nonblocking finding。八维绝对质量＋paired gain＋qualified human content acceptance 的正式标准见 `docs/eval/FIN_0_1_3_RESEARCH_CONTENT_OUTPUT_QUALITY_RUBRIC_20260806.zh-CN.md`。

## 1. 决策

FIN 0.1.2 在 S4-T08 扩大审计中证明了完整的工程链路形状、三案例产品投影、exact review 控制和大量不可变执行证据，但同时暴露出财务真值、证据覆盖、研究语义和 current 产品闭环仍未达到 FIN 0.1 PRD 的 release 定义。

因此：

1. FIN 0.1.2 不继续在 T08 内展开实现修补；T08 只负责完成审计、阶段归属和 honest-block handoff。
2. FIN 0.1.2 的 S5 只做一次 decision-only closeout：冻结候选、已知失败、成本和 rollback 边界，并明确 `release_not_qualified`；不在已知 RG2/RG3 失败时机械执行六轮发布证明。
3. 新建 FIN 0.1.3 作为 **FIN 0.1 最后一个专项修复与正式收口候选**。FIN 0.2 仍保持 Earnings Review Alpha 的原定义，不吸收本轮欠账。
4. FIN 0.1.3 仍使用 S0–S5 表达责任层和成熟顺序，但采用差量执行：继承 FIN 0.1.2 未受影响的 immutable evidence，只运行发生变化的阶段、依赖回归和最终 release gate。
5. 失败必须留在最早责任阶段；不得因为 S4 暴露问题，就在 Workbench、renderer 或 T08 末端加补丁掩盖上游缺陷。

> **2026-08-07 二轨重排**：三案 Gold dogfood 证明，继续把精力集中在固定九次 DeepSeek 调用的合同遵循，无法证明 PRD 所要求的 Agentic Search/Research。FIN 0.1.3 不升级版本、不推翻已完成的 S0–S3 工程资产，但把后续执行重排为：先在同一冻结 Evidence Pack 上隔离测量 DeepSeek 的分析与综合能力；再修复 MCP、当前外部来源与 Agentic Search；最后才让 DeepSeek 从检索开始完成端到端研究。工具缺陷不得记为模型缺陷，模型推理缺陷也不得通过扩大工具范围掩盖。

## 2. 扩大审计结论

### 2.1 数量

按共同根因合并、避免把每个字段或页面症状重复计数后，识别出 21 个修复包：

| 最早责任阶段 | 修复包数量 | 占 21 个修复包 | 核心结论 |
| --- | ---: | ---: | --- |
| S0 | 3 | 14% | 版本继承、持久状态、共享执行治理和金融语义测试基线不完整 |
| S1 | 5 | 24% | 财务期间真值、数值程序、来源覆盖、Graph 和检索质量未达到产品门槛 |
| S2 | 3 | 14% | 模型权限边界已较强，但模型合同与评测仍无法证明产品级研究能力 |
| S3 | 5 | 24% | 三 Cell、通用 Claim/WWC、弱 Lead/Writer 和计数型 Verifier 未达到 PRD Workpaper |
| S4 | 5 | 24% | current 产品仍是三案例投影，真实任务、执行、repair、review 和 burden 闭环不完整 |

合计 S0–S3 为 16/21，约 76%；S4 为 5/21，约 24%。S5 另有 RG1–RG5 五个发布门禁尚未执行，它们是验证义务，不重复计作根因修复包。

### 2.2 关键判断

- S4 不是大多数问题的根因层；S4 首次把前面阶段接成可见产品，因而集中暴露了早期缺口。
- DELL 的 `USD 23.931B` 被标为 FY2025 全年营收，实际是 FY2025 Q4 营收；现有 72 项相关合同测试仍全绿，证明当前测试主要覆盖 identity/cardinality/digest，而不是财务 duration 真值。
- 三案例均能形成 15 Evidence、3 Numeric、3 Cell、6 Claim、9 WWC 和 9 Artifacts，但 Claim/WWC/gap 高度通用，Graph 为 typed empty，报告主要是结构投影而非公司专属研究备忘录。
- current Workbench 已能只读展示、exact return/replay 和 authenticated NVDA review，但它还不是从新建 Case 到实际 repair 再到重新验收的完整 current workflow。
- T07-C 本地私有 SQLite 已存在一次 `accept_exact_version`，`qualified_human_review=true`、`bounded_NVDA_R3=true`、`release_qualified=false`；该状态尚未持久投影到 Project OS，属于 S0 状态一致性欠账，不推翻本地真实动作。

### 2.3 研究内容输出质量是硬门禁

FIN 0.1.3 的通过不再只看 Artifact topology、合同完整性、引用和页面渲染。DELL、MU、NVDA 最终 verifier-bound Workpaper/Report 必须分别通过八维内容 Rubric：公司与问题专属性、证据论证、Numeric 解释、因果机制、跨 Cell 综合、反方/gap、WWC 行动价值和 senior 决策可用性。

每案必须达到 `>=24/32`，Q1–Q7 无低于 2，Q1/Q2/Q3/Q8 各不低于 3，并由 qualified reviewer 单独签署 content acceptance。任何 material financial L1/L2 失败不可由内容分补偿；任何通用模板化内容也不可由工程绿灯、Claim/WWC 数量或 Owner workflow acceptance 补偿。

## 3. 21 个修复包的阶段归属

### S0：继承、状态与测试真值基线

| ID | 修复包 | 受影响 PRD | 0.1.3 通过条件 |
| --- | --- | --- | --- |
| `013-S0-01` | 建立 FIN 0.1.2→0.1.3 delta inheritance manifest；同步 T07-C 本地真实决定、Project OS、产品版本、S-stage、合同版本和 attempt 状态 | F04/F12/F15 | 同一 current truth 在 repo ledger、private store projection 和 UI 中不矛盾；不保存 credential |
| `013-S0-02` | 收口 shared Runtime admission ledger `RC-P36-115` 与 historical proof replay/mutable-SHA debt `RC-P36-128` | F04/F13/F15 | exact-once、replay denial、历史证据不可变和 current successor 回归共同通过 |
| `013-S0-03` | 建立金融语义 truth-oracle 测试分类，区分 shape/integrity、financial truth、analysis quality、product usability | F07/F08/F15 | 任何季度/全年、entity、unit、scale、formula 错配均能在 S1/S3 前失败；不得再以 72 个 shape test 代替金融正确性 |

> **2026-08-06 `013-S0-01` 完成**：新增 `fin_ia_0_1_3_repair_closeout_*` canonical namespace；按 SHA 将 47 个旧 `0.1.3` 资产分为 historical、superseded projection 和 8 个待 S0-02 复证的 version-neutral candidate。新 active-suite 只选择本轮 S0-01 gate，旧同名 proof 不再自动建立 current authority。T07-C 以只读字段白名单投影为 `1/4/1 + accept NVDA`，未保存 credential digest、session ID、reviewer identity 或 note。focused=`5 passed`，S0 整体尚未完成。

> **2026-08-06 `013-S0-02` 完成**：新增 repository-independent shared SQLite admission ledger，以 `admission_digest` 做原子占用键，并在任何 source/model/provider/business side effect 前 reserve；reservation 即 consumption，进程崩溃也不自动释放，并发竞争只有一个 winner，ledger 位于本次 disposable runtime 内会 fail closed，跨 runtime root 第二次消费 fail closed，terminal 精确绑定 Run/Attempt/result digest。FIN 0.1.3 current runner 强制注入该 ledger，旧 0.1.2 runner 只保留历史兼容钩子。RC-P36-128 通过 disposable issuance root 与 historical receipt / living source role 分离关闭，未重写旧 decision、receipt 或已消费 runtime。8 个候选复证后：reference-role v1.1、reference proof policy v3、typed environment parity 原摘要复用；reference-role v1.0 被 supersede；旧 runtime resource registry 因漏注册 1 个真实资源而拒绝并生成 31-resource canonical successor；三项旧测试仅复用两组逻辑，固定计数测试不再作为 current gate。S0-01+S0-02 canonical suite=`14 passed`，S0 整体仍需 S0-03 financial semantic truth-oracle taxonomy。

> **2026-08-06 `013-S0-03` 完成，S0 关闭**：新增四层 oracle，明确区分 `shape/integrity`、`financial truth`、`analysis quality` 和 `product usability`，并为每层绑定最早 owner；前两层阻断 S1/S3 输入，后两层在 S2/S3 与 S4/S5 继续作为 release-blocking 要求，不能互相补偿。三案 reviewed annual revenue 对照通过；当前 DELL `23.931B` 结果被稳定识别为 91 天 Q4 事实冒充全年，另检出 `source_filed_at=2026-06-23` 以本地快照时间代替真实 filing date `2025-03-25`。entity/issuer、annual/quarter/duration、unit/currency、scale/normalized value、formula 重算和四类时间角色 mutation 均可在下游前失败。canonical S0-01/S0-02/S0-03 suite=`29 passed`，model/provider/network/source/business=0，current 数据行重写=0。S0 的通过只说明门禁能正确发现问题；DELL 真值仍失败并归 `013-S1-01` 从最早 staging/mart 修复，模型与 full-chain 继续禁止。

### S1：数据、检索、Numeric 与 Graph 真值链

| ID | 修复包 | 受影响 PRD | 0.1.3 通过条件 |
| --- | --- | --- | --- |
| `013-S1-01` | 修复 DELL annual/quarter duration 与 `source_filed_at`/`as_of_date` 语义；从最早错误 mart/staging artifact 修复，不在 renderer 改数 | F05/F07/F13 | DELL/MU/NVDA annual、quarter、YTD、filing date 真值 fixture 全部通过；0 known material period mismatch |
| `013-S1-02` | 扩展 material Numeric 程序、公式和重算覆盖，避免每案只有三条 consolidated number 就宣称 F07 完成 | F07/F08 | 所有进入核心 Claim/表格的 material number 均绑定 entity/period/duration/unit/scale/source/formula 或 typed gap |
| `013-S1-03` | 补齐 official IR、SEC、PDF/redirect/parser fallback 和 source exhaustion 的 current 证明 | F05/F06/F09/F13 | 每个 required EvidenceSlot 有 accepted evidence 或 attempt-backed typed gap；request/response capture-first，零 false promotion |
| `013-S1-04` | 让 relationship/Product Graph 至少在有权威关系证据时形成 approved edge；无证据时继续 typed empty | F05/F06/F08/F13 | 正向 edge、无证据空态、跨案污染、无日期候选和错误实体 mutation 均通过 |
| `013-S1-05` | 建立 retrieval/evidence usefulness eval，而不是只数 accepted rows；覆盖 candidate ceiling、required-slot recall、来源多样性、证据利用率和冲突证据 | F05/F06/F08 | 预注册 gold slot/negative set；已知可达证据必须进入候选，失败必须归因到 router/parser/ranker 或外部 gap |

> **2026-08-06 `013-S1-01` 完成**：从最早 SEC CompanyFacts duration 分类修复，日期区间成为 annual/qtd/ytd/instant 的语义权威，`fp=FY` 与 10-K 不再把 91 天 Q4 洗成全年；Runtime 即使读取旧 staging 标签也会重算 duration，Gold Mart v0.2 以非破坏迁移增加 period/time 字段，SQL 仅选择截止日前 annual authority。`source_filed_at / published_at / as_of_date / snapshot_at` 已拆分：前两者来自来源、`as_of` 由研究请求绑定、snapshot 只表示本地物化。完整本地重建产生 10,146 Runtime rows 和 74,897 Mart rows；三案实际 SQL→Numeric 为 DELL `95.567B`、MU `37.378B`、NVDA `130.497B`，均 364 天且 filing date 与 reviewed oracle 一致。RC-P36-130 关闭。旧 0.1.2 Evidence Pack 与 acceptance 保持历史不可变；三个旧 byte/digest 断言因合法 changed source/data 被标为 event-time non-gating，不能更新旧证明冒充新 acceptance。S1 继续进入 `013-S1-02`，不调用模型/full-chain。

> **2026-08-06 `013-S1-02` 完成**：新增 versioned material Numeric policy 与本地确定性编译/校验器，直接消费 current Gold Mart 和同份 current 10-K 的比较期 instant staging。DELL/MU/NVDA 共形成 `23 base facts / 14 derived metrics / 8 typed gaps / 45 governed slots / 0 ungoverned`；公式覆盖 gross margin、operating margin、free cash flow、average-inventory days，并在 MU/NVDA 覆盖 capex intensity。DELL 的 current 年度公式现为 gross margin `22.2357%`、operating margin `6.5263%`、FCF `1.869B USD`、inventory days `25.32`，旧 0.1.2 以 Q4 revenue 计算出的 `88.797%/26.0624%` 不再进入 current authority。缺少的 server/ISG、HBM、Data Center product 级收入/利润及 PVM、可比营运资本变化均保留为 case-specific typed gap，`source_exhaustion_proven=false` 并交 `013-S1-03`，没有为了补齐数量虚构事实。S1-02 仅证明本地 Numeric 真值、公式可复算和 Claim/表格准入治理；未调用模型/Provider/网络，也未继承旧 R2/R3 或宣称 F07 产品完成。

> **2026-08-06 `013-S1-01/S1-02` 有界返工与 `013-S1-03` 完成**：S1-03 current official-source proof 暴露出一个更早的 truth 问题：S1-01 虽修复了 quarter/annual 误分类，但当时 staging 只到 2026-06-06，S1-02 又把 fiscal year 固定在策略文件中，导致截至 2026-07-26 的 DELL/NVDA 仍选择 FY2025，而非已经公开的 FY2026。该问题没有伪装成 S1-03 parser 缺陷；RC-P36-135 归回 S1-01/S1-02。targeted capture-first SEC refresh、Runtime/Gold successor 和 material v1.1 已将“截至日之前最新可用年报”编译为确定性选择规则，未来 filing 不可越过 as-of；当前三案年度营收为 DELL FY2026 `113.538B`、MU FY2025 `37.378B`、NVDA FY2026 `215.938B`。数值面形成 `25 base / 16 formula / 7 gaps / 48 governed`，再由官方 DELL FY2026 文档确定性提取 AI-optimized server revenue `24.683B` 与 ISG operating income `7.111B`，消解两条 gap，最终为 `27 exact facts / 16 formulas / 5 attempt-backed gaps / 0 ungoverned`。official-source R4 使用 shared exact-once admission，完成 `10 network calls / 11 accepted / 6 attempt-backed gaps / 0 model`；其中 9 条为三案 current semantic evidence，旧 DELL working-cap gap 已由结构化 AR/AP 变化 successor 取代。剩余 5 条仅为 MU HBM revenue/profit/PVM 与 NVDA product/accelerator revenue/profit；SEC archive 的 403 已 capture-first 保存，但不冒充 source exhaustion。JSON/HTML/PDF/redirect/parser failure、binary junk、false promotion 与 exact-once replay 均有 deterministic coverage。S1-03=`engineering_pass`；Graph、retrieval usefulness、Agent/研究质量、full-chain 和 release 仍未开始，下一项严格归 `013-S1-04`。

> **2026-08-06 `013-S1-04` 完成**：没有继续继承 0.1.2 的“三案 Graph 一律 typed empty”。S1-04 只读消费 S1-03 已捕获并解析的 issuer source 与 S1-02 current date authority，不新增网络或模型调用：MU 官方年报产生 Samsung、SK hynix 两条 `competitive_landscape` edge；NVDA 官方 FY2026 release 产生 Meta `strategic_partnership` 与 AWS、Google Cloud、Microsoft Azure、Oracle Cloud 四条 `official_deployment_event` edge，共 7 条 approved current edge。DELL 当前 bounded source 只有匿名客户、供应商和 channel 语言，因此保持 1 个 typed empty，且明确 `source_exhaustion_proven=false`。所有 edge 绑定本案 issuer、resolved target、explicit statement、publication/as-of、source capture、parser digest 和 claim boundary，并固定 `relationship_fact_only=true / financial_fact_authority=false`。跨案、错误实体、未来日期、capture/digest 漂移、node/source-lineage 重新封装、required statement 缺失和 false-empty mutation 均 fail closed。active suite=`70 passed / 1 historical event-time assertion deselected`。旧 0.1.2 Workbench 三案空图投影保持历史，不在 S1 偷改 UI；current Graph 的检索利用与产品投影分别归 S1-05/S3/S4。S1-04=`engineering_pass`，下一项 `013-S1-05`。

> **2026-08-06 `013-S1-05` 完成，S1 关闭**：usefulness audit 没有把 S1-03 的 `9 semantic accepted` 原样当真。原始 statement 复核发现 DELL demand 是 forward-looking/risk-list 命中、DELL counterevidence 只指向 SEC risk filing、MU counterevidence 是目录；历史 R4/capture 不改写，零调用 semantic successor 形成 `7 useful accepted / 2 honest typed gaps`，其中 DELL demand 与 NVDA realized counterevidence 保留 gap，RC-P36-136 关闭。旧 BM25 snapshot 虽有 `89,112` records，却缺 DELL/NVDA latest annual（`0/108/0`），且部分 stale lexical row 排在 current authority 前；FIN 0.1.3 因此禁止把旧 index 当 current authority，改由 semantic successor＋current material Numeric＋DELL official exact numeric＋S1-04 Graph 编译 governed retrieval pack。9/9 query terminal、26/26 required candidate recall、per-query ceiling 8、false promotion 0；三案 value query 均有至少 2 个 source URL，其他单源 query 显式记录 exception，Graph 永不成为 financial authority。RC-P36-137 对本三案由 current pack 关闭，通用主索引增量刷新未被伪装完成。active suite=`76 passed / 1 historical event-time assertion deselected`。S1=`pass_closed`；Agent 消费、动态研究计划、八维内容质量、产品验收和 release 仍为 false，下一项仅进入 `013-S2-01`。

### S2：模型表面、合同与代表性评测

| ID | 修复包 | 受影响 PRD | 0.1.3 通过条件 |
| --- | --- | --- | --- |
| `013-S2-01` | 保留 alias/enum/local truth ownership，同时允许模型输出公司专属机制原子，禁止合同把所有结果压成通用句式；修复 prompt metadata compaction 把 int/bool/decimal 全部字符串化的 typed-contract 漂移 | F08/F10 | prompt/schema/validator/fake/selector 同源；公司专属语义可表达，数字/日期/identity 权限不回退；允许字段的 native scalar type 在 Agent request 中保持一致 |
| `013-S2-02` | 将模型评测从 MU 三 family 小 canary 扩展到代表性的 evidence→Claim→Lead synthesis node；区分模型能力、合同限制和上下文缺陷 | F08/F10/F11 | changed family/node 的自然输出通过预注册 rubric；不以一个全局模型 winner 覆盖所有 family |
| `013-S2-03` | 收敛 55k–58k input 对约 3k output 的低产出上下文结构，去重 role view，保留必要反证和 lineage | F04/F08/F15 | node-level 信息利用率、容量、成本和质量同时满足预算；不得通过隐藏证据获得绿色容量 |

> **2026-08-06 `013-S2-01` 完成**：入口审计确认旧合同的问题不只是 `line_item_count` 类型错误。旧 0.1.2 虽称 judgment atom，Provider 仍可自由写 `direct_answer_atom/counterevidence_atom/boundary_atom`，因此结构化外观不能阻止三案通用套话。本轮先从共享 `specialist_llm._compact_pack_metadata` 根因修复 RC-P36-134：显式字段类型策略由 prompt projection 与 validator 共用，int/bool 保持 native type；ratio/score Decimal 仅按显式 decimal-string 合同编码；未知 numeric/bool 不再静默转字符串。随后只读消费 S1 current governed pack，将三案三个代表性 Cell 编译成 9 个公司专属 decision question/method request，绑定 26 个 Evidence alias、2 个 typed-gap alias、18 个公司专属 mechanism choice 和 18 个 WWC choice。Provider schema/fake/validator/selector 均来自同一合同源，输出面只允许 closed enum 与 request-local alias，禁止 raw numeric/date/identity/ID/free narrative；本地继续掌握事实值、日期、身份、lineage 与最终渲染。focused=`11 passed`，active S0–S2 suite=`87 passed / 1 historical event-time assertion deselected`，模型/网络=0。扩大 legacy Specialist suite=`60 passed / 3 failed`，三项失败均发生在 compactor 之前：repository Product Intelligence autoload 抢占单测显式 Evidence，造成 source-family 与 row-selection 预期漂移；登记 RC-P36-138 并归 S2-02 上下文 precedence/isolation，不在 S2-01 关闭真实 autoload 来换绿。该完成状态是 `contract_translated + fixture_proven`，不是 node runtime consumption 或 DeepSeek 能力证明；固定三 Cell 只是 S2 代表性面，不替代 S3 的 10–20 Cell 动态 DecisionSurface。下一项进入 `013-S2-02`，先明确 explicit current governed pack 优先级，再做代表性 evidence→Claim→Lead node 注入与评测。

> **2026-08-06 `013-S2-02` 零调用部分完成**：RC-P36-138 已通过 hermetic low-level builder 语义关闭：没有 Research Lead 显式决策时，直接构建 Agent data view 不再读取 repository/environment Product Intelligence；生产 LangGraph 仍保留 Research Lead 明确开启 autoload 的路径。扩大 Specialist 回归恢复为 `63 passed`，并证明相同显式 Evidence 在 repo 与空工作目录形成相同 digest。S2-01 九个 request 已被代表性 runtime 消费，物化 `9 Claim / 3 Lead synthesis`，而非继续停留在 registry/fixture；Claim、execution、Lead 均有内容 digest 和 S1/S2 lineage。三类自然 canary 已在执行前冻结 request、rubric、硬失败与 `3 calls / 0 retry / 0 fallback` 预算，但尚未 admission 或调用模型。canonical suite=`161 passed / 1 historical event-time assertion deselected`。因此 S2-02 当前为 `zero_call_node_consumption_pass / natural_canary_pending`，不能提前标记完整完成，也不能把本地 synthesis 当作最终研究内容质量。

> **2026-08-06 `013-S2-02` 完成并关闭**：clean-head fresh admission 已由 shared ledger exact-once 消费；DELL demand、MU value/profit、NVDA bottleneck 三项 DeepSeek Pro 自然输出均为单次 transport、`finish_reason=stop`、预注册五维 Rubric `10/10`。总计 `3 calls / 3 raw capture-first objects / 3 local Claims / 0 retry / 0 fallback / 0 business promotion`，`3093 input / 362 output / 3455 total tokens`。三项仅选择 request-local alias/enum；DELL、NVDA 未把 gap 洗成正面结论，MU 未把 consolidated/DRAM 总量冒充 HBM economics。该结果证明受限代表性 Specialist 合同的自然遵循，不等于自由叙事能力、最终研究质量或产品通过。private raw request/response 留在 Git 外，可公开 successor 只保存选择、Claim/capture digest、usage 和边界。S2-02=`pass_closed`，下一项为 `013-S2-03` context yield/capacity；不得直接跳到 full-chain。

> **2026-08-06 `013-S2-03` 零调用工程通过、自然复证待执行**：9 个代表性节点的模型可见输入由 `40,326` 字符降至 `24,289`，缩减 `39.7684%`；Evidence、typed gap、mechanism、what-would-change alias 保留率均为 `100%`。模型不需要的 candidate/slot/gap ID、digest 和 S1 lineage 改由本地 sidecar 保留。canonical successor=`191 passed / 1 historical event-time assertion deselected`。因模型可见 bytes 改变，阶段仍需一次最高负载 NVDA demand compact-context natural reproof；不得扩大为 full-chain，也不得把容量工程结果冒充 S3 研究内容质量。

> **2026-08-06 `013-S2-03` 自然复证通过并关闭**：clean/synced commit 上只执行预注册最高负载 NVDA demand compact-context request，DeepSeek Pro `1 call / 1 transport / finish_reason=stop / 927 input / 149 output / 0 retry / 0 fallback`，输出仅含本案 alias/enum 并成功物化本地 Claim。canonical successor=`195 passed / 1 historical event-time assertion deselected`。S2-03=`pass_closed`，下一项为 `013-S3-01` 动态 DecisionSurface 入口审计；S3 的内容质量责任不回塞 S2。

### S3：研究计划、判断、Lead、Writer 与 Verifier

| ID | 修复包 | 受影响 PRD | 0.1.3 通过条件 |
| --- | --- | --- | --- |
| `013-S3-01` | 把 current exact product 从固定三 Cell 升级为动态 DecisionSurface；Anchor 覆盖 10–20 Cell、目标 12–16 和六个必选 family | F03/F08 | reviewer 可审阅/裁剪计划；每 Cell 有问题、owner、slot、stop rule 和 WWC，不硬编码标题 |
| `013-S3-02` | 修复通用 Claim、重复 gap、9/9 通用 WWC；形成公司专属机制、证据边界和可观测触发条件 | F08/F10 | 每个核心 Claim 包含本案对象、机制、证据/数字或 gap；WWC 有指标、方向、时间/阈值和下一证据路线 |
| `013-S3-03` | 让 dependency、conflict 和 gap 成为真正的跨 Cell 综合，而不是复述 supported/cannot infer 状态 | F08/F10 | Lead 对冲突给出 resolve/defer/block 理由；gap 有影响、优先级、owner 和 stop condition |
| `013-S3-04` | 提升 Workpaper/Writer 的产品、财务、客户/供应链、竞争、资本/price-in、估值边界、风险和 counter-thesis 内容 | F08/F11 | 报告能回答“结论、为什么、反方、缺什么、什么会改变”，不是六个 atom 的排版投影 |
| `013-S3-05` | 重做 Verifier/paired rubric：完整性 gate 与研究内容质量硬门禁分离，正式消费八维 Rubric | F07/F08/F10/F11/F15 | DELL period 错误必须 L1 fail；三案逐案达到 `>=24/32`、核心维度下限、material paired gain 和 qualified human content acceptance；通用 Claim/WWC 不得凭数量获得 L3/L4 pass |

> **2026-08-06 `013-S3-01` 工程通过**：current S1 governed pack＋S2 公司专属研究合同＋case delta 已编译为 DELL `13`、MU `12`、NVDA `13` 个动态 Cell，三案均覆盖 P36 六个必选 family。每 Cell 均有本案问题、owner、EvidenceSlot、stop rule、WWC、dependency 和 current/planned evidence binding；DELL/NVDA 的附加 Cell 由真实 typed gap 触发，并非固定标题。Reviewer inspect/prune/split/add/return 和 immutable revision 已零调用证明，material numeric sanity、risk/counterevidence、Writer boundary 不可静默删除。shared composition 遗漏 WWC 投影的根因已修复。current suite=`207 passed / 1 historical assertion deselected`，model/provider/network/source/business run=0。S3-01 只达到 `engineering_pass`，不等于 12–13 Cell 已产生高质量判断；下一项为 `013-S3-02`。

> **2026-08-06 `013-S3-02` 工程通过**：九个代表性 Claim 已形成公司、机制、证据边界、Numeric 或 typed gap、选择权威和 lineage 完整的 Claim Card；12 个 Numeric、2 个 typed gap 被本地精确绑定，13 条已选 WWC 全部具指标/事件、方向、时间窗、阈值和下一证据路线。既有 exact-once natural choice 只有 4/9，其余 5/9 明确为 fixture-only；29 个新动态 Cell 明确为 planned/no-claim，没有制造结论。S3-02 未改变模型 alias/enum 合同，不重复付费 canary。current suite=`214 passed / 1 historical assertion deselected`；下一项为 `013-S3-03`，full-chain 与内容验收仍禁止。

> **2026-08-06 `013-S3-03` 工程通过**：三案各形成 1 条跨 Claim mechanism dependency、1 条带 tension/disposition/reason 的 conflict，合计 5 条具 impact/priority/owner/stop/next-route 的 gap；typed gap 与 Claim-boundary gap 分离，不再复述 supported/cannot-infer 状态。三案 natural Claim coverage 分别为 1/3、1/3、2/3，故 synthesis 全部 fixture-mixed，冲突均 defer；fixture 假 resolve 会 fail closed。29 个 planned/no-claim Cell 未被综合。current suite=`219 passed / 1 historical assertion deselected`，additional canary=0；下一项为 `013-S3-04`。

> **2026-08-06 `013-S3-04` 工程通过**：三案已形成 no-source Workpaper/Writer decision-ready 内容合同，每案固定覆盖 8 个研究 lens，并逐 lens 回答结论、原因、反方、缺口和改变条件；共 `24 lens = 21 bounded judgment + 3 explicit research gap`。现有 Claim、精确 Numeric、Lead dependency/conflict/gap 与 observable WWC 被连接为公司专属内容；没有 Claim 的资本/price-in 或竞争维度明确不作结论，29 个 planned Cell 没有被当成 finding。由于当前三案仍是 4 个 natural choice 加 5 个 fixture choice，三个预览均为 `fixture_mixed_engineering_only`，不是产品交付；Provider-visible Writer input 未激活，也未新增 paid canary。current suite=`226 passed / 1 historical assertion deselected`；下一项为 `013-S3-05`，先实现八维 Verifier/paired 硬门禁，再决定唯一正式 full-chain。

> **2026-08-06 `013-S3-05` deterministic gate 工程通过**：八维逐案 ScorePacket 已正式区分 L1/L2 与 L3，要求总分 `>=24/32`、核心维度下限、dimension-specific reason refs、最强反方/跨 Cell 裁决/可执行 WWC。paired 必须同 input head、不同 Run/Artifact 且至少三维实质增益；qualified-human content acceptance 与 workflow/identity acceptance 分开，Codex/自动化不能代签。三份 fixture-mixed 预览均在评分前拒绝，正式分数与通过数为 0。

> **2026-08-06 formal Anchor R1 与 Evidence-role v2 处置**：R1 在第一个 DELL demand 节点返回合法 JSON，选择一条收入观察事实，同时诚实保留 `cannot_infer` 与 demand-durability gap；旧合同因把 `support_aliases` 等同 thesis support 而拒绝。R1 保持旧合同下的失败证据，不能追认。S3 successor 已改为“模型选择观察，本地分配证据角色”，把 cannot-infer 下的观察归为 `boundary_only`，不允许成为 thesis support。零调用九节点 full-fake 与 mutation 已通过，但模型可见合同发生变化，因此下一步先做一次 DELL demand 单节点自然 canary；只有 canary 证明新字段合同可遵循，才另行裁决九节点 replacement。该处置不重开 S2、不改变 FIN 0.1.3 产品版本，也不降低三案内容质量门。

> **2026-08-06 Evidence-role v2 单节点自然 canary 通过**：DeepSeek Pro 对 DELL demand 自然返回 `cannot_infer`、收入观察 `DELL_E01` 和 typed gap `DELL_G01`；本地将收入观察归为 `boundary_only`，没有 thesis-support 晋升。调用为 `1`，tokens=`738`，retry/fallback/Artifact=`0/0/0`。renamed schema 风险已关闭，因此只授权一次 fresh 九节点 v2 replacement；它仍必须首错停止，成功后才能进入三案质量评分，失败则不得自动 R3。

> **2026-08-06 formal Anchor v2 R2 失败并停止**：九节点 replacement 在第 5 个 MU value/profit 节点停止，前四项自然输出通过，后四项未调用。MU 节点返回 `cannot_infer` 并选择四条 consolidated/DRAM 事实，但上游 request 没有任何 gap option，因而空 `gap_aliases` 被本地 typed-gap 硬门拒绝。该结果没有证明模型能力不足；它暴露的是项目没有为 gapless request 编译本地默认“证据不足以回答当前问题”边界。R2 保持失败，R3 未授权。下一步只做零调用 local-default typed-gap 与失败 terminal raw-output 投影处置，不改 S2 历史结果、不降低 typed-gap 门。

> **2026-08-06 gapless-request 零调用结构处置通过**：只有在上游 gap option 为 0 且模型返回 `cannot_infer` 时，本地 compiler 才生成并绑定一个 request-specific 默认 typed gap；Provider 不拥有 gap 文案，已有 gap option 的漏选仍失败。R2 MU raw 输出已重放为 boundary-only observations 加本地 gap，九节点 full-fake 继续贯通。失败 terminal 同时新增 parsed raw output 与 normalization receipt，提升追溯性。该修复未改变模型可见 context，R3 仍需单独权限决策，不能自动执行。

> **2026-08-06 S3 formal Anchor readiness 工程通过**：入口审计发现旧 successor validator 冻结在 `4/9 natural + 5 fixture`，且缺 FIN 0.1.3 九节点 runner；已在 S3 原地修复，不改写 S0 历史基线。零调用 full-fake 已证明 `9 capture-first calls -> 9 natural Claim -> 3 all-natural Lead -> 3 all-natural Workpaper -> quality entry`，第 4 call fault injection 后 5 项跳过、0 retry/0 fallback、admission 二次消费 fail closed。current suite=`240 passed / 1 historical assertion deselected`。下一步仅在 clean/synced commit 上签发并执行一次 fresh DeepSeek Pro formal Anchor；真实评分、paired、人工接受和 S3 product proof 仍未成立。

> **2026-08-06 S3 formal Anchor R1 首错停止**：唯一 admission 在第 1 个 DELL demand request 后 terminal failed；transport/JSON 均成功，真实错误是 DeepSeek 同时选择 `cannot_infer` 与非空 support alias，违反 `s2_compact_output_cannot_infer_support`。只产生 1 capture，后 8 项跳过，0 retry/0 fallback。原 runner 将继承 `ValueError` 的语义异常误分类为 JSON invalid，immutable R1 不改写，successor classifier 已零调用修正。current suite=`242 passed / 1 historical assertion deselected`；不得自动签 R2，下一项是首个可信失败的 root-cause/replacement disposition。

### S4：current 产品工作流与真实 dogfood

| ID | 修复包 | 受影响 PRD | 0.1.3 通过条件 |
| --- | --- | --- | --- |
| `013-S4-01` | 把 current 三案例只读 projection 接回真实 Task Center/Case create/search/open、Objective 和 Plan 编辑 | F01/F02/F03 | 用户不编辑 JSON 即可创建、恢复和审阅 current Case；legacy/fixture 不冒充 current |
| `013-S4-02` | 将 current exact execution 与 cancel/resume/checkpoint/typed stop 连接；现有 legacy/fixture primitive 只作复用资产 | F04/F15 | 至少一次 current 中断恢复和局部 retry/stop 可回放，exact attempt 与 artifact lineage 不漂移 |
| `013-S4-03` | 把 `return_for_repair` 从 append-only 请求推进到实际 source/numeric/domain repair、重建、diff 和 closeout | F06/F09/F12/F13 | 至少一条真实 targeted repair 被执行并关闭，或以 attempt-backed stop 终止；Writer 不补源 |
| `013-S4-04` | 将 authenticated exact review 从 NVDA 单案扩展为三案一致流程，并把真实决定安全投影进 Project OS | F10/F12/F15 | 三案 review target/version/hash 一致；credential 不入 Git/telemetry；accept 不等于 release |
| `013-S4-05` | 真实测量 task completion、review burden、编辑量、失败理解和继续使用意愿 | F01/F12/F15 | 有预注册任务、计时、review edits、repair 次数和用户结论；不再用测试数代替用户价值 |

## 4. F01–F15 当前校正

| Feature | 当前诚实状态 | 最早主要修复阶段 |
| --- | --- | --- |
| F01 Dashboard / Task Center | legacy 能力存在；current 主要是固定三案例入口，未证明新建到完成 | S4 |
| F02 ResearchCase / Objective | typed Case/identity 可编译；current UI 与真实 live chain 未完整绑定 | S4 |
| F03 Plan / DecisionSurface | 三 Cell bounded product 可运行；不满足 10–20 Cell 和六 family | S3 |
| F04 Durable execution | exact-once/capture/terminal 很强；current 产品 cancel/resume/repair execution 未闭环 | S0/S4 |
| F05 Agentic Search | 三案 current governed retrieval pack 已达 9/9 query terminal、26/26 required recall、0 false promotion；旧 BM25 因缺 DELL/NVDA latest annual 被降为 non-authority，通用增量索引仍属后续能力 | S1/S2/S3 |
| F06 Evidence Workbench | current Evidence/Graph/Numeric 与 honest gap 数据面已关闭；Agent 消费和真实 evidence repair 仍未执行 | S1/S3/S4 |
| F07 Numeric / Fact audit | period 与 latest-available annual 真值已修复；三案 48 个 material slot 当前为 27 exact facts、16 formula、5 attempt-backed gap，0 ungoverned；current Claim/表格消费与最终 UI/产品验收仍未完成 | S1/S3/S4 |
| F08 Workpaper / Domain Judgment | 结构存在；内容通用、三 Cell、弱综合，不满足 PRD 深研 | S3 |
| F09 Gap / Repair Queue | typed request/replay 成立；actual repair loop 未成立 | S4 |
| F10 Lead Review / Writer Admission | 合同和 Artifact 存在；Lead semantic adjudication 偏弱 | S3 |
| F11 Internal Deliverable | renderer/preview/trace 工程可用；研究内容和产品可用性不足 | S3/S4 |
| F12 Human Review | bounded authenticated NVDA action 本地成立；三案与 durable projection 不完整 | S4 |
| F13 Provenance / Trace | 工程强项；错误上游事实仍可被完整追踪到错误结果 | S0/S1 |
| F14 Same-Case explanation | bounded demo/nonblocking；不作为 0.1.3 release blocker | S4 optional |
| F15 Quality / Release Feedback | quality surface 存在；RG1–RG5 和 honest release decision 未完成 | S5 |

## 5. FIN 0.1.3 差量执行规则

1. 每阶段先读取 inheritance manifest；若该阶段没有 changed contract、root cause 或下游依赖，可记为 `inherited_pass_no_execution`，不重复历史 authority/proof。
2. 已知问题直接进入修复和 deterministic regression，不重复“发现问题→单独处置→单独签权”的多轮流程。
3. 每个共同根因 family 最多一个合并实现包；同一根因的多个症状不得拆成无限 R 编号。
4. S0/S1 先于 S2/S3；truth ceiling 未通过时禁止模型或 full-chain 用于发现已知数据问题。
5. changed model contract 先做 node-level natural canary；三案例 full-chain 只在全部 deterministic gate 通过后执行一次正式候选证明。
6. FIN 0.1.2 exact runs 保持 immutable，可作为回归 anchor；修复导致 input/data/contract digest 改变后，旧 R2/R3 不能自动继承为新 candidate 的产品通过。
7. 新 L1 留在所属阶段修；不因为失败自动创建 FIN 0.1.4。只有 0.1.3 完整终止或产品范围再次实质变化，才讨论新版本。
8. S5 RG1–RG5 不采用差量跳过：只有最终 candidate 才执行一次完整 release qualification。

## 6. 0.1.3 S0–S5 最小程序

| Stage | 只做什么 | 明确不做什么 |
| --- | --- | --- |
| S0 | delta manifest、Project OS/private projection 对齐、shared admission/replay、truth-oracle test taxonomy | 不重跑未变化的全部 hermetic 历史包 |
| S1 | period/numeric/source/Graph/retrieval quality 修复与扩展 fixture | 不调用模型，不做报告润色 |
| S2 | changed contract、代表性 node canary、context economy | 不做三案例 full-chain，不重新比较所有模型 |
| S3 | dynamic DecisionSurface、semantic Lead/Writer/Verifier、八维内容质量硬门禁、一个 Anchor product proof | 不做 Workbench repair/UI 扩展 |
| S4 | current create→run→repair→review dogfood、三案 transfer、burden measurement | 不回修 S1/S3 缺陷，不新增 release feature |
| S5 | 一次 RG1–RG5；RG3 必须逐案通过研究内容质量，另含 rollback、成本、安全和 release/honest-block | 不在 gate 中临时补丁、降级内容标准或自动重跑 |

## 7. 版本边界

- FIN 0.1.3 是 FIN 0.1 Internal Alpha 的修复收口版本，不改变 FIN 0.1 的产品范围。
- FIN 0.2 继续是 Earnings Review Alpha；季度财报 workflow 的新增产品能力不能提前塞入 0.1.3。
- SaaS/Bank 只作为 universal archetype、period/metric policy 和 gap boundary 的结构回归；不在 0.1.3 建全行业 Sector Pack。
- 20-F、多币种和 PDF/redirect 可以作为 deterministic/adversarial portability fixture，不自动扩大正式三案例产品验收范围。

## 7A. 2026-08-07 三案 Gold dogfood 后的二轨执行重排

### 7A.1 为什么重排

三案参考研究与现有 S3 R3 的差异表明，当前最小 Anchor 已证明合同、exact-once、lineage 和基本 L1/L2，但没有证明完整产品研究能力：R3 只有 9 个模型选择、0 条自然 thesis-support、0 条自然 counterevidence 选择，另有 29 个 planned Cell 未研究。Codex 三案 Gold candidate 虽形成更完整的事实、机制、反方、price-in 和 WWC，但实际是“Codex supervisor＋产品本地数据/部分 MCP＋外部一手来源”的混合研究；当前 stdio MCP 仅证明初始化、工具注册和 market handler，SEC search/exact-ledger 仍有资源绑定或超时问题（RC-P36-140）。

因此不能把两者直接比较为“Codex 比 DeepSeek 强”或“DeepSeek 不会研究”。必须先隔离变量，再验证完整系统。

### 7A.2 两个实验严格分开

| 实验 | DeepSeek 可见输入 | 目的 | 不允许得出的结论 |
| --- | --- | --- | --- |
| A：同证据分析与综合 | 同一 objective、as-of、共享 Benchmark Evidence Pack、数值/来源 lineage；不开放检索工具，不提供 Codex thesis、推理、评分或修订 | 测量 Specialist、Lead、Writer、Verifier 的机制判断、反证、跨证据综合和报告能力 | 不评价 Agentic Search、MCP、抓取器或数据源覆盖 |
| B：端到端 Agentic Search/Research | 同一 objective、as-of、source authority 和预算；开放修复后的产品检索/MCP/外源工具，不提供 Gold 答案 | 测量问题分解、查询迭代、证据晋升、gap repair、综合、写作和停止能力 | MCP/source/parser 失败不得直接归因模型；supervisor 扶正后的结果不得冒充独立成功 |

Experiment A 的共享 Evidence Pack 必须包含 Codex Gold candidate 使用的重要官方事实与来源，但不得包含 Gold 的 thesis、机制综合、counter-thesis 结论、WWC 答案或分数。Gold scoring objects 保持隐藏；DeepSeek raw、supervisor correction 与 corrected candidate 分开保存。

### 7A.3 阶段仍是 owner，不再是机械流水号

| 新 ID | owning stage | 工作 | 通过条件 |
| --- | --- | --- | --- |
| `013-S2-04` | S2 | 冻结三案共享 Benchmark Evidence Pack、blind input、hidden Gold scoring objects 和泄漏检测 | 同案、同 as-of、同 source authority；事实可追溯；无 Gold 结论泄漏；Codex/DeepSeek 可见差异为 0 或显式登记 |
| `013-S2-05` | S2 | 执行 Experiment A：DeepSeek 在零检索下逐节点消费共享 Pack | raw capture-first；节点首个 material 偏离暂停；三案分别形成可评分 raw candidate，不用 supervisor 修订换取“自然通过” |
| `013-S2-06` | S2 | 形成 supervisor correction ledger 与模型能力边界 | 每个差异归因到模型分析、合同、证据或评分；决定哪些面留给模型、哪些由本地 planner/renderer/authority 拥有 |
| `013-S1-06` | S1 | MCP operational truth：registry parity、canonical resource binding、cold/warm start、handler phase telemetry、timeout/cancel/no-orphan | SEC search/exact-ledger/market 等目标 handler 均有有界成功或 typed failure；禁止无期限 stall |
| `013-S1-07` | S1 | 当前外部来源 runtime：SEC/IR/web/PDF/redirect/crawler/parser、capture-first、source admission 与 fallback | 三案能抓到并解析真实正文，不以 URL/metadata wrapper 冒充 Evidence；失败保留原始 capture 和原因 |
| `013-S1-08` | S1 | Agentic Search 质量评测 | 以 Gold evidence slots 检查 query revision、required recall、false promotion、currentness、source diversity、accepted/rejected/gap；三案均通过预注册门槛 |
| `013-S3-06` | S3 | 动态 Research Lead loop | Lead 可按 hypothesis、Cell、evidence gap 和信息增益增删/拆分/重排任务，不再固定 fan-out 或固定调用数 |
| `013-S3-07` | S3 | EvidenceRequest→operator→Evidence Pack→targeted repair 闭环 | 缺口能触发可执行查询、证据晋升或 typed stop；Writer 不补源；repair 有 diff、lineage 与关闭条件 |
| `013-S3-08` | S3 | 执行 Experiment B：DELL/MU/NVDA 端到端 DeepSeek Agentic Research | 每案保留 ToolUseLedger、raw/corrected 分轨、停止理由、成本和完整研究产物；MCP 与模型问题分账 |
| `013-S3-09` | S3 | 对隐藏 Gold 做正式八维、paired 与 qualified-human 内容验收 | 每案 L1/L2 通过、八维 `>=24/32` 及核心下限、实质增益、人工接受；旧九调用 R3 仅作 minimum control |
| `013-S4-06` | S4 | current Workbench 三案 dogfood | create→plan→run→pause/intervene→repair→resume→report→review 全链可操作；UI 显示来源/工具状态、未决 gap、supervisor correction 和 provenance |
| `013-S5-01` | S5 | 最终 RG1–RG5 与扩大回归 | RG1 工具/数据可靠性；RG2 自主研究与恢复；RG3 三案内容质量；RG4 用户/审阅负担；RG5 安全、成本、重放、回滚均有诚实结论 |

S0 已完成的继承、状态和四层 oracle 不重跑；原 S1–S3 已完成项不撤销。上述 successor 只处理 Gold dogfood 新暴露的能力缺口。执行次序按依赖而不是编号：`S2-04 → Experiment A(S2-05/06) → S1-06/07/08 → S3-06/07 → Experiment B(S3-08/09) → S4 → S5`。

> **2026-08-07 `013-S2-04` 完成并冻结**：DELL、MU、NVDA 的 Gold candidate 被重新编译为中性的 model-visible 事实卡，而不是从 Gold 报告中简单删结论。共享 Pack 固定 `3 cases / 10 sources / 33 evidence items / 12 derived numeric / 12 explicit gaps`；另有 evaluator-only `12 hidden targets`。model-visible blind input 与共享 Pack 的事实、数值、来源边界和 gap 精确相同；Gold thesis、机制综合、counter-thesis、WWC 答案、分数及 evaluator key/phrase 均不可见。两个可见对象与隐藏评分对象物理分目录，逐对象 digest、三案 identity、as-of、source publication date、numeric/formula 重算、跨案污染和隐藏证据 case-local binding 均 fail closed。focused=`10 passed`，current S1–S3 successor=`146 passed`；模型/Provider/网络/MCP=`0/0/0/0`。扩大历史命名回归为 `276 passed / 8 failed`，8 项均属于旧快照的固定资产计数、旧哈希、旧 0.1.4 next-action 或 latest-ledger 假设，不作为 S2-04 失败，也没有改写历史证据换绿。S2-04 只建立公平输入与评估隔离，不证明 DeepSeek 推理质量；下一项是 `013-S2-05` Experiment A admission authority decision，尚未签发模型执行权限。

> **2026-08-07 `013-S2-05` admission authority 暂不签发**：入口审计确认 S2-04 公平输入合格，但仓库不存在 Experiment A 专用动态 runner、节点输出合同、case-scoped exact-once capture/terminal、容量成本 envelope 和 raw/correction/corrected 写权限隔离。现有 S2 三调用 canary 与 S3 九次 compact Specialist Anchor 都不兼容产品级同证据实验，禁止直接复用。唯一 successor 实现固定为每案独立 admission：Research Lead 先动态规划 `6–8` 个研究单元，再逐单元 Specialist、cross-cell synthesis、Writer、Verifier，故每案 `10–12` 调用、三案最多 `36`，而不是三案合计 9 次。DELL→MU→NVDA 顺序执行，首个 material failure capture-first 后暂停当前案且不自动启动下一案；raw runner 只能写 raw track，不能读取 hidden Gold 或写 supervisor/corrected track。focused=`7 passed`，模型/Provider/网络/MCP/credential read=`0/0/0/0/0`。下一项仅实现 dynamic-node runner＋full-fake/preflight；通过后还需新的 admission authority decision，不能从本决定自动调用 DeepSeek。

> **2026-08-07 `013-S2-05` dynamic runner 工程通过与 fresh authority**：专用 policy/runner/entrypoint 已完成：Lead=`1`、Specialist=`6–8`、synthesis/Writer/Verifier=`1/1/1`，单案 `10–12`、campaign 最大 `36`；完整 Evidence/Gap 覆盖、identity/as-of、引用、数值、capture-first、shared-ledger exact-once、首错停本案/全 campaign 和 raw/correction/corrected/evaluator 分轨均 fail closed。逐调用累计每案 `200000 input / 30200 output / USD 0.18 estimated` 上限，retry/fallback=0。DELL/MU/NVDA full-fake=`30 calls`，8-unit=`12 calls`，S2 named=`95 passed`。fresh authority 无 material blocker，但只批准下一步在 clean/synced descendant 上签发 DELL 一份 admission；admission 存 Git 忽略的 restricted `.codex_runtime` authority root，避免自指提交。消费/exact-live/MU/NVDA 仍未授权，本项 model/Provider/network/MCP/admission=`0/0/0/0/0`。

> **2026-08-07 `013-S2-05` DELL exact-live R1 首错终止**：一份 fresh admission 已在 clean/synced `a3f2edf8…c1989` 上 exact-once 消费。DeepSeek Pro Lead 正常返回 6 个 DELL-specific research units，但在输入外提出若干 scenario/stop thresholds；同时项目 numeric classifier 对 `51.3B/24.4B` suffix、value＋percent unit 和自然 rounding 存在假阳性。运行按 `experiment_a_unbound_numeric_surface` 在第 1 次调用后停止，calls/captures=`1/1`，tokens=`3766`，估算 USD=`0.0035378`，retry/fallback/Artifact=`0/0/0`；Specialist/Lead synthesis/Writer/Verifier、MU/NVDA 和 hidden scoring 均未到达。RC-P36-141 归 S2：事实数字继续 hard authority，但 hypothetical planning threshold 必须 typed 分轨，suffix/unit classifier 必须零调用修复。本失败不创建新版本、不自动签 replacement，也不支持对 DeepSeek 整体研究能力作结论。

> **2026-08-07 `013-S2-05/06` DELL layered raw 与监督边界已形成**：replacement successor 已完成 Lead＋6 Specialist＋Synthesis＋Writer＋Verifier 的 `10/10` raw chain；typed schema 漂移未复发，但 raw 内容因“中个位数→4–6%”虚假精度、4/6 Specialist 无反证和 Verifier false-green 而失败。path-aware evaluator v1.1 重算为 `2 L1 / 1 L2 / 23 L3`，关闭 `10-K`、跨 section OCF/P-E 和 conditional threshold 层级误报，真实 L1 保留。DELL raw 记为 `complete_quality_fail`，不扶正为自然成功。为避免三案 benchmark 污染，DELL supervisor 模型纠错延后到 MU/NVDA raw 完成之后；MU 仅可进入独立 authority decision，并必须沿用冻结 model-visible contract、不得读取 DELL correction 或 hidden Gold。

> **2026-08-07 `013-S2-05` MU raw authority 已编译**：在不修改 runtime、policy、blind input 或模型可见合同的前提下，MU 专属 authority/issuer 已零调用形成。MU 仅消费自身 `11 Evidence / 3 derived numeric / 4 explicit gaps`，DELL raw/correction 与 evaluator-only hidden Gold 不可见；post-hoc evaluator v1.1 不进入 prompt。权限限一份 admission、一次 execution、最多 12 calls、retry/fallback=0；NVDA、supervisor、business promotion 和 automatic next-case 均未授权。提交推送后才可签发 Git 忽略 admission，并须重新通过 scoped execution preflight；当前尚无 admission 或 Provider 调用。

> **2026-08-07 `013-S2-05/06` MU raw 与 supervision boundary 已形成**：唯一 MU run 完成 `10/10 calls/captures`，全部 `ok/stop`、0 retry/fallback。模型形成比最小 S3 Anchor 更完整的 MU-specific 研究链，但把 trailing P/E 改写为单季度倍数、把 deposits＋financial commitments 改写为现金/可退款预付款、把平均 FCF margin 直接用作边际收入敏感性，且 Verifier 零 finding 接受。Evaluator 先按单位族/条件语义关闭 12 条误报，再以通用财务不变量补齐 semantic coverage；最终 MU=`6 L1/2 L2/14 L3`，DELL 同版 replay=`2/1/23`。MU raw 记为 `complete_quality_fail`；22-row correction ledger 已分出 model return、研究内容 return、未校准 scenario/reference 和 Verifier false-green。不得用 deterministic renderer 代写研究，不做 supervisor correction；下一项只可独立审查 NVDA raw authority。

> **2026-08-07 `013-S2-05` NVDA raw authority 已编译**：第三案继续绑定同一 blind input/runtime/DeepSeek Pro 合同；NVDA 仅见本案 `13 Evidence / 3 Numeric / 4 gaps`，前两案 raw/correction 与 hidden Gold 均不可见。一次 admission、一次 execution、最多 12 calls、0 retry/fallback；evaluator v1.3 仅 post-hoc。authority/production/Project OS 零调用预检与 84 项宽回归通过。提交推送前不签发；NVDA raw 完成后先冻结本案结果和 supervision boundary，再单独决定三案 supervisor，不自动纠错或晋升。

> **2026-08-07 `013-S2-05` NVDA raw R1 terminal 与项目门禁修复**：唯一正式运行在 Lead 后以 `experiment_a_unbound_numeric_surface` 停止，`1 call/1 capture/0 retry`。原因为冻结 `5359 USD_billion` 被模型合法写成 `$5.36T`，而本地 compiler 未生成 billion→trillion 等价舍入表面；非 Provider/模型造数。修复后 immutable Lead replay 通过，宽回归 88 passed，但 R1 继续保持 terminal failed、raw chain incomplete。不得自动补跑；需先提交修复，再单独决定 replacement authority。三案 raw、supervisor recoverability 与 S2-06 仍未完成。

> **2026-08-07 `013-S2-05` NVDA raw replacement R2 authority 已编译**：用户已单独批准一次修复后 exact-live。R2 沿用 R1/DELL/MU 的 model-visible contract、NVDA case digest、DeepSeek Pro 参数和最多 12-call/0-retry envelope；唯一差异是本地 typed billion→trillion 等价表面修复。R1 admission/root 不复用，前两案 raw/correction、supervisor prompt 与 hidden Gold 不可见。focused=`34 passed`、S2-05/S2-06 broad=`93 passed`；当前 admission/provider=0。需 clean commit/push 后重新 preflight 才能签发；R2 若出现新 L1，停止且不自动进入 R3。

> **2026-08-07 `013-S2-05` 三案例 raw campaign 已完成、全部质量失败**：NVDA R2 exact-once 完成 `10 calls/10 captures`、0 retry，R1 numeric-scale 误杀未复发。post-run evaluator v1.4 删除 cash-flow/P-E 条件清单共现造成的 2 L1＋1 L2 误报，并对三案统一补齐 citation ID-role 检查；immutable replay 最终 DELL=`3 L1/1 L2/23 L3`、MU=`8/2/14`、NVDA=`4/1/27`。三案 raw 与 deterministic supervision boundary 均已物化且 raw mutation=0；三案均 `complete_quality_fail`。`013-S2-05` raw measurement 完成，但 `013-S2-06` supervisor recoverability、corrected candidate、formal hidden score 与业务晋升仍未完成。不得 NVDA R3 或逐案重跑；下一项只可单独裁决统一三案例 supervisor 实验。

> **2026-08-07 `013-S2-06` 三案例统一 Supervisor authority decision 完成、签发仍阻断**：统一实验冻结为同一协议下 DELL/MU/NVDA 三个物理隔离执行；每案 Supervisor 只能看本案 raw、visible finding 与 blind case pack，hidden/Codex Gold 和跨案结果不可见。每案最多 `1 SupervisorPlan + 10 corrected graph`、campaign 最多 33 calls、0 retry/fallback；逐案必须 `L1=0/L2=0`，关闭空反证与未校准阈值并让 Verifier 覆盖 prior material classes，三案全部通过才可称 recoverability proven。当前缺 case-qualified plan、coverage/citation owner、partial graph corrected runner 与 candidate-freeze scoring guard，故 admission/provider=0；下一项是唯一 zero-call shared implementation package，不允许先调用模型发现这些已知项目缺口。

> **2026-08-07 `013-S2-06` 唯一共享零调用实现包工程通过**：新增 case-qualified v1.2 correction boundary、三类 citation/coverage 明确 owner/action、单源 SupervisorPlan、依赖感知 corrected runner、fresh identity、共享 admission exact-once、capture-first terminal、candidate freeze 与 post-freeze scoring guard。本地只做 typed routing 与 source-bound 删除，不代写金融研究。三案 full-fake 最坏均为 `11 calls/case`；真实 frozen raw 容量预检为 DELL=`8 calls/33,590 chars`、MU=`10/28,104`、NVDA=`10/35,650`，均在 `11/90,000` 硬上限内。focused=`24 passed`，S2-05/06 broad=`120 passed / 3,201 deselected`，模型/Provider/network/admission/paid candidate=0。四项项目 blocker 工程关闭，但这不证明 DeepSeek 能生成合格计划或修好研究内容；下一步先 clean-commit independent fresh proof，再单独决定三案 admission。

> **2026-08-07 `013-S2-06` independent fresh zero-call proof 通过**：在 clean/synced `60b66bc9...0ef` 上生成两个独立 Git archive，分别注入三案受限 raw 并由两个 fresh process 重算 current evaluator、v1.2 boundary、SupervisorPlan、容量和 mutation；两份归一化结果 digest 相同，24/24 测试通过。真实矩阵保持 DELL=`33,590 chars/6 directives/8 calls`、MU=`28,104/8/10`、NVDA=`35,650/9/10`，源 raw 与目标 supervision tree 未改写，外部调用/admission/paid candidate=0。发现 blind-input 历史 SHA 绑定 Windows CRLF、Git blob 为 LF；proof 仅以严格 normalized-content-equal 投影恢复冻结字节，记录为 S5 portability 债务，不冒充跨平台 release proof。下一项仅为三案 Supervisor admission authority decision；自然纠错、L1/L2 closure、内容增益、human acceptance 与 release 仍未成立。

> **2026-08-07 `013-S2-06` Supervisor admission authority 通过**：四项项目内签发 blocker 和独立 fresh proof 均已关闭/通过，三案真实冻结输入均在预注册容量内，因此批准一个顺序、物理隔离的 supervised-recoverability campaign。预计 calls 为 DELL=`8`、MU=`10`、NVDA=`10`，合计 `28`，硬上限仍为 `11/case,33/campaign`，成本 `USD 0.18/case,0.54/campaign`，retry/fallback=0。每案必须 fresh Run/Attempt/runtime/admission，上一案 terminal 分类后才签下一案；共享项目缺陷停全 campaign，已排除共享原因后的 case-local 模型/内容失败无 retry、无现场 patch，但可继续其余案例完成能力分布。三案全部逐案 `L1=0/L2=0` 且有实质内容增益才可称 proven，部分通过不得平均。机器 decision=`32146a12...453e`；本项 admission/Provider/candidate/score/promotion=0，下一项仅为 DELL admission issuance 与 exact-once execution。

> **2026-08-07 `013-S2-06` DELL issuer/runner 零调用实现就绪**：新增最小 release support、DELL admission issuer 与 exact-once runner，不修改已冻结共享 Runtime 或模型可见合同。admission 绑定 authority、implementation、clean Git、policy、DELL raw/evaluation/boundary 与 execution entrypoint SHA；存储和 shared-ledger 均在 Git 外，capture-first、0 retry/fallback。真实容量仍为 `8 calls / 33,590 chars`，focused=`21 passed`；本项 admission/provider=0。提交推送后才可运行 scoped preflight、签发一份 DELL admission 并 exact-once 执行。

> **2026-08-07 `013-S2-06` DELL Supervisor R1 项目合同漂移终止**：唯一 admission exact-once 消费，SupervisorPlan transport/JSON 正常，`1 call / 1 capture / 9,795 tokens / USD 0.0072278 / 0 retry`。输出的 identity、partition、六个 directive 与 alias 均受控，但 Verifier directive 未选 Evidence/Gap。模型可见 Schema 允许空数组且 Prompt 未声明每 directive 非空，本地 Validator 却隐藏强制非空，故 RC-P36-147 归项目 Prompt/Schema/Validator 漂移，不计为模型能力失败。R1 immutable，candidate=0，MU/NVDA 未启动；只允许一个共享零调用 compiled-contract 修复包，fresh proof 后再单独决定 DELL replacement。

> **2026-08-07 `013-S2-06` Supervisor compiled-contract v1.1 工程通过**：唯一共享零调用包已把每 directive（含 Verifier）至少一条 Evidence-or-Gap 的规则统一编译到 Schema、Prompt、Validator 与三案 fixture，Numeric-only 明确不足；真实 R1 空 Verifier 形状回放与 broad `133 passed`。旧 R1 入口主动失效，外部调用/admission=0。下一步只做 clean commit 独立 fresh proof，再单独决定 DELL replacement；不得直接重跑或启动 MU/NVDA。

> **2026-08-07 `013-S2-06` DELL replacement authority 有条件通过**：v1.1 已在 clean `978c7c33` 上经双 archive/双 fresh process、每 worker `27/27` 独立证明，因此允许一次 DELL R2；但 successor issuer/runner 尚未绑定，当前不可签发或执行。R2 保持 `8 expected/11 hard calls, USD≤0.18, retry/fallback=0`，不自动 R3、不授权 MU/NVDA；下一项仅实现并提交 successor governed entrypoint，再由用户单独决定是否执行。

> **2026-08-07 `013-S2-06` DELL R2 successor entrypoint 工程通过**：隔离 support、issuer、runner 已绑定新 decision、v1.1、fresh proof、immutable DELL inputs 与入口 SHA；独立 `DELL_R2` authority root 和 fresh R2 identity 阻止 R1 复用，旧入口仍 fail-closed。focused=`5 passed`、broad=`143 passed`，外部调用/admission=0。提交推送后只做 clean Project OS/runner/issuer dry-run preflight；通过后必须返回用户获取 execution 指令，不得自动签发。

> **2026-08-07 `013-S2-06` DELL R2 successor clean preflight 通过**：clean/synced `f1238ad9` 上 Project OS、runner 与 issuer dry-run 均通过；v1.1/immutable DELL/capacity 与 credential-presence 边界成立，authority/Run root 均未创建，外部调用/admission=0。当前必须停止并等待用户 execution 指令；之后才可签发一份 R2 admission 并 exact-once 执行，仍禁止自动 R3 和 MU/NVDA 越序。

> **2026-08-07 `013-S2-06` DELL Supervisor R2 可信终止**：唯一 R2 admission 在 `85b3a8bb` 上 exact-once 消费，SupervisorPlan v1.1 自然通过，随后 U3/U4 corrected Specialist 共完成 2 次调用；总计 `3 calls/3 captures/13,177 tokens/USD 0.009741/0 retry`。R1 的 RC-P36-147 未复发，但新 RC-P36-148 暴露共享协议缺口：Supervisor 看得到 finding code/path，corrected node 只收到 correction ID/action/aliases，且 generic node validator 不验证 assigned correction 是否关闭；U3 仍为空反证却被接受。U4 同样未关闭反证，并把方向性中个位数重新写成无授权约 `5%`，在 `experiment_a_unbound_numeric_surface` 首错停止。该结果同时包含项目 correction semantic/closure 缺口与模型 numeric semantics 不遵循；按共享缺陷规则停止 campaign，不自动 R3/MU/NVDA。下一项只允许一个零调用结构处置，不得逐字段 live patch。

### 7A.4 调用、扶正与停止规则

1. 不设全局固定 9 次或 15–25 次调用上限。每案根据 DecisionSurface、material evidence gap 和工具预算预注册最大值；只有新增可信证据、关闭重要 gap、解决冲突或提高 authority 才继续。
2. formal run 在首个 material 失败处停止并保存 terminal。若为了集中暴露问题需要 collect-all diagnostic，必须预先标记 `quarantined_non_promotable`；其下游结果不得成为产品通过证据。
3. supervisor 可暂停、补证、缩小任务或退回节点，但 raw model-only、correction ledger 和 corrected result 必须分开。扶正后的链只证明“受监督可恢复”，不证明 autonomous success。
4. Experiment A 的模型问题留在 S2/S3；MCP/source/parser 问题留在 S1；产品交互问题留在 S4；release 只在 S5 判断。S4 不得再次吸收 S1/S3 根因。
5. 三案是正式 anchor；stale/future source、冲突证据、证据缺失、quarter/annual、跨案污染、20-F/多币种/PDF redirect 作为 deterministic/adversarial fixtures。新增行业或全新正式案例只在不改变 FIN 0.1.3 范围的有界 transfer 集中执行。
6. 任一失败 attempt 不创建 FIN 0.1.4；只有 FIN 0.1.3 完整结束或产品范围/兼容性发生实质变化时才讨论新版本。

### 7A.5 2026-08-07 数值权威、纠错闭环与研究质量重排

DELL Supervisor R2 说明旧计划还缺一条统一原则：模型需要看到并使用精确事实完成分析，但不能在全节点自由重写中重新制造 material number；本地 Runtime 又不能因此接管 thesis 和研报叙事。历史文档对此有 alias、judgment atom、local renderer 等局部规定，但没有统一编译到 current correction request、closure validator、artifact renderer 和内容质量门。

本次只修正 FIN 0.1.3 内部执行顺序，不创建 FIN 0.1.4，也不重开已关闭的 S0/S1：

| 顺序 | Owner stage | 工作包 | 完成标准 | 明确不做 |
| --- | --- | --- | --- | --- |
| `S2-06A` | S2 | 冻结模型可见/分析/引用/写作与本地渲染/晋升五权边界；登记 PRD、合同和阶段计划 | 本文、PRD 7.9、跨域合同 38 与 Project OS 一致 | 不修改 Runtime、不调用模型、不宣称 RC-P36-148 关闭 |
| `S2-06B` | S2 | 一个共享零调用合同包：`NumericFactView`、`ProtectedNarrativeDraft`、完整 `CorrectionObjective`、逐项 `CorrectionClosureReceipt`；Prompt/Schema/Validator/fake/renderer 单源编译 | corrected node 看见 finding code/path/reason/required resolution/closure rule；默认最小 patch；未关闭项 fail closed | 不逐字段 live patch，不让本地代写 thesis/机制/完整段落 |
| `S2-06C` | S2 | deterministic proof | 回放 DELL U3/U4；DELL/MU/NVDA full-fake；覆盖空反证、unknown alias、未授权数字、period/unit、placeholder residue、整节点重写 reopen 等 mutation | 不用 paid call 发现确定性问题 |
| `S2-06D` | S2 | 合同变化后的最小自然 canary | 只对实际变化的合同 family 做一个节点级自然输出；证明 ref/closure 合同可遵循 | 不直接恢复三案 campaign，不以 canary 代替产品报告 |
| `S2-06E` | S2 | project-level formal proof decision | 基于零调用 proof＋canary 决定是否值得再做一次 DELL supervised proof；需新的 authority | 不自动 R3，不自动启动 MU/NVDA |
| `S1-06/07/08` | S1 | MCP、current external source runtime、Agentic Search 质量 | 工具可靠性、currentness、source diversity、accepted/rejected/gap 和 recoverability 达门 | 不把工具缺陷算到模型 |
| `S3-06/07` | S3 | 动态 Lead 与 targeted repair 消费新 correction contract | evidence gap 能触发真实查询/修复/typed stop；每个 correction 可关闭和追溯 | Writer 不补源，Harness 不代写研究 |
| `S3-08/09` | S3 | 三案端到端研究与正式内容验收 | L1/L2、八维质量、paired gain、qualified-human acceptance 全过；成品无模板化退化 | 不以完整调用链或 placeholder 全清替代研究质量 |
| `S4-06` | S4 | Workbench dogfood | 展示 fact ref、source、analyst threshold、correction diff/closure 和 final artifact；用户可审 | 不回收 S1/S2/S3 根因 |
| `S5-01` | S5 | release gate | 同时证明 truth safety、研究质量、anti-template、成本、重放、rollback 与 portability | 不在 gate 内现场补合同或降门槛 |

当前状态：`S2-06A/B/C` 已完成文档、Runtime 消费和独立 deterministic proof，RC-P36-148 的项目内 guard 可记 engineering repaired；`S2-06D` 证明 DeepSeek 自然 evidence-role/closure 未通过，`S2-06E` 已阻断 formal DELL proof。只有后续 successor atom/narrative paid artifact 和 qualified-human 内容验收通过，才能说明这套混合权威同时达到可靠性与报告质量。

### 7A.6 2026-08-07 Provider-neutral Harness 与 DeepSeek 适配重排

S2-06D 证明当前问题不能继续按“发现一个 DeepSeek 输出错误，就给共享 Harness 加一个字段或分支”处理。FIN 冻结稳定金融控制内核；模型差异进入 `ModelCapabilityProfile`，权限通过 `AutonomyGrant` 升降，DeepSeek workaround 必须可识别、可复测、可退役。

本项不改变当前先执行 `S1-06/07/08` 的顺序。它为后续 `S3-06/07` 增加三个前置子包，不创建新产品版本或新 S-stage：

| 子包 | 内容 | 通过标准 | 停止规则 |
| --- | --- | --- | --- |
| `DS-A1 capability profile` | 冻结 strict JSON、identity、numeric ref、evidence role、closure、threshold、narrative、tool use 的 family 级能力 | profile 绑定 model/version/contract/evidence，当前失败与允许 autonomy tier 清楚 | 不用全链发现 family 能力 |
| `DS-A2 judgment atom` | evidence-role closed-set＋claim/mechanism/counter-thesis/gap/WWC atom；closure 本地计算 | DELL/MU/NVDA fake/mutation 与一个自然节点 canary 通过 | 不允许模型 self-attest closed，不逐字段扩 Prompt |
| `DS-A3 protected narrative` | accepted atoms→DeepSeek 自然叙事→本地 protected render | reliability floor 与 paired 内容质量 floor 同时通过 | 质量下降则不晋升；同 family 一轮最多一次结构修订 |

DeepSeek 当前只在已自然证明的 JSON/identity/numeric-ref family 保留权限；evidence-role、closure、threshold 和 corrected whole-node authoring 降级。未来 DeepSeek 或其他模型升级时，重跑同一 capability matrix 并调整 `AutonomyGrant`，不得复制旧 workaround 或修改稳定内核。

## 7B. 2026-08-08 PRD / TECH / Runtime 第二次互校准与当前计划基线

### 7B.1 为什么必须重排

原 21 个修复包仍保留为 FIN 0.1.3 的问题来源和历史责任图，但实际工程证明，“S1-01–05 关闭”只代表本地 truth/retrieval pack 基线通过，不能代表 PRD 的 Agentic Search 已通过。S1-06/07 补齐了 MCP 与受控官方来源 Runtime；S1-08 的 DELL exact-live 又证明 target-in-pool、客户/供应链来源发现和外部 provider 能力仍失败。故此前“只差排序”的理解被真实结果否定，必须把 candidate ceiling 放回 ranking 之前。

同样，S2 的合同、fixture 和 Experiment A 已完成，但 DeepSeek 的自然 evidence-role/correction closure 未通过；S3-01–05 只形成 minimum engineering anchor，不是内容合格研报；S4/S5 尚未在 FIN 0.1.3 current candidate 上开始。该纠正不创建 FIN 0.1.4，也不改写任何失败 Attempt。

### 7B.2 当前阶段事实

| 阶段 | 当前事实 | 当前结论 | 不得宣称 |
| --- | --- | --- | --- |
| S0 | `013-S0-01–04G` 已关闭；typed blocker state、RunScopeRegistry v1.0 与 unknown fail-closed 已通过 clean compatibility proof | shared execution governance scoped pass | 任意 preflight pass 即可代替 exact admission/runner/source binding |
| S1 | `S1-01–07` 已通过各自 scope；S1-08 DELL R3 live=`15 calls / 0 unique source / target-in-pool 0`，并暴露 owned scheduler/cache natural-topology defect | S1-08 仍未通过；no-R4 生效，当前只允许 P3 零调用处置 | reranker/ranking 已可评、typed gap 等于来源穷尽、Agentic Search 产品可用 |
| S2 | `S2-01–04` 与 deterministic correction control 已证明；Experiment A 三案内容失败，S2-06D natural correction closure 失败 | 实验和模型能力边界已形成，产品级模型自主权未通过 | S2 产品通过、DeepSeek 能自主纠错、内容质量通过 |
| S3 | `S3-01–05` minimum anchor 有结构与控制证据；29 Cell 未研究、自然 thesis support/counterevidence 不足；`S3-06–09` 未开始 | engineering anchor only，等待 S1 candidate ceiling 与 DS-A1/A2/A3 | 产品级 research、完整研报、八维质量验收通过 |
| S4 | 只有继承自 0.1.2 的只读 Workbench/Report projection；尚未消费 0.1.3 final candidate | FIN 0.1.3 current dogfood 未开始 | 当前版本产品验收或审阅负担已通过 |
| S5 | RG1–RG5 未对 0.1.3 candidate 执行 | release blocked | FIN 0.1 Internal Alpha 已冻结或发布 |

### 7B.3 新发现问题的唯一归属

| 问题 | 最早 owner | 处置 |
| --- | --- | --- |
| provider 只有声明/接口、没有 operational/live proof | S1-08 / TECH_02 | capability lifecycle 与 route-unavailable；不得冒充 broad search |
| target 进不了候选池却先测 NDCG/MRR | S1-08 / TECH_02/03/10 | target-in-pool 与 required-slot recall 先行，ranking 不准入 |
| 旧 BM25 89,112 rows 缺 current DELL/NVDA annual | S1-08 / TECH_03 | 旧索引 non-authority；current metadata/source coverage 单列修复 |
| slot starvation、fetch ceiling 语义、关系方向、发布日期误判 | S1-08 / TECH_02 | v3 zero-call 实现＋clean proof＋有界 live 验收 |
| 未知 blocker state/run scope 可能 fail-open | `013-S0-04G`，S5 release 再验 | typed blocker state、versioned RunScopeRegistry、unknown fail-closed；不塞进 SourceHunter |
| DeepSeek evidence-role、closure、threshold 和整节点纠错不稳定 | S2 capability profile；S3 atom/narrative | DS-A1/A2/A3；同 family 一轮最多一次结构改造，不再逐字段修 Prompt |
| 动态 Cell、跨证据机制综合、反方和可执行 WWC 不足 | S3-06–09 | Search Quality Card 通过后做动态 research/targeted repair 与八维内容验收 |
| 页面内容稀薄、review burden、repair UX | S4-06 | 只在 current research candidate 上 dogfood，不回收上游根因 |
| release、rollback、portability、共享治理最终证明 | S5 | RG1–RG5；不得在 gate 内现场修合同 |

### 7B.4 更新后的依赖顺序

1. [x] `S1-08-P1 / S1_08_V3_MATURE_COMPONENT_RELATIONSHIP_BUDGET_CLEAN_INDEPENDENT_ZERO_CALL_PROOF`：已在 clean `a3f15fa2` 上由双 Git archive、双 fresh process 各执行完整 `60 passed / 0 skipped`，并复现依赖、两份真实 R2 日期、三案例 full-fake/mutation；零网络、零模型。
2. [x] `S1-08-P2 / S1_08_V3_DELL_FRESH_LIVE_AUTHORITY_DECISION`：零调用 decision 已批准一个条件性 R3 successor，但当前不可签发；旧 R2 runner 固定绑定 v2 catalog 且 authority/result 已消费。decision 本身没有 admission、network 或 live。
3. [x] `S1-08-P2B / S1_08_V3_DELL_R3_SUCCESSOR_ENTRYPOINT_ZERO_CALL_IMPLEMENTATION`：R3-only admission/terminal/module/runner/namespace/result 已实现；decision、R2、v3 proof/catalog/source SHA、reserve-before-DNS 与 capture-first terminal 均进入合同。working-tree focused=`7`、S1-08=`70`，正式 admission/live=`0/0`。
4. [x] `S1-08-P2C / S1_08_V3_DELL_R3_SUCCESSOR_CLEAN_ZERO_CALL_PREFLIGHT`：clean A1 的 144 个无关 collection errors 已保留；修复后的 A2 在 clean/synced `d713eb66` 的 Git archive/fresh process 中显式执行 10 个文件并 `70 passed / 0 failed / 0 skipped`。R1=`19`、R2=`2` 受限输入不变，source/mutation/exact-once 全通过，formal admission/external/live=`0/0/0`。
5. [x] `013-S0-04G`：typed blocker state、RunScopeRegistry v1.0、unknown fail-closed 与 downstream clean compatibility proof=`85/85` 已完成；RC-P36-156 closed。
6. [x] `S1-08-P2D / S1_08_V3_DELL_R3_EXACT_LIVE_ISSUANCE_AUTHORITY_PROJECTION_DECISION`：v1.2 clean requalification=`85/85` 后，最终 v1.1 只批准一个独立 DELL R3 Attempt；decision 内 admission/network/live=`0/0/0`。
7. [x] `S1-08-R3 / S1_08_V3_DELL_R3_EXACT_LIVE_ISSUANCE_AND_EXECUTION`：唯一 admission 已 exact-once 消费。terminal/capture pass，但 `15 network / 0 candidate / 5 gaps / 229 qualified locators / 0 document request`，candidate ceiling 与 target-in-pool 失败；no-R4 生效。
8. [x] `S1-08-P3 / S1_08_P3_POST_R3_OWNED_SCHEDULER_CACHE_AND_PROVIDER_PRODUCT_SCOPE_DISPOSITION_DECISION`：已选择 repair-first；Provider、动态页／licensed source 与来源范围缩减 deferred，no-R4、16 次上限和质量门不变，本 decision 外部/admission/live=`0/0/0`。
9. [x] `S1-08-P3A / S1_08_P3A_PROTECTED_DOCUMENT_FETCH_BUDGET_AND_ATTEMPT_LOCAL_CACHE_ZERO_CALL_IMPLEMENTATION_AND_PROOF`：v4 工作树 `92/92`；A1 输入装配失败保留；A2 在 clean/synced `5e9726c2` 双 archive／双 fresh process 各 `92 passed / 0 failed / 0 skipped`，R1/R2/R3=`19/2/39` 不变，外部调用为 0。P3A 只证明 protected-fetch/cache 不变量。
10. [x] `S1_08_DIAGNOSTIC_BROAD_SEARCH_SEARXNG_ADAPTER_ZERO_CALL_IMPLEMENTATION_AND_PROOF`：diagnostic-only JSON adapter、本地容器、provider-neutral locator、capture/typed error/预算/去重/no-promotion 均已实现；clean v1.1=`15 passed`、三案 full-fake、`9 captures / 0 network / 0 model / 0 promotion`。首次部署 launcher 与搜索式 healthcheck 失败均保留，修复后只读本地探活通过。
11. [ ] **当前下一项 `S1_08_DIAGNOSTIC_BROAD_SEARCH_SEARXNG_BOUNDED_NETWORK_BASELINE`**：用 DELL/MU/NVDA 各一个预注册 query 测量 engine participation、unresponsive engine、canonical locator coverage、duplicate/currentness metadata availability；FIN query ceiling=`3`、configured engine ceiling/query=`4`、retry=`0`。结果只能形成诊断基线，供未来付费 API 同口径对照；SearXNG 内部 HTTP fan-out 不能伪报为 exact 3 calls。
12. `S1-08-P3B/P4`：结合 P3A 与 diagnostic provider 对照，再由 Owner 复核生产 Provider、Internal Alpha source claim 与 no-R4。只有新的 DELL product-live 被单独批准且 candidate ceiling 通过，才可能恢复 MU/NVDA bounded transfer和 ranking。
13. `DS-A1/A2/A3`：冻结 model-family capability profile，完成 evidence-role/judgment atom 与 protected narrative 门；只对实际变化 family 做一个自然 canary。
14. `S3-06/07`：Lead 根据真实 Search Quality Card 编译动态 DecisionSurface、发起 EvidenceRequest、执行 targeted repair；调用预算由未闭合 Evidence Slot/Cell 决定，不再把“9 次调用”当产品设计目标。
15. `S3-08/09`：执行三案 Experiment B，比较同一 evidence/search boundary 下的模型研究质量；必须通过 L1/L2、八维 `>=24/32`、核心维度下限、paired gain 与 qualified-human acceptance。
16. `S4-06`：在 current candidate 上完成新建/恢复 Case、检索活动、Evidence/Numeric、Workpaper、repair、LeadReview、Report、exact review 和 trace 的真实 dogfood。
17. `S5-01`：执行 RG1–RG5、rollback/portability/known-gap 决策；只有这一步可给 FIN 0.1.3 内部收口结论。

### 7B.5 止损与版本边界

- 同一结构 family 最多一次 zero-call 结构修订加一次自然 canary；新的非阻断 L2–L4 表达问题进入 S3/S4 backlog，不再反复修改 S1/S2；
- fresh live 再出现新的 L1 时，先归因到 provider/locator/parser/contract/model family；只有最早 owner 的结构问题可留在本阶段，其他问题后传；
- 若 Internal Alpha 必须依赖当前没有运营能力的 broad external search，必须做产品 source-scope 或 provider acquisition 决策，不能用 typed gap、更多调用或官方单域抓取伪装满足；
- FIN 0.1.3 仍是当前版本。只有完整迭代完成、正式终止或产品范围/兼容性发生真实变化，才讨论下一产品版本；单个 proof 或 attempt 失败不触发版本跳跃。

## 7C. 2026-08-08 中段产品—技术—实证审计与执行再基线

### 7C.1 核心反思

从 S0 到当前 P2C，仓库已经非常擅长保存失败、绑定身份、构建 successor、做 clean proof 和阻断未授权执行；但这些能力的成熟度明显高于“找到足够资料、形成公司专属判断、产出 reviewer-ready 研报、让用户完成审阅”。P2C 已在 clean archive/fresh process `70/70` 通过，下一步却仍需再追加一条手工 scope projection，说明 RC-P36-156 已从后台债务变成主线吞吐瓶颈。

另一项关键偏差是把“方法已写入 registry／合同已设计”误当成研究能力落地。当前 thesis-path-first、product-to-financial bridge、customer/supplier read-through、bounded leading signal 等方法多未同时达到 `runtime_injected + node_consumed + paid_artifact_proven + human_accepted`。这解释了为什么工程链条完整，Workbench/Report 仍显得内容稀薄。

本次重排不删除审计控制，也不降低质量门；它把重复 proof 和字段级模型修补的预算转回搜索覆盖、研究方法激活、内容质量和用户验收。

### 7C.2 修订后的阶段边界

| 阶段 | 只保留的责任 | 明确不再承担 |
| --- | --- | --- |
| S0 | typed blocker state、versioned RunScopeRegistry、unknown fail-closed、版本/attempt/authority 基线 | 为每个业务节点做定制 allowlist；重做 admission/SourceHunter |
| S1 | provider operational truth、候选池、ranking、promotion、current Evidence Pack | DeepSeek 研究质量；renderer/Workbench 修饰 |
| S2 | provider-neutral ModelCapabilityProfile、DeepSeek profile、AutonomyGrant、最小 family canary | 逐字段 prompt 修补；重复 full-chain |
| S3 | 动态 DecisionSurface、方法到 Runtime、EvidenceRequest/targeted repair、thesis/机制/反方/WWC、内容验收 | 搜索 route 缺口；页面 UX |
| S4 | current-candidate Workbench、repair/review/trace、review burden 和 human acceptance | 本地超级拼装补写上游没有的研究内容 |
| S5 | RG1–RG5、rollback、known-gap 和版本收口 | 在 release gate 内现场修上游合同 |

### 7C.3 新依赖顺序

1. `M0 / 013-S0-04G`：一次最小零调用治理包，关闭 RC-P36-156；只改 shared blocker/scope registry 与 preflight fail-closed，不扩成治理平台重写。
2. `M1 / S1-08-P2D + DELL R3`：P2D 只重核权限；通过后另建 Attempt，执行唯一一次 `<=16 network / 0 model-provider-retry / no R4` 的 DELL candidate-ceiling live。
3. `M1 outcome fork`：R3 pass 才用共同 transfer contract 验 MU/NVDA 并准入 ranking；R3 fail 则停止 SourceHunter live loop，转 Provider acquisition／动态页 fallback／licensed source／Internal Alpha source-scope 决策。
4. `M2 / DS-A1–A3`：可与 S1 transfer 准备有界并行，在冻结同一 Evidence Pack 上完成 DeepSeek profile、judgment atom、protected narrative 与一个最小 family canary；不依赖 broad live search。
5. `M3 / S3-06–09`：S1 SearchQualityCard 与 S2 AutonomyGrant join 后，激活动态研究方法，完成三案例 Experiment B、八维内容评分、paired gain 与 qualified-human acceptance。
6. `M4 / S4-06`：只对 M3 current candidate 做完整 Workbench dogfood；底稿和报告必须是实质内容，不接受通用 atom 列表。
7. `M5 / S5`：执行 RG1–RG5 并决定 FIN 0.1.3 close／conditional／blocked。FIN 0.2 定义保持不变。

### 7C.4 证明预算与停止条件

- ordinary deterministic change 不再机械拆成 implementation、entrypoint、authority、preflight 四轮；只有权限、成本、外部副作用或不可移植性真实变化时才单独决策；
- 同一 contract family 最多一次结构修订与一次自然 canary；字段级新症状回到 compiler/profile/root cause，不增加 live 轮次；
- DELL R3 是本结构下最后一次 SourceHunter live。再次 SQ2 fail 后，禁止 R4；
- S3 formal end-to-end 只在 SearchQualityCard、NumericTruthCard、ModelCapabilityProfile 就绪后执行；
- 方法 registry 覆盖率、测试数、Artifact 数和页面可见性均不得作为 research outcome 替代指标。

## 7D. DELL R3 后的当前再基线（2026-08-08）

P2D 已通过且唯一 R3 已消费。R3 的控制面按预期完成 exact-once、capture-first、typed gap 和 terminal，但产品来源质量为硬失败：`15 network / 13 query attempts / 0 candidate / 5 gaps`。它不是又一次“来源确实没有资料”的证明：adapter 在 `229` 个 locator 通过初筛后没有发出任何 document request。

本次实际工程证据修正了 P2C 后的过早假设。此前 60/70/85 项 deterministic proof 证明了 fixture 范围内的 parser/date/relationship/round-robin/ceiling 和 lineage，却没有覆盖自然 adapter 的多 route discovery、正文抓取以及跨 slot document cache。真实根因为 attempt allowance 同时支付 landing、structured endpoint 和 document fetch，且本地 budget stop 被作为 document cache 结果跨 attempt 复用。运营 Provider/动态页/market snapshot 缺口仍存在，但不能替代 owned defect 的修复责任。

因此执行线现在固定为：

1. [x] `P3` 已选择 repair-first：批准一次 bounded scheduler/cache 零调用 repair/proof；Provider、动态页、licensed source 与 Internal Alpha 来源承诺缩减 deferred；
2. [x] `P3A` 已在 `16` 次上限不变时完成 v4 successor、R3 natural-topology replay、三案 fake/mutation 和 A2 双 clean proof；A1 保留，P3A 不生成 live authority；
3. [x] 完成 SearXNG diagnostic adapter 与一次有界三案 baseline；它只比较 locator coverage，不拥有 Evidence/事实/生产 fallback 权。正式结果=`3 FIN queries / 30 unique locators / 9 captures / 0 model-retry-promotion`，但只有 DuckDuckGo 产出 locator、Brave 三案均限流、Bing 被不兼容的统一 `year` 过滤挡住、默认 Google inactive，且 `0/30` 返回发布日期；故机械诊断链通过，多引擎与 currentness 质量失败；
4. `P3B` 不再自动进入新 SearXNG live。先等待一个候选付费 broad-search API 的完整 HTTPS/认证/响应/成本资料，再以 provider-neutral semantic query＋provider-specific capability compiler 做零调用资格审查和同案有界对照；之后由 Owner 复核生产来源能力、来源承诺与 no-R4；
5. 在 DELL candidate ceiling 重新成立前，MU/NVDA、ranking、Experiment B、S3 formal research、S4 current dogfood 和 S5 release 均不准入；
6. 本轮不调用 DeepSeek，所以 S2 model profile 不因 R3/P3 增减分。模型能力与搜索工具能力继续分轨。

本再基线不创建 FIN 0.1.4，也不改变 FIN 0.2 定义。问题留在 FIN 0.1.3 的最早 owner `S1-08`，但 no-R4 规则要求先做产品级 P3，而不是自动继续现场维修。

## 7E. 查询编译器完成后的 S1-08 再基线（2026-08-08）

本节 supersede 7B.4 的旧 SearXNG current-next、7D 的“直接等待下一付费 API”和 worklog 740 中“修复后仍跑 Firecrawl 24-query”三项计划。新证据证明 Provider 对照不能继续复用 24 条 subject＋generic-slot 查询，否则 customer/supply 的 evidence owner fan-out 会再次丢失。

1. [x] `S1_08_PROVIDER_NEUTRAL_RELATIONSHIP_AWARE_SEARCH_INTENT_COMPILER_AND_SOURCE_EQUIVALENCE_EVALUATOR_ZERO_CALL_IMPLEMENTATION`：已编译 `36` 条官方精确路线和 `24` 条语义开放网路线；三案每条 customer/supply intent 只绑定一个 owner，研究主体仅作 context，不生成未经验证的客户／供应商断言。typed source-equivalence 只接受 exact locator、SEC accession、verified canonical/redirect 或 verified content identity。三案 full-fake/mutation=`13 passed`，S1-08 全组=`169 passed`，外部调用为 0。
2. [ ] **当前下一项 `S1_08_DOMESTIC_FIRST_PROVIDER_INPUT_QUALIFICATION_AND_RELATIONSHIP_AWARE_COMPARATOR_SCOPE_DECISION`**：零调用核对国内候选的 standalone raw search 形态、认证、字段、domain/date/filter、分页、限流、人民币成本、充值／发票和凭据治理；优先 Tencent 新 successor 与百度千帆，阿里／火山只有在能力形态满足时进入对应 lane。Firecrawl 是免费控制，Exa 是可选国际 semantic benchmark，不作为主线采购前提。
3. [ ] comparator 设计不得把 60 条意图自动全部变成一次 live。`precise_official_domain=36` 与 `semantic_open_web=24` 分别给出 ceiling、成本、Provider capability degradation 和 stop rule；Owner 看见资格审查后才决定签发哪一 lane、哪一家 Provider。旧 Tencent 24-query result 保持 immutable，不能改名重跑。
4. [ ] 只有新的 locator comparator 在 Gold-blind、capture-first 下达到 target-in-pool、日期可核验、来源多样性、成本和延迟门，才进入独立 SourceHunter adapter integration。通过前 ranking/reranker、MU/NVDA transfer、Experiment B、S3/S4/S5 仍 blocked。

本次没有把支付便利写成核心搜索逻辑。它属于 Provider procurement/operation profile：国内充值、人民币结算、发票和支持便利可以提高采用优先级，但不能降低金融证据与候选质量标准。若国内 Provider 都不能达到 candidate ceiling，再向用户提出国际 API 或 Internal Alpha source claim 调整，而不是静默改用国外服务或降低门槛。

## 7F. 国内 Provider 输入资格后的 S1-08 再基线（2026-08-08）

1. [x] `S1_08_DOMESTIC_FIRST_PROVIDER_INPUT_QUALIFICATION_AND_RELATIONSHIP_AWARE_COMPARATOR_SCOPE_DECISION`：Tencent SearchPro 与百度千帆 `baidu_search_v2` 均确认为 standalone raw-search API；阿里 Web Search MCP 单列为可返回 `pages` 的国内语义工具；Firecrawl 保留无密钥控制，Exa 仅作可选国际 benchmark。network/provider/model/document/Evidence=`0/0/0/0/0`。
2. [x] 暴露新的项目输入边界：百度明文限制 query 为 72 units、中文按 2 计；当前 canonical 60-query 加权范围=`122–268`，直接兼容=`0/60`。这不回滚 SearchIntent，而要求 provider wire projection 把 domain/date 移入结构化字段并生成 digest-bound 短查询。
3. [ ] **当前下一项 `S1_08_DOMESTIC_PROVIDER_WIRE_PROJECTION_AND_FAIR_COMPARATOR_CONTRACT_ZERO_CALL_IMPLEMENTATION`**：实现 canonical intent 到 Tencent／Baidu／Alibaba MCP／Firecrawl wire object 的薄适配；百度投影必须 `<=72 units` 且保留 owner、period、claim direction、source family；三案 fake/mutation 必须证明无跨案污染、无 Gold 泄漏、semantic lane query parity 和 36/24 独立预算。
4. [ ] 零调用 proof 通过后才决定具体 live：优先使用新建且未暴露的国内 Provider 凭据；没有国内 Key 时可单独运行 Firecrawl control，但不能宣称国内主线完成。任何 live 都必须另有 provider-specific admission、capture-first、0 retry 与停止规则，不自动执行 60 次。

本次保持 FIN 0.1.3 与 S1-08 归属，不新建版本。字面 query 因公开 transport limit 可由 adapter 压缩，但 canonical intent identity、hidden target、评估口径与金融门禁不变；因此仍是同一研究矩阵，而不是为某家供应商改标准答案。

## 7G. wire projection 完成后的 S1-08 再基线（2026-08-08）

1. [x] `S1_08_DOMESTIC_PROVIDER_WIRE_PROJECTION_AND_FAIR_COMPARATOR_CONTRACT_ZERO_CALL_IMPLEMENTATION`：四家 profile 共 240 个 intent-bound wire object；百度 query units=`37–66`、兼容=`60/60`；semantic 24 intent 在四家逐字 parity；Alibaba MCP 在完整 schema capture 前保持 non-admissible。
2. [x] 查询质量人工复核：首版机械标签已替换为实体／槽位相关研究词（Azure AI capex、AI-server backlog、HBM、Blackwell、CoWoS 等）；完整 direction/source family 保留在 wire metadata，不靠冗长边界词占用搜索 query。
3. [x] exact-payload coalescing：60 个 logical intent 保持独立；每家执行计划为 `22 precise + 24 semantic=46 units`，相对逐 intent 调用少 14 次。共享 capture 必须列出 consumer intent IDs/digests，并按案例分别评估，不允许静默跨案晋升。
4. [x] 专项=`12 passed`，S1-08 全组=`181 passed`；network/provider/model/document/Evidence=`0/0/0/0/0`。
5. [ ] **当前下一项 `S1_08_DOMESTIC_PROVIDER_CREDENTIAL_READINESS_AND_FIRECRAWL_CONTROL_COMPARATOR_AUTHORITY_DECISION`**：secret-safe 检查 Tencent/Baidu fresh credential readiness；国内 Key 不可用时，只决定是否先用 Firecrawl 执行一个 control lane。必须在 `22 precise` 与 `24 semantic` 中明确选择，不能自动签 46 次，更不能复用聊天暴露 Key。
6. [ ] 某一 lane authority 通过后，另行建立 exact-once runner、capture-first terminal 与 evaluator-only Gold；比较 useful@10、target-in-pool、date accuracy、publisher diversity、cost、p50/p95。candidate gate 失败仍禁止 reranker rescue 或 SourceHunter integration。

这一实现没有把“多一个 Provider”当产品进度，而是先修正了输入公平性和查询质量。下一轮 live 的价值在于测索引／排序能否把一手证据带入候选池，不再重复测量 query compiler 缺陷。

## 7H. Firecrawl 控制终态与腾讯同矩阵接力（2026-08-08）

1. [x] Firecrawl relationship-aware semantic control 已 exact-once 完成：`24/24` successful、topical useful=`133/240`、customer/supply case-slot target-in-pool=`5/6`。query compiler 获得 live support，但 Firecrawl 因 `0/235` 日期、中文 exact target=0、DELL supply 缺口和 p95=`6877 ms` 保持 diagnostic-only。
2. [x] 新腾讯凭据已通过 presence-only 资格判断；项目不读取或保存值，也不允许复用聊天暴露的旧 AK/SK。选择 Tencent `semantic_open_web 24-query`，不执行 precise 22 或 combined 46。
3. [x] `S1_08_TENCENT_RELATIONSHIP_AWARE_SEMANTIC_SAME_MATRIX_RUNNER_ZERO_CALL_IMPLEMENTATION_AND_PROOF`：Tencent 24 个 Query-only wire 与 Firecrawl control 的 intent/query text=`24/24 parity`；capture-first、systemic-stop terminalization、standard tier、成本与共同质量 evaluator 已实现，focused fake/mutation=`7 passed`、外部调用=0。
4. [ ] 当前下一项是 clean authority：通过 S1-08 回归、Project OS scoped preflight、secret scan、clean commit/push 后，只签发一次 Tencent 24-query exact-live。该 live 是旧腾讯弱查询结果的 successor，不改写旧结果，也不构成对 Firecrawl 的逐调用单变量 A/B 之外的额外扩张。
5. [ ] Tencent 若所有 candidate/date/diversity/cost/latency/standard-version 门通过，只进入独立 SourceHunter adapter integration authority 决策；若失败，保持 diagnostic-only，并转下一 Provider 或 Internal Alpha source claim 决策。两种情况都禁止 reranker rescue、正文抓取、DeepSeek 或 S3 提前执行。

这一步不会因配置了 Key 就把“腾讯可调用”等同于“产品检索可用”。真正的产品增量仍由 required evidence target 是否进入候选池、日期能否核验以及三案例来源覆盖决定。

## 7I. Official-first 组合路由通过后的外源／内源检索连续计划（2026-08-08）

最新证据纠正 7H 中“单个 Provider 通过后再谈集成”的过耦合假设，但不放宽 candidate ceiling。official-first 零调用 successor 已把 60 个关系感知 intent 分成 `36 official + 24 Firecrawl shadow`，12/12 required slot 都有 route opportunity；immutable replay 仍保留 Firecrawl `5/6`、Tencent `0/6` 和 DELL supply typed gap。新增 provider/network/model/document/Evidence=`0/0/0/0/0`，所以它是 engineering pass，不是 external search 或 S1-08 产品通过。

用户已批准并要求长期保留下列顺序；所有工作仍属于 FIN 0.1.3，不创建新版本：

1. [x] `S1_08_OFFICIAL_FIRST_SOURCEHUNTER_PORTFOLIO_AND_DISCOVERY_SHADOW_ZERO_CALL_IMPLEMENTATION`：route planner、local authority replay、duplicate accounting、contamination mutation 与 SearchQualityCard proof 通过；
2. [x] `S1_08_OFFICIAL_FIRST_PORTFOLIO_CLEAN_INDEPENDENT_ZERO_CALL_PROOF`：A3 在两个 clean archive／两个 fresh process 各 `45 passed`，规范化输出一致；A1/A2 失败保留；
3. [x] `S1_08_UNIFIED_QUERY_FACET_PLAN_ZERO_CALL_IMPLEMENTATION`：60 intent 合并为 36 个共享计划，exact／lexical／semantic／graph／negative／forbidden／route filters 已生成，专项 13、S1-08 全回归 228；
4. [x] `S1_08_QUERY_FACET_THREE_WAY_DELL_MU_NVDA_EVALUATION`：raw/local 零调用 A/B 已完成（facet coverage `0.138889→1.0`、addressability proxy `0/9→9/9`、local 污染/重复=`0/0`）。唯一一次 DeepSeek query-atom natural canary 返回 18 个形状正确的原子，但其中一个 MU 原子绑定了不存在的 Evidence Slot；整批按合同 fail closed，未逐字段修补、未部分捞取、未 retry。当前正式基线冻结为本地确定性 compiler，模型辅助变体只有在未来独立能力决策中才能重新准入；
5. [x] `S1_08_OFFICIAL_ROUTES_PLUS_FIRECRAWL_SHADOW_COMBINED_LIVE`：R1 保持 immutable；v1.1 successor 经双 clean archive 复证后唯一 recovery exact-live 已完成。official DNS 阻断未复发，三案完成并获得 `4/12` required-slot selected coverage；Firecrawl 在首个 `429 reason=credits` 后停止，23 条剩余 query no-network terminalize。runtime recovery 通过，但 hidden Gold target-in-pool=`0/12`、来源族=1，结合历史 Firecrawl `5/6 but date=0` 与 Tencent `0/6`，external product acceptance=false。当前 provider round 诚实收口，禁止 R3／等额度补跑／reranker rescue；外源覆盖不足继续作为 release blocker；
6. [ ] **当前立即回到内源**：把同一 Query Facet 接入 exact SQL／object、BM25／ObjectBM25、dense／Milvus 与 relationship graph，修复“同一 raw query 无差别发送给全部 route”的历史弱点；
7. [ ] 扩大 DELL／MU／NVDA 人工 qrels、period／entity／relationship hard negatives，先证明 internal candidate ceiling；
8. [ ] candidate ceiling 通过后才比较 BGE embedding、RRF／fusion 与 reranker；报告 Recall@K、MRR／NDCG、false promotion、稳定性、延迟和资源成本；
9. [ ] 最后证明 selected candidate 进入 Evidence Gate、Claim、Workpaper 和报告。检索指标改善但下游未使用，不关闭 S1 或产品质量。

机器真相为 `configs/releases/fin_ia_0_1_3_s1_retrieval_query_facet_external_internal_progression_plan_v1_1.json`。第 6–9 项现在是已登记的同阶段后续，不提前扩大当前 external live；但第 5 项完成后不得遗忘、跳过或直接进入 S3。尤其不能用 BGE 或 reranker 掩盖候选池根本没有目标，也不能只汇报检索离线指标而不证明下游实际消费。

## 7J. 内源 Query Facet 投影通过后的候选池再基线（2026-08-09）

第 6 项已完成零调用工程实现，但其含义必须严格限定。36 份中英 Query Facet 已按同一 `case × Evidence Slot × evidence owner` 合并成 18 个双语研究束，并分别投影为 SQL、ObjectBM25、BM25、Milvus、Graph 共 90 个 typed candidate request；专项测试 `11/11` 通过。它纠正了旧链路把案例 ticker 和同一 raw query 无差别发送给全部 route 的问题：研究 DELL 的 Microsoft 客户需求时，内容路由现在过滤 `MSFT`；研究 TSMC 供给时使用本地 `TSM`，同时继续保存研究主体、披露主体、关系方向、期间和截至日。中文查询只保留为 alternate lineage，当前英文 SEC 内源不重复消耗预算。

这只是 `internal_query_facet_projection=true`，不是候选召回通过。当前执行顺序更新为：

1. [x] route-specific Query Facet projection：18 bundle／90 request，retrieval／embedding／rerank／Evidence=`0/0/0/0`；
2. [ ] **当前**：在真实本地 SQL／ObjectBM25／BM25／Graph 上测 candidate ceiling，并对 Milvus 与本地 BGE 资源做资格检查；按案例、Evidence Slot、披露方、期间和 hard negative 保存候选与 route contribution；
3. [ ] qrels 先使用 `agent_curated_pending_owner_review`，明确与历史 agent-authored diagnostic qrels 分开；Owner 未复核前不得写成“人工 qrels 已通过”；
4. [ ] 只有 target-in-pool 和 required-slot ceiling 通过后，才允许 BGE、facet-aware fusion 与 reranker 对照；旧证据显示 naive RRF 可能降低多 facet 质量，所以不得默认采用；
5. [ ] 排序通过后，再证明 Evidence Gate、Claim、Workpaper 和报告确实使用了新增候选。

本地资产预审同时暴露了真实数据边界：BM25／ObjectBM25 有 DELL、MU、NVDA、MSFT 但缺少 `TSM`；Gold SQL 有 `TSM`，但 current-quarter exact authority 可能稀疏；Milvus 有约 66 万向量，但模型 locator 仍需资格化；本地存在 BGE-M3，reranker 模型目前不存在。上述缺口必须在候选池阶段分型为 query／route／index／corpus／resource gap，不能靠调大 top-k 或提前下载 reranker 混在一起修。机器真相推进为 `configs/releases/fin_ia_0_1_3_s1_retrieval_query_facet_external_internal_progression_plan_v1_2.json`。

## 7K. 内源 candidate ceiling 结果与 current corpus/index refresh（2026-08-09）

第 7J 的 candidate ceiling 已真实执行，并纠正了一个会制造假缺口的合同问题：报告财年与文件发布年份必须分离。NVDA `Q1 FY2027` 是 reporting period 2027，但文件在 2026 发布；SQL 使用前者，文档索引使用后者。v1.0 的混用结果与 v1.1 首次 Milvus collection 未 load 结果不删除，修正后的 Attempt R2 作为新证据。

R2 的 18 个 bundle 得到 `SQL 0 / ObjectBM25 360 / BM25 360 / Graph 196`，Milvus 仅资格化未执行。18 个 agent-curated strict current target 中 `9/18` 进入 pool；另外 9 个主要缺 MU current Q3、DELL／NVDA current regulatory document 和 TSM/TSMC lexical/object rows。由此第 7J 的第 2、3 项状态变更为“候选观察已完成，但 gate failed”；失败归属 S1 数据/索引新鲜度，而不是 BGE、reranker 或 DeepSeek。

更新后的有界顺序为：

1. [x] typed period successor、真实 local candidate observation 与 provisional qrels packet；
2. [ ] **当前**：只做 current official corpus 与 index inventory，优先复用已保存 capture/raw source；明确每个缺失 target 是 source absent、parser absent、Gold transform absent 还是 index stale；
3. [ ] 在新路径构建 successor Gold SQL／ObjectBM25／BM25／Graph／Milvus，不原地覆盖历史资产；
4. [ ] 用同一 18-target qrels 重跑 candidate ceiling，达到 `18/18` 后交 Owner 复核；
5. [ ] 复核通过后才准入 BGE-M3、facet-aware fusion 与可选 reranker；
6. [ ] 最后执行 Evidence Gate→Claim→Workpaper→report utilization proof。

机器真相推进为 `configs/releases/fin_ia_0_1_3_s1_retrieval_query_facet_external_internal_progression_plan_v1_3.json`。external coverage 仍为独立 release blocker；内源通过不会自动关闭外源问题。

## 7L. R7 18/18、exact-SQL 分账与 ranking 准入（2026-08-09）

MU Q3 FY2026 10-Q 单文档 successor 已 exact-once 成功并形成 118 条 BM25＋118 条 ObjectBM25 增量 candidate。R7 在不改变 90-request 形状、过滤和预算的前提下达到 agent-curated research qrels `18/18`；新命中的监管/对账片段含承诺、capex、采购义务、政府补贴 clawback 与 DRAM 扩产正文，不是标题命中。Owner 仍未复核，因此 candidate ceiling 只可记为 agent-curated pass，不能自签 ranking admission。

独立 exact-SQL suite 进一步把两类问题分开：

1. [x] latest-available annual：三案例 60-row successor mart 对 revenue／gross profit／operating income=`9/9`；旧 74,897-row 主 mart 仅=`3/9`，证明 exact lookup 可用但候选策略仍指向陈旧资产；
2. [ ] current-quarter：DELL Q1 FY2027、MU Q3 FY2026、NVDA Q1 FY2027 六个冻结产品事实在两套 mart 均=`0/6`，必须由 capture-backed current numeric ingestion 建 successor，禁止从 benchmark 回填；
3. [x] BGE/Milvus 资源资格：本地 BGE-M3 必需文件和 hidden size 1024、Milvus collection/schema/ticker 与显式 pymilvus dependency 均已确认；旧 runtime model locator 仍失效；
4. [ ] **当前 Owner gate**：复核 18-row research qrels。接受后才建立 successor model locator 和 BGE/fusion evaluation authority；退回则只修被退回 qrel/corpus，不重跑来源链；
5. [ ] sparse／BGE dense／facet-aware fusion 同池对照；reranker 本机缺失，只有独立资源到位并证明增益才加入，不作为当前必需门；
6. [ ] current-quarter exact mart refresh、Evidence Gate→Claim→Workpaper→report utilization proof；external `4/12` 继续作为独立 release blocker。

机器真相分别为 `configs/releases/fin_ia_0_1_3_s1_internal_qrels_review_packet_v1_3.json`、`configs/releases/fin_ia_0_1_3_s1_internal_numeric_sql_qrels_observation_v1_0.json`、`configs/releases/fin_ia_0_1_3_s1_internal_dense_resource_qualification_observation_v1_0.json` 与推进计划 `configs/releases/fin_ia_0_1_3_s1_retrieval_query_facet_external_internal_progression_plan_v1_4.json`。本节不创建新版本，也不把资源存在写成 ranking 已通过。

## 8. 下一步

1. [x] 将 FIN 0.1.2 S4-T08 记为 `audit_complete_product_closeout_blocked`。
2. [x] 完成 FIN 0.1.2 S5 decision-only honest-block/freeze 包；`release_qualified=false`，没有机械执行 RG1–RG5。
3. [x] 完成 FIN 0.1.3 `013-S0-01` delta inheritance、旧 `0.1.3` namespace 分类和 secret-safe current truth baseline。
4. [x] 完成 `013-S0-02` shared runtime admission/replay、historical receipt/living source debt和 8 个 version-neutral candidate 复证。
5. [x] 完成 `013-S0-03` 四层金融语义 oracle；S0 canonical suite 29/29，通过的是分类与早期阻断，不是当前 DELL 真值。
6. [x] 完成 `013-S1-01` 主修与有界 freshness successor：annual/Q4 duration、四类时间角色和截至日之前 latest-available annual 都由本地确定性链拥有；RC-P36-130/135 关闭。
7. [x] 完成 `013-S1-02` current successor：三案 `25 base / 16 formula / 7 typed gap / 48 governed / 0 ungoverned`，并允许 S1-03 官方精确数值按 typed-gap digest 消解，不使用自由数字叙事。
8. [x] 完成 `013-S1-03`：R4 为 `10 source calls / 11 accepted / 6 attempt-backed gaps / 0 model`；组合后是 `27 exact / 16 formula / 5 gap / 9 semantic slots / 57 governed surface`。403 不冒充 source exhaustion，历史 R1–R3 保持 immutable。
9. [x] 完成 `013-S1-04`：MU/NVDA 共 7 条 current approved relationship edge，DELL 诚实 typed empty；所有 edge 非财务事实权威，旧 Workbench 空图历史未改写。
10. [x] 完成 `013-S1-05`：semantic successor=`7 useful / 2 typed gap`，governed retrieval=`9/9 query / 26/26 required candidate / 0 false promotion`，旧 BM25 明确 non-authority；S1 pass closed。
11. [x] 完成 `013-S2-01`：RC-P36-134 关闭；9 个 representative request 绑定 `26 Evidence / 2 gap / 18 mechanism / 18 WWC`，Provider 只选 alias/enum，本地拥有数字/日期/identity/lineage/final narrative；active suite 87 passed / 1 historical deselected。
12. [x] 完成 `013-S2-02`：RC-P36-138、显式 pack precedence、hermetic 注入、`9 Specialist / 9 Claim / 3 Lead` 零调用消费均通过；fresh exact-once DeepSeek canary=`3/3 pass, 10/10 each, 0 retry/0 fallback`，原始捕获与公开摘要分离。
13. [x] 完成 `013-S2-03`：审计 node context yield、重复 role view、Evidence 利用率、容量和成本；零调用编译与 mutation 通过，模型可见 bytes 改变后只执行一次最高负载单节点 natural reproof 并通过，未运行三案例 full-chain。
14. [x] 保留 `013-S3-01`–`013-S3-05` 与 R3 为 minimum engineering/control anchor：结构、exact-once、9 natural Claim、3 Lead、3 Workpaper、L1/L2 成立；0 thesis-support、0 natural counterevidence 与 29 个未研究 Cell 使其不构成产品级研究证明。
15. [x] 完成 DELL/MU/NVDA 三份 Codex-authored Gold candidate 与交叉订正；明确它们是混合研究候选，不是当前产品或完整 MCP 已独立产出的报告。
16. [x] 完成 `013-S2-04`：三案共享 Benchmark Evidence Pack、blind input 和 evaluator-only hidden Gold scoring objects 已按 digest 冻结，公平性、泄漏、跨案污染、日期和数值重算检查通过。
17. [x] 执行 `013-S2-05/06` Experiment A 并诚实终止：`013-S2-05` 三案 raw 均为质量失败；DELL Supervisor R2 暴露 RC-P36-148。`S2-06A/B/C` 已完成 canonical contract、统一 Runtime 与双 archive/process 独立 proof；`S2-06D` 最小 DELL/U3 natural canary 为 `1 call/1 capture/4,483 tokens/0 retry`，模型虽返回合法 envelope，却在反证为空时虚假声明 correction closed，新 guard 正确拒绝。`S2-06E` 已决定不值得且不授权正式 DELL proof；S2 deterministic repair 通过，model natural correction adherence 失败并流转 S3。下一步按依赖进入 S1 search tool/source runtime；formal score、业务晋升和 release 均未成立。
18. [x] 完成 `013-S0-04G / FIN_0_1_3_S0_04G_TYPED_BLOCKER_STATE_AND_RUN_SCOPE_REGISTRY_MINIMUM_ZERO_CALL_IMPLEMENTATION`：typed state、RunScopeRegistry v1.0、unknown fail-closed 与 post-adoption lineage 已实现；clean archive/fresh process=`85/85`，并以 predecessor proof 复证 R3 downstream compatibility。网络／模型／Provider／正式 admission／live=`0/0/0/0/0`，RC-P36-156 关闭。
19. [x] P2D 首个 candidate 的 transition-invariant defect 已保留；v1.2 clean requalification=`85/85` 后最终 P2D v1.1 通过。累计外部调用/admission/live=`0/0/0`。
20. [x] 以独立 Attempt 签发并执行唯一 DELL R3：`15 network / 0 model-provider-retry / 0 candidate / 5 gaps`；terminal/capture 完整但 candidate ceiling 失败，no-R4 生效。
21. [x] 完成零调用 `S1_08_P3_POST_R3_OWNED_SCHEDULER_CACHE_AND_PROVIDER_PRODUCT_SCOPE_DISPOSITION_DECISION`：选择 repair-first，Provider／产品来源范围 deferred，no-R4 与 16-call ceiling 不变。
22. [x] `S1_08_P3A_PROTECTED_DOCUMENT_FETCH_BUDGET_AND_ATTEMPT_LOCAL_CACHE_ZERO_CALL_IMPLEMENTATION_AND_PROOF`：A2 clean proof pass，P3A independently proven，外部调用、admission 与 live 均为 0。
23. [x] 实现并零调用证明 `S1_08_DIAGNOSTIC_BROAD_SEARCH_SEARXNG_ADAPTER_ZERO_CALL_IMPLEMENTATION_AND_PROOF`；clean v1.1 通过，失败部署尝试保留，SearXNG 仍不计生产能力。
24. [x] 执行一次 `S1_08_DIAGNOSTIC_BROAD_SEARCH_SEARXNG_BOUNDED_NETWORK_BASELINE`：三案均 terminal materialized，FIN→SearXNG=`3`、raw/unique locator=`30/30`、capture=`9`、model/retry/Evidence promotion=`0/0/0`；只有 DuckDuckGo 贡献结果，`published date=0/30`，因此结论为 `diagnostic execution pass / multi-engine and currentness quality fail`。运行后 Windows GBK 控制台显示失败不改写已原子保存的 UTF-8 终态，admission 已消费且未重跑。
25. [x] **候选付费 Provider 输入资格审查**：用户提供腾讯云 WSA AK/SK；官方文档、SearchPro schema、套餐能力、错误码、按量价格与 SDK `3.1.152` 已核对。candidate-only profile、secret-safe normalizer、exact-once hidden-input runner 与注册 scope 已通过零调用验证；唯一 DELL 单调用 authority 已签发未消费。凭据不落盘且运行后必须轮换；本项不构成生产能力。
25a. [x] **腾讯 WSA R1 immutable terminal**：clean `0b4d2eb8` 上一次 DELL SearchPro 返回 `InvalidParameter / illegal Mode`；`1 provider/network / 0 retry/model/document/Evidence / 276 ms / 0 locator`。官方文档称 `Mode=0` 合法，故登记外部文档/live drift 与项目 compiler 显式默认 optional field 的组合问题；未重试。
25b. [x] **Query-only replacement decision/engineering/authority**：Owner 新建子账号 API Key 并明确要求继续；独立 successor 只允许 wire body=`{Query}`，任一 optional field 在 transport 前拒绝。Project OS scoped preflight=`pass`、targeted=`15 passed`、外部调用=`0`，唯一 R2 authority 已签发未消费。
25c. [x] **Query-only replacement exact-live terminal**：clean `ff25e92f` 上只发送 `Query`，1 provider/network、0 retry、129 ms；腾讯返回 `AuthFailure.SignatureFailure`，0 locator/date。Mode compiler 已绕开，但鉴权先失败，故 CAM、服务开通和搜索质量仍未证明；R2 immutable、未自动重试。
25d. [x] **exact-copy AK/SK R3 zero-call authority**：Owner 看见 R2 terminal 后以直接文本提供另一组 standard AK/SK 并明确要求再试。建立 distinct R3 successor，绑定 immutable R2 result/assessment，wire body 仍只有 `Query`，credential 仅 hidden runtime input；focused=`21 passed`、Project OS scoped preflight/compile pass，provider/network=`0/0`。唯一 R3 authority 已签发未消费；提交推送 clean head 后才允许 1 次 live，0 retry，任何终态均停止且不自动 R4/comparator/integration。
25e. [x] **exact-copy AK/SK R3 terminal 与质量处置**：clean/synced `b9dfa025` 上唯一 R3 exact-once 成功，`1 provider/network / 0 retry/model/document/Evidence / 1036 ms`，返回 `lite / 10 unique locator / 10 provider date`。鉴权、TC3、服务、Query-only schema、capture/normalizer 均 pass；但 8 条为 Dell driver/support 页面、2 条为无关第三方排障，冻结 AI-server 研究意图的 research-useful=`0`，date authority=`0`。因此只把 authentication/service path 记为 qualified，locator quality fail；不自动 comparator、integration、R4 或产品晋升。
25f. [x] **standard-tier R4 zero-call authority**：Owner 声明元宝搜索已切换 standard 并批准一次同-query recheck。R4 绑定 immutable R3，只改变 subscription tier，冻结同 credential path、同 DELL Query-only、SDK、endpoint、normalizer 与 result ceiling；相关=`37 passed`、Project OS/compile pass，外部调用=`0`。唯一 R4 authority issued-unconsumed，预算 `1 call / 0 retry`；失败只进入 DELL/MU/NVDA 中英 Evidence-Slot comparator 设计，不自动执行或接入。
25d. [ ] **Credential/auth-mode decision**：删除聊天中暴露的新 Key；Owner 另行选择“精确复制的新 AK/SK 隐藏输入”或“WSA service API Key/Bearer 零调用资格审查”。第三次请求、三案 comparator、SourceHunter integration 和 production 均未授权。
26. [ ] Provider 对照后由 Owner 单独决定 production Provider／source claim／no-R4；在此之前不命名或签发新 DELL product-live，也不重跑 SearXNG。
27. [ ] 在冻结 Evidence Pack 上完成 `DS-A1/A2/A3` ModelCapabilityProfile、DeepSeek profile、AutonomyGrant 与最小 natural canary；可做零调用准备，但在 S1 candidate ceiling 未解锁前不得进入 S3 formal run。
28. [ ] 完成 `013-S3-06–09`：动态 Lead loop、研究方法 runtime injection/node consumption、EvidenceRequest/targeted repair、三案 Experiment B、隐藏 Gold 八维对照、paired gain 与 qualified-human 内容验收。
29. [ ] 执行 FIN 0.1.3 current S4 Workbench dogfood，再执行 S5 RG1–RG5；只有内容合格的 current candidate 可获得 FIN 0.1.3 内部版本收口结论。

> **2026-08-07 `013-S1-06` 已 `L4_scope_pass`**：根因审计确认 registry 有 9 个业务工具而 stdio server 只暴露 6 个；SEC handler 即使 `rerank_budget=0` 仍强制加载 Linux 默认 BGE 路径，约 56 秒后才失败。结构包已完成 server/registry parity、版本化 canonical resource profile、显式 BM25-only operational mode、可复用进程 supervisor、cold/warm/phase receipt、timeout/cancel/process-tree no-orphan 以及 typed missing-reranker failure。focused/broader=`23/53 passed`、stdio=`10 tools`；clean/synced `ab638c38` proof 全过，SEC cold/warm=`13,750/104 ms`、Exact Ledger=`1,317 ms`、market=`3 ms`，missing reranker 在 handler 前约 `1 ms` typed fail，close 后 no orphan。RC-P36-140 closed。S1-07/08、BGE/Milvus 质量、外网 current-source acquisition 与模型调用仍未开始；当前下一项仅为 `013-S1-07`。

> **2026-08-07 `013-S1-07` engineering implementation 已完成、clean canary 待执行**：没有新造平行 crawler，而是将 S1-03 已验证的 capture-first、allowlisted HTTPS transport、HTML/PDF/JSON parser 与 content-addressed store 接到 MCP `web_evidence_snapshot`。新增 verified company-domain gate、public-network/SSRF 防护、跨域/3-hop redirect、16 MiB/120 s 上界、raw request/response、parser/promotion capture 和 typed gap。公司官方/IR、监管/政府 parsed source 可按边界晋升；news/commerce/social 只保留 context-only；web parser 不拥有 exact numeric authority。broader=`82 passed`，model/provider/network=`0/0/0`。下一步只允许 clean/synced commit 上一次 DELL/MU/NVDA 官方来源 exact-once canary；失败留在 S1-07，不进入 S1-08。

> **2026-08-07 `013-S1-07` R1 exact-once canary immutable fail**：3/3 调用均在 HTTP 前被 private-network guard 拦截，因为当前执行环境把三家 IR hostname 映射为 RFC 2544 `198.18.1.52/53/54`；3 request + 3 failure captures、admission terminal 和 no-orphan 均成立，0 retry。该共同失败归类为 synthetic-DNS environment compatibility，不归因来源、parser 或 DeepSeek。只做一项有界修复：runner 自动识别“全部显式 allowlist hostname→198.18/15”并启用受控 transport mode，其他 private network 保持拒绝；随后 new commit/new admission 执行一次 R2，R1 不覆盖。

> **2026-08-07 `013-S1-07` R2 partial live success**：MU official PDF 与 NVDA official IR HTML 均真实 fetch/capture/parse/promote；Dell IR PDF 单源在 30 s 内未返回并 typed `official_source_transport_failed`。不重跑两条成功路径、不扩大 timeout、不修改 parser；只新增一个 1-call Dell SEC official HTML fallback successor。若该 fallback 通过，三案合并关闭 S1-07；若失败，立即停止并保留 blocker，不进入更多轮次。

> **2026-08-07 `013-S1-07` bounded stop**：Dell-only SEC fallback 返回 HTTP 403，capture 原文明确为 `Undeclared Automated Tool`；不是正文 parser 问题。至此 MU/NVDA=`fetch+parse+promote pass`，Dell=`IR timeout + SEC client-identity rejection`，S1-07 只能记 `2-of-3 partial`，不得进入 R4/S1-08。下一步需单独决定 SEC-compliant audited contact User-Agent 或 Dell IR browser/CDN adapter；未经该决策不再调用来源。

> **2026-08-07 `013-S1-07` 最终 `L4_scope_pass`**：用户选择 runtime-only SEC contact identity；实现对 SEC 域名 missing/invalid contact fail-closed，并保持明文不进入 Git/result/admission。clean/synced `86779fd8` 上只执行一次 Dell successor：SEC official 10-K HTML 在 `14,027 ms` 内完成 fetch/capture/parse/promote，`1 Evidence / 0 gap / 0 retry / 0 model/provider`。与 R2 immutable MU PDF、NVDA IR HTML 成功结果合并，三案 official-source runtime 全部成立；result v1.3 terminal=`three_case_official_source_runtime_proven`。下一项进入 `013-S1-08`，只评测检索召回、排序、时效、来源多样性和证据利用；S1-07 不宣称 Research、DeepSeek 或报告质量通过。

> **2026-08-07 `013-S1-08` entry audit 通过但 upstream blocked**：已冻结 2026-08-06 三案 Gold-slot 搜索评测合同，规模=`10 source / 33 Evidence / 32 mandatory / 12 target groups`；target-in-pool、recall@8、currentness、diversity/reconciliation/selected-pack coverage 与 false-promotion 均为 hard gate，Gold expected insight/evidence ID 不得进入 planner。当前 governed/live 合并仅 7 个 distinct URL，与 9 个 benchmark HTTP source exact overlap=`0/9`；该值是保守下界，不否定替代权威来源。现有 executable Agentic Search 仍是 FIN 0.1.2 合同且没有 query revision，因此不允许计算/调优 NDCG、MRR、BGE 或 Milvus。RC-P36-154 留在 S1-08；下一包只实现 current source catalog、candidate generation、query revision 与 evaluator-only Gold matcher，full-fake/mutation 后再决定 live canary。

> **2026-08-07 `013-S1-08` candidate-generation engineering proof 通过、live ceiling 未证明**：current source catalog 只保存公司身份、CIK、官方 landing page、ecosystem role 与通用 evidence-role blueprint，不含 Gold ID、expected insight 或 benchmark document URL。Runtime 已实现 research-objective→五类 evidence query、每 target 最多两次有理由 revision、cross-case/future/unpromoted/missing-lineage fail closed；具体 official adapter 已覆盖 landing/SEC discovery、source capture、parser capture 和 candidate promotion，local market snapshot 也要求受控 capture，且发布时间/authority 不符的 stale snapshot 不得匹配 current Gold。三案 evaluator fixture pool=`DELL 6 / MU 7 / NVDA 7`，12 target 的 target-in-pool/selected coverage=`1.0/1.0`；focused/broad=`15/33 passed`、external calls=0。该结果只证明工程 ceiling，不证明真实网络发现能力；NDCG/MRR/reranker 继续不准入。下一步为 clean commit proof 后一次 DELL current-search canary authority decision，不自动执行三案或进入 S3。

> **2026-08-07 `013-S1-08` DELL canary pre-admission block**：exact-once runner 已在 clean/synced `a179fe41` 通过，Project OS scoped preflight pass、related=`37 passed`。但当前 Codex 进程没有 `FINSIGHT_SEC_CONTACT_EMAIL`，而 DELL source discovery 必须访问 SEC submissions；因此在 admission/ledger/network 之前 fail closed，observed=`0/0/0`，历史聊天明文未复制到命令或版本化产物。该结果不是 live search 失败。重新从带有效 runtime env 的父进程启动 Codex 后，可复用同一工程签发一份 fresh admission；MU/NVDA/ranking/S3 仍不授权。

> **2026-08-07 `013-S1-08` formal runner readiness**：重启后 runtime SEC contact 已就绪；复核发现此前所谓 runner 只有模块和测试，没有正式 CLI/结果物化，现已在 S1-08 原阶段补齐，并修正 terminal 完成时间与异常网络计数。focused=`19 passed`、related=`52 passed / 1 known S0-02 historical mutable-source-SHA failure`；联系方式未进入版本化产物。下一步只允许 clean commit/push、scoped Project OS preflight 和一份 DELL exact-once admission；真实 candidate ceiling 不足仍阻断 ranking，不自动扩到 MU/NVDA 或 S3。

> **2026-08-07 `013-S1-08` DELL live R1 terminal**：唯一 admission 在 clean/synced `09387ebd` exact-once 消费，`19` 次来源调用、`212 s` 后因未包装的 `RemoteDisconnected` 终止，模型/Provider/retry=`0/0/0`。受限 capture 保留 `19 request / 15 response / 3 typed transport failure / 13 parser`，但最后请求缺 failure capture，partial candidate/typed gap 未正式物化。审计同时证明 locator currentness/质量不足：Microsoft IR 导航噪声被抓取，DELL SEC 选到 2022/2023 旧 filing。R1 不重跑，candidate=`0` 不得解释为来源不存在；下一步只做一个 captured-replay 零调用结构包，统一 transport termination、source-family/path/date filter、partial terminalization 与效率上限。replacement DELL、MU/NVDA、ranking 和 S3 均需后续独立决定。

> **2026-08-08 `013-S1-08` 质量优先 SourceHunter × Capture Replay 统一升级计划**：用户纠正“只做兜底逻辑”的偏差后，下一项不再拆成 crawler quality 与 replay 两条松散路线。R1 immutable captures 将同时驱动 Evidence Slot planner、多通道 provider-neutral discovery、fetch 前 source-family/path/title/entity/form/date/currentness/slot-fit 过滤、fetch 后正文质量与 promotion、typed transport、partial terminalization 和效率门。计划拆成 `S1-08Q-A..H`，但 `A..G` 必须作为一个零调用实现/证明包完成；`H` 仅为 clean proof 后的独立 replacement authority decision。硬门新增 R1 全请求终态分类、导航噪声零 fetch、stale filing 零误选、partial materialization 100%、五类 Evidence Role candidate-or-gap 全覆盖、qualified-document yield `>=0.5`，并保留既有 target-in-pool/recall/currentness/diversity/reconciliation/false-promotion 门。拟议 DELL R2 为 `<=16 network / 0 model / 0 provider / 0 retry`；本计划本身不授权 R2、MU/NVDA、ranking 或 S3。机器合同=`configs/releases/fin_ia_0_1_3_s1_08_quality_first_sourcehunter_capture_replay_integrated_upgrade_plan_v1_0.json`。

> **2026-08-08 `013-S1-08Q-A..G` 零调用工程实现通过、clean 独立复证待执行**：v2 catalog/runtime 已将五类 role 编译为 Evidence Slot，声明 SEC/普通 IR/local-market 的真实 operational route；structured-IR 尚缺 feed/sitemap locator adapter、external-site-search 尚缺运营 Provider，两者明确 unavailable。抓取前按 source family/path/title/form/date/as-of/slot fit 去除 Microsoft 导航、商店和产品噪声并优先 current SEC filing，抓取后再做正文研究角色 gate。连接终止统一 typed capture，attempt 后 content-addressed checkpoint，unexpected failure 保留 formal partial result。R1 restricted objects=`19/19` digest verified、raw/header 不输出；sanitized replay 的 unpaired/noise/stale=`0/0/0`、五 role closure=`5/5`，qualified-document yield 使用 discovery＋document fetch 的真实总调用分母，为 `6/11=0.545455`。focused/related=`46 passed`、materializer byte-identical，且历史 v1 revision-one SEC widening保持不变；external calls/admission=0。当前只到 engineering pass，下一项为 clean archive/fresh-process 独立复证；不自动进入 Q-H、DELL R2 或 ranking。

> **2026-08-08 `013-S1-08Q-A..G` clean 独立复证通过**：`ee5ebf3b...17925` 的两个 Git archive、两个 fresh process 各=`46 passed`，restricted R1 request objects 每边=`19/19`；重物化 proof SHA 与仓库一致。首次 archive 暴露 CRLF/LF byte portability defect，修复后从新 commit 重新双复证通过。A..G 现为 `independently proven`，但这不是 live source-quality 证明；下一项只有 Q-H replacement authority decision，不自动签发/执行 DELL R2。

> **2026-08-08 `013-S1-08Q-H` DELL R2 replacement authority decision**：scoped Project OS preflight pass 后批准最多一次 DELL R2，预算=`<=16 network / 1 doc per query / 0 model-provider-retry / no automatic R3`。旧 R1 result path 已占用，旧 admission 又不绑定 Q-H decision/independent proof，因此当前 `approved but not issuable`；下一项只实现 R2 successor admission/runner 的零调用 binding，之后才能重新 clean preflight、签发和执行。

> **2026-08-08 `013-S1-08` DELL R2 successor engineering pass**：首轮 binding test 发现 Q-H v1.0 的 proof SHA 标签错误，v1.0 未消费即 supersede，v1.1 分开绑定 engineering 与 independent proof SHA。R2-only admission/terminal/namespace/result path、R1 terminal body 重算、decision/proof/catalog/commit binding、shared-ledger-before-DNS、30/300 秒预算和 exact-once 均完成；focused/related=`52 passed`，外部调用/admission=0。下一项仅为 clean-commit zero-call preflight。

> **2026-08-08 `013-S1-08` DELL R2 successor clean preflight pass**：clean `27d31315` fresh archive=`53 passed`，Runtime/Runner SHA 已进入必需 proof artifact，R1 exists/R2 absent、外部调用/admission=0。发现 Project OS 对未知 run-scope 字符串不会天然 fail closed；本 R2 用 direct proof/source binding 补强，通用 scope registry 问题后传共享治理阶段。当前仅一份 DELL R2 eligible，不自动放行其他案例或 ranking。

> **2026-08-08 `013-S1-08` R2 preflight-shape repair**：第一次 execution probe 因 runner 读取 CLI compact-only blocker count 而在 admission 前失败，外部调用=0；核心 API 实际以 blocker list 为权威。修复后 clean `e48ec1b3` fresh archive 仍=`53 passed`，v1.1 proof 重绑新 Runtime/Runner SHA，v1.0 未消费即 supersede；唯一 R2 eligibility 保持。

> **2026-08-08 `013-S1-08` DELL R2 terminal / source-quality failed**：唯一 exact-live 完成 `16 network / 0 model-provider-retry`，终态与 partial/gap capture 完整，但 accepted=`2` 仅对应 1 份 unique DELL 8-K，customer/supply/market 三 role 为 gap。qualified yield=`0.125<0.5`，四组 DELL hidden target 的 target-in-pool 与 selected coverage 均为 0，ranking 不准入。失败归属 operational source coverage/locator，不归因 DeepSeek；不自动 R3，下一项为 S1-08 post-R2 provider/candidate coverage disposition。

> **2026-08-08 `013-S1-08` post-R2 provider/candidate coverage disposition 已选定**：零调用 replay 把失败继续拆到最早责任面：16 次调用中 customer slot 独占 12 个 document fetch，supply slot 为 0；`document_ceiling_per_query=1` 实际只限制 accepted candidate，未限制 fetch；Microsoft 下游客户故事缺少关系方向约束；两个明确写出 `July 29, 2026` 的官方 release/event 页未被当前日期 parser 识别；同一 DELL 8-K 的两个 role binding 又把 unique-source yield 从真实 `1/16=0.0625` 记成 `2/16=0.125`。下一包固定为官方 IR feed/sitemap、official-domain bounded search、SEC 20-F/6-K、typed publication date、relationship-aware Evidence Slot、round-robin reservation budget 和 canonical source/role-binding 分账的一次零调用实现；全局 16 次暂不增加，`external_site_search` 在无真实 Provider 时继续 unavailable。只有 replay＋三案 mutation 通过后才另行决定 fresh live；本决定不授权 R3、MU/NVDA、ranking、DeepSeek 或 S3。

> **2026-08-08 `013-S1-08` mature-component v3 零调用工程通过**：在不联网、不调用模型/Provider 的前提下，`feedparser 6.0.12` 与 `Trafilatura 2.1.0` 已以“消费 immutable capture、没有网络权和 promotion 权”的方式接入；FIN 本地 Runtime继续拥有日期、关系方向、预算、lineage 和 Evidence 晋升。真实 R2 两份 Microsoft capture 证明 Trafilatura 能明显减少导航词噪声，但会把 `2026-06-30` 报告期误判为 press-release 日期；typed adjudicator 已正确选择两页的 `2026-07-29`，并拒绝 reporting-period/library-only date。v3 还完成官方 feed/robots/sitemap、SEC `20-F/6-K`、nested-customer fetch 前拒绝、五 slot round-robin、每 attempt `2 fetch/1 unique accept`、source-document/role-binding 分账及本地 market 分母隔离；v1/v2 历史 serialization 保持不变。focused＋既有回归=`48 passed`，三案 fake slot starvation=`0`。当前仍只是 engineering pass：feed/sitemap/bounded-domain route 尚无 fresh live proof，broad `external_site_search` 仍 unavailable，target-in-pool/ranking/S3 均未解锁；下一步只能先做独立零调用复证，再另行决定一次 fresh live authority。

> **2026-08-08 `013-S1-08-P1` v3 clean independent zero-call proof 通过**：clean/synced `a3f15fa2` 上两个 Git archive、两个 disposable root、两个 fresh Python process 各=`60 passed / 0 failed / 0 skipped`；每边只读核验 R1 request objects=`19/19`、R2 content captures=`2/2`，依赖版本和两页 `2026-07-29` 日期裁决一致，DELL/MU/NVDA fake/mutation 复现，normalized output SHA 相同。A1 在旧 commit `2cdb09ce` 因漏注入 R1 objects 为 `59/1`，已保留为 proof-input assembly failure；Runtime 未改。P1 只把 deterministic engineering 提升为 `independently_proven`，fresh reachability、target-in-pool、ranking、研究内容与 release 仍未证明。当前下一项仅为 `S1_08_V3_DELL_FRESH_LIVE_AUTHORITY_DECISION`，本 proof 没有签发或执行 live。

> **2026-08-08 Project OS scope-policy 负向复核**：三个在 RC-P36-157 中显式禁止的 live/ranking/S3 scope 最初仍被预检误报为 `pass`。根因是共享实现只识别固定五种开放状态，描述性 `open_*` 状态在 scope 匹配前被跳过。当前以 RC-P36-156 canonical `open`＋wildcard block＋本零调用实现 allowlist 恢复即时 fail-closed；共享状态 schema/run-scope registry 仍归 S0/S5。任何后续 live 必须继续由 exact runner/admission 直接绑定，不能把一次 Project OS `pass` 当成充分权限。

> **2026-08-07 用户已选择 SEC contact 路线**：真实联系身份只通过运行时环境注入，不进入 Git 或结果物；SEC 域名无合法 contact 时 fail closed。新增 identity mutation 后 broader=`84 passed`。只授权 new admission 的 1-call Dell SEC v1.3 proof，复用 MU/NVDA 已成功结果；不重跑三案、不进入额外 fallback。

> **2026-08-06 S5 交接发现**：仓库中存在早先已被合并/放弃的 47 个 `FIN 0.1.3` 命名 config/runtime/test 资产，0.1.2 active-suite 仍有 7 个相关引用。它们必须保留为历史证据，但不能自动成为本轮新 0.1.3 authority。`013-S0-01` 必须先签发 canonical delta namespace/inheritance successor，再开始其他实现。

> **2026-08-08 `013-S1-08` Tencent standard R4 与三案中英 comparator**：standard same-query R4=`1 call / 0 retry / 971 ms / 0.046 CNY`，`Version=standard`；topical useful=`10/10`，但 Evidence-eligible useful=`0/10`、DELL target group=`0/4`、有效独立来源生态=`1`，故不接入。下一步不再做单 query R5，而是 exact-once 消费已签发的 `3 case × 4 external Evidence Slot × 2 language=24` comparator，0 retry/model/document/Evidence，成本上限 1.104 元。查询生成阶段看不到 Gold；全部调用 terminal 后才计算 topical/Evidence useful@10、target-in-pool、hidden target recall、日期准确率、来源多样性、成本和延迟。任何门失败都保持 diagnostic-only，禁止 reranker rescue；通过也只允许后续独立 integration decision。

> **2026-08-08 `013-S1-08` Tencent comparator 终态与重新规划**：唯一 24-query comparator 已 exact-once 完成，24/24 standard、0 retry/model/document/Evidence、1.104 元、p95 941 ms；topical useful=`110/240`，但 Evidence-eligible=`0/240`、case-slot target-in-pool=`0/12`、hidden target group=`0/12`。中文优于英文但没有转化为一手目标，日期字段 155/155 存在却因 0 exact target 无法验证。Tencent 保持 diagnostic-only，S1-08 candidate coverage blocker 继续 open；删除 Tencent R5/query patch/reranker rescue 路线。下一项改为 Owner 在“另一 broad-search Provider 使用同 comparator 资格审查”和“显式缩减 Internal Alpha source claim”之间做产品决策；两者决定前 S2/S3 live、Workbench product acceptance 与 S5 release 均不解锁。

> **2026-08-08 `013-S1-08` Provider 市场扫描与 Firecrawl keyless 有界试跑完成**：官方文档横评确认搜索服务至少应拆为 precise official/SERP lane、semantic open-web lane、document crawler/extractor 与 synthesized research benchmark。Firecrawl capture-first A2 issuer/regulatory=`6/6 terminal, exact target 3/6`，A3 official-domain=`3/3`，A4 customer/supply generic=`6/6 terminal, exact target 0/6`；合计 30 credits、0 model/document/Evidence。A4 暴露项目内共同根因：current catalog 已有 MSFT/TSMC/MU/DELL/NVDA counterpart role，`compile_initial_queries()` 也计算 `entity_keys`，但 provider-visible query 没有投影 evidence owner alias 和 claim direction；旧 24-query bilingual plan 同样使用 subject-company＋通用 slot 词。故上一条“直接换下一 Provider”的计划被新证据修订：先在 S1-08 原地完成 `S1_08_PROVIDER_NEUTRAL_RELATIONSHIP_AWARE_SEARCH_INTENT_COMPILER_AND_SOURCE_EQUIVALENCE_EVALUATOR_ZERO_CALL_IMPLEMENTATION`，三案 fake/mutation 通过后再跑一次 Firecrawl 24-query comparator。若仍需新 Key，顺序为 Exa semantic complement，再用 Serper/DataForSEO 做 exact SERP control；不在修复前盲测多家 API，不缩减 source claim，不解锁 S2/S3/S4/S5。

> **2026-08-08 `013-S1-08` 国内凭据 readiness 与 Firecrawl semantic control runner 完成**：仅按变量名确认 Tencent/Baidu/Alibaba fresh credential 当前均不可用，未读取或保存值，也不复用聊天暴露 Key。选择新查询矩阵中的 customer/supply `24 semantic` 单 lane，22 precise 与 combined 46 均不授权；原因是该 lane 直接复验旧 A4 `0/6` 的 evidence-owner/direction 查询缺口。exact-once runner、raw capture-first、systemic auth stop、24-identity terminal 和 post-terminal Gold evaluator 已实现；plan=`24 intent/24 unit/3 case/2 slot/2 language`，digest=`3d636459...d9e19`，full-fake/mutation=`8 passed`，外部调用=0。下一项只允许从 clean implementation commit 签发唯一 24-call Firecrawl authority；控制组通过也不建立国内 Provider、SourceHunter、S1-08、S3 或 release 能力。

> **2026-08-08 `013-S1-08` Firecrawl relationship-aware semantic control 终态**：唯一 authority 在 clean `db427ee4` 消费，24/24 terminal success、48 credits、235 locator、0 retry/model/document/Evidence；topical=`133/240`、customer/supply case-slot target=`5/6`，旧 generic A4 为 `0/6`。由于新矩阵为 24 条 owner-fanout 中英查询，差异不冒充单变量 A/B，但足以将 query compiler 记为 live-supported。Firecrawl 本身因 DELL supply prepared-remarks exact miss、date=`0/235`、中文 exact target=0、四条 useful<0.3、p95=`6877 ms` 而 fail diagnostic-only。no-R2/no-query-patch/no-reranker/no-precise-expansion 生效；下一项等待 fresh 国内 Key，执行 `S1_08_DOMESTIC_PROVIDER_FRESH_CREDENTIAL_READINESS_AND_SAME_MATRIX_COMPARATOR_AUTHORITY_DECISION`。S1-08、ranking、S3/S4/S5 继续 blocked。

> **2026-08-08 `013-S1-08` Tencent relationship-aware same-matrix authority**：新凭据只做 presence-only readiness；24 条 Tencent semantic query 与 immutable Firecrawl control 逐字一致。zero-call runner/evaluator 在 clean/pushed `9a0040e1` 固化，S1-08=`199 passed`；唯一 admission 已签发未消费，成本 ceiling=`1.104 CNY`，provider/network=`24/24`，retry/model/document/Evidence=`0/0/0/0`。下一项只执行一次 exact-live；通过也不自动接 SourceHunter，失败也不自动逐 query 修补或重试。

> **2026-08-08 `013-S1-08` Tencent same-matrix terminal**：24/24 standard、0 retry/model/document/Evidence、1.104 元、p95 1,330 ms；但 topical=`103/240`、六个 case-slot frozen primary target=`0/6`，显著弱于同矩阵 Firecrawl 的 `133/240` 与 `5/6`。172/172 provider date 因无 exact target 不能验证准确性，主要结果来自聚合/社区站点。Tencent 保持 diagnostic-only，不接 SourceHunter、不做 reranker rescue/query patch/replacement。下一项只做 provider portfolio 与 production search 边界决策，S1-08 与后续阶段继续 blocked。

> **2026-08-08 `013-S1-08` Provider portfolio boundary selected**：纠正单一 broad Provider 全职责门槛，选择 official-first、role-specific portfolio。SEC/IR/feed/sitemap/official-domain 负责 known primary；Firecrawl 仅作为 discovery shadow 候选；Tencent 维持 diagnostic-only；Provider date 只作 telemetry，本地 capture-backed date 与 Evidence Gate 不放宽。暂停新 Provider 采购/live，下一项先完成组合 route planner、immutable replay、三案 mutation 和 SearchQualityCard 的零调用实现。S1-08、ranking、S3/S4/S5 仍 blocked。

## 7M. Owner qrels 接受、R2 ranking 结果与 dense refresh 接力（2026-08-09）

Owner 已接受 18/18 research qrels，local ranking 得到一次真实执行资格。R1 因 namespaced evidence identity 在首个 `::` 被错误截断而失效，失败结果和 18 条 collision 审计保持不可变；修复只收窄 identity canonicalization，未改变 qrels、queries、filters、budgets 或 fusion weights。

有效 R2 的 sparse／dense／fusion Recall@10 分别为 `16/18、3/18、14/18`，MRR@10 分别为 `0.51111111、0.16666667、0.28201058`。fusion 低于 sparse，故当前保留 sparse，不准入 fusion。后续 read-only 诊断证明 10 个唯一目标只有 5 个进入旧 Milvus；18 行里 8 行是 index freshness gap，另有 7 行属于已在索引但语义排序未达到 top10／top24。

下一顺序据此重新冻结：

1. 只从 capture-backed supplemental current documents 建立 immutable dense successor，并与历史 662,908-vector collection 联邦；禁止覆盖旧索引；
2. 先达到 selected target physical presence=`10/10 unique`，否则不得再跑 dense/fusion；
3. presence gate 通过后只做一次 same-matrix ranking successor，不按 Gold 调权重；
4. 若 dense/fusion 仍弱，sparse 继续作为候选基线；query formulation 和 reranker 另立实验，reranker 不静默下载；
5. 独立完成 current-quarter exact SQL `0/6` refresh；
6. 之后才做 Evidence→Claim→Workpaper→Report 的下游利用和内容质量证明；
7. external official `4/12` 仍是独立 release blocker，只有新 Provider 按冻结矩阵通过或 Owner 明确缩减产品来源承诺才能关闭。

这里没有新建产品版本，也没有把 S1 的缺口传给 S2/S3。dense index freshness 和 semantic retrieval 都留在 S1；研究综合与最终报告质量仍由 S3/S4 承担。

## 7N. Supplemental dense 零调用通过后的执行接力（2026-08-09）

两份 current supplemental manifests 已在 qrels 不可见的编译阶段产生全量 410 条 vector specs。零调用 full-fake 证明 13 个 batch 可精确终态 410，旧库写入 0，8 类 mutation 全部 fail closed；历史 5 个已存在 unique targets 与 supplemental 5 个缺失 targets 合并后，presence projection 为 `10/10 unique、18/18 rows`。

下一顺序冻结为：

1. clean commit/push 当前 policy、compiler、proof、tests 与文档；
2. 单独签发一次 `S1_INTERNAL_CURRENT_CORPUS_AND_INDEX_REFRESH` incremental-build authority，精确绑定 clean commit、410-vector terminal digest、本地 BGE locator、1024 维、新 DB 路径和新 collection；
3. 只执行一次本地 embedding＋new Milvus build，0 network/provider/LLM/document/rerank/Evidence、0 retry，不覆盖旧库；
4. 真实构建后只读复证 exact entity count=410、lineage 和 federated selected-target presence=10/10；
5. presence 通过仍不自动运行 ranking；另行签发一次 unchanged-matrix successor 后才可判断 Dense/Fusion 是否改善；
6. 如果 Dense/Fusion 仍低于 sparse，继续保留 sparse，把 query-semantic 与可选 reranker 分成后续受控实验，禁止围绕 Gold 反复调权；
7. current-quarter exact 0/6、external official 4/12 和 downstream content-quality proof 继续分账，不塞进本次 index build。

本项仍为 FIN 0.1.3 S1 原地修复，不创建 FIN 0.1.4，也不把 S1 根因传给 S3。

## 7O. Ubuntu Milvus、业务语义错误账本与外源补源重排（2026-08-09）

用户补充确认本机已有 Ubuntu／WSL，可用于判断 supplemental dense R1 是 Windows portability 问题还是项目 Writer 本身的问题；同时要求此后检索汇报不仅给总分，还必须说明每条失败在金融业务上“搜到了什么、为什么不对”。另确认外源检索不是取消项，而是在本地检索和工具链稳定后，由本地真实残余缺口驱动的补源层。

本轮只允许一个 1-vector、零 BGE、零网络、零模型的 Linux 可移植性 canary，完整执行 create／insert／double flush／close／reopen／count／metadata query，并同时递归绑定 `pymilvus` 与实际执行持久化的 `milvus-lite` 包。首个环境启动若在进入 Milvus 前失败，必须单独保留为 dependency-bootstrap attempt，不能覆盖后伪装成数据库成功或失败。

R2 的排序结果仍对 qrels v1.3 有效，但产品解释必须更新：dense `3/18` 中 8 行是目标未进入旧索引，另外多为同公司同期间内通用材料挤掉具体证据，并非简单的“搜到别家公司”。同时至少两条 NVDA supply 目标预览从联系人／免责声明开始，说明 Owner 接受 ranking label 不等于 Evidence-content 通过。下一次正式 ranking successor 前先执行 qrels 业务语义复核；旧标签不删除、不静默改写，问题行只允许扩邻、替换或退回 typed gap，并保留 supersession lineage。

更新后的 S1 顺序为：

1. 完成 Ubuntu／WSL Milvus 1-vector portability qualification，并记录 dependency bootstrap 与真正 storage path 的不同终态；
2. 物化逐 qrel 业务语义错误账本，先复核联系人、免责声明、页头、泛化章节等弱 Gold；
3. 在 Linux runtime、完整依赖指纹和 fresh authority 成立后，才允许一个新的 410-vector immutable replacement build；
4. 只读证明 410 entities 与 requalified target physical presence 后，运行一次 unchanged-matrix sparse／dense／fusion successor，并逐行解释失败；
5. 补齐 current-quarter exact SQL、graph 和本地工具调用，形成逐 Evidence Slot residual gaps；
6. 用这些 gap 回到 external official／broad supplement，沿用同一 Query Facet，重新关闭 external `4/12` blocker；
7. 本地＋外源 Evidence Pack 统一通过 Evidence Gate 后，才进入 Claim／Workpaper／Report 的研究内容质量证明。

这次重排既不创建新版本，也不把 external 永久后传。Milvus Linux canary 通过只证明嵌入式存储可用，不代表 410 构建、dense 质量、外源补源、研报质量或 S1 通过。

## 7P. 18-row qrel 全文复核后的 Owner gate（2026-08-09）

18 行 accepted qrels 已逐条读取完整正文、target facets 与同 bundle 冻结候选。结果不是“又有一批 qrel 作废”：`18/18` 仍满足 candidate-level ranking relevance；但只有 `4/18` 单候选完整覆盖目标 facets，`14/18` 只覆盖部分业务面。后续研报必须由多个本地候选、外源补源和 Evidence Gate 共同补齐，不能把 `18/18 target-in-pool` 解释为资料充分。

上一轮对两条 NVDA supply 的判断被精确修正：截断 preview 的确先显示联系人和免责声明，但完整 chunk 后半部明确写到第三方制造、组装、封装和测试依赖。因此问题属于切块精度与模板噪声，不是内容完全不存在。冻结候选池已有更干净的同源 child claim。类似地，三条 MSFT demand 宽段落后半部确有 AI 基础设施投入和 AI 使用增长，但同池判断原子能更直接代表目标。当前提出 5 个 candidate identity replacement，另外 13 行保持不变。

第一次准备签发该复核包时又发现：R7 中 NVDA child claim 的正文和 accession 虽正确，URL 却继承母 8-K，而不是实际承载正文的 Exhibit 99.1。该投影缺陷留在 S1 原地修复；R8 只把相应 candidate URL／lineage 改为 `q1fy27pr.htm / exact_accession_exhibit`，候选数量、rank 和 typed gaps 均未变化。今后 child-claim replacement 必须同时通过内容和可点击来源血缘，母 filing URL 不得代替实际被引附件。

接续顺序改为：

1. Owner 只确认或退回上述 5 个替换，不重复审核 13 个不变标签；
2. 确认后物化 qrels v1.4 successor，并继续禁止 Evidence promotion；
3. 完成 WSL BGE/GPU、Python、`pymilvus`、`milvus-lite` 与 Linux DB path 的完整 production binding；
4. 再决定并执行唯一 fresh 410-vector immutable build 与只读 10/10 presence proof；
5. presence 成功后另行决定 unchanged-matrix ranking，不自动从本包进入 ranking；
6. current-quarter exact、graph／tool、external `4/12` 和下游研报质量仍按既定顺序分账。

本项是 FIN 0.1.3 S1 的 Gold／evaluation target 质量修复，不创建新版本、不重跑旧 R2，也不把完整 Evidence Slot 的资料充分性责任错误压到单条 qrel 上。

## 7Q. 三案例尸检后的金融研究泛化纵切（2026-08-09）

三案例 A／B／external replay／C 证明，直接继续 410-vector build 会把已有 source／chunk／query 形状固化，而不会自然得到完整 Evidence Pack。原 7P 的 5 个 qrel successor 和既有 410 specs 保留为历史资产，但不再是当前立即执行项；它们必须等新的金融对象与 Pack evaluator 证明后再决定是否复用、扩邻或重建。

更新后的唯一顺序为：

1. [x] `S0_S1_FINANCIAL_RESEARCH_GENERALIZATION_CONTRACT`：冻结 provider-neutral 金融内核、9 类 Evidence Slot、稳定插件接口、AI compute Industry Pack、DELL／MU／NVDA case profile 和三个 blind held-out archetype；只做零调用合同与 mutation proof；
2. [x] `S0_S1_DELL_FINANCIAL_SOURCE_OBJECT_AND_EVIDENCE_PACK_VERTICAL_SLICE`：从 DELL 真实 research question 出发，逐 facet 审查 current source inventory、document hierarchy、Q&A／table／child-parent chunk、typed query lane、candidate selection、multi-candidate Pack 和 residual gaps；结果为 `engineering_pass_product_pack_incomplete`：`23 lanes / 265 candidate rows / 23 of 23 reviewed targets / 15 parent sources / 0 contract rejection`，全部未覆盖 required facet 已显式成为 typed residual gap，未调用模型、未建 dense、未晋升 Evidence；
3. [ ] `S0_S1_MU_NVDA_CORE_UNCHANGED_TRANSFER`：锁定第 2 项的核心 module／plugin digest；MU／NVDA 只能改 Pack／case config／source data。任何 ticker-specific core patch 都记为 transfer failure；
4. [ ] `S0_S1_THREE_HELD_OUT_GENERALIZATION_PROOF`：在 proof 前才选择一个美国非半导体、一个 non-US 20-F／6-K、一个披露稀疏案例；不写入 Gold URL，覆盖 alias／period／currency／PDF／relationship／stale／zero-result mutation；
5. [ ] `S1_SPARSE_DENSE_REBUILD_DECISION`：只对上述纵切证明值得保留的 Source／Section／Q&A／Table／claim objects 建 successor sparse/dense；旧 410 specs 不删除，但不得自动执行；
6. [ ] `S1_RESIDUAL_GAP_EXTERNAL_SUPPLEMENT`：先完成本地 Candidate Pack，才把真实 residual facets 投影到 official-first／broad discovery；外源 capture 后回到同一 evaluator 与 Evidence Gate；
7. [ ] `S2_S3_MODEL_DYNAMIC_FOLLOW_UP_AND_RESEARCH_SYNTHESIS`：在同一已治理 Evidence Pack 上让 DeepSeek 提出 bounded follow-up atoms、动态关闭 gaps、形成机制／反证／WWC，并与 Codex reference 和 qualified-human rubric 比较研究内容质量；
8. [ ] 完成 Workbench／S5 产品验收；不能用 contract pass、retrieval 指标、9 Artifacts 或页面可打开替代。

止损边界：第 1 项不调用网络、Provider、模型、retrieval、embedding、rerank 或 Evidence promotion；第 2 项先允许自然暴露 DELL 全链问题，不因单个 facet 缺失逐次 live。第 3 项若需要改核心，先记录原因并回到通用边界一次性处置。第 4 项通过前不准第 5 项；本地 Pack 未形成前不准用外源把缺口混成另一套 truth；DeepSeek 最后进入，避免把 S0／S1 产品缺陷算成模型能力。

第一项机器合同与零调用证明分别为：

- `configs/runtime/fin_ia_0_1_3_s0_s1_financial_research_generalization_contract_v1_0.json`
- `configs/releases/fin_ia_0_1_3_s0_s1_financial_research_generalization_zero_call_proof_v1_1.json`
- `configs/releases/fin_ia_0_1_3_s1_dell_financial_source_object_vertical_result_r3_v1_0.json`

当前状态严格为前两项通过：通用合同与 DELL 本地纵切工程成立，但 DELL Candidate Pack 因 residual gaps 仍不完整且从未晋升为 Evidence。下一项只做 MU／NVDA core-unchanged transfer；不能宣称 sparse／dense、外源补源、跨案例泛化、DeepSeek 研究或研报质量通过。
