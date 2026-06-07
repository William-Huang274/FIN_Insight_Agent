# 250 Evidence Fusion Selector Source Family Bundles

日期：2026-06-07

## Prompt

承接 `249` 后继续按 `expanded_universe_retrieval_agent_framework_v0_1.zh-CN.md` 的下一步推进：更新 Evidence Fusion Selector，让不同 Specialist 看到不同 source-family bundle，并保持 Milvus typed semantic rows 的补召回边界。

## Work Completed

- 在 `build_agent_data_view(...)` 输出中新增 `source_family_bundle`：
  - schema：`sec_agent_source_family_bundle_v0.1`。
  - 记录 `allowed_source_families`、`available_source_families`、`selected_source_families`、`row_counts_by_source_family`。
  - 显式列出 `context_only_source_families`、`exact_value_authority_source_families` 和 `forbidden_claim_scopes`。
- 保持原 Specialist 数据分流边界：
  - Fundamental：只接 SEC filing / ledger source family。
  - Market-Valuation：只接 `market_snapshot`。
  - Industry/Supply-Chain：接 `industry_snapshot` + `relationship_graph`。
  - Risk：接 SEC + market + industry，但继续排除 relationship graph rows。
- 为 `milvus_semantic` rows 增加 bounded-row 标记：
  - `semantic_supplement=true`
  - `semantic_route_role=semantic_recall_supplement`
  - `semantic_claim_scope=filing_semantic_recall_supplement_only`
  - `exact_value_authority=false`
  - 保留 typed `vector_kind` / `vector_kinds`。
- 将 `source_family_bundle` 透传到 Specialist request、LLM prompt payload、repair payload 和 route summary，避免 data-view 有边界但实际 prompt 丢失。

## Verification

- 本地语法检查：
  - `python -m py_compile src\sec_agent\multi_agent_runtime.py src\sec_agent\specialist_llm.py`
  - 结果：pass
- 本地 targeted tests：
  - `python -m pytest tests\test_multi_agent_specialist_llm.py tests\test_multi_agent_universe_relationship.py -q`
  - 结果：`49 passed`
  - `python -m pytest tests\test_multi_agent_operator_permissions.py -q`
  - 结果：`19 passed`
- 云端同步：
  - 已同步 `src/sec_agent/multi_agent_runtime.py`、`src/sec_agent/specialist_llm.py`、`tests/test_multi_agent_specialist_llm.py` 到 `/root/autodl-tmp/fin_agent_sp500_stage/workspace`。
  - 云端 `PYTHONPATH=src /root/miniconda3/bin/python -m py_compile ...` pass。
  - 云端 inline source-family bundle contract check pass：`remote_source_family_bundle_check: pass`。

## Decision

- Architecture 下一步第 4 项“更新 Evidence Fusion Selector，让不同 Specialist 看到不同 source-family bundle”已完成到 data-view / Specialist prompt contract。
- 本轮没有改变 route 激活策略，也没有把 Milvus 设为默认 full-chain 主路径；Milvus rows 只作为 typed SEC semantic recall supplement，可辅助找材料，不能单独证明 exact value。

## Next

1. 更新 Research Lead prompt/skill，让它按成本和问题类型选择 route。
2. 更新 Specialist skill vNext，特别是 Market 和 Industry 的 source boundary。
3. 先跑 A1-A5 分层 gate，不直接跑 full-chain。
