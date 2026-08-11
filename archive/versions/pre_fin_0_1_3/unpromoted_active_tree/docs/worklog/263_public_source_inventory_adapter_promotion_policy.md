# 263 公开数据源 promotion policy / inventory adapter

## Prompt

用户要求继续往下做，在 mapping / endpoint gates 已经下载并处理好目标 universe 数据后，进入 runtime 前的 source-specific promotion policy 和 inventory adapter 阶段。

## Decision

本轮不把公开源 rows 直接接进 agent runtime 默认路径。先新增机器可读 promotion policy 和 adapter，把 mapping / endpoint gate 产物分成：

- 可进入 feature-flagged source inventory / resolver registry 的高置信 identifier rows。
- 可进入 bounded context-only evidence 的公开宏观上下文 rows。
- 必须继续补 resolver、parser、route allowlist 或 alias override 的 rejected candidates / gap rows。

关键边界：

- `runtime_eligible=true` 只表示可进入 feature-flagged source inventory 或 resolver surface，不等于可以证明研报结论。
- `bounded_evidence_eligible=true` 当前只给 Census 宏观上下文 rows。
- `exact_value_authority=0`，公开源不覆盖 SEC filing / exact-value ledger。
- DART corp_code 只作为 Korean issuer disclosure locator；DART filing metadata 仍不能作为主披露正文证据。
- ClinicalTrials.gov、openFDA、NHTSA、FDIC、EIA rows 暂不提升，等 sponsor/product/make/entity/route resolver。

## Work Completed

- 新增 `configs/data_sources/public_source_promotion_policy_v0_1.yaml`。
- 新增 `scripts/data_expansion/build_public_source_inventory_adapter.py`。
- 新增 `tests/test_public_source_inventory_adapter.py`。
- 基于上一轮真实产物：
  - `data/processed_private/public_sources/public_source_mapping_endpoint_gate_v0_1/mapping_candidates.jsonl`
  - `data/processed_private/public_sources/public_source_mapping_endpoint_gate_v0_1/endpoint_records.jsonl`
  - `data/processed_private/public_sources/public_source_mapping_endpoint_gate_v0_1/source_gaps.jsonl`
- 生成 tracked adapter manifests：
  - `data/manifests/public_source_inventory_adapter_v0_1.jsonl`
  - `data/manifests/public_source_inventory_adapter_summary_v0_1.json`
- 生成 ignored processed artifacts：
  - `data/processed_private/public_sources/public_source_inventory_adapter_v0_1/public_source_inventory_rows.jsonl`
  - `data/processed_private/public_sources/public_source_inventory_adapter_v0_1/public_source_gap_rows.jsonl`
  - `data/processed_private/public_sources/public_source_inventory_adapter_v0_1/rejected_public_source_candidates.jsonl`
  - `data/processed_private/public_sources/public_source_inventory_adapter_v0_1/metadata.json`

## Result

输入：

- mapping candidates：`1,219`
- endpoint records：`127,712`
- source gaps：`213`

输出：

- promoted inventory rows：`1,103`
- runtime-eligible rows：`1,103`
- resolver-eligible rows：`1,100`
- bounded context-only evidence rows：`3`
- exact-value authority rows：`0`
- rejected candidates：`127,828`
- gap rows：`220`，其中 source policy blockers `7`
- required next gates：`dart_document_parser_before_primary_disclosure_evidence`、`gleif_alias_and_relationship_resolver_before_relationship_claims`

可提升的范围：

- SEC CIK identity：`588` rows，issuer identity / SEC join key only。
- OpenFIGI security identifier：`14` rows，FIGI / security join key only。
- GLEIF high-confidence LEI：`495` rows，legal entity identifier candidate only；仍有 alias / relationship resolver gap。
- DART corp_code：`3` rows，Korean disclosure locator only；DART document parser 未完成。
- Census macro context：`3` rows，可作为 `industry_snapshot` runtime source family 的 bounded context-only rows。

保留为 gap / rejected：

- FDIC：`4,287` candidates/records held，`66` gap rows；需要 bank institution/subsidiary -> listed issuer resolver。
- ClinicalTrials.gov：`2,006` candidates/records held，`9` gap rows；需要 sponsor/product/condition resolver。
- openFDA：`417` candidates/records held，`54` gap rows；需要 product/sponsor endpoint resolver。
- NHTSA：`255` candidates/records held，`4` gap rows；需要 make/model/year issuer resolver。
- EIA：`1,000` endpoint rows held，`1` source-level blocker；需要 route allowlist 和 entity/asset mapping。
- DART：bulk corp-code and filing metadata rows rejected for runtime evidence until document parser exists。

## Validation

- `python -m py_compile scripts\data_expansion\build_public_source_inventory_adapter.py` -> pass
- `python -m pytest tests\test_public_source_inventory_adapter.py` -> `4 passed`
- `python scripts\data_expansion\build_public_source_inventory_adapter.py` -> pass，生成 `1,103` promoted inventory rows / `220` gap rows / `127,828` rejected candidates

## Follow-up

- Wire `public_source_inventory_adapter_summary_v0_1.json` and `public_source_inventory_rows.jsonl` into `build_project_inventory` behind an explicit feature flag.
- Add runtime tests proving public identifier rows cannot enter bounded Specialist evidence as financial facts.
- Add manual alias overrides for high-value GLEIF / ClinicalTrials.gov / openFDA / NHTSA misses.
- Build DART document/package downloader/parser before promoting Korean filings as primary disclosure evidence.
- Add EIA route allowlist and entity/asset mapping before promoting EIA endpoint rows as industry context.
