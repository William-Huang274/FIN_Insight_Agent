# P34 Fact Table Projection Preview v0.1

本预览为 no-paid deterministic projection，不调用 LLM，不跑 full-chain。目的只验证 P34 accepted runtime rows 是否能以 analyst-ready fact table 进入最终 surface。

核心判断:
当前 AI/Semis 链条的可用证据支持一个有边界的正向研究判断：AI 基建需求池是真实存在的，NVDA GB200/Blackwell、AMD MI300X/MI355X、Google TPU/A4X 和 DELL PowerEdge 路径能够说明产品能力、替代压力与采用表面；但这还不能自动转化为 DELL 高质量利润、NVDA/DELL 订单 allocation、semicap AI-specific backlog 或 market price-in 结论。报告应先用数据表说明已有锚点，再判断哪些链条成立、哪些只是 proxy，最后把 DELL margin bridge 和市场定价列为会改变判断的关键缺口

关键数据表:
**财务桥与利润质量锚点**
这些 row 用来判断 DELL / NVDA / AWS 等经营锚点与利润质量；其中摘要型 row 只能说明披露路径或上下文，不能替代 AI server gross margin、GPU pass-through、SKU revenue 或订单 exact
| 公司 | 指标/属性 | 数值或事实 | 期间/版本 | 证据强度 | 边界 | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| DELL | ISG revenue / operating income / margin | Dell Q1 FY26 results disclose ISG revenue, Servers and Networking revenue and ISG operating income margin. (U… | FY2026 Q1 | structured_metric_context | AI server gross margin; Blackwell mix | [C15] |
| AMZN | AWS revenue / operating income | AWS revenue and operating income growth disclosed (USD / growth) | Q1 2026 | structured_metric_context | GPU purchase amount; DELL/SMCI orders | [C2] |
| NVDA | Data Center segment revenue | NVIDIA Data Center revenue provides segment-level accelerator demand confirmation. (USD segment revenue conte… | Q1 FY2027 | structured_metric_context | GB200 SKU revenue; DELL allocation | [C5] |
| DELL | AI server orders / shipments / backlog disclosure | Dell discloses AI-optimized server orders, shipments and backlog in FY26 results. (USD demand/revenue visibil… | FY2026 / FY2027 starting backlog | structured_metric_context | AI server gross margin; GPU pass-through cost | [C14] |

**产品规格、架构与性能 proxy**
这些 row 是产品竞争力判断的直接材料：可以比较架构、内存、带宽、benchmark 和系统形态，但不能外推收入、ASP、出货量或份额
| 公司 | 指标/属性 | 数值或事实 | 期间/版本 | 证据强度 | 边界 | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| GOOGL | TPU architecture specification | Google TPU v6e / Trillium docs provide custom accelerator architecture context. (technical specification) | TPU v6e / Trillium | specific_technical_or_deployment_fact | TPU procurement mix; NVIDIA replacement ratio | [C12] |
| NVDA | GB200 NVL72 rack-scale architecture | 36 Grace CPUs / 72 Blackwell GPUs / NVLink rack-scale domain (system specification) | Blackwell generation | specific_technical_or_deployment_fact | GB200 revenue; supplier allocation | [C13] |
| AMD | MLPerf inference performance proxy | AMD reports MI355X MLPerf Inference 6.0 throughput/proxy performance progress. (performance proxy) | MLPerf Inference 6.0 | specific_technical_or_deployment_fact | accelerator revenue; market share | [C8] |
| AMD | Accelerator memory / bandwidth specification | MI300X official specs include 192GB HBM3 and 5.3 TB/s memory bandwidth. (technical specification) | MI300X generation | specific_technical_or_deployment_fact | MI300X revenue; market share | [C7] |
| AMD | Accelerator memory / bandwidth specification | MI300X official datasheet includes up to 192 GB HBM3 and 5.3 TB/s max peak theoretical memory bandwidth. (tec… | MI300X generation | specific_technical_or_deployment_fact | MI300X revenue; market share | [C7] |

**客户部署、OEM 配置与采用路径**
这些 row 证明产品进入云实例、OEM 配置或官方部署路径；可以支持采用存在和 read-through，不能推出部署规模、客户集中度、单客户收入或 DELL margin
| 公司 | 指标/属性 | 数值或事实 | 期间/版本 | 证据强度 | 边界 | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| DELL | OEM system configuration | Dell PowerEdge XE9712 is identified with NVIDIA GB200 NVL72 rack-scale configuration context. (official OEM c… | 2024 OCP announcement | specific_technical_or_deployment_fact | DELL revenue; customer purchase volume | [C10] |
| DELL | Official OEM product path | Dell official product path links PowerEdge systems to NVIDIA GB200/NVL72 AI infrastructure. (official deploym… | 2024 OCP announcement | specific_technical_or_deployment_fact | order value; shipment volume | [C9] |
| GOOGL | Cloud deployment surface | Google Cloud A4X VMs expose NVIDIA GB200 GPU deployment surface. (official cloud deployment surface) | A4X / GB200 generation | specific_technical_or_deployment_fact | Google purchase quantity; NVIDIA allocation | [C11] |

**云厂商 capex 与需求池**
这些 row 支撑 AI infrastructure 需求池，但只有连到客户部署、订单、产品配置或供应商 allocation 时才可上升为供应商收入/订单判断
| 公司 | 指标/属性 | 数值或事实 | 期间/版本 | 证据强度 | 边界 | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| GOOGL | Technical infrastructure capex context | Alphabet management discussion provides technical infrastructure / AI capex demand-pool context. (demand pool… | 2025 Q1 | context_summary | GPU unit demand; server OEM share | [C1] |
| META | AI infra capex and component cost risk | Meta capex outlook provides AI infrastructure demand-pool and component cost risk context. (demand pool / ris… | FY2025 / 2026 outlook | context_summary | NVDA allocation; DELL revenue | [C3] |
| MSFT | Cloud / AI capex context | Microsoft annual report discloses capital expenditure context tied to cloud and AI infrastructure. (demand po… | FY2025 annual report | context_summary | NVDA allocation; DELL order conversion | [C4] |

**Foundry / semicap read-through**
这些 row 用来判断 AI 需求向 advanced node、光刻、材料工程、HBM/封装工艺强度的传导；不能直接替代 AI-specific booking、customer allocation 或 shipment tracker
| 公司 | 指标/属性 | 数值或事实 | 期间/版本 | 证据强度 | 边界 | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| TSM | Advanced node / HPC revenue-mix context | revenue / margin / advanced-node share disclosed (USD / percent) | Q1 2026 | structured_metric_context | NVDA/AMD/GOOGL customer split; CoWoS capacity exact unless disclosed | [C19] |
| AMAT | Equipment segment mix | revenue / margin / Semiconductor Systems mix (USD / percent) | Q2 FY26 | structured_metric_context | AI-specific order value; customer concentration | [C16] |
| ASML | Lithography cycle disclosure | ASML Q1 results provide lithography cycle, installed base and margin context. (semicap primary disclosure con… | Q1 2026 | context_summary | AI-specific ASML order; customer allocation | [C17] |
| LRCX | Memory / HBM process-intensity context | Lam official technology content links advanced packaging, HBM stacking, TSV etch and copper deposition to AI-… | official technology overview | context_summary | AI-specific LRCX booking; exact HBM equipment share | [C18] |

**市场 price-in 与反证边界**
这些 row 只支持市场预期、拥挤度、反证和风险路径的有边界讨论；不能给出实时资金流、完整期权仓位、borrow cost 或买卖建议
| 公司 | 指标/属性 | 数值或事实 | 期间/版本 | 证据强度 | 边界 | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| AI_SEMIS_BASKET | Independent counter-thesis context | Counter-thesis can use accepted independent rows for AMD accelerator competition, Google TPU/GB200 deployment… | P34 live route attempt set | context_summary | revenue impact magnitude; market-share change | [C20] |
| AI_SEMIS_BASKET | Market price-in / capital-feedback context | P33 capital-market feedback fixture provides bounded valuation, liquidity, holder/market proxy and capital-fe… | P33 fixture snapshot | context_summary | real-time fund flow; complete single-stock options positioning | [C6] |

**已尝试但仍缺的 exact slot**
这些不是未查找，而是已有 route attempt 后仍未形成可提权 exact row；writer 只能把它们写成决策缺口，不能伪装为公开源缺失或已补齐数据
| 公司 | 指标/属性 | 数值或事实 | 期间/版本 | 证据强度 | 边界 | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
|  | source_absent_after_attempt | Public issuer rows can support AI server revenue visibility and ISG baseline, but do not disclose AI server m… |  | attempt_backed_gap | AI server gross margin; GPU pass-through economics | [C21] |
|  | commercial_gap | Public delayed/context rows can support price-in discussion, but exact crowding, real-time flow, complete opt… |  | attempt_backed_gap | real-time fund flow; single-stock gamma exposure | [C22] |

关键问题回应:
1. 加速器架构与竞争替代：产品层可以形成有边界的判断：NVDA GB200/Blackwell 仍代表外部加速器系统的关键瓶颈，AMD MI300/MI35x 与 Google TPU 构成真实但更偏工作负载或自用体系的替代压力
   - 边界：不能从规格、benchmark 或云实例表面推出 SKU 收入、份额、出货量、ASP 或毛利。
   - 会改变判断：生产部署、采购 mix、定价证据和客户配置会改变产品竞争权重
2. 客户部署与 OEM 采用路径：客户部署层面，DELL AI server / NVIDIA GB200 配置路径和 Google cloud TPU/GB200 云实例表面能证明采用路径存在，但仍不足以推出部署规模、客户集中度或单客户收入
   - 边界：不能从采用路径或配置表面推出部署规模、客户集中度或单客户收入。
   - 会改变判断：官方客户部署、GA capacity、配置 mix 或订单规模披露会提高采用证据强度
3. DELL AI server 利润质量：DELL 的 AI server 需求可见度较强，但投资质量取决于 ISG margin、GPU pass-through、attach rate 和 backlog conversion，而不是只看 AI server revenue 或订单表述
   - 边界：不能在 AI server 毛利、GPU pass-through、attach rate 和 backlog conversion 披露前认定 DELL 利润质量已经改善。
   - 会改变判断：ISG margin 随 backlog 转化改善，并伴随 attach economics 提升，会提高 DELL 质量判断
4. Foundry / semicap 供应链传导：供应链 read-through 必须按机制拆开：TSMC 对应 advanced node / 先进封装，ASML 对应光刻和 installed base，AMAT 对应 materials engineering，LRCX 更偏 memory/HBM 工艺强度
   - 边界：不能从 broad revenue / margin 直接推出 AI-specific orders、客户 allocation 或具体设备订单。
   - 会改变判断：按工具类别的 bookings/backlog、HBM/先进封装订单和客户集中度会改变 semicap read-through 置信度
5. 市场 price-in 与资本反馈：市场 price-in 仍是薄弱项：业务链条方向偏正面，但缺估值分位、持仓拥挤度、short/options、ETF flow 和事件后价格反应，不能形成强买卖建议
   - 边界：不能只凭业务证据推出拥挤度、price-in 程度或买卖建议。
   - 会改变判断：估值分位、13F/ETF/insider/short/options 和事件反应数据会打开 recommendation 级别判断

投资含义:
- 当前更适合把 AI/Semis 写成有边界的正向研究 workpaper，而不是 recommendation：产品与需求证据支持主线，但利润质量和 price-in 仍未闭环
- DELL 的关键不是 AI server 需求是否存在，而是 backlog 转化、GPU pass-through 和 ISG margin 是否证明收入质量

什么会改变判断:
- 如果 DELL 披露 AI server mix、gross margin、attach economics 或 backlog conversion 改善，DELL 质量判断可以上调
- 如果 hyperscaler capex 下修、AMD/TPU 替代扩大、NVDA supply delay 或 semicap bookings/backlog 滞后，主线应降权

后续跟踪:
- 跟踪 DELL AI server orders / shipments / backlog / ISG margin
- 跟踪 NVDA GB200、AMD MI300X/MI355X、Google TPU/A4X 的部署、配置、benchmark 和供应链约束
- 跟踪 ASML/AMAT/LRCX 的 bookings/backlog、China exposure、HBM/advanced packaging 相关披露

证据索引:
- [C1] alphabet capex server chain context
- [C2] amzn aws demand pool context
- [C3] meta capex component pricing risk
- [C4] msft cloud ai capex supply shortfall
- [C5] nvda data center revenue demand confirmation
- [C6] market price in valuation positioning gap
- [C7] amd mi300x memory bandwidth competition
- [C8] amd mlperf mi355x performance proxy
- [C9] dell nvidia poweredge ai factory product path
- [C10] dell xe9712 gb200 oem system config
- [C11] google a4x gb200 cloud deployment surface
- [C12] google tpu v6e trillium architecture
