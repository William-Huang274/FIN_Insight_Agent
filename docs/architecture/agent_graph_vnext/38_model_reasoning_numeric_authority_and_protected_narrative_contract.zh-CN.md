# 模型研究判断、数值权威与受保护叙事合同

日期：2026-08-07

状态：跨 TECH 实施合同草案。本文补齐 PRD 中“模型如何使用精确事实、Harness 如何守住金融真值、同时不把研报退化为模板拼装”的缺口。本文不是新的业务真相 owner，也不表示 Runtime 已实现或 DeepSeek 已通过产品验收。

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

本文当前只到 `contract_draft`。后续必须依次证明 `runtime_injected -> deterministic_fixture_proven -> node_level_consumed -> paid_artifact_proven -> dogfood_accepted`，不得用文档完成替代代码、真实模型结果或产品验收。

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
