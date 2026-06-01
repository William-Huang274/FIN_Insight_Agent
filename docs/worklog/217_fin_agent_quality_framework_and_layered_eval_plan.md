# 217 - Fin Agent 投研质量评价体系与分层门控计划

日期：2026-06-01

分支：`codex/api-model-call-architecture`

状态：评价体系与执行门控已落文档和 artifact-only 审计脚本；S1 Research Lead、S2 Universe / Relationship EconomicLinkMap、S3 Evidence Operators 真实检索 gate 已通过。

敏感信息说明：本阶段不写入任何 API key、token、密码或私有凭据。后续真实模型运行只从 shell 环境变量读取。

## 1. 问题

用户指出当前不能每次都靠人工判断 full-chain memo 好坏，需要先参考投研专家的做法，为项目建立一个可长期迭代的投研报告 / 金融问题回答质量评价体系；随后基于该体系优化项目，并在 LangGraph 控制下按 agent / node 分层通过门控，而不是一开始直接跑 full chain。

## 2. 决策

新增独立于工作日志的评价体系文档，并配套一个执行层文档和机器可读 rubric：

- 长期质量框架：`docs/eval/fin_agent_investment_research_quality_framework_v0_1.md`
- 分层执行文档：`docs/eval/fin_agent_layered_quality_execution_plan_v0_1.md`
- 机器可读配置：`configs/fin_agent_quality_rubric_v0_1.json`
- Artifact-only 审计脚本：`scripts/audit_fin_agent_layer_quality.py`

评价体系采用 hard gates + 0-4 质量评分双层结构。Hard gates 负责 source boundary、权限、工具调用、unsupported claim 等不可妥协项；质量分负责 thesis、经济关系、风险平衡、输出可用性和成本效率。

## 3. 参考基线

框架参考投研实践与金融沟通的通用质量要求，而不是照搬当前项目已有实现：

- CFA Institute Research Challenge：分析、估值、报告写作和展示能力。
- FINRA Rule 2210：金融沟通应 fair and balanced，并提供 sound basis。
- SEC Investment Adviser Marketing 公开材料：潜在收益需要与重大风险和限制 fair and balanced 展示。

这些参考被转换为项目内维度：问题理解、证据边界、财务指标、经济关系、投资 thesis、风险反证、输出可用性、成本效率、权限审计。

## 4. 完成内容

已落地：

- 新增 v0.1 投研质量框架，定义 9 个质量维度、case 层级、agent 分层门控、质量总分和版本治理。
- 新增 v0.1 分层执行文档，按 S1-S10 冻结 Research Lead、Universe / Relationship、Evidence Operators、Coverage、Specialists、Aggregator、Memo Writer、Verifier、Renderer、Full chain / Multi-turn 的进入条件、通过门控和失败处理。
- 新增 JSON rubric，供脚本和后续 eval runner 使用。
- 新增 `scripts/audit_fin_agent_layer_quality.py`，从保存的 `activation_diagnostic.json` 或 `real_chain_eval_summary.json` 生成统一质量审计 JSON/Markdown；脚本不调用 LLM、检索、数据库或外部 API。
- 新增单测 `tests/test_fin_agent_layer_quality_audit.py` 覆盖 Research Lead pass/fail、full-chain cost-quality flags 和未知 schema fail-closed。

## 5. 下一步执行顺序

严格按以下顺序：

1. 运行脚本单测和现有 artifact 审计，确认新门控可用。
2. 从 S1 Research Lead 开始真实 DeepSeek 分层 gate。
3. S1 通过后保存 activation artifact，再进入 S2 Universe / Relationship。
4. 每一层失败时复用已通过上游 artifact，不直接 full-chain 重跑。
5. 全部 S1-S9 通过后，再跑 S10 full-chain 和 multi-turn。

## 6. 当前未运行项

- 尚未运行 full-chain。
- 尚未接入 LLM-as-judge；v0.1 只固化 deterministic gates 与 artifact audit，避免主观 judge 覆盖 source-boundary 硬失败。

## 7. 风险和回滚

- 新审计脚本是 artifact-only，不影响主链路 runtime。
- 如果 rubric 阈值过严，可以版本化到 `v0.2`，不要直接覆盖历史结果。
- 如果某阶段 gate 与真实业务质量冲突，先登记为 evaluator issue，再决定是否修改 agent prompt / schema / gate。

## 8. S1 Research Lead 真实门控结果

运行：

- Run ID: `20260601_fin_agent_s1_research_lead_quality_gate_deepseek_v0_1`
- Entry point: `scripts/eval_multi_agent_research_lead_activation.py`
- Fixture: `tests/fixtures/multi_agent_activation_cases_v0_1.jsonl`
- 模型：DeepSeek `deepseek-v4-pro`
- API key：仅通过进程环境变量读取，未写入文件。

结果：

| 指标 | 结果 |
| --- | ---: |
| Gate status | pass |
| Case count | 5 |
| Pass count | 5 |
| Mode correct | 5/5 |
| Validation pass | 5/5 |
| Required agent pass | 5/5 |
| Budget pass | 5/5 |
| Evidence requirement pass | 5/5 |
| Forbidden activation count | 0 |
| Total latency | 116,126 ms |
| Total tokens | 28,038 |

新增质量审计：

- Script: `scripts/audit_fin_agent_layer_quality.py`
- Source type: `research_lead_activation`
- Gate status: pass
- Weighted score: `2.688`
- Quality flags: none

解释：

- S1 的 weighted score 只是阶段诊断，不代表完整投研输出质量。分数低于 full-deliverable `3.0` 是因为 relationship、retrieval、specialist、memo、verifier、renderer 尚未运行。
- 该结果允许进入 S2 Universe / Relationship，但不允许跳到 full chain。

下一步：

- 复用 S1 activation artifact，进入 S2 Universe / Relationship 分层 gate。

## 9. S2 Universe / Relationship 真实门控结果

新增：

- `scripts/eval_multi_agent_universe_relationship_gate.py`：从 S1 activation artifact 中筛选需要 `universe_relationship` 的 case，执行 bounded relationship lookup，并只调用 Universe / Relationship LLM。
- `scripts/audit_fin_agent_layer_quality.py`：新增 `sec_agent_universe_relationship_diagnostic_v0.1` 识别和 S2 审计。

调试过程：

| Run | 结果 | 发现 | 修复 |
| --- | --- | --- | --- |
| `20260601_fin_agent_s2_universe_relationship_quality_gate_deepseek_v0_1` | fail | lookup 有 `24` 条 relationship rows，但 plan `relationships=0`。 | S2 runner 的 source inventory 只包含 S1 search scope，导致 route compaction 把 bounded related tickers 过滤掉。 |
| `20260601_fin_agent_s2_universe_relationship_quality_gate_deepseek_v0_2` | pass but superseded | plan 有 `8` 条关系，但 AI capex query 混入 energy pack。 | 移除 `capex` 作为 AI alias；跨 sector pack 只有在 AI + power/load + transmission 同时出现时放行。 |
| `20260601_fin_agent_s2_universe_relationship_quality_gate_deepseek_v0_3` | pass but superseded | 关系 plan 只保留 `technology_ai_infrastructure_depth`，但仍是 relationship list，不足以表达经济传导机制。 | 升级为 `EconomicLinkMap` gate。 |
| `20260601_fin_agent_s2_economic_link_map_quality_gate_deepseek_v0_1` | fail | 新增 economic map 后，首次 gate 暴露 map 字段/引用不足。 | 收紧 prompt、schema validator 和 compact input。 |
| `20260601_fin_agent_s2_economic_link_map_quality_gate_deepseek_v0_2` | pass | Universe 输出包含 bounded entities、economic links、mechanisms、investment implications。 | 接受为当前 S2 gate。 |

S2 economic-link-map v0.2 结果：

| 指标 | 结果 |
| --- | ---: |
| Gate status | pass |
| Case count | 1 |
| Pass count | 1 |
| Lookup relationship count | 24 |
| Plan relationship count | 4 |
| Economic entity count | 6 |
| Economic link count | 4 |
| Mechanism count | 2 |
| Investment implication count | 2 |
| Fallback count | 0 |
| Total latency | 72,279 ms |
| Total tokens | 11,465 |
| Quality audit gate | pass |
| Quality audit weighted score | 2.736 |
| Quality flags | none |

最终 S2 输出的 relationship refs 全部来自 `technology_ai_infrastructure_depth`，不再混入 energy pack。`economic_link_map` 明确把 NVDA/AMD 与 DELL/HPE/SMCI/ANET 的经济关系限制为 `economic_mechanism_hypothesis_only`，该层仍只支持 scope / hypothesis，不支持公司财务事实或确认商业供应链事实。

下一步：

- 复用 S1/S2 artifacts，进入 S3 Evidence Operators 分层 gate。

## 10. S3 Evidence Operators 真实检索门控结果

新增：

- `scripts/eval_multi_agent_evidence_operator_gate.py`：从已通过的 S1 activation artifact 和 S2 relationship artifact 启动 LangGraph，只运行到 `execute_evidence_operators`，然后停止，不进入 Specialist/Memo/Verifier。
- `scripts/audit_fin_agent_layer_quality.py`：新增 `sec_agent_evidence_operator_diagnostic_v0.1` 识别和 S3 审计。
- `src/sec_agent/ledger_store.py` / `src/sec_agent/mcp_tool_registry.py`：增加 metric-family alias 与 exact-value filing/period relaxed fallback，解决 MSFT 2026 capex 这类 exact lookup 被 S1 年份/表单条件卡死的问题。
- `src/sec_agent/multi_agent_runtime.py`：修复 BGE `auto` 策略，CUDA 可用时 focused / standard / deep 都走 CUDA。

调试过程：

| Run | 结果 | 发现 | 修复 |
| --- | --- | --- | --- |
| `20260601_fin_agent_s3_evidence_operator_gate_v0_1` | fail | MSFT capex exact-value rows 为 `0`。 | 增加 capex/ledger metric alias，并允许 exact lookup 在无结果时放宽 filing type / period role。 |
| `20260601_fin_agent_s3_evidence_operator_gate_v0_2` | pass | 2-case targeted gate 通过。 | 扩展到默认 4-case 覆盖集。 |
| `20260601_fin_agent_s3_evidence_operator_gate_v0_3` | fail | AMZN focused case 触发 BGE，但 CUDA gate 失败，说明 auto 策略在 focused mode 下回落 CPU。 | `_resolve_bge_device` 改为 CUDA 可用时 auto/default 一律选 `cuda`。 |
| `20260601_fin_agent_s3_evidence_operator_gate_v0_4` | pass | 4-case 默认覆盖集通过。 | 接受为当前 S3 gate。 |

S3 v0.4 结果：

| 指标 | 结果 |
| --- | ---: |
| Gate status | pass |
| Case count | 4 |
| Pass count | 4 |
| Tool calls | 14 |
| SEC context rows | 300 |
| Runtime ledger rows | 349 |
| Market snapshot rows | 7 |
| Industry snapshot rows | 10 |
| SEC candidates before rerank | 360 |
| Sent to BGE rerank | 300 |
| BGE CUDA gate | 4/4 |
| Quality audit gate | pass |
| Quality audit weighted score | 2.792 |
| Quality flags | none |

4-case 覆盖：

| Case | Mode | 关键输出 |
| --- | --- | --- |
| `ma_msft_capex_lookup` | deterministic lookup | exact-value ledger rows `37` |
| `ma_amzn_margin_focused` | focused answer | context rows `20`，ledger rows `6`，BGE `cuda` |
| `ma_nvda_amd_market_standard` | standard memo | context rows `40`，ledger rows `136`，market rows `2`，BGE `cuda` |
| `ma_ai_capex_supply_chain_deep` | deep research | context rows `240`，ledger rows `170`，market rows `5`，industry rows `10`，relationship lookup rows `24`，relationship plan rows `4`，BGE `cuda` |

解释：

- S3 证明 operator 层已经不只是 route 成功，而是真实执行了 SEC search、BM25/ObjectBM25/BGE rerank、exact-value ledger、market/industry/relationship 数据注入。
- S3 不评价 Specialist 是否能把 rows 转成高质量 ClaimCards，也不评价 memo 输出；这些必须进入 S4/S5/S6/S7 后分层验证。

下一步：

- 进入 S4 Coverage / Reflection gate。只有 S4 通过后再复用 S3 rows 进入 Specialist，不直接重跑 full chain。
