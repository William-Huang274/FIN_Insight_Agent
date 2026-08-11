# 22. Source Route Attempt Ledger 与产品族证据硬化计划

更新时间：2026-06-22

## 背景

16-21 阶段已经把 600+ 公司 L1-L3 source lane、exact-slot matrix、source-role closeout、Product-KPI diagnostic 和 R16 深修跑通。但上一轮暴露了一个更根本的问题：**“没进 runtime”不能等同于“公开源没有”。**

典型风险：

- DECK 这类公司披露了 HOKA / UGG brand net sales，但当前 Product-KPI route/parser 没吃到。
- NVDA / AMD / Intel / Google TPU 这类产品竞争判断需要产品规格、代际提升、benchmark、客户部署 proxy，而不是只有 product revenue / ASP / shipment。
- ASML / Tokyo Electron / Hon Hai / MSFT 公开披露了系统出货量、业务 mix、云指标、RPO 等经营指标，但不能硬塞进 Product-KPI exact。
- L3 source-role 中，fetch failed / parser failed / credential missing 不能被写成 final public-source boundary。

因此，R17 的目标不是继续堆网页，而是把 `source discovery -> fetch -> parse -> verify -> promote/reject -> closeout` 变成可审计流水线，阻止 parser/source-route 漏吃被误判为公开源边界。

## 核心原则

1. 任何 gap 不能直接从“没进库”推导成“公开源没有”，必须先证明 source route 跑过、parser 吃过、verifier 判过。
2. L1/L2/L3 proxy 可以进入 evidence graph，但不能绕过 authority gate 成为产品销售、ASP、份额、库存、sell-through、backlog 等 exact 事实。
3. 产品数据不再等同于 Product-KPI exact。产品族证据拆成五类：
   - `financial_product_kpi`：公司披露的产品/品牌/产品线收入、出货、ASP、backlog。
   - `technical_product_spec`：产品参数、架构、功耗、性能、互联、内存、发布时间。
   - `competitive_benchmark`：官方 benchmark、MLPerf/SPEC、可信第三方实测。
   - `deployment_proxy`：客户集群、云实例、OEM 配置、公开订单/采购、数据中心部署。
   - `ecosystem_proxy`：CUDA/ROCm/TPU software stack、开发者生态、package/repo/docs、marketplace。
4. Known-public canary 必须防止回归：如果公开披露已知存在但 runtime 没吃到，只能标为 `route_or_parser_debt`，不能 closeout 成 company-undisclosed gap。
5. 剩余 gap 的 closeout 必须说明 ladder attempts、fetch/parser/verifier 状态、是否需要 credential、是否需要商业 tracker、是否不适用。

## R17 执行分解

### R17-0 SourceRouteAttemptLedger 基线

已开始实现：

- 新增 `scripts/data_expansion/build_r17_source_route_attempt_ledger.py`。
- 输出：
  - `data/manifests/source_route_attempt_ledger_v0_1.jsonl`
  - `data/manifests/source_route_attempt_ledger_summary_v0_1.json`
  - `docs/internal/vnext_20260610/vertical_lanes/r17_source_route_attempt_ledger.zh-CN.md`
- 新增测试：`tests/test_r17_source_route_attempt_ledger.py`。

当前 R17 状态：

- `row_count=718`
- `source_role_exact_gap=108`
- `product_kpi_gap_or_ready=603`
- `known_public_canary=7`
- `unclassified_count=0`
- `action_required_count=303`
- `known_public_current_contract_failure_count=0`
- `known_public_new_contract_required_count=0`
- Product-KPI closeout 已因 DECK 修复从 `product_kpi_exact_ready=172` / `product_kpi_gap=369` 更新为 `product_kpi_exact_ready=173` / `product_kpi_gap=368`。

这里的 `action_required` 不是失败隐藏，而是下一轮修复入口。

已完成 current-contract canary 修复：

- `DECK`：SEC archive 直接下载被 SEC automated-tool policy 拦截，本轮改走公司 IR 官方 FY2025 press release route。
- 新增 `scripts/data_expansion/build_r17_known_public_product_kpi_repair_rows.py`，从官方 IR HTML 解析 UGG / HOKA / Other brands FY2025 brand net sales。
- 输出 `data/manifests/r17_known_public_product_kpi_repair_runtime_rows_v0_1.jsonl`，并接入 closeout / diagnostic / runtime source context store 默认输入。
- R17 ledger 中 DECK canary 现在为 `canary_covered`。

已完成 new-contract canary 最小真实 runtime 接入：

- 新增 `scripts/data_expansion/build_r17_product_family_evidence_rows.py`。
- 从本地官方快照解析 `24` 条 runtime rows：
  - `NVDA`：`10` 条 H100/GB200 technical product spec、`2` 条 GB200 benchmark proxy、`1` 条 Hopper -> Blackwell generation edge、`2` 条 xAI Colossus customer deployment proxy、`1` 条 Spectrum-X ecosystem deployment context。
  - `MSFT`：`1` 条 Azure FY2025 revenue / growth cloud operating metric。
  - `ASML`：`4` 条 FY2025 system sales units / EUV / DUV / metrology and inspection operating metrics。
  - `8035.T`：`1` 条 Tokyo Electron FY2025 Field Solutions sales operating metric。
  - `2317.TW`：`1` 条 FY2025 total revenue operating metric、`1` 条 Cloud and Networking Products Q4 business mix rank。
- 输出：
  - `data/manifests/r17_product_family_evidence_runtime_rows_v0_1.jsonl`
  - `data/manifests/r17_product_family_evidence_summary_v0_1.json`
  - `docs/internal/vnext_20260610/vertical_lanes/r17_product_family_evidence.zh-CN.md`
- 新 runtime rows 已接入 `RuntimeSourceContextStore` 默认路径，并修复 selector priority，使 `technical_product_spec` / `customer_deployment_proxy` / `product_benchmark_proxy` / `product_generation_edge` / `product_ecosystem_deployment_context` 不会被普通产品页 context 挤出预算。
- Runtime scope smoke 覆盖 `NVDA/MSFT/ASML/8035.T/2317.TW` 时，新 manifest 的 `24/24` 条 rows 均可进入 bundle：`8` 条 L1 operating metric，`16` 条 L2 product/spec/deployment/benchmark/context。
- R17 ledger 中 6 个 new-contract canary 现在均为 `canary_covered`，`known_public_new_contract_required_count=0`。

通过条件：

- `unclassified_count=0`
- `fetch_failed` / `parser_failed` / `credential_required` 不允许被算成 final public boundary。
- DECK 这类 current-contract known-public canary 若未被 Product-KPI runtime 覆盖，必须显示为 `current_contract_route_or_parser_failure`。
- NVDA product spec / deployment proxy、MSFT cloud operating metric、ASML/TEL semicap operating metric、Hon Hai business mix 等 current schema 未覆盖项，必须显示为 `new_contract_required` 或 reroute debt，不能伪装成 Product-KPI gap 已闭合。

### R17-1 产品族证据合同扩展

已新增最小 runtime contract：

- `ProductSpecSlot`
- `ProductGenerationEdge`
- `ProductBenchmarkProxy`
- `CustomerDeploymentProxy`
- `ProductEcosystemContext`
- `IndustryOperatingMetricSlot`

本轮未把 `CloudInstanceAvailabilityProxy` / `OEMConfigurationProxy` 做成全行业 adapter；它们仍属于下一轮产品族 route 扩展项。但 R17 已先用官方可验证的 NVDA/xAI/GB200/ASML/TEL/MSFT/Hon Hai canary 建立 contract 和 gate，避免已知公开事实继续被误写成 Product-KPI gap。

通过条件：

- 这些 row 只能支持产品竞争、需求 proxy、生态采用和技术路线判断。
- 不允许推断未披露收入、销量、ASP、份额、库存、sell-through。
- Memo/Verifier 必须能区分 `financial_product_kpi` 和 `technical_product_spec` / `deployment_proxy`。

### R17-2 Source Ladder 与 canary gate

每个 gap 必须按 source ladder 记录 attempt：

- L1：SEC / 20-F / 6-K / local exchange / company IR annual report / earnings release / exhibit / PDF table / HTML table。
- L2：official product page / datasheet / whitepaper / developer docs / regulator API / official technical post。
- L3：customer deployment / cloud instance / OEM config / marketplace / public procurement / careers / benchmark / app store / GitHub/npm/PyPI/HuggingFace。

Known-public canary 初版：

- DECK：HOKA / UGG brand net sales。
- NVDA：H100 / Blackwell / GB200 official specs。
- NVDA：official customer deployment proxy。
- MSFT：Azure / cloud / RPO operating metrics。
- ASML：EUV / DUV / system units / installed base。
- 8035.T：SPE / field solutions / application mix。
- 2317.TW：cloud/networking business mix / AI server exposure。

通过条件：

- canary 全部进入 `covered`、`rerouted_ready` 或明确 `new_contract_required`。
- current-contract canary 不允许停留在 final boundary。

### R17-3 High-ROI parser/source-route 修复

优先修：

1. DECK 类 earnings release / 8-K exhibit / 10-K brand table parser。
2. NVDA/AMD/Intel/Google TPU official spec / datasheet / whitepaper parser。
3. NVDA/xAI、cloud instance、OEM config、server SKU 这类 deployment/channel proxy parser。
4. ASML/TEL/Renesas/Delta/Hon Hai 等 non-US IR PDF / local exchange / annual report table parser。
5. MSFT/SaaS/cloud RPO、ARR、remaining performance obligations、usage/pricing/status page industry operating slots。

通过条件：

- 可结构化 row 必须有 `value/spec/unit/period/product/source_url/citation` 或对应 source-role 的最小字段。
- 无 exact 值的产品页只能进入 spec/taxonomy/context，不得进入 financial KPI。
- 修复后重跑 R17 ledger，current-contract canary failure 必须下降。

### R17-4 ProductFamilyLaneRegistry 回灌

把新增证据合同挂到 product family：

- GPU/accelerator：spec、generation、benchmark、deployment、cloud instance、OEM/server config。
- CPU/server：core/thread、memory channel、PCIe、TDP、server share proxy、benchmark。
- Semicap：system units、installed base、tool category、service revenue、application mix。
- SaaS/cloud：ARR/RPO/remaining obligation、pricing、status、marketplace、developer artifacts。
- Auto/EV：model specs、deliveries、registrations、NHTSA/recall、battery/range、charging。

通过条件：

- Research Lead 能按 product family 选择 source route。
- Product/Technology Specialist 能拿到 spec/deployment/benchmark rows，而不是只看到财务表摘要。
- Verifier 能阻止 proxy 冒充 exact financial KPI。

### R17-5 Full-chain 接入前门控

接 full-chain 前必须满足：

- R17 ledger `unclassified_count=0`。
- current-contract canary failure 为 0，或明确记录为 parser blocker。
- new-contract canary 已有 runtime contract 和至少一个 deterministic parser smoke。
- closeout 中 `fetch_failed` / `parser_failed` 不再算 final public boundary。
- Memo 输出能把“产品规格/代际/部署 proxy/财务 KPI/商业 tracker gap”分清。

## 禁止事项

- 禁止把官方产品页、新闻、客户部署、渠道 SKU、招聘、专利、论文直接写成产品收入、销量、份额或 ASP。
- 禁止把 fetch failed、blocked、parser failed 写成 public-source exhausted。
- 禁止因 Product-KPI exact 缺失而忽略 technical spec / deployment proxy / operating metric 的研究价值。
- 禁止用 weak fallback 填满矩阵后宣称完成。

## 当前下一步

1. 修 `fetch_failed` 仍被 closeout 为 public exhausted 的 `4` 条 source-role route。
2. 继续把 `action_required_count=303` 拆成可执行 source-route/parser debt：`route_or_parser_debt=160`、`reroute_required=139`、`source_route_retry_required=4`。
3. 将 `CloudInstanceAvailabilityProxy` / `OEMConfigurationProxy` / 更多官方 benchmark route 纳入 ProductFamilyLaneRegistry 的 family-scoped adapters。
4. 在 full-chain case 中验证 Product/Technology Specialist 能实际利用 R17 rows 做产品规格、代际、客户部署和行业 operating metric 分析，而不是只暴露缺口。
