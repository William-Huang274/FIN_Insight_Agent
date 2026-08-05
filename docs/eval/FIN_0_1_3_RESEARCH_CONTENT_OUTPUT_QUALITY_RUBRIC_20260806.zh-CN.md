# FIN 0.1.3 研究内容输出质量硬门禁 Rubric

日期：2026-08-06
状态：`accepted_product_quality_gate / runtime_compilation_pending / release_blocking`

## 1. 目的

本 Rubric 确保 FIN 0.1.3 不再把“合同正确、Artifact 齐全、页面可打开”误记为“研究内容质量通过”。它独立于金融事实、证据权威、lineage 和 UI 工程门禁，专门回答：最终研究底稿和报告是否像一份对 analyst/senior 有决策价值的公司研究成果。

以下情况即使 L1、L2、9 Artifacts、Verifier、renderer 和 Workbench 全部工程通过，也不得进入 S4 dogfood、R2/R3 产品接受或 S5 release：

- 核心 Claim 只是可替换 ticker 的通用句式；
- 报告只罗列 Evidence、Claim、gap 或 WWC 数量；
- 数字正确但没有解释其经营、盈利、现金流或估值含义；
- dependency/conflict 只复述 supported/cannot infer 状态；
- counter-thesis、gap 和 WWC 不可观察、不可证伪或没有下一证据路线；
- qualified reviewer 认为结果不具备继续研究、复核或决策价值。

## 2. 与 L1–L4 的关系

| 层 | 考核对象 | 是否可被其他层补偿 |
| --- | --- | --- |
| L1 Financial Truth | entity、period、duration、unit、scale、formula、identity | 不可补偿；任一 material error 直接失败 |
| L2 Evidence Authority | source、citation、authority、freshness、false promotion、gap | 不可补偿；证据不足必须 typed gap |
| L3 Research Content Quality | 公司专属判断、机制、数字解释、综合、反方、WWC、决策价值 | **FIN 0.1.3 起为硬门禁，不再是 nonblocking finding** |
| L4 Product Delivery | 最终页面/HTML/Markdown 的可读性、一致性、review 与使用价值 | 不可用的最终交付不能由 raw Artifact 分数补偿 |

评分只在 L1/L2 通过后进行。高 L3 分数不能覆盖错误事实或无权威证据；高工程完整性也不能覆盖低 L3。

## 3. 八维评分

每一维按 0–4 分评分，总分 32 分。

| 维度 | 0 分 | 1 分 | 2 分 | 3 分 | 4 分 |
| --- | --- | --- | --- | --- | --- |
| Q1 公司与问题专属性 | 缺失/错公司 | 可替换 ticker 的模板 | 提及本案但机制浅 | 明确回答本案问题与边界 | 形成不可简单迁移的公司专属 thesis |
| Q2 证据到结论的论证 | 无 evidence/gap | 引用堆砌或越权 | 有 evidence→Claim 绑定 | 解释证据为何支持/削弱判断 | 多来源权威、冲突与局限共同形成论证 |
| Q3 财务与 Numeric 解释 | 错误或缺失 | 只抄数字 | 正确描述数字 | 解释增长、利润、现金流或经营含义 | 连接驱动因素、桥接、敏感性和估值/price-in 边界 |
| Q4 因果机制与行业逻辑 | 无机制 | 泛化叙事 | 有 bounded mechanism | 机制、条件、传导链明确 | 能区分相关性、因果、时滞与替代解释 |
| Q5 跨 Cell 综合与冲突裁决 | 无综合 | 罗列各 Cell | 有 dependency/conflict 但浅 | resolve/defer/block 有理由与影响 | 形成一致 thesis，并保留不可解冲突的决策边界 |
| Q6 反方、风险与 gap 纪律 | 无反方/gap | 形式化风险清单 | 有具体反方或 gap | 说明影响、优先级、owner、stop | strongest counter-thesis 能实质改变结论或置信度 |
| Q7 WWC 与行动价值 | 无 WWC | 通用“持续关注” | 有指标或时间但不完整 | 指标、方向、时间/阈值、证据路线齐全 | 能直接驱动 follow-up、repair 或 thesis 状态转换 |
| Q8 写作与 senior 决策可用性 | 无法理解 | 机械拼接/重复 | 可读但需大量重写 | senior 可复核并继续工作 | 接近内部可交付研究备忘录，层次、重点和限制清晰 |

## 4. 通过条件

每个正式 release case 必须同时满足：

1. L1 与 L2 独立通过；
2. 八维总分 `>=24/32`；
3. Q1–Q7 任一维不得低于 2；
4. Q1 公司专属性、Q2 证据论证、Q3 Numeric 解释、Q8 决策可用性必须各 `>=3`；
5. 至少四个维度达到 3 分或以上；
6. 每个核心 Claim 均有本案对象/机制以及 evidence、numeric 或 typed gap；
7. 最终报告至少有一个 strongest counter-thesis、一个经过裁决的 cross-cell dependency/conflict，以及一个可执行 WWC；若案例确实不存在冲突，必须给出 evidence-backed `no_material_conflict_observed` 理由；
8. qualified reviewer 对“内容可用于继续研究/复核”明确接受，且该决定与 workflow/identity acceptance 分开记录。

DELL、MU、NVDA 必须逐案通过，不能用三案平均分掩盖单案失败。

## 5. Baseline 与 Agent 增益

FIN 0.1.3 同时要求绝对质量和相对增益：

- deterministic baseline 与 Agent 使用相同 evidence/input head，但保持不同 Run/Artifact；
- Agent 最终输出必须达到第 4 节绝对门槛；
- 相对 baseline 至少在三个内容维度出现 reviewer-confirmed material gain，且 L1/L2 不回退；
- “多了 6 Claim、9 WWC”不是增益证据，只有分数和具体业务内容改善才算；
- 若 deterministic local composition 已达到同等质量，允许减少模型表面，不为了证明 Agent 存在感保留低价值调用。

## 6. 评分对象与流程

评分对象必须是最终 verifier-bound 产品交付，而不是只看 raw Provider response：

1. Workpaper；
2. Lead dependency/conflict/gap adjudication；
3. final Report/HTML/Markdown；
4. exact Numeric 与 citation drawer；
5. What-Would-Change/repair projection；
6. reviewer 可见 limitation 与 trace。

流程：

```text
L1/L2 deterministic gate
 -> generic/coverage deterministic precheck
 -> identity-sealed reviewer packet
 -> frozen 8-dimension score and reasons
 -> baseline/Agent reveal and paired comparison
 -> qualified reviewer content acceptance or return
```

评分理由必须引用具体 Claim/section/evidence/numeric/WWC ID。只给总分、只给“看起来不错”或只使用模型自评均无效。

## 7. 自动化与人工边界

- deterministic checks 可以拒绝通用占位句、重复 gap、无本案实体、缺 evidence/gap、无 WWC 字段和未裁决 conflict。
- LLM-as-judge 只能作为 shadow/辅助评分，不能单独签发 product acceptance 或 release。
- 最终内容接受需要 qualified human reviewer；reviewer identity 与研究内容评分是两份独立记录。
- rubric 在正式 candidate 前冻结。看见 test output 后新增维度或调整阈值只能进入下一 evaluation cycle，不得回调同一结果。

## 8. Stage 消费要求

| Stage | 必须消费本 Rubric 的位置 |
| --- | --- |
| S0 | 将 Rubric 版本、阈值、case 和 evaluator protocol 写入 delta manifest；建立 score schema |
| S1 | 证明 evidence/numeric ceiling 足以支持 Q2/Q3；不足则 upstream-blocked |
| S2 | 编译公司专属 mechanism atom 与 node-level score packet；changed-node canary 必须按 Q1–Q7 评估 |
| S3 | Lead、Writer、Verifier 和 paired assessment 正式消费八维 Rubric；达到绝对质量门槛 |
| S4 | Workbench 展示内容评分、理由、return target 和 repair 后差异；真实 reviewer 完成内容验收 |
| S5 | RG3 单独验证三案研究内容质量，RG4 验证 reviewer 使用价值；任一失败则 release honest-block |

## 9. 当前状态

本 Rubric 已成为 FIN 0.1.3 产品与 release 约束，但尚未编译为 runtime schema、deterministic gate、score packet 或 Workbench surface。当前状态只能标记为 `documented_accepted / contract_translation_pending`，不得宣称已实现或已通过。
