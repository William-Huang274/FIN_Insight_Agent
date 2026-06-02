# 218 - Fin Agent S2 Relationship Inference 与 S4 Reflection Gate

日期：2026-06-01

## 1. 问题

上一轮 S2 只能生成经济传导假设，不能保证 bounded relationship lookup rows 被完整保留下游可见；S4 也还没有作为单层门控验证 second-pass request、loop break 和 source-gap boundary。

本轮目标：

1. 升级 S2 relationship edge schema，让已有 sector-depth 数据中能被推断的关系都进入结构化 relationship rows。
2. 明确 inferred relationship 和 confirmed direct customer/supplier edge 的边界。
3. 复用已通过 S1/S2/S3 artifact，运行 S4 Coverage / Reflection gate。
4. 把 S2/S3/S4 结果写入 model-run ledger 和分层执行文档。

## 2. S2 实现与结果

主要实现：

- `relationship_graph` edge schema 升级到 v0.3，新增 `inference_level`、`confirmation_status`、`evidence_basis`、`missing_confirmations`、`source_limitations`。
- `UniverseRelationshipPlan` validator 要求 `sector_inferred` / `category_inferred` 关系不得写成 confirmed direct edge；必须保留 missing confirmations。
- Universe LLM prompt 不再要求模型复制完整 relationship rows；模型只产出经济图谱，runtime 用 deterministic completion 把 lookup rows 补回 plan。
- S2 eval gate 新增 relationship coverage、inference-level、direct-edge boundary 和 external confirmation gap 检查。

真实 DeepSeek 运行：

| Run ID | Gate | Key metrics |
| --- | --- | --- |
| `20260601_fin_agent_s2_relationship_inference_coverage_gate_deepseek_v0_2` | pass | lookup relationships `42`，plan relationships `42`，deterministic completed `42`，fallback `0`，tokens `36,646`，latency `102,207 ms` |

解释：

- 当前本地数据能推断 sector-depth economic relationship：例如 AI capex 相关上下游、同一产业包内供需/需求传导假设。
- 当前本地数据不能证明完整商业关系图谱，因为没有独立的 customer/supplier graph artifact，也没有合同、订单、客户集中度、供应商披露等外源或专门抽取数据。
- 因此所有 42 条关系都标记为 `sector_inferred` + `no_confirmed_direct_edge`，只支持研究范围、传导假设和 Specialist 上下文。

## 3. S3 复跑结果

使用新的 S2 relationship inference artifact 复跑 S3：

| Run ID | Gate | Key metrics |
| --- | --- | --- |
| `20260601_fin_agent_s3_after_s2_relationship_inference_v0_2` | pass | cases `4/4`，tool calls `14`，context rows `300`，runtime ledger rows `349`，market rows `7`，industry rows `10`，SEC candidates `360`，BGE candidates `300`，BGE CUDA gate `4/4` |

结论：

- `sec_search_filings` 真实触发 BM25 / ObjectBM25 / BGE rerank。
- exact-value ledger、market snapshot、industry snapshot、relationship rows 都能形成可传给 S4/S5 的 bounded row payload。

## 4. S4 Coverage / Reflection 实现与结果

新增：

- `scripts/eval_multi_agent_coverage_reflection_gate.py`。
- `coverage_reflection` artifact-only audit 入口。
- `optional_second_pass` 的 stop-after-node 路由修复，避免 stop 后继续进入 Specialist。
- `compile_second_pass_retrieval_plan` 修复：second-pass contract 必须使用 reflection 生成的 requirements，不能复用 stale 原始 requirements。

真实 S4 运行：

| Run ID | Gate | Key metrics |
| --- | --- | --- |
| `20260601_fin_agent_s4_coverage_reflection_gate_after_s3_v0_1` | pass | cases `4/4`，second-pass allowed `3`，second-pass ran `3`，added rows `0`，missing requirements `3`，audit score `2.844` |

Case 级现象：

| Case | Missing requirement | Second pass | 结果 |
| --- | --- | --- | --- |
| `ma_msft_capex_lookup` | 0 | 未触发 | exact-value rows 已满足 |
| `ma_amzn_margin_focused` | `8k_commentary:no_rows` | 触发 | 无新增 rows，bounded no-gain 中止 |
| `ma_nvda_amd_market_standard` | `8k_commentary:no_rows` | 触发 | 无新增 rows，bounded no-gain 中止 |
| `ma_ai_capex_supply_chain_deep` | `8k_commentary:no_rows` | 触发 | 无新增 rows，bounded no-gain 中止 |

结论：

- S4 已能区分无缺口 case、可查缺口 case 和二次检索无增益 case。
- 当前仍没证明 second pass 对 evidence quality 有正增益；这轮只证明了 bounded retry 和 loop break 是安全的。

## 5. 验证

单测：

```text
python -m pytest tests/test_multi_agent_universe_relationship_llm.py tests/test_multi_agent_universe_relationship.py tests/test_relationship_graph_lookup.py tests/test_multi_agent_reflection_second_pass.py tests/test_multi_agent_langgraph_routing.py tests/test_fin_agent_layer_quality_audit.py -q
result: 56 passed
```

编译检查：

```text
python -m compileall src/sec_agent/universe_relationship_llm.py src/sec_agent/multi_agent_runtime.py src/sec_agent/langgraph_orchestrator.py scripts/eval_multi_agent_universe_relationship_gate.py scripts/eval_multi_agent_coverage_reflection_gate.py scripts/audit_fin_agent_layer_quality.py
result: pass
```

真实门控：

- S2 relationship inference coverage gate: pass。
- S3 evidence operator gate after S2: pass。
- S4 coverage reflection gate: pass。
- S4 quality audit: pass，weighted score `2.844`，quality flags none。

## 6. 后续顺序

1. S5 Specialist：复用 S3/S4 rows 和 source-gap boundary，检查每个 Specialist 是否能把 rows 转成 memo-ready ClaimCards。
2. S5 不通过时，只修 Specialist data view / skill / prompt，不重跑 S1-S4。
3. S6 Aggregator：从 ClaimCards 生成 `InvestmentThesisPlan`。
4. S7 Memo Writer：只消费 thesis plan 和精选 claim cards，继续压 token 和 retry。
5. S8/S9 通过后再进入 S10 full-chain / multi-turn。

## 7. 风险与回滚

- S2 token 仍偏高，主要来自 3 次 LLM call / 2 次 repair；可优化 prompt 和 validation failure diagnostics，但不影响当前 gate 通过。
- S4 three second-pass attempts 都无新增 rows，说明缺口可能是源数据不可达或当前 operator 对 8-K commentary 覆盖不足；进入 S5 时必须保留 source-gap boundary，不能让 Specialist 或 Memo Writer 填空。
- 所有 credential 只通过环境变量读取，未写入文档或 run artifacts。
