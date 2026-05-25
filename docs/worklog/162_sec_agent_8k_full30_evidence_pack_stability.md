# 162 SEC Agent 8-K Full30 Evidence Pack Stability

Date: 2026-05-25

## Problem

- P1 8-K earnings-release source needed从 pilot 扩到 full30，并验证 mixed 10-K/10-Q/8-K 全链路稳定性。
- full30 初次扩展暴露出真实链路问题：
  - 多家公司 2026 已有 Item 2.02 8-K，但 Exhibit 99.1 文件名不含 `ex991`，例如 `q1fy27pr.htm`，主 8-K HTML 表格只写 `99.1 Press Release`，旧 selector 误报 `no_earnings_release_exhibit_for_item_2_02_8k`。
  - retrieval 已找回 `8K_EARNINGS::*` rows，但 final evidence pack 的 48 行预算被 ledger/coverage rows 吃满，8-K rows 没进入 synthesis prompt，导致模型只写 8-K 边界而不引用 8-K 内容。
  - `Data Center net revenue of $5.8 billion ... increased by 57%` 这类句子同时包含总额和增长率，旧 `metric_role` 判断用整句 context，把 `$5.8 billion` 误标为 `period_change_amount`。
  - model output 仍可能把 `services_revenue/cloud_revenue` 推断为“经常性收入特征”，但当前 ledger 未给出 ARR/subscription/RPO/deferred revenue 支撑。

## Decisions

- 不通过兜底扩大结果，而是修核心契约：
  - 8-K selector 必须支持 SEC exhibit 表格中的纯 `99.1` / `99.01` 行标签和相对 `href` 文件名。
  - mixed-with-8k source contract 必须保证已请求、已检索到的 company-authored 8-K rows 进入 final synthesis evidence pack，而不是只存在于 retrieval trace。
  - `metric_role` 应按当前 numeric value 的语义判断；同一句里的增长率不能污染前面的金额总额。
  - 收入质量过度表述的 sanitizer 必须覆盖最终 answer 结构里的 `decision_drivers` 字段。

## Implementation

- `src/connectors/sec_edgar_connector.py`
  - `_exhibit_descriptions_from_primary_html(...)` 支持 `href="file.htm"` 这种无路径相对链接。
  - `_infer_exhibit_type(...)` 支持 `99.1` / `99.01` / `99` exhibit table labels，不再只依赖 `EX-99.1` 文本或 `ex991` 文件名。
- `configs/sec_tech_8k_earnings_full30_2026_2027.yaml`
  - 新增 full30 8-K earnings-release source config，覆盖 30 家、2026/2027 filing year、`SEC_PRIMARY_MIXED_WITH_8K_EARNINGS` 和 `company_authored_unaudited_sec_filing`。
- `scripts/cloud/sec_agent_interactive.sh`
  - mixed-8k wrapper 默认切到 full30 artifact paths。
- `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
  - `_select_prompt_context_rows(...)` 在 coverage/ledger rows 填满 prompt budget 前，优先为 requested company-authored 8-K context 预留最多 6 行，并优先按 ticker 覆盖。
  - recurring-quality overclaim sanitizer 覆盖 `decision_drivers.driver_claim/why_it_matters/caveat`。
- `scripts/cloud/sec_agent_interactive.py`
  - renderer 的 metric label 考虑 `metric_role`，例如 `percentage_rate` + growth-like metric 显示为增长率。
  - `_ledger_row_from_metric(...)` 不再用整句 context 直接判定金额 role；只有金额本身出现在 `increased/decreased by $X` 位置时才标为 `period_change_amount`。
- Tests:
  - selector 覆盖纯 `99.1 Press Release` + `q1fy27pr.htm`。
  - full30 config 覆盖 30 家。
  - evidence pack 即使被 coverage/ledger rows 填满，也必须保留 requested 8-K rows。
  - metric-role regression 覆盖 `$5.8 billion ... increased by 57%` 为 `total_value`，以及 `increased by $2.1 billion` 为 `period_change_amount`。
  - recurring-quality sanitizer 覆盖 `decision_drivers`。

## Cloud Artifact Results

Cloud environment:

- Path: `/root/autodl-tmp/FIN_Insight_Agent`
- Python: `/root/autodl-tmp/envs/sec-agent-cu128/bin/python`
- Hardware profile: RTX 5090 cloud node
- Secrets were only passed via process environment for immediate smoke execution and were not written to files or worklogs.

Full30 8-K rebuild results:

- `data/processed_private/manifests/sec_tech_8k_earnings_full30_manifest_2026_2027.jsonl`: `27` rows.
- `data/processed_private/chunks/sec_tech_8k_earnings_full30_chunks_2026_2027.jsonl`: `331` rows.
- `data/processed_private/evidence_objects/sec_tech_8k_earnings_full30_evidence_2026_2027.jsonl`: `331` rows.
- `data/processed_private/manifests/sec_tech_primary_mixed_with_8k_earnings_full30_manifest_fy2023_2027.jsonl`: `146` rows.
- `data/processed_private/evidence_objects/sec_tech_primary_mixed_with_8k_earnings_full30_evidence_fy2023_2027.jsonl`: `10628` rows.
- `data/processed_private/source_gaps/sec_tech_8k_earnings_full30_source_gaps_merged_2026_2027.jsonl`: `33` rows.

Coverage after selector fix:

- Successful 2026 8-K tickers: `AAPL, ADBE, ADP, AMAT, AMD, AMZN, AVGO, CAT, CRWD, CSCO, CVX, GOOGL, INTC, INTU, JNJ, JPM, LLY, META, MSFT, MU, NVDA, PANW, QCOM, SNOW, V, WMT, XOM`.
- Successful rows by year: `2026=27`.
- Gap reasons:
  - `no_8k_for_filing_year=30` for 2027, expected because current calendar date is 2026-05-25 and filing year 2027 8-Ks are not yet available.
  - `no_earnings_release_exhibit_for_item_2_02_8k=3` for remaining 2026 cases.

## Verification

Local:

```bash
python -m pytest tests/test_sec_agent_8k_earnings_source.py tests/test_sec_agent_10q_source_contract.py -q
python -m py_compile scripts/cloud/sec_agent_interactive.py scripts/run_sec_eval_synthesis_qwen9b_backend.py src/connectors/sec_edgar_connector.py
```

Result:

- `65 passed`.

Cloud:

```bash
/root/autodl-tmp/envs/sec-agent-cu128/bin/python -m pytest tests/test_sec_agent_8k_earnings_source.py tests/test_sec_agent_10q_source_contract.py -q
/root/autodl-tmp/envs/sec-agent-cu128/bin/python -m py_compile scripts/cloud/sec_agent_interactive.py scripts/run_sec_eval_synthesis_qwen9b_backend.py src/connectors/sec_edgar_connector.py
```

Result:

- `65 passed`.

Final real mixed 8-K DeepSeek smoke:

- Prompt: `结合最新10-Q和8-K业绩新闻稿，比较NVDA、AMD、MSFT的AI相关业务表现和管理层解释，注明8-K证据边界`
- Run root: `eval/sec_cases/outputs/interactive_sec_agent/20260525_150644_6226dc940d`
- Report: `reports/quality/sec_mixed_8k_full30_smoke_nvda_amd_msft_final_20260525.md`
- Gates: `ok=True`, `pass=12`, `fail=[]`.
- Coverage: `complete=True`, `primary_complete=True`, `support={'medium': 5}`.
- Ledger rows: `77`.
- Context rows: `120`.
- Evidence-pack check:
  - `qwen/input_output.md` contains `8K_EARNINGS::MSFT::...`, `8K_EARNINGS::NVDA::...`, and `8K_EARNINGS::AMD::...`.
  - Final answer cited `MSFT 2026 8-K earnings release Exhibit 99.1 (company-authored unaudited)` and `NVDA 2026 8-K earnings release (company-authored unaudited)` while preserving 10-K/10-Q ledger authority.
- Metric-role check:
  - AMD `Data Center net revenue of $5.8 billion` is now `data_center_revenue::total_value::qtd`.
  - AMD `57%` remains `data_center_revenue::percentage_rate::qtd`.

## Remaining Limitations

- 2027 8-K coverage is unavailable by date, not a parser failure.
- 2026 still has 3 companies with no selected earnings-release exhibit; these should be inspected case by case before claiming full 30/30 8-K support.
- 8-K values are still company-authored unaudited management material. They can support explanation and management commentary, but must not replace audited 10-K or reviewed 10-Q ledger facts.
- The cloud project directory is not a Git repository on the new node; Git hygiene remains local-first, with cloud used for artifact build and smoke validation.

## Next Step

- Inspect the 3 remaining 2026 8-K gaps to decide whether they are true source absences, non-standard exhibit labels, or source-policy exclusions.
- After that, run one broader full30 mixed-8k prompt cohort instead of only NVDA/AMD/MSFT, so source-tier reservation and renderer behavior are tested outside the AI semiconductor/cloud cluster.

## Safety Notes

- No API keys, passwords, or cloud credentials were written to this document.
- Raw SEC HTML/exhibit files, processed private evidence, BM25 indexes, and cloud-run reports remain generated/private artifacts and should not be staged by default.
