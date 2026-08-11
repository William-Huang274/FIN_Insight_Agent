# 337 R12 L2/L3 Parser Entity-Binding Metadata

日期：2026-06-16

## 问题

L2/L3 public web parser rows 进入 evidence graph 后，如果只有 `structured_context_summary`，Specialist 仍然难以判断这条 context 应该绑定 issuer、product、counterparty 还是只作为市场/行业事件背景。更大的风险是把“Research Lead repair plan 以某 ticker 发起”误读成“网页快照已经验证该 issuer”。

本轮目标是先补一个轻量 entity-binding metadata 层，让每条 parser row 暴露绑定状态和边界，帮助后续 selector / Specialist 分配证据，但不做完整 Entity Master，也不改变 exact authority。

## 完成工作

1. 扩展 `src/sec_agent/public_web_context_parser.py`：
   - 每条 parser row 增加：
     - `entity_binding`
     - `issuer_binding_status`
     - `product_binding_status`
     - `counterparty_binding_status`
     - `entity_binding_claim_boundary`
   - `entity_binding` 内包含：
     - `issuer_ticker`
     - `issuer_matched_terms`
     - `product_matched_terms`
     - `counterparty_matched_terms`
     - `source_entity_role`

2. 新增 deterministic binding 状态：
   - `issuer_mentioned_in_snapshot`
   - `company_domain_bound`
   - `repair_plan_ticker_bound_unverified_in_snapshot`
   - `product_mentioned_in_snapshot`
   - `counterparty_mentioned_in_snapshot`
   - `relationship_context_candidate`
   - `counterparty_keyword_context_candidate`
   - `not_bound`

3. 新增 source role 分类：
   - `supplier_customer_or_partner_context`
   - `product_or_platform_context`
   - `trusted_event_or_industry_context`
   - `channel_offer_proxy_context`
   - `public_proxy_signal_context`
   - `public_order_or_procurement_lead`

4. 补测试：
   - 主流新闻 fixture 不出现 ticker 时，行应标为 `repair_plan_ticker_bound_unverified_in_snapshot`，不能冒充快照中 issuer 已验证。
   - 供应链官方新闻 fixture 出现 Dell 时，行应标为 `issuer_mentioned_in_snapshot`，并作为 `relationship_context_candidate`。

## 验证结果

已运行：

```powershell
python -m py_compile src\sec_agent\public_web_context_parser.py
python -m pytest tests\test_public_web_gap_repair.py -q
python -m pytest tests\test_runtime_bridge_contracts.py tests\test_source_layer_capability_audit.py tests\test_multi_agent_real_llm_chain_eval.py tests\test_multi_agent_specialist_llm.py tests\test_multi_agent_contracts.py -q
python scripts\data_expansion\audit_source_layer_capabilities.py --strict
```

结果：

- Public web repair tests：`14 passed`
- Runtime / source-layer / multi-agent eval / Specialist / contracts：`140 passed`
- Source-layer audit strict：`pass`

## 当前边界

1. 这不是完整 entity resolver，也没有接 D3 Entity / Security Master。
2. 绑定状态只用于 routing / selector / Specialist 消费 context，不代表 exact issuer fact、product KPI、shipment、sales、market share 或 order-volume authority。
3. 真实实体绑定仍需要后续做 issuer alias、product alias、counterparty graph、domain ownership、page title / JSON-LD name / document citation 的综合 resolver。
4. 本轮未运行 DeepSeek full-chain。

## 下一步

1. 把 `entity_binding` 接入 role-specific evidence selector，让 Product / Market / Supply-chain specialist 按绑定状态和 source role 分配 parser rows。
2. 做高优先级 source-specific adapters/backfill：company product pages、mainstream news、supplier/customer official news、channel/ecommerce、developer ecosystem、tenders/orders、hiring、rankings/reviews。
3. 跑 1 个 targeted full-chain case，检查 Research Lead targeted repair -> parser rows -> selector -> Specialist -> Memo 是否真实用到这些 L2/L3 context，而不是只暴露缺口。
