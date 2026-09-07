# S1 工作记录 096：DELL 03B R7 program-level execution plan

日期：2026-08-26

状态：`approved same-stage non-overwriting R7 plan / implementation not started / no R7 policy, attempt, private or public result`

## 1. 目标、成功含义与不可变边界

R7 只修复 fresh R6 dual audit 在 owning stage 复现的三个通用根因：

- `RC-S1-079`：R6 的“typed clause”仍是正则命中包装，完成组可跨 proposition/clause/sentence 做 existential union；缺少真正的单一命题角色绑定。
- `RC-S1-080`：material anchor 仍从文本扫描，未绑定到同一 accepted proposition 的产品、价格、数量、期间与 process role。
- `RC-S0-105`：递归 key allowlist 已存在，但允许字段的字符串内容缺少 field-typed fail-closed validation。

R7 的成功含义仅是：03B candidate-chain 的通用语义、materialization coverage 与 public projection 经过作者门和新鲜独立审计。它不等于补源完成、Evidence admission、S2 完成、R17 研报修复或产品验收。

R6 policy/private/public/receipt/audit、保存 raw execution 与 Git identity 全部 immutable；R7 必须使用新 module、runner、tests、schema、policy、attempt、private/public result path。不得原地修改或追认 R6，不得复用 R6 attempt。

R7 不执行网络、外源、4B embedding、reranker、Provider、生成模型、CandidateDecision、Evidence/NumericFact promotion、gap closure、S2 或 Writer。当前 R6 actual route 中 ASP 的 reranker eligibility 和四个 residual target 的 external eligibility 只作为 bounded input 保留，不在本阶段消费。

## 2. 设计不变量

1. **一个 complete 对应一个 proposition**：所有 required semantic roles 必须来自同一 sentence/clause span 和同一 proposition ID。不同 proposition、不同 clause 或不同 sentence 的 group 不得求并集后升级 complete。
2. **命题先于完成组**：先抽取 typed proposition，再从 proposition roles 映射 group；不得先在 package 上积累 group，再补一个 guard 追认 typed。
3. **anchor 只来自 accepted proposition roles**：不得对整句、整段或 package 做通用数字扫描后供所有 target 共享。
4. **显式不确定性**：polarity、modality、status/revocation、reported-speech owner、qualifier、unit/process 缺失或冲突时 fail-close 为 partial，不用近似猜测补槽。
5. **公开值也需要 schema**：key 合法不代表 value 合法；每个公开字段必须有明确类型、grammar、长度/字符和 locator/secret/traversal 约束。
6. **成功不得跨阶段外推**：R7 fresh PASS 最多签发下一受控 route 的规划资格，不自动签发 external/reranker/4B、Evidence、S2 或报告。

## 3. 需求票与依赖图

依赖顺序：`R7-00 -> R7-01 -> R7-02 -> R7-03 -> R7-04 -> R7-05 -> R7-06 -> R7-07`。R7-04 和 R7-05 在 R7-03 后可独立实现，但 formal policy/attempt 必须等待两者和全部门禁共同通过。

### R7-00：冻结 predecessor、审计 finding 与 regression corpus

输入：R6 policy/public/private/receipt、R6 fresh dual-audit、R6 implementation/authority/result Git identity、R5/R4 由 R6 已绑定的 predecessor、current R39 runtime、R17 质量 artifact refs。

输出：

- 精确 predecessor binding set 与 SHA/digest；
- R6 审计 `0/0/3/0` 和 R17 open `0/1/2/1` 的结构化校验；
- R6 95 个作者测试、fresh audit 全部新 attack/positive control 的冻结 fixture；
- R7 实现期不得改变的 authority matrix。

验收：R6 audit identity、self-digest、reviewed commit/tree/parent、三项 root cause、R17 四项 open finding 任一漂移均 fail；不得只检验状态字符串。

### R7-01：TypedProposition IR 与稳定 clause/sentence provenance

输入：一个 bounded source/compiled package 的原始 sentence units、clause spans、metadata 和 target ID。

输出：每个候选命题一个 deterministic `TypedProposition`，至少包含：

- `proposition_id`、sentence/clause index、start/end span；
- `actor/subject`、`predicate/action`、`object`、`recipient/counterparty`；
- `polarity`、`modality`、`status`、`revocation/suspension`；
- `speech_mode`、`reporter/speaker`、`asserted_actor`；
- `quantity`、`measure`、`currency`、`unit/denominator`、`qualifier`；
- `product/entity`、`period`、`process`；
- `role_conflicts`、`missing_required_roles`、`limitations`。

规则：

- sentence/clause boundary 必须保留原 absolute provenance；相同文本不能先去重再赋位置；
- 并列句可以产生多个 proposition，但每个 proposition 的 roles 独立；
- rumor/allegation、第三方报告、Dell 自述、Dell 否认与事实陈述必须区分；
- later revoked/suspended/withdrawn 等状态作用于对应 proposition，不得被切成无关肯定命题；
- 能力态、预测态、零值与 observed fact 分开编码。

### R7-02：六 target 的 proposition extractor 与 role contract

依赖 R7-01。每个 target 只在一个 proposition 内校验 required roles：

- **ASP**：Dell 必须是 seller/quoter，price/currency、physical product/configuration、quantity/denominator 若语义需要必须同命题；`can/allegedly/denied/withdrew quote` 不 complete，其他公司报价不得与 Dell 数量拼接。
- **supplier read-through**：named supplier、Dell recipient/counterparty、supply/delivery/relationship predicate、affirmative/actual status 同命题；rumor、denied、suspended 与仅 capability 不 complete。
- **capacity release**：upstream capacity/allocation、Dell recipient、非零 committed/earmarked/allocated status、period/process 同命题；HP recipient、can allocate、zero allocation、later revoked 不 complete。
- **observed yield/utilization**：相关 manufacturing/HBM process、observed/achieved measure、percent、period 同命题；forecast/can reach/simulated/withdrawn/wrong-process/橙汁等不 complete。
- **HBM supply bridge**：Dell/PowerEdge product、HBM component、incorporation/configuration/allocation/supply predicate 和 affirmative status 同命题；无关 HBM constraint 加其他 process yield 不 complete。
- **units**：Dell 是实际 seller/shipper、physical server product、quantity、period 同命题；客户转述、Dell disputed report、客户部署或 GPU count 不 complete。

输出：`accepted_proposition_id` 至多一个；若多个合格，按稳定 provenance/materiality 规则选择并保留 alternatives，不合并 roles。`matched_group_ids` 必须完全由 accepted proposition 映射；package-level R4/R6 group 只能作为 recall hint，不能作为 completion authority。

### R7-03：single-proposition completion 与 source/object/candidate 一致性

依赖 R7-02。

输出：source、compiled、union、final 各层的 completeness、package role、limitations 与 accepted proposition digest。

规则：

- complete 当且仅当一个 proposition 同时满足 target contract、in-period 与 materiality；
- 不允许 `all(group in package_groups)` 形式跨 proposition 升级；
- source 与 object coverage 比较 proposition digest/role anchors，不比较散落 group union；
- parent/slice/candidate family 去重不得改变 proposition span 或制造 adjacency；
- source/compiled/union/final 结果若不一致，必须输出具体缺失 role/anchor，不得只给 boolean gap。

### R7-04：role-bound material anchor v3

依赖 R7-02/03。

输入：accepted proposition 的 typed roles，不再输入未经筛选的整句供通用扫描。

输出：稳定 role-labeled anchors，例如：

- `product_code:h100`、`product_code:xe9680`；
- `price.currency_usd:15`、`price.magnitude:million`、`price.qualifier:about|at_most`；
- `quantity.physical_server:2`；
- `period.fiscal_year:2026`、`period.quarter:1`；
- `yield.percent:90`、`process:hbm_production`。

等价语法必须覆盖：H100/H100s/H-100s/H−100/H_100，已知 H/B/A/GB/MI/XE 系列的合法 separator/复数；FY26/FY2026/FY'26/FY’26/fiscal 2026；`$15`、`USD 15`、`USD$15`、`15 dollars`、`$15m` 及合法 decimal/magnitude/qualifier。产品码内部数字不得变成 quantity/price/year；无关 support/freight、HP/B200/100-unit 或第二 proposition 的数字不得进入 Dell target anchors。

coverage 必须比较同 role 的 canonical anchor；`price=15` 不能被 `support_cost=15` 覆盖，`price=150` 加无关 `15` 不能形成 zero gap。

### R7-05：field-typed public content validator

依赖 R7 private/public schema 清单。

输入：R7 private result；输出：R7 public projection。

规则：

- 保留 R6 exact recursive key allowlist；对每个 allowed path 绑定 value validator；
- SHA/digest/commit、target/request/attempt ID、branch、repo-relative ref、status/enum、计数、rank、bool 分别使用严格 grammar；
- canonical repo-relative ref 只允许正斜杠、已知根前缀、无 scheme、无 drive、无 leading slash、无 empty segment、无 `.`/`..`，需要时校验与 bound ref exact equal；
- narrative/limitation 字段拒绝 credential-like assignment、secret-like/high-entropy token、control chars 和 locator；先 percent-decode 再检查 scheme、`www`、UNC、absolute/relative traversal 与 backslash traversal；
- financial narrative 中合法 `$15`、百分比、产品码和普通英文/中文不得被误杀；
- 任何 unknown path、validator 未注册 path 或 ambiguous scalar fail-close。

### R7-06：predecessor、policy、exact-once 与 atomic output seal

依赖 R7-00 至 R7-05 全部通过。

输出：新 `v1.6` policy validator 和 exact-once runner。

规则：

- policy schema=`fin_ia_dell_report_internal_chain_ceiling_policy_v1_6`；attempt=`dell-rsq-03b-internal-chain-r7`；public/private result schema/path 使用 v1.6；
- 绑定 R6 policy/public/private/receipt/fresh audit 与 R6 Git identity，并继承/复验 current R39 和全部必要 predecessor；
- implementation commit 先独立 clean push；policy-only authority commit 的唯一 parent 必须是 implementation，唯一 changed path 必须是 R7 policy；
- attempt/output collision、clean `HEAD==upstream`、minimum free disk、exact branch/commit/tree、canonical path、exclusive receipt、atomic private/public pair 与 no retry 全 fail-close；
- 正式执行仍为 5 个冻结 request、1 个 local Qwen3-Embedding-0.6B query batch、每 request 精确 96 union／16 final；network/provider/generation/external/4B/reranker/retry/mutation/promotion/closure 全为 0。

### R7-07：作者结果、独立双审计与 authority transition

输出：作者 exact replay/reprojection、immutable result record，以及另一个全新 fork-none、作者分离、只读 reviewer 的 R7/R17 dual audit。

审计必须同时覆盖：

- R7 Git/attempt/digest/raw replay、proposition semantics、role anchors、public field content、route counts；
- R17 reader citation/source appendix、gap crosswalk consumption、WWC operationalization、事实密度/重复、定量可重算、边界诚实、02B/qualified-human/formal 8D。

R7 finding 与 R17 finding 分开计数。Reviewer 不得写文件、改结果、调用外源/4B/reranker 或冒充 qualified human。若有 material finding，R7 不通过；保留 R7 immutable bytes，回到 owning stage 另开 successor，不以审计记录覆盖结果。

## 4. 冻结输入与新增输出

冻结输入至少包括：

- R6 implementation=`512aa32b0f312499b430c483ebfd3fbd9c520d38`、authority=`b6410eb274601abc0913c90f6b4adcf08c91cd48`、result=`9ca3c83087644496c08ddcc43b5a7d871efa52ef`；
- R6 v1.5 policy/public/private/receipt 与 raw execution；
- R6 fresh audit digest=`11935696805f386364661f95c0ab1ae3076f86f5edc562d8d58f339e39516342`；
- current R39 source=1,888、objects=34,199 与 runtime binding；
- R6 已绑定的 R5/R4/predecessor artifacts；
- R17/crosswalk/method/02B artifacts仅用于保持 report-quality boundary，不参与 R7 semantic completion。

计划新增、不得提前存在的输出：

- `src/retrieval/dell_report_internal_chain_ceiling_r7.py`
- `scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r7.py`
- `tests/test_dell_report_internal_chain_ceiling_r7.py`
- `configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_6.json`（implementation clean push 后才生成）
- `configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_result_v1_6.json`（唯一 formal attempt 后才生成）
- canonical ignored private/receipt under attempt `dell-rsq-03b-internal-chain-r7`。

R7 policy 的 bound-input 与 implementation-file exact set 由实现完成后的 validator 冻结；计划阶段不猜测最终文件数。

## 5. 冻结测试矩阵

### 5.1 Semantic false-complete attacks

- supplier：`allegedly partnered`、partnership rumor denied、partnered then suspended、`can supply`；
- capacity：allocated to HP rather than Dell、`can be allocated`、zero allocated、later revoked；
- yield：`can reach 90%`、figure later withdrawn、simulated yield、HBM constraint 加 orange-juice yield；
- units：customer reported Dell shipped、Dell disputed/denied reports it shipped；
- ASP：Dell `can quote`、allegedly quoted、withdrew quote、HPE quoted price 加 Dell offered quantity；
- 所有 R4/R5/R6 已冻结的 negation、future、wrong-process、reported-speech、dedup-before-position、substring-anchor attacks。

### 5.2 Positive recall controls

- `NVIDIA is Dell's supplier for AI server delivery.`
- capacity `was earmarked for Dell`；
- PowerEdge systems `incorporated HBM`；
- HBM production `achieved a 90% yield`；
- Dell `sent four ... servers`；
- Dell `sold two ... servers for $15`；
- R6 当前真实 ASP/supplier packages 与所有既有 positive controls。

### 5.3 Anchor attacks/controls

- H100s/H-100s/H−100/H_100/H/800、FY'26/FY’26/fiscal 2026/FY2026；
- `USD$15`、`15 dollars`、`$15m`、`about $15`、`at most $15`；
- unrelated `$150` support、shipment freight `$15`、HP B200/100 units、命题价格 `$150` 加无关 `$15`；
- 同 role 等价语法 coverage=pass；不同 role 或不同 proposition 的同数值 coverage=fail。

### 5.4 Public content attacks/controls

- allowed narrative/identifier/ref 中的 secret-like/high-entropy payload、credential-like assignment、percent-encoded locator、`..` parent traversal、backslash traversal、UNC/drive/absolute path；
- unknown key、literal network locator 和 absolute path 的 R6 controls；
- 合法 SHA/digest/commit、repo-relative refs、target/request IDs、中文/英文 limitation、货币/百分比/产品码 narrative 必须通过。

## 6. 工程验收标准

1. R6 95 tests 全部在 R7 seam 下保持通过；R1/R3/R4/R5/R6/R7 adjacent contracts 不回退。
2. 5.1–5.4 的每个 attack/positive control 都有独立断言，不能用一个 broad assertion 掩盖多种失败。
3. `TypedProposition` deterministic：相同输入重复编译得到相同 IDs、spans、roles、limitations 与 digest；roles 不共享可变状态。
4. complete 的实现路径中不存在 package-level required-group union；测试直接构造两个各缺一槽的 proposition，合并后仍必须 partial。
5. source/object/union/final 只比较同 proposition contract 与 role anchors，所有 mismatch 输出具体 role/anchor reason。
6. public projection 对每个 allowed field path 有 validator coverage；新增 allowed field 若无 validator 必须失败。
7. R6/R39/predecessor bytes 不修改；R7 preview 不写 policy/private/public/receipt，不消费 attempt。
8. targeted、adjacent、Project OS、active baseline、compileall、pyflakes、config JSON、Project OS JSONL、secret scan、`git diff --check` 与 full repository 全通过。

## 7. 模型节点与研究输出质量标准

### Formal 0.6B query batch TokenBudgetBasis

- purpose：在语义编译器变更后，对同一五个冻结请求生成正式、可审计的 candidate ranking trace；不承担 proposition 判断。
- input scale：current R39 1,888 source records／34,199 compiled objects，5 requests。
- required outputs：每 request 96 unique union／16 unique final、连续唯一 rank、raw execution SHA/digest、完整零权限 counters。
- schema burden：R6 predecessor/fresh audit、R39 runtime、R7 proposition/anchor/public schema、Git/attempt/atomic-output seal。
- materiality/quality risk：candidate drift、truncation、重复 rank、CPU/network fallback 或非冻结模型会破坏比较；全部 fail-close。
- comparable evidence：R6 one local Qwen3-Embedding-0.6B batch、5×96/16、saved-raw exact replay；R7 不增加 request 或 output 上限。
- reasoning profile：embedding only，无生成式 reasoning/token output；4B/reranker/Provider/network budget=0。
- stop/truncation：任一 request 缺 96/16、模型/设备/registry 不符、OOM/fallback、output collision、disk 或 identity gate 失败即停止；同 attempt 不重试。

### Semantic/anchor output quality

- 冻结 controlled set 的 false complete=0、false negative=0；每个判定可追溯到一个 proposition ID 和 role contract。
- source/compiled/union/final completeness 使用同一 R7 classifier，不允许某层回退 R4/R6 package union。
- role-anchor equivalence 对所有等价语法稳定；跨 role/跨 proposition 污染=0。
- current corpus 若与 R6 counts 不同，必须逐 target、逐 proposition 给出 sentence/package-level cause；未解释前停止，不签 policy。
- empty local result 仍不是 proved public-information gap；external route 只是下一候选动作。

### Privacy output quality

- private exact recompile、public exact reprojection；public/private link、四 self-digest 与 raw SHA 精确。
- unknown key、unknown validator path、所有冻结 content attacks 100% 拒绝；合法 control 100% 通过。
- 当前 public 不含 private/model/material text、locator、credential-like/high-entropy payload、scheme、absolute/relative traversal。

## 8. Current corpus 预期与差异处置

R7 不是检索扩容；formal candidate pool 与 R6 同源。因此默认预期仍为：

- ASP=`2/2/2/2`，best final rank 15，reranker challenger eligible；
- supplier=`2/2/2/1`，best rank 2；
- capacity/yield/HBM/units=`0/0/0/0`；
- material coverage gaps=0；external route candidate=4；target-specific 4B recall eligible=0。

这不是硬编码的“必须相同”。若 true proposition binding 识别出 current corpus 中此前漏掉的真实同义正例，必须保存 before/after proposition crosswalk、证明同一 source/object materialization，并由测试与作者复核后才能接受；若任何原有 complete 被撤回，同样必须给出具体 invalid role。无法解释则停止在 implementation，不签 policy。

## 9. 上一版研报信源缺失与后续完整顺序

R7 不会假装已经解决上一版研报的 14 个 gap，也不会在 classifier 修复期间擅自补源。R7 fresh audit PASS 后，完整下游顺序仍是：

1. 重新基于 R7 结果生成 residual gap/route crosswalk，把每项明确归属 S1 retrieval、S2 numeric derivation、S3 Writer/WWC 或 genuine commercial/private boundary；已有本地证据不得重复补源。
2. 对 ASP rank-15 的同一冻结 candidate pool 执行独立 reranker challenger；reranker 没有被取消，其结果不能替代 Evidence admission。
3. 对 capacity/yield/HBM/units 执行完整、可回执的外源梯子，而不是只抓少数方便页面；取得候选后再做 provenance、materiality、时间和角色验收。
4. 4B mixed embedding challenger 继续保留；只有外源/新增候选 pool 的 target-specific recall eligibility 被正式证明时，才在 8GB GPU 的量化/显存预演通过后与 0.6B 同请求对照。当前 R6/R7 预期 eligibility=0，故 R7 内不运行。
5. 对通过的候选执行 CandidateDecision/Evidence Gate；02B human-required 项必须由 qualified human 决定。未通过即保留 gap，不得把空结果当 public-information gap。
6. 重编 current Pack/Readiness 与受影响的 units/share、ASP/mix、PVM、产品利润、营运资金归因；只运行受影响 S2/动态单元。
7. 生成不覆盖 R17 的新报告：消费 accepted crosswalk，提供读者可读 citation/source appendix，typed WWC、阈值/owner/evidence/response route，降低重复并保持所有未证实桥为 null/open。
8. 分别做工程审计与研报质量八维审计，最后由 qualified human 验收；没有 material finding 才能讨论产品/publication/release。

因此，“R7 先做”是为了保证后续补源和报告不会被错误 classifier/anchor/privacy route 污染，不代表信源缺口已解决。

## 10. 最终研报质量门（R7 只保持，不消费）

Fresh R7 auditor 必须把 R17 质量继续纳入审计范围，至少核对：

- reader-visible claim-to-source citation 与 source appendix；
- 14 Pack／9 dynamic／4 Writer groups／10 Writer refs／4 S2 bridges 的 crosswalk consumption；
- 六项 WWC 的 metric、direction、window、threshold、authority、owner、evidence route、response route；
- 数值 presentation/relations、margin bridge、non-GAAP 标识与 PVM/ASP/units/product/WC boundary；
- 事实密度、重复、反方/不确定性、可读性与 publication safety；
- 02B decisions、qualified-human 身份与 formal 8D prerequisites。

R7 PASS 不能修改 R17 verdict。只有未来 R17 successor 实际消费合格 Evidence、S2 与 crosswalk 后，才能进行正式报告评分。

## 11. 阶段顺序、停止条件与责任边界

1. 本计划完成 Project OS 固化、校验、独立 commit/push；此时 implementation=false。
2. 实现 R7-00 至 R7-05 和 targeted tests；不得创建 policy/attempt/result。
3. 用 immutable R6 raw execution 做零模型 full-corpus preview 和 public projection attack suite。
4. 任一 false-complete/false-negative、cross-proposition union、anchor pollution、合法 public control 误杀、current-count drift 未解释或 predecessor mutation，立即停止在 R7 implementation。
5. targeted/adjacent/full repository 与 Project OS 门全部通过后，才做 clean implementation commit/push。
6. 在 implementation identity 冻结后才生成 policy；policy 单文件 commit/push，不能与实现混合。
7. 只有 clean `HEAD==upstream`、parent/path/input/output/disk 全 exact，才消费唯一 R7 attempt；任何失败保留 receipt，同 attempt 不重试。
8. 作者 exact replay/reprojection 和 immutable result commit/push 后，启动一个从未参与 R7 作者工作的全新 fork-none read-only reviewer。
9. Fresh dual audit 有 material finding：R7 independent=false，保留 immutable R7，回到 owning stage 开下一 successor；无 material finding也只按 audit 明示的 authority transition 前进。
10. 03C、4B、reranker、Evidence/NumericFact、gap closure、S2、Writer、产品、publication、release 在对应显式 gate 前持续 false。

责任边界：作者负责 R7 plan/implementation/preview/exact result 与作者门；fresh reviewer 只读审 R7 和 R17；qualified human 负责 02B 和最终报告/产品验收。三种角色不得互相冒充。

## 12. 计划固化门

- Project OS preflight=`82 passed`。
- config JSON=`1,149`；Project OS JSONL=`8 files / 1,285 rows`，全部可解析。
- repository secret scan=`8,144 files / 0 findings`；`git diff --check` 通过。
- 计划固化期间 model/provider/network/embedding/4B/reranker/external/runtime mutation/policy/attempt/result 均为 0。
