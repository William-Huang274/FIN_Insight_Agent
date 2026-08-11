# P36 AI 基建五链条手工 Writer 研究报告

日期：2026-07-09

## 边界

本报告是 P36 Node10 的 `supervisor-augmented` 研究报告，不是 runtime-only writer pass。

- Runtime-only writer 只能写 bounded partial report。
- 本报告使用了 `docs/project_os/p36_supervisor_source_supplement_ledger_v0_1.json` 中的公开源补充。
- 补源事实尚未回灌为 accepted runtime rows。
- 未调用 paid LLM、未运行 true runtime full-chain、未做模型对比、未做 case expansion 或 release eval。

## TL;DR

AI 基建需求已经真实转化为收入和利润，但利润捕获高度不均衡。

证据最硬的是 NVIDIA accelerator 和 TSMC / HBM 这三条链；利润质量最强的是 HBM 和 TSMC advanced node / packaging；Server OEM 的收入真实但利润质量分化；Semicap 是高质量公司群，但 AI signal 更像滞后 capex read-through，不是实时需求温度计。

排序上，我会把五链条分成三档：

| 档位 | 链条 | 判断 |
|---|---|---|
| 1 | HBM、Foundry / Packaging | 最像瓶颈租和高质量利润捕获。 |
| 2 | Accelerator | 收入和毛利事实最硬，但 export / capex digestion / price-in 风险也最集中。 |
| 3 | Server OEM、Semicap | 需求真实，但 Server OEM 有 margin dilution / cash conversion 分化，Semicap 是滞后确认链条。 |

## Decision Surface

| 链条 | 收入证据 | 利润质量 | 捕获机制 | 主要反证 | 本轮 source grade |
|---|---|---|---|---|---|
| Accelerator | NVIDIA Q1 FY2027 revenue $81.6B，Data Center $75.2B | GAAP / non-GAAP GM 74.9% / 75.0% | GPU + networking + software ecosystem | 中国收入假设、客户 capex ROI、ASIC 替代、price-in | runtime partial + supervisor official |
| Server OEM | Dell AI server revenue $16.1B；HPE Cloud & AI revenue $7.7B；SMCI sales $10.2B | Dell ISG OM 10.5%，HPE Cloud & AI OM 12.4%，SMCI GM 9.9% | 集成、交付、客户关系、服务 attach | GPU/HBM pass-through、低毛利、现金占用 | supervisor official |
| Foundry / Packaging | TSMC Q1 revenue $35.90B，先进节点 74% wafer revenue | GM 66.2%，OM 58.1%，FCF NT$348.21B | 先进制程 + advanced packaging bottleneck | CoWoS capacity/pricing/allocation 多为二级估算 | supervisor official PDF |
| HBM | SK hynix / Samsung / Micron 均披露 AI memory 高景气 | SK hynix OP margin 72%；Samsung DS OP KRW 53.7T；Micron HBM4 shipment cycle | 供给短缺、资格认证、generation transition | HBM4/HBM4E 供给释放、ASP 反转、客户集中 | supervisor official / official mirror |
| Semicap | ASML / AMAT / LRCX / KLA 最新收入利润强 | ASML GM 53%；AMAT OM 31.9%；LRCX OM 35.0%；KLA FCF $622M | EUV、etch/deposition、process control、packaging tools | capex lag、出口管制、China exposure、订单周期 | supervisor official / official mirror |

## 逐链判断

### Accelerator

NVIDIA 是本报告里收入和毛利事实最硬的环节。Q1 FY2027 的 revenue、Data Center revenue 和 gross margin 已经足以证明需求不是口头订单。

但 accelerator 的投资判断不能只看强需求。NVIDIA Q2 FY2027 outlook 明确不假设来自中国的 Data Center compute revenue，BIS 2026 规则又把 H200、MI325X 和类似芯片对华出口放入 case-by-case 许可。出口不是附录风险，而是收入路径约束。

当前判断：业务质量最硬，但赔率问题最大。要持续验证 hyperscaler capex ROI、ASIC/TPU 替代、出口政策和 valuation / ownership price-in。

### Server OEM

Server OEM 不能一概写成 GPU 搬运费，也不能一概写成高质量受益者。

Dell 的 AI orders、AI server revenue 和 ISG operating income 说明需求已经进入收入和利润；HPE 的 Cloud & AI revenue、AI Systems backlog 和 sovereign / enterprise order mix 说明它不是纯消费互联网客户的单一代理。相反，SMCI 的 9.9% gross margin 和 $6.6B operating cash outflow 提醒我们：这个环节容易有高收入、低毛利、重营运资本的问题。

当前判断：收入真实，利润质量分化。Dell / HPE 若能持续证明 margin、cash conversion 和 service/platform attach，Server OEM 可以从 demand proxy 向 partial value capture 升级；若 SMCI 式现金消耗扩散，则应下调。

### Foundry / Packaging

TSMC 是高质量收费站。Q1 2026 revenue $35.90B、GM 66.2%、OM 58.1%、先进节点 74% wafer revenue，说明 AI demand 已经转成高质量 foundry economics。Presentation 中的 FCF 和 2026 revenue growth outlook 进一步支撑了 capex digestion 能力。

但 CoWoS / advanced packaging 的 exact capacity、ASP、客户分配和利用率仍不是本轮 runtime official fact。报告可以写 TSMC 官方财务和先进节点强度，不能把 CoWoS 产能估算当官方事实。

当前判断：真实需求 + 高质量利润捕获。缺的是 CoWoS cell 的 source-grade 分层，而不是 TSMC 需求本身。

### HBM

HBM 是当前 runtime 最不该遗漏的一等链条。SK hynix、Samsung 和 Micron 的补源共同指向一个结论：AI memory 已经从需求叙事变成收入、利润和产品 generation 事实。

SK hynix 披露季度收入首次超过 KRW 50T，operating margin 72%；Samsung DS revenue / operating profit 强，Memory business 创季度新高，并提到高价值 AI demand 和有限供给；Micron 披露 HBM4 high-volume shipments，并给出 HBM4E volume production 时间线。

当前判断：HBM 是本 case 中最像瓶颈租的链条之一。主要风险不在“需求是否真实”，而在 HBM4/HBM4E 供给释放、ASP 反转、客户资格认证变化和价格已充分交易。

### Semicap

Semicap 公司利润质量强，但 AI 传导链条长。ASML、AMAT、LRCX、KLA 都有强收入、毛利、现金流或 segment margin 证据；AMAT 管理层也明确把 AI infrastructure、leading-edge logic、DRAM 和 advanced packaging 作为增长基础。

问题是 semicap 的 AI-specific signal 通常经过 hyperscaler capex、accelerator / HBM / foundry demand、fab / packaging capex、WFE booking、revenue 这几层传导。它更适合作为 capex cycle confirmation，而不是需求最前端温度计。

当前判断：高质量但滞后。风险重点是订单周期、China exposure 和出口管制，尤其 LRCX China revenue 34% 这种地理暴露应进入主表。

## Real Demand vs Demand Proxy

| 类别 | 链条 | 理由 |
|---|---|---|
| Real demand / direct capture | NVIDIA accelerator、HBM、TSMC advanced node / packaging | 直接披露收入、利润率、产品/平台 demand 或 advanced-node mix。 |
| Partial capture | Dell / HPE server OEM | AI server revenue、orders、backlog 真实，但 GPU/HBM pass-through 和 cash conversion 决定利润质量。 |
| Demand proxy / lagged read-through | SMCI、Semicap peer group | SMCI 反映 server throughput 与 margin/cash 风险；Semicap 反映 capex 链条滞后确认。 |

## 反证和转折信号

| 信号 | 影响 |
|---|---|
| Hyperscaler capex 增速放缓或 AI revenue monetization 不及预期 | 下调 accelerator、server OEM、TSMC、semicap 的持续性。 |
| HBM4 / HBM4E 大规模供给释放、ASP 下行、客户转单 | 下调 HBM 瓶颈租和 price-in。 |
| CoWoS utilization / pricing / allocation 松动 | 下调 TSMC packaging rent，但不等于下调其 foundry 基本质量。 |
| Server OEM gross margin 和 free cash flow 恶化 | 把 Dell/HPE 向 SMCI 风险形态靠拢。 |
| BIS / 出口政策收紧或实施不确定性上升 | 下调 accelerator 和 semicap TAM / mix，尤其对 China exposure 高的设备链。 |
| 估值、持仓、期权、short interest 过度拥挤 | 将结论从 business quality 转成 risk/reward 分层。 |

## Runtime 与补源边界

Runtime-only 可以支撑的结论：

- 系统并非没数据；RAG、exact-value ledger、market snapshot、ownership、PIG、graph 和 risk skill 都有材料。
- 当前 agent 链路能写出 bounded partial memo。
- writer 禁止补源是正确边界。

Supervisor supplement 才支撑的结论：

- HBM peer panel 的强利润判断。
- Dell / HPE / SMCI server OEM peer split。
- TSMC 官方财务 + cash-flow + forward outlook。
- Semicap peer panel 的最新收入、margin、cash-flow 和 China exposure。
- BIS 2026 export policy row。

仍缺 runtime 化的部分：

- source hunter 自动找到这些源。
- parser 抽成 value / unit / period / segment / source / authority rows。
- `DecisionSurfacePack` 把 rows 投射成五链条 x 判断格。
- market / ownership / valuation / derivative price-in pack。
- Workbench cell-level review。

## 结论

本轮报告的投资结论是：AI 基建需求真实，但最好利润捕获不一定在“最显眼的收入增长”处。NVIDIA 和 TSMC 证明了核心需求强度；HBM 证明了供给瓶颈的利润弹性；Dell/HPE 证明 Server OEM 不再只能被写成低价值代理，但 SMCI 证明 margin 和 cash risk 仍真实；Semicap 是高质量滞后确认链条。

本轮 dogfood 的工程结论同样明确：FIN_Insight_Agent 的底层材料和治理能力已经有差异化，但只有当 `DecisionSurfaceContract -> SourceHunterLoop -> parser promotion -> specialist cell packs -> DecisionSurfacePack -> writer` 这条链闭合时，multi-agent 才会稳定超过联网 single-agent。
