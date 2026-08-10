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
