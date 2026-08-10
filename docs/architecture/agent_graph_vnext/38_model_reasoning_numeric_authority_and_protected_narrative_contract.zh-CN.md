# 模型研究判断、数值权威与受保护叙事合同

日期：2026-08-07

状态：稳定金融事实/纠错合同已 `runtime_injected + deterministic_proven`；DeepSeek 最小自然 canary 在 evidence-role/closure 失败；Provider-neutral capability profile、adaptive autonomy 和 constraint retirement 仍为 `contract_translated / runtime_not_implemented`。本文不是新的业务真相 owner，也不表示 DeepSeek 或产品已通过验收。

## 1. 为什么需要本合同

历史文档已经分别写过：模型选择数值 alias、本地渲染 exact value、Writer 不补源、Numeric Agent 拥有 material number、Verifier 检查 lineage。但这些规则分散在局部故障处置和单节点合同中，没有统一回答五个不同问题：

1. 模型能否看到精确数字；
2. 模型能否用数字做比较、机制分析和判断；
3. 模型如何引用数字和来源；
4. 模型能否在自由文本中直接写 material number；
5. 谁负责把最终数字、单位、期间、引用和身份写进成品。

这使“收回数值权威”容易被误解为“不给模型数字、由本地脚本代写报告”，也使 Runtime 在自由生成与机械模板之间来回摆动。FIN 的正式原则是：

> 模型可以看见、理解、选择和引用受治理的事实；但 material fact 的最终写入、换算、舍入、身份、期间、单位、引用和 lineage 由确定性 Harness 负责。Harness 是 truth compiler，不是 report author。

## 2. 五种权限必须分开

| 权限 | 模型 | 本地 Harness | 说明 |
| --- | --- | --- | --- |
| `visibility_authority` | 是 | 编译输入 | 模型必须看到具备语义名称、exact value、unit、scope、period、source 和 authority 的 `NumericFact`，不能只看到无意义 ID |
| `reasoning_authority` | 是 | 提供边界与校验 | 模型负责比较、归因、机制、反方、冲突、置信度、gap 和 thesis，不因事实写入权被收回而失去分析权 |
| `citation_selection_authority` | 有界 | 验证并绑定 | 模型选择 Evidence/Numeric ref 说明依据；不得发明 ref、source 或 locator |
| `freeform_authoring_authority` | 判断叙事为是；material fact span 为否 | 保护受控 span | 模型可以写自然语言机制和结论；关键数字、日期、实体身份、公式结果和 citation 使用受保护引用 |
| `render_and_promotion_authority` | 否 | 是 | 本地按 ref 生成精确展示、执行换算/舍入规则、绑定引用、验证最终成品并决定是否晋升 |

“模型不能随意写 material number”不等于“模型不知道数字”或“模型不能引用数字”。模型输入中的事实必须足以支持研究判断；限制的是最终事实表面的无权改写。

## 3. 三类输出面

### 3.1 本地硬权威面

以下内容由本地单源合同生成或验证：

- case/entity identity、as-of、period、currency、unit；
- exact amount、ratio、formula result、允许的 scale conversion 和 rounding；
- Evidence/Numeric/Gap ID、source locator、citation、lineage；
- artifact/run/attempt/version identity 与 promotion status。

### 3.2 模型研究面

以下内容必须保留给模型或 human analyst，不能由模板代写：

- 证据选择与重要性排序；
- 因果机制、经济含义和跨证据综合；
- thesis、counter-thesis、冲突处置和不确定性；
- 什么证据会改变判断；
- 报告故事线、段落组织和面向受众的解释。

### 3.3 受保护混合叙事面

模型输出自然语言，但用 typed refs 表达 material fact，例如：

```text
AI server growth is economically meaningful because [NUM:DELL_N07]
expanded while [EVID:DELL_E09] indicates the mix shift is not yet a
clean company-wide margin proof.
```

本地只替换受保护 span、绑定 citation 并做一致性检查，不改写“为什么重要”“能否外推”“反方是什么”。最终产物不得残留 placeholder，也不得出现无绑定 material number。

## 4. 建议对象

### `NumericFactView`

- `numeric_ref`
- `semantic_name`
- `exact_value`
- `display_surfaces`
- `unit / currency / scale`
- `company / segment / product / geography`
- `period_role / period_start / period_end / as_of`
- `source_ref / authority / formula_trace`
- `allowed_uses`

### `ProtectedNarrativeDraft`

- `narrative_text`
- `numeric_refs[]`
- `evidence_refs[]`
- `gap_refs[]`
- `analyst_threshold_refs[]`
- `unsupported_span_findings[]`

### `CorrectionObjective`

- `correction_id`
- `finding_code / target_path / reason`
- `required_resolution`
- `allowed_authorities[]`
- `closure_rule`
- `affected_node / downstream_consumers[]`
- `unresolved_policy`

### `CorrectionClosureReceipt`

- `correction_id`
- `status = closed | typed_unresolved | rejected_new_violation`
- `before_ref / after_ref`
- `evidence_or_gap_refs[]`
- `new_findings[]`
- `validator_version`

默认使用最小 typed patch；只有整个节点语义失效时才允许整节点重算。整节点重算必须重新检查所有已关闭 L1/L2，不能修一处又重开另一处。

## 5. 假设、阈值与事实必须分轨

- 已披露事实：只能引用 `NumericFactView`。
- 可复算派生值：必须引用 `NumericProgramTrace`。
- 管理层 guidance：保留原始措辞、范围和期间。
- analyst scenario / WWC threshold：使用独立 `AnalystThreshold`，标明是研究假设、计算依据和敏感性，不得冒充公司披露。
- 方向性词语如“中个位数”不得自由改写成 `约 5%`；若研究确需数值阈值，必须新建有依据的 analyst threshold，而不是伪装成 source fact。

## 6. 防止报告质量下降的硬约束

1. Harness 不得生成 thesis、因果机制、counter-thesis 或完整报告段落。
2. semantic alias 必须对模型可读，不能把模型降级成盲选 ID 的分类器。
3. 只在 material spans 上使用保护机制；普通定性叙事保持自然生成。
4. style/edit pass 必须发生在受保护 span 替换之前，或通过 protected-span diff guard 保证事实不被重写。
5. correction 默认局部修复，避免整节点重写造成内容漂移和新 L1。
6. 最终验收同时检查事实安全与研究内容，不能以 `L1=0` 掩盖模板化、低密度、无机制的报告。

## 7. 验收与失败口径

### 确定性门禁

- material numeric ref coverage = 100%；
- placeholder residue = 0；
- 未绑定 material number/date/entity/citation = 0；
- unit/period/scope/source/identity mutation 全部 fail closed；
- 每个 assigned correction 都有 closure receipt；
- DELL/MU/NVDA full-fake、历史 U3/U4 capture replay 和负向 mutation 通过。

### 内容质量门禁

- 使用同一 Evidence Pack 做 candidate-vs-baseline paired assessment；
- 继续执行 FIN 0.1.3 八维研究内容评分，不因受保护叙事而降级；
- 特别检查 evidence-to-claim bridge、机制、counterevidence、跨证据综合、WWC 可执行性、内容密度和可读性；
- 必须证明相对 raw candidate 没有实质分析质量退化，并由 qualified human 判断成品不是模板拼装。

### 成熟度口径

五权、`NumericFactView`、correction objective/receipt 与 deterministic guard 已在 S2-06B/C 达到 `runtime_injected + deterministic_fixture_proven + node_level_consumed`；S2-06D 只证明当前 DeepSeek 能形式遵循 envelope/numeric ref，却未通过 evidence-role/closure。新增 capability profile/adaptive autonomy 仍只到 `contract_translated`。完整能力仍须依次达到 `paid_artifact_proven -> dogfood_accepted`，不得用局部成熟度替代产品验收。

## 8. Owner 映射

| 合同部分 | Owner |
| --- | --- |
| `NumericFactView`、换算、舍入、公式与 material span 检查 | TECH_04 |
| 模型判断、counter-thesis、WWC 与领域语义 | TECH_05 |
| CorrectionObjective 的 durable attempt、exact-once 与 capture | TECH_06 |
| agent/prompt/schema/handoff 的单源编译 | TECH_08 |
| ProtectedNarrativeDraft、render、citation、artifact verification | TECH_09 |
| closure、paired quality、anti-template 与 release gate | TECH_10 |

本文不改变这些 owner，只规定它们必须共享同一合同版本和对象引用。

## 9. 三层 Harness 结构与约束生命周期

### 9.1 稳定金融控制内核

以下能力组成 provider-neutral kernel，不接受“模型更强所以删除”的理由：source capture、financial truth、identity/time/unit/currency、lineage、permission、budget、exact-once、durable terminal、promotion、human attestation、version/supersession 和 audit。强模型可以减少失败和人工介入，但不能同时成为事实、权限和晋升的唯一裁判。

### 9.2 Model Capability Adapter

Provider/model/version 的差异进入 `ModelCapabilityProfile`，不得成为散落在共享 Runtime 中的 `if deepseek` 或逐字段补丁。最小字段为：

- `provider / model / model_version / evaluated_at`；
- `contract_family` 与冻结 prompt/schema 版本；
- strict JSON/schema、identity、numeric ref、citation、evidence-role、threshold、closure、tool-use、context 和 narrative 的独立状态；
- 每个 family 的 fixture、natural canary、样本数、pass rate、首次可信失败和适用案例；
- latency/cost、上下文和输出容量；
- `maximum_autonomy_tier`、禁止动作、降级触发器和复测条件。

### 9.3 Adaptive Autonomy Policy

统一自主权等级如下：

| Tier | 模型权限 | 本地责任 |
| --- | --- | --- |
| `A0` | 不参与或仅生成非权威建议 | 全确定性路径/人工 |
| `A1` | closed-set alias/enum/evidence-role 选择 | 验证、closure、render、promotion |
| `A2` | typed judgment atom、机制、反方和 WWC | 事实/角色候选/结构/closure |
| `A3` | 基于已接受 atom 的 protected narrative | material span render、citation、final gate |
| `A4` | whole-node research authoring | 全量 post-node truth/quality verification |
| `A5` | dynamic plan/tool loop | ToolGateway、budget、Evidence promotion、durable control |

权限按 contract family 授予，不设一个全局“模型强/弱”标签。某模型可在 narrative 为 `A3`，在 correction closure 仍为 `A1`。升级必须由冻结 eval 证明，失败立即回落到上一稳定 tier；降级不改变业务对象或核心 Runtime。

### 9.4 约束退役

每条模型相关控制必须声明 `permanent_financial_invariant`、`adaptive_gate` 或 `provider_workaround`。只有后两类可以退役。退役需要：新模型/版本的独立 capability proof、三案非回归、paired 内容质量不下降、shadow 观察期无 material escape，以及可恢复 rollback。删除的是补偿性限制，不是 raw capture、truth、lineage、permission 或 promotion gate。

## 10. DeepSeek 当前能力处置（基于 S2-06D）

当前 DeepSeek v4 Pro 的证据不是“完全不遵循”：它通过 JSON/envelope、case identity 和 protected numeric alias；失败集中在 evidence-role semantics、correction closure 和 analyst-threshold discipline。因此禁止继续以整节点自由修正＋模型自报 `closed` 作为主协议，也禁止再按单字段扩 Prompt。

当前 profile 应冻结为：

- strict JSON/envelope：`natural_pass_observed`；
- case identity：`natural_pass_observed`；
- protected numeric ref：`natural_pass_observed`；
- evidence-role classification：`natural_fail_support_misclassified_as_counterevidence`；
- correction closure self-attestation：`revoked`；
- analyst threshold discipline：`natural_fail_observed`；
- corrected whole-node authoring：`not_authorized`；
- formal DELL full graph：`not_authorized`。

这只是当前模型版本和合同 family 的能力记录，不是 DeepSeek 永久结论，也不自动适用于 Flash、后续 Pro 或其他 Provider。

## 11. DeepSeek 下一步适配：原子判断与叙事解耦

下一轮 S3 不再“修 DeepSeek 的完整输出”，而按以下逻辑协议执行：

1. **Evidence-role candidate compiler**：Harness 根据来源类型、claim direction、authority boundary 和目标问题编译 `supports / contradicts / qualifies / neutral / insufficient` 候选及理由边界；它不替模型决定 thesis。
2. **Judgment Atom pass**：DeepSeek 只选择证据角色、claim stance、mechanism、gap、counter-thesis 和 WWC atom；禁止自报 correction `closed`，禁止在 atom 中自由写 material number。
3. **Deterministic closure**：Harness 根据已验证 atom、Evidence/Gap 和 closure rule 计算 `closed / typed_unresolved / rejected`；模型没有 self-attestation authority。
4. **Narrative pass**：只有 atom 通过后，DeepSeek 才基于 accepted atoms 和 `NumericFactView` 生成 protected narrative。叙事可以丰富，但不得改变 atom、Evidence role 或 material facts。
5. **Targeted repair**：失败只重算对应 atom 或段落，不重写整个 Specialist/Lead/Writer 节点；原始结果、diff 和 receipt 全部保留。
6. **Paired quality gate**：与原始候选/Gold 对比机制深度、反方、综合、密度和可读性。可靠性变好但质量下降时不晋升。

逻辑上是两阶段，不强制永远两次 Provider 调用：DeepSeek 当前先采用 atom→narrative 分调用；未来模型若在组合 canary 中稳定通过，可合并为一次响应的两个受隔离区块。

## 12. 避免反复修复的评测与停止规则

1. Prompt/Schema/Validator 只按 `contract_family` 版本化，不为单个失败字段产生共享 Runtime 分支。
2. 每个变化 family 先做 deterministic fixture，再做至多一次自然节点 canary；同一 family 的新失败先进入 quarantined collect-all diagnostic，不逐项 paid rerun。
3. 一个评测周期内每个 family 最多一次结构修订；若仍失败，降低 autonomy tier 或更换模型候选，不继续扩大 Prompt。
4. 新模型先跑 capability matrix，再决定哪些 family 可以提升；不得直接复制 DeepSeek workaround，也不得先跑 full-chain 才发现已知能力缺口。
5. Experiment B 只在 identity、numeric ref、evidence role、closure、threshold 与 narrative 六个前置 family 达到各自门槛后启动。
6. 正式通过同时要求 reliability floor 与 content-quality floor；任一不足都不能用另一项补偿。

## 13. PresentationAlias、NumericProgramTrace 与 bounded successor

### 13.1 数字权威不是“禁止模型写数字”

模型仍可读、比较、解释并引用精确数字。Runtime 为每个 source NumericFact 编译三类可选表面：

- `NUM:*`：来源原值及 identity／period／unit／source locator；
- `PRES:*`：只允许 `multiply/divide/quantize/format` 的等价展示，保存 operand、rounding mode、precision 和 rendered surface；
- `FORM:*`：预注册公式，保存 ordered inputs、同实体/期间/口径门禁、运算与结果表面。

最终 point 中出现 material number 时，必须同时给出 Evidence alias 和覆盖该文本表面的 `NUM/PRES/FORM` ref。Verifier 按 ref 的允许表面匹配，不用模糊字符串或“数值看起来合理”放行。未知值、错期间、跨单位公式、未授权舍入和自由 arithmetic 仍为 L1。普通定性文字不受本地模板控制。

### 13.2 跨 Attempt 复用的最小安全合同

Provider transport failure 后，bounded successor 只能复用已成功且内容、capture、request、terminal lineage 均 digest-bound 的节点输出。旧失败 capture 只作审计证据，不能进入 prior outputs。successor admission 必须绑定 predecessor Run/Attempt/terminal/import bundle、新 model-visible digest、剩余 node order、代码 SHA 和累计容量；新 runner 从逻辑失败节点继续，但实际 provider call index 从 1 重新计数，并同时保留 logical node index。这样用户能区分“本次新增 8 次调用”和“整个案例累计 14 次 provider attempts／13 个逻辑节点”。

successor 不修改旧 terminal，不消费旧 admission，不自动重试，不拥有业务晋升权。任何新 failure 都形成新的 capture-first terminal，并立即停止。

### 13.3 paired 公平性

只要 numeric authority、Prompt、schema 或其他模型可见输入发生变化，旧 baseline 就不能与新 Agent candidate 构成 strict same-input pair。可以继续完成 bounded successor 来评估恢复链和内容，但 paired assessment 必须标记 `eligible=false`；后续若独立审计表明 candidate 值得比较，才单独签发一次相同增强输入的 direct baseline。Evidence Pack 相同不等于 model-visible input 相同。

### 13.4 2026-08-10 exact-live 对合同的纠正

DELL successor 证明，把 `NUM` 和语义重复的 `PRES` 同时交给模型选择，会让可靠性依赖模型是否记得第二个展示 ID；当前 DeepSeek 能稳定使用 source `NUM` 和 4 个 `FORM`，却没有选择任何 `PRES`，导致合法中文尺度换算被重复判错。后续稳定合同改为：模型引用事实/公式 authority（`NUM/FORM`）并写分析意图；Harness 根据该 authority 的封闭 presentation program 校验或渲染等价表面。模型仍能看见、分析和引用数字，本地层只控制展示，不替模型生成 thesis。完整 source numeric inventory 与 token boundary（例如不得从 `FY27` 抽取尾数 `7`）是该门禁的必要前置。

同一次 live 还证明 Verifier 不应重抄整份长报告。Verifier 输入必须是 compact `claim_id + evidence/numeric/gap refs + bounded text span`，输出只返回 claim-ID verdict、finding code 和必要的短 reason；原 claim 由 Harness 通过 ID 连接。任何 `finish_reason=length`、截断 JSON 或缺失 required claim verdict 都是 `verification_incomplete` 的 hard stop，而不是普通可后传的 parse-quality finding。该纠正只改变审计表面和终态分类，不降低事实、引用或内容质量门槛。

### 13.5 Evidence Pack 改变后的定向补源与完整链重编译

Source supplement 不得直接改 Writer 文本。它只允许向不可变 base Pack 追加 capture-backed `SourceMaterial` 与 `EvidenceItem`，并按 Evidence target 的实际存在条件更新 `Gap`：完整关闭、收窄为更具体的 attribution／allocation gap，或原样保留。每个新增对象必须携带 `research_subject`、`evidence_owner`、`evidence_role`、`relationship_direction`、publication/period、source capture 和 citation boundary。

技术路径固定为：

1. exact local object selection 优先，选择规则与 corpus SHA 绑定；
2. 已知官方 URL 使用 allowlisted HTTPS、capture-first、parse-after-capture，一次失败即 typed gap；
3. issuer direct evidence、counterparty bounded context 与 independent market PIT 分开计数和授权；
4. 原始正文只在受限 object store，公开 result 只保存 ref、digest、状态与计数；
5. `Evidence Pack digest` 改变后，所有 Specialist、Lead、Writer 和 Verifier 输入必须从头编译。旧节点输出只能作为历史 baseline，不能在新 Pack 上复用；
6. 新数字先进入 `NumericFactView／NumericProgramTrace`，市场价格与 EPS 等 derived multiple 由本地公式计算；模型可解释倍数，但不能自由改变 operand 或把单点倍数写成目标价。

同结构报告比较的因变量是研究判断质量，而不是网页数或 token 数。至少比较 evidence utilization、机制桥、反方、WWC 可执行性、估值边界、重复率和决策密度；新增材料若没有转化为更好的判断，应判为 `source_increment_not_utilized`，不能因 Pack 更大自动晋升。

### 13.6 多命中窗口、safe transport envelope 与 PIT 反答案泄漏合同

`SourceMaterial` 摘录不得对每个 required regex 只执行一次 `search()`。实现必须对每个 pattern 收集全部 occurrence，按起止位置排序，用确定性最小覆盖窗口选择同时包含全部 pattern family 的候选；tie-break 固定为 `(span, start, end)`。窗口先受 `max_anchor_span<=4000` 约束，再扩展 bounded before/after 和句子边界，最终 excerpt 仍受 4,000 字符硬上限。缺 pattern 与 pattern 存在但无法形成连贯窗口使用不同 typed code。DELL TSMC immutable capture 的旧 first-hit span=`18,170`，新 coherent span=`233`、最终 excerpt=`912`，证明修复无需增加容量。

official-source capture v1.1 为失败增加白名单字段：

- `failure_phase`：`dns_resolution／tls_handshake／connect／connect_or_read／response_transport／transport` 等有限枚举；
- `safe_cause_class`：`dns_resolution_failure／tls_handshake_failure／connection_refused／timeout／connection_terminated／unknown_transport_failure`；
- 原 `failure_code`、request/response ref 与 digest 继续保留；
- raw exception message、解析 IP、credential、Authorization、Cookie 永不进入 capture。

旧 v1.0 capture 保持不可变，不能反向补写原因；目标 DELL source successor 已显式采用 v1.1。其他 official-source consumer 迁移前，RC-P36-168 只可记为目标路径已修复、全局仍需迁移，不能宣称所有历史 transport 已可归因。

PIT parser 的 acceptance contract 不再比较预置 `close_token`。合同输入只允许 `ticker／provider_date_value／currency／source lineage`；parser 从 capture 中选中精确日期行并校验 close 是可解析数值，随后才生成 NumericFact。测试必须使用与历史预置值不同的 capture close，证明运行时没有标准答案泄漏。路线资格状态机固定为 `discovered locator -> executable candidate + parser proof -> fresh authority -> captured/adjudicated or typed terminal -> Pack promotion decision`，严禁把 locator discovery、authority issuance 与 live success混为一谈。

### 13.7 Provider-neutral 行情适配器、双门与 shadow 合同

市场数据接入不得把 Alpha Vantage、AKShare 或任何未来 Provider 的响应形状扩散到 Evidence Pack 和 Writer。稳定内核只接受 `MarketPointRequest(case, ticker, exchange, exact_date, currency, price_basis)`，Provider profile 负责 transport 与响应解析；成功后统一生成 `MarketPointInTimeNumericFact`。当前 Alpha Vantage profile 固定使用 `TIME_SERIES_DAILY + outputsize=compact + datatype=json`，读取精确日期的 `4. close`，并明确其语义为 raw as-traded close，而不是 adjusted close、实时行情或估值结论。

capture-first 顺序固定为：

1. 保存不含 secret 的 request shape；
2. transport 在内存中注入环境变量凭据；
3. 保存受限 response capture 后再 parse；
4. 校验 Provider symbol、精确日期、正数 Decimal、币种、单位、价格口径与 source coordinate；
5. 生成 digest-bound NumericFact，再编译为 Evidence Pack 的 `object_type=metric` 与 `structured_metric`；
6. 任一 identity/date/field/rate-limit/transport/secret-echo 异常形成 typed failure，不用预置答案补齐。

request、safe endpoint、公开 route result 和 telemetry 不得出现 `apikey` 值。由于 Alpha Vantage 以 query parameter 传 key，真实 URL 只能存在于 transport 调用栈；capture URL 必须删除该参数。若 response body 包含当前 credential bytes，只保存 body digest／长度与 `market_data_response_contains_credential`，不保存 body。

双门在 Runtime 中独立计算：

- `core_research_ready = predecessor_valid && Dell issuer fragments complete && TSMC replay complete`；
- `supplier_context_ready = Micron fragments complete`；
- `valuation_input_ready = Alpha exact-date NumericFact accepted`；
- `successor_pack_ready_for_model_input = core_research_ready`，不再与单个行情 Provider 成败做逻辑与；
- 兼容字段 `valuation_ready` 只能是 `valuation_input_ready` 的展示别名，禁止下游把它解释为 fair value／target price ready。

AKShare profile 是 non-promoting shadow：它使用未复权 exact-date row 与 primary 做诊断比较，任何输出都标记 `diagnostic_shadow_only_never_authoritative`，不进入 Pack 的 `numeric_facts`。该依赖可被替换或移除而不改变核心合同；未来更强或商业行情 Provider 只需增加 profile，不得改 Writer、Evidence Gate 或报告 schema。

当前零调用定向测试覆盖 primary success、wrong symbol、missing date、negative close、rate limit、secret echo、shadow non-promotion，以及 `core=true/valuation=false`、`core=false/valuation=true`、两门同时通过和单点收盘价不得关闭历史相对估值／情景敏感度 Gap。fresh Git archive proof 与真实 live 尚未发生，因此这里记录的是实现合同和 fixture evidence，不是生产行情能力。

### 13.8 Exact-official URL 的 managed-reader transport profile

当 exact official URL 已通过公司／文档身份资格审查，但 direct-origin transport 在 HTTP response 前稳定 timeout 时，Runtime 可以使用独立 managed-reader profile；这不是将来源权威委托给 Reader。稳定合同为：

- 输入仅为 allowlisted `https` official URL、origin host、byte ceiling 与 timeout；Reader endpoint 不得由模型自由选择；
- Reader endpoint 固定在 provider profile，本轮为 `https://r.jina.ai/<official-url>`，并请求 JSON；
- capture-first 保存完整 Reader JSON bytes、digest、长度、safe headers、redirect chain 与 transport metadata，然后才解析 `data.content`；
- `data.url` 必须与请求的 official URL 在去除末尾 `/` 后严格一致，Reader HTTP／payload code 必须成功，正文必须超过最小长度；
- `SourceResponse.final_url` 仍为 official URL，因此既有 official allowlist 与 Evidence compiler 不会把 Reader 域误当成来源域；
- lineage 显式写入 `retrieval_intermediary=jina_reader`、`origin_direct_response_bytes_preserved=false`、`intermediary_raw_response_preserved=true`；
- Reader timeout／connection／invalid payload 使用 provider-neutral typed failure，任何失败先保存 request／terminal capture，0 retry。

Reader JSON parser 只把被保存的 `data.content` 转成待匹配文本；目标片段仍由本地 required-pattern、最小覆盖窗口、身份／期间／角色和 Gap disposition 确定性编译。中介不能贡献 NumericFact、估值、推荐或未在官方原文中出现的判断。该 profile 通过 fake、timeout、anchor missing、cross-origin、URL mismatch 和 authority-escalation mutation 后，仍须 clean archive proof 与 fresh exact-once authority；fixture 或匿名诊断成功不构成 Evidence promotion。

### 13.9 长文档语义 anchor compiler 与贪婪 regex 防线

`_smallest_regex_window` 的输入不得是任意手写 regex。每个 pattern 先编译为短语义原子并经过静态检查：跨行模式下拒绝无界贪婪 `.*`、`.+` 和等价结构；限制单 occurrence 最大长度；对需要表达顺序的词组优先拆成多个 anchor，由 window selector 负责组合，而不是让单一 regex 跨越任意正文。

failure 必须区分：`anchor_missing`、`pattern_occurrence_unbounded`、`multi_anchor_window_too_wide` 与 `final_excerpt_too_large`。Dell／Micron live 已证明这四者业务含义不同：原文 anchor 全部存在且真实距离很短，但 policy pattern 自身贪婪跨越长文，属于本地 compiler defect。修复只能零网络回放 immutable Reader captures，并加入重复主题词、文档尾部同名词和顺序变换 mutation；不得更改历史 result、扩大 span 或自动发起新的 source call。

当前 successor 将 v2 输入面收窄为 `literal_phrase_groups_v1`：每组包含一个语义原子及少量等价 literal，compiler 先做合同数量／长度检查，再在 whitespace-normalized、case-folded 正文中枚举全部 occurrence，并把位置映射回原始文本；滑动窗口选择覆盖每个 group 的最小原文 span。v2 不接受 `required_patterns`，因此无界 regex 无法重新进入该链。selector receipt 保存每组命中的 literal、原文 start/end、occurrence count、最小窗口和最终 excerpt 长度，但不把整份原始正文写入公开 result。两个 clean Git archive／fresh process 已独立重放真实 captures，并得到 byte-equivalent corrected Pack digest=`5ba1091d...5e9984`；Dell 三片段窗口为 `310／219／90` 字符，Micron 两片段为 `139／219` 字符，五条均在原上限内，network/model/retry=`0/0/0`。

### 13.10 Evidence-driven NumericFact co-compilation 与 layered verification

changed-input live 暴露了静态 NumericFact inventory 的扩展上限。新 Pack 中 SMCI `97.8%` 与 Dell `over 5,000 customers` 都存在于 cited Evidence，但未进入 NumericFactView；Dell `$16.1B` 又是同一 `$16.132B` 精确事实的官方 rounded surface。模型能正确理解并引用这些内容，但本地交付门无法绑定。该失败不是取消数字门的理由，而是要求 Numeric authority 与 Evidence selection 使用同一编译源。

稳定数据流调整为：

1. `SelectedEvidence[]` 先经 source-type parser 产生带 source coordinate 的 `NumericCandidate[]`，保留原字符串、Decimal 候选、单位、币种、期间、实体、上下文窗口和 materiality hint；
2. deterministic adjudicator 将候选分为 `authorized_fact／authorized_formula_operand／descriptive_nonmaterial／forbidden_or_ambiguous`，并保存 decision code；无法确定实体、期间或单位的候选不能进入 NumericFactView；
3. stable target resolver 以 `target_id + source_record_id + period/unit` 去重；同一 target 的精确值、来源 rounded surface、单位换算与格式展示由一个 presentation program 编译，而不是生成互相独立的手工 alias；
4. Provider view 只暴露当前节点可用的 `NUM/FORM` 和明确的 `DO_NOT_OUTPUT` 候选。若出于研究理解需要保留原文，禁止输出状态必须与对应 text span 同位置可见，不能藏在全局 prompt 尾部；
5. final local guard 先按 claim 的 explicit refs 匹配 material numeric surface，再核对 Evidence lineage；source text 中存在但无 authority 仍 fail closed，并将 finding 分成 `inventory_omission` 与 `model_unbound_output`，允许同时成立；
6. compact model Verifier 与 deterministic guard 是串联关系，不是互相覆盖。Verifier 返回 pass 只说明它没有发现语义支持问题；数字、身份、期间、单位和 lineage 必须由本地 gate 独立通过。

本轮 direct baseline 有 8 条 L1，Red Team／Final Writer 后只剩 2 条，说明模型链具有实质控制增益；compact Verifier 30/30 pass 却漏掉三枚未绑定 surface，说明 Verifier 不具备单独晋升权。后续测试必须覆盖新增 Evidence 自动出现未知数字、同 target 多精度表面、百分比／客户数／日期 token、cross-case、错期间、source 数字可见但不可输出，以及 Verifier false-pass 后本地门仍阻断。完成零调用 co-compilation proof 前不得再发 DELL paid rerun。

#### 13.10.1 冻结后的候选合同

零调用处置拒绝静态 whitelist 扩表和 raw-text regex-all promotion。每次 selected Evidence 变更必须同事务生成 `MaterialNumericCandidateInventory`；其中 `MaterialNumericCandidate` 最小字段固定为：`candidate_id／case_key／evidence_target_id／evidence_alias／source_record_id／source_coordinate_or_span／source_surface／value_kind／parsed_value_or_bounds／canonical_unit／currency／scale／entity_or_evidence_owner／period_or_as_of／slot_ids／facet_ids／relationship_directions／semantic_metric_key／claim_and_output_boundary／adjudication_status／decision_code`。

`value_kind` 至少覆盖金额、百分比、计数、比率／倍数、数值区间、时间区间／边界和定性数字带。`adjudication_status` 固定为 `authorized_fact／authorized_formula_operand／descriptive_nonmaterial／context_only_do_not_output／forbidden_or_ambiguous`。stable fact identity 由 `case + entity + semantic metric + period/as-of + canonical unit + authoritative source scope` 决定；Evidence target、source record 和精确 span／table path 是 lineage，不足以单独定义经济事实。

发现层按来源类型拆分：structured metric 直接投影；表格候选必须继承 parent currency／unit／period 和 row／column path；叙事候选只在 selected Evidence 的 bounded span 内发现，并携带 Slot／Facet 语义；count、percentage、range、H1／beyond-year、qualitative band 和 PIT market input 使用独立 parser。Regex 可以提出候选，不能作晋升裁决。

#### 13.10.2 四种视图与晋升顺序

1. `private_audit_view` 保存完整 raw request／response／assistant output，restricted access、不可直接晋升。
2. `research_view` 给 Lead／Specialist bounded Evidence、Slot／Facet、授权候选和与原 span 同位置的 non-output 标记；不得继续发送未注解的完整数字正文。
3. `writer_view` 只给可写 `NUM/FORM`、bounded nonnumeric narrative 和稳定遮蔽标签；context-only 数字不得靠全局 prompt 尾注约束。
4. `verifier_view` 只给 compact claim、ref、Evidence support 和边界。其 semantic pass 后仍必须串行执行 local identity／period／unit／currency／ref／lineage gate。

Harness 的确定性 renderer 只写入已授权事实表面，不生成机制、thesis 或反方。S3 可以在以后新增“按实体＋指标＋期间＋Slot 请求更多数字目标”的模型动作，但请求只能产生待裁决 candidate，不能直接写值或取得输出权威。

#### 13.10.3 泛化与实现边界

DELL／MU／NVDA 用于叙事、表格、供应商／客户 read-through 和 PIT 输入；ORCL／ASML／ANET 用于 `source_materials=[]` 的 structured metric、USD／EUR、货币／非货币单位和期间隔离。mutation 必须覆盖同数不同义、精确＋官方舍入、错实体／期间／币种、table child 缺 parent、slot 外数字、日期／规则号／产品型号、count qualifier、range／H1／beyond-year、cross-case、排序稳定、Writer 越过 DO_NOT_OUTPUT、公式 lineage、PIT 不越权估值，以及 Verifier false-pass。

处置工件只达到 `decision_complete_implementation_pending`。下一项 `FIN-0.1.3-S2-SELECTED-EVIDENCE-NUMERIC-CANDIDATE-COCOMPILATION-MINIMUM-ZERO-CALL-IMPLEMENTATION` 依次实现 pure schema/compiler、source-aware adapters、deterministic adjudicator、node views／renderer／guard、六案 fake／capture replay／mutation 和双 clean proof；不得在此之前自动重跑 DELL。

#### 13.10.4 实现后的编译不变量与已知迁移边界（2026-08-11）

当前 pure compiler 已实现为单事务：`SelectedEvidence -> CandidateInventory -> StableFactPresentationProgram -> BoundedNodeViews -> LocalDeliveryGuard`，并由共同 transaction digest 绑定。structured metric 直接继承 table path／parent unit／period；显式表格只选择命中 row rule 的单元；叙事 parser 发现金额、百分比、count、range、temporal 和 qualitative band 后，必须通过 Slot／Facet、金融微句、实体、期间和 output boundary 裁决。日期、Form／Rule、RTX／HBM／GB／3D 等产品或技术 token 只可进入 forbidden/context 状态。

叙事关联使用两层 span：默认用非数字逗号、句号、分号和 bullet 切分 micro-clause，防止 `revenue 43.8B, cash flow 4.1B` 串义；只有 policy 显式 `allow_cross_comma_context` 的高特异规则可回看 major span。相对期间 parser 在 fact identity 前处理显式季度、九个月、prior quarter 和 same period last year。`increased 3%` 与 `increased to 85%` 分开，前者不能成为 margin level。

Node view 使用同一 fact/formula parity digest，并各自保存字符容量 receipt；完整 raw source 不进入 successor model input，只保留 private audit digest set。Delivery guard 先验证 used refs，再只接受这些 refs 的 exact rendered presentation；context-only literal、错单位表面和 PIT→target-price 越权即使 semantic Verifier pass 也 hard fail。

六案 working-tree replay 与 mutation 已通过，且测试真实抓出并修正上述串义、期间折叠和 guard 误杀；这比只断言 schema 完整更强，但仍不是 clean-source proof。当前叙事 exact coordinate 有一部分由通用迁移 adapter 从已选正文恢复；未来 S1 `FinancialSourceObject` 应在 selection 时直接保存 numeric coordinates，让 S2 只做权威裁决和展示编译。该长期迁移不应在本 S2 修复中重开 S1。
