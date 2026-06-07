# Fin Agent Full-Chain / Multi-Turn Eval Plan v0.1

日期：2026-06-01

## 1. 目标

本轮用于收口前的真实 full-chain / multi-turn 能力检查。它不替代 S1-S8 分层门控，而是在分层门控稳定后验证：

- Research Lead 是否按问题难度精准激活 agent，而不是所有问题都开全员。
- Evidence Operators 是否真实触发 SEC BM25/ObjectBM25/BGE、market、industry、relationship lookup。
- Specialist 是否能消费真实 evidence rows，输出可被 Aggregator / Memo Writer 使用的 ClaimCards。
- Memo Writer / Verifier / Renderer 是否稳定产出中文或英文目标语言的投研输出。
- Multi-turn scope revision 是否能沿用上一轮上下文，同时遵守新一轮的 scope override。

## 2. 执行纪律

先设计 `10-20` 个 case，但真实 DeepSeek 先跑 `2-3` 个高信息量 case：

1. 若任一 case 出现 hard gate fail，停止扩展，先修 root cause。
2. 若失败是数据覆盖 ceiling，记录为 data/source limitation，不通过 prompt 让模型补事实。
3. 若失败是 token/repair 成本异常，先降 payload 或修 gate，不继续批量跑。
4. 只有首批 smoke 全 pass 后，才扩到更多行业 / multi-turn case。

## 3. Case Fixture

Fixture 路径：

`tests/fixtures/fin_agent_full_chain_multiturn_cases_v0_1.jsonl`

当前包含 `20` 个 case：

| Case ID | 类型 | 公司 / 行业 | 主要考察 |
| --- | --- | --- | --- |
| `fin_full_exact_msft_capex_zh` | exact lookup | MSFT | 单指标、低成本、非 memo 路径、真实 SEC/ledger |
| `fin_full_exact_jpm_credit_provision_zh` | exact lookup | JPM | 银行指标 exact-value retrieval |
| `fin_full_focused_amzn_margin_management_zh` | focused answer | AMZN | 10-Q + 8-K 管理层解释，不激活 Specialist |
| `fin_full_focused_healthcare_lly_rnd_zh` | focused answer | LLY | 医疗外部临床/监管缺口边界 |
| `fin_full_standard_nvda_amd_market_zh` | standard memo | NVDA/AMD | 基本面 + 8-K + market + risk |
| `fin_full_standard_jpm_bac_deposit_credit_zh` | standard memo | JPM/BAC | 银行 NII / deposit / credit risk |
| `fin_full_standard_xom_cvx_energy_zh` | standard memo | XOM/CVX | energy capex / commodity / cash flow |
| `fin_full_standard_wmt_tgt_consumer_zh` | standard memo | WMT/TGT | consumer margin / inventory / demand |
| `fin_full_sector_ai_infra_depth_zh` | sector-depth | NVDA/DELL/ANET/VRT | AI infra relationship + industry + risk |
| `fin_full_sector_banking_depth_zh` | sector-depth | JPM/C/WFC/GS | financial services relationship pack |
| `fin_full_sector_healthcare_depth_zh` | sector-depth | PFE/BMY/AMGN/HCA | healthcare pack + data limitation |
| `fin_full_sector_utilities_power_depth_zh` | sector-depth | NEE/DUK/SO + AI capex names | AI power-load transmission |
| `fin_full_english_msft_googl_ai_capex_en` | standard memo | MSFT/GOOGL | 英文输出 contract / language gate |
| `fin_full_mt_semis_scope_t1` | multi-turn T1 | NVDA/AMD | 首轮标准 memo；只要求 Fundamental + Market；未显式要求 risk 时 Risk 必须不激活 |
| `fin_full_mt_semis_scope_t2` | multi-turn T2 | NVDA only + AI capex chain | Scope override，不能继续分析 AMD |
| `fin_full_mt_banking_t1` | multi-turn T1 | JPM/BAC | 首轮银行比较 |
| `fin_full_mt_banking_t2` | multi-turn T2 | BAC only | Follow-up narrowed scope，不能继续分析 JPM |
| `fin_full_scope_nvda_basic_fundamental_zh` | scope-decision | NVDA | 单公司基本面必须先窄 scope，可条件扩展但不能无故全行业扩展 |
| `fin_full_scope_nvda_ai_supply_chain_readthrough_zh` | scope-decision | NVDA + AI infra chain | 检查 cloud capex、memory/foundry/equipment、server/networking/power、export risk、market reaction 的 scope decision 和 Universe contract |
| `fin_full_scope_nvda_non_us_supply_chain_gap_zh` | scope / gap escalation | NVDA + non-US supply chain | 非美供应链 disclosure 若只有 hypothesis/source gap，必须输出 structured gap request 并在 Memo/Renderer 保留边界 |

## 4. Hard Gates

所有 case：

- `agent_activation_validation.status=pass`。
- required agents present，forbidden agents absent。
- expected tool names called。
- tool ownership valid，无 duplicate / budget loop break。
- summary 不保存 raw evidence、API key 或 private path。

Exact lookup case：

- 必须产生 `runtime_ledger_rows`，不能只靠 text context rows 或 bounded stub 通过。
- 若真实 ledger store 未配置，`ledger_first` 可通过 `sec_search_filings` 回退到 ObjectBM25 / SQLite structured-object retrieval 构建 runtime ledger。
- 对 exact-value 单指标，结构化 `ledger_first` ObjectBM25 命中可替代 BGE rerank gate；standard / sector-depth memo 仍要求 SEC 检索有 BM25/BGE rerank 证据。
- Renderer 必须输出用户语言下的单指标结果和证据边界，不能返回 `Bounded answer only` 空壳。

Memo / Renderer case：

- Memo LLM route pass，无 deterministic fallback。
- Verifier pass。
- `response_language` 与 query / case contract 一致。
- 中文 case 的 rendered answer 必须主要为中文；英文 case 不强制中文。
- 要求 rendered claims 的 case 必须出现 `关键论据:` / `Key memo claims:`。
- 要求 refs 的 case 必须出现 `证据=` / `refs=`。
- Specialist activation gate 需要区分 primary 和 conditional：没有风险/反证/信用/下行情景 intent 的 standard memo，应跳过 `risk_counterevidence_analyst`；若 case prompt 明确要求 risk / counterevidence / credit risk / 反证，则必须激活并通过。

Sector-depth case：

- relationship lookup 被调用。
- expected relationship pack 可见且被正确使用。
- Industry Specialist 必须看到并引用 relationship evidence。
- relationship graph 只能支撑 hypothesis / research scope，不能写成确认客户/供应商事实。

Multi-turn case：

- `conversation_id` 和 `turn_index` 有序。
- T2 必须接收 previous turn summary。
- 若 T2 缩小 scope，forbidden scope ticker 不得进入 activated focus/search scope。
- T2 不允许把上一轮已排除 ticker 继续作为主分析对象。

A6 scope-decision / gap-escalation case：

- Research Lead 必须输出 `scope_decision`，包含 `scoping_pattern`、`expansion_mode`、`catalogs_to_inspect`、`candidate_lenses`、`expansion_budget`、`stop_condition`。
- `scoping_pattern` 必须落在 case 的 expected set 中，例如 `single_company_fundamental`、`supply_chain_readthrough`、`sector_depth`。
- `expansion_mode` 必须符合 case 预期：`no_expansion`、`conditional_expansion` 或 `required_expansion`。
- Universe / Relationship 被要求时，必须输出 per-ticker scope contract：`included_ticker`、`candidate_lens`、`inclusion_rationale`、`available_source_families`、`relationship_strength`、`downstream_operator_owner`。
- 若 case 要求 excluded rationale，excluded ticker 必须带 `excluded_ticker`、`candidate_lens`、`exclusion_rationale`。
- Specialist 输出的 `evidence_gap_requests` 必须按要求的 request type 出现，并被 Judgment / Memo 保留。
- Renderer 必须显示 hypothesis-only、source gap 或 coverage boundary，不能把缺口包装成 confirmed finding。

Token / latency case：

- 每个 A6 scope case 可设置 `max_case_elapsed_ms_lte`、`max_total_tokens_lte`、`max_research_lead_tokens_lte`、`max_universe_tokens_lte`、`max_specialist_tokens_lte`、`max_memo_tokens_lte`、`max_verifier_tokens_lte`。
- 这些阈值是真实云端 A6 的 stop/proceed 约束，不是本地单测目标。
- 如果 token 或 latency fail，先看 prompt/data-view/second-pass 是否过宽；不要只提高 max tokens。

## 5. 首批 Smoke

建议首批只跑：

1. `fin_full_exact_msft_capex_zh`
2. `fin_full_scope_nvda_basic_fundamental_zh`
3. `fin_full_standard_nvda_amd_market_zh`
4. `fin_full_sector_ai_infra_depth_zh`

原因：

- 覆盖 exact lookup、单公司 scope decision、standard memo、deep research relationship path。
- 只跑 4 个 case 即可捕捉 retrieval、scope contract、language gate、memo/verifier、relationship 的主要风险。
- 如果这 4 个稳定，再跑 banking / energy / healthcare / utilities / multi-turn / gap-escalation 的行业扩展。

## 6. 命令模板

```powershell
python scripts\eval_multi_agent\eval_multi_agent_real_llm_chain.py `
  --cases-path tests\fixtures\fin_agent_full_chain_multiturn_cases_v0_1.jsonl `
  --output-dir eval\sec_cases\outputs\multi_agent_real_llm_chain_eval `
  --run-id 20260607_expanded_a6_scope_smoke_v0_1 `
  --case-id fin_full_exact_msft_capex_zh `
  --case-id fin_full_scope_nvda_basic_fundamental_zh `
  --case-id fin_full_standard_nvda_amd_market_zh `
  --case-id fin_full_sector_ai_infra_depth_zh `
  --real-evidence-operators `
  --evidence-top-k 16 `
  --object-top-k 16 `
  --reranker-candidate-limit 48 `
  --reranker-top-k 10 `
  --memo-max-tokens 4200 `
  --verifier-max-tokens 1200 `
  --strict
```

如果首批通过，再新增：

- `fin_full_scope_nvda_ai_supply_chain_readthrough_zh`
- `fin_full_scope_nvda_non_us_supply_chain_gap_zh`
- `fin_full_standard_jpm_bac_deposit_credit_zh`
- `fin_full_standard_xom_cvx_energy_zh`
- `fin_full_sector_utilities_power_depth_zh`
- `fin_full_english_msft_googl_ai_capex_en`

## 7. Stop / Proceed

Proceed：

- 首批 smoke `3/3` hard gate pass。
- Memo / Verifier fallback 为 `0`。
- rendered answer language gate pass。
- scope-decision case 的 `scope_gap_contract.*` 全 pass。
- performance layer 的 token / latency 阈值全 pass。

Stop：

- 任一 full-chain gate fail。
- 真实 retrieval 没触发但 case 要求 real retrieval。
- Verifier pass 依赖 fallback 或 repair 成本异常。
- 中文 output 退回英文。
- Research Lead 缺 `scope_decision`，或 Universe 缺 per-ticker scope contract。
- gap-escalation case 中 Specialist gap request 未被 Judgment / Memo / Renderer 保留。
- token / latency 超过 case 明确阈值。

Pivot：

- 本地数据无法支持某行业事实，例如临床结果、实时监管、外部 consensus、商品实时价格。
- 记录 source/data limitation，再决定是否扩数据源，而不是让 LLM 猜。

## 8. 当前执行状态

Accepted functional smoke:

- Run ID: `20260601_fin_agent_full_chain_multiturn_smoke_after_lead_prune_v0_1`
- Cases: exact MSFT capex + semis multi-turn T1/T2
- Gate: `3/3` pass
- Tool calls: `14`
- T1 no-risk prompt: `risk_counterevidence_analyst` 已被正确跳过。
- T2 scope override: 没有继续把 AMD 作为主分析对象。

未通过收口门控的问题：

- T2 deep-research 仍有 `high_total_token_cost`，总 tokens `80,293`。
- 单纯降低 top-k / output caps 的 `20260601_fin_agent_full_chain_t2_cost_tight_smoke_v0_1` 未改善成本，反而升至 `88,893` tokens，不作为推荐配置。

Proceed 条件补充：

- 后续扩到剩余 `14` 个 case 前，需要先把同一 T2 deep-research 的 token cost 降到质量框架阈值内，且保持 gate pass、rendered answer 中文、relationship / risk / market claim cards 不退化。
