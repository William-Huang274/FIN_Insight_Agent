# FIN 0.1.3 修复收口版范围与差量 S0–S5 计划

日期：2026-08-05
状态：`FIN_0_1_2_honest_block_frozen / FIN_0_1_3_minimum_anchor_complete / three_case_gold_candidates_complete / two_track_rebaseline_active / S2_04_complete / S2_05_authority_honest_block / Experiment_A_runner_next / FIN_0_2_definition_unchanged`

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
18. [ ] 执行 `013-S1-06/07/08`：修复 MCP operational truth、当前外部来源 runtime 和 Agentic Search 质量门；不调用 DeepSeek 来发现确定性工具缺陷。
19. [ ] 执行 `013-S3-06/07`：先完成 `DS-A1/A2/A3` provider-neutral capability profile、judgment atom 与 protected narrative 门，再进入动态 Lead loop 与 EvidenceRequest/targeted repair 闭环；同一 family 不逐字段反复 live 修补。
20. [ ] 执行 `013-S3-08/09` Experiment B：三案端到端 DeepSeek Agentic Search/Research、隐藏 Gold 八维对照和 qualified-human 内容验收。
21. [ ] 执行 current S4 Workbench dogfood，再执行 S5 RG1–RG5；只有最终 candidate 可获得 FIN 0.1.3 内部版本收口结论。

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

> **2026-08-07 用户已选择 SEC contact 路线**：真实联系身份只通过运行时环境注入，不进入 Git 或结果物；SEC 域名无合法 contact 时 fail closed。新增 identity mutation 后 broader=`84 passed`。只授权 new admission 的 1-call Dell SEC v1.3 proof，复用 MU/NVDA 已成功结果；不重跑三案、不进入额外 fallback。

> **2026-08-06 S5 交接发现**：仓库中存在早先已被合并/放弃的 47 个 `FIN 0.1.3` 命名 config/runtime/test 资产，0.1.2 active-suite 仍有 7 个相关引用。它们必须保留为历史证据，但不能自动成为本轮新 0.1.3 authority。`013-S0-01` 必须先签发 canonical delta namespace/inheritance successor，再开始其他实现。
