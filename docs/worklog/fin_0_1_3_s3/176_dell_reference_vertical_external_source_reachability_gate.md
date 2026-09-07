# DELL 单案例完整纵切：A01 外源可达性审计与 A02 检索预算建议门

- 审计日期：2026-09-02
- 研究 as-of：`2026-09-02T23:59:59+08:00`
- 状态：`A01_EXTERNAL_SOURCE_REACHABILITY_AUDIT_COMPLETE / EXACT_URL_R4_4_OF_4_ZERO_MODEL_PASS_CANDIDATE_ONLY / A02_AND_EVIDENCE_HOLD`
- 产品范围：仅限 `DELL_AI_INFRA_REFERENCE_VERTICAL` 的时效性外源资格，不恢复 R14，不扩展为通用研究平台。
- 上游运行：`20260902-dell-reference-vertical-q1-a01`，Planner 已产生 9 个分支、19 个 Evidence 请求、10 个 `external_required` 请求；A01 随后在 provider structured-output adapter 层失败，Evidence/Finance、外源、Specialist、Counter、Lead、HITL 与报告均未执行。
- 审计输入：A01 immutable model-call outcome 与人工只读网络检索。
本次未执行：A02、任何付费模型调用、Evidence admission、S2 写入、网页批量下载或仓库运行时变更。

## 1. 门的目的与结论

本门回答的不是“这些资料能否自动成为研究事实”，而是更早的一层问题：A01 Planner 要求的时效性资料，人是否能发现、打开并提取；哪些是工具或路由问题，哪些才是真实公开信息边界；A02 应给每个分支多少检索轮次和页面预算。

只读审计的结论如下：

1. 十个 A01 `external_required` topic families 均存在可执行的公开检索路径；Dell 最新季度、Rubin/GB300、GPU/内存供给、模型公司算力扩张、hyperscaler capex、竞争/ODM、BIS 规则等主要主题均已实际找到并打开官方来源。
2. 不是所有目标都能由公开资料闭合。Dell 配置数量与同口径成交价、Dell 中国收入与出口管制损失、客户到 backlog 的归因、Dell 实际 BOM/采购价、ODM 单柜利润分配、具体闭源模型 GPU-hours 等仍有真实边界。
3. “页面发现但一个 URL 路由打不开”不等于公开信息缺口。Dell quarterly-results 的个别静态链接出现过 `403` 或内部错误，但同一披露可由 SEC accession、SEC Exhibit 或 Dell IR PDF 取得。
4. 本次证明的是人工/通用网页检索的 source reachability，不证明 A02 选定的 Exa、capture adapter 或 MCP 已经自动复现。下面的 URL 应作为 A02 外源 qualification gold set。
5. 任何打开或抓取成功的网页仍只是 candidate。只有 claim-level source、日期、locator、说话主体、事实/预测属性和归因范围通过后，才可进入 Reviewed Evidence；不得因来源“看起来官方”而自动晋升。

### 1.1 状态定义

- `discover`：搜索能够定位到官方或成熟行业来源。
- `open`：URL/PDF 确实可访问，而非只有搜索摘要。
- `capture`：正文或 PDF 文本能够提取并保留 URL、发布日期和 locator。
- `citation candidate`：内容可能支持某个 claim，但尚未通过 Evidence admission。
- `public boundary`：在正确来源、替代路由和有界检索均实际尝试后，仍没有公开披露；不得拿 parser/crawler/route failure 冒充。

## 2. A01 十个 external-required topic families 的可达性矩阵

以下十条 query 来自 A01 Planner 的 immutable outcome，不是审计者重新改写的问题。主要来源均已实际打开或正文可提取；网页正文只作摘要记录，不在本 worklog 大段复制。

### 2.1 `Q1_ISSUER_TRUTH`：最新发行人事实

**A01 query**：`Dell Technologies FY2027 Q2 8-K EX-99 earnings release SEC filing`

**已打开主要来源**：

- [SEC accession `0001571996-26-000039` 目录](https://www.sec.gov/Archives/edgar/data/1571996/000157199626000039/)，2026-09-01；route：官方 EDGAR accession → Exhibit。
- [Dell FY27 Q2 Prepared Remarks PDF](https://investors.delltechnologies.com/static-files/a909096f-5091-4dcf-8291-019f6f9fb887)，2026-09-01；route：Dell IR static PDF。
- [Dell FY27 Q2 Performance Review PDF](https://investors.delltechnologies.com/static-files/5d15be71-1d9a-45ec-8308-8987fb41084d)，2026-09-01；route：Dell IR static PDF。
- [Dell FY27 Q2 Exhibit 99.1](https://investors.delltechnologies.com/static-files/2ea39342-d76a-4bed-b5d8-be06d7c86a66)，2026-09-01；route：Dell IR static Exhibit，SEC 目录可交叉核对。

**可以支持**：Dell 最新 AI server orders、revenue、backlog、FY27 guidance、客户数、分部表现和管理层对 Rubin shipment 的表述；同一指标可在 SEC/IR 多路交叉核对。

**不可以支持**：把 Exhibit 文字数字自动写成 SEC CompanyFacts/XBRL `NumericFact`；从发行人总量反推未披露的客户、地区、GPU 型号或交付季度构成。

**真实边界**：当前季度 Exhibit 是可引用的发行人文字 Evidence，但不因此获得 S2 结构化数值权威。

### 2.2 `Q2_DEMAND_QUALITY`：具名部署、客户关系与需求质量

**A01 query**：`Dell Technologies AI infrastructure customer deployment named customer relationship hyperscaler`

**已打开主要来源**：

- [Dell：Sovereign AI 选择 Dell 建设 EMEA AI 数据中心](https://www.dell.com/en-us/dt/corporate/newsroom/announcements/detailpage.press-releases~usa~2026~1~sovereign-ai-selects-dell-technologies-to-power-next-generation-ai-data-centers-across-emea.htm)，2026-01-21；route：Dell corporate newsroom HTML。
- [Dell：BUZZ HPC 使用 Dell 推进加拿大主权 AI](https://www.dell.com/en-us/dt/corporate/newsroom/announcements/detailpage.press-releases~usa~2025~11~buzz-hpc-taps-dell-technologies-to-advance-sovereign-ai-in-canada.htm)，2025-11-17；route：Dell corporate newsroom HTML。
- [Dell FY27 Q2 Prepared Remarks](https://investors.delltechnologies.com/static-files/a909096f-5091-4dcf-8291-019f6f9fb887)，2026-09-01；route：Dell IR static PDF。
- [OpenAI–AWS partnership](https://openai.com/index/aws-and-openai-partnership/)，2025-11-03；route：模型公司官方 HTML，仅用于行业需求对照，不用于 Dell 归因。

**可以支持**：少量具名 Dell 部署、Dell 对客户 cohort 扩展的发行人表述，以及模型公司/云厂商整体算力采购环境。

**不可以支持**：把 OpenAI、Anthropic、Microsoft、Meta 或其他 hyperscaler capex 自动写成 Dell 订单；把少数具名案例外推为 backlog 客户结构。

**真实边界**：Dell 未披露 950 亿美元级 AI backlog 的完整客户清单、客户集中度、取消权、预付款或分季度交付结构。

### 2.3 `Q3_UNITS_ASP_PVM`：配置数量、价格与 PVM

**A01 query**：`Dell AI server configuration quantity price public procurement award`

**已打开主要来源**：

- [Dell AI Factory with NVIDIA 产品与 availability 更新](https://investors.delltechnologies.com/news-releases/news-release-details/dell-ai-factory-nvidia-delivers-proven-path-enterprise-ai-roi)，2026-03-16；route：Dell IR HTML。
- [Dell FY27 Q2 Prepared Remarks](https://investors.delltechnologies.com/static-files/a909096f-5091-4dcf-8291-019f6f9fb887)，2026-09-01；route：Dell IR static PDF。
- [TrendForce Enterprise SSD Q3 2026 报告公开摘要](https://www.trendforce.com/research/download/RP260728RU)，2026-07-28；route：成熟行业来源公开 landing page，完整正文付费。

**可以支持**：产品配置族、availability、发行人总订单/收入，以及部分组件市场价格方向；经过逐项来源审核后，这些可作为 scenario inputs 或低权威 `research_calculation` 输入，但不是 S2 `NumericFact`。

**不可以支持**：在没有同一配置、数量、采购时间、折扣、服务和网络 bundle 的前提下计算权威 ASP、units 或 PVM；公开产品 availability 不是成交价，组件市场价也不是 Dell BOM。

**真实边界**：本次未找到能同时绑定 Dell AI server 具体配置、数量和可比成交价的官方采购 award。A02 有界检索后若仍无匹配来源，应保留 null/区间或显式非权威 scenario，不得补造精确值。

### 2.4 `Q4_ARCHITECTURE_RAMP`：架构量产、系统可用性与交付阶段

**A01 query**：`Dell PowerEdge AI server availability firmware readiness liquid cooling networking`

**已打开主要来源**：

- [NVIDIA：Vera Rubin Ramps Into Full Production](https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Vera-Rubin-Ramps-Into-Full-Production-to-Power-Agentic-AI-Factories-Worldwide/default.aspx)，2026-05-31；route：NVIDIA IR HTML。
- [NVIDIA Q2 FY2027 Earnings Call Transcript PDF](https://investor.nvidia.com/files/content_files/TRANSCRIPT_-NVIDIA-Corp-NVDA-US-Q2-2027-Earnings-Call-26-August-2026-5_00-PM-ET.pdf)，2026-08-26；route：NVIDIA IR static PDF。
- [Dell AI Factory with NVIDIA 产品与 availability 更新](https://investors.delltechnologies.com/news-releases/news-release-details/dell-ai-factory-nvidia-delivers-proven-path-enterprise-ai-roi)，2026-03-16；route：Dell IR HTML。
- [Foxconn Q2 2026 results/news page](https://www.honhai.com/en-us/press-center/press-releases/latest-news)，2026-08-12；route：Foxconn 官方 press-center HTML。

**可以支持**：GB300 选择性出货、PowerEdge 产品 availability window、Rubin production shipment、系统 OEM/ODM 生态，以及 Foxconn 对 Rubin rack 量产时间的表述。

**不可以支持**：把 announcement、qualification、firmware readiness、production、shipment、customer deployment 和 Dell revenue recognition 混成同一事件；供应商宣称的量产不等于 Dell 已确认收入。

**真实边界**：具体客户现场的 firmware 验收、集群稳定性、部署完成日期和收入确认通常不完整公开，需要具名客户或 Dell 的进一步原始证据。

### 2.5 `Q5_SUPPLY_AND_PRICE`：GPU、HBM、DRAM、NAND/eSSD 与基础设施供给

**A01 query**：`Micron SK Hynix TSMC Broadcom HBM server DRAM NAND price direction supply capacity`

**已打开主要来源**：

- [Micron Q3 FY2026 Prepared Remarks PDF](https://s25.q4cdn.com/621799436/files/doc_financials/2026/q3/Q3-FY26-Prepared-Remarks.pdf)，2026-06-24；route：Micron IR static PDF。
- [Micron Q3 FY2026 Results](https://investors.micron.com/news/press-release/2026/Micron-Technology-Inc--Reports-Record-Results-for-the-Third-Quarter-of-Fiscal-2026/default.aspx)，2026-06-24；route：Micron IR HTML。
- [TrendForce Q3 2026 DRAM/NAND 价格预测](https://www.trendforce.com/presscenter/news/20260703-13134.html)，2026-07-03；route：成熟行业来源公开 HTML。
- [NVIDIA Q2 FY2027 Earnings Call Transcript](https://investor.nvidia.com/files/content_files/TRANSCRIPT_-NVIDIA-Corp-NVDA-US-Q2-2027-Earnings-Call-26-August-2026-5_00-PM-ET.pdf)，2026-08-26；route：NVIDIA IR static PDF。
- [Western Digital FY2026 Q4 Results](https://investor.wdc.com/node/28586)，2026-08-05；route：WD IR HTML。
- [Seagate FY2026 Q4 Results](https://investors.seagate.com/news/news-details/2026/Seagate-Technology-Reports-Fiscal-Fourth-Quarter-and-Full-Fiscal-Year-2026-Financial-Results/default.aspx)，2026-07-28；route：Seagate IR HTML；直接打开有过内部错误，搜索索引正文与 IR 新闻目录可作为 discovery fallback。

**可以支持**：DRAM/NAND 供需和价格方向、数据中心 SSD/HDD 需求、NVIDIA 对 GPU/内存/电力/数据中心供给约束的管理层表述。

**不可以支持**：把 Micron/TrendForce 市场变化直接写成 Dell 实际采购价、库存成本或单台服务器成本；从 WD/Seagate 公司利润率倒推 HDD 合同价；把供应商展望写成已实现事实。

**真实边界**：Dell 的供应商 allocation、长约价格、BOM、库存账龄和向客户传导的时间差不公开。本次未逐一完成 SK Hynix、TSMC、Broadcom 官方页的 qualification，因此 A02 需要为这些未覆盖子层保留第二轮，而不能把已开 Micron/NVIDIA 来源当成全链闭合。

### 2.6 `Q6_MODEL_COMPUTE_DEMAND`：训练、推理、agentic/test-time compute

**A01 query**：`MLCommons inference results model compute training inference test-time compute benchmark`

**已打开主要来源**：

- [OpenAI：Building the compute infrastructure for the Intelligence Age](https://openai.com/index/building-the-compute-infrastructure-for-the-intelligence-age/)，2026-04-29；route：OpenAI 官方 HTML。
- [Anthropic 与 AWS 扩大算力合作](https://www.anthropic.com/news/anthropic-amazon-compute?invite=1)，2026-04-20；route：Anthropic 官方 HTML。
- [OpenAI–NVIDIA systems partnership](https://openai.com/index/openai-nvidia-systems-partnership/)，2025-09-22；route：OpenAI 官方 HTML。
- [Anthropic 扩大使用 Google Cloud TPU](https://www.anthropic.com/news/expanding-our-use-of-google-cloud-tpus-and-services)，2025-10-23；route：Anthropic 官方 HTML。

**可以支持**：模型公司实际签署或宣布的 GW 级基础设施扩张、多芯片部署与 agentic AI 对算力需求的方向性证据。

**不可以支持**：将行业算力扩张自动归因给 Dell；从宣传性 workload multiplier 推导 Dell revenue；在没有 benchmark protocol 和可比 workload 时比较每个模型的单位算力。

**真实边界**：GPT-5.6 等闭源模型的训练 GPU-hours、推理流量、token economics 和硬件分配通常不公开。本次打开的公司来源能证明 compute expansion，但尚未单独 qualification MLCommons 当前结果页；A02 若要做可比性能论证，需在第二轮补官方 benchmark/result，而不是用厂商宣传替代。

### 2.7 `Q7_EXPORT_CONTROL_CHINA`：美国对华先进计算限制

**A01 query**：`BIS export control advanced computing AI chips China rule effective date performance threshold 2025 2026`

**已打开主要来源**：

- [BIS：Revises License Review Policy for Semiconductors Exported to China](https://media.bis.gov/press-release/department-commerce-revises-license-review-policy-semiconductors-exported-china)，2026-01-13；route：BIS 官方 press release HTML。
- [Federal Register public-inspection rule PDF](https://public-inspection.federalregister.gov/2026-00789.pdf)，2026-01；route：Federal Register 官方 PDF。
- [BIS Advanced Computing Guidance PDF](https://media.bis.gov/media/documents/bis-guidance-may-31-2026.pdf)，2026-05-31；route：BIS 官方 PDF。
- [Current EAR Part 748](https://www.bis.gov/regulations/ear/748)；route：BIS living regulation HTML，capture 必须保存检索日期和版本。
- [Dell FY2026 10-K](https://www.sec.gov/Archives/edgar/data/1571996/000157199626000008/dell-20260130.htm)；route：SEC filing HTML。

**可以支持**：规则版本、许可审查方向、适用目的地/实体条件，以及 Dell 自己披露的出口控制与海外运营风险。

**不可以支持**：从 NVIDIA 中国收入、Dell APJ 或国外收入直接推出 Dell 中国收入和受限订单损失；用当前 living EAR 页面替代带日期的规则快照。

**真实边界**：Dell 没有公开量化 China revenue、China AI server revenue 或出口限制导致的订单损失。A02 应把它标为公司级量化边界，而不是用 APJ 比例填空。

### 2.8 `Q8_COMPETITION_VALUE_POOL`：竞争与 OEM/ODM/组件价值池

**A01 query**：`NVIDIA AMD Intel Micron Broadcom data center revenue margin value capture`

**已打开主要来源**：

- [NVIDIA Q2 FY2027 10-Q](https://investor.nvidia.com/files/doc_financials/2027/NVDA-2027-Q2-10Q-Final-including-exhibits.pdf)；route：NVIDIA IR/监管文件 PDF。
- [Micron Q3 FY2026 Prepared Remarks](https://s25.q4cdn.com/621799436/files/doc_financials/2026/q3/Q3-FY26-Prepared-Remarks.pdf)，2026-06-24；route：Micron IR static PDF。
- [HPE Q2 FY2026 Earnings Transcript](https://investors.hpe.com/~/media/Files/H/HP-Enterprise-IR/documents/q2-2026/q2-2026-transcript.pdf)，2026-06-01；route：HPE IR static PDF。
- [Supermicro FY2026 Q4 Results](https://ir.supermicro.com/news/news-details/2026/Supermicro-Announces-Fourth-Quarter-and-Full-Fiscal-Year-2026-Financial-Results/default.aspx)，2026-08-11；route：Supermicro IR HTML；结果为 preliminary/unaudited，必须保留限定。
- [Foxconn Q2 2026 results/news page](https://www.honhai.com/en-us/press-center/press-releases/latest-news)，2026-08-12；route：Foxconn 官方 HTML。
- [Celestica Q2 2026 Results](https://corporate.celestica.com/news-releases/news-release-details/celestica-announces-second-quarter-2026-financial-results)，2026-07-27；route：Celestica IR HTML。

**可以支持**：Dell/HPE/Supermicro 的订单与 margin 口径对照、GPU/内存/网络/存储层的公司级价值捕获，以及 Foxconn/Celestica 所显示的 ODM/平台增长方向。

**不可以支持**：将公司整体或分部 margin 等同于 AI rack margin；精确拆分一柜利润由 NVIDIA、Dell、Foxconn 等各占多少；把 preliminary 数据与已审计数据无差别比较。

**真实边界**：Dell 的具体 ODM 外包份额、单柜 BOM、客户 allocation 与供应链利润分配不公开。本次未逐一 qualification AMD、Intel、Broadcom 的最新官方页，A02 应按 materiality 补齐，而不是无限扩展所有供应商。

### 2.9 `Q9_COUNTEREVIDENCE_WWC-A`：需求减速、重复下单与 backlog 风险

**A01 query**：`Dell AI server demand slowdown double ordering backlog risk competition counterevidence`

**已打开主要来源**：

- [Dell FY2026 10-K](https://www.sec.gov/Archives/edgar/data/1571996/000157199626000008/dell-20260130.htm)；route：SEC filing HTML。
- [Dell FY27 Q2 Prepared Remarks](https://investors.delltechnologies.com/static-files/a909096f-5091-4dcf-8291-019f6f9fb887)，2026-09-01；route：Dell IR static PDF。
- [HPE Q2 FY2026 Earnings Transcript](https://investors.hpe.com/~/media/Files/H/HP-Enterprise-IR/documents/q2-2026/q2-2026-transcript.pdf)，2026-06-01；route：HPE IR static PDF。
- [Supermicro FY2026 Q4 Results](https://ir.supermicro.com/news/news-details/2026/Supermicro-Announces-Fourth-Quarter-and-Full-Fiscal-Year-2026-Financial-Results/default.aspx)，2026-08-11；route：Supermicro IR HTML。

**可以支持**：发行人风险因素、交付复杂度、竞争订单趋势、供需和 backlog 兑现风险；可形成 WWC 监控项。

**不可以支持**：没有直接证据时断言 Dell 已发生 double ordering 或订单取消；把竞争对手增长等同于 Dell 份额必然下降。

**真实边界**：backlog 的取消权、重复下单程度和客户级交付表不公开。正确结论应是“存在待验证风险/监控条件”，而非制造一个确定的负面事实。

### 2.10 `Q9_COUNTEREVIDENCE_WWC-B`：margin、供应缓解、营运资本与现金转化

**A01 query**：`Dell AI infrastructure margin pressure supply easing working capital cash conversion risk`

**已打开主要来源**：

- [Dell FY27 Q2 Performance Review](https://investors.delltechnologies.com/static-files/5d15be71-1d9a-45ec-8308-8987fb41084d)，2026-09-01；route：Dell IR static PDF。
- [Dell FY2026 10-K](https://www.sec.gov/Archives/edgar/data/1571996/000157199626000008/dell-20260130.htm)；route：SEC filing HTML。
- [Micron Q3 FY2026 Prepared Remarks](https://s25.q4cdn.com/621799436/files/doc_financials/2026/q3/Q3-FY26-Prepared-Remarks.pdf)，2026-06-24；route：Micron IR static PDF。
- [NVIDIA Q2 FY2027 Earnings Call Transcript](https://investor.nvidia.com/files/content_files/TRANSCRIPT_-NVIDIA-Corp-NVDA-US-Q2-2027-Earnings-Call-26-August-2026-5_00-PM-ET.pdf)，2026-08-26；route：NVIDIA IR static PDF。

**可以支持**：Dell 分部 margin、现金流和营运资本的公司披露，以及上游价格/供给方向，可形成压力机制和后续验证指标。

**不可以支持**：把某个组件涨幅一比一映射为 Dell margin 变化；在没有库存、采购长约、定价和 mix 信息时给出精确传导系数。

**真实边界**：Dell 未公开完整 AI server 单位经济模型。任何 margin bridge/PVM 只能使用可定位输入、公式和假设，保持 `numeric_fact_authority=false`，不得伪装成公司披露。

## 3. 真实公开信息边界清单

下列项目经过来源检索后仍不能由公开材料权威闭合，A02 不应以继续加 query、放宽来源质量或让模型猜测来“补齐”：

1. **Dell 配置数量与同口径成交价**：没有同时绑定具体 AI server 配置、GPU/网络/服务 bundle、数量、成交时间和折扣的权威公共样本，不能生成权威 ASP/units/PVM。
2. **Dell backlog 组成**：客户集中度、订单取消权、重复下单、GPU 架构、地区和交付季度构成未公开。
3. **模型公司采购到 Dell 的归因**：OpenAI、Anthropic、Microsoft、Alphabet、Amazon、Meta、Oracle 的 compute/capex 证明行业需求，不证明 Dell share。
4. **Dell 实际组件成本**：DRAM、HBM、SSD、HDD、网络和 GPU 的 Dell 合同价、allocation、BOM、库存和传导时滞未公开。
5. **Dell 中国量化影响**：BIS/EAR 规则可查，Dell China revenue、AI server revenue 和受限订单损失不可查。
6. **模型级单位算力**：闭源模型训练 GPU-hours、推理流量与 token economics 未公开；厂商 workload multiplier 只能保留说话主体。
7. **ODM 单柜价值池**：公司级/分部级 revenue 和 margin 可查，但 Dell 外包份额、单柜利润分配和客户 allocation 不可查。
8. **完整部署生命周期**：announcement、sampling、production、shipment 可由厂商披露；客户现场 firmware 验收、稳定运行和 Dell revenue recognition 常缺少同一对象的完整链。

只有在正确来源和替代路由都尝试过后，上述项目才可记为 `public_information_boundary`。任何 HTTP、robots、JS、PDF parser、locator、MCP transport 或 adapter failure 必须先记录为工具/路由失败。

## 4. Dell 发行人来源 fallback 合同

A02 对 Dell 最新发行人披露必须执行以下顺序；前一路失败不允许直接宣告 gap：

```text
1. SEC accession directory / filing exhibit
   ↓ not found、HTTP、locator 或 capture failure
2. Dell IR static PDF / static Exhibit
   ↓ not found、HTTP、PDF text 或 digest failure
3. Dell IR HTML / corporate newsroom
   ↓ not found、HTTP、JS/robots 或 semantic mismatch
4. typed failure receipt
```

typed failure receipt 至少保存：

```json
{
  "topic_family": "Q1_ISSUER_TRUTH",
  "query": "...",
  "attempted_routes": ["sec_exhibit", "issuer_static_pdf", "issuer_ir_html"],
  "attempted_urls": ["..."],
  "discovered": true,
  "opened": false,
  "captured": false,
  "failure_type": "http_403 | internal_error | robots | js_required | parse_error | semantic_mismatch | not_found",
  "http_status": 403,
  "retrieved_at": "2026-09-02T...+08:00",
  "public_gap_allowed": false,
  "next_route_or_stop_reason": "..."
}
```

非 Dell topic 采用同一原则：监管/正式申报优先，其次公司 IR/官方产品页，再其次成熟行业来源；搜索摘要只用于 discovery，不可代替已打开正文。收费报告只能引用公开摘要，不能引用未取得的正文。

## 5. A02 每分支 rounds/pages 预算建议

### 5.1 计数口径

- `round` 是一次有明确子目标的 search/discovery 轮次，不是模型调用次数；同义词重复搜索不算新的有效轮次。
- `page` 是 canonical URL 与内容 digest 去重后的一个捕获文档；一个多页 PDF 算一个 capture object，但应保留页码 locator。
- 分支 `pages` 是该分支最多可消费的逻辑证据文档数；同一 Dell/NVIDIA/Micron 页面可被多个分支引用，实际网络抓取只计一次并从共享 cache 复用。
- 预算是质量充分性和防循环的计划，不是要求必须耗尽；当 material claim 已由优先来源闭合，应提前停止。
- 旧的“每分支最多 2 轮、4 页、全 run 24 页”可继续作为 soft target，但本次审计显示 Q5/Q8 需要覆盖多个独立价值层，若把 24 当不可突破的硬合同会迫使遗漏。A02 应采用 task-specific `TokenBudgetBasis`，不能为了守住低页数删掉必要研究。

### 5.2 分支预算

| A02 分支 | 建议 search rounds | 建议逻辑 pages 上限 | 证据依据与停止条件 |
|---|---:|---:|---|
| `Q1_ISSUER_TRUTH` | 1 | 3 | SEC Exhibit、Dell prepared remarks、performance review 已能闭合最新发行人事实。只有口径冲突或单路由失败时才启用 fallback；不为同一新闻稿重复抓多个镜像。 |
| `Q2_DEMAND_QUALITY` | 2 | 4 | 第一轮只找 Dell 具名客户/部署；第二轮找模型公司或 hyperscaler 官方需求背景并明确“非 Dell 归因”。四页足以形成具名样本加行业对照；没有客户绑定时停止外推。 |
| `Q3_UNITS_ASP_PVM` | 2 | 4 | 第一轮找公共采购 award/同配置数量价格，第二轮只补产品配置与组件价格边界。两轮后仍无同口径样本即冻结为 null/区间/有来源标识的 `research_calculation`，禁止无限搜索或拼装精确 ASP。 |
| `Q4_ARCHITECTURE_RAMP` | 2 | 4 | Dell、NVIDIA、Foxconn 已提供 OEM/GPU/ODM 三角来源。第一轮覆盖 announcement→production→shipment，第二轮仅补 firmware/customer deployment/revenue recognition；无法绑定同一对象时保留阶段差异。 |
| `Q5_SUPPLY_AND_PRICE` | 2 | 6 | GPU/HBM、DRAM/NAND/eSSD、HDD/网络/电力是不同供给层，四页不足以覆盖。优先 NVIDIA、Micron、待补 SK Hynix/TSMC/Broadcom 与一个成熟行业价格源；六页后仍无 Dell 合同数据即确认公司级边界。 |
| `Q6_MODEL_COMPUTE_DEMAND` | 2 | 5 | 第一轮使用 OpenAI/Anthropic 等实际 capacity commitments；第二轮补 MLCommons 或可比 benchmark，区分训练、batch inference、low-latency inference、agentic/test-time compute。不得用五份宣传材料重复证明同一方向。 |
| `Q7_EXPORT_CONTROL_CHINA` | 2 | 4 | BIS press release、Federal Register rule、BIS guidance/EAR、Dell filing 构成规则+公司风险四层。第二轮仅用于确认当前 effective rule 和 Dell 量化披露；确认未披露后停止，不用 APJ/NVIDIA 替代。 |
| `Q8_COMPETITION_VALUE_POOL` | 2 | 6 | 至少需要 Dell、一个 OEM peer、一个 direct/rack competitor、一个 ODM、GPU/内存/网络价值层；审计已证实 HPE、Supermicro、Foxconn、Celestica、NVIDIA、Micron 可达。六页后保持口径差异，不做单柜利润伪精确拆分。 |
| `Q9_COUNTEREVIDENCE_WWC` | 2 | 5 | A01 本身有两条 external query。第一轮覆盖需求/backlog/竞争反证，第二轮覆盖 margin/working-capital/cash-conversion。每个主 thesis 只需一个 source-bound counterclaim 和一个可监控 WWC；不得把“可能风险”写成已发生事实。 |

逻辑上限合计为 41 个 branch-document uses，但其中 Dell Q2、Dell 10-K、NVIDIA、Micron、HPE 等会跨分支复用。建议 A02 的去重后真实 capture 预算为：

- soft target：24 个 unique documents；
- planned budget：30 个 unique documents；
- abnormal hard ceiling：36 个 unique documents；
- 超过 30 时必须由当前未闭合的 material claim、已尝试来源和下一页预期增量解释；
- 超过 36 不自动继续，应停止并形成 typed failure/public-boundary review。

这个预算只约束网页 discovery/capture，不应被换算成固定的 13 次模型调用。A02 的 Planner、Specialist、Counter、Lead 与必要 follow-up 仍需分别形成 `TokenBudgetBasis`；页面数、输入规模和 schema 负担应成为预算依据，而不是把研究内容裁到一个预设低 token 数内。

## 6. 候选资料不自动成为 Evidence

外源状态必须保持以下单向门：

```text
search result
  → discovered candidate
  → opened/captured candidate
  → claim-level review
  → Reviewed Evidence（仅在通过后）
```

以下情况一律不得自动 admission：

- 只有搜索摘要、没有打开正文；
- 页面没有发布日期、说话主体或可复现 locator；
- 发行人/供应商的预测被去掉主体写成客观事实；
- generic hyperscaler capex 被改写成 Dell share；
- NVIDIA China 数据被改写成 Dell China 数据；
- TrendForce 市场估算被改写成 Dell 采购价；
- current Dell Exhibit 文字数字被改写成 S2 `NumericFact`；
- Foxconn/Celestica 公司 margin 被改写成 Dell AI rack margin；
- 付费报告公开 landing page 被当成已经读取完整正文。

每个 candidate 最少保存：`publisher`、`source_type`、`published_at`、`retrieved_at`、canonical `url`、claim locator、说话主体、`fact_or_forecast`、`supports`、`does_not_support`、capture status 和 content digest。计算型输入还需保存 unit、formula、assumption、input authority 与 `numeric_fact_authority=false`。

## 7. A02 proceed/stop 决策

本门给出的决定是：

- `PROCEED`：可将上述 URL 和 topic matrix 作为 A02 外源 discovery/capture qualification gold set；可修复并验证外源 adapter、route fallback、typed failure 和预算汇总。
- `NOT AUTHORIZED BY THIS DOCUMENT`：自动创建或启动付费 A02、将 candidate 晋升为 Evidence、写入 S2、完成报告或对外宣称 Dell case 已通过。
- `STOP/PIVOT`：若 adapter 无法保存 canonical URL、日期、locator、来源主体、digest 或 typed failure；若需要用不可访问的付费正文才能支持主 claim；若两轮后只能通过 Dell-specific 猜测填补公开边界。

下一合法动作仍是由主任务基于本门和 A01 adapter root cause，冻结 A02 的独立 attempt ID、clean commit、zero-call preflight、task-specific budget 与 Owner 授权；不得覆盖 A01 immutable failure。

## 8. 当前 Agent adapter 的无模型现实探针

人工找到 URL 不等于 Agent 工具已通过。主任务随后用现有 Exa MCP／static capture 做了无模型探针；这批观测没有单独的 durable replay receipt，因此只用于确定下一责任层，不能冒充 A02 preflight PASS。

- Q1 broad Exa query 返回 5 hits，2 个通过 include-domain/filter；exact accession query 找到 SEC current filing／directory。
- 同一 exact family 的短重试可返回 0 candidate，说明 discovery 结果不稳定，不能把一次命中当 route guarantee。
- Q5 supply/price probe 返回 5 raw hits，但 include-domain 后 accepted=0。
- Q6 compute demand 找到 OpenAI compute infrastructure／Stargate 等 candidate。
- Q7 export controls 找到 Federal Register／BIS official candidate。
- Q8 competition 找到 Supermicro FY26 Q4 等 candidate。
- 已知 SEC route 的 static capture 实际返回 HTTP 403；当前代码已把它记录为 `capture_http_status_403`。
- Dell IR static HTML 实际 15 秒 timeout；当前代码记录为 `capture_static_timeout`。
- 403／timeout／connection／request failure 全部明确 `failure_is_not_public_information_gap=true`；300–399 非有效 redirect 也 fail closed 为 typed HTTP status。

因此当前真实状态是：

- human source reachability：`PASS_BOUNDED`；
- Exa discovery：`PARTIAL / UNSTABLE`；
- known-route static capture：`HOLD`；
- browser／issuer fallback：尚未形成可复现 receipt；
- Agent external retrieval gate：`NOT PASSED`。

最小修正不是再写 crawler，而是按 `official API or known URL → issuer fallback → search discovery supplement → typed stop` 排序复用现有 transport，并对十类 source gold set 保存一次无模型、可重放的 receipt。其前不创建付费 A02。

## 9. exact-URL r4 bounded successor

可重放 attempt：

`Z:\FIN_Insight_Agent_qualification\dell_reference_vertical\external_exact_url_qualification\dell_external_exact_url_zero_model_20260902_r4\manifest.json`

该 attempt 对四个冻结官方 exact URL 全部得到 `PASS`，并逐 route 绑定 official URL、publisher/period identity marker、content marker、discovery receipt、capture receipt 与 captured-text digest：

| Route | 官方对象 | 结果 | 重要边界 |
|---|---|---|---|
| `E01_OPENAI_GPT56_COMPUTE` | OpenAI GPT-5.6 官方页 | PASS | 只支持模型公司算力需求背景，不能归因 Dell；未截断。 |
| `E02_TSMC_2Q26_TRANSCRIPT` | TSMC 2Q26 transcript | PASS | 只支持 CoWoS/capex/fab buildout；限定到 50,000 字。 |
| `E03_MICRON_Q3_FY26_PREPARED_REMARKS` | Micron FY26 Q3 prepared remarks | PASS | 只支持 HBM4、供给紧张与客户协议；未截断。 |
| `E04_DELL_Q1_FY27_PERFORMANCE_REVIEW` | Dell FY27 Q1 performance review | PASS | 支持当季 orders/backlog/content-rate 表述；限定到 50,000 字。 |

精确 receipt 字段为：`attempted_route_count=4`、`passed_route_count=4`、`exact_url_mode=true`、`model_calls=0`、`deepseek_calls=0`、`paid_calls=0`、`candidate_is_not_evidence=true`、`source_capture_authority=false`、`evidence_admission_authorized=false`、`mcp_promotion_authorized=false`、`production_status=HOLD`。manifest digest=`c49c3f575cdf5ad49de555bbf8fdbf71655fcd85cc9be9332368d907276ed9c9`。

“zero-model”只表示本项目没有调用生成模型或 DeepSeek；transport 为 `exa_hosted_web_fetch`，且 manifest 明确 `hosted_transport_internal_model_usage_observable=false`，不能对托管服务内部实现作无模型声明。r4 关闭的是四个 frozen exact URL 的 transport/capture identity smoke，不是十个 topic family 的完整覆盖，也不是 claim-level admission。所有 captured text 仍是 candidate；在人工 admission 前不得引用、进入 Reviewed Evidence、写入 S2 或触发 A02。

## 10. exact-URL r12 完整候选包与人工复核

最终冻结 attempt：

`Z:\FIN_Insight_Agent_qualification\dell_reference_vertical\external_exact_url_qualification\dell_external_exact_url_zero_model_20260902_r12\manifest.json`

- manifest file SHA-256=`db7eae9aaa8108faadbe7ff07404dd25414e0191b7f62af0c7a42b85a0938b94`；manifest digest=`c12d47a7a6dc9c6b5a4134c70e9916753e25d00ca494ee117e8147511f7a79df`。
- declared/attempted/passed=`12/12/12`；FIN model/DeepSeek/paid calls=`0/0/0`。
- r5-r11 的失败均保留且未覆盖：Dell IR static PDF、NVIDIA PDF 和过窄 marker 等失败先后暴露了 route 与验收条件问题；r12 只在改用可读官方 HTML／eCFR living text并把 marker 收敛到正文真实可见内容后通过。
- 12 条 official routes 覆盖九个分支：Dell FY27 Q2 SEC Exhibit、Volta 133MW named deployment、Dell AI Factory availability、NVIDIA Vera Rubin production、BIS China licensing policy、eCFR 15 CFR 742.6、HPE FY26 Q2 transcript、Supermicro FY26 Q4 preliminary results、Western Digital FY26 Q4 results、OpenAI GPT-5.6、TSMC 2Q26 transcript、Micron FY26 Q3 prepared remarks。

实现者逐页查看了正文而非只接受通过数。关键 does-not-support 边界为：Volta 不能证明 Dell revenue/order value；Dell/NVIDIA product readiness 不能证明 Dell shipment/revenue recognition；BIS/eCFR 规则不能量化 Dell China exposure；HPE/SMCI facts 不能变成 Dell facts，且 SMCI 页面明确 preliminary/unaudited；WD 只能支持 storage demand 与 gross-margin direction，不能证明 Dell HDD BOM 或合同价；OpenAI compute demand 不能推出 Dell share。

现有 MCP 的薄接线遵循：frozen exact URL 先提供已校验 locator/text；不足 `max_results` 时由 Exa primary 实时补足；全局 canonical URL 去重和 limit；有 frozen/primary candidate 时不运行 DDGS diagnostic。Q5 同分支按 route ID 稳定为 TSMC→Micron→WD，所以 `capture_limit=2` 先读最直接的 foundry/memory 原文，同时 limit=4 仍为 SK Hynix/Broadcom 等 live supplement 留位置。这个顺序不使用 query-specific issuer 规则。

r12 与 MCP 输出始终保持 `candidate_is_not_evidence=true`、`source_capture_authority=false`、`admission_required_before_citation=true`、`citation_eligible=false`、`evidence_admission_authorized=false`、`mcp_promotion_authorized=false`、`s2_write_authorized=false`、`numeric_fact_authority=false`、`production_status=HOLD`。它关闭的是 A02 candidate input 的已知官方 URL 可读性和可复放性，不是 claim-level Evidence admission、完整市场覆盖、formal 或产品验收。
