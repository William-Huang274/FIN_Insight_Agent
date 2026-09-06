# Dell：成本根因、成熟外源与真实交互的顺序交付

日期：2026-09-06。产品FIN0.1.3，同分支/S3，不是新版本。源设计：`docs/architecture/research/FIN_0_1_3_DELL_AGENTIC_MULTI_AGENT_VERTICAL_DETAILED_TECHNICAL_DESIGN_20260903.zh-CN.md` §0最新顺序。起点 `e8aacc02b0c6860ba7fabf2d53a901c09150ae04` clean且与origin一致。

## Owner目标与当前范围

先查清此前约10元消耗来自试错、上下文还是prompt，再按证据优化；成熟外源必须由宿主先亲测，再通过MCP交DS；前端需真实任务/实时Agent过程/人工干预/追问，不只是换布局。Dell完整案例跑通后再做1–2个包含长任务与短问答的案例，说明任务复杂度与费用关系。允许真实DS测试及普通问题自主修复、适当Flash/Pro动态路由；不授权新框架、无限付费重试或削弱来源校验。余额已恢复（上轮只读2026-09-05T20:51:09Z available=true），旧A2保持失败，不重写资金阻断历史文件。

## 第一包：离线真实用量审计

输入仅 `Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/q1_specialist_paid_shadow/attempts/*/model-call-events.jsonl` 及同目录项目私有模型上下文；不是Codex live SQLite/JSONL。脚本 `scripts/qualification/dell_q1_specialist_paid_shadow/audit_token_cost.py`，脱敏聚合输出 `D:/temp/fin_dell_token_cost_audit_20260906_a1.json`；原始run不改。字符归因不伪称DeepSeek token归因；不导出原文、prompt或私有reasoning。

实际86 started请求、83有input/output用量、77有cache明细、76有reasoning明细；另1条R10 input_limit在transport前阻断，不能算第87次付费请求。合计input4,502,669/output657,392/total5,160,061；6个R3请求缺cache明细，3个provider失败缺usage，未知不是0。旧A01/A02 Planner另2请求/47,904tokens不在本次脚本范围；R14、RAG裁判、Codex和其他账户消费也不在此范围，不能与账户总扣款等同。

当前官方人民币价（2026-09-06在线读取）Pro空闲时段每百万cache_hit0.15、cache_miss4.5、output13.5；Flash分别0.05/1.5/4.5，高峰翻倍；北京时间工作日9–12、14–18为高峰。这86请求的时间均为空闲。依据：[DeepSeek价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)。搜索快照中旧促销美元价不能套用。

| 77次明细完整请求的费用重算 | CNY | 含义 |
|---|---:|---|
| 缓存输入2,928,896tokens | 0.4393 | 重复历史不是全按cache-miss计费 |
| 非缓存输入1,500,461tokens | 6.7521 | 新材料、首次大包、未命中前缀等 |
| 输出654,815tokens | 8.8400 | 包含推理和工具参数/报告正文 |
| 合计 | 16.0314 | 估计，不是供应商账单 |

R3已知用量在全部命中/全部未命中两端对应约0.0458–0.3647元；这意味着83次usage可见请求按当前价的区间约16.08–16.40元，不能推断3次无usage失败的账单。输入命中率在77次完整明细中约66.1%。有明细的reasoning489,510tokens，占对应thinking输出约74.8%；A5审查尤其明显，48,938/52,828≈92.6%。

| 调试/研究包 | 实际请求 | 已报告tokens | 明细可重算CNY |
|---|---:|---:|---:|
| R2–R10早期单Agent资格 | 24 | 876,563 | 2.42左右，另R3缺cache |
| R11单Agent完整工具循环 | 7 | 509,224 | 1.0837 |
| Q1审查/作者修复A1/A2/A4/A5 | 20 | 1,825,875 | 8.44左右 |
| Lead Q5/Q6 A1 | 18 | 1,047,944 | 2.1742 |
| Lead Q5/Q6 A2 | 17 | 900,455 | 1.9141 |

这些是事后描述性分组，不是相互独立的因果贡献：失败attempt里的成功调用仍有成本、也可能产出可复用研究。仅截断/解析失败/宿主payload拒绝的6次有用量请求约1.61元；大量返工发生在status=success请求里，不能只统计异常请求。Q1审查/修复反复读大包与生成长思考是主要成本之一；两次Lead失败约4.09元均没有已收集底稿，不能当成成功用户任务的正常定价。

输入字符累计约1303万，约59%是同Agent先前已经出现过的消息；这是正常多轮历史与重复包装共同结果，不是59%可省费用。系统prompt正文仅约17.3万字符/1.3%，不能说长system prompt是主因；工具schema字符未含在该分母。A5 reviewer首轮约15.1万字符是继承observations、1.88万是待审正文，另1.47万是能力/skill披露，说明高成本不能全归为工具结果上的几行JSON。

## 已做的最小工程修正

1. 既有SDK audit公开记录cache_hit/miss/reasoning计数，缺失或非法明细为null，不泄露提示词/思维链；成功和已知异常统一记录。
2. 每批并行ToolMessages保留每个结果与tool_call_id，但current_context只在最后一条注入一次；不变的collaboration正文首轮给过不再每轮重发。原文、引用、错误反馈和自己模型的完整reasoning不截断，改变的审查上下文仍传。
3. 原ChatDeepSeek客户端支持用途profile的Flash/Pro与显式reasoning effort；旧配置仍Pro/high（thinking disabled时不发effort），无router模型、无新增框架、无provider fallback。接口已实现不等于Flash金融研究质量已验证。

定向验证：成本脚本、SDK、native batch真实旧R6/MCP回放、review、Lead共104passed/19.81s；随后预算路由小修再次104passed/19.15s。这是同组检查复跑，不是208个不同测试；没有全仓回归、无新真实推理、没有重写旧run。

## 成熟方案调研裁决与紧接的真实对照

- [LangChain context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)：采用既有框架的模型选择/消息投影；若后续真有上下文压力，用原生summarization middleware资格验证，不自造记忆系统。现在没有证据需要为此迁移整个runtime。
- [OpenAI compaction](https://developers.openai.com/api/docs/guides/compaction)：支持Responses压缩，是供应商能力，不能假设DeepSeek Chat API有同样端点。
- [DeepSeek thinking mode](https://api-docs.deepseek.com/guides/thinking_mode/)：带tools的历史reasoning要完整续传，删除它既违背当前用户要求也可能破坏协议。
- [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness/blob/master/README.md)及[compaction](https://deepseek-harness.github.io/deepseek-harness/en/reference/subsystems/compaction)：MIT/官方，但developer preview并明确兼容性会变；借鉴原始日志与模型上下文分离、保持工具成对、按压力压缩，不现在再换成第二套runtime。

下一小额组件对照：从A5 reviewer第一轮的真实输入取样（无自身历史reasoning，含真实待审底稿与原文），保持相同工具schema；各一次Flash/high与Pro/low，对照归档Pro/default-high。这是已知输入的诊断，不是盲评，也不是完整Agent资格。通过现有ChatDeepSeek SDK+LangSmith请求，只观察模型下一步，不执行它提出的工具、不提交研究结果。每个节点TokenBudgetBasis：目的=比较有上下文的金融审查下一步；输入≈6–8万tokens/约19万字符真实源包；输出=合法review或合法工具请求及引用/简明理由；schema负担=现有7类以内原生工具/结构化finding；质量风险=不能漏掉重大财务误用或把可用原文说成缺口；参照=A5已归档4次审查395606tokens；profile=Flash/high或Pro/low；上限32000输出、480s、每profile1请求、不自动retry/resume/fallback，截断/非法参数保持失败；预估约0.5–1.2元合计，保守当前时段上限约1.8元（不含未知provider失败计费）。

先完成这包再接外源，前端/完整Dell/新案例仍未完成，不用本包测试数冒充产品交付。

## 第一包真实对照结果（2026-09-06 05:34–05:40 北京时间）

实现提交 `b4c8c078`，两次均经现有SDK发往DeepSeek，真实LangSmith已查到对应LLM spans；原输入187,815字符，无私有历史reasoning，工具schema相同。输出放在 `Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/q1_specialist_paid_shadow/20260906-cost-review-{flash-high,pro-low}-a1/`。`request.json`、`response.private.json`、`outcome.json` 分开保存，旧A5不改，未实际执行模型提出的工具/财务审查准入。

| 对照 | 输入 | 输出（其中reasoning） | 耗时 | 当前价重算 | 结果 |
|---|---:|---:|---:|---:|---|
| Flash/high本次 | 66,906 | 32,000（32,000） | 237.435s | 0.244359元 | finish=length，无tool call，失败 |
| Pro/low本次 | 66,827 | 15,023（13,312） | 166.143s | 0.503532元 | 合法SubmitReviewAction/no_material_finding |
| Pro/default-high归档首轮 | 66,906 | 19,730（19,435） | 历史异时对照 | 不作配对计费比较 | RequestSourceAction要求看完整Q1电话会 |

本次两者cache_hit均0，输入小差异是provider报告，不擅自修成相同token数。共2请求/180,756tokens，估0.747891元；没有第三次重试。LangSmith IDs：Flash `01a0737e-5413-73c3-b81e-ceac44771da2`；Pro `01a0737f-cae3-7362-9d42-1ffe048aae21`。LangSmith span的success仅指收到供应商响应，Flash项目结果明确为truncated，不能因trace success而伪称成功。

结论：**拒绝把大包金融终审直接切到Flash/high。** 便宜单价不保证便宜完成；Flash在这一输入上思考完上限仍无动作。Pro/low能形成有内容的逐项审查，包含Q1/Q2毛利率、现金流、GAAP/非GAAP、来源权威及反证检查，是可继续验证的候选，不是与Pro/high质量等价证明；两者下一步不同，且只一例、旧high并非同期随机对照。保留Flash在小范围资料选择/短任务的后续候选资格，复杂跨材料判断优先Pro；不继续为同一大包无限增加输出上限。接下去以真工具/真任务的总完成成本（含返工）选择profile。

当前产品增量仍为0份完整Dell报告；工程增量是用量可见、薄用途路由和重复context小修；研究资格新增2次真实模型证据，外源/Multi-Agent全覆盖/实时UI仍未完成。

## 第二包：成熟外源已由宿主亲测并接通同一个 MCP 原文工具

采用已有 `ExaHostedMCPProvider` / `ExaHostedMCPPageFetcher`，与官方 [Exa MCP](https://exa.ai/docs/reference/exa-mcp) 的 `web_search_exa` / `web_fetch_exa` 对齐；此次明确走 hosted，不启用 DDGS/浏览器/provider fallback，不引入新爬虫平台。模型未参与以下搜索、选择和检查，不把宿主已知结论偷偷注入模型。

真实宿主证据保存在 `Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/`：

| artifact目录 | 实测来源与结果 | 不能扩大成什么结论 |
|---|---|---|
| `external-live-20260906-a2` | HPE FY26 Q2 官方业绩/电话会/SEC候选；业绩页抓到19,332字符，首次保存窗口18,000明确截断 | 有同行资料，不等于已完成同行研究或与Dell数字直接可比 |
| `external-live-20260906-a3` | 微软2026-07-29官方业绩页18,098字符，16,000窗口明确截断 | 公司自己说AI需求，不等于独立证明Dell订单 |
| 同上 | TrendForce研究商城页2,015字符；人工检查确定只售卖报告，不能把店铺价格当SSD价格；另读公开2026-07-03新闻6,970字符 | 公开行业预测不是实际成交价/Dell成本，也没有读到付费报告 |
| `external-live-mcp-20260906-a1` | **真正经过既有数据composition/ToolLane/MCP `read_source_document`** 搜索并读回HPE全文窗口19,332字符；有MCP chain/URL/精确窗口；0模型调用 | 工具通路PASS，不是模型已会使用/完整研究PASS |

`external-live-20260906-a1` 仅在宿主误写分支别名时建了空目录，参数校验在搜索前拒绝，无模型/外源请求；没有删除该失败痕迹。所有实测as-of仍为2026-09-02；采集日期不替代发布日期。宿主实际读过正文、业务分部行和脚注：HPE并购/GAAP与non-GAAP、微软管理层表述、TrendForce预测与商业预览的含义需要研究Agent判断，不靠一套逐句NLP规则代替。

工程改动：`SourceDocumentRequest` 可显式选择 `source_space=web`，先search获取WEB文档ID，再read按字符窗口/offset阅读；本地默认行为不变。新的薄 `WebSourceReader` 只组合现有搜索/抓取、短生命周期locator cache、统一来源窗口；不是新索引/爬虫/队列/持久化引擎。已披露窗口和capture标识进入正常工具观察；未披露的缓存正文不是持久恢复保证，新生命周期需重搜。模型不能传任意路径/原始URL/私网地址/命令，公网guard仍在；未知ID、跨run/branch读、已知晚于as-of的文章拒绝；未知日期允许看但明确不能据此宣称as-of可用。

兼容边界：原 `CaptureReceipt` 的候选状态和 admission 标记完全不改。新增阅读能力返回既有 `SourceBoundPassage` 合同：writer_citable只表示可对实际看到的文字作逐字引用，**不表示Reviewed Evidence准入、S2 NumericFact、真实性、时间性或全文完整性已验证**。外源来源级别、非S2数字、预测/意见/推断须说明；source quote仍由本地严格校验。只对已亲测TrendForce商城增加“商业预览不是报告”提示，不自动付费或绕过权限。

许可连接到既有paid authority的 `live_external_calls_authorized`；默认/旧文件全部false，新执行才能显式true且必须source_read_enabled。Agent Server普通Specialist、Lead子任务、review子任务都从同一authority向下传，不从模型文本取得权限。旧A1/A2没有被重新开放网络，也未重写旧artifact。旧A5真实seed经定向测试仍可验证（新增默认字段不改变旧动作序列化）。

验证：70项相邻测试通过/11.25s，涵盖新reader、既有外源安全、原文、组合和paid authority；另显式host-only真实MCP网络测试1passed/8.57s；调用方Agent Server/Lead/review/SDK再跑99passed/16.81s。不是全仓回归，也不是170次真实模型调用。下一步完整Dell动态分工和研究收敛；实时UI尚未修改，完整Dell仍未PASS。

## 第三包提前明确：完整覆盖的研究执行，不再用两主题代替完整产品

沿用同一Lead图、Send、Specialist tool loop、SDK、MCP、Agent Server、Postgres/Redis与LangSmith，只将新执行的研究义务扩为既有Q1–Q9。原two-topic authority仍只两项。Q1复用已审A5，其他八项须实际交研究底稿；当前worker task仍一项覆盖义务，Lead可命名不同角色、安排依赖、在看到结果后追加任务，不硬编码九种Agent类。最多12任务（八个新义务+有意义的后续）、并行2、Lead12轮、worker16轮/24工具；数字是异常停止上限，不是必须做满的绩效指标。

本次真实run的完成定义仅是全部覆盖的**research_ready_for_review**，不能因此标金融或完整产品PASS。下一仍必须跨主题Counter/语义Verifier→具体责任修复→综合报告→最终审查→人工产品验收。UI继续接同一Agent Server，不再造队列/消息总线；本包不伪称前端已完成。review prompt从硬编码“只审Q1”改为实际assigned task scope，旧Q1仍不被其他主题要求阻断。

模型配置 `fin_ia_0_1_3_dell_full_research_pro_low_v1_0.json`：复杂研究暂全部Pro/low，自己完整reasoning/history保留；没有router LLM，也不让Flash大包失败后偷偷fallback。Lead500k输入字符/24k联合输出/480s，worker500k/32k/480s，各一次transport、无retry/resume/fallback。依据A2 Lead12,278输入/8,412输出及两位worker的真实规模、Pro/low本次审查诊断给余量；非质量等价证明。counter/planner旧配置不在此研究run执行，独立审查运行前另按实际整包大小选预算。

成本预估是首次全覆盖研究资格而非产品定价：约40–70次请求、约6–12元量级具有较大不确定性（输入缓存、检索次数、思考长度都会变化）；不承诺一次短问答也需这些费用，不把财务缺漏静默删掉来压成本。若连续重复无新增信息、工具/模型截断、宿主错误、余额/未知provider结果，则保留结果并停在责任层，不无限重跑。每次模型请求的实际cache/reasoning/费用素材继续入账。泛用任意公式计算器尚未暴露；可以用已有S2派生指标和带来源的报道值，不能冒充任意算术已被本地验证；后续研究若确需新增计算，处理为具体工具能力问题，不能说成公开信息缺口。

前置检查：78条scope/Lead/entry/review检查通过，新增完整九义务调度测试证明Q1 seed不可假充其他八项、不会重新调用Q1；真实九分支同一数据组合均可打开（另2passed/7.52s）。新paid authority在实现提交后单独创建，不重写旧A1/A2；保持同FIN0.1.3/S3，无formal/发布。

实现 `35d68dfb61b4142b680846104f40ca62ea799275`；最后组合130passed/1skipped（显式网络probe）/21.94s。新执行 `20260906-dell-full-research-web-a1`，authority `389f734175250541d48e4123b47aaf9b4eadf8ce76d141a196bde397b255f0a4`，全新Compose project `finsight-dell-q1-paid-389f73417525`、端口18165、拟用已查未占用子网10.253.28.0/24；旧容器/volume/失败证据不删除。本段是启动前记录，不能当执行成功收据。

## 全覆盖研究 A1 真实失败与责任层修正

`20260906-dell-full-research-web-a1` 已终止，非网络/余额故障。Lead第一次请求13,241输入/12,078输出（10,792 reasoning）/132.502s；计划Q2/Q3，但把 `route:Q2_DEMAND_QUALITY:required-reviewed` 一类资料路线ID填入 `coverage_obligation_ids`，本地正确拒绝。第二次25,431输入/24,000输出且全为reasoning/253.214s，finish=length，无修正动作。合计2请求/74,750tokens，缓存25,216/新输入13,456，按空闲价估0.5513874元；0已注册任务、0新Specialist、无底稿/报告PASS。容器运行约401.234s，build约100.906s，不混入模型时间。Agent Server thread `1e4aad37-1135-569a-81c5-fb6c6bf5d9a3`，root `01a073ae-c89b-7b33-aa8d-7fbac3e2cc98`。失败state/私有原始消息/用量均在原attempt目录保留；host session48436已exit1。精确三个实验容器已停止，卷/镜像/证据保留。

核查真实SDK `_get_request_payload` 确认Pro/low参数确实发送且符合DeepSeek官方位置；不能说参数漏传，也不能证明provider内部一定执行了何种计算。最早项目问题是语义编号说明歧义、错误反馈不够可操作；后续失败是长思考用尽输出预算。已补schema/Lead提示区分branch与route，并让拒绝返回合法ID列表；不改写模型参数、不放松范围。既有用途profile可选择thinking开关，自己的原始消息/已返回reasoning仍保留，不换runtime、不加fallback。

下一至多两次小额组件诊断：从本次失败的Lead第二轮真实messages取样，保留其自己的第一轮模型回复/reasoning与实际错误反馈，只使用修正后的当前Lead系统说明；Pro/disabled一次、Flash/disabled一次，工具schema相同。用原 `compare_review_model_once.py --task lead --source-turn 2`，各一个provider请求，不执行所提工具、不启动Specialists、不晋升旧A1。TokenBudgetBasis：purpose=同一Lead修正任务分派；input=约79k原始审计字符/上次25,431输入tokens，当前系统说明小增量；outputs=一个合法规划动作、研究目标/验收/依赖/简明理由而非完整报告；schema=已有三种Lead工具且覆盖ID必须来自已披露Q1–Q9；risk=不能丢研究义务、伪造worker或把路线ID当主题；comparable=刚才2次/74,750tokens/0worker、第二轮24k全思考；profile=原生non-thinking，多轮消息仍保留；max_output=6,000，timeout=480s，每profile1次、retry/resume/fallback均无，截断/非法仍failed。不把6k用于专家报告，当前价保守合计约0.3元量级。先验证下一动作与实际本地范围绑定，成功也只是调度用途资格，不是全任务质量/等价或Dell产品PASS。
## Lead 用途对照已完成：非思考调度，不削减专业研究

实现6de1cf73，两次同实际错误上下文/当前字段说明：Pro/disabled14,742输入+936输出=15,678tokens、9.068s、估0.078975元；Flash/disabled14,742+1,061=15,803tokens、5.938s、估0.0268875元。合计31,481tokens/约0.1058625元。两者均单次DelegateResearchTasksAction，精确current context/合法Q2和Q3 IDs；人工看了完整任务目标、success criteria、工具能力和简明理由，原研究问题未删、无伪造worker。旧原始tool feedback和自己的reasoning在审计messages里原样保留；非思考请求的provider输入较原第二轮少，不能擅自把这种provider计数差异写成我们删除了历史。reasoning计数未报告，记null，不冒充报告0。

真实LangSmith spans已读取：Pro01a073c4-bfbf-7c60-b5ec-da52096c8d5e，Flash01a073c5-b16d-7d80-841c-01d819340f9f；两者有end_time、error=false且token对应。目录为Z资格根q1_specialist_paid_shadow/20260906-cost-lead-{pro,flash}-disabled-a1。只有修正下一动作资格，未实际运行workers/完整综合；不把独立异时小样本当等质统计证明。

下一采用配置fin_ia_0_1_3_dell_full_research_routed_v1_0.json：Flash/disabled Lead，Pro/low thinking-enabled Specialists，按可信用途选择既有SDK client、不多调用router；Lead8,000输出可容纳最多12任务的目标/依赖/验收和研究交接（本次2任务只用1,061），专家仍32k/480s/500k输入字符。任务数/覆盖/工具/网页权限不扩；独立财务审查仍需Pro另验。完整研究是该混合配置的首次收敛资格，不是已通过的质量/成本保证。

旧Project OS CLI仅认识历史fixed-pack/R系列decision，不能冒称认识新Agent Server authority。只为现有命令加薄分流：当前schema直接复用现有runner Git/authority校验、现有Pydantic/config绑定与thinking-budget一致性；旧decision继续旧校验，不重签历史失败、不造第二套权威或清除全仓红灯。实际data/MCP/身份preflight仍由Agent Server在模型前做。新authority在实现commit后冻结，随后先跑该CLI和现有runner，失败不越过。

## 全覆盖 A2 已结束：七份新底稿保留，只补 Q8

实现5f398792、authority提交692c952a；execution `20260906-dell-full-research-web-a2`，root run `01a073d0-73d0-7a53-85cc-cd80f85ff455`，thread `d1904951-438d-5f66-b221-69aed21a4631`。真实68次请求均有usage，合计2,999,396 tokens，按模型/当时空闲价估6.625332元，不是账单。Lead Flash7次约0.114303元，其余Pro研究；没有provider传输失败。宿主1935.079s（约32.3分钟，构建90.5s另列）。没有完整研究handoff、独立全案审查或最终报告PASS。

父图收回Q2/Q3/Q4/Q5/Q7/Q9六份。Q8最后534,978审计字符超过本地500k启发式上限，在第十次准备请求前阻断（未发provider）；这不是DeepSeek上下文窗口溢出、余额或网络故障。此前Q8三次内部context哈希错误、一回非法JSON、后续十个引句不匹配导致修订。Q6并行被父图取消，但原生PostgreSQL checkpoint已真实保存 `specialist_submission_accepted`/12claims，按官方JsonPlusSerializer只读导出并通过既有validate_workpaper_state。原父图failure不改，也不把提取底稿说成原父图成功。现在有七份新底稿，加已审Q1，共八个研究面；只缺Q8。Q6/Q8只读导出在 `Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/20260906-full-research-a2-recovery/`；没有重启旧任务或改数据库。

内容人工抽看：Q2真实使用了外源客户/媒体，Q4区分部署与未来架构，Q5比较毛利率与经营利润率；但存在因果过强、Q1/Q2时点不齐、部分英文、公司/第三方转述不等于独立客户确认等待复核项。Q5还正确披露电话会源读取故障；不能把本地故障说成公开不披露。原稿和来源保持；这些不是已通过的语义审查。

### 下一最小实施包（先本地反例，再仅Q8真实运行）

1. 内部context绑定从“模型复制64位字符串”移回可信SDK调用上下文；新配置显式启用，旧配置/回放不变。采用[LangChain ToolRuntime的宿主注入原则](https://docs.langchain.com/oss/python/langchain/tools)，provider schema不再要求内部字段，原始返回保持私有审计，FIN仍校验真实call/上下文/权限/数据/引用；模型不能选择别的上下文。
2. 修提交拒绝反馈的重复源注入：旧原文已经在native历史中，报错时不再额外复制最后一份来源。自己的reasoning、真实工具结果与错误均保留，不做自造摘要或静默截断。
3. 已知模型预算/供应商失败走现有终止handoff，让LangGraph保存该分支状态、其他独立分支正常结束；意外身份/合同损坏仍抛错。无自动retry/fallback，未完成分支不算覆盖。
4. 只补Q8的fresh研究任务，已完成七项/Q1不重跑。Q8曾读多公司多期间约291k工具结果字符，534,978是包含自己的思考/两份草稿/SDK元数据的本地计数；为本任务设700k输入字符余量而非再次被任意字符阈值切断，仍32k输出/480s/16模型轮/24工具。此为任务规模修正，不是压缩省token证明；引用错误必须模型自己修，不能弱化validator。预算/新authority在本地反例通过后冻结。

前端等待期间已实际在Z隔离环境安装 `@langchain/react1.0.35` / `@langchain/langgraph-sdk1.10.2` 并测试当前真实Agent Server。新v2 transport两次只握手200、0事件，不能算通过；同官方SDK经典 `threads.joinStream` 两次连回均读到实际specialist/collect/lead/lead_tools事件。采用已测接口，不自造消息总线。UI仍未接入/渲染、未提交或取消任务；正式集成留在研究收口后的下一工作包。

### Q8 定向 A1：provider schema 暴露了执行器不支持的输出类型

实现a9c4ee81、authority88e46797，`20260906-dell-q8-targeted-completion-a1` 已failed，2次Flash请求33,776tokens/估0.0594796元，0新Specialist。第一轮754输出/8.477s生成有内容的Q8任务，但generic ResearchTaskSpec允许 `verifier_finding`，当前worker只实现三个研究产物，因此正确拒绝却只有含糊错误；第二轮误陷入“为何Q8只有Q1权限”的重复自然语言（不是隐藏thinking），8000输出/61.915s截断。没有通过增加token或掩盖任务错误推进。第一轮也已证实新provider不填写context_digest，宿主正常绑定到真正执行器，说明这次失败与哈希注入无关。

最小修正：provider专用 `DelegatedResearchTask` 继承原领域任务，只缩窄为实际已支持的planned/ready和branch_notebook/narrative_artifact/claim_ledger，不新增研究规则；公共ResearchTaskSpec不动。Lead只看真实存在的shared capability refs和访问边界，不误收Q1 seed专属ticker/topic/route完成标准；每个worker仍从原组合领取真实的分支披露与权限。拒绝信息附真实allowed values。86条相邻测试通过，包含不可变Q8第一轮反例的准确字段失败，不伪称历史任务被修成成功。原失败/成本保留，三容器停止、卷不删；下一同scope fresh Q8 A2、不增加任务、预算、模型或权限。
