# 245 SEC CompanyFacts / Submissions 和非美 Profile 下载状态

## Prompt

用户要求先把 SEC CompanyFacts / Submissions 下载成 raw / staging fact rows，同时继续推进非美 profile-specific downloader / parser，重点覆盖 DART、MOPS、EDINET、HKEX、CNINFO。

## Decision

- SEC 结构化事实可以直接按官方 API materialize，因为 Tier1 + Tier2 SEC 公司池已经稳定，且 CompanyFacts / Submissions 是公司披露事实的结构化补充。
- 非美监管和交易所路径不能用公司 IR fallback 冒充。DART / EDINET 需要官方 API key；MOPS / HKEX / CNINFO 暂不猜参数，先把阻塞原因写入 profile、队列和 metadata，后续按 profile 分别实现。
- 当前结果只进入 staging，不合并到主线 exact-value ledger、BM25、ObjectBM25 或 Milvus。

## Work Completed

- 新增 SEC 结构化事实下载和归一化脚本：
  - `scripts/data_expansion/download_sec_structured_facts.py`
- 新增测试：
  - `tests/test_sec_structured_facts_download.py`
- 更新非美公开披露 profile：
  - `configs/data_sources/global_public_disclosure_profiles_v0_1.yaml`
- 更新非美公开披露下载器：
  - `scripts/data_expansion/download_global_public_disclosures.py`
- 更新非美下载任务测试：
  - `tests/test_global_public_disclosure_download_tasks.py`
- 更新执行文档：
  - `docs/architecture/layered_data_source_expansion_execution_plan.zh-CN.md`

## Results

SEC CompanyFacts / Submissions：

- 输入：`data/manifests/structured_financial_fact_source_plan_v0_1.jsonl`
- 公司：`588`
- CompanyFacts raw payload：`588`
- Submissions raw payload：`588`
- CompanyFacts staging fact rows：`2,790,261`
- Submissions filing rows：`6,605`
- 年份：`2023`、`2024`、`2025`
- 表单：`10-K`、`10-Q`、`20-F`、`40-F`
- 表单分布：`10-K=988,200`、`10-Q=1,752,865`、`20-F=44,890`、`40-F=4,306`
- 输出：
  - `data/staging/structured_financial_facts/sec_companyfacts_financial_fact_rows_v0_1.jsonl`
  - `data/staging/structured_financial_facts/sec_submissions_filing_rows_v0_1.jsonl`
  - `data/manifests/sec_structured_facts_download_summary_v0_1.json`

非美 profile-specific smoke：

- 队列：`69` 个任务，覆盖 `15` 家非美主披露公司。
- EU company IR：`3` 个任务真实下载。
- DART / EDINET：`48` 个任务标记为 `blocked_requires_official_api_key`，分别需要 `DART_API_KEY` / `EDINET_API_KEY`。
- MOPS / HKEX / CNINFO：`18` 个任务标记为 `profile_specific_scaffold_pending`。
- 输出：
  - `data/manifests/tier2_global_public_disclosure_download_tasks_v0_2.jsonl`
  - `data/manifests/tier2_global_public_disclosure_download_tasks_summary_v0_2.json`
  - `data/manifests/tier2_global_public_disclosure_profile_specific_smoke_v0_1.jsonl`
  - `data/manifests/tier2_global_public_disclosure_profile_specific_smoke_summary_v0_1.json`

## Gates

- `python -m pytest tests\test_sec_structured_facts_download.py tests\test_structured_financial_fact_source_plan.py -q`：`7 passed`
- `python -m pytest tests\test_global_public_disclosure_download_tasks.py tests\test_global_public_disclosure_source_plan.py tests\test_global_public_disclosure_source_plan_audit.py -q`：`18 passed`
- `python -m compileall scripts\data_expansion\download_sec_structured_facts.py scripts\data_expansion\download_global_public_disclosures.py`：pass

## Remaining Gaps

- SEC staging fact rows 尚未进入 exact-value ledger；下一步需要做 metric ontology、period/duplicate resolution、currency/value-role gate 和 smoke query。
- DART / EDINET 需要官方 API key 后才能实现真实 regulator-first 下载。
- MOPS / HKEX / CNINFO 需要分别补 profile-specific 检索参数、发行人代码映射、报告类型过滤、旧公告过滤和 checksum metadata。
- 非美官方报告 parser / chunk / table-boundary audit 尚未完成，因此非美结构化事实不能进入 ledger 或主线检索。

## Safety Notes

- 未写入任何 API key、SSH 密码、私有 token 或云端凭据。
- raw SEC JSON 和 staging fact rows 属于 generated/private data，不应直接提交到公开仓库。
