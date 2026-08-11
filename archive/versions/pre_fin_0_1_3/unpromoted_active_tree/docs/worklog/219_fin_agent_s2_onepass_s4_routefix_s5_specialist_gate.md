# 219 - Fin Agent S2 One-Pass、S4 8-K Route Fix 与 S5 Specialist Gate

日期：2026-06-01

## 1. 问题

本轮接续 218 的分层门控。上一版存在两个具体问题：

1. S2 Universe / Relationship 虽然能通过，但需要 `3` 次 DeepSeek call / `2` 次 repair，主要是模型把搜索范围 tickers 和 pack-level refs 写进结构化字段。
2. S4 second-pass 之前对 `8-K` commentary 缺口无新增 rows，根因不是数据不存在，而是 retrieval route / source resolver 对 `2025 + 2026` 与 `8-K` 的 Cartesian scope 处理过严，阻止了可用 2026 8-K rows 进入链路。

本轮目标：

1. 让 S2 尽量 one-pass，通过 deterministic completion / sanitizer 修掉机械字段错误。
2. 修复 S4 上游的 8-K route 过滤，使 S3 能直接拿到可用 8-K rows，S4 不再把可检索证据误判为缺口。
3. 新增 S5 Specialist layer gate，复用 S1-S4 artifacts，只跑 Specialist layer，不重跑检索。

## 2. 实现

### S2 One-Pass

- `src/sec_agent/universe_relationship_llm.py`
  - 在 LLM 输出后强制从 bounded lookup rows 补全 `relationships`。
  - 对 `included_tickers` / `expanded_tickers` 只允许 focus tickers 和有 relationship evidence 的 tickers。
  - 新增 `EconomicLinkMap` deterministic completion：从 lookup rows 自动补 `entities`、`links`、`mechanisms`、`investment_implications`。
  - 新增 economic-map sanitizer：如果模型把 `MSFT/AMZN/GOOGL` 这类搜索范围但无 relationship rows 的 tickers 写入 entity/link，则丢弃该 row，并从 lookup rows 补最小合规 map。
  - fallback plan 也补 `EconomicLinkMap`，避免 diagnostic artifact 空 map。

### S4 8-K Route Fix

- `src/sec_agent/mcp_tool_registry.py`
  - 对显式 `retrieval_route` 的 SEC search，也按 manifest 编译可用 form/year/tier route scope。
  - 避免把不存在的 `2025 8-K` 和存在的 `2026 8-K` 混在同一个不可满足 scope 里。
- `scripts/run_sec_benchmark_eval.py`
  - `SEC_PRIMARY_MIXED_WITH_8K_EARNINGS` / `8-K` partial source missing 不再 fatal；有可用 filings 时允许继续检索。
- `scripts/eval_multi_agent_evidence_operator_gate.py`
  - S3 summary 写入完整但 capped 的 `context_rows`、`runtime_ledger_rows`、`market_rows`、`industry_rows` 和 `source_gaps`，而不是只给 5-row sample。
- `scripts/eval_multi_agent_coverage_reflection_gate.py`
  - S4 优先读取 S3 full rows 字段，再 fallback 到 legacy sample 字段。

### S5 Specialist Layer Gate

- 新增 `scripts/eval_multi_agent_specialist_layer_gate.py`。
- 从 S1 activation、S2 relationship、S3 evidence、S4 coverage artifacts 重建 LangGraph state。
- 入口节点为 `optional_specialist_subgraph`，stop node 也是 `optional_specialist_subgraph`。
- 真实调用 `SEC_AGENT_MULTI_AGENT_SPECIALIST_ROUTER=llm`，但不重跑 S1-S4。
- Gate 区分：
  - Specialist route 是否成功。
  - Specialist 是否真的消费 bounded evidence rows。
  - Industry/Supply-Chain 是否看到并引用 relationship evidence。
  - 各 Specialist 输出 refs 是否来自已知 bounded rows。

## 3. 真实运行结果

| Stage | Run ID | Gate | Key metrics |
| --- | --- | --- | --- |
| S2 | `20260601_fin_agent_s2_relationship_inference_onepass_deepseek_v0_3` | pass | `1/1` case，`1` call，`0` repair，`0` fallback，lookup relationships `42`，plan relationships `42`，tokens `10,975` |
| S3 | `20260601_fin_agent_s3_after_s2_onepass_and_8k_routefix_v0_1` | pass | `4/4` cases，tool calls `14`，context rows `371`，runtime ledger rows `399`，8-K rows 已进入 AMZN/NVDA-AI cases，BGE CUDA gate `4/4` |
| S4 | `20260601_fin_agent_s4_after_8k_second_pass_routefix_v0_1` | pass | `4/4` cases，missing requirements `0`，second-pass allowed `0`，说明 8-K 缺口已在 S3 上游解决 |
| S5 | `20260601_fin_agent_s5_specialist_layer_gate_after_s4_v0_1` | pass | `2/2` specialist cases，`7` specialist routes，real evidence quality `2/2`，`0` repair，tokens `65,251` |

S5 case 级结果：

| Case | Specialists | Input rows / source behavior |
| --- | --- | --- |
| `ma_nvda_amd_market_standard` | Fundamental / Market / Risk | Fundamental `24` primary SEC rows；Market `2` market rows；Risk `16` SEC/8-K/market rows；全部 route pass，refs known |
| `ma_ai_capex_supply_chain_deep` | Fundamental / Industry / Market / Risk | Fundamental `32` primary SEC rows；Industry `32` industry/relationship rows，relationship summary `24` rows，引用 relationship refs `14`；Market `5` rows；Risk `32` rows；全部 route pass，refs known |

## 4. 判断

- S2 one-pass 问题已修复。之前高 token 主要来自 repair loop；现在仍有约 `10.9k` tokens，因为 prompt 输入包含较多 lookup relationship rows，但没有 repair 浪费。
- S4 second-pass 问题不是 Reflection 本身，而是 S3 8-K route scope 编译过严。修复后 S3 能拿到 8-K rows，S4 正确判断 evidence sufficient，不再触发无意义 second pass。
- S5 证明当前 Specialist layer 能理解上游任务、消费 bounded rows、按 evidence boundary 输出，并且 Industry Specialist 能使用 relationship evidence。
- S5 token 仍高：2 个 case / 7 个专家合计 `65,251` tokens。后续 S6-S7 前应继续保留 route 成功与 evidence-quality 区分，不能因为 S5 gate pass 就认为最终 memo 已达标。

## 5. 验证

单测与编译：

```text
python -m pytest tests/test_multi_agent_universe_relationship_llm.py tests/test_multi_agent_universe_relationship.py tests/test_relationship_graph_lookup.py -q
result: 25 passed

python -m pytest tests/test_multi_agent_universe_relationship_llm.py tests/test_multi_agent_universe_relationship.py tests/test_relationship_graph_lookup.py tests/test_multi_agent_reflection_second_pass.py tests/test_multi_agent_langgraph_routing.py tests/test_fin_agent_layer_quality_audit.py -q
result: 56 passed

python -m compileall src/sec_agent/universe_relationship_llm.py src/sec_agent/mcp_tool_registry.py scripts/run_sec_benchmark_eval.py scripts/eval_multi_agent_evidence_operator_gate.py scripts/eval_multi_agent_coverage_reflection_gate.py scripts/eval_multi_agent_specialist_layer_gate.py
result: pass
```

真实门控：

- S2 one-pass DeepSeek gate: pass。
- S3 real retrieval / BGE CUDA gate: pass。
- S4 Coverage / Reflection gate: pass。
- S5 Specialist layer DeepSeek gate: pass。

## 6. 后续

1. S6 Judgment Aggregator：复用 S5 outputs，检查是否能把 Specialist ClaimCards 合成为 `memo_thesis_plan`，不能压扁冲突或 source boundary。
2. S7 Memo Writer：只消费 S6 thesis plan 和精选 ClaimCards，评估最终 memo 是否从 evidence summary 变成有投资观点的结构化 memo。
3. S8 Verifier：从“安全门”升级为 memo-quality gate，检查 thesis coverage、反证、source-boundary 和 unsupported leakage。
4. S9 Renderer / user-facing output：检查中文可读性、证据引用和 bounded caveat 呈现。

## 7. 风险与安全

- DeepSeek key 只通过环境变量读取，未写入代码、文档或 artifacts。
- S5 通过不等于最终 memo 通过；当前只是证明专家层可以把真实 rows 转为合规 ClaimCards。
- `reports/eval/` 和 `eval/sec_cases/outputs/` 为生成 artifacts，默认不纳入提交。
