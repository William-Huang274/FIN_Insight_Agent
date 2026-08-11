# P33 Humanmade Gold Set Answer Exemplars v0.2

日期：2026-07-06

状态：`answer_exemplars_documented_pending_user_review`

来源：

- Gold Set 规则骨架：`docs/internal/vnext_20260610/p33_humanmade_gold_set_spec_v0_1.zh-CN.md`
- 机器可读规则骨架：`docs/project_os/humanmade_gold_set_spec_v0_1.json`

边界：

- 本文档只补“答案级样例”，不审计当前 aggregate r7 / Memo Writer payload。
- 本轮不跑 paid LLM、Memo Writer、full-chain、模型对比或 audit runner。
- 这些样例不是投资建议，也不是自动生成的事实结论；它们是用来约束 agent 输出风格、推理深度和边界表达的 humanmade gold answer pattern。

## 1. 为什么 v0.1 不够

v0.1 已经列出 case、证据角色、通过标准和失败标准，但很多内容仍是 rules。它能告诉 agent “不要怎么写”，但还不能稳定告诉 Research Lead、specialist 和 Memo Writer “一个合理答案应该长什么样”。

v0.2 的目标是把规则翻译成答案样板：

```text
不是：缺 SKU revenue 时不能说产品层无法判断。

而是：
虽然没有 H100 / B200 SKU revenue，但产品层仍可从架构代际、显存/互联、CUDA/Networking、客户部署、OEM 配置、CoWoS/HBM 供应瓶颈和竞品替代关系形成 bounded product judgment；只是不能外推出 SKU revenue、ASP、出货量或份额。
```

后续 audit runner 应该用这些段落检查 Memo Writer 是否真的学会了“判断 + 机制 + 边界”，而不是只遵守一组禁止规则。

## 2. Rubric Gold Case Answer Exemplars

### RGC-001: Semicap Cycle / Backlog / Export Control

合格答案样例：

> 半导体设备公司的 AI read-through 不能写成“AI capex 增长，所以 ASML / AMAT / LRCX / KLAC 都受益”。更合理的判断是：AI 需求只有通过 foundry / memory / logic 客户的实际资本开支，进一步落到 WFE、EUV / DUV、deposition、etch、process control、advanced packaging 等设备类别，才会转成设备商的 bookings、backlog、shipment 和 service revenue。ASML 的关键在 EUV/DUV 订单、installed base service 和先进制程客户节奏；AMAT / LRCX / KLAC 的关键更偏工艺步骤暴露、存储周期、晶圆厂利用率、客户集中度和服务收入韧性。
>
> 因此，一个合格的 semicap 结论要拆成两层：第一，AI / leading-edge capex 可以支持中长期设备需求方向；第二，短中期利润质量取决于订单是否进入 backlog、出货周期是否可见、China/export restriction 是否压制收入、memory/foundry/logic cycle 是否同步，以及服务收入能否缓冲新设备周期波动。如果只有 peer group、行业关系图谱或 AI 需求叙事，最多只能支持 research scope，不能当成订单周期和利润改善的主证据。

### RGC-002: Cloud / SaaS AI Monetization And Capex Tradeoff

合格答案样例：

> Cloud / SaaS 的 AI 投资不能简单写成“AI 产品发布，所以公司会增长”。更有用的判断是：AI 同时是需求入口和成本压力。对 Microsoft、Amazon、Google 这类云厂商，capex 和 GPU / data center 支出先进入资产负债表和折旧，再通过 Azure / AWS / Google Cloud revenue、usage growth、AI workload attach、enterprise contract、RPO、gross margin 和 operating margin 体现回报。对 CRM、NOW、ORCL 等软件公司，重点不是“有没有 AI 功能”，而是 AI 是否提升 seat expansion、pricing tier、renewal、workflow lock-in 或 RPO/ARR。
>
> 所以合格结论应该分开说：AI capex 能证明云厂商在争夺未来 workload，但不能自动证明 monetization 成功；AI product launch 能证明产品路线，但不能自动证明 ARR 或 margin。若云收入增长、RPO/remaining performance obligation、gross margin、deferred revenue、客户采用和开发者生态同时改善，才可以把 AI 从“成本和叙事”提高为“收入和留存驱动”。如果只有 capex 增加而缺 monetization 指标，结论应是 bounded：AI 提供增长期权，但短期可能压制 FCF 和 margin。

### RGC-003: Financials Rate / Credit / Capital Return

合格答案样例：

> 银行和券商类金融公司的分析不能停在 revenue / EPS。利率上行也不是线性利好，关键要看资产端收益率重定价和负债端存款成本、存款流失、批发融资成本之间的差。对 JPM / BAC / WFC / C，核心是 deposits、deposit beta、loan growth、NIM、provision、credit charge-offs、capital ratio 和回购/分红能力；对 SCHW 或区域银行，还要看 cash sorting、证券组合未实现损失、HTM/AFS 压力、流动性来源和监管资本约束。
>
> 合格结论应当是资产负债表驱动的：如果高利率提高资产收益但存款成本和信用损失上升更快，NIM 或 ROE 可能并不改善；如果贷款增长弱但信用质量恶化，收入韧性也可能掩盖未来拨备压力。宏观利率和 FDIC/FRED 数据只能提供环境，不能替代 issuer-level deposit、loan、capital、credit rows。只有把利率、存款、贷款、信用、资本回报和估值放在一起，才能回答“金融股是受益于利率，还是承压于融资和信用周期”。

### RGC-004: Healthcare Product Approval / Adoption / Reimbursement

合格答案样例：

> 医药和医疗器械不能把 trial、FDA 或产品存在直接写成销售成功。更合理的判断链是：产品/适应症先要有 clinical evidence 或 regulatory pathway，再看 label、payer / reimbursement、医生或医院采用、产能/渠道、procedure volume 或 prescription/usage proxy，最后才进入 revenue、gross margin 和 pipeline optionality。比如 GLP-1、肿瘤药、animal health、surgical robotics、cardiovascular device，各自的关键证据不一样，不能用一套“有研发、有审批”泛化。
>
> 因此合格答案应该说清楚：ClinicalTrials / openFDA / FDA approval 能支持产品存在、研发阶段、适应症和监管路径，但不能直接支持处方量、市场份额或产品收入。若公司披露 procedure volume、installed base、utilization、new patient starts、manufacturing capacity、payer coverage 或产品线收入，才可以提高判断强度。没有商业 tracker 或处方数据时，可以给 adoption direction 和 risk boundary，但不能把 regulatory context 冒充商业表现。

### RGC-005: Energy / Utilities Power Demand And Balance Sheet

合格答案样例：

> AI data center 用电增长不能直接写成公用事业利润增长。对 regulated utility，负荷增长只有在进入 rate base、capex plan、transmission/distribution investment、allowed ROE 和 rate case 后，才会变成较可见的长期 earnings base；同时，capex 扩张也会带来债务、利息、股权融资和监管滞后风险。对 merchant power 或核电/独立发电公司，电价、容量市场、燃料成本、PPA 和节点电网约束比 rate base 更重要。
>
> 合格结论应该拆开：数据中心需求可以提高 power demand 和长期资产投资机会，但是否创造股东价值取决于监管允许回报、融资成本、资产负债表、现金流覆盖和电价传导。若公司披露 load growth、interconnection queue、rate case、capex、debt maturity、cash flow 和客户合约，可以形成强判断；若只有 EIA/电价/AI 用电新闻，则只能支持需求背景，不能直接推断 EPS、ROE 或股价上行。

### RGC-006: Retail / Consumer Traffic / Price / Margin

合格答案样例：

> Retail / consumer 的收入增长必须拆成 traffic、ticket、price/mix、unit volume、store expansion 和 promotion。WMT、COST、TGT、SBUX、MCD、PG、KO 这类公司表面上都可能有 revenue growth，但质量完全不同：同店销售靠客流增长和会员/复购支撑，比靠价格或促销更健康；gross margin 改善如果来自 freight relief 或 shrink 改善，和来自价格转嫁的可持续性不同；库存上升、促销加大或 mix 下滑可能提前暴露需求疲软。
>
> 合格答案不应该只写“消费者仍有韧性”。应该回答：增长来自更多人买、每单更贵、价格提升、产品 mix 变化，还是门店扩张？毛利率改善和销售费用变化是否支持经营杠杆？库存和促销是否显示渠道压力？POS、scanner、panel 和真实 sell-through 多数需要商业数据，公开源下可用的是公司披露 operating KPI、同店销售、traffic/ticket、库存、毛利、宏观消费和渠道 proxy。公开 proxy 可以帮助判断方向，但不能冒充 sell-through exact。

### RGC-007: Auto / EV / Industrial Cycle

合格答案样例：

> Auto / EV 不能只看 deliveries，工业公司也不能只看订单标题。对 TSLA / GM / F / TM，交付量增长如果伴随 ASP 下滑、库存上升、激励增加或融资成本上升，利润质量可能下降；NHTSA recall、质量事件和产能利用率会影响产品风险和成本。对 CAT / DE 这类工业周期股，订单、backlog、dealer inventory、end-market exposure、融资条件和 commodity / construction / agriculture cycle 才能说明周期位置。
>
> 合格答案应该区分“需求量”和“利润质量”：交付增长能证明产品或渠道有需求，但不能单独证明 margin 改善；ASP、mix、inventory days、warranty/recall、capacity utilization、financing rate 和 dealer/channel data 才能回答需求是否健康。若只有 NHTSA 或 recall context，它能支持质量/监管风险，不等于销量或利润；若只有 delivery headlines，最多支持 volume direction，不能支持 pricing power、market share exact 或 FCF quality。

### RGC-008: Secondary Market Price-In / Capital Feedback

合格答案样例：

> 二级市场分析不是替代基本面，而是回答“好消息是否已经被定价，以及资金和资本结构是否会反过来影响公司”。一个公司产品和财务改善，并不等于股票仍有性价比；需要看 valuation relative to history/peers、growth implied by price、13F/ownership crowding、ETF/passive flow、short interest、options/IV/skew、credit spread、debt maturity、buyback/offering、insider activity 和事件日历。市场信号告诉我们预期、拥挤度和风险定价，不直接证明公司基本面变好。
>
> 合格答案应该写成双轨：基本面和产品证据回答“公司有没有变好”，市场资金面和资本反馈回答“市场是否已经给了这个价格、融资窗口是否改善、是否存在拥挤或事件风险”。如果估值已显著扩张、期权 implied move 很高、持仓拥挤或公司有潜在增发/可转债/解禁压力，即使基本面方向正确，也要降低短期 risk/reward。反过来，如果基本面证据改善但估值、持仓和事件定价尚未充分反映，可以形成更强的 expectation gap。不能把这些写成面向外部用户的交易建议。

## 3. Negative Gold Case Correct Response Patterns

### NGC-001: Missing SKU Revenue Does Not Mean Product Layer Failure

正确答案样例：

> 不能因为 NVIDIA 没拆 H100 / H200 / B200 / GB200 的 SKU 收入，就说产品层无法判断。更合理的判断是：NVIDIA 当前 AI accelerator 竞争力主要来自三层绑定。第一，GPU 代际升级本身，H100 到 H200 / Blackwell 的显存、带宽、互联、功耗效率和整机系统设计提升，使云厂商购买的是训练/推理集群能力，而不是单颗芯片。第二，CUDA、Networking、NVLink / InfiniBand 等软件和系统生态抬高迁移成本，AMD MI300 或 Google TPU 即使在部分 workload 有竞争力，也更像分流和补充，而不是短期全面替代。第三，客户部署、OEM AI server 配置、CoWoS/HBM 供应瓶颈和数据中心 capex 说明需求不只是新闻叙事，而是进入交付约束。
>
> 这个判断的边界也要明确：这些证据能支持“产品能力强、采用真实、供应链有瓶颈、替代短期有限”，不能直接推出 H100/B200 revenue、ASP、shipment 或 share。如果要升级成财务强判断，需要看到 data center revenue、gross margin、supply allocation、客户集中度、云厂商 capex 转化和订单交付节奏继续匹配。

### NGC-002: Demand Pool Is Not Supplier Allocation

正确答案样例：

> MSFT / AMZN / GOOGL / META capex 上升可以说明 AI infrastructure demand pool 真实存在，但不能直接说明这些钱流向了某一家 GPU、server OEM、semicap 或 power/cooling 公司。更合理的写法是：hyperscaler capex 是需求端上限和方向性证据，它支持“AI 基建投资仍在扩张”，也支持向 accelerator、networking、server、foundry/packaging、HBM 和电力设备做 read-through，但供应商受益程度还需要客户部署、采购合同、OEM 配置、供应链分配、backlog、shipment 或公司披露来验证。
>
> 所以如果问题是 DELL 或 NVDA 是否受益，不能把 capex 直接翻译成“DELL 订单增加”或“NVDA 份额提升”。合格结论应该是：capex 增长提高了需求池可信度，NVDA / DELL / ASML / LRCX 的受益需要进一步看产品供给、客户部署、供应瓶颈和公司财务桥。没有这些桥时，只能写 bounded demand read-through，不能写 supplier allocation exact。

### NGC-003: Relationship Graph Is Not A Financial Fact

正确答案样例：

> ProductRelationshipGraph 的价值是把研究路径打通，不是直接替代证据。比如图谱显示 NVIDIA GPU、TSMC advanced packaging、HBM、DELL AI servers、hyperscaler capex、ASML/LRCX/AMAT/KLAC semicap 之间有 upstream/downstream、supplier、customer、read-through 或 competitive relationship，这能帮助 Research Lead 知道应该查哪条传导链，也能帮助 writer 解释业务机制。
>
> 但图谱边本身不是订单、收入、毛利或 backlog。合格写法应该是：关系图谱支持“为什么这些公司应该被放在同一条 AI infrastructure 研究链上”，并提示下一步证据要求；若没有公司披露、客户公告、合同、shipment、backlog 或 segment financial rows，不能把图谱边写成财务事实。图谱是 thesis map 和 evidence search guide，不是财务结论。

### NGC-004: Parser Gap Is Not Public Source Absence

正确答案样例：

> 如果 ASML、TEL、Hon Hai、DART、本地交易所或公司 IR 的年报/季报/演示稿已经定位到，但表格、附注或数字没有被抽出来，正确结论不是“公开源没有数据”。正确结论是：source 存在，当前 parser / locator / local disclosure adapter 没能把它转成可审计 row。这个 gap 应该写成 parser_gap、table_extraction_gap、local_filing_adapter_gap 或 source_route_runtime_gap。
>
> 对用户可读的表达应该是：我们能确认该公司有公开披露路径，但当前系统还没稳定抽出 bookings、backlog、regional exposure、product mix 或 financial table，因此不能把缺失归因给公司不披露。下一步应该修具体 parser 或 source route，而不是让 Memo Writer 用“无公开数据”兜底。这类问题是系统 owned defect 或 adapter 深挖项，不能被当成公开源边界关闭。

### NGC-005: Available Evidence Must Not Be Reported Missing

正确答案样例：

> 如果 pre_memo_fact_selection、aggregate r7 或 writer payload 已经包含 LRCX revenue/capex、DELL ISG revenue、gross margin、operating income、working capital 或 capex rows，最终 memo 就不能写“缺少 LRCX/DELL 财务数据”。这不是数据缺失，而是 selector、projection、JudgmentCard、MemoLogicPlan 或 writer consumption 的内部传导失败。
>
> 合格处理方式是直接 fail 这个输出，并回溯：证据在哪个 artifact 里存在？它是否被选入 JudgmentCard？是否进入 required_item_answer_plan？是否被 Memo Writer 压缩时丢掉？是否被 renderer/verifier 误归类？只有找出最早 faulty layer 后，才能继续跑 writer。不能用 fallback 文案说“数据不足”，因为上游已经有数据，只是系统没有把它用对。

### NGC-006: Commercial Tracker Boundary Must Be Explicit

正确答案样例：

> 公开网页、新闻、App Store 排名、电商 listing、招聘、开发者生态、channel availability 和政府/监管 proxy 可以支持方向性判断，但不能冒充 IDC、Gartner、IQVIA、NielsenIQ、POS sell-through、OPRA、borrow cost 或 app revenue 这类商业/授权数据。比如看到某产品在 Amazon/JD/official store 有售，可以说明 channel presence；看到 App Store 排名变化，可以说明 attention 或 adoption proxy；看到 openFDA / ClinicalTrials 可以说明监管或研发路径。它们都不能直接写成市场份额、真实销量、处方量、app revenue 或实时资金盘。
>
> 合格答案应该同时保留两件事：第一，不丢掉公开 proxy 的研究价值，因为它们能支撑需求方向、产品存在、采用线索、渠道覆盖或风险提示；第二，明确 exact commercial tracker gap，告诉用户哪些结论需要商业数据或授权数据才能提高置信度。错误写法是把公开 proxy 填成 exact sales/share；另一个错误写法是因为没有商业 tracker 就把整段分析写成“无法判断”。正确做法是 bounded judgment + explicit commercial gap。

## 4. v0.2 对后续 agent 的要求

后续 audit runner 不应只检查字段是否存在，而要检查输出是否达到这些 answer-level 特征：

- 开头先给 judgment，而不是先列证据或先道歉。
- 每段必须说明业务机制：为什么这个证据会影响收入、利润、资本成本、预期或风险。
- 对没有 exact 数据的部分，先写仍可判断的内容，再写不能外推的边界。
- 如果缺口是系统 parser / projection / writer consumption 导致，不能写成 public source absent。
- Negative case 的正确答案必须能被 Memo Writer 学成“bounded analyst answer”，而不是简单拒答。

## 5. 后续第五步仍等待用户审阅

用户审阅 v0.2 后，才允许进入：

```text
P33-3_humanmade_gold_set_audit_spec_and_runner
```

该步骤将使用 v0.1 的规则 schema 与 v0.2 的 answer exemplars，一起审计 accepted aggregate r7 / Memo Writer payload。
