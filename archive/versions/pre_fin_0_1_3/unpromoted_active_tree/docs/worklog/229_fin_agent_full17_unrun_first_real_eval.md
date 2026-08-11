# 229 Fin Agent 17-case Full-chain 未跑优先真实评测

## 背景

用户要求做一次 17-case full-chain 测试，并优先跑之前没跑过的 case。本轮使用 `tests/fixtures/fin_agent_full_chain_multiturn_cases_v0_1.jsonl`，先生成未跑过优先的临时 ordered cases 文件：

- `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/_ordered_cases/20260602_fin_agent_full17_unrun_first_cases_v0_1.jsonl`

未跑优先顺序为：

1. `fin_full_standard_nvda_amd_market_zh`
2. `fin_full_sector_ai_infra_depth_zh`
3. `fin_full_sector_banking_depth_zh`
4. `fin_full_sector_healthcare_depth_zh`
5. `fin_full_sector_utilities_power_depth_zh`
6. `fin_full_mt_banking_t1`
7. `fin_full_mt_banking_t2`

随后跑此前已通过或已覆盖过的 10 个 case。

## Run

- Run ID: `20260602_fin_agent_full17_unrun_first_real_retrieval_v0_1`
- Entry point: `scripts/eval_multi_agent_real_llm_chain.py`
- Mode: real evidence operators, strict gate
- Result: `fail`
- Total cases: `17`
- Passed: `8`
- Failed: `9`
- Pass rate: `0.4706`
- Wall time: `3,192,528 ms`（约 `53.2` 分钟）
- Total tool calls: `91`

## Category Results

| Category | Cases | Passed | Failed | Notes |
| --- | ---: | ---: | ---: | --- |
| `standard_memo` | 5 | 5 | 0 | 当前最稳定路径。 |
| `focused_answer` | 2 | 2 | 0 | AMZN / LLY focused 均通过；LLY v0.10 guard 在完整 run 中保持有效。 |
| `sector_depth` | 4 | 0 | 4 | 全部被 Specialist real-evidence quality gate 拦下，主要是 temporal claim ref-depth。 |
| `multi_turn` | 4 | 1 | 3 | T1/T2 scope inheritance 和 activation/gate contract 仍不稳。 |
| `exact_lookup` | 2 | 0 | 2 | deterministic lookup 与 eval real-retrieval gate 存在 contract mismatch，且 exact row selector 质量仍需修。 |

## Case Results

| Ord | Case | Gate | Mode | Elapsed(s) | Tools | Main Failure |
| ---: | --- | --- | --- | ---: | ---: | --- |
| 1 | `fin_full_standard_nvda_amd_market_zh` | pass | `standard_memo` | 165.9 | 4 | - |
| 2 | `fin_full_sector_ai_infra_depth_zh` | fail | `deep_research` | 211.3 | 11 | Risk Specialist temporal ref-depth |
| 3 | `fin_full_sector_banking_depth_zh` | fail | `deep_research` | 228.0 | 10 | Fundamental temporal ref-depth |
| 4 | `fin_full_sector_healthcare_depth_zh` | fail | `deep_research` | 320.5 | 12 | Fundamental temporal ref-depth |
| 5 | `fin_full_sector_utilities_power_depth_zh` | fail | `deep_research` | 344.5 | 10 | tool budget exhausted + Risk temporal ref-depth |
| 6 | `fin_full_mt_banking_t1` | pass | `standard_memo` | 143.1 | 4 | - |
| 7 | `fin_full_mt_banking_t2` | fail | `focused_answer` | 111.8 | 3 | missing expected `market_operator` / `market_get_snapshot` |
| 8 | `fin_full_exact_msft_capex_zh` | fail | `deterministic_lookup` | 28.3 | 1 | eval expects `sec_search_filings/BGE`; exact row selector picked weak capex rows |
| 9 | `fin_full_exact_jpm_credit_provision_zh` | fail | `deterministic_lookup` | 24.0 | 1 | eval expects `sec_search_filings/BGE`; row selector picked change-rate rows |
| 10 | `fin_full_focused_amzn_margin_management_zh` | pass | `focused_answer` | 56.7 | 3 | - |
| 11 | `fin_full_focused_healthcare_lly_rnd_zh` | pass | `focused_answer` | 71.3 | 3 | - |
| 12 | `fin_full_standard_jpm_bac_deposit_credit_zh` | pass | `standard_memo` | 146.2 | 3 | - |
| 13 | `fin_full_standard_xom_cvx_energy_zh` | pass | `standard_memo` | 165.7 | 5 | - |
| 14 | `fin_full_standard_wmt_tgt_consumer_zh` | pass | `standard_memo` | 394.3 | 3 | slow but pass |
| 15 | `fin_full_english_msft_googl_ai_capex_en` | pass | `standard_memo` | 306.6 | 4 | slow but pass |
| 16 | `fin_full_mt_semis_scope_t1` | fail | `standard_memo` | 147.7 | 4 | forbidden `risk_counterevidence_analyst` activated |
| 17 | `fin_full_mt_semis_scope_t2` | fail | `deep_research` | 326.3 | 10 | tool budget exhausted |

## Main Findings

### 1. Standard / Focused path 已经可用

- `standard_memo`: `5/5` pass。
- `focused_answer`: `2/2` pass。
- 本轮新增的 focused unit guard 和中文残句 guard 在 LLY case 中保持稳定。

### 2. Sector-depth 失败不是检索没跑，而是 quality gate 和证据粒度不匹配

4 个 sector-depth case 都完成了 deep-research route、real SEC retrieval、market/industry/relationship retrieval 和 Specialist LLM。失败主要来自 `specialists.real_evidence_quality_pass=false`。

典型失败：

- Banking: Fundamental claim 写 “JPM 1Q26 net revenue up 19% YoY”，只引用 1 个 evidence ref，temporal gate 要求至少 2 个 refs。
- Healthcare: HCA 4.3% year-over-year revenue growth，只引用 1 个 evidence ref。
- AI infra / Utilities: Risk claim 使用单条 disclosure row 说明 trend / prior-period context，被 temporal ref-depth gate 拦下。

当前假设：SEC / 8-K 表格行常常在单个 evidence row 中同时包含 current period、prior period 和 YoY/change 信息；现在的 gate 机械要求两个 evidence refs，会误杀这种“单证据行内置比较口径”的合法 claim。后续应升级 temporal gate，让它检查 cited row 是否包含 YoY/prior-period/comparative markers，而不是只数 ref 个数。

### 3. Exact lookup 需要单独修 contract 和 row selector

Exact case 只触发 `sec_query_exact_value_ledger`，符合 deterministic lookup 的成本目标；但 eval case 仍要求 `sec_search_filings` / BGE，因此 gate contract 不一致。

同时输出质量也暴露 selector 问题：

- MSFT capex case 把 property/equipment net 和 land 等资产科目排到了前面，弱于直接 capex/additions row。
- JPM credit provision case 把 change-rate rows 排到前面，弱于 total amount / provision amount rows。

后续应对 exact lookup 做：

- deterministic lookup gate 与 full retrieval gate 分离；
- exact-value selector 按 metric_role / metric_family / role priority 排序；
- 金额问题优先 `total_value / amount / period_change_amount`，rate/change-rate 只在用户问增长率或变化率时选。

### 4. Multi-turn 仍不稳

- Banking T1 pass，T2 失败：T2 被判为 focused answer 但 fixture 要求 market operator；可能是 case contract 过强，也可能是 previous turn context 没让 Lead 理解需要沿用市场维度。
- Semis T1 失败：Risk Specialist 被激活，但 fixture forbidden risk。当前 Lead 的 risk-balanced activation 可能比 fixture 更积极；需要重新定义该 multi-turn case 是否应禁止 Risk。
- Semis T2 失败：deep-research 工具预算耗尽，说明 T2 scope expansion 下 tool budget / grouped route / second-pass 仍需优化。

### 5. Latency / token 仍偏高

Quality audit flags:

- `high_total_token_cost`: `5`
- `low_memo_chars_per_token`: `7`
- `memo_surface_says_evidence_thin`: `9`
- `memo_writer_retry_cost_present`: `1`

慢 case：

- WMT/TGT standard: `394.3s`
- Utilities sector-depth: `344.5s`
- Semis T2: `326.3s`
- Healthcare sector-depth: `320.5s`
- English MSFT/GOOGL: `306.6s`

说明 route coalescing 降低了重复检索，但真实 LLM 编排和 deep-research Specialist/Memo/Verifier 仍是主要成本。

## Next Fix Order

1. 修 exact lookup selector 和 deterministic gate contract。
2. 修 Specialist temporal gate：允许单 evidence row 中有 explicit YoY / prior-period / percent-change markers 时通过。
3. 修 deep-research tool budget：对 sector-depth / multi-turn T2 做 per-agent route cap 和 grouped route reuse audit。
4. 修 multi-turn context inheritance：T2 是否继承 T1 的 market / risk / scope 维度要显式进入 Research Lead prompt。
5. 复跑失败子集，而不是再直接跑 17-case 全量：
   - exact 2 case
   - sector-depth 4 case
   - multi-turn 3 case

## Safety

- Runtime credential 只从环境变量读取。
- 未保存 API key。
- Raw LLM response 未保存。
- Ordered cases 文件是临时 eval artifact，不应作为主线代码提交，除非后续决定把“unrun-first 17-case”变成正式 fixture。
