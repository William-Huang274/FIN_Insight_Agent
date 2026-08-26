# S1 工作记录 100：DELL 03B R8 program-level execution plan

日期：2026-08-27

状态：`approved same-stage non-overwriting R8 plan / implementation not started / no R8 policy, attempt, private or public result`

## 1. 目标、成功含义与不可变边界

R8 只修复 fresh R7 dual audit 在 owning stage 复现的三个通用根因：

- `RC-S1-079`：R7 的 sentence-unit `TypedProposition` 仍可把同句中独立 predicate frame 的 actor、predicate、object、recipient、product、price、quantity 或 process 拼成一个 complete；trailing modality、reporting 与 uncertainty 未覆盖完整 proposition span。
- `RC-S1-080`：R7 material anchor 虽已按 role 输出，但 role 的来源仍未绑定到具体 predicate-argument span；多价格、多数量与同句独立事件时会错误归属，且受审同义表达 recall 不足。
- `RC-S0-105`：R7 public validator 可被 grammar-valid 高熵 identifier 和多层 percent-encoded locator 绕过；type/identifier early return 早于 threat/entropy 检查。

R8 的成功含义仅是：03B candidate-chain 的 predicate-frame 语义、frame-local anchor、公开值验证、source/object/union/final 一致性通过作者门和新鲜独立审计。它不等于上一版研报信源已补齐，不等于 Evidence admission、S2、Writer、qualified-human、产品验收、publication 或 release。

R7 policy/private/public/receipt/result/audit、保存 raw execution 和 Git identity 全部 immutable。R8 必须使用新的 module、runner、tests、schema、policy、attempt、private/public result path；不得修改、覆盖、重试或追认 R7，也不得复用 R7 attempt。

R8 实现、preview 和审计阶段不得执行网络、外源、4B embedding、reranker、Provider、生成模型、CandidateDecision、Evidence/NumericFact promotion、gap closure、S2 或 Writer。R7 的四个 external-required target、4B eligibility=0 与 same-pool reranker eligibility=0 只是 bounded predecessor observations，不在 R8 消费。

## 2. 核心设计不变量

1. **一个 complete 对应一个 predicate frame**：每个 required role 必须具有独立 span，并由同一 predicate head/argument structure 直接拥有；同句不等于同一 frame。
2. **role provenance 先于 role value**：任何 actor、recipient、product、price、quantity、period 或 process 都必须保存 `source_span -> frame_id -> role_name -> normalized_value` 链；无 provenance 的值不得参与 completion 或 coverage。
3. **scope 覆盖完整 frame**：polarity、modality、epistemic status、reported speech、revocation 与 trailing modifier 必须作用于对应 frame 的完整 span；不得只扫描 predicate 左侧或首个 clause。
4. **歧义 fail-close**：同 frame 内出现多个可归属价格/数量/产品且无法用 predicate-argument locality 唯一解析时，输出 typed ambiguity 和 partial，不选择最近或最大值。
5. **受审 grammar 是 bounded recall，不是通用语言理解声明**：新增同义表达必须有正例、近邻反例、span 断言和 target contract；不得仅扩一条 broad regex。
6. **威胁检查先于类型 acceptance**：公开字符串先 Unicode normalize、bounded fixed-point decode、locator/traversal/secret/high-entropy 检查，再做 identifier/ref/narrative grammar；任何 early return 都不得绕过 threat checks。
7. **成功不得跨阶段外推**：R8 fresh PASS 最多签发 residual source route 的规划与执行资格；不自动证明 public-information gap、研报质量或产品 readiness。

## 3. 需求票、依赖图与责任阶段

主依赖顺序：

`R8-00 -> R8-01 -> R8-02 -> R8-03 -> (R8-04 || R8-05 || R8-06) -> R8-07 -> R8-08 -> R8-09`

其中 R8-04/05/06 可在 frame contract 稳定后独立实现，但 R8-07 integration、R8-08 formal seal 和 R8-09 fresh audit 必须等待三者全部通过。

### R8-00：冻结 predecessor、fresh audit、测试与审计材料清单

责任：作者／Project OS；不调用模型或网络。

输入：

- R7 implementation commit `b2f8ce3ce393d593f0cb4964aeb11ba09aa3fb92`；
- R7 authority commit `b740270c2012cd936b87562ce47c3fb1886358b1`；
- R7 immutable result commit `22c85026aaf1703f3f96a473b545a3a3e18cb35e` 与 exact Git identity；
- R7 audit record commit `41a5e9873a16f180e45c2c10ef3585fdce993315`；
- R7 policy/private/public/receipt、raw execution、model-run 与 audit artifact；
- fresh audit digest `904637666c90ce9c65a45ef741ac7669b19bd118c1797de6ebffa5d601844abb`；
- R17 fixed report-quality bundle 和仍开放的 `0/1/2/1` findings。

输出：

- exact predecessor binding set 和 SHA/digest；
- R7 三项 P2 与 R17 四项 open finding 的结构化 freeze；
- 所有 audit reproductions、positive controls、privacy attacks 的不可变 fixture；
- R8 implementation/test path allowlist；
- hash-bound audit manifest 草案，明确工程审计包、研报审计包、缺失材料与 `NOT_ASSESSABLE` 规则；
- authority matrix：implementation/tests/zero-model preview only。

验收：R7 reviewed commit/tree/parent、result/audit digest、三项 root cause、R17 findings 或 fixture 文本任一漂移即 fail。计划和实现阶段不得生成 R8 policy、attempt、private/public result。

### R8-01：不可变 PredicateFrame IR 与 span-bound RoleBinding

责任：S1 semantic compiler。

输入：一个原始 sentence unit、absolute source provenance、sentence/clause spans、target ID。

输出：deterministic immutable `PredicateFrame`，至少包含：

- `frame_id`、sentence index、clause index、frame start/end、predicate start/end；
- 每个 role 的 `RoleBinding(role, raw_text, normalized_value, start, end, source_kind, confidence_class)`；
- actor/subject、predicate/action、direct object、recipient/counterparty、product/component；
- price/currency/magnitude/qualifier、quantity/measure/unit/denominator；
- period、process、status、polarity、modality、epistemic/reporting owner、revocation；
- `scope_bindings`、`role_conflicts`、`ambiguities`、`missing_required_roles`、`limitations`；
- canonical frame digest。

实现约束：

- 同句每个独立 predicate head 生成独立 frame；并列、从属、reported clause 可以共享 sentence provenance，但不得共享可变 role 容器；
- role span 必须落在 frame span 内，或由显式 syntactic/control relation 引入并保存关系；不能凭同句 membership 借值；
- proposition/frame 去重必须在 span 和角色已确定后进行；相同文本不同位置不得先去重；
- IR dataclass/record immutable，序列化字段顺序固定，相同输入重复编译 digest 完全相同；
- 不把 regex match 本身当作 frame ownership 证明。

验收：直接构造同句两个 frame、嵌套 reporting frame、并列独立 frame、trailing modifier frame；每个 role 的 frame/span ownership 必须可断言，任何跨 frame 借值均失败。

### R8-02：六个 target 的 frame-local role contract

责任：S1 target qualification。

依赖：R8-01。

每个 target 只在一个 frame 内校验 required roles：

- **ASP**：Dell 是实际 seller/quoter；physical product/configuration 和 price/currency 必须由同一 quote/sale frame 拥有；support/freight/financing/第三方价格不得归给 hardware；realized company ASP 仍需 units/denominator，不因单笔 quote 自动成立。
- **supplier read-through**：named supplier、Dell recipient/counterparty、supply/provide/deliver/relationship predicate、affirmative actual status同 frame；仅 `partners including` 保持 bounded relationship 类型，不可自动升级 actual delivery。
- **capacity release**：upstream capacity/allocation、Dell recipient、非零 committed/earmarked/released/allocated status、period/process 同 frame；HP 或其他 recipient 不得借给 Dell。
- **observed yield/utilization**：相关 manufacturing/HBM process、observed/achieved/yielded measure、percent、period同 frame；solar/orange-juice 等无关 process 不得借给 GPU/HBM。
- **HBM supply bridge**：Dell/PowerEdge product、HBM component、uses/incorporates/configured-with/allocated-to/supplied-to predicate 和 affirmative status同 frame；HBM 对 HP 可用加 Dell announcement 不 complete。
- **units**：Dell 为实际 seller/shipper/dispatcher、physical server product、quantity、period同 frame；NVIDIA shipped、Dell marketing-material shipment 或 GPU count 不得形成 Dell server units。

输出：每个 candidate 至多一个 `accepted_frame_id`；多个合格 frame 按稳定 materiality/provenance 规则列出 alternatives，不合并 roles。`matched_group_ids` 只能由 accepted frame 的 bindings 派生。

验收：六 target 的 false complete=0；既有 R7 真阳性保留或逐 frame 解释撤回；contract 不得调用 package-level group union。

### R8-03：完整 frame scope 的 polarity、modality、status 与 reporting

责任：S1 semantic scope。

依赖：R8-01/02。

规则：

- `allegedly`、`according to an unconfirmed report`、`rumored`、`estimated`、`anticipated`、`can/may/could`、`denied/disputed/refuted`、`withdrew/revoked/suspended` 等必须绑定其支配的 frame；
- trailing modifier 与 sentence-final reporting phrase 必须进入 scope，不能因出现在 predicate 右侧而失效；
- quoted/reporting frame 与 embedded asserted frame 分开：reporter、asserted actor、evidence status 不混为一体；
- negation/uncertainty 只否定或降级被支配 frame，不误杀同句独立肯定 frame；
- scope 不明确时 partial，并输出 `ambiguous_scope:<modifier>:<candidate_frames>`。

验收：正例、否定、能力态、传闻、撤销和同句两个独立事件均有 frame/span 断言；不得用“整句含某词则全部拒绝”的 broad guard。

### R8-04：predicate-argument provenance anchor 与多值歧义拒绝

责任：S1 anchor compiler。

依赖：R8-01/02/03。

输入：accepted frame 的 RoleBinding；不得输入未经筛选的整句供全局数值扫描。

输出：role-labeled anchor plus provenance，例如：

- `price.hardware.currency_usd:15@frame/span`；
- `price.support.currency_usd:150@frame/span`；
- `quantity.physical_server:4@frame/span`；
- `product.server_model:xe9680@frame/span`；
- `period.fiscal_year:2026@frame/span`；
- `yield.hbm_production.percent:90@frame/span`。

规则：

- product、price、quantity、period、process 都必须与 target predicate 的 argument structure 相连；
- 多个价格/数量若局部语法不能唯一归属，fail-close 为 typed ambiguity，不用 first/nearest/largest heuristic；
- product code 内数字不产生 price/quantity/year；support/freight/financing 数值不得覆盖 hardware price；
- coverage 比较同 role、同 frame type、canonical value，不能只比较裸数值；
- source/object/union/final 必须保留 anchor provenance digest。

验收：`Dell quoted $150 for support plus $15 for PowerEdge XE9680 hardware.` 只能把 `$15` 绑定 hardware；若 parser 无法证明归属则 partial，绝不能把 `$150` 绑定 XE9680。

### R8-05：bounded reviewed synonym grammar 与正负成对控制

责任：S1 recall grammar。

依赖：R8-02/03。

首批必须支持并保存 span/role provenance 的六个 fresh-audit 正例：

- `NVIDIA provides GPUs to Dell.`
- `NVIDIA released GPU capacity to Dell in Q1 2026.`
- `HBM production yielded 90% in 2026.`
- `Dell PowerEdge servers use HBM in Q1 2026.`
- `Dell dispatched four PowerEdge XE9680 AI servers in Q1 2026.`
- `Dell offered PowerEdge hardware for USD 15 in FY2026.`

每条 grammar 必须同时有：

- 同义形态/时态/主动被动正例；
- recipient、actor、process、product 或 modality 改变的近邻反例；
- predicate span、argument spans、normalized role 和 completion 断言；
- 不影响其他 target 的隔离断言。

不得把 `provides/released/yielded/uses/dispatched/offered` 作为无上下文关键词直接命中；它们只提供 predicate candidate，最终 authority 来自 frame-local contract。

### R8-06：Unicode-normalized fixed-point public value validation

责任：S0 public boundary。

依赖：R7 public schema 与 R8-00 attacks。

统一字符串 pipeline：

1. 保留原值用于 exact projection audit；
2. Unicode normalization（NFKC）与 control/bidi-risk 检查；
3. bounded fixed-point percent decode，最多 6 轮；每轮若值不再变化即停止；
4. 若达到上限仍含可解码 `%[0-9A-Fa-f]{2}` 或 decode 异常，fail-close；
5. 对 normalized/每层 decoded 值执行 scheme、`www`、UNC、drive、absolute/relative traversal、backslash、credential assignment、secret/token pattern、高熵检查；
6. 最后才执行 identifier/ref/narrative 的 field grammar 和 bound-value equality；
7. unknown field、unknown validator path、ambiguous scalar 一律拒绝。

冻结攻击：

- `REQ::DELL::TOKEN_LIVE_PRODUCTION_A1B2C3D4E5F6G7H8::V1` 必须因 threat/entropy 拒绝，即使满足 request-ID grammar；
- `See https%2525253A%2525252F%2525252Fexample.invalid%2525252Fprivate` 必须在 fixed-point decode 后因 locator 拒绝；
- R7/R6 的 literal URL、`www`、credential、unknown key、absolute/relative/backslash traversal、secret-like controls 全保留；
- 合法 SHA/digest/commit、repo-relative refs、普通 target/request IDs、中文/英文 limitations、货币/百分比/产品码 narrative 必须通过。

验收：所有 public paths 都有注册 validator；threat checks 不可被任何 type-specific early return 绕过；合法 control false reject=0，冻结 attack false accept=0。

### R8-07：source/object/union/final compiler 与 current-corpus crosswalk

责任：S1 integration。

依赖：R8-01 至 R8-06。

输出：

- source、compiled object、union、final 的 frame completeness、accepted frame digest、role/anchor provenance；
- before/after current-corpus crosswalk；
- 每个 target 的 source/object/union/final count、best rank、complete/partial reason；
- 性能与内存 receipt；
- zero-model public preview。

规则：

- 四层共用同一 R8 frame classifier，不允许某层退回 R7 sentence-wide union；
- slice/parent/dedup 不得制造 frame adjacency 或丢 absolute provenance；
- count/rank 变化必须逐 package/frame 解释，不能只给汇总差异；
- current R7 counts 是 bounded expectation，不是硬编码 golden：ASP=`1/1/1/1 rank2`、supplier=`3/3/2/1 rank2`、capacity/yield/HBM/units=`0/0/0/0`、external-required=4、local repair/4B/reranker eligibility=0；
- 若 R8 正确召回正例或撤回 false complete，可接受变化，但必须有 frame-level evidence；无法解释则停止在 implementation。

性能门：R7 exact zero-model preview baseline=`223.188s`。R8 preview 若超过 `600s`，或相同输入出现无解释的 `>2x` regression，立即停止并 profile；不得等待 20–30 分钟才判断。Preview 不生成 policy、attempt、private/public result，也不调用模型/网络。

### R8-08：policy、exact-once formal execution 与 immutable result seal

责任：作者／formal runner；仅在 implementation freeze 后。

依赖：R8-00 至 R8-07 全部通过、clean implementation commit 已 push、唯一 T4 freeze gate 有效。

输出：

- 新 `v1.7` policy 与 validator；
- attempt `dell-rsq-03b-internal-chain-r8`；
- canonical ignored private/receipt；
- tracked public result、model-run、author-integrity record；
- saved-raw exact replay/reprojection receipt。

规则：

- policy-only authority commit 的唯一 parent 精确为 clean/pushed implementation commit，changed path 仅为 R8 policy；
- 绑定 R7 result/audit、R8 implementation/test/audit-manifest input set、current runtime 和 exact Git identity；
- collision、dirty/unsynced、disk、branch/commit/tree、canonical path、exclusive receipt、atomic private/public pair、schema/self-digest 或 output identity 任一失败即停止；
- 同 attempt 不重试，不覆盖，任何失败保存为 immutable evidence。

### R8-09：hash-bound fresh dual audit 与 authority transition

责任：全新 fork-none、作者分离、只读 reviewer；qualified human 仍是另一阶段。

固定审计包必须在 reviewer 启动前生成，并绑定：

- reviewed commit/tree/parent 和 changed-file manifest；
- R7 predecessor/result/audit、R8 policy/private/public/receipt/self-digest/raw SHA；
- T1/T2/T3/T4 test receipts、static/secret/diff receipts；
- 冻结 attack/positive-control matrix 和 current-corpus crosswalk；
- exact replay/reprojection 命令与结果；
- R17 固定 report-quality bundle：报告 bytes、reader citations/source appendix、14/9/4/10 crosswalk、六 WWC、fact-density/repetition、source passages/locators、02B/human/formal-8D states。

审计分相：

1. integrity/route；
2. semantics/frame/scope；
3. anchor/recall；
4. public privacy；
5. R17 report quality。

每相只读固定清单和必要直接依赖；不得递归遍历历史寻找“也许相关”的材料。固定包缺证据时直接标记 `NOT_ASSESSABLE` 并列出缺项，不通过无界阅读替作者补包。Reviewer 不跑 full pytest、不调用网络/模型/4B/reranker、不写文件；只有具体 material suspicion 才运行 targeted mutation。主 Agent 可在 scope expansion、重复历史阅读或无新证据时中断并要求阶段性 verdict。

R8 与 R17 findings 分开计数。任一 material R8 finding 都使 03B independent=false；保留 R8 immutable bytes，回 owning stage 开 non-overwriting successor。R17 failure 不篡改已通过的 R8 工程 verdict，但继续阻断 report/product/publication/release。

## 4. 冻结 fresh-audit 复现矩阵

### 4.1 必须拒绝的 frame/semantic attacks

- `NVIDIA quoted $15, and Dell sold the PowerEdge XE9680 hardware.`
- `Dell quoted $15 for PowerEdge hardware, allegedly.`
- `NVIDIA shipped chips, and Dell sold PowerEdge servers.`
- `NVIDIA supplies Dell AI servers, according to an unconfirmed report.`
- `Dell received financing alongside GPU capacity being allocated to HP in Q1 2026.`
- `Solar-panel production yield was 90%, and GPU sales rose in 2026.`
- `HBM supply was available to HP, and Dell announced earnings.`
- `Dell shipped marketing materials, and NVIDIA delivered four PowerEdge XE9680 AI servers in Q1 2026.`

每条必须断言：frame 数量、predicate spans、role owner、scope binding、目标 completion=false 和具体 limitation。只断言最终 boolean 不足以验收。

### 4.2 必须正确归属或 fail-close 的 anchor attack

- `Dell quoted $150 for support plus $15 for PowerEdge XE9680 hardware.`

验收优先级：正确 frame/argument 绑定 `$15` 为 hardware price；如果 bounded parser 无法证明，则 typed ambiguity/partial。把 `$150` 绑定 XE9680 或用两个裸数字合并 coverage 均失败。

### 4.3 必须召回的 positive controls

- `NVIDIA provides GPUs to Dell.`
- `NVIDIA released GPU capacity to Dell in Q1 2026.`
- `HBM production yielded 90% in 2026.`
- `Dell PowerEdge servers use HBM in Q1 2026.`
- `Dell dispatched four PowerEdge XE9680 AI servers in Q1 2026.`
- `Dell offered PowerEdge hardware for USD 15 in FY2026.`

### 4.4 必须拒绝的 public attacks

- `REQ::DELL::TOKEN_LIVE_PRODUCTION_A1B2C3D4E5F6G7H8::V1`
- `See https%2525253A%2525252F%2525252Fexample.invalid%2525252Fprivate`

同时继承 R7/R6 全部 unknown-field、literal/encoded locator、credential、secret-like、absolute/relative/backslash traversal attacks 和合法 controls。

## 5. 工程验收与风险分层测试策略

R8 采用 `docs/project_os/risk_tiered_test_evidence_policy.zh-CN.md`，不把全仓 pytest 当作日常心跳。

### T0：静态与结构检查

每个可提交增量运行：受影响文件 compile/import、`git diff --check`、JSON/JSONL parse、changed-path secret scan。纯计划/账本/policy/result/audit 文档变化只跑对应 Project OS/validator，不跑全仓。

### T1：直接合同测试

每次 semantic/anchor/privacy 代码编辑后只跑 R8 直接测试；测试按 `frame`、`scope`、`anchor`、`recall`、`public`、`compiler` 分组，可精确到失败 case。目标是秒级到十几秒反馈。

### T2：邻接合同测试

当一个 ticket 达到局部 freeze 时，运行 R7+R8、共享 candidate compiler/public projector 的显式测试清单。当前 marker 未完成审计，不使用 `-m 'not ...'` 负向排除制造假安全。

### T3：子系统回归

仅在 shared retrieval/public validator、active consumer、Project OS binding 或 runner seam 变化时运行对应子系统；若只新增隔离 R8 module 且邻接清单已覆盖，不机械扩大。

### T4：全仓冻结门

只在 R8 implementation/test freeze、clean policy 前运行一次：

`python -m pytest -q --durations=50`

它覆盖“未知耦合未被定向测试识别”的剩余风险。之后 policy-only、formal result、工作记录、Project OS、审计 artifact 不重复全仓；它们消费该 freeze receipt，并运行受影响 validator。只有以下情况使 T4 失效并要求重跑：

- freeze 后 production/test/shared validator/active consumer 语义发生变化；
- 依赖影响面无法确定；
- targeted/adjacent 出现无法解释的跨子系统失败；
- merge/release gate 明确要求新 HEAD 的全仓证据。

Reviewer 不重复 T4。若 material suspicion 可由 targeted mutation 证明，直接记录 finding；只有影响面确实未知才升级。

### 工程通过条件

1. 4.1–4.4 每个 case 都有独立 frame/span/role/scope/value 断言。
2. R7 151 tests 与 R8 seam 的相邻合同不回退；新实现不得修改 immutable R7 semantics/result files。
3. `PredicateFrame`/`RoleBinding` deterministic、immutable、无共享可变状态；相同输入序列化和 digest 稳定。
4. completion 路径中不存在 sentence/package-level required-role union；测试直接构造两个互补 frame，合并后仍 partial。
5. source/object/union/final 使用同一 R8 classifier，任何 mismatch 有 typed reason。
6. public 所有 allowed paths 有 validator；threat-first pipeline 无 early-return bypass。
7. current-corpus count/rank 变化逐 frame 可解释；preview 性能门通过。
8. T0/T1/T2、必要的 T3 与唯一一次 T4 通过；active baseline、config/Project OS parse、secret scan 与 diff check 通过。

## 6. 模型节点 TokenBudgetBasis 与输出质量

### Formal 0.6B query-embedding batch

- **node purpose**：在 R8 frame compiler 冻结后，对同一五个冻结请求生成可比较、可审计的 candidate ranking trace；embedding 不承担 semantic/frame 判断。
- **input scale**：current R39 1,888 source records／34,199 compiled objects，5 requests。
- **required outputs**：每 request 精确 96 unique union／16 unique final、连续唯一 rank、raw execution SHA/digest、完整 route counters 和 frame/anchor crosswalk。
- **schema burden**：R7 predecessor/result/audit、R8 frame/anchor/public schema、current runtime、Git/attempt/atomic-output seal。
- **materiality/quality risk**：pool drift、truncation、duplicate rank、CPU/network fallback、非冻结模型、无法解释 count change 都会破坏比较，全部 fail-close。
- **comparable evidence**：R7 为 5 requests、one local Qwen3-Embedding-0.6B batch、5×96/16、saved-raw exact replay；R8 不扩 request/output 上限。
- **reasoning profile**：embedding only，无生成式 reasoning/token output；4B/reranker/Provider/network/external budget=0。
- **stop/truncation**：任一 request 非 96/16、模型/设备/registry 不符、OOM/fallback、identity/disk/output collision 或 schema gate 失败即停止；同 attempt 不重试。

### Semantic/frame 输出质量

- 冻结 false-complete attacks false accept=0；冻结 positive controls false reject=0。
- 每个 complete 可追溯到一个 frame ID、predicate span 和全部 required RoleBinding；不得只给 group list。
- scope、ambiguity 与 limitation 为 typed 输出，不能用无结构自由文本代替判定原因。
- current corpus 的每个新增/撤回 complete 都有 before/after frame crosswalk；无法解释即不签 policy。

### Anchor 输出质量

- 多值错误归属=0；跨 frame/跨 role 裸数值 coverage=0。
- 合法同义产品/价格/数量/期间/process 规范化稳定；所有 canonical value 保留原 span 和 normalization rule。
- 无法唯一归属的 material value 必须 partial，不允许“为了 recall”猜值。

### Public 输出质量

- private exact recompile、public exact reprojection；public/private link、self-digest、raw SHA 精确。
- 两条 fresh attack 与既有 public attacks 100% 拒绝，合法 controls 100% 通过。
- public 不含 private/model/material text、locator、credential/secret-like/high-entropy payload、scheme 或 traversal。

## 7. 最终研报质量标准与 R8 的边界

R8 不生成报告，也不能自动修复 R17。但研报质量必须留在 program plan 和 future audit 中，不能只验工程：

1. reader-visible citation URL/locator 和 source appendix 必须存在并能回到原始 passage；repo internal ref 不能替代读者信源。
2. 14 个上一版研报 gap、9 个已有候选、4 个 residual external target、10 个 downstream bridge 的 crosswalk 必须被新报告实际消费并带 digest。
3. 六个 WWC 必须具有 operational fields：trigger、direction、magnitude/range、time window、observable、disconfirming condition、source/limitation、affected thesis/valuation bridge。
4. 所有数值关系可重算；ASP/units/share -> PVM -> product profit/working-capital 的输入、期间、单位、PIT 与公式血缘完整。
5. 事实与 WWC 重复受控；同一事实不得仅换措辞重复 4–5 次。必须区分 evidence、analysis、inference 与 information boundary。
6. source passages/locators 缺失时语义支持标 `NOT_ASSESSABLE`，不得把内部数学正确等同原文支持正确。
7. 02B 16 项 CandidateDecision/Evidence Gate 必须有 qualified-human decisions；formal 8D 在其前保持 invalid。
8. 新报告必须使用非覆盖式 successor path，R17 bytes/verdict immutable；工程审计和研报审计分别给 finding，最后才由 qualified human 验收。

## 8. R8 fresh PASS 后的完整下游顺序

只有 R8 fresh independent PASS 后，才按以下顺序继续；任一门失败留在 owning stage：

1. 重算 14/9/4/10 gap crosswalk，区分 local data/object/index/SQL、retrieval/ranking/tool/model、真实公开信息边界与商业/private-data boundary。
2. 对四个 residual target 执行完整外源梯子并保存 reachability、query、candidate、source-quality 与 admission receipts；不再把 empty local result 当 public-information gap。
3. 对新 candidate pool 做 0.6B/4B mixed embedding shadow comparison；4B 只作为 recall challenger，不替代 lexical/SQL/object routes，也不因模型大而自动胜出。
4. 保留 reranker：在有真实 rerank eligibility 或独立固定候选集评测时运行，比较 relevance、materiality、source quality 与 rank stability；当前 R7 same-pool eligibility=0 不人为制造调用。
5. 完成 CandidateDecision/Evidence Gate；只有合格 evidence 才进入 current Pack，失败与边界保留 receipts。
6. 重编 Pack/Readiness、units/share、ASP/mix、PVM、product-profit 与 working-capital attribution；输入不充分时保持 typed gap，不推导伪精确结果。
7. Readiness 通过后仅运行受影响的 DELL 动态单元，不直接启动无边界的付费多-Agent live。
8. 生成不覆盖 R17 的 successor 报告，包含 reader citations/source appendix、crosswalk、WWC、数值血缘、scenario/sensitivity、supplier/capacity read-through 和 valuation basis。
9. 分别做工程审计与研报质量审计；fresh reviewer 使用固定 manifest，qualified human 处理 02B/admission/final report judgment。
10. 只有上述门全部通过，才讨论 product/publication/release；R8 PASS 本身不授予这些状态。

## 9. 停止条件与变更控制

立即停止且不签 R8 policy 的条件：

- 任一 fresh attack 仍 false complete，任一六正例仍 false negative；
- role 没有 frame/span provenance，或 completion 仍存在跨 frame union；
- 多价格/数量歧义仍被 heuristic 猜值；
- public 两条 fresh attack 任一通过，或合法 control 被 broad secret guard 系统性误杀；
- current corpus 差异无法逐 frame 解释；
- preview `>600s` 或无解释 `>2x` regression；
- targeted/adjacent/T4 或 identity/secret/static gate 失败；
- R8 plan scope 需要扩大到外源、4B、reranker、Evidence、S2 或 Writer。

若发现超出本计划的 material 产品/成本/发布变化，先记录 evidence/impact/recommendation 并向 owner 报告，不静默扩权。失败保存为同阶段 immutable attempt；测试失败本身不创建产品版本。

## 10. Definition of done 与当前 authority

R8 program plan done 的含义：本文件、Project OS context 和 capability ledger 精确记录 tickets、依赖、输入输出、工程/模型/研报质量、测试升级、性能、审计固定包、TokenBudgetBasis、停止条件与下游顺序。

当前 authority 仅允许：

- 新建 R8 implementation/tests/zero-model preview；
- 运行 T0/T1/T2、必要 T3 和 implementation freeze 时唯一一次 T4；
- clean commit/push 后另行生成 policy-only authority；
- 唯一 formal R8、作者完整性与 fresh dual audit。

当前明确为 false：R8 implementation、R8 policy、R8 attempt/result、03B independent、03C external、4B、reranker、CandidateDecision、Evidence/NumericFact、gap closure、Pack/Readiness、S2、S3、R17 successor、report quality、formal 8D、qualified human、product、publication、release。
