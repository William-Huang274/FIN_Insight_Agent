# 334 R12 L2/L3 Parser Backfill Foundation

日期：2026-06-15

## 问题

前一轮已经让系统知道 L2/L3/L4 源层能力和 role-visible distribution，但 web repair 仍主要产出页面 snapshot 与少量 lead rows。这样下游 ClaimCards 和 Memo Writer 看到的仍是“页面到达”，不是可分析的 bounded facts，导致产品、市场 proxy、供应链、资本上下文仍然浅。

本轮目标是先补 L2/L3 parser/backfill foundation：抓到 allowed public web snapshot 后，至少要把网页/JSON/HTML table 中的可用信息转成结构化 context/proxy rows；同时保留严格边界，不能把这些 rows 提权成产品销量、订单、份额、ASP、库存或 sell-through 事实。

## 完成工作

1. 新增 public web context parser：
   - `src/sec_agent/public_web_context_parser.py`
   - 新增 `parse_public_web_context_rows(...)`。
   - 输出 schema：`finsight_public_web_context_parser_v0_1`。
   - 输出字段包括：
     - `source_specific_parser=public_web_context_parser_v0_1`
     - `bounded_structured_context=true`
     - `parser_status=source_specific_context_parser_pass`
     - `structured_fact_status=bounded_context_fact_materialized`
     - `structured_context_type`
     - `structured_context_summary`
     - `parser_claim_boundary`
     - `exact_value_authority=false`
     - `can_support_company_exact_fact=false`

2. Parser 覆盖的 foundation 类型：
   - SEC submissions JSON：解析 issuer identity、filing presence、filing date、accession context。
   - HTML tables：解析 allowed-source table rows，作为 bounded context/proxy rows。
   - 官方产品页：解析 product taxonomy、product/spec sentences、model/spec/capacity/throughput 等上下文。
   - market proxy：解析 market/share/rank/download/review/shipment/registration/price/channel/vendor 句子和表格。
   - supply-chain：解析 supplier/customer/partner/channel/contract/order/tender/award 句子。
   - capital/ownership：解析 debt/note/maturity/coupon/offering/13F/13D/13G/Form 3/4/5/holder/ownership 句子。
   - issuer/local filing：解析 annual report、20-F、6-K、10-K、10-Q、8-K、regulator、exchange、presentation 等 source context。

3. 接入 targeted web repair：
   - `src/sec_agent/official_issuer_repair.py`
   - `_execute_probe(...)` fetch 成功后调用 parser。
   - `context_rows` 现在包含 snapshot row、lead rows、structured parser rows。
   - `artifact_refs[]` 记录 `structured_context_row_count`。
   - `official_context_summaries[]` 记录 `structured_context_types`。

4. L3 source-class route 放开到计划层和执行层：
   - `src/sec_agent/lead_supervision.py`
   - `src/sec_agent/official_issuer_repair.py`
   - `market_proxy` allowlist 新增：
     - `official_app_store_or_marketplace`
     - `ecommerce_major_platform`
     - `developer_ecosystem_snapshot`
     - `public_tender_or_contract_portal`
     - `job_posting_snapshot`
     - `channel_pricing_snapshot`
     - `platform_review_or_ranking_snapshot`
   - `build_targeted_repair_plan(...)` 会保留 `market_source_class`，并从 gaps 中读取 app/ecommerce/developer/GitHub/npm/PyPI/HuggingFace/tender/order/hiring/channel/review URLs。

5. 新增 URL-derived L3 public API adapter smoke：
   - `official_issuer_repair` 对 `developer_ecosystem_snapshot` URL 做 source-specific expansion：
     - GitHub repo URL -> `https://api.github.com/repos/{owner}/{repo}`
     - npm package URL -> `https://registry.npmjs.org/{package}`
     - PyPI project URL -> `https://pypi.org/pypi/{package}/json`
     - HuggingFace model URL -> `https://huggingface.co/api/models/{model_id}`
   - 对 `official_app_store_or_marketplace` URL 做 expansion：
     - App Store `/id...` URL -> `https://itunes.apple.com/lookup?id=...`
   - parser 可把 GitHub stars/forks/pushed_at、npm latest/modified、PyPI version/summary、HuggingFace downloads/likes/pipeline、App Store rating/rating_count/version/release_date 转成 L3 bounded proxy rows。

6. Research Lead ClaimCard 消费 parser rows：
   - `src/sec_agent/langgraph_orchestrator.py`
   - `_lead_targeted_repair_context_claims(...)` 现在会读取 `structured_context_summary` / `fact_value`。
   - ClaimCard 文本增加 `bounded parsed context includes ...`，让下游知道补回来的不只是“网页到了”，而是有 bounded parsed facts。

## 验证结果

已运行：

```powershell
python -m py_compile src\sec_agent\public_web_context_parser.py src\sec_agent\official_issuer_repair.py src\sec_agent\lead_supervision.py src\sec_agent\langgraph_orchestrator.py
python -m pytest tests\test_public_web_gap_repair.py tests\test_runtime_bridge_contracts.py tests\test_source_layer_capability_audit.py -q
python -m pytest tests\test_multi_agent_real_llm_chain_eval.py tests\test_multi_agent_specialist_llm.py tests\test_multi_agent_contracts.py -q
python scripts\eval_multi_agent\smoke_public_web_gap_repair.py --mode fixture --output-dir reports\quality\public_web_gap_repair_smoke\l2_l3_parser_fixture
python scripts\eval_multi_agent\smoke_public_web_gap_repair.py --mode fixture --output-dir reports\quality\public_web_gap_repair_smoke\l3_adapter_fixture
python scripts\eval_multi_agent\smoke_public_web_gap_repair.py --mode fixture --output-dir reports\quality\public_web_gap_repair_smoke\l3_adapter_fixture_after_identity_fix
python scripts\data_expansion\audit_source_layer_capabilities.py --strict
```

结果：

- Public web repair + runtime adapter tests：`21 passed`
- Source-layer / multi-agent eval / Specialist / contracts：`127 passed`
- Public web repair fixture smoke：`pass`
  - `attempted_count=1`
  - `success_count=5`
  - `bounded_gap_count=0`
- Live GitHub + App Store adapter smoke：`pass`
  - `attempted_count=2`
  - `success_count=6`
  - `bounded_gap_count=0`
  - `structured_types=['app_store_marketplace_context', 'developer_ecosystem_context']`
  - `source_layers=['L3']`
- Source-layer audit strict：`pass`

中途 live smoke 暴露过一个真实 parser bug：GitHub API 的 `name` 字段被通用 JSON parser 误识别为 `official_issuer_identity_context`。已修复为只有带 `filings` / CIK 的官方披露 JSON 才生成 issuer identity row，复跑 live smoke 后仅保留 developer/app marketplace L3 context。

## 当前边界

1. 这不是全量 L2/L3 adapter closeout。GitHub/npm/PyPI/HuggingFace/App Store 已有 URL-derived API smoke；其他真实站点级 adapters / resolvers 仍待补：
   - 电商/渠道报价；
   - 公开招投标 / 公开订单；
   - 招聘；
   - 平台评论 / 下载排名；
   - 主流财经新闻和行业协会数据。
2. 当前 parser rows 只能支撑 bounded context/proxy，不支持公司 exact product KPI、真实销量、份额、订单、库存、sell-through、ASP。
3. 本轮没有跑 DeepSeek full-chain。下一轮如跑 case，应先看 targeted repair execution 是否真的出现 parser rows，再看 Memo 是否使用这些 rows 形成更有信息密度的产品/市场/供应链判断。

## 下一步

1. 为 2-3 个高价值 L3 route 做 source-specific live adapter smoke：
   - App Store / marketplace；
   - developer ecosystem；
   - channel/ecommerce offer 或 public tender/order。
2. 把 adapter 输出统一成当前 `bounded_structured_context` row contract。
3. 再跑 1 个非 SEC issuer 或产品/市场缺口明显的 full-chain case，观察 Research Lead targeted repair、Specialist selector、Memo Writer 是否真正使用 parser rows，而不是只写缺口边界。
