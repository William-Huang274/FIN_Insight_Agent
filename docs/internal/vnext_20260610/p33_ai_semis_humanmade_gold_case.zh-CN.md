# P33 AI/Semis Humanmade Gold Case v0.2

日期：2026-07-06

状态：`humanmade_gold_case_v0_2_polished_memo_updated_no_paid_run`

## 1. 文档定位

本文档不是 agent 输出样例，也不是 Memo Writer 模板。它是一个人工 analyst 先做出来的 gold case，用来回答两个问题：

1. 如果人类投研分析师在公开数据前提下做这个 AI/Semis case，应该怎么拆问题、找证据、形成判断和写底稿。
2. 如果要让 agent 产出同等质量，Research Lead、specialist、JudgmentCard、ProductIntelligenceGraph、MemoLogicPlan、writer、verifier 和 Workbench 必须倒推成什么样。

本轮不跑 paid LLM，不跑 full-chain，不做模型对比。本文档建立人类研究尺子、source-backed workpaper v0.1，并把 polished memo 升级到 v0.2。

## 2. Gold Case 范围

研究对象不是“AI 需求强不强”这个宽泛问题，而是：

```text
AI workload / hyperscaler capex
 -> accelerator product capability / supply
 -> cloud/OEM/customer deployment
 -> server OEM revenue quality / margin bridge
 -> foundry / packaging / HBM / semicap read-through
 -> market expectation / price-in
 -> counter-thesis and what-would-change
```

核心公司/链条：

- Accelerator：NVDA、AMD、GOOGL TPU。
- Server OEM / integrator：DELL，并可扩展到 SMCI、HPE、ODM。
- Demand pool：MSFT、AMZN、GOOGL、META 等 hyperscaler capex。
- Foundry / equipment：TSM、ASML、AMAT、LRCX、KLAC。

本 v0.2 先聚焦 `NVDA / AMD / GOOGL TPU -> DELL AI server -> hyperscaler capex -> TSM/ASML/AMAT/LRCX read-through`。

## 3. Source Ledger

| Source | Authority role | 关键可用信息 | 能支持 | 不能外推 |
| --- | --- | --- | --- | --- |
| Dell FY26 Q4 8-K exhibit | issuer exact / operating disclosure | Dell 披露 FY26 全年 AI-optimized server orders、shipments、FY27 backlog，以及全年收入、现金流、资本返还 | AI server 订单/出货/积压是真实经营事件；DELL 已经有可量化 AI server demand | 不能直接证明 AI server 毛利率、GPU pass-through cost、客户集中度或每个客户订单 |
| Dell FY26 Q1 release | issuer exact / segment disclosure | ISG、Servers and Networking、Storage revenue；ISG operating income / margin | DELL ISG 财务桥的基准；AI server 增长应落到 ISG 收入/利润质量 | 不能单独拆 AI server margin，也不能证明 Blackwell 配置占比 |
| Dell + NVIDIA AI Factory / PowerEdge announcements | issuer official product / deployment surface | PowerEdge XE9680 支持 H200/B200；XE9712 是 GB200 NVL72 平台 | DELL 有具体 NVIDIA-powered AI server / rack 产品路径 | 不能证明收入、订单量、客户签约或利润率 |
| NVIDIA GB200 NVL72 official page | product architecture / technical fact | GB200 NVL72 为 36 Grace CPU + 72 Blackwell GPU，rack-scale NVLink domain，面向 trillion-parameter inference/training | NVDA 产品从 GPU 卡扩展到 rack-scale system，支持 supply bottleneck 和系统级定价能力判断 | 不能证明 NVDA SKU 收入、DELL 订单或客户采购量 |
| NVIDIA Q1 FY2027 IR page | issuer exact / segment revenue | NVIDIA 披露 record revenue 和 Data Center revenue；Data Center revenue 高速增长 | AI accelerator demand 已进入 NVDA 财报，不只是宏观叙事 | 不能拆到 B200/GB200/GB300 每个 SKU，不能证明 DELL 份额 |
| AMD MI300X official product page | product architecture / competitor spec | MI300X 有 192GB HBM3、5.3 TB/s bandwidth、CDNA3、FP8/FP16 等规格 | AMD 是真实替代/竞争路线，特别在 memory-heavy inference/training 场景 | 不能证明 AMD 市占、客户迁移规模或 NVDA 定价下行 |
| AMD MLPerf 6.0 blog / MLCommons results | performance proxy / benchmark context | AMD 新一代 MI355X 在若干 MLPerf inference 场景接近或部分超过 B200/B300，且强调 ROCm/scale-out | 支持 AMD 竞争力改善和软件栈进步的方向性判断 | 厂商 blog 不能替代独立采购决策；benchmark 不能直接外推出收入或份额 |
| Google Cloud TPU v6e docs | product architecture / cloud deployment surface | TPU v6e/Trillium 有官方规格：bf16/int8 compute、HBM、ICI、Pod size、all-reduce/network bandwidth | TPU 是 hyperscaler 自研 accelerator 的真实替代路线；GOOGL 内部/外部云可降低纯 NVIDIA 依赖 | 不能证明 TPU 对 NVDA 的实际替代比例或 GOOGL 内部采购节奏 |
| Google Cloud A4X GB200 blog | cloud deployment / adoption signal | Google Cloud A4X preview 使用 GB200 NVL72，并说明 B200/A4 与 GB200/A4X 的定位 | 证明 GB200 已进入 hyperscaler cloud product surface；同时体现云厂商既用 NVIDIA 也做 TPU | 不能证明购买金额、供货方收入或可用区域规模 |
| MSFT FY26 Q2/Q3 investor materials | hyperscaler capex / demand pool | capex、云/AI 收入增长、customer demand exceeding supply 等披露 | AI compute capex 是大规模真实需求池；可作为 upstream demand proxy | 不能直接传导到 NVDA/DELL 订单份额 |
| AMZN Q1 2026 results | hyperscaler / AWS demand pool | AWS sales and operating income growth | AWS AI/cloud demand context | 不能直接证明 AWS 买了多少 NVDA GPU 或 DELL server |
| Alphabet Q1 2026 release/call | hyperscaler capex / cloud growth / TPU context | CapEx、服务器/数据中心网络占比、Google Cloud revenue growth | GOOGL capex 和 cloud AI demand 是真实需求背景；服务器占比可连接 accelerator/server chain | 不能证明 NVDA vs TPU 采购拆分 |
| Meta Q1 2026 transcript | hyperscaler capex / risk | 2026 capex guidance raised to support future capacity and component pricing | AI infra demand pool 和 component price pressure | 不能直接证明供应商收入；也提示 capex digestion / overbuild 风险 |
| TSMC Q1 2026 release | foundry exact / advanced node | revenue、margin、advanced technology wafer revenue share；leading-edge process demand | advanced node / HPC/AI read-through；foundry 端有财务质量支撑 | 不能单独证明 NVDA/AMD/Apple/TPU 各客户占比 |
| ASML Q1 2026 release | semicap exact / lithography | net sales、gross margin、installed-base management、new/used lithography systems sold、2026 guide | EUV/DUV/installed-base read-through 和 semicap cycle 背景 | 不能直接把 AI capex 等同 ASML 订单；需区分 memory/foundry/logic/China exposure |
| AMAT Q2 FY26 release | semicap exact / equipment mix | revenue、gross margin、Semiconductor Systems segment, foundry/logic/DRAM/flash mix | WFE / foundry-logic / DRAM 和 AI packaging/equipment exposure | 不能替代 customer order backlog |
| LRCX Mar 2026 results | semicap exact / etch/deposition / memory | revenue、gross margin、operating margin；AI-driven demand management commentary | memory/HBM/foundry process equipment read-through | 不能证明每个 HBM / advanced packaging 订单 |
| MLCommons MLPerf | neutral benchmark methodology | 公开、同行可比较的 inference/training benchmark 框架、availability/category/closed/open division | 可作为产品能力/性能 proxy 的高质量公开基准 | 不可直接推导销量、ASP、份额或财务结果 |

## 4. Human Research Workflow

### 4.1 Research Lead 先拆问题，而不是先派 agent

合格的人类 Research Lead 会先写下 7 个必答问题：

1. AI capex 是否是真实需求池，还是 overbuild / digestion 风险？
2. NVDA 的产品代际、rack-scale 架构和软件生态是否仍构成供给瓶颈和定价能力？
3. AMD MI300/MI35x 与 Google TPU 能在哪些场景替代 NVIDIA，替代边界是什么？
4. DELL AI server 是高质量收入，还是 GPU pass-through 驱动的低毛利放量？
5. DELL 的 AI server 订单/出货/积压如何传导到 ISG revenue、gross margin、operating income、working capital 和 backlog conversion？
6. TSMC / ASML / AMAT / LRCX 哪些环节受益于 AI，哪些只是 broader semicap cycle？
7. 当前市场是否已经 price-in 这条链的好消息，什么证据会推翻判断？

这一步的输出不是 agent list，而是 `thesis_path`：

```text
initial_view:
  AI infra demand is real, but value capture differs sharply by layer.
  NVDA/foundry/semicap have stronger product/supply bottleneck evidence.
  DELL has strong AI server demand evidence, but margin-quality proof remains the key unresolved bridge.

must_answer:
  demand_pool, product_capability, customer_deployment, financial_quality, semicap_readthrough, price_in, counter_thesis

writer_order:
  summary -> thesis chain -> product/architecture -> deployment/customer -> financial quality -> semicap read-through -> market expectation -> counter-thesis -> what would change
```

### 4.2 Analyst 证据分层

强证据：

- issuer-reported orders、shipments、backlog、segment revenue、gross/operating margin、capex、cash flow、advanced node mix、equipment systems sold。
- official product specs、cloud instance docs、OEM official configurations。
- customer / partner official deployment announcement。

中等证据：

- official product page、IR deck、conference call commentary。
- MLPerf / benchmark results。
- official partner ecosystem announcement。

Proxy：

- hyperscaler capex as demand pool。
- market / industry snapshot。
- relationship graph peer/supplier/customer scope。
- channel availability、pricing、blog/customer case。

不可外推：

- capex pool 不能直接外推到 DELL/NVDA/TSM/ASML 收入份额。
- product spec 不能直接外推到收入、ASP、shipment。
- customer deployment case 不能直接外推到 total demand。
- relationship graph 不能直接当财务事实。
- benchmark 不能直接当市场份额。

## 5. Human Workpaper v0.1

### 5.1 核心判断

AI infrastructure demand is real, but the investment quality is not uniform across the chain.

目前公开证据更支持三件事：

1. hyperscaler / cloud capex 已经形成真实需求池；
2. accelerator 和 advanced semiconductor supply chain 的产品/供给瓶颈仍然较强；
3. server OEM 的收入机会真实存在，但利润质量必须单独验证。

换句话说，不能把 MSFT/AMZN/GOOGL/META 的 capex、NVDA 的 Blackwell/GB200 产品能力、DELL 的 AI server 订单、TSMC/ASML/AMAT/LRCX 的设备/先进制程需求简单合并成一句“AI 基建全链条都受益”。更好的写法是：

```text
AI demand pool 是真；
NVDA / TSMC / semicap 的供给瓶颈证据更硬；
DELL 的 AI server revenue tailwind 很强，但 margin quality 仍是核心问号；
AMD / TPU / custom silicon 是价格和份额的反证链；
capex digestion / export control / customer concentration / price-in 是主要风险。
```

### 5.2 Demand Pool：capex 支持真实需求，但不是订单分配

MSFT、Alphabet、Meta、Amazon 都有大额 AI / cloud / technical infrastructure capex 或云业务增长披露。Alphabet 披露 Q1 2026 capex 主要用于 technical infrastructure，且服务器约占 60%；Microsoft 披露 demand continues to exceed supply；Meta 上调 2026 capex 区间并提到 component pricing 和 future capacity；Amazon AWS 增长仍强。

判断：

- 这些证据足以支持 “AI compute demand pool exists”。
- 这些证据不足以证明 “DELL/NVDA/TSMC 各自拿到多少份额”。
- 对 DELL/NVDA 的传导必须通过 orders、shipments、backlog、cloud/OEM configuration、customer/deployment 或 supply-chain relationship 继续验证。

合格 agent 不能只写 “hyperscaler capex 强”。它必须追问：capex 进入的是 GPU、networking、data center construction、custom silicon、storage、power/cooling 还是 internal TPU？这些 capex 是否通过 DELL/SMCI/ODM 采购？是否已经被市场 price-in？

### 5.3 Product / Architecture：产品层可以判断，但不是 SKU revenue

NVDA GB200 NVL72 的关键不是单颗 GPU，而是 rack-scale architecture：36 Grace CPUs、72 Blackwell GPUs、large NVLink domain、liquid-cooled rack system。这意味着 NVDA 的竞争壁垒不只是芯片性能，还包括 system architecture、networking、software stack、deployment ecosystem。

AMD MI300X 官方规格显示它在 HBM capacity / bandwidth 和 FP8/FP16 compute 上具备真实竞争力。AMD 后续 MI35x / MLPerf 公开结果显示竞争不应被写成“没有 NVDA 就没法做 AI”。Google TPU v6e/Trillium 官方规格和 Google Cloud 文档说明 hyperscaler custom silicon 是长期替代/补充路线。

判断：

- NVDA 仍是主链，但 AMD/TPU 是真实反证，不是噪声。
- 产品分析不能因为没有 SKU revenue 就失败。规格、架构、系统形态、benchmark、cloud/OEM 配置和客户部署都可以支持 “product capability / adoption / substitution risk”。
- 但这些证据只能支撑产品竞争力和 adoption direction，不能直接写成 revenue/share/ASP。

### 5.4 Customer Deployment / Adoption：DELL 有产品路径，但客户层仍需更硬证据

Dell 披露 AI-optimized server orders / shipments / backlog，且官方产品和 AI Factory 路线支持 H200/B200/GB200 相关配置。Google Cloud A4X preview 说明 GB200 NVL72 已经进入 hyperscaler cloud product surface。Dell XE9712 / XE9680 等官方产品路径说明 server OEM 与 NVIDIA rack-scale 方案之间存在可追溯连接。

判断：

- DELL 的 AI server demand evidence 比一般 “AI 受益” 说法更硬，因为有 orders / shipments / backlog。
- 但 DELL 的客户部署质量仍需进一步拆：客户是谁、合同期、配置、GPU pass-through、服务/存储/networking attach、交付节奏、是否集中于少数大客户。
- 如果公开源只能拿到官方产品和总订单，memo 应写成 “AI server revenue demand strong, margin quality unresolved”，而不是 “AI server 高质量增长已证明”。

### 5.5 Financial Quality：DELL 的关键不是有没有收入，而是利润质量

Dell Q1 FY26 披露 ISG revenue、Servers and Networking revenue、ISG operating income / operating margin。FY26 Q4 8-K 披露全年 AI-optimized server orders、shipments 和 backlog。

这些证据足以回答：

- AI server 是 DELL 的真实 revenue tailwind；
- ISG 是 AI server 财务传导的主入口；
- DELL 整体现金流和资本返还能力不错。

但还不能充分回答：

- AI server gross margin 是否高于传统 server；
- GPU pass-through 成本是否稀释毛利；
- AI server backlog conversion 是否转化为 operating income；
- storage / services / networking attach 是否改善利润质量；
- AI server 客户集中度和 working capital 压力。

所以人类 analyst 的判断应是：

```text
DELL has strong AI server revenue visibility, but the investment-quality question is margin conversion.
The right bridge is not "AI server orders -> buy DELL";
it is "orders/backlog -> shipments -> ISG revenue -> gross/operating margin -> cash conversion -> working capital pressure".
```

### 5.6 Semicap / Foundry Read-through：要分层，不要 peer group 一锅端

TSMC Q1 2026 披露高收入、高毛利、advanced technology revenue share 和 leading-edge process demand。ASML 披露 Q1 2026 net sales、gross margin、new/used lithography systems sold、installed base management sales 和全年 sales/gross margin guide。AMAT 和 LRCX 披露 revenue、margin 和半导体设备/服务业务表现。

判断：

- Foundry / leading-edge demand 和 semicap revenue/margin 有公开 exact 支撑。
- 但 ASML、AMAT、LRCX、KLAC 的 read-through 机制不同：
  - ASML：EUV/DUV、installed base、China/export、bookings/backlog。
  - AMAT：deposition / materials engineering、foundry/logic/DRAM mix、advanced packaging。
  - LRCX：etch/deposition、memory/HBM、advanced packaging。
  - KLAC：process control / inspection / metrology。
- 不能用 “同属 semicap peer group” 当主证据。peer group 只能定义研究范围。

### 5.7 Market Expectation / Price-in：当前 v0.1 仍不足

公开数据足以支持业务链条，但 market price-in 还需要进一步补：

- valuation multiples、historical percentile、relative valuation；
- stock reaction to earnings/product/order news；
- 13F / ETF ownership / insider / short interest / options positioning；
- sector rotation / SOX / cloud capex basket / cross-asset signals。

因此 v0.1 不应给强烈买卖建议。它只能写成：

```text
The fundamental chain is directionally positive for AI infrastructure,
but market price-in and positioning need a separate capital-feedback pack before an investment recommendation.
```

### 5.8 Counter-thesis

必须写在主文，不是最后兜底：

1. Capex digestion：hyperscaler 可能过度建设，未来消化压力导致订单波动。
2. Margin dilution：server OEM 可能收入增长很快但毛利被 GPU pass-through 稀释。
3. Substitution：AMD、TPU、custom ASIC 可能限制 NVDA pricing power。
4. Supply bottleneck：HBM、CoWoS、先进封装、电力/冷却可能限制出货节奏。
5. Export / China：ASML、NVDA、部分 semicap 有政策风险。
6. Customer concentration：AI server / GPU cluster 大客户集中度可能很高。
7. Price-in：如果股价已提前反映高增长，基本面兑现不一定带来继续上行。

## 6. Polished Human Memo v0.2

### 6.1 Core view

AI infrastructure is a real investment cycle, but it should not be underwritten as a single "AI beneficiary basket". Public evidence supports a real demand pool, a strong accelerator and advanced-semiconductor supply chain, and a visible server-OEM revenue opportunity. It does not yet prove that every layer captures high-quality profit.

The current public-data conclusion is:

```text
Underwrite: AI compute demand, NVIDIA-led accelerator system demand, foundry / advanced packaging / selected semicap read-through.
Do not yet underwrite: Dell AI server growth as high-quality margin growth.
Keep as active counter-thesis: AMD / TPU substitution, capex digestion, export controls, server-OEM margin dilution, and market price-in.
```

The most important distinction is between `revenue visibility` and `profit quality`. Dell has unusually visible AI server demand through disclosed AI-optimized server orders, shipments and backlog. But the key investment question is whether that backlog converts into gross margin, operating margin, cash conversion and attach economics, rather than low-margin GPU pass-through revenue.

### 6.2 Demand pool: cloud capex proves demand, not supplier allocation

The hyperscaler evidence is strong enough to say the AI demand pool is real. Microsoft, Alphabet, Meta and Amazon all disclose large cloud / AI / technical infrastructure spending or cloud growth. Alphabet's Q1 2026 call states that capex was mainly technical infrastructure, with servers roughly 60% of the mix; Microsoft disclosed large capex and customer demand exceeding supply; Meta raised 2026 capex guidance and cited component pricing plus future capacity; AWS continued to grow revenue and operating income.

That supports a demand-pool judgment:

```text
AI compute capacity is being purchased, deployed and monetized at cloud scale.
```

It does not support a supplier-allocation judgment by itself:

```text
It does not tell us how much of the pool goes to NVIDIA GPUs, Google TPU, AMD accelerators, Dell servers, ODMs, networking, data-center construction, power/cooling, or storage.
```

So the analyst path should be: capex creates the pool; product and deployment evidence decide who captures it; financial evidence decides whether captured revenue becomes good profit; capital-feedback evidence decides whether the market has already priced it in.

### 6.3 Accelerator layer: NVIDIA is still the main system bottleneck, but substitution is real

NVIDIA's public product evidence is not just "better GPU". GB200 NVL72 is a rack-scale system architecture: 36 Grace CPUs, 72 Blackwell GPUs, rack-scale NVLink, liquid-cooled deployment, and a system-level path for trillion-parameter inference and training. This matters because the bottleneck is no longer only chip compute; it is the integrated accelerator, networking, software and deployment stack.

That supports a bounded positive judgment on NVIDIA:

```text
NVIDIA still has system-level leverage in the AI infrastructure chain, and Blackwell/GB200 strengthens the supply-bottleneck thesis.
```

But the counter-thesis cannot be ignored. AMD MI300X has official memory and bandwidth specifications that make it credible in memory-heavy workloads. AMD MLPerf disclosures and MLCommons results show that the competitive story is not static. Google TPU v6e / Trillium has official cloud documentation and makes internal accelerator substitution a structural issue for hyperscalers. Google also offers GB200-based cloud instances, so the right conclusion is not "TPU replaces NVIDIA" or "NVIDIA has no substitution risk"; it is:

```text
NVIDIA remains the main external accelerator system supplier, while AMD and TPU create workload-specific price, availability and bargaining-power pressure.
```

This is exactly where the product graph should help the memo: `GB200 -> deployed in cloud / OEM rack systems`, `TPU -> substitutes_for selected workloads`, `AMD MI300/MI35x -> competes_with memory-heavy inference/training`, and each edge must state what it can and cannot prove.

### 6.4 Dell layer: revenue visibility is strong; margin quality is unresolved

Dell is the clearest example of why product, customer deployment and financial bridge must be linked. Dell's FY26 disclosure gives unusually concrete AI server operating evidence: AI-optimized server orders exceeded `$64B`, shipments exceeded `$25B`, and FY27 starting backlog was about `$43B`. That is not a generic AI proxy. It is issuer-disclosed demand visibility.

Dell's Q1 FY26 segment data shows the financial bridge entry point: ISG revenue was about `$10.3B`, Servers and Networking was about `$6.3B`, and ISG operating income was about `$998M`, or roughly `9.7%` of ISG revenue. The question is therefore not whether AI server demand exists. It is whether AI server mix improves or dilutes ISG profitability.

The current Dell judgment should be:

```text
Dell has strong AI server revenue visibility, but public evidence has not yet proven high-quality AI server margin conversion.
```

What must be proven next:

- AI server gross margin versus traditional server margin;
- GPU pass-through cost and whether Dell keeps enough value-add;
- storage / networking / services attach rate;
- backlog conversion into shipments and operating income;
- customer concentration and payment / working-capital pressure.

This is the point where a weak memo becomes a search summary. A strong memo should not stop at "Dell has AI orders". It should explain the bridge:

```text
AI server orders -> backlog -> shipments -> ISG revenue -> gross margin / operating margin -> cash conversion / working capital.
```

If the public source cannot fill that bridge, the answer is not "cannot judge Dell". The answer is a bounded judgment: Dell's revenue tailwind is supported; Dell's margin-quality thesis remains unproven and should be monitored through ISG margin, backlog conversion, attach economics and inventory / receivables.

### 6.5 Foundry and semicap: AI read-through exists, but mechanisms differ by company

TSMC's public financials support advanced-node and HPC/AI demand more directly than a generic semicap peer-group argument. TSMC reported high revenue and gross margin, and advanced technologies accounted for a large share of wafer revenue. This supports the view that AI accelerator demand is visible at the foundry layer, although it does not disclose customer-level allocation across NVIDIA, AMD, Apple, Google or others.

ASML, AMAT and LRCX should not be grouped as one undifferentiated "semicap basket". Their mechanisms differ:

- ASML: EUV/DUV lithography, installed-base management, China/export exposure, bookings/backlog cycle.
- AMAT: materials engineering, deposition, foundry/logic, DRAM/flash, advanced packaging exposure.
- LRCX: etch/deposition, memory/HBM, advanced packaging and process-intensity exposure.
- KLAC, if included in the next round: process control / inspection / metrology.

The correct semicap judgment is:

```text
AI demand supports leading-edge foundry, HBM / memory intensity, advanced packaging and process complexity, but each equipment company needs its own mechanism and order/backlog evidence.
```

So ASML revenue and margin strength cannot by itself prove AI-specific EUV orders. AMAT and LRCX revenue/margin cannot by itself prove direct AI order capture. But together with TSMC advanced-node demand, HBM/packaging constraints and customer capex, they support a semicap read-through thesis that should be separated by lithography, memory/HBM, foundry/logic, advanced packaging, inspection/process control and installed-base service.

### 6.6 Market expectation: current public business evidence is not enough for recommendation

The business chain is directionally positive, but a buy/sell conclusion requires a separate capital-feedback layer. The current public business pack does not answer valuation, ownership crowding, options positioning, short interest, ETF/sector flows, earnings-reaction asymmetry, or implied growth.

That means the proper output is not a trading recommendation. It is:

```text
The fundamental and product evidence supports AI infrastructure as a real multi-layer investment cycle.
The capital-market pack must still decide whether this is already priced in, crowded, or vulnerable to capex digestion / margin disappointment.
```

For a B-side workpaper, this is a useful conclusion because it tells the analyst where to spend the next hour: not re-proving that AI demand exists, but checking price-in, positioning, Dell margin conversion and substitution risk.

### 6.7 What I would underwrite

I would underwrite three things from public sources:

1. AI infrastructure demand is real and being funded by hyperscaler capex.
2. NVIDIA-led accelerator systems, leading-edge foundry, HBM / advanced packaging and selected semicap vendors have stronger evidence of structural demand than a generic "AI beneficiary" basket.
3. Dell has unusually visible AI server revenue demand through disclosed orders, shipments and backlog.

I would not underwrite three things yet:

1. Dell AI server growth is high-margin growth.
2. Hyperscaler capex mechanically flows to Dell / NVIDIA / TSMC in fixed proportions.
3. Semicap peers have identical exposure to AI demand.

### 6.8 What would change the view

The positive view strengthens if:

- Dell discloses improving AI server gross margin, attach economics, backlog conversion or cash conversion;
- cloud deployments show broad production use of GB200 / Blackwell systems beyond preview-stage availability;
- TSMC / ASML / AMAT / LRCX / KLAC disclose order or backlog strength tied to advanced packaging, HBM, leading-edge foundry or process complexity;
- capital-feedback evidence shows the market has not fully priced the improvement.

The positive view weakens if:

- hyperscaler capex guidance rolls over or shifts materially toward internal accelerators;
- Dell AI server revenue grows while ISG margin fails to improve;
- AMD / TPU substitution gains enough proof to pressure NVIDIA pricing or allocation;
- HBM / CoWoS / power/cooling bottlenecks delay deployments;
- export controls or China restrictions hit semicap or accelerator demand;
- valuation / positioning shows the AI infra thesis is already crowded and price-in is extreme.

## 7. Public Data Ceiling And Required Targeted Repair

公开源下应继续深挖：

1. DELL AI server gross margin / GPU pass-through / attach rate / backlog conversion。
2. DELL customer deployment / official customer case / cloud or enterprise AI Factory deployment。
3. NVDA Blackwell / GB200 supply allocation、cloud availability、partner deployment。
4. AMD/TPU benchmark and deployment evidence，区分 official spec、official cloud docs、MLPerf、third-party benchmark。
5. TSMC advanced packaging / CoWoS / HBM customer demand if official disclosures allow。
6. ASML bookings/backlog/EUV/DUV/China exposure。
7. AMAT/LRCX/KLAC order/bookings / customer segment / memory vs foundry/logic / services。
8. Capital feedback：valuation, ownership, short/option, sector/ETF, price reaction。

如果这些在公开源拿不到，应写成 typed gap：

- `commercial_tracker_gap`：需要 IDC、Omdia、Counterpoint、S&P Mobility、IQVIA、sell-through / channel tracker 等。
- `issuer_not_disclosed_gap`：公司未披露 SKU revenue / customer order / gross margin。
- `parser_gap`：文件定位到了，但表格/脚注/口径未抽出来。
- `runtime_projection_gap`：源数据有，但没有进入 JudgmentCard / MemoLogicPlan。

## 8. Agent Advantage Opportunities

这个 humanmade case 不是终点。agent 相比 junior analyst 的优势应体现在：

1. 快速从 10-K/10-Q/8-K、IR、product docs、cloud docs、benchmark、local filing 中抽出结构化 evidence rows。
2. 把每条证据标注 authority：exact、technical fact、deployment signal、proxy、gap。
3. 自动维护 `Company/Product -> Customer/Deployment -> Supplier/Foundry/Equipment -> FinancialBridge -> MarketFeedback` 图谱。
4. 对每个 judgment 生成反证、不可外推边界和 what-would-change。
5. 发现 “证据存在但 writer 没用上” 或 “节点有输出但没回答核心问题” 的最早 faulty artifact。
6. 用 Workbench 让 reviewer 能从最终判断 drill down 到 evidence、parser、source、graph edge、gap 和 reviewer decision。

## 9. Reverse Engineering Spec

### 9.1 Research Lead

必须先输出：

```text
thesis_path:
  initial_view
  must_answer_questions
  required_evidence_by_lane
  evidence_role_plan
  repair_plan
  writer_order
```

失败条件：

- 只激活 specialists，没有提出 DELL margin quality / NVDA substitution / semicap mechanism / price-in。
- 把 capex demand pool 当作订单证据。
- 没有写 “如果找不到什么证据，允许形成什么 bounded conclusion”。

### 9.2 Specialist

每个 specialist 输出 `judgment_candidate`，不是 evidence summary：

```text
judgment
answered_question
mechanism
supporting_evidence_refs
graph_edge_refs
authority_level
cannot_infer
counter_read
what_would_change_view
```

最低要求：

- Product specialist：比较 NVDA / AMD / TPU 的架构、memory、interconnect、ecosystem、deployment surface。
- Fundamental specialist：回答 DELL AI server revenue tailwind 是否能转成 margin / cash flow。
- Industry specialist：拆 supply chain mechanism，不把 peer group 当主证据。
- Market specialist：只在有 valuation/ownership/price-reaction 数据时谈 price-in，否则 typed gap。
- Risk specialist：必须写 capex digestion、margin dilution、substitution、supply bottleneck、export/customer concentration。

### 9.3 JudgmentCard

JudgmentCard 必须是判断卡，不是证据卡：

```text
judgment_card:
  card_id
  dimension
  judgment
  evidence_role
  authority_level
  business_mechanism
  financial_bridge
  product_or_graph_bridge
  cannot_infer
  counter_thesis
  what_would_change
  source_refs
```

### 9.4 ProductIntelligenceGraph Projection

图谱边必须投影为投资含义：

| Edge | Investment role |
| --- | --- |
| `NVDA -> supplies_gpu_to -> DELL/SMCI/OEM` | supply constraint / revenue pass-through / margin pressure |
| `DELL -> sells_ai_server_to -> customer/channel` | customer deployment / backlog conversion |
| `GOOGL TPU -> substitutes_for -> NVIDIA GPU` | substitution / pricing pressure |
| `TSMC/CoWoS/HBM -> capacity_for -> accelerator` | supply bottleneck / shipment constraint |
| `ASML/AMAT/LRCX/KLAC -> enables -> advanced-node/HBM/packaging` | semicap read-through |

### 9.5 MemoLogicPlan / Writer

Writer 只能拿：

- `MemoLogicPlan`
- `JudgmentCards`
- `dimension_judgments`
- `typed gaps`
- compressed source refs

Writer 不能重新从 raw evidence dump 里自己研究。若 JudgmentCard 没回答核心问题，writer 应 fail，并指出哪一 lane 不足。

## 10. Acceptance Criteria

Humanmade gold case v0.2 通过条件：

- [x] 有人类 analyst 研究链条。
- [x] 有 source-backed evidence ledger。
- [x] 有强/中/proxy/不可外推边界。
- [x] 有 human workpaper v0.1。
- [x] 有 polished memo v0.2，且不再只是结论列表，而是按 demand pool / accelerator / Dell financial bridge / semicap read-through / market price-in / counter-thesis 形成连续判断。
- [x] 有 public data ceiling 和 typed gap 定义。
- [x] 有倒推 Research Lead / specialist / JudgmentCard / ProductIntelligenceGraph / writer 的工程要求。
- [x] 未跑 paid LLM / full-chain。

尚未完成：

- [ ] 把本文档转成 machine-readable `HumanmadeGoldCaseSpec`。
- [ ] 用 accepted aggregate r7 / Memo Writer payload 做 no-paid `ResearchJudgmentRulerAudit`。
- [ ] 对照本文档逐节点标记：human expectation -> current agent artifact -> gap -> root cause。
- [ ] 在 audit 通过或 bounded pass 后，才允许单节点 paid Memo Writer rerun。

## 11. Source URLs

- Dell FY26 Q1 results: https://investors.delltechnologies.com/news-releases/news-release-details/dell-technologies-delivers-first-quarter-fiscal-2026-financial
- Dell FY26 Q4 8-K exhibit: https://www.sec.gov/Archives/edgar/data/1571996/000157199626000003/exhibit991earnings8kq4fy26.htm
- Dell NVIDIA AI Factory: https://investors.delltechnologies.com/news-releases/news-release-details/dell-offers-complete-nvidia-powered-ai-factory-solutions-help
- Dell XE9712 / Integrated Rack 7000: https://www.dell.com/en-us/dt/corporate/newsroom/announcements/detailpage.press-releases~usa~2024~10~dell-servers-storage-at-ocp.htm
- NVIDIA GB200 NVL72: https://www.nvidia.com/en-us/data-center/gb200-nvl72/
- NVIDIA financial reports: https://investor.nvidia.com/financial-info/financial-reports/default.aspx
- AMD MI300X: https://www.amd.com/en/products/accelerators/instinct/mi300/mi300x.html
- AMD MLPerf 6.0 blog: https://www.amd.com/en/blogs/2026/amd-delivers-breakthrough-mlperf-inference-6-0-results.html
- Google Cloud TPU v6e: https://docs.cloud.google.com/tpu/docs/v6e
- Google Cloud A4X / GB200: https://cloud.google.com/blog/products/compute/new-a4x-vms-powered-by-nvidia-gb200-gpus
- Microsoft FY26 Q3 results: https://www.microsoft.com/en-us/investor/earnings/fy-2026-q3/press-release-webcast
- Microsoft FY26 Q2 call: https://www.microsoft.com/en-us/investor/events/fy-2026/earnings-fy-2026-q2
- Amazon Q1 2026 results: https://ir.aboutamazon.com/news-release/news-release-details/2026/Amazon-com-Announces-First-Quarter-Results/default.aspx
- Alphabet Q1 2026 SEC exhibit: https://www.sec.gov/Archives/edgar/data/1652044/000165204426000043/googexhibit991q12026.htm
- Alphabet Q1 2026 earnings call: https://abc.xyz/investor/events/event-details/2026/2026-Q1-Earnings-Call-2026-nW8kCrBAKS/default.aspx
- Meta Q1 2026 transcript: https://s21.q4cdn.com/399680738/files/doc_financials/2026/q1/META-Q1-2026-Earnings-Call-Transcript.pdf
- ASML Q1 2026 results: https://www.asml.com/en/news/press-releases/2026/q1-2026-financial-results
- TSMC Q1 2026 earnings release: https://investor.tsmc.com/english/encrypt/files/encrypt_file/reports/2026-04/e85216eea8dccd8ca75d7e040e8d57be3ccd618b/1Q26%20EarningsRelease.pdf
- AMAT Q2 FY26 results: https://ir.appliedmaterials.com/news-releases/news-release-details/applied-materials-announces-second-quarter-2026-results
- LRCX Mar 2026 results: https://www.prnewswire.com/news-releases/lam-research-corporation-reports-financial-results-for-the-quarter-ended-march-29-2026-302750629.html
- MLCommons MLPerf Inference overview/results: https://mlcommons.org/benchmarks/inference-datacenter/
