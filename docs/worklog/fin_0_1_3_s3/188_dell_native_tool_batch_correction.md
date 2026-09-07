# S3/188 — 原生多工具响应修补与后续功能验证

状态：**R11 单 Specialist 运行闭环 PASS（有界），正文语义/引用覆盖复核未 PASS。** 7真实模型/8数据动作，现有派生指标被模型自主使用，字段反馈与原文复查后补交成功。不能作为完整多Agent/中文报告/金融质量验收；不再自动开R12追求漂亮指标，下一工作包是原设计中的Verifier/Counter语义与覆盖检查。历次失败不改。

## 本轮范围与 Owner 授权

2026-09-05，Owner 要求继续修复 RC-S3-114，并进一步明确：同类明确的本地实现问题自行修复、按风险验证后继续任务，不逐补丁请求意见；扩大权限、删除数据、明显增加费用或改变产品方向才暂停求授权。

本轮只补现有 single-Specialist 的 native tool batch 流转，不改 RAG/SQL 数据、不扩多 Agent、不增加工具权限。不新增通用调度、恢复、审批框架。原始 provider reasoning 仍只保留私有审计，公开 trace 不含正文。

## 具体实现

1. SDK 的一个 AIMessage 内所有 tool_calls 原样保留；内部用一个批次决定记录它，一条模型 receipt/轮次，多个数据动作。不把四个工具伪装成四轮模型。
2. 使用已固定版本的 LangGraph `ToolNode`、`StructuredTool`、`ToolMessage`。ToolNode 的标准 `max_concurrency=1` 串行执行，薄适配复用现有 MCP ports 和来源校验，不造队列或调度器。
3. 每个调用用原始 schema、当前 context、任务路由及 source-read profile 单独校验；错误按 tool_call_id 返回。模型终止/提交不与读操作混用；缺失/重复 ID 不执行。既有预算只按实际 dispatch 计数，不暗改输入或放宽来源。
4. 下一轮 provider wire 保留上一轮原 AIMessage、实际 reasoning、该批全部 ToolMessage；历史不重复塞入全量观测，不能只返回首个调用或最后一个 observation。
5. 旧单动作与 R3 notebook/receipt 仍可读取；R6 原始文件只读。使用真实 R6 四调用做离线反例回放，另测部分失败、权限、计数、终止混用和真实 MCP 数据。

## 验证与停止条件

- 定向回归：graph、provider adapter、source-read、composition、Agent Server entry；不全仓重跑。
- 离线证明必须包含实际 SDK wire 第二轮四份结果/原 reasoning，及真实本地 MCP/SQL 反馈；离线脚本不计入真实模型指标。
- Owner 最新授权后，修复及针对性验证完成可用 fresh identity 做一次真实 enabled 功能运行，沿用原任务、权限和任务规模预算依据，不称 thinking A/B；不自动增加预算或无限重试。
- 若遇新的数据/模型研究问题，先看真实内容与最早责任层；不把工具失败当公开信息缺口，不因本地修补创建产品版本。

## 离线结果

8 个相关文件共 **115 passed in 36.05s**，不是全仓回归。新增批次专项 14 项，覆盖四读请求、一轮/四动作计数、call ID 完整回传、错误参数/action tag/context/任务路由/未知工具、重复查询、source-read 禁用、动作上限、终止混用、缺失/重复 ID 与结果错配。

真实 R6 反例来自其私有审计文件及失败后的只读 state，原参数、原 context 和四个 call ID 未改。离线 SDK MockTransport → 现有本地 MCP → 下一轮 SDK wire 验证成功：Reviewed Evidence、S2 NumericFact、源文档目录实际返回；一个模型决定形成四个实际 MCP 动作/观察，下一次 wire 的四个 ToolMessage 与原调用 ID 对应，上一轮实际 reasoning 内容保持一致且不进入 graph notebook/公开 audit。第二轮是人为的离线终止 fixture；无新的网络模型调用或研究结论，旧文件字节未变。

实现只增加宿主内部批次表示及 ToolNode 薄适配，不向模型暴露第六个工具。现有单 terminal/legacy action 路由和 R3 notebook 可读性仍通过。私有 provider 历史仍为本次进程内的 SDK history；没有借此次修改声称生产级 resume 或多 Agent 上下文已完成。

依据：[LangGraph ToolNode/工具执行](https://docs.langchain.com/oss/python/langchain/tools#toolnode)。运行中继续补充真实质量、token、耗时和来源内容检查，不以离线 PASS 替代它们。

## R7 模型前部署失败与最小网络纠正

R7 implementation=9541c03ee371577b530c44de3abd81d6c818c934，authority HEAD=6fce9eec6ddd2f1a7de8ecf67fcf4811679fb0fa。fresh execution=20260905-dell-q1-native-tool-batch-enabled-r7，project=finsight-dell-q1-paid-469df916ca70，port=18178。BuildKit kbll8j7fns3n3w76j3dzpupjc 已成功导出镜像；Compose up 在 183.922 秒返回失败，项目容器/卷未创建，模型调用=0，failed-receipt 原样保留。

网络诊断明确返回 `all predefined address pools have been fully subnetted`；现有 30 个 bridge 网络耗尽默认可用分配池，历史测试网络仍有停止容器引用。这不是本次 wheel TLS 或代理故障。诊断 network create 同样失败，未新增网络。未删除任何网络/容器/卷/镜像；此前仅停止已结束 R6 的三项服务减内存。

采用 Docker Compose 原生可选 IPAM overlay 和 launcher `--subnet`（私有 IPv4 /24），不改全局 daemon、不共享历史网络、不生成网络分配框架。人工只读核对 Windows IPv4 routes 及全部 Docker IPAM 后，10.253.8.0/24 无冲突；新 R8 使用它。CLI 选择写入部署 receipt；默认不传该参数仍沿用既有 Compose 行为。R8 的模型任务、数据、五工具、权限和预算不变，此网络纠正后继续一次尚未发生的真实功能验证，不消耗无限模型重试。

官方依据：[Docker Compose IPAM](https://docs.docker.com/reference/compose-file/networks/#ipam)。

网络/launcher 这次局部修补只重跑相关两文件：**10 passed in 0.51s**，含默认无 overlay、显式私有 /24、拒绝公网/过宽/非网段地址/IPv6；没有重复 115 项、更没有全仓回归。新运行继续走原 start-once runner，未手工复用失败 R7。

## R8 真实结果：批次已跑通，最终输出被截断

- implementation c09a478344c696fd16217be29fc763059295419d，authority HEAD d101d6b7；execution=20260905-dell-q1-native-tool-batch-enabled-r8，project=finsight-dell-q1-paid-bbc1c9bd7956，port18145，私有网段10.253.8.0/24。Compose build/up 17.328s（复用镜像层），三服务健康。run/root=01a0713f-7c5d-7763-81da-4ec9d2902056；thread=470365c6-ace3-5c24-8df4-c96944f684ee。
- 5 次真实 DeepSeek HTTP200，4 轮被 graph 接受，6 个数据动作全部成功：Reviewed、quarter-discrete SQL、instant SQL、目录、Dell EX-99.1 原文、NVIDIA 原文。模型自主采用两个双调用批次和两个单读取调用；源码权限、期间类型和引用权威区分不改。人工查看实际源块，确认返回完整表格上下文和 locator，而非仅看计数。
- 第二至第五轮的实际 SDK 输入逐轮检查：原 AIMessage reasoning 一致，返回 ToolMessage IDs 分别完整匹配 2、2、1、1 个前轮调用。没有丢工具结果或 reasoning；这些内容仍只在私有审计，不进入公开 trace/graph notebook。
- 总 input **214,277**、output **30,513**、total **244,790 tokens**；模型累计 **389.057s**。LangSmith root error、五个 LLM span 有真实成功 HTTP 响应，估费 **USD0.053608037**（非账单）。不能将 LLM span success 当整条研究 PASS。
- 第五轮输入236,988chars/75,198tokens；输出16,000tokens触发 finish_reason=length，其中reasoning10,616，函数输出约5,384。已开始 SubmitWorkpaperAction，包含实质的收入/订单/利润/现金转换交叉分析，但在 citation 清单中途截断，**无完整底稿/无金融质量 PASS**。宿主拒绝半截 JSON 正确；不是应放宽 validator 的问题。
- 原 failed-receipt.json、模型审计及只读 HTTP GET 原样下载的 diagnostic-state-after-failure.private.json（358132bytes）保留；未 resume、未修补/拼接原输出。

### 输出容量小修正与下一步

采用新配置 fin_ia_0_1_3_dell_q1_source_read_thinking_workpaper_capacity_v1_0.json，旧配置/已消费 authority 不改：联合输出32,000tokens；输入360,000chars；单轮480s。基于10,616实际reasoning+至少5,384未完成正文及实际生成速度，给完整正文/claim ledger和一次纠错留余量；仍是12轮、11数据动作、一次transport、不静默截断、不改模型/任务/权限。不是为了低成本而砍掉必要研究，不新增上下文框架。

这属于 Owner 最新授权下基于反例的本地配置修补；接着 fresh R9 做一次功能验证，部署用另一个经核对的私有 /24，既有R8服务可停止减内存但不删除。完整多Agent和正式报告仍未到交付点。

容量配置及相邻的 source-read/预算/launcher 检查：**24 passed in 37.12s**。旧16k配置和原authority保持不变；Dockerfile仅末尾复制新配置，不触发锁依赖层变化。R8结束服务已停止、全部资源保留；新网段10.253.9.0/24未与现有Windows路由及Docker IPAM冲突。

## R9：完整响应后的两个字段遗漏与本地反馈缺陷

- implementation=b6d2f83399dc5f0e32ba68829e5ac34c27c8d381；authority HEAD=e95ea681732b2dc12d68a8ddf6dcf5bb2afbc289；execution=20260905-dell-q1-native-tool-batch-enabled-r9。project=finsight-dell-q1-paid-6b23ca9bc002，port18159，subnet10.253.9.0/24。BuildKit rp75niqdos77b5w30lvofya8x，Compose build/up104.344s；容器内run420.875s。root/run=01a07158-a63f-7b82-8172-412339fddead，thread=9e40ec5f-8dee-566a-9bdd-4a2c1b1509cd。
- 4次真实模型调用，已接受3轮；工具批次3+2+2，7个数据动作成功。末轮输入200700chars/63646tokens、输出22218tokens（reasoning15719），finish_reason=tool_calls，1个完整SubmitWorkpaperAction、0 invalid_tool_calls。narrative_markdown为3049字符、16条claims；不是再次截断。
- 总输入148329、输出31789、总计180118tokens；模型累计398.896s；LangSmith root error，4个LLM span实际成功响应，估费USD0.051430137（不是账单）。完整参数不等于已接受研究，宿主仍failed/final_submission=null。
- 两个Pydantic错误是claims[11]与claims[13]的reported_fact_requires_evidence。具体为C12_Q2_WORKING_CAPITAL、C14_Q2_CASH_FLOW：原文quotation、passage ID键、非S2权威说明均在，但evidence_ids=[]。正确行为是拒绝提交并返给模型改字段，而非直接structured_parse_failed终止。源SQL/RAG结果不能背这个锅。
- 原failed-receipt、public audit、private reasoning audit不改；失败后用只读HTTP GET保存原始diagnostic-state-after-failure.private.json。另做了仅内存诊断：将那两个已有quote键作为临时evidence_ids后，既有引用验证返回0错误；未写回、未导出为修正稿、未恢复原运行，也不把此人工诊断算模型PASS。自然输出的内容质量仍须单独检查。

### 具体小修正及验证

1. 只在完整原生JSON工具调用的字段验证失败时，保留原call ID和原args，交给已存在的ToolNode；缺/重复ID、无工具调用、半截JSON和finish_reason=length仍不自动修复/晋升。
2. Pydantic字段错误以现有ToolMessage/feedback返给模型，附loc/type/msg，不带input/context/url，不泄露私有reasoning。不给模型填evidence_ids，不降低SpecialistClaim或来源校验。
3. 单独terminal调用复用原validate_submission/human-review控制路由，不发送到数据MCP、不计作数据动作；terminal与读工具混批仍全部拒绝。
4. 四个相邻测试文件 **86 passed in22.53s**，不是全仓检查。实际SDK+MockTransport+ToolNode中，缺引用字段→字段反馈→模型fixture补出错误引用→语义反馈→正确fixture提交；原R9两处错误原样进入模型下一轮wire，私有reasoning仍完整连续，测试以人为handoff结束，不当真实研究证据。另验证独立terminal、权限、原R6多调用回放及现有source/graph/provider回归。

下一步沿用新容量配置、原DeepSeek V4 Pro thinking enabled、12轮/11数据动作、只读来源权限，fresh R10做一次功能验证。R9估费约5美分，预期同规模或增加一次模型修正；不扩模型节点/工具范围、不开新恢复协议、不无限重试。普通实现问题按Owner要求自行修复和适度验证后推进；实质扩权/删除/明显费用或产品目标变化才暂停。

## R10：真实字段纠错已成立，余下为披露/上下文接缝

implementation=ac4a05232bbb47746bb07436a33513f4ad8d3219，authority HEAD=c928d01e；project=finsight-dell-q1-paid-27a98535f454/port18169/subnet10.253.10.0/24。run/root=01a0717b-e63a-7522-ba55-10507e3343f4，thread=072dd331-df36-50c6-acb7-92b731c928c6。BuildKit rcmzrivwfa0p0tbhf9m59e3vt，Compose build/up253.797s、container run553.625s。三服务healthy，无新网络/代理失败。

6次真实成功模型响应，310392input+43025output=353417tokens，累计535.095s，LangSmith估费USD0.062461998（非账单）。4轮自主选择3+2+1+1，共7个成功数据动作，工具receipt耗时合计1.301s。第五轮完整底稿中部分reported_fact错误使用numeric_authority=non_authoritative；现有Pydantic要求这些kind使用not_applicable并在authority_note说明来源。ToolNode准确返回10个字段位置，**第六轮模型自行修正，字段验证通过**，没有再中止于adapter。

第六轮引用验证仍拒绝：一处quote不是原passage精确子串；C13做了正确的4081−963=3118并绑定S2输入/来源，但未取得本地计算结果。第七轮准备输入370397chars，超过360000本地上限，**未发送第七次模型请求**。保留failed-receipt、审计和只读HTTP导出的diagnostic-state；原R10不resume/不改写。RC-S3-118获得真实闭环验证，但这不是完整研究PASS。

### 最小后续修补：不重造计算器/上下文系统

- 查到现有financial_facts executor和同一个RequestFinanceAction→MCP已支持free_cash_flow、gross_margin、operating_margin。模型能力清单却用observed_tickers过滤，错误排除没有直接存储行的derived_at_query_time指标。现在把这些既有查询能力照实披露，并带原derived_metric_rule；不保证所有期间有结果，仍允许typed gap。
- 真实只读S2/MCP验证返回Q1 FY2027 FCF=3118000000 USD，附formula_trace、两个输入fact ID、源observations、期间/单位和determinstically-derived来源状态。没有写S2、没有外源补数、没有添加第六工具；数字不是写入模型prompt的答案。
- 在现有schema字段说明和反馈中解释numeric_authority跨kind用法、如何请求已披露派生指标。只有真正查回的S2派生NumericFact才能按该来源类型引用，并说明计算来源；S2血缘不等于GAAP分类或发行人直接披露。禁止把模型自算结果改名成fact/inference蒙混过关；通用任意公式/非S2计算器仍未接入，不假称已完成。
- 新配置fin_ia_0_1_3_dell_q1_source_read_corrective_context_v1_0.json只把specialist输入字符上限从360000调为500000，依据R10的370397实际需求和后续纠错余量；32000输出/480s/12轮/11数据动作/同模型thinking/五工具/一次transport不变。不压缩或丢掉原reasoning、历史和资料。[DeepSeek官方模型资料](https://api-docs.deepseek.com/quick_start/pricing/)当前列1M-token上下文；此次撞到的是本地字符限制，不是模型上下文极限。
- 4文件72 passed in13.50s，现有authority/runner2文件10 passed in0.57s，共82定向检查。历史R6反例测试使用其冻结L0输入（测试内替换current L0构建，不改生产代码/历史文件），保持原参数/context/call ID的精确回放；新披露另做真实MCP专项，不能用current L0假装历史输入。

下一步fresh R11一次同任务功能验证，不重用R10。R9人工内容复核另发现英文草稿未满足中文交付，且误称GAAP free cash flow（原文明确为non-GAAP）；这些是需Verifier/内容复核处理的语义反例，未通过本地引用存在性校验就假称正确，也未把旧答案注入R11。

## R11 收口：单 Agent 闭环实际通过，但正文不能直接发布

### 运行事实

- implementation=44b6ef7af7dccaad1ea57ef5f801faa7d8124d6c，authority HEAD=0db33daee124c7f8eb424f1ab9059d2fa9a6b212；project=finsight-dell-q1-paid-fcbbce075df1，port18147，subnet10.253.11.0/24。BuildKit vmr866f2l9b7vjca37n1nvicq；Compose build/up256.594s，单次容器执行/验证771.109s。
- run/root=01a0719b-786a-71d3-84d8-f0b1d93fd276；thread=f7503a09-1d3d-5e52-863d-6daa6dda9f83。[实际LangSmith trace](https://smith.langchain.com/o/a8877d59-9079-4556-a411-bc1a1e2559c6/projects/p/ad1e16df-7ca2-4667-b409-3a72f9de3aaf/trace/01a0719b-786a-71d3-84d8-f0b1d93fd276/run/01a0719b-786a-71d3-84d8-f0b1d93fd276)。公开trace输入/输出隐藏，原reasoning只保留私有审计。
- 终态specialist_submission_accepted，terminal-receipt.status=pass。receipt digest=d1d577fecea02c10531b05ba5586ba03a0a617456c2cd534d809b4b0e318a402；原始file SHA=0b2eb90d8bf4c22d34fb77137130247f0ccefdae92fd40d84078229cc977b03d。此为**运行及现有结构验证通过**，不是金融语义PASS。
- 7次真实模型响应/8数据动作。第一轮模型自主选择free_cash_flow、gross_margin、operating_margin，S2实际返回公式、输入fact/source/期口径；没有将已知答案写入prompt。四/五轮提交被字段/quote检查拒绝，六轮主动重新读取原文，七轮补交接受。每次provider transport均一次，无retry/resume/fallback、无新数据/权限/模型节点。
- 第二至第七轮SDK wire逐轮核对，前轮原reasoning一致、call ID对应完整，ToolMessage数依次4/2/1/1/1/1。模型可接受工具错误并继续，但这不证明生产级durable resume或跨Agent上下文。
- tokens：input454359（cache_read391168，约86.1%）、output54865（含reasoning35625）、total509224。模型累计743.482s≈12分23秒；数据工具receipt合计1.132s。输入峰值344829chars，本轮未撞新500000上限，不能称其最大容量已经实压证明。

### 成本口径纠正

LangSmith R11估费USD0.076638619，不是账单。按2026-09-05[DeepSeek官方V4 Pro off-peak价格](https://api-docs.deepseek.com/quick_start/pricing/)（cache hit0.022/miss0.66/output1.98 USD每百万tokens）及本次真实usage复算约USD0.158944456，同样不是账单。R8/R9/R10按该费率复算分别0.104005088/0.100571328/0.127373532；原LangSmith数值保留为平台观察，不再把它当精确现行费率。模型思考/完整底稿重复生成是主要耗时，不是检索/SQL；后续优化应基于此事实，不先扩数据基座。

### 可读交付与同作者内容复核

原artifact根目录：Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/q1_specialist_paid_shadow/attempts/20260905-dell-q1-native-tool-batch-enabled-r11。

- [原始英文底稿](Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/q1_specialist_paid_shadow/attempts/20260905-dell-q1-native-tool-batch-enabled-r11/specialist-workpaper.original.md)：机械导出3502字符模型正文、thesis/mechanism、11条claim及29个原已引用ID的URL；正文逐字比对一致，没有替模型补引用/改答案，不含原始reasoning。
- [中文复核记录](Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/q1_specialist_paid_shadow/attempts/20260905-dell-q1-native-tool-batch-enabled-r11/specialist-workpaper.review.zh-CN.md)：这是同一实施作者的内容抽查，不冒充独立Verifier。

正文已有订单、收入、利润、指引、营运资金和现金转换的实质分析。抽查Q1 FCF31.18亿美元、毛利率17.75%、营业利润率8.34%与实际S2派生结果一致。模型区分了Q1 S2数据与Q2 8-K文字来源，并做实际Q2 SQL探查；不是仅有边界说明，也不是凭空编造这些数字。

但必须保留如下未通过结论：

1. 最初14条claim，最终11条。第五轮C8(backlog)、C11(Q2现金)、C12(Q2余额)有PASSAGE引用；后两条用省略号拼接不连续表格行，精确quote校验正确拒绝。最终PASSAGE引用全部消失，正文仍保留相关数字。C7的Q2订单60.9B/backlog95B并不在其最后引用的两个Reviewed excerpt中（一个是Q1材料，一个是Q2分部摘要）。它们存在于已读原文不代表最终引文绑定合格。
2. 正文/counter把应付增加和存货/应收增加一概写成吸收现金；这是因果解释错误，应付增加通常是供应商融资，且余额变化不能直接代替现金流量表影响。不能靠资料绑定就判其推断正确。
3. 最终5个numeric_fact、5个reported_fact、1个boundary，未登记重要因果推断，reasoning_summary均空；虽然私有reasoning完整保留，并不等于每个交付结论都提供了审计解释。
4. 仍为英文，未满足中文交付；外部跨公司验证只到candidate，不是完整Dell研究链。

RC-S3-121归S3语义Verifier/正文claim覆盖与内容验收，不再把这个问题变成逐句NLP规则工程。下个有价值工作包是按既有多Agent设计，让Verifier/Counter用最终正文、claim、已读原文上下文及简洁判断依据做实质复核，再回派责任Agent；不继续给本轮开R12、改阈值、人工补引文或把内部pass升级为研究/发布PASS。

### 工程收口

此前R8/R9/R10服务已停止，原容器/卷/镜像/失败artifact均保留；R11三服务保持供只读查验，不自动追加模型调用。无磁盘删除、S2写、Evidence admission、外源补源、S2或产品版本推进。本轮结束只同步文档/ledger，不再次全仓回归；最后相关代码为82项定向通过，真实R11通过上述有限运行验证。Owner的普通小修补自主推进规则已持久写入协作政策。
