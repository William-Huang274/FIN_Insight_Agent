# 338 R12 Role-Visible Entity-Binding Selector Wiring

日期：2026-06-16

## 问题

337 已经让 L2/L3 public web parser rows 具备 `entity_binding`、issuer/product/counterparty binding status 和 `source_entity_role`。但如果这些字段没有进入 role-visible bounded rows、prompt distribution 和 source-layer selected sources，下游专家仍然看不到或用不上，最终 memo 还是会退回“数据不足”的写法。

本轮目标是把 entity-binding metadata 真实接到 Specialist 输入面，并修复 industry/supply-chain specialist 漏看 `live_public_web_context` 的问题。

## 完成工作

1. 扩展 `multi_agent_runtime._bounded_row`：
   - 保留 public web parser row 的：
     - `source_class`
     - `structured_context_type`
     - `product_family`
     - `product_or_segment`
     - `issuer_binding_status`
     - `product_binding_status`
     - `counterparty_binding_status`
     - `entity_binding_claim_boundary`
     - `source_entity_role`
     - compact `entity_binding`

2. 扩展 bounded row / prompt row distribution：
   - `by_source_entity_role`
   - `by_issuer_binding_status`
   - `by_product_binding_status`
   - `by_counterparty_binding_status`

3. 修复 industry/supply-chain specialist 可见性：
   - `_specialist_required_source_families("industry_supply_chain_analyst")` 加入 `live_public_web_context`。
   - industry/supply-chain row filter 纳入 `live_public_web_context`。
   - industry/supply-chain activation signal count 纳入 live web context rows。

4. 扩展 `role_evidence_selector` / Specialist prompt source-layer compact：
   - `selected_sources[]` 保留 `source_entity_role` 和三类 binding status。

5. 新增 deterministic tests：
   - `test_specialist_request_preserves_public_web_entity_binding_metadata`
   - 扩展 `test_specialist_prompt_includes_compact_source_layer_distribution`

## 验证结果

已运行：

```powershell
python -m py_compile src\sec_agent\multi_agent_runtime.py src\sec_agent\specialist_llm.py src\sec_agent\role_evidence_selector.py
python -m pytest tests\test_multi_agent_specialist_llm.py::test_specialist_request_preserves_public_web_entity_binding_metadata tests\test_multi_agent_specialist_llm.py::test_specialist_prompt_includes_compact_source_layer_distribution -q
python -m pytest tests\test_multi_agent_specialist_llm.py tests\test_multi_agent_contracts.py tests\test_multi_agent_real_llm_chain_eval.py tests\test_runtime_bridge_contracts.py tests\test_source_layer_capability_audit.py tests\test_public_web_gap_repair.py -q
python scripts\data_expansion\audit_source_layer_capabilities.py --strict
```

结果：

- Entity-binding selector targeted tests：`2 passed`
- Related regression：`155 passed`
- Source-layer audit strict：`pass`

## 当前边界

1. 这只保证 public web parser row 能进入 Specialist 输入并保留 binding metadata；不代表 Specialist LLM 一定会高质量使用这些 rows。
2. 这不是完整 entity resolver，也没有解决 issuer alias / product alias / counterparty graph 的全量匹配。
3. 这不改变 source authority：L2/L3 context rows 仍不能证明销量、份额、ASP、库存、订单量、shipment 或产品级收入。
4. 本轮未运行 DeepSeek full-chain。

## 下一步

1. 做 high-priority source-specific adapters/backfill，把更多真实 L2/L3 rows 写入 runtime evidence graph。
2. 跑一个 targeted full-chain case，检查 Lead targeted repair、selector、Specialist 和 Memo 是否真的利用 `entity_binding`，而不是只把它当成审计字段。
3. 根据 case 结果再决定是否需要把 entity-binding 规则升级到 D3 Entity Master / KG edge 层。
