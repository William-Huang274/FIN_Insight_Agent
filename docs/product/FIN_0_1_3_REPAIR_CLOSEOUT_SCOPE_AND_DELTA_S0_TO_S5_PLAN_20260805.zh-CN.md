# FIN 0.1.3 修复收口版范围与差量 S0–S5 计划

日期：2026-08-05
状态：`FIN_0_1_2_honest_block_frozen / FIN_0_1_3_S2_02_complete / S2_03_next / FIN_0_2_definition_unchanged`

> **2026-08-06 用户新增硬要求**：FIN 0.1.3 必须把研究内容输出质量作为 release-blocking 考核，不得再将 L3 的通用 Claim、弱综合、机械 Writer 或不可执行 WWC 降级为 nonblocking finding。八维绝对质量＋paired gain＋qualified human content acceptance 的正式标准见 `docs/eval/FIN_0_1_3_RESEARCH_CONTENT_OUTPUT_QUALITY_RUBRIC_20260806.zh-CN.md`。

## 1. 决策

FIN 0.1.2 在 S4-T08 扩大审计中证明了完整的工程链路形状、三案例产品投影、exact review 控制和大量不可变执行证据，但同时暴露出财务真值、证据覆盖、研究语义和 current 产品闭环仍未达到 FIN 0.1 PRD 的 release 定义。

因此：

1. FIN 0.1.2 不继续在 T08 内展开实现修补；T08 只负责完成审计、阶段归属和 honest-block handoff。
2. FIN 0.1.2 的 S5 只做一次 decision-only closeout：冻结候选、已知失败、成本和 rollback 边界，并明确 `release_not_qualified`；不在已知 RG2/RG3 失败时机械执行六轮发布证明。
3. 新建 FIN 0.1.3 作为 **FIN 0.1 最后一个专项修复与正式收口候选**。FIN 0.2 仍保持 Earnings Review Alpha 的原定义，不吸收本轮欠账。
4. FIN 0.1.3 仍使用 S0–S5 表达责任层和成熟顺序，但采用差量执行：继承 FIN 0.1.2 未受影响的 immutable evidence，只运行发生变化的阶段、依赖回归和最终 release gate。
5. 失败必须留在最早责任阶段；不得因为 S4 暴露问题，就在 Workbench、renderer 或 T08 末端加补丁掩盖上游缺陷。

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

### S3：研究计划、判断、Lead、Writer 与 Verifier

| ID | 修复包 | 受影响 PRD | 0.1.3 通过条件 |
| --- | --- | --- | --- |
| `013-S3-01` | 把 current exact product 从固定三 Cell 升级为动态 DecisionSurface；Anchor 覆盖 10–20 Cell、目标 12–16 和六个必选 family | F03/F08 | reviewer 可审阅/裁剪计划；每 Cell 有问题、owner、slot、stop rule 和 WWC，不硬编码标题 |
| `013-S3-02` | 修复通用 Claim、重复 gap、9/9 通用 WWC；形成公司专属机制、证据边界和可观测触发条件 | F08/F10 | 每个核心 Claim 包含本案对象、机制、证据/数字或 gap；WWC 有指标、方向、时间/阈值和下一证据路线 |
| `013-S3-03` | 让 dependency、conflict 和 gap 成为真正的跨 Cell 综合，而不是复述 supported/cannot infer 状态 | F08/F10 | Lead 对冲突给出 resolve/defer/block 理由；gap 有影响、优先级、owner 和 stop condition |
| `013-S3-04` | 提升 Workpaper/Writer 的产品、财务、客户/供应链、竞争、资本/price-in、估值边界、风险和 counter-thesis 内容 | F08/F11 | 报告能回答“结论、为什么、反方、缺什么、什么会改变”，不是六个 atom 的排版投影 |
| `013-S3-05` | 重做 Verifier/paired rubric：完整性 gate 与研究内容质量硬门禁分离，正式消费八维 Rubric | F07/F08/F10/F11/F15 | DELL period 错误必须 L1 fail；三案逐案达到 `>=24/32`、核心维度下限、material paired gain 和 qualified human content acceptance；通用 Claim/WWC 不得凭数量获得 L3/L4 pass |

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
13. [ ] 完成 `013-S2-03`：审计 node context yield、重复 role view、Evidence 利用率、容量和成本；先零调用编译与 mutation，再只对真正改变的模型合同决定是否需要单节点 canary，不直接运行三案例 full-chain。

> **2026-08-06 S5 交接发现**：仓库中存在早先已被合并/放弃的 47 个 `FIN 0.1.3` 命名 config/runtime/test 资产，0.1.2 active-suite 仍有 7 个相关引用。它们必须保留为历史证据，但不能自动成为本轮新 0.1.3 authority。`013-S0-01` 必须先签发 canonical delta namespace/inheritance successor，再开始其他实现。
