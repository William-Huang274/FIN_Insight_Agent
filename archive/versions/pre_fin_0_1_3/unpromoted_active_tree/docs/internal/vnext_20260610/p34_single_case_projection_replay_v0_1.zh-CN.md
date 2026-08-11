# P33 Single Case Projection Replay v0.1

## 结论

- status: `pass`
- source artifact: `eval/sec_cases/outputs/p34_ai_semis_scoped_writer_runs/p34_scoped_memo_writer_node_deepseek_20260707_120609/p34_ai_semis_scoped_writer_case_v0_1/memo_writer_node_result.json`
- 未运行：paid LLM、full-chain、模型对比、case expansion。

## Renderer Projection

- status: `pass`
- rendered chars: `6105`
- citation labels: `14`
- internal marker hits: `[]`

## Final Verifier Projection

- status: `pass`
- deterministic status: `pass`
- projected claims: `6`
- known evidence refs: `15`
- approx verifier prompt chars: `14478`

## Workbench Projection

- status: `pass`
- counts: `{'section_count': 9, 'claim_count': 6, 'gap_count': 1, 'gate_count': 2, 'artifact_count': 2, 'event_count': 4, 'evidence_linked_claim_count': 6, 'section_claim_link_count': 9}`

## Rendered Workpaper Preview

核心判断:
已披露事实给出的主线是：DELL 的orders shipments backlog/isg revenue operating income margin提供基本面锚点，需要和利润率、现金流及订单证据一起判断。NVDA/AMD/GOOGL 的accelerator memory bandwidth spec/mlperf inference performance proxy说明产品线、技术能力或经营锚点存在，可用于判断需求承接，但不能自动等同于 SKU revenue 或订单。MSFT/AMZN/GOOGL 的technical infrastructure capex context/aws revenue operating income只能说明客户/需求侧资本开支或终端需求池扩张，不能当作供应商收入、backlog 或直接订单。TSM/ASML/AMAT 的equipment segment mix/lithography cycle disclosure用于验证行业需求能否传到具体供应商收入和毛利。主要折价项来自 NVDA/DELL/AMD / accelerator memory bandwidth spec/mlperf inference performance proxy 指向影响。因此当前判断框架是：客户/需求侧 capex、供应商自身 capex、产品收入/订单与毛利锚点要分层看；只有当客户部署、订单或利润质量证据能连上时，供应链传导才可以上升为更强判断

分维度分析:
1. 资本需求、市场定价与反馈：业务机制是把基本面和产品证据再映射到估值、持仓、拥挤度、期权/short、ETF flow 和事件反应，判断好消息是否已经 price-in 资本市场桥是把业务改善与估值分位、资金持仓、流动性、short/options 和事件反应相互校验，判断预期是否已经被股价吸收 [C1][C2][C3]
2. 产品架构、部署与采用：业务机制是用架构、benchmark、云实例、OEM 配置和官方产品线判断产品能力与采用路径，再把它连接到收入承接和供应链瓶颈，而不是把产品页冒充收入或份额 财务桥是产品能力和客户部署先进入 OEM/server revenue visibility，再通过 backlog conversion、attach rate 和 margin mix 决定利润质量 [C7][C8][C9]
3. 基本面：DELL 的核心不是 AI server 需求是否存在，而是订单和 backlog 能否转化成高质量利润：现有公开材料能证明 AI server revenue tailwind 和 ISG 财务桥，但还不能证明 AI server gross margin、GPU pass-through、attach rate 或 backlog conversion 已经改善 业务机制是 orders/backlog -> shipments -> ISG revenue -> gross/operating margin -> cash conversion；缺任何一段都只能说明需求或收入可见度，不能说明利润质量 财务桥必须落到 DELL ISG revenue、Servers/Networking、gross/operating margin、working capital 和 cash conversion，而不是只写订单金额或收入增长
4. 行业与供应链：AI read-through 必须按机制拆开：TSMC 承接 advanced node / 先进封装，ASML 承接 lithography / installed base，AMAT 对应 materials engineering，LRCX 更偏 memory/HBM process intensity；这能支持半导体设备周期传导 业务机制是把 AI accelerator / HBM / packaging / advanced-node demand 映射到 foundry 和 semicap 工具链的具体环节，而不是用 peer group 代替订单 财务桥是从 AI demand 到 TSMC/HBM/advanced packaging，再到 ASML/AMAT/LRCX 等设备公司的 bookings、backlog、services 和区域/客户暴露
5. 风险与反证：反证不是泛泛的 AI 风险，而是 hyperscaler capex digestion、DELL margin dilution、AMD/TPU 替代、NVDA supply delay、出口管制、客户集中和 semicap 订单滞后；如果订单/部署兑现放缓、利润率恶化或 capex 下修，AI infrastructure thesis 应该降权 业务机制是先识别主线判断最脆弱的传导环节，再用反证限制结论权重，而不是在结尾泛泛列风险 反证的财务桥包括 DELL 低毛利放量、GPU pass-through 压缩利润、capex digestion 降低订单、出口管制和 semicap backlog 延后

关键问题回应:
1. 云厂商 capex 到供应商的传导：市场价格层面还不能形成强买卖建议：业务链条方向偏正面，但缺 valuation percentile、13F/ETF/insider/short/options、事件后价格反应等 price-in 证据，所以当前只能给出有边界的研究判断，不能判断市场是否已经充分定价 不能外推：Supplier allocation, OEM order conversion, or AI server margin from cloud capex alone. 会改变判断：Named procurement, supplier allocation, cloud instance deployment, or order/backlog conversion rows.
2. 必答问题：产品层可以形成有边界的判断：NVDA GB200/Blackwell 仍代表外部加速器系统的关键瓶颈，AMD MI300/MI35x 与 Google TPU 构成真实但更偏工作负载或自用体系的替代压力。 不能外推：不能从规格、benchmark 或云实例表面推出 SKU 收入、份额、出货量、ASP 或毛利。 会改变判断：生产部署、采购 mix、定价证据和客户配置会改变产品竞争权重
3. 必答问题：客户部署层面，DELL AI server / NVIDIA GB200 配置路径和 Google cloud TPU/GB200 云实例表面能证明采用路径存在，但仍不足以推出部署规模、客户集中度或单客户收入。 不能外推：不能从采用路径或配置表面推出部署规模、客户集中度或单客户收入。 会改变判断：官方客户部署、GA capacity、配置 mix 或订单规模披露会提高采用证据强度
4. 必答问题：DELL 的 AI server 需求可见度较强，但投资质量取决于 ISG margin、GPU pass-through、attach rate 和 backlog conversion，而不是只看 AI server revenue 或订单表述。 不能外推：不能在 AI server 毛利、GPU pass-through、attach rate 和 backlog conversion 披露前认定 DELL 利润质量已经改善。 会改变判断：ISG margin 随 backlog 转化改善，并伴随 attach economics 提升，会提高 DELL 质量判断
5. 必答问题：供应链 read-through 必须按机制拆开：TSMC 对应 advanced node / 先进封装，ASML 对应光刻和 installed base，AMAT 对应 materials engineering，LRCX 更偏 memory/HBM 工艺强度。 不能外推：不能从 broad revenue / margin 直接推出 AI-specific orders、客户 allocation 或具体设备订单。 会改变判断：按工具类别的 bookings/backlog、HBM/先进封装订单和客户集中度会改变 semicap read-through 置信度
6. 必答问题：市场 price-in 仍是薄弱项：业务链条方向偏正面，但缺估值分位、持仓拥挤度、short/options、ETF flow 和事件后价格反应，不能形成强买卖建议。 不能外推：不能只凭业务证据推出拥挤度、price-in 程度或买卖建议。 会改变判断：估值分位、13F/ETF/insider/short/options 和事件反应数据会打开 recommendation 级别判断

关键论据:
1. Dell 通过订单、出货和积压数据拥有 AI 服务器收入可见度，但利润质量因缺乏 GPU 传递成本、附加率和积压转换细节而受限 [C14]
2. NVIDIA 凭借 Blackwell/GB200 架构保持最强外部加速器系统瓶颈信号，AMD MI300/MI355X 和 Google TPU 提供真实但有限的替代压力 [C7]
3. MSFT、AMZN、GOOGL、META 的投融资与资本开支证据提供当前判断锚点；涉及 technical infrastructure capex context、aws revenue operating income；该证据应进入利润质量和产品组合判断，不能只写成收入增长线索 [C1]
4. TSM、ASML、AMAT、LRCX 的投资判断证据提供当前判断锚点；涉及 equipment segment mix、lithography cycle disclosure；该证据应说明需求如何沿客户、供应链或产能瓶颈传导 [C15]
5. NVDA、DELL、AMD、GOOGL 的投资判断证据提供当前判断锚点；涉及 accelerator memory bandwidth spec、mlperf inference performance proxy；该证据可支撑需求端资本开支强度，但不能直接证明供应商订单或份额 [C7]
6. DELL、GOOGL、NVDA 的产品与产线证据提供当前判断锚点；涉及 technical infrastructure capex context、orders shipments backlog；该证据可支撑采用/部署存在性，但不能替代订单金额、sell-through 或 backlog [C1]

投资含义:
- AI 基建链条的方向偏正面，但当前更适合写成有边界的研究判断：NVDA/Blackwell 仍是供给瓶颈，DELL 受益于 AI server demand，但投资质量取决于 ISG margin、GPU pass-through 和 backlog conversion
- 半导体设备 read-through 应按 TSMC advanced node、ASML lithography、AMAT materials engineering、LRCX memory/HBM process intensity 分机制判断，不能用 peer group 替代订单或 backlog

什么会改变判断:
- 如果 DELL backlog 转化时 ISG margin 没改善，或 AI server 只是低毛利 GPU pass-through，DELL 的投资质量应降权
- 如果 AMD/TPU 部署扩散、NVDA supply delay、hyperscaler capex 下修或 semicap bookings/backlog 滞后，AI infrastructure 主线应降权

后续跟踪:
- 跟踪 DELL AI server orders、shipments、backlog conversion、ISG margin 与 attach economics，确认收入可见度能否转化为利润质量
- 跟踪 NVDA/AMD/Google TPU 的生产部署、采购 mix、cloud availability、OEM configuration 和定价证据，确认产品竞争与替代压力
- 跟踪 valuation percentile、13F/ETF/insider/short/options、事件后价格反应，判断 AI 基建好消息是否已经 price-in

可行动的证据缺口:
- 仍需公开源或商业 tracker 补齐：AI server gross margin、GPU pass-through、客户配置 mix、供应商 allocation、SKU/ASP/shipments 和 market positioning 数据

限制与注意事项:
- 市场定价边界因缺少估值、持仓和资金流数据而受限，无法形成强买卖建议
- 产品分析基于规格和部署表面，非 SKU 收入或份额数据

证据边界: P34 AI/Semis 已验收公开源 runtime rows

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
- [C10] dell xe9712 gb200 oem sys
