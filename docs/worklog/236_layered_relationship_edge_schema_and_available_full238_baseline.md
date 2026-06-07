# 236 Layered Relationship Edge Schema And Available Full238 Baseline

## Prompt

用户要求开始下一阶段分层数据源扩容，并提示当前 238 家 SEC 关系边抽取可以考虑直接做 500 家。

## Reasoning And Decision

- 直接“抽 500 家关系边”需要先有 500 家对应 SEC evidence。当前本地稳定 evidence 资产仍是 full238，因此本轮把 `target_company_count=500` 作为目标池标签和脚本合同，不把 current-only 结果冒充完整 500 家抽取。
- 先做 R1/R2：关系边 schema、置信度规则、实体归一基础、候选抽取、确定性 verifier 和质量 audit。只有这些通过后，扩容数据才能进入 R3/R4/R5 和 typed vector。
- 抽取策略选择高精度优先，宁可少抽，也不能把地区、泛称客户、行业暴露写成真实客户/供应商。

## Work Completed

- 新增配置：
  - `configs/data_sources/universe_tiers.yaml`
  - `configs/data_sources/source_families.yaml`
  - `configs/data_sources/ingestion_profiles.yaml`
  - `configs/data_sources/universe_company_overrides_v0_1.json`
  - `configs/entities/entity_alias_rules_v0_1.json`
  - `configs/relationships/relationship_edge_schema_v0_1.json`
  - `configs/relationships/relationship_confidence_rubric_v0_1.json`
- 新增代码：
  - `src/sec_agent/entities/entity_resolution.py`
  - `src/sec_agent/relationships/edge_schema.py`
  - `src/sec_agent/relationships/sec_edge_extractor.py`
  - `src/sec_agent/relationships/relationship_verifier.py`
- 新增脚本：
  - `scripts/data_expansion/build_universe_tiers.py`
  - `scripts/data_expansion/audit_universe_tiers.py`
  - `scripts/relationships/extract_relationship_edge_candidates.py`
  - `scripts/relationships/verify_relationship_edges.py`
  - `scripts/relationships/audit_relationship_edge_quality.py`
- 新增测试：
  - `tests/test_entity_resolution_contract.py`
  - `tests/test_relationship_edge_schema.py`
  - `tests/test_relationship_edge_extractor.py`
- 更新执行文档和 master checklist，记录首轮 R1/R2 结果。

## Result And Evidence

- E1 manifest smoke：
  - Tier 0 current full238：`238` companies。
  - missing CIK：`0`。
  - `CTRA` 通过本地 SEC evidence 确认为 `Coterra Energy Inc.`，并写入小型 override。
- R1/R2 available full238 baseline：
  - 输入：`Z:\FIN_Insight_Agent_artifacts\evidence_objects\sector_depth_full238_us_v0_5_mixed_with_8k_evidence_fy2023_2027.jsonl`
  - evidence rows：`91,708`
  - candidates：`818`
  - verified：`768`
  - rejected：`50`
  - verified relation counts：`contractual_relationship=320`、`partner_channel=440`、`direct_customer_supplier=8`
  - confidence counts：`high=38`、`medium=730`
  - rejected reason counts：`direct_customer_supplier_target_is_generic_or_geographic=25`、`evidence_missing_contract_language=9`、`evidence_missing_partner_language=16`
- Target gates repaired during the run:
  - 地区列表不能生成 direct customer。
  - `U.S`、`China-based`、`Table of Contents Online sales`、`Major customer One of our end customers`、`Certain Key` 不能进入 verified direct edge。
  - 只有精确实体匹配才能升 `high`，包含匹配最多为 `medium`。

Verification commands:

```powershell
python -m pytest tests\test_entity_resolution_contract.py tests\test_relationship_edge_schema.py tests\test_relationship_edge_extractor.py -q
python -m compileall src\sec_agent\relationships src\sec_agent\entities scripts\relationships
python scripts\data_expansion\audit_universe_tiers.py --manifest eval\sec_cases\outputs\data_expansion_smoke\universe_tiers\tier0_full238_manifest.jsonl --expected-count 238 --summary-output eval\sec_cases\outputs\data_expansion_smoke\universe_tiers\tier0_audit_v0_1.json
python scripts\relationships\audit_relationship_edge_quality.py --edges-path eval\sec_cases\outputs\relationship_edges_available_full_v0_4_gate\verified_v0_1.jsonl --summary-output eval\sec_cases\outputs\relationship_edges_available_full_v0_4_gate\quality_v0_1.json --min-verified-edges 1
```

## Follow-Up

- 已在后续同日补做 S&P 500 constituent 下载和 Tier 1 manifest 构建：`503` 个 S&P 500 symbols、`500` 个唯一 CIK，与 current full238 合并后为 `505` 家，`0` missing CIK。
- 下载和清洗 Tier 1 SEC evidence 后，才能跑真正 500 家关系边抽取。
- 继续 R3：扩展 external counterparty alias registry，处理 `WT Microelectronics Co., Ltd`、`ODP`、`Janssen Biotech, Inc`、`Genentech, Inc` 等目标实体。
- 继续 R4/R5：把 verified relationship edges 接入 Relationship Router、Industry Specialist 和 runtime ledger。

## Safety Notes

- 没有写入 API key、SSH 密码或私有 token。
- 本轮生成的 eval 输出保留在 `eval/sec_cases/outputs/...`，不作为 Git 跟踪对象。
- 当前关系边 evidence text 来自本地 SEC evidence，只用于本地诊断和后续 pipeline 输入；公开仓库提交应只包含脚本、合同和小测试，不提交大规模 generated edge JSONL。
