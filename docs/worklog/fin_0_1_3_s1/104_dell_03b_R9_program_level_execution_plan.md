# S1 工作记录 104：DELL 03B R9 program-level execution plan

日期：2026-08-27

状态：`same-stage non-overwriting R9 plan / R9-00～R9-06 author implementation, zero-call preview and local engineering freeze pass / implementation commit and push pending / no R9 policy, attempt, private or public result`

## 1. 目标、成功含义与不可变边界

R9 只修复 fresh R8 split dual-audit 在 owning stage 确认的三项 P2，并补完一项未评估 provenance seal：

1. `RC-S1-079`：R8 frame boundary 依赖 `, and` 等带标点 coordinator；无逗号的两个独立谓词仍可保留在一个 record 并跨事件拼 role。
2. `RC-S1-079`：R8 epistemic/reporting/revocation 仍是非完备枚举；demonstrative suspension、`discontinued`、`exploring`、leading `According to an analyst` 被当作 actual/active/direct。
3. `RC-S1-080`：R8 price→hardware 仍使用右侧词面 heuristic；变更 coordination 或只有一个 support price 时可错绑 hardware。
4. Audit `NOT_ASSESSABLE`：source 与 compiled complete row 的 `accepted_frame_digest` 有差异，但当前 artifact 没有 source-frame→compiled-frame 的显式 transformation binding。

R9 成功只表示 03B candidate-chain 在 punctuation-independent frame split、frame-local semantic state、product-role-bound price anchor、四层 transformation provenance、冻结 recall/privacy controls 上通过作者门和 fresh independent engineering audit。R9 不补四个 residual 外源，不运行 4B 或 reranker，不做 CandidateDecision/Evidence、Pack/Readiness、S2 或 Writer，也不修 R17。

R8 policy/attempt/raw/private/public/result/audit 与 commit identity 全部 immutable。R9 使用新的 semantic/compiler/runner/test/schema/policy/attempt/result path；不得覆盖、重试或“修正” R8。

R17 及其 fixed 14-file bundle 同样 immutable。其最新独立 verdict=`FAIL_GATE_OPEN_NOT_ASSESSABLE`、findings=`0/1/2/1`。在 R17/report/source-binding/crosswalk/method/human artifacts 全部 SHA 不变时，R9 audit 只验证 bundle 与本次 audit receipt 的哈希并继承 verdict，不重复完整内容审计。只有任一绑定 artifact 变化，才重新执行 report-quality content audit。

## 2. R9 核心设计不变量

1. **coordination 由谓词与显式 subject 决定，不由逗号决定**：`and/but/while/whereas` 两侧各有独立 predicate candidate，且右侧出现新的显式 subject 时才拆 frame；compound subject 在共享 predicate 前不得拆。
2. **一个 complete 仍只对应一个 frame**：split 后 required roles 不得从 sibling/parent/trailing frame 借用；共享 sentence provenance 不等于共享 argument。
3. **semantic state 是 frame-local typed state，不是全句关键词 veto**：每个 frame 明确 `assertion_owner`、`speech_mode`、`actuality/modality`、`polarity`、`lifecycle_status/revocation` 和 scope edges。
4. **coreferential state change 通过显式 scope edge 绑定 antecedent**：`this partnership was later suspended` 可以是独立 modifier frame，但必须指向前一 partnership frame 并使其 non-active；不能靠把两段文本盲目 merge。
5. **role attachment 先于 normalized value**：price、product、support/service/freight、quantity、period 都具有 argument-group/governor provenance。只有 hardware object group 的 price 能形成 `price.hardware`。
6. **歧义 fail-close**：一个 price 无法证明属于 hardware，或多个 price 与多个 object 无法唯一匹配时返回 typed ambiguity/partial；不得 first/nearest/largest 猜值。
7. **表示 digest 与语义 digest 分离**：exact text/span 的 `representation_frame_digest` 允许 source/compiled 不同；target、predicate、normalized roles、scope state 的 `semantic_signature_digest` 必须有显式 source→compiled transformation binding。
8. **已通过的 public contract 冻结复用**：R9 默认直接复用 hash-bound R8 public validator。若修改该 validator、schema 或 projection consumer，RC-S0-105 重新打开并重跑全部 privacy controls。
9. **bounded grammar 不宣称通用 NLP**：每个新 grammar family 都有正例、轻微改写、近邻反例、span/state 断言和 target isolation。
10. **任何 S1 pass 不跨阶段外推**：R9 fresh PASS 只解锁下一门 residual source program，不自动授予外源事实、Evidence、S2、report 或产品 authority。

## 3. 需求票、依赖图与责任阶段

主依赖：

`R9-00 -> R9-01 -> R9-02 -> R9-03 -> R9-04 -> R9-05 -> R9-06 -> R9-07 -> R9-08`

R9-01/02/03 的实现可在各自 unit fixtures 上迭代，但 R9-04 provenance 必须消费三者冻结后的 IR；R9-05 integration 后才能做 zero-call preview；R9-07 formal authority 必须等待 R9-06 implementation freeze；R9-08 fresh audit 最后执行。

### R9-00：冻结 R8 audit、通过面、失败面与 authority

责任：作者／Project OS；零模型、零网络。

输入：

- R8 implementation=`a9403e327e2de740015d63223ee6fbeace0f93a6`；
- R8 authority=`f4c3c629c789fa8d61deda2f4375eb887f5f8ce4`；
- R8 result=`aa58a503d5d1416ff2d778808875667b904e6ce4`；
- fixed manifest=`4db3c4bf74e5075201997ed61340aa8f4bef67a3`；
- audit materialization=`110bf9261d1a3b1ffd5597bde66a9e63b800e602`；
- R8 audit digest=`d8f2176e3f0972976ed601c5f0d261617e372df2c3a8de88097f18ed3e5cb612`；
- immutable R8 raw capture 与 15 engineering/14 report bindings。

输出：

- R8 three-P2 fixtures、两项 NOT_ASSESSABLE、63+8 negatives、6+11 positives、15/3 privacy controls 的 hash-bound freeze；
- R8 actual route `ASP 1/1/1/1 rank2`、`supplier 3/3/2/1 rank2`、four residual 0 的 bounded baseline；
- R9 implementation path allowlist；
- R17 carry-forward receipt：14/14 SHA 不变则直接继承 `FAIL_GATE`，变化则强制内容重审；
- authority matrix：R9 implementation/tests/zero-call preview only。

验收：任一 predecessor identity、audit digest、fixture、R17 binding 或已有通过面漂移即停止。R9 plan/implementation 阶段不得出现 policy、attempt、private/public result。

### R9-01：punctuation-independent coordination frame splitter

责任：S1 frame segmentation。

输入：normalized sentence、candidate predicate spans、explicit subject/company spans、coordinator spans、absolute source provenance。

输出：immutable `FrameBoundaryDecision`，至少包含：

- coordinator raw/span/type；
- left/right predicate spans；
- right explicit-subject span；
- `split | shared_subject | compound_subject | ambiguous`；
- reason code 与 canonical decision digest。

规则：

- 对 `and/but/while/whereas`，只有左侧已有 predicate、右侧以新的显式 subject 开始且随后存在 predicate 时拆分；comma 只是一项 surface feature，不能成为必要条件；
- `Dell, NVIDIA, and Micron partnered ...` 的 coordinator 位于共享 predicate 前，保持 compound subject，不拆成事件；
- `Dell shipped ... and NVIDIA delivered ...` 必须拆；
- `Dell quoted support ... and PowerEdge hardware ...` 若右侧没有独立 subject/predicate，不在 frame splitter 伪造第二事件，留给 argument-group attachment；
- ambiguous coordinator 不允许 sentence-wide completion；应形成 partial limitation 或保守 frame 边界，不得借角色；
- semicolon 与 `alongside` 保留既有规则，但 coreferential state clause 由 R9-02 scope edge 处理，不通过文本 merge 获得 authority。

工程验收：三个 no-comma false complete 均拆或 partial；R8 comma attacks 继续拒绝；compound-subject 正例保持一个 frame；每个 boundary decision 的绝对 span 和 digest 可复算。

输出质量：false split=0、false merge=0 于冻结矩阵；新增 family 必须有 punctuation/no-punctuation 成对测试。

### R9-02：frame-local semantic state 与 scope-edge state machine

责任：S1 semantic scope。

依赖：R9-01。

输入：predicate frames、modifier/report/revocation frames、argument roles、sentence-local antecedent candidates。

输出：

- `polarity=affirmative|negative|disputed`；
- `actuality=actual|exploratory|capability|forward_looking|alleged`；
- `lifecycle_status=active|suspended|discontinued|revoked|expired|unknown`；
- `speech_mode=direct|issuer_attributed|third_party_attributed|unconfirmed`；
- `assertion_owner` RoleBinding；
- `ScopeEdge(source_modifier_frame, target_assertion_frame, relation, evidence_span)`；
- ambiguity/limitation 与 semantic-state digest。

最低 grammar families：

- demonstrative/definite coreference：`this/the/that partnership|relationship|allocation|quote|shipment...`；
- lifecycle：`suspended/discontinued/terminated/revoked/withdrawn/cancelled/expired`；
- exploratory：`exploring/considering/evaluating/discussing a partnership`；
- leading attribution：`According to an analyst/source/report, ...`；
- 继承 trailing allegedly/unconfirmed、negative、capability/future controls。

规则：scope edge 必须同时有 modifier span、target frame id 与 relation；无唯一 antecedent 时 typed ambiguity/partial。不得因同句出现 `suspended` 就否定独立 frame，也不得因 reporter 同时是 named company 就自动把第三方 assertion 变 direct。

验收：审计四个 scope 反例均 non-complete 且 typed state 正确；同句独立肯定事件不被 broad guard 误杀；每个 state transition 可由 exact span 重算。

### R9-03：argument-group-bound product/price anchor

责任：S1 ASP/anchor compiler。

依赖：R9-01/02。

新增 immutable `ArgumentGroupBinding`：

- group id、governing predicate span；
- object/product span 与 semantic class `hardware|support|service|freight|financing|unknown`；
- price/currency span；
- connector/preposition span；
- attachment rule 与 confidence/ambiguity reason；
- representation/semantic digest。

规则：

- `for USD 150`、`USD 150 for support` 等 price 必须先绑定 object group；只有 `hardware/server/equipment/bundle` group 可产出 hardware price；
- support/service/freight/financing group 的 price 可以保留为 non-target role，但不能进入 ASP completion/coverage；
- `support USD150 and hardware USD15` 必须选择 hardware `$15`；只有 support `$150` 加 hardware product 时必须 partial；
- one-price 路径与 multi-price 路径使用同一 attachment contract；
- product/price/period/quantity anchor 从 accepted argument groups 派生，不再从 record 全局挑第一值；
- source/object/union/final 输出 role + group + predicate + span provenance。

验收：原 R8 anchor attack 和两条 audit mutation 全部正确绑定或 fail-close；合法单 hardware-price 正例仍 complete；support-only、freight、financing 近邻反例均 partial。

### R9-04：source→compiled frame transformation provenance seal

责任：S1 compiler/provenance integration。

依赖：R9-01/02/03 IR 已冻结。

输出每个 complete/partial family 的 `FrameTransformationBinding`：

- canonical source family id、source record id、source frame id/digest/spans；
- compiled object/window ids、compiled frame id/digest/spans；
- source/compiled `semantic_signature_digest`；
- transformation type `exact_slice|normalized_slice|bounded_window|many_object_same_source`；
- role-by-role source→compiled mapping；
- loss/addition/ambiguity flags 与 binding digest。

规则：

- representation digest 可因 absolute/relative span 或 bounded object window 不同；semantic signature 只在 target、predicate、normalized role、scope state 等价时相等；
- source complete→compiled complete 必须至少一条无 role loss/addition 的 binding；
- compiled complete 若没有 source complete antecedent，必须有可解释的合法 materialization path，否则是 provenance failure；
- many-to-one/one-to-many 必须列全部 object/source ids，不以相同 family id 代替证明；
- coverage 与 crosswalk 使用 semantic signature + role provenance，不能仅比较裸 anchor set。

验收：审计发现的 source/compiled digest 差异全部被 exact binding 解释，或在 implementation 阶段 fail；四层 complete-family set、每层 accepted frame 与 transform receipt 可独立重算。

### R9-05：六 target integration、冻结矩阵与 zero-call preview

责任：S1 target/compiler integration。

依赖：R9-01 至 R9-04；R8 public validator SHA 冻结。

输出：

- 新 `dell_report_predicate_frames_r9.py`；
- 新 `dell_report_internal_chain_ceiling_r9.py`；
- 新 R9 runner/test；
- 逐 attack/positive/anchor/privacy/provenance receipts；
- immutable-R8-raw zero-call full-corpus preview 与 current R8 crosswalk；
- source/object/union/final target counts/ranks、frame transformations、coverage、external/4B/reranker eligibility。

实现边界：R9 默认复用 `dell_report_public_validation_r8.py`，不改 shared active modules、R8 files、runtime registry 或 current consumer。若实现必须修改共享/活动路径，先暂停、报告影响并升级测试证据。

性能门：R8 preview=`35.276s`。R9 在 `>70s` 进入 profile/warning，在 `>120s` 强制停止；不得等待 10–20 分钟。任何 count/rank 变化逐 frame 解释；R8 counts 是 expectation 不是硬编码 golden。

### R9-06：风险分层 implementation freeze

责任：作者／Git hygiene；不调用模型。

R9 新文件默认不进入 active runtime，因此不用“全仓 pytest”证明一个不存在的活动消费关系。必须先用 import graph 和 active baseline 证明隔离；测试证据按风险升级：

- **T0（每个 patch）**：changed Python compile/static、JSON/JSONL parse、diff check、changed-path secret scan、R8 immutable SHA、R9 path allowlist。目标 `<30s`。
- **T1（每个 ticket freeze）**：R9 direct fixtures，只覆盖当前 ticket 和所有已冻结 R8/R9 attacks/positives。目标 `<30s`，硬停 `90s`。
- **T2（R9 integration freeze）**：R8+R9 显式 adjacent tests，不扫所有历史 R1–R7。目标 `<60s`，硬停 `120s`。
- **T3（仅 shared seam/provenance/runner freeze）**：选定 S1 compiler/runner/Project OS tests；目标 `<90s`，硬停 `180s`。
- **T4（条件式，不是 R9 默认门）**：只有修改 production/shared validator/active consumer、import graph 显示未知影响、T1–T3 暴露跨域失败或 owner 明确要求，才跑一次 full repository。R8 的 `1823 passed` 不能冒充覆盖 R9 新代码，但也不因新增隔离文件自动失效。

测试不得使用未建立 positive marker 的负向 `-m not ...` 排除。失败留在 owning tier；先定位最小影响面，不用全仓重跑“碰运气”。

Freeze 验收：T0/T1/T2、必要 T3 全通过；active import graph 证明 R9 未被当前 consumer 隐式导入；preview 在性能门内；没有 unexplained crosswalk；T4 触发条件逐项为 false，或若被触发则保存唯一 receipt。

### R9-07：policy-only authority、唯一 formal attempt 与 immutable seal

责任：作者／formal runner。

依赖：R9-00 至 R9-06 全通过、clean implementation commit 已 push。

计划输出：v1.8 policy、attempt `dell-rsq-03b-internal-chain-r9`、raw capture、receipt、private/public result、model-run 与 author-integrity record。具体 policy/attempt 在 implementation freeze 前不得创建。

规则继承 R8：authority 唯一 parent=implementation、changed path 仅 policy；clean/synced/collision/disk/exact paths/exclusive receipt/raw-before-compile/terminal failure receipt/atomic private-public；same attempt 不重试、不覆盖。保存 raw 后 exact replay private/public canonical bytes。

Formal model authority 仅为同 5 request 的一个本地 Qwen3-Embedding-0.6B query batch。network/Provider/generation/external/4B/reranker/Candidate/Evidence/promotion/closure 全为 0。

### R9-08：fresh bounded engineering audit 与 R17 receipt carry-forward

责任：全新 fork-none、作者分离、只读 reviewer；qualified human 另行。

审计从一开始拆包：

- Engineering A：identity/hash/topology/route/reprojection，checkpoint 后结束；
- Engineering B：coordination + semantic state，固定 mutation；
- Engineering C：anchor + transformation provenance + bounded recall/privacy；
- Report receipt：14-file R17 bundle 与 R8/R17 audit artifact SHA 全不变则继承 `FAIL_GATE_OPEN_NOT_ASSESSABLE`，只报告 carry-forward；任一变化才启动独立 report content audit。

Reviewer 禁止 full pytest、formal attempt、模型/网络、写入与递归历史扫描。允许固定文件、hash/JSON、内存 mutation，最多一次 R9 direct targeted pytest，且必须给出具体 material suspicion。每 phase 设命令清单和 wall budget；连续两个 60 秒周期无 checkpoint 则中断，已完成证据保留，余项 `NOT_ASSESSABLE`。

任何 material R9 finding 都使 03B independent=false，保留 R9 immutable bytes并回 same stage；R17 carry-forward failure 继续阻断 report/product，但不能篡改已独立通过的 R9 工程 verdict。

## 4. 冻结 R9 验收矩阵

### 4.1 no-comma coordination attacks

- `Dell shipped marketing materials and NVIDIA delivered four PowerEdge XE9680 AI servers in Q1 2026.`
- `Dell received financing and GPU capacity was allocated in Q1 2026.`
- `HBM supply was available to HP and Dell announced earnings in Q1 2026.`

断言 boundary decision、frame count、left/right subject/predicate spans、target completion=false 与 limitation。

Compound control：`Dell, NVIDIA, and Micron partnered for AI delivery.` 必须保持一个 shared-predicate frame，不能因 `and` 盲拆。

### 4.2 semantic-state attacks

- `Dell and NVIDIA partnered for delivery; this partnership was later suspended.`
- `Dell discontinued its partnership with NVIDIA for delivery.`
- `Dell is exploring a partnership with NVIDIA for delivery.`
- `According to an analyst, Dell partnered with NVIDIA for delivery.`

断言 exact modifier span、ScopeEdge、typed actuality/status/speech owner 与 completion=false。

### 4.3 price/product attachment attacks

- `Dell quoted support for USD 150 and PowerEdge XE9680 hardware for USD 15.` → hardware `$15` 或 typed ambiguity；绝不能 `$150`。
- `Dell quoted a support package for USD 150 for PowerEdge XE9680 hardware.` → partial；support `$150` 不得成为 hardware price。
- 继承 `Dell quoted $150 for support plus $15 for PowerEdge XE9680 hardware.` → hardware `$15`。

每条断言 argument groups、object semantic class、price span、attachment reason、accepted anchor。

### 4.4 inherited pass surface

- R7 63 negatives、R8 fresh 8 negatives；
- 6 fresh positives＋11 selected R7 positives；
- 15 public attacks＋3 valid controls；
- actual R8 four-layer complete-family counts/crosswalk；
- policy/runner failure/exact-once/public projection contracts。

### 4.5 transformation provenance

对 actual ASP 与 supplier complete families，逐层断言 representation digest、semantic signature 与 FrameTransformationBinding。source/compiled digest 不相等不自动失败，但缺显式无损 role mapping必须失败。

## 5. 工程、模型环节输出与最终研报质量标准

### 5.1 工程标准

- 每个 frame/boundary/state/argument group/transformation record immutable、canonical、digest 可复算；
- exact spans 落在 normalized source/document 或明确 compiled representation 中；
- completion 不跨 frame，scope 不跨无 edge 的 frame，anchor 不跨 argument group；
- source/object/union/final 使用同一 R9 classifier 和 semantic signature；
- current corpus 差异逐 family/frame 解释；
- public validator SHA 与 behavior 保持 R8 bounded pass；
- formal runner exact-once、raw-before-compile、failure receipt 与 atomic result seal 不退化。

### 5.2 模型节点 TokenBudgetBasis

#### Zero-call preview

- node purpose：验证 R9 compiler/semantics/provenance，不重新检索；
- input scale：immutable R8 raw execution、1,888 sources、34,199 objects；
- required outputs：六 target 四层 counts/ranks、frames/state/argument/transformation receipts、crosswalk；
- schema burden：新增 boundary/state/argument/transformation records；
- materiality risk：false complete、false partial、unexplained transformation；
- comparable evidence：R8 preview 35.276s、exact replay 42.489s；
- reasoning profile：deterministic zero-model；
- stop/truncation：70s warning/profile、120s hard stop、无 partial authority。

#### Formal 0.6B query embedding

- node purpose：在 R9 frozen compiler 上重现同 5 request candidate pool；
- input scale：5 query、one batch、每 request 96 union/16 final contract；
- required outputs：raw query embedding/retrieval result plus complete execution counters；
- schema burden：raw capture before compiler、exact SHA、private/public links；
- materiality risk：identity drift、missing request、rank/candidate drift；
- comparable evidence：R8 one local batch、338 union/80 final；
- reasoning profile：local deterministic embedding，无 generation；
- stop/truncation：任一 request/counter/schema/identity 不完整则 attempt 失败并保存 receipt，不重试。

4B/reranker TokenBudgetBasis 不在 R9 创建，因为调用 authority=false。它们保留到 R9 fresh PASS 后、真实新 candidate pool 与 eligibility 出现时另立 authority。

### 5.3 模型环节输出质量

- semantic：三 no-comma、四 scope、全部 inherited negatives false-complete=0；17 个选定 positives false-negative=0；
- anchor：三 price attacks 均正确或 typed partial；合法 hardware-price controls complete；
- provenance：actual complete families 100% 有 transformation binding；role loss/addition=0；
- recall/current route：任何 count/rank 改变都有 exact frame explanation；
- privacy：15/15 attacks reject、3/3 valid accept；
- formal：5 requests、1 local batch、exact 96/16、forbidden counters zero。

### 5.4 最终研报质量标准与 R9 边界

R9 不生成研报。后续 report successor 必须消费本次 R17 审计确认的真实缺口：

1. 建立 `ClaimSourceBinding`：每个 report claim/EV 精确映射 source record/material ref、issuer/title/date/period、passage text digest、quote/locator、stable URL 与 use boundary；内部 EV membership 不能替代。
2. Reader source appendix 必须展示可解析 locator/URL；material claim 的 citation 可从报告回到 exact passage。
3. 14/9/4/10 crosswalk content digest 必须绑定并完整呈现，包含 price-in、scenario/sensitivity、supplier-capacity read-through、valuation basis。
4. 六 WWC 必须有 trigger、direction、horizon/window、threshold/authority、observable/source、owner、response/decision route；method threshold 先冻结。
5. 数值关系继续可重算，ASP/units/share→PVM→product profit/working capital 的期间、单位、PIT、formula lineage 完整；输入不足保持 typed gap。
6. 72/36 重复基线必须显著下降；事实表只呈现一次，叙述聚焦 interpretation/counter-thesis/boundary。
7. 02B 16 项仍需 qualified-human decisions；其前 formal 8D score=null。
8. 新报告 non-overwriting R17，工程/研报双审计与 qualified-human 分离。

在这些 artifact 未变化时，R9 不重复评估同一 R17 内容，只 hash-lock carry-forward failure；这不是忽略研报质量，而是避免对 immutable failure 重复付费。

## 6. 停止条件与变更控制

立即停止且不签 R9 policy：

- 任一三 no-comma、四 scope、三 anchor attack 仍 false complete/错绑；
- compound subject 被错误拆分或任一 17 positive 退化；
- completion/state/anchor 缺 frame/span/group provenance；
- source→compiled complete 没有明确 transformation binding；
- R8 public attack/valid controls 任一退化；
- current corpus 差异无法逐 frame 解释；
- T1 >90s、T2 >120s、T3 >180s 未先停止/profile；
- preview >120s，或 >70s 后未停止定位；
- 实现需要修改 active shared consumer、runtime registry 或 R17/report artifacts 而未先报告影响；
- identity/secret/static/JSON/diff/targeted gate 失败。

测试失败不创建产品版本。Formal failure 保存 immutable receipt，用新 attempt/version 需新的原因与 authority。若新证据要求扩大到外源、4B、reranker、Evidence、S2 或 Writer，先暂停并向 owner 报告，不静默扩权。

## 7. R9 fresh PASS 后的下游顺序

R9 fresh independent PASS 后仍按完整产品链继续：

1. 重算 residual/gap crosswalk，并执行四个 residual 的完整外源梯子；
2. 对真实新增 candidate pool 做 0.6B/4B mixed embedding shadow；4B 是 recall challenger；
3. 在真实 rerank eligibility 或固定独立候选集上运行 reranker，不人为制造调用；
4. CandidateDecision/Evidence Gate 与 qualified-human 02B；
5. Pack/Readiness、units/share、ASP/mix、PVM、product profit、working-capital attribution；
6. Readiness 后只运行受影响 DELL 动态单元；
7. 建立 claim-source locator contract，生成 non-overwriting R17 successor；
8. 工程 audit、研报 quality audit、qualified-human final judgment 分离；
9. 全部门通过后才讨论 product/publication/release。

## 8. Definition of done 与当前 authority

R9 plan done：本文件与 Project OS 明确记录 tickets、依赖、输入输出、工程与模型输出标准、研报质量 carry-forward、风险分层测试、命令/时间预算、TokenBudgetBasis、停止条件和下游顺序。

当前仅允许：

- 新建 R9 semantic/compiler/runner/tests；
- 运行 T0/T1/T2 与触发时的最小 T3；
- immutable R8 raw zero-call preview；
- clean implementation commit/push 后再建立 policy-only authority、唯一 formal R9 与 bounded fresh audit。

当前明确 false：R9 policy/attempt/result/fresh pass、03B independent、03C external、4B、reranker、CandidateDecision、Evidence/NumericFact、gap closure、Pack/Readiness、S1/S2/S3、R17 successor、formal 8D、qualified human、product、publication、release。R9 author implementation/preview 的后续状态见第 10 节。

## 10. 2026-08-27 实施状态回写

- R9-00～R9-05 已实现：punctuation-independent `FrameBoundaryDecision`、typed semantic state/`ScopeEdge`、`ArgumentGroupBinding`、representation/semantic digest separation、lossless `FrameTransformationBinding`、六 target compiler、explicit preview/formal/replay runner、exact-once/raw-first/redacted-failure/atomic-pair 合同均已有直接测试。
- 零调用全量 preview 读取 immutable R8 raw、1,888 source/34,199 object，用时 `39.649437s`；ASP=`1/1/1/1 rank2`、supplier=`3/3/2/1 rank2`、四 residual=`0/0/0/0`，六 target complete transformation coverage=true，完整计数/排序相对 R8 无变化。312 条 partial-family diagnostics 保留为显式非 complete receipt；external target=4，当前 4B/reranker eligible=0。
- R9-06 行为与静态门已通过：T1=`56`、T2=`153`、T3=`93`，compileall/pyflakes/import isolation、active baseline=`213/8/5/28/0`、8 JSONL/1,319 rows、8,179-file secret scan/0均通过。R9 未修改 shared/active surface且无跨域失败，故 T4 trigger 为 false；staged diff/commit/push仍在 implementation Git closeout。
- R9-07/08 仍未执行：v1.8 policy、formal attempt、private/public result、exact replay、immutable audit manifest和 fresh dual audit 均不存在。工作记录 105 是本状态的详细证据。
- 更正本计划末尾的旧状态：`R9 implementation=false` 已被作者实现与 preview证据取代；但 `R9 executed=false`、`R9 independent=false` 以及所有 03C/4B/reranker/Evidence/S2/S3/report/product authority 仍为 false。R17 固定 14 文件质量失败继续原样 carry forward。
