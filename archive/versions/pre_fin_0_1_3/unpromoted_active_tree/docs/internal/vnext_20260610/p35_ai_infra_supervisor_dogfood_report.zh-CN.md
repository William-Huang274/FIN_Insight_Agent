# P35 AI Infra Supervisor Dogfood Report

日期：2026-07-09

范围：本报告围绕一个具体投研问题做 FIN_Insight_Agent dogfood：AI 基建需求是否真实转化为 accelerator、server OEM、foundry / packaging、HBM、semicap 公司的高质量收入和利润；哪些链条已有证据，哪些只是 demand proxy，哪些存在 margin dilution、supply bottleneck、capex digestion、export control 或 price-in 风险。

边界：本轮未跑 paid LLM、未跑 true full-chain、未跑模型对比。报告结论由三部分组成：P34 当前 runtime rows / fact-table projection、P35 决策面框架与 gap audit、我作为 supervisor 额外补的公开源 ledger。补源事实尚未回灌为正式 runtime rows。

## 一、结论

AI 基建需求已经真实转化为半导体供应链收入和利润，但不是所有链条质量相同。

最强证据链是 HBM 和 TSMC/advanced packaging。HBM 的证据最像“瓶颈租”：SK hynix、Samsung、Micron 都披露了与 AI / high-value memory 相关的收入和利润跃迁，利润质量明显强于普通存储周期。TSMC 的 foundry / packaging 是“收费站”：官方披露显示 HPC 占比、先进制程占比、毛利率和现金流都很强，但 CoWoS 具体产能、价格、客户分配仍需要把官方披露与二级估算分层处理。

NVIDIA accelerator 的收入和利润证据最硬，但风险也最被市场关注：高毛利、高数据中心收入是真实的；capex digestion、出口管制、自研 ASIC / TPU 替代和 price-in 是主要约束。Server OEM 不能再简单写成“全是 GPU 搬运费”，但也不能写成统一高质量受益者：Dell / HPE 已有更好的 AI server revenue、backlog、operating margin 和 cash-flow evidence；SMCI 则仍证明这个环节有低毛利、现金流消耗和客户/供应链波动风险。Semicap 公司利润质量高，但它对 AI 的证据更多是滞后的 capex read-through，而不是实时需求温度计。

**证据链强度排序**

| 排名 | 环节 | 当前判断 | 核心原因 |
| --- | --- | --- | --- |
| 1 | HBM | 最强真实需求 + 最强利润捕获 | AI demand、有限供给、高价值产品、长协/资格认证共同推动收入和 margin。 |
| 2 | Foundry / Packaging | 强真实需求 + 高质量收费站 | TSMC 官方收入、HPC、先进节点、毛利率和 FCF 很强；CoWoS 细分参数仍需 source-grade。 |
| 3 | Accelerator | 最硬收入利润事实，但 price-in / export / capex 风险高 | NVIDIA 数据中心收入和 GM 是 A 级事实；但客户 capex ROI、出口管制、自研芯片是主要反身性风险。 |
| 4 | Server OEM | 收入真实，利润质量分化 | Dell / HPE 变强；SMCI 证明低毛利和现金流压力仍真实。整体仍有 demand proxy 属性。 |
| 5 | Semicap | 高质量公司，AI-specific 证据滞后 | ASML / AMAT / LRCX / KLAC 利润好，但 AI 到设备订单是 capex 链条二阶映射，且出口和周期风险大。 |

## 二、Decision Surface

| 链条 | 收入证据 | 利润质量 | 供给瓶颈 / 捕获机制 | Margin dilution | Capex digestion | Export control | Price-in |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Accelerator | 极强：NVDA Q1 FY2027 revenue $81.6B，Data Center $75.2B | 极强：GAAP / non-GAAP GM 74.9% / 75.0% | GPU / networking / software ecosystem 捕获，短期仍有 allocation power | 低，目前未见 gross margin dilution | 高，取决于 hyperscaler capex ROI 与折旧吸收 | 高，Q2 guide 明确不假设中国 Data Center compute revenue | 高，需要市场/估值 pack；P34 当前不足 |
| Server OEM | 强：Dell AI orders $24.4B、AI server revenue $16.1B；SMCI net sales $10.2B；HPE Cloud & AI revenue $7.7B | 分化：Dell ISG OM 10.5%、HPE Cloud & AI OM 12.4%；SMCI GM 9.9% 且 OCF -$6.6B | 组装/集成/交付能力，不完全拥有 GPU/HBM 瓶颈租 | 中高，尤其 SMCI；Dell/HPE 改善但仍需持续验证 | 高，下游客户 capex 放缓会迅速传导 | 中，受 GPU 出口限制和客户地域影响 | 混合，需要 valuation / backlog conversion / cash conversion pack |
| Foundry / Packaging | 强：TSMC Q1 2026 revenue $35.90B，HPC 61%，7nm 及以下 74% wafer revenue | 极强：GM 66.2%、OM 58.1%、net margin 50.5% | 先进节点 + CoWoS / advanced packaging；瓶颈租主要由 TSMC 和 HBM 捕获 | 低，当前 margin 仍在上行区间 | 中，TSMC capex 回收能力强，但客户 capex 放缓会影响边际预期 | 中高，地缘和出口规则影响客户与设备供给 | 高，CoWoS 细分估算不可直接当官方事实 |
| HBM | 极强：SK hynix、Samsung DS、Micron CMBU / HBM product cycle 均有官方或官方镜像证据 | 极强：SK hynix OP margin 72%；Micron GAAP GM 84.6%；Samsung DS OP KRW 53.7T | HBM supply、qualification、advanced packaging attach；瓶颈租最清晰 | 低，短期反而 margin accretive | 中低，因供给紧且客户需求刚性；但 2027 后需看 HBM4/HBM4E 供给释放 | 中，间接受中国 AI chip / export mix 影响 | 高，超级周期叙事已充分交易，需要订单/价格转折信号 |
| Semicap | 中强：ASML / AMAT / LRCX / KLAC 官方收入利润强，但 AI-specific split 不完整 | 强：ASML GM 53%、AMAT GM 49.9%、LRCX GM 49.8% | EUV、etch/deposition、process control、advanced packaging equipment，但收入是 capex 链滞后项 | 低，设备公司本身 margin 质量好 | 高，典型滞后链条；客户 capex digestion 会反映到订单/booking | 高，LRCX China 34%；设备出口管制是核心风险 | 混合，需订单/booking 与估值联动数据 |

## 三、逐链分析

### 1. Accelerator：真实收入和利润最硬，但风险也最集中

NVIDIA 官方披露显示，Q1 FY2027 revenue 为 $81.6B，同比增长 85%；Data Center revenue 为 $75.2B，同比增长 92%；GAAP / non-GAAP gross margin 为 74.9% / 75.0%。这已经足以证明 AI accelerator 需求不是单纯 order talk，而是收入和高毛利事实。

但这个环节最不能忽略反身性。NVIDIA 同时披露 Q2 FY2027 revenue guide 为 $91.0B +/- 2%，且不假设来自中国的 Data Center compute revenue。BIS 2026 年规则又把 H200、MI325X 等对华许可放入 case-by-case 机制。也就是说，出口管制不是尾注，而是收入路径中的硬约束。

对 accelerator 的正确写法不是“最强所以无风险”，而是“收入/利润证据最强，capex digestion、出口、ASIC 替代、price-in 共同决定下一阶段赔率”。

### 2. Server OEM：收入已真实，但利润质量必须拆开

WorkBuddy 把 Server OEM 归为 demand proxy，这个方向是对的，但现在需要更细。Dell Q1 FY2027 披露 AI orders $24.4B、AI server revenue $16.1B、FY2027 AI-Optimized Servers revenue expectation around $60B；ISG revenue $29.0B，operating income $3.1B，operating margin 10.5%。HPE Q2 FY2026 披露 Cloud & AI revenue $7.7B、operating margin 12.4%，AI Systems backlog $5.9B。

但 SMCI Q3 FY2026 同时披露 net sales $10.2B、GAAP gross margin 9.9%、cash flow used in operations $6.6B。这说明 server OEM 的核心问题不是“有没有收入”，而是“收入能不能留下来”。GPU / HBM BOM 占比高时，OEM 容易成为高周转、低利润、现金占用的吞吐节点。

因此本报告给 Server OEM 的判断是：收入证据强，需求代理属性仍在，利润质量高度分化。Dell / HPE 的企业/主权客户 mix 和服务/平台 attach 是改善路径；SMCI 的毛利与现金流是反例。

### 3. Foundry / Packaging：TSMC 是高质量收费站，CoWoS 细分仍要分源

TSMC Q1 2026 官方披露 revenue $35.90B、gross margin 66.2%、operating margin 58.1%、net profit margin 50.5%；3nm / 5nm / 7nm 分别占 wafer revenue 的 25% / 36% / 13%，7nm 及以下合计 74%。TSMC presentation 还披露 HPC platform 为 Q1 2026 revenue 的 61%，free cash flow 为 NT$348.21B，并预计 2026 年 USD revenue 增长 above 30%。

这支持一个高置信判断：foundry/advanced packaging 环节已经把 AI demand 转成高质量收入和利润。TSMC 不是单纯 capex proxy，而是先进制程和先进封装的瓶颈收费站。

但 CoWoS 的 exact capacity、ASP、customer allocation 多数仍来自二级估算或卖方模型，不应和 TSMC 官方财务事实混为一谈。我们当前项目应该把“TSMC 官方强财务事实”和“CoWoS 产能/定价估算”放在同一决策格内但不同 source grade，而不是为了保守直接删掉 CoWoS 故事。

### 4. HBM：这次报告里 P34 最明显缺的链条

HBM 是本 case 中最需要被一等对待的环节。P34 当前 runtime rows 没有把 SK hynix、Samsung、Micron 作为一等 HBM segment peer panel，所以 writer 很难自然得出“HBM 可能是最强利润捕获者”的结论。

补源后，证据很清楚。SK hynix Q1 2026 官方镜像披露 revenue KRW 52.5763T、operating profit KRW 37.6103T、operating margin 72%、net margin 77%，并把 record performance 归因于 strong AI demand 下的 high value-added products。Samsung Q1 2026 披露 Device Solutions revenue KRW 81.7T、operating profit KRW 53.7T，Memory business 创季度新高，受 high-value AI demand 和 limited supply 支撑。Micron FQ3 2026 披露 revenue $41.456B、GAAP GM 84.6%、Cloud Memory BU revenue $13.769B、GM 83%，并披露 HBM4 high-volume shipments。

这些事实说明 HBM 不是 demand proxy。它是 AI accelerator BOM 中能够直接货币化供给短缺的部件之一。风险不在“需求是否存在”，而在 price-in、供给扩张、下一代 HBM4/HBM4E 资格认证、客户集中和周期转折。

### 5. Semicap：高质量公司，但 AI signal 是滞后读数

ASML、AMAT、LRCX、KLAC 的官方披露显示设备公司仍有强收入和 margin：ASML Q1 2026 net sales EUR 8.8B、gross margin 53.0%；AMAT Q2 FY2026 revenue $7.91B、GAAP gross margin 49.9%、operating margin 31.9%；LRCX March 2026 quarter revenue $5.84B、GAAP gross margin 49.8%、operating margin 35.0%；KLAC fiscal Q3 2026 revenue $3.415B、quarter FCF $622.3M。

但 semicap 对 AI demand 的传导链条更长：hyperscaler capex -> accelerator/HBM/foundry demand -> fab/packaging capex -> WFE / equipment booking -> revenue。它既是真实需求链条的一部分，也是滞后项。把 semicap 写成“AI 实时需求温度计”会误导；把它写成“无关 AI”也错误。

最大风险是订单周期、China exposure、出口管制和客户 capex digestion。LRCX 披露 China 为 revenue 的 34%，这类地理暴露要进入风险矩阵主表，而不是放在附录。

## 四、Real Demand vs Demand Proxy

**Real demand / direct capture**

- HBM：供给短缺、高价值产品、资格认证和长协直接转成收入和高 margin。
- TSMC advanced node / advanced packaging：先进节点、HPC platform、CoWoS/packaging bottleneck 共同支撑收费站逻辑。
- NVIDIA accelerator：收入和 gross margin 已披露，需求不是 proxy。

**Demand proxy / indirect capture**

- Server OEM：AI server revenue 和 backlog 真实，但瓶颈租主要不在 OEM 手里。Dell / HPE 的服务、企业客户和平台化能力能改善质量；SMCI 表明低 margin / cash conversion 风险不能忽略。

**Lagged read-through**

- Semicap：设备公司利润质量高，但 AI-specific demand 多数是客户 capex 与工艺强度的二阶映射。它适合作为周期确认，不适合作为最前端温度计。

## 五、最需要跟踪的转折信号

| 信号 | 为什么重要 | 触发后如何改判断 |
| --- | --- | --- |
| Hyperscaler capex / revenue 与 free cash flow 压力 | 决定 accelerator、server、foundry、semicap 的需求可持续性 | Capex 增速放缓且 AI revenue 未跟上，会下调 NVDA / server / semicap 排名 |
| HBM4 / HBM4E qualification 与供给释放 | 决定 HBM 瓶颈租持续时间 | 多家供应明显放量、ASP 下行或客户转单，会下调 HBM price-in 与 margin quality |
| CoWoS / advanced packaging utilization 与客户分配 | 决定 TSMC 是否继续捕获封装瓶颈租 | 利用率或价格松动，会把 TSMC 从“瓶颈收费站”调为“强 foundry，但 packaging rent 边际下降” |
| Server OEM gross margin / OCF / backlog conversion | 区分高质量平台商和 GPU 搬运费 | 如果 Dell/HPE margin 和 FCF 持续改善，Server OEM 可上调；若 SMCI 式现金消耗扩散，则下调 |
| BIS / export control 实施细则和 China revenue assumption | 决定 NVDA/AMD/semicap TAM 和客户结构 | 管制收紧会下调 accelerator 和 semicap TAM；放松只能部分修复，因为国产替代和客户配置已改变 |
| 估值、持仓、事件反应 | 决定“好公司”是否仍有好赔率 | 业务事实强但估值已充分透支时，报告应把结论从 fundamental quality 转成 risk/reward 分层 |

## 六、为什么 WorkBuddy 看起来比我们好

WorkBuddy 的优势不神秘：它先把题面拆成用户可见的 Decision Surface，然后连续联网补源，最后默认生成 HTML 表格和可视化。它的目标函数是“先把故事讲完整”。所以它即便是 single-agent，也能快速做出 70%-80% 可读的产业链研究报告。

它的弱点也明确：信源混合，官方披露、二级媒体、卖方估算、博客材料和模型推断经常同屏出现；有些估算数字的 source-grade 不够硬；数字 sanity 和 claim-level lineage 不足。它适合做 front-office draft，不适合作为可审计的研究生产系统。

FIN 这次的问题不是“RAG / SQL / 图谱没有价值”，而是当前链路经常把目标函数变成证明 lineage、避免 gate fail、避免越界。库存很多，但题面的取货单没有开对。P34 的 21 条 accepted runtime rows 能回答原 AI/Semis gold case 的一部分，但不能自然覆盖这次 5 环节 x 12 维度的研究面，尤其缺 HBM、SMCI/HPE、CoWoS 细分、semicap peer panel、price-in。

所以，数据库、图谱、skill、multi-agent 的商业价值不应该是“比 single-agent 更会声明边界”。它必须是：

1. 先产出和 WorkBuddy 同等甚至更强的 Decision Surface。
2. 每个格子都有 source grade、官方/估算/推断分层、numeric sanity、typed gap。
3. 每个判断能被 Workbench 单格 review、accept、reject、supersede。
4. 后续复跑时能知道哪个 cell 因哪个 source/parser/model 变化而改变。

如果做不到第 1 点，多 agent 没有产品意义；如果只做到第 1 点而没有 2-4 点，那只是另一个 WorkBuddy。

## 七、这次亲自 dogfood 发现的工程问题

### 1. 决策面没有成为 runtime contract

P34 的 rubric、judgment chain、evidence slot 做了很多正确工作，但它仍围绕上一个 gold case 的 20 个 evidence slots。当前用户题面要求的是 5 个产业链环节、12 个维度、60 个 decision cells。P34 可以 deterministic pass，同时仍无法回答用户肉眼看到的问题。

修复方向：Research Lead 的首个产物必须是 `DecisionSurfaceContract`，source routes、specialist packs、MemoLogicPlan、writer payload、verifier 都围绕 cell completeness 运行。

### 2. Source Hunter loop 缺失

WorkBuddy 在推理中反复 search/fetch，直到故事链足够完整。我们现在有 crawler/parser/source route，但更像预设路线执行器，不像面向缺口的 supervisor hunter。结果是：库里没有某个 cell 的一等材料时，writer 更容易进入边界说明，而不是主动打开新 official source route。

本轮我手工补了 15 条 source rows，说明 source 本身公开可得；缺的是从决策格到 source route 的闭环。

### 3. Parser 深度和 writer 可见事实之间有断层

P34 已有 accepted rows 和 fact-table projection，但有不少是 `context_summary`。这对边界判断有帮助，对 ranking / margin / cash conversion / peer panel 不够。用户看到的是“你有数据库和 RAG，为什么还没数字”。真实原因是很多官方 PDF / press table 还没被解析成 value / unit / period / product / segment rows。

### 4. Writer 被迫在不完整故事上做合规

P33/P34 的 writer payload policy 排除了 raw/bounded evidence rows，writer 依赖上游压缩后的 claims、required-item answer plan、fact tables。这个方向本身没错，因为 writer 不该自由编；但上游如果没有把 story surface 凑完整，writer 就只能写“不能推断”。

边界声明应该是 cell metadata，不应该是正文主角。

### 5. 输出产品面弱于内部治理面

WorkBuddy 默认交付 HTML、矩阵、图表。FIN 当前更强在 ledger、gate、trace、Workbench review，但面向用户的 artifact 还没有把这些优势转成“好看、好扫、好判断”的报告。投研用户第一眼比较的是报告，不是 lineage ledger。

### 6. 这里的“数据问题”不是单指 SEC 向量库

本报告前面说 parser / 抽取器没有稳定识别数据，指的不是“SEC 向量库或 SQL 数据库整体无效”。更准确的拆分如下：

| 数据层 | 当前状态 | 本 case 的问题 |
| --- | --- | --- |
| SEC / XBRL / CompanyFacts / filing text / 13F 基础层 | 已有较多结构化、索引、ledger 与 source-boundary 能力 | 对美国 filing facts 有价值，但覆盖不了 TSMC、SK hynix、Samsung 等非 SEC 主披露，也不能直接替代 CoWoS / HBM operating metrics。 |
| 非 SEC 官方披露和 IR PDF | 本轮主要靠 supervisor 手工补源 | TSMC PDF、HPE presentation、Samsung / SK hynix / Micron、ASML / AMAT / LRCX / KLAC 等公开源没有自动进入当前 P34 runtime rows。 |
| 表格型经营指标抽取 | P34 有 fact-table projection，但仍有不少 `context_summary` | segment revenue、gross margin、operating margin、orders、backlog、OCF、regional exposure 等没有稳定变成 value / unit / period / segment rows。 |
| 产业链 operating metrics | 当前更像估算/上下文，不是稳定事实表 | CoWoS capacity / ASP / utilization / customer allocation、HBM qualification / shipment / generation 等没有统一 source-grade 与 numeric sanity。 |
| 资本市场与 price-in 层 | 项目已有 S8 / capital-market feedback 能力，但本轮未充分接入 | 13F、估值分位、持仓拥挤度、期权/short interest、事件反应没有被系统拉入本报告的 60 个 cells。 |

因此，“缺数据”不是说已有 SEC/RAG/SQL 没价值，而是说当前题面需要的 source mix 超出了 P34 已接入的 rows，并且很多能召回的公开材料没有被提成分析可计算的 numeric runtime rows。

### 7. 财务、投融资、持仓、估值和衍生指标没有做够

本报告用了官方财务和经营数据，例如 revenue、gross margin、operating margin、orders、backlog、cash flow、regional exposure。但这还不等于完整投资研究 memo。

缺口明确存在：

- 估值：没有系统做 P/E、EV/Sales、EV/EBITDA、FCF yield、历史分位、同业分位和估值对利润质量的敏感性。
- 持仓：没有系统接 13F top holders、持仓变化、拥挤度、ETF / thematic fund exposure。
- 投融资和 capex：没有把 hyperscaler capex intensity、depreciation burden、AI revenue monetization vs capex 作为完整 cross-segment model。
- 衍生指标：没有接 implied volatility、skew、gamma / dealer positioning、short interest 或 borrow。
- 市场反馈：没有系统做 earnings reaction、revision breadth、price-in 程度和事件驱动赔率。

这不是项目不适用，而是本轮 dogfood 没有真正把 S8 capital-market pack、13F / ownership、valuation layer 和 derivatives / market-snapshot layer 接到 P35 decision surface。结果是报告能回答“需求是否真实、利润质量在哪”，但不能充分回答“业务好是否还有赔率”。下一版必须把 `fundamental quality` 和 `market price-in` 做成并列主表。

### 8. 图谱、skill 和模型编排也有问题

图谱不是没用，问题是当前图谱更像 relationship graph，不够像 value-capture graph。本 case 需要图谱表达的不是简单的 NVDA、TSMC、HBM、OEM、hyperscaler 之间有关系，而是：

- 谁捕获瓶颈租；
- 谁只是 revenue pass-through；
- 哪条边是 capex lag；
- 哪条边受 export control；
- 哪条边会 margin dilution；
- 哪条边是 official fact，哪条边只是 estimate 或 inference。

Skill 也不是没用，问题是现有 industry / fundamental / risk skill 更像研究提示和写作约束，不是硬运行时验收合同。它没有强制每个 `segment x dimension` cell 都输出 judgment、key number、source grade、numeric sanity、cannot infer、what-would-change。

模型编排的问题最核心：当前 multi-agent 仍容易变成每个节点交付自己的 evidence summary / gate pass，而不是由一个 supervisor 盯住 60 个 decision cells。缺哪个 cell，就应该触发 source hunter、parser、graph projection、capital-market pack 或 specialist 补齐；如果补不到，就写 attempt-backed typed gap。writer 不应该在这个过程完成前被要求“写好故事”。

### 9. 本轮 dogfood 的实际执行方式

这次“亲自参与全流程”需要准确理解：我没有完整按线上 multi-agent / DeepSeek 的全部节点顺序重跑一遍，也没有启动所有 parallel subagents。

实际做过的事情：

1. 读取 Project OS、P34 handoff、P34 route / adapter / live attempt / no-paid audit / fact-table projection 等本地 artifacts。
2. 审计 WorkBuddy 本地 HTML、task JSON、trace，确认它的 search/fetch/report 形态和样本质量。
3. 运行 P34 scoped no-paid runner 复核，包括 source route plan、adapter fixtures、live route attempts、no-paid quality audit、writer payload preflight、fact-table projection alignment。
4. 新增 P35 deterministic runner，把用户题面固化成 60 个 decision cells，并对照 P34 runtime rows 与 WorkBuddy samples 找缺口。
5. 我手工做 official-first 补源，写入 source supplement ledger，再以 supervisor / analyst 角色写出报告和工程反思。

没有做过的事情：

1. 没有通过实际 MCP 知识库检索、重排、SQL/vector/RAG 工具链来按 cell 自动取数。
2. 没有真的让 Research Lead、source hunter、fundamental specialist、industry specialist、market specialist、risk specialist、aggregate、writer 按线上编排逐个运行。
3. 没有在 parallel subagents 中分别加载各自 prompt / skill / graph pack 后产出独立判断，再由 aggregate 合成。
4. 没有运行 paid DeepSeek writer / true full-chain / model comparison。
5. 没有把补源 rows 回灌到 accepted runtime rows，也没有验证这些 rows 被 graph、specialist 或 writer 真正消费。

所以 P35 的证据性质是：supervisor 手工贯穿 + deterministic runtime audit + 手工补源报告。它足以定位产品和工程缺口，但不等于完整 multi-agent dogfood closeout。下一次如果要真正验证 agent 体验，必须按实际链路执行并记录每个节点的 consumed inputs、produced cells、missing cells、补源动作和 reviewer verdict。

## 八、本轮已落地的 P35 产物

| 产物 | 路径 | 作用 |
| --- | --- | --- |
| Decision Surface framework | `docs/project_os/p35_ai_infra_decision_surface_framework_v0_1.json` | 固化 5 环节 x 12 维度 x 60 cells，规定每格必须有判断、数字、source grade、numeric sanity、cannot infer、what would change。 |
| Current system gap audit | `docs/project_os/p35_ai_infra_current_system_gap_audit_v0_1.json` | 对照 P34 runtime rows 与 9 个 WorkBuddy samples，识别 25 个缺失 decision cells 和 5 个 root causes。 |
| Source supplement ledger | `docs/project_os/p35_ai_infra_source_supplement_ledger_v0_1.json` | 记录 15 条 supervisor 补源，区分官方、官方 PDF、官方镜像和政府源；尚未 runtime-ingested。 |
| Framework note | `docs/internal/vnext_20260610/p35_ai_infra_supervisor_dogfood_framework.zh-CN.md` | 汇总最终输出预期、审计摘要、关键缺口和未运行事项。 |
| 本报告 | `docs/internal/vnext_20260610/p35_ai_infra_supervisor_dogfood_report.zh-CN.md` | 把投研结论、dogfood 反思、工程修复方向合并成可读交付物。 |

新增脚本与测试：

- `src/sec_agent/p35_ai_infra_supervisor_dogfood.py`
- `scripts/eval_multi_agent/run_p35_ai_infra_supervisor_dogfood.py`
- `tests/test_p35_ai_infra_supervisor_dogfood.py`

## 九、下一步产品化修复建议

1. 实现 `DecisionSurfaceContract`，把 segment x dimension cells 作为 Research Lead 第一等输出，而不是 writer 后处理。
2. 加 `SourceHunterLoop`：对 missing / weak cells 自动按 official-first 策略打开 source routes，找不到时写 attempt-backed typed gap。
3. 把 P35 source supplement ledger 转成真实 route attempts、parser fixtures、normalized runtime rows，再重跑 quality audit。
4. 把 source grade / numeric sanity 作为每个 cell 的必填字段，而不是附录。
5. 加 report renderer：先渲染 Decision Surface、risk matrix、evidence ranking、what-would-change，再渲染正文；边界声明贴在 cell 下。
6. Workbench review 粒度从 memo/claim 扩到 decision cell：每格可接受、驳回、要求补源、标为估算。
7. 把 capital-market pack 接成每个链条的 `fundamental quality vs market price-in` 主表，而不是附录。
8. 把 relationship graph 升级为 value-capture graph，边上带 bottleneck rent、pass-through、lag、policy risk、source grade。
9. 让 skill 从提示词变成验收合同：每个 cell 的字段、证据等级、禁止替代、what-would-change 都必须可测试。
10. 垂直行业不要“大鸣大放”铺满所有行业。先选 2-3 条高价值业务线，把 source route、parser、skill、graph、report renderer 做到稳定可复跑，再扩行业。

## 十、核心来源

- NVIDIA Q1 FY2027: https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-first-quarter-fiscal-2027
- Dell Q1 FY2027: https://www.dell.com/en-us/dt/corporate/newsroom/announcements/detailpage.press-releases~usa~2026~05~dell-technologies-delivers-first-quarter-fiscal-2027-financial-results.htm
- Supermicro Q3 FY2026: https://ir.supermicro.com/news/news-details/2026/Supermicro-Announces-Third-Quarter-Fiscal-Year-2026-Financial-Results/default.aspx
- HPE Q2 FY2026: https://www.hpe.com/us/en/newsroom/press-release/2026/06/hpe-reports-fiscal-2026-second-quarter-results.html
- TSMC Q1 2026 earnings release: https://investor.tsmc.com/english/encrypt/files/encrypt_file/reports/2026-04/e85216eea8dccd8ca75d7e040e8d57be3ccd618b/1Q26%20EarningsRelease.pdf
- TSMC Q1 2026 presentation: https://investor.tsmc.com/english/encrypt/files/encrypt_file/reports/2026-04/a7e3abe65a3fbc342aa55f9f53a5490dd621c1ac/1Q26%20Presentation%20%28E%29.pdf
- SK hynix Q1 2026 official mirror: https://www.prnewswire.com/news-releases/sk-hynix-announces-1q26-financial-results-302750959.html
- Samsung Q1 2026: https://news.samsung.com/global/samsung-electronics-announces-first-quarter-2026-results
- Micron FQ3 2026: https://investors.micron.com/news-releases/news-release-details/micron-technology-inc-reports-record-results-third-quarter
- ASML Q1 2026: https://www.asml.com/en/news/press-releases/2026/q1-2026-financial-results
- Applied Materials Q2 FY2026: https://ir.appliedmaterials.com/news-releases/news-release-details/applied-materials-announces-second-quarter-2026-results
- Lam Research March 2026 quarter official mirror: https://www.prnewswire.com/news-releases/lam-research-corporation-reports-financial-results-for-the-quarter-ended-march-29-2026-302750629.html
- KLA fiscal Q3 2026 official mirror: https://www.prnewswire.com/news-releases/kla-corporation-reports-fiscal-2026-third-quarter-results-302757602.html
- BIS export policy: https://www.bis.gov/press-release/department-commerce-revises-license-review-policy-semiconductors-exported-china
