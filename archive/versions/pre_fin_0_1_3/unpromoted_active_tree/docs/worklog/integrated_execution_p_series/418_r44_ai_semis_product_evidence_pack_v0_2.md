# 418 R44 AI/Semis ProductEvidencePack v0.2

## Prompt

用户要求在跑 full-chain 前先把产品层六块做实：Product Profile、Product Spec / Architecture、CustomerDeployment / Adoption、Product Performance Proxy、Product-KPI Exact、Product Relationship Graph；可以先从 AI/Semis 行业开始，但必须保证这个行业的公司有 depth，而不是宽泛数据绑定。

## Decision

继续保持 `Product-KPI exact` 严格，不把产品页、新闻、部署、benchmark、渠道、OpenAlex 等 proxy 冒充为销量、收入、ASP、份额、backlog 或订单金额。新增一个更大的 `ProductEvidencePack v0.2`，把 specs、deployment/adoption、performance proxy、exact KPI 和 relationship graph 分层提供给 Research Lead / Product Specialist。

关键边界：

- route gate / seed / not-materialized 只能作为 repair 指令，不算 evidence。
- 产品规格、客户部署、渠道、供应链、developer ecosystem、OpenAlex 等可支撑 bounded thesis driver。
- exact KPI 仍必须有 `value/unit/period/product/citation`。
- CustomerDeployment 不再作为孤立维度，而是产品图谱里的 `Company/Product -> customer/channel/deployment/order/supply-chain context` 边。

## Work Completed

- 新增 `src/sec_agent/product_intelligence_depth.py`。
  - 读取 AI/Semis V1 route gate、PIG v0.1 company pack、L2/L3 source-row 文件。
  - 输出逐公司 `ProductEvidencePack v0.2`。
  - 分层记录 `product_profile`、`product_spec_architecture`、`customer_deployment_adoption`、`product_performance_proxy`、`product_kpi_exact`、`product_relationship_graph`。
  - 生成 strict / bounded depth gate 和 gap queue。
- 新增 `scripts/data_expansion/build_ai_semis_product_evidence_pack_v0_2.py`。
- 新增 `tests/test_ai_semis_product_evidence_pack.py`。
  - 覆盖 route-only 不提权、产品页不能冒充 Product-KPI exact、deployment/proxy context-only、explicit depth pack 可被 Research Lead / Product Specialist 消费。
- 接入 runtime：
  - `src/sec_agent/supervising_analyst.py` 的 `product_bridge_pack` 新增 `product_evidence_pack_ref` 和 depth coverage。
  - `src/sec_agent/multi_agent_runtime.py` 的 Product Specialist data view 新增 `product_evidence_pack_ref` 和 role-context policy。

## Artifacts

- `data/manifests/ai_semis_product_evidence_pack_v0_2.jsonl`
- `data/manifests/ai_semis_product_depth_gate_v0_2.json`
- `data/manifests/ai_semis_product_depth_gap_queue_v0_2.jsonl`

## Result

真实 V1 AI/Semis 构建结果：

- company count：`53`
- main depth gate：`pass`
- `depth_status_counts`：`pass=45`，`pass_with_public_boundary=8`
- strict depth：`pass=45`，`needs_strict_depth_followup=8`
- layer coverage：
  - `product_profile`：`53/53 detailed_profile_ready`
  - `product_spec_architecture`：`23/53 evidence_ready`
  - `customer_deployment_adoption`：`41/53 evidence_ready`
  - `product_performance_proxy`：`25/53 evidence_ready`
  - `product_kpi_exact`：`40/53 exact_or_operating_metric_ready`
  - `product_relationship_graph`：`52/53 evidence_ready`

8 家 `pass_with_public_boundary`：

- `005930.KS` Samsung Electronics
- `2308.TW` Delta Electronics
- `2317.TW` Hon Hai
- `ACLS` Axcelis
- `ETN` Eaton
- `LSCC` Lattice Semiconductor
- `MCHP` Microchip
- `TXN` Texas Instruments

这些公司不是没有产品包，而是没到 strict depth。典型缺口是官方规格/技术页 parser row、developer/research/channel proxy、customer deployment/adoption row、Product-KPI exact row 或 parser-backed relationship edge。LSCC 目前只有详细产品/业务 profile + exact/operating KPI，官方产品页 requests 返回 403，需要后续 browser-rendered fetch 或替代官方文档源处理。

## Verification

- `python -m py_compile src/sec_agent/product_intelligence_depth.py scripts/data_expansion/build_ai_semis_product_evidence_pack_v0_2.py src/sec_agent/supervising_analyst.py src/sec_agent/multi_agent_runtime.py`
- `python -m pytest tests/test_ai_semis_product_evidence_pack.py -q`：`5 passed`
- `python -m pytest tests/test_ai_semis_product_evidence_pack.py tests/test_product_intelligence_graph.py tests/test_product_spec_pack.py tests/test_supervising_analyst_pack.py tests/test_multi_agent_langgraph_routing.py -q`：`45 passed`
- `python scripts/data_expansion/build_ai_semis_product_evidence_pack_v0_2.py --strict`：main depth gate `pass`
- artifact autoload smoke：`NVDA pass/pass evidence_role_count=5`，`LSCC pass_with_public_boundary/needs_strict_depth_followup evidence_role_count=2`

未跑 LLM full-chain；本轮只做 full-chain 前的产品证据包和 runtime 消费面。

## Follow-up

- 针对 8 家 strict follow-up 公司，继续跑 browser-rendered official spec / architecture locator、customer deployment/partner case-study adapter、developer/research/channel proxy adapter。
- 把 v0.2 ProductEvidencePack 的 layer/gap 信息进入后续 LeadReviewCheckpoint / TargetedRepairPlan 的 source-specific repair queue。
