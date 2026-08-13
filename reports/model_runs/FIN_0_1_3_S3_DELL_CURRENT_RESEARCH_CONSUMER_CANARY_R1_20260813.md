# FIN 0.1.3 S3 DELL 当前研究消费者 Canary R1

日期：2026-08-13
状态：`terminal_failed_no_retry / provider_completed / contract_and_content_failures_preserved`

## 目的与权限

本次只测试 DeepSeek Pro 能否消费当前固定 DELL reviewed Evidence Pack、S2 NumericFact 和 residual gaps，完成五个研究单元的引用选择、判断、机制、反方和 what-would-change。权限为 1 次模型调用、1 次 transport attempt、0 retry、0 fallback、0 外源检索、0 Planner 调用和 0 产品发布。

## 终态

- Provider HTTP 成功，`finish_reason=stop`；
- 返回内容是 exact JSON，包含 5/5 必需 cell；
- prompt/completion/total tokens=`14,141 / 2,643 / 16,784`；
- 输出只包含 `cells`，没有返回 `schema_version` 和 `research_input_digest`，因此首个硬失败为 `research_consumer_output_envelope_invalid`；
- 没有 retry、fallback、字段修补、手工追认或 Workbench 发布；
- terminal result digest=`c3b172d4...b4711`。

## 零调用完整诊断

不能因为首个失败是 envelope 就认为“本地包一层即可通过”。对保存输出只做诊断性包装后，后续问题一次性暴露如下：

1. **模型看不到实际枚举值**：model-visible contract 只写“one allowed status / confidence / direction”，却没有列出合法枚举。模型因此自创 `supported_with_caveats`、`issuer_disclosure_plus_ecosystem_readthrough` 和 `weaken`。这是项目合同缺陷，不应全部归咎模型。
2. **本地已知字段被要求回写**：schema 和 input digest 本来由 Harness 确定，让模型逐字回写只增加无业务价值的失败面。后续应由本地 envelope wrapper 注入，同时对 cells 绑定当前 input digest。
3. **cell 范围表达不够自然**：模型看到一份全局 Evidence 表，再另外查每个 cell 的 allowed ref。它把毛利 mix 证据用于经营表现、把客户集中/取消风险用于现金反方；这些业务用途并非荒谬，但当前 slot 投影未把它们授权给相应 cell。后续应让每个 cell 直接携带自己的可见 cards，或补齐明确的 supplemental role，而不是让模型在全局 alias 表中自行对照。
4. **同一证据可能同时支持事实并限制推论**：需求、价值获取和反方单元把若干 Evidence 同时列为 supporting 与 counter。当前合同一律禁止 overlap，但一段披露完全可能既证明订单存在，又限制对订单持续性的外推。后续需要 `support / limit / context` 的 typed evidence-use，而不是把复合证据强塞进二元数组。
5. **自由数量级表述仍出现**：价值获取单元在 prose 中写了“中个位数”，没有通过 Numeric/Evidence ref 渲染，当前硬门正确阻止其直接成为交付事实。

## 内容质量审计

即使忽略上述结构错误，本轮也不能通过 L1／研究质量：

- 需求单元把“订单规模、积压和客户广度”写成需求“具有持续性”，而 Pack 明确保留 pull-forward、取消率和消化节奏 gap；最多只能判断当期需求真实、持续性待证。
- 经营表现单元声称 AI 服务器“推动 EPS 和分部利润大幅提升”。现有数字只证明集团/分部结果与 AI server 收入同期披露，不能建立该因果归属。
- 价值获取单元写入“低于传统业务”和“规模效应带来经营杠杆”，现有 Evidence 没有完整产品利润桥支持这两个结论。
- 现金单元把库存、应收、应付变化归因于 AI 服务器增长，而现有 gap 明确说明总表不能做该归因。
- 反方单元称“供应瓶颈正在逐步缓解”，但当前 TSM/MU Evidence 只证明扩产、爬坡或约束存在，没有 Dell-specific 分配、时点、利用率或良率证据。

因此，本轮不是“格式差一点但报告内容已经合格”，而是合同表达与自然研究判断均未通过。

## Capture 与审计边界

- request capture：`.codex_runtime/model_runs/fin_0_1_3_s3/dell_current_research_consumer/FIN013-S3-DELL-CURRENT-CONSUMER-CANARY-R1/ATTEMPT-01/model_visible_request.json`
- response capture：同目录 `provider_response.json`
- public terminal：`configs/research/evals/fin_ia_0_1_3_s3_dell_current_research_consumer_canary_result_v1_0.json`
- credential、Authorization 和 provider private reasoning 未保存；完整 assistant 输出只留在受限 capture。

## 处置与下一项

R1 永久保持 failed，不签发自动 R2。下一项限定为零调用结构处置：

1. Harness 本地注入 envelope，只让模型返回判断 payload；
2. model-visible schema 明列所有枚举和每个 cell 的 cards；
3. Evidence 使用改成 `support / limit / context` typed role；
4. 增加 `directly_supported / bounded_inference / not_inferable` 推论权限，产品归因与因果句必须绑定直接支持；
5. 用本轮 immutable output、fake 和 mutation 做零调用回放，证明合同修复不会把当前越界内容追认为事实；
6. 只有结构包与内容门均通过后，才另行判断是否值得一次新的自然 canary。不得逐字段补丁或重启旧九调用链。
