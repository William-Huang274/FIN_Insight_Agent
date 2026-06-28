# 339 R12 Source Coverage Gate Matrix

日期：2026-06-16

## 问题

用户指出：L1/L2/L3 的骨架和 parser/gate 已经有了，但真实接入时如何保证覆盖面足够、不会漏源，不能继续靠人工记忆和事后聊天复盘。

本轮目标是把“应接哪些公开源、接入后是否真的被解析和分给专家”变成可运行的 coverage gate，而不是直接开始盲目爬站。

## 完成工作

1. 新增 `src/sec_agent/source_coverage_gate.py`：
   - 定义行业 required source matrix。
   - 支持 `registry` 阶段审计 source capability rows。
   - 支持 `runtime_case` 阶段审计实际 evidence/context rows、parser-backed rows、entity binding rows 和 specialist-visible rows。
   - 对 L2/L3/L4 exact-authority promotion 做硬失败。

2. 首批行业覆盖：
   - `generic_public_research`
   - `semiconductors_hardware`
   - `consumer_electronics`
   - `software_saas`
   - `healthcare_pharma_medtech`
   - `auto_mobility`
   - `financials_banks`
   - `energy_utilities`
   - `retail_cpg`

3. 每个 requirement 输出：
   - `source_ids`
   - `layer_ids`
   - `specialist_roles`
   - `ready_source_count`
   - `observed_row_count`
   - `parser_row_count`
   - `entity_bound_row_count`
   - `specialist_visible_row_count`
   - `gap_type`
   - `claim_boundary`
   - `next_action`

4. 新增 CLI：
   - `scripts/data_expansion/audit_source_coverage_gate.py`
   - 默认读取 `data/manifests/source_layer_capability_audit_v0_1.jsonl`
   - 输出：
     - `data/manifests/source_coverage_gate_summary_v0_1.json`
     - `docs/internal/vnext_20260610/source_coverage_gate.zh-CN.md`

5. 新增 deterministic tests：
   - registry gap 暴露；
   - runtime case 要求 observed/parser/binding/visible rows；
   - `source_class` 到 canonical `source_id` 的 alias 归一；
   - L2/L3 exact-authority violation 失败；
   - 多行业 matrix summary。

## 当前 Gate 结果

已运行：

```powershell
python scripts\data_expansion\audit_source_coverage_gate.py --strict
```

结果：

- status: `gap`
- industry schemas: `9`
- requirements: `65`
- gap requirements: `35`
- fail requirements: `0`
- exact-authority violations: `0`

主要 registry gap：

- 官方产品页 / company-reported product operating metrics 仍是 parser / mapping not runtime ready。
- NHTSA、ClinicalTrials、openFDA、FDIC、EIA/FRED、OpenAlex、PatentsView 仍需要 entity/product/asset/topic resolver。
- 电商、渠道报价、App Store、developer ecosystem、公开 tender/order、招聘、review/ranking 仍需要 runtime route / parser / resolver。

## 验证结果

已运行：

```powershell
python -m py_compile src\sec_agent\source_coverage_gate.py scripts\data_expansion\audit_source_coverage_gate.py
python -m pytest tests\test_source_coverage_gate.py -q
python scripts\data_expansion\audit_source_coverage_gate.py --strict
```

结果：

- `py_compile` pass
- `tests/test_source_coverage_gate.py`: `5 passed`
- coverage gate strict validation pass；整体 status 为 `gap`，这是当前未完成源接入的预期结果。

## 当前边界

1. 这不是 crawler/backfill；它是 source 接入前后的机器验收门控。
2. Registry gap 不等于公开源不可得，只表示当前 runtime 还没达到 route/parser/binding/visible 的要求。
3. 后续每个真实 adapter / parser / resolver 做完，都必须让对应 requirement 从 gap 收敛到 runtime-case pass，或保留为明确 bounded/commercial/source gap。
4. 本轮没有跑 DeepSeek full-chain。

## 下一步

1. 按 coverage gate 的 gap 排序做 high-priority source-specific adapters/backfill：
   - company product / product operating metrics；
   - supplier/customer official news 和 mainstream news 的真实站点覆盖；
   - developer ecosystem / channel / ecommerce / tender / hiring / review proxy；
   - NHTSA / ClinicalTrials / openFDA / FDIC / EIA/FRED / OpenAlex / PatentsView resolvers。
2. 每完成一个 adapter，跑 `runtime_case` coverage gate，要求 observed/parser/entity/specialist-visible rows 通过。
3. 再进入 1-2 个 full-chain case，检查 Research Lead targeted repair、specialist analysis 和 Memo surface 是否真的使用这些新增 rows。
