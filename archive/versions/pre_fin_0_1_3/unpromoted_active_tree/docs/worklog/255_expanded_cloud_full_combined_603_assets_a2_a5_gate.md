# 255 Expanded Cloud Full Combined 603 Assets A2-A5 Gate

日期：2026-06-07

## 问题

上一轮云端 A2/A3 只是 diagnostic：A2 使用 focused exact-value ledger，并且 market/industry 是旧 full238 产物。用户随后确认完整 full-source 资产在 Z 盘，并通过 OSS 临时包提供给云端。本轮目标是先替换 focused/旧产物，再按文档推进 A4/S5 和 A5/S6-S8，避免和旧会话状态断档。

## 资产同步

本地 verified 资产来源：

- Root：`Z:\FIN_Insight_Agent_artifacts\tier1_tier2_full_source_v0_1`
- Combined ledger：`indexes\ledger\tier1_tier2_sec_full_source_mixed_fy2023_2027_v0_1_ledger.duckdb`
- Market：`market\processed\...20260606_market_yahoo_chart_tier1_tier2_1y_v0_1_3m_market_evidence.jsonl` 和 `market_snapshot_catalog.duckdb`
- Industry：`industry\processed\20260606_industry_fred_eia_tier1_tier2_merged_v0_1`

云端解包位置：

- `/autodl-fs/data/fin_agent_milvus_bge_m3/full_source_uploads/tier1_tier2_full_source_v0_1`

校验结果：

- Package SHA256：`a3c351b7f9201313ada1676902660adadf757e1fe52dda972d686be03c5161d1`
- Combined ledger：`6789032` facts，`581` tickers。
- Ledger source tiers：`primary_sec_filing=6331573`，`company_authored_unaudited_sec_filing=457459`。
- Ledger forms：`10-K=5057547`，`10-Q=1128718`，`8-K=457459`，`20-F=126936`，`40-F=18372`。
- Market evidence/snapshot/analytics：`603/603/603` rows；market catalog includes `market_daily_bars=151320`。
- Industry merged evidence：`23` rows；industry observations：`27750` rows。
- FRED 慢源缺口仍按 metadata 保留，不能由模型补写。

临时 OSS URL、SSH 密码和 DeepSeek key 均未写入仓库或持久日志。

## 修复

云端 A4 首次 run `20260607_expanded_a4_cloud_full_combined_603_assets_specialist_gate_deepseek_v0_1` 失败 `1/2`，失败项是 `ma_ai_capex_supply_chain_deep` 的 `industry_supply_chain_analyst` real-evidence quality。根因不是 LLM 输出随机性，而是 artifact root 解析：

- S2 relationship summary 的 `output_dir` 可能记录本地 Windows 路径。
- A4/A5 之前直接信任 `summary["output_dir"]`，云端会读不到 case-level `relationship_lookup.json`。
- 结果是 Industry Specialist 的 input rows 只有 `industry_snapshot`，`relationship_graph` rows 和 relationship summary count 都为 `0`。

修复：

- `scripts/eval_multi_agent/eval_multi_agent_specialist_layer_gate.py`：A4 复用 S3 `_summary_artifact_root(...)`，当 `output_dir` 不存在时回退到 summary JSON 所在目录。
- `scripts/eval_multi_agent/eval_multi_agent_judgment_memo_gate.py`：A5 对 specialist / relationship / evidence / coverage roots 使用同一 fallback。
- `tests/test_eval_multi_agent_gate_config_roundtrip.py`：新增 A4/A5 stale output_dir 回归。

云端修复后检查：`ma_ai_capex_supply_chain_deep` 可从 S2 artifact root 读取 `42` 条 relationship rows。

## 云端门控结果

### A2/S3 full combined + 603 assets

- Run ID：`20260607_expanded_a2_cloud_full_combined_603_assets_operator_gate_v0_1`
- Output：`/root/autodl-tmp/fin_agent_sp500_stage/workspace/eval/sec_cases/outputs/multi_agent_evidence_operator_diagnostic/20260607_expanded_a2_cloud_full_combined_603_assets_operator_gate_v0_1/evidence_operator_diagnostic.json`
- Gate：`pass`
- Cases：`4/4`
- Tool calls：`14`
- Context rows：`146`
- Runtime ledger rows：`430`
- Market snapshot rows：`4`
- Industry snapshot rows：`9`
- SEC pre-rerank candidates：`550`
- BGE candidates：`433`

该 run 替代 254 中 focused ledger / full238 market-industry 的 A2 diagnostic。

### A3/S4 full combined + 603 assets

- Run ID：`20260607_expanded_a3_cloud_full_combined_603_assets_coverage_reflection_gate_v0_1`
- Output：`/root/autodl-tmp/fin_agent_sp500_stage/workspace/eval/sec_cases/outputs/multi_agent_coverage_reflection_diagnostic/20260607_expanded_a3_cloud_full_combined_603_assets_coverage_reflection_gate_v0_1/coverage_reflection_diagnostic.json`
- Gate：`pass`
- Cases：`4/4`
- second-pass allowed：`1`
- second-pass ran：`1`
- second-pass added rows：`0`
- missing requirement count：`1`

### A4/S5 Specialist

- Accepted Run ID：`20260607_expanded_a4_cloud_full_combined_603_assets_specialist_gate_deepseek_v0_2`
- Output：`/root/autodl-tmp/fin_agent_sp500_stage/workspace/eval/sec_cases/outputs/multi_agent_specialist_layer_diagnostic/20260607_expanded_a4_cloud_full_combined_603_assets_specialist_gate_deepseek_v0_2/specialist_layer_diagnostic.json`
- Gate：`pass`
- Cases：`2/2`
- Specialist routes：`7`
- Route pass cases：`2`
- Real evidence quality pass cases：`2`
- Token usage：input `42872`，output `8164`，total `51036`
- Repair attempts：`0`

Supersedes failed v0_1 A4 attempt.

### A5/S6-S8 Judgment / Memo / Verifier

- Run ID：`20260607_expanded_a5_cloud_full_combined_603_assets_judgment_memo_gate_deepseek_v0_1`
- Output：`/root/autodl-tmp/fin_agent_sp500_stage/workspace/eval/sec_cases/outputs/multi_agent_judgment_memo_diagnostic/20260607_expanded_a5_cloud_full_combined_603_assets_judgment_memo_gate_deepseek_v0_1/judgment_memo_diagnostic.json`
- Gate：`pass`
- Cases：`2/2`
- Memo route pass cases：`2`
- Verifier pass cases：`2`
- Memo profiles：`expanded=2`
- Token usage：memo writer `19094`，verifier `9288`，total `28382`
- Memo repair attempts：`0`

## 验证

本地：

- `python -m py_compile scripts\eval_multi_agent\eval_multi_agent_specialist_layer_gate.py scripts\eval_multi_agent\eval_multi_agent_judgment_memo_gate.py tests\test_eval_multi_agent_gate_config_roundtrip.py`
- `python -m pytest tests\test_eval_multi_agent_gate_config_roundtrip.py -q` -> `4 passed`
- `python -m pytest tests\test_multi_agent_specialist_llm.py tests\test_multi_agent_universe_relationship.py -q` -> `49 passed`

云端：

- synced A4/A5 scripts。
- `py_compile` pass。
- relationship artifact root fallback check pass：failed v0_1 case now reads `42` relationship rows。
- A4 v0_2 / A5 v0_1 strict gates pass。

## 决策

- A2-A5 expanded cloud layered gate 现在可以视为通过，且使用完整 combined ledger 与 603-company market/industry 资产，不再依赖 focused ledger / full238 market-industry shortcut。
- 这仍不是生产主路径验收：A1/S1、S2 复用已有 cloud artifacts，A6 10-20 case full-chain / multi-turn 尚未跑，非美 global-public parser 和外部供应链/新闻关系证据仍未补齐。
- 下一步按架构文档进入 A6：先选 10-20 个覆盖 exact / focused / standard / expanded / sector-depth / multi-turn 的小批 full-chain cases，再看是否允许把 expanded path 设为默认 agent 主路径。
