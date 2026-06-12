# 259 公开数据源 key 配置与 live smoke

## Prompt

用户提供 Census、BEA、FRED、DART、BLS、FDA/openFDA、OpenFIGI、EIA 等免费/公开 API key，要求本地保存，后续不要重复索要，并继续推进 P0-P3 数据接入。

## Decision

本轮只把 key 存入本地 `.env` 并接入脚本加载流程；不把密钥、原始响应或付费/商业源写入仓库。

执行边界：

- `.env` 是本地忽略文件，只记录变量名，不进入 Git。
- access plan 和 probe manifest 只记录 `env_var`、`env_present`、脱敏 URL、行数和样例字段。
- P2 先做 key-backed bounded smoke，不直接提升为主线 collector。
- EDINET key 仍缺，JP EDINET 继续保留为 P2 auth gap。

## Work Completed

- 新增 `scripts/data_expansion/env_loader.py`，为数据扩容脚本提供本地 `.env` 加载。
- 更新 `scripts/data_expansion/build_public_source_access_plan.py`：
  - 支持 `.env` 加载。
  - 将 BEA、Census、EIA、FRED API、DART、BLS、OpenFIGI 纳入 live probe 支持面。
  - access-plan summary 只输出 loaded env key names。
- 更新 `scripts/data_expansion/probe_public_source_access.py`：
  - 支持 query param、JSON body、HTTP header 三种 key 注入方式。
  - 输出 URL 对 key 参数脱敏；header/body key 不写入 probe manifest。
  - 新增 BEA、Census、EIA、FRED API、DART、BLS、OpenFIGI parser/smoke profile。
- 更新 `scripts/industry/10_download_industry_source_snapshot.py`，让现有行业数据脚本也能读取本地 `.env`。
- 新增 probe key 脱敏回归测试。
- 刷新 P0-P3 access plan、P1/P2/optional-key probe manifest。

## Results

P0 access plan：

- source count：`32`
- phase counts：P1 `20`，P2 `6`，P3 `5`，deferred `1`
- registry errors：`0`
- live probe supported count：`15`
- available required P2 key envs：
  - `BEA_API_KEY`
  - `CENSUS_API_KEY`
  - `DART_API_KEY`
  - `EIA_API_KEY`
  - `FRED_API_KEY`
- missing required P2 key envs：
  - `EDINET_API_KEY`
- optional key envs present：
  - `BLS_API_KEY`
  - `OPENFDA_API_KEY`
  - `OPENFIGI_API_KEY`

P1 no-key / no-key-limited live smoke：

- candidate count：`10`
- passed：`10/10`
- passed sources：`bls_public_api`、`clinicaltrials_api`、`fdic_bankfind_api`、`fred_graph_csv`、`gleif_api`、`nhtsa_vpic_api`、`openalex_api`、`openfda_api`、`openfigi_api`、`sec_edgar_apis`

P2 key-backed live smoke：

- candidate count：`5`
- passed：`5/5`
- passed sources：`bea_data_api`、`census_data_api`、`eia_open_data`、`fred_api`、`kr_dart_openapi`
- sample sanity：
  - EIA latest period sample：`2026-05`
  - FRED FEDFUNDS latest observation sample：`2026-05-01`
  - DART sample company：Samsung Electronics / `00126380`

Optional key smoke：

- candidate count：`3`
- passed：`3/3`
- passed sources：`bls_public_api`、`openfda_api`、`openfigi_api`

## Validation

- `python scripts/data_expansion/build_public_source_access_plan.py` -> pass
- `python scripts/data_expansion/probe_public_source_access.py --allow-failures --timeout-s 30` -> P1 `10/10` pass
- `python scripts/data_expansion/probe_public_source_access.py --phase-filter P2 --allow-failures --timeout-s 30 --output data/manifests/public_source_access_probe_p2_v0_1.jsonl --summary-output data/manifests/public_source_access_probe_p2_summary_v0_1.json` -> P2 `5/5` pass
- `python scripts/data_expansion/probe_public_source_access.py --source-id-filter bls_public_api,openfigi_api,openfda_api --phase-filter P1 --allow-failures --timeout-s 30 --output data/manifests/public_source_access_probe_optional_keys_v0_1.jsonl --summary-output data/manifests/public_source_access_probe_optional_keys_summary_v0_1.json` -> optional `3/3` pass
- `python -m pytest tests/test_public_source_access_plan.py tests/test_industry_source_snapshot.py tests/test_market_industry_expansion_manifests.py` -> `7 passed`
- `git diff --check` -> pass
- `.env` value scan over `scripts/`、`tests/`、`configs/`、`docs/`、`data/manifests/` -> `NO_SECRET_VALUE_HITS`

## Follow-up

- 用户如需 JP EDINET 官方 API 路径，需要补 `EDINET_API_KEY`。
- 下一步应把通过 smoke 的源分成两条 collector 线：
  - macro/industry collector：FRED API、BLS、BEA、Census、EIA、FDIC。
  - identity/product/disclosure collector：DART、GLEIF、OpenFIGI、openFDA、ClinicalTrials.gov、NHTSA vPIC。
- Product/sales 研究仍应优先从 company-reported product operating metrics 和 official product status 抽取；openFDA/NHTSA/ClinicalTrials 只能作为产品状态和监管/使用背景，不能替代公司销量或收入事实。
