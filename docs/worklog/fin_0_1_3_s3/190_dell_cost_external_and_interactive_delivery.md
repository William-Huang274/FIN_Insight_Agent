# Dell：成本根因、成熟外源与真实交互的顺序交付

> 最新状态：2026-09-06 A3已关闭；见文末“A3收口与真实审阅Workbench”。历史下一步不得用于重启已消耗attempt。

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

## Q8 定向 A2 收口：九个主题均有底稿，不是完整 Dell PASS

`20260906-dell-q8-targeted-completion-a2`，实现 `cff85e2850ab563c4c1da8517887f5eddbdd83c1`、authority提交 `2c8fc7e3aa599b6bc1b0b230edd6995f3c3061ef`，真实终态 `research_ready_for_review`。Lead自主分为同行价值捕获、可比性/架构与营运资本反证两个独立任务；不是固定两种类，也不是两位独立终审。两份底稿分别提交，引用失败有正常反馈和模型修订；没有重新调用已保存的其他七主题/Q1。父图成功范围仅Q8研究交接。

| 本次实际 actor | 请求 | tokens | 当前价格估算 CNY |
|---|---:|---:|---:|
| Flash/disabled Lead | 3 | 72,393 | 0.0720837 |
| Pro/low 同行价值捕获 | 6 | 235,202 | 0.7668216 |
| Pro/low 可比性与反证 | 9 | 553,140 | 1.1397798 |
| 合计 | 18 | 860,735 | 1.9786851 |

18次均有usage；758,270输入/102,465输出。宿主执行808.547秒（并行模型累计1,181.082秒，不能当墙钟），构建98.359秒另列。Agent Server thread `1e5bb09b-98db-5fdb-85e8-b90c2d68d027`，root/LangSmith `01a0740f-fa63-7383-93f4-1f2989962163`，project `finsight-dell-q1-paid-cc5167c4feec`、loopback18144。terminal-receipt和private state在原attempt目录，session98928已exit0。三个精确容器已停止，卷/镜像/源结果均保留。较早full-A2和Q8-A1的失败仍是失败，没有改成PASS。

累计审计更新 `D:/temp/fin_dell_token_cost_audit_20260906_a3.json`：attempt目录176个实际请求，173个有usage共9,128,718tokens；167个有cache细项的估价25.2462955元，另外6个旧请求缺cache拆分、3个provider失败缺usage，不记0费用。另有4次独立用途诊断212,237tokens/0.8537535元，不在attempt目录；合起来180次实际请求/9,340,955已报告tokens（仍有3次未知）。这些包含历史试错、审查返工、不同配置对照，不是“一次正常提问”的价格，更不是DeepSeek账单。新增Q8这次的1.98元也不能充作全Dell最终成本，尚未做全案审查/报告。

## 人工看稿后的实际问题：先承认语义缺陷，不用来源格式PASS替代质量

已看十份原稿中的实质结论（不改写原稿、不把人工看法作为盲测gold）：Q6把orders/backlog称为“实际使用量”，并从管理层/供应商表述推出效率提升“不降低”单位需求，证据强度过头；Q7从“单个外国国家<10%”推“大中华区合计<10%”不成立，且把已找到新闻稿/旧规则当当前法律状态的把握不足；Q8以不同业务组合毛利率直接定位整个价值池、只比较应付分别大于存货/应收就宣称融资效率优势，也需要财务方法复核。还有各主题财年/季度不齐、未搜完与不披露混淆、Q3/Q4英文的问题。Q9是反证主题研究，并非独立Counter。下一审查必须主动检查这些类别；不能只查112条claim是否能复制引文，也不能偷偷把人工答案注入独立reviewer再宣称其自行发现。

## 最小工具修正与全案按需上下文（不新建执行框架）

1. **长文阅读**：原WebSourceReader只抓50,000字符却允许请求更大offset，越界抛MCP异常。现仍用同一[Exa MCP web_fetch](https://github.com/exa-labs/exa-mcp-server/blob/main/src/tools/webFetch.ts)，host抓取上限200,000，模型默认24,000/上限80,000窗口不扩大，越界返回实际captured-text边界和可操作说明，不声称全文完整/公开不披露。真实宿主同MCP搜索并读原Q7 Federal Register `2023-23055`，成功读取offset50,000之后24,000字符；证据 `Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/external-long-source-mcp-20260906-a1/`，0模型。这只证明长文工具已可用，不证明旧规则当前有效或全文已完整抓取。
2. **旧两次搜索限制**：新live-web native profile的模型method视图去掉历史workflow `scope_ceiling`，明确使用当前图实际max_model_turns/max_tool_actions。研究方法、公开来源/时间/只读权限不变；原foundation及历史digest不改。旧Q7/Q8的“两轮用尽”是真实历史受限，不能继续作为新review/修订的硬上限，也不是公开信息缺口。
3. **计算采用成熟组件**：[simpleeval](https://github.com/danthedeckie/simpleeval) `1.0.7` / MIT / 无额外运行依赖，已在Z隔离安装和本项目agent-runtime extra固定、uv.lock仅新增该包。标准库Decimal作34位十进制运算，simpleeval解析/求值，仅配置算术节点/四则和有界输入；不实现新表达式引擎。S2变量从已观察NumericFact直接读本地值；非S2变量必须有原文逐字quote及其中的数字literal；无来源变量必须标假设。返回公式、输入、结果、假设、来源与权威提醒。运算正确不等于单位/期间/提取含义/经济因果已验证；一律不升级S2、不改数据库。经真实官方MCP client复算同期间Dell FY2026 gross_profit/revenue*100，与既有S2派生gross_margin精确一致；包括错误S2值、伪引文、数字子串、缺来源/假设、未知源、代码/属性/函数/幂/移位/分号/除零等反例。没有声称DS已调用此新工具。
4. **研究包不是新lineage库**：`collect_research_bundle.py`只读四个明确源artifact，保留原phase/来源文件路径和一次性digest，不改旧run、不复制私有模型messages/reasoning到其他Agent。所得十份底稿/九主题/112claims/179个paper内来源（非去重独立信源数），在 `Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/case-convergence-20260906-a1/`。原底稿/工具观察合计2,910,278字符；模型目录6,396字符，全部底稿正文视图141,466字符，来源按ID/窗口再读。**这是信息组织规模测量，不是已节省相同比例tokens/费用的因果证明**。官方MCP服务器新增可选host注入的catalog/read-paper/read-source/calculate四工具，旧单分支server默认不获得跨稿权限；精确引用/未完成路线/非S2权威边界保留。工具已经代码集成并经实际MCP client测试，尚未接到下一Agent Server模型图，前端也尚未使用。

### 下一工作包的实施边界

先将上述按需工具接入**现有Agent Server内**的全案审查：同LangGraph/原生ToolNode与消息/checkpoint能力，同DeepSeek SDK和LangSmith，不另造队列、上下文引擎、跨代理私有CoT转发或另一个HTTP服务。Counter/Verifier从目录与各稿结论开始，自主按需读稿、读原文、S2/计算、必要补源；反馈指向paper/claim/原文锚点及责任层。仅有实质问题的作者收到相应反馈和资料，产生新revision，不重跑其他研究、不把预算停止伪称信息不披露。接着综合中文报告与最后审查/人工验收；最终报告的自然语言不靠僵硬全文NLP模板校验。

下一模型预算必须按6.4k目录、141k全部正文和按需来源规模，而不是把2.9M字符一次塞给每个reviewer；参考本次复杂Q8 6/9调用和已知大包Flash失败，复杂语义审查先Pro/low，简单调度仍Flash/disabled，不能假称两者等质。具体node TokenBudgetBasis与一次真实执行范围在代码/近邻检查通过后记录，不复写旧authority。当前本包没有新付费run。真实交互前端仍下一独立包：接同Agent Server的标准thread/run/stream/cancel/HITL，并投影公开决策摘要/工具/来源/usage；不能把私有模型reasoning直接公开，也不能用静态播放冒充可运行。Dell完成前不启动新case。

## 全案原生审查循环实际接入（2026-09-06；真实模型执行前）

采用官方 [LangChain create_agent](https://docs.langchain.com/oss/python/langchain/agents) `1.4.0` / MIT；先Z隔离安装与检查，再正式只新增这一项依赖，既有LangGraph1.2.11/core1.6.1/MCP2.1.1不升级。`langchain-mcp-adapters0.3.2` 的解析器实际拒绝与MCP2.1.1组合（要求MCP>=1.24,<2），因此该候选只留Z实验、不进入正式依赖、不降级MCP。最新 `langchain.mcp` 是依赖FastMCP的beta入口，本次不再迁移传输层。保留已资格通过的官方MCP2 Client，用小型schema→StructuredTool映射；传输、工具循环、错误配对、消息、并行、checkpoint仍由成熟库负责，无新HTTP服务/队列/上下文摘要系统。

`dell_case_review_agent.py` 实际接同Agent Server与原once runner，新增 `case_workpaper_review` 仅执行Counter/Verifier全案独立审查。两者从同一已冻结目录开始、自主读取十份底稿/来源；通过静态可发现的RunnableSequence子图分别保存native messages，不向对方或父图公开私有reasoning。提交工具只校验实际读稿覆盖、paper/claim ID、原文精确quote；语义由模型审查，不将自然语言全文模板化。错误提交留在原生工具循环让模型修正；正常结束却未交review明确为incomplete。原生ModelCallLimit/ToolCallLimit控制有界执行，不写新计数器/重试器；SDK不retry/fallback，截断/未知结果保留审计并停止。

任务预算已在 `fin_ia_0_1_3_dell_case_review_native_v1_0.json` 写入：两位均Pro/low，最多各24次模型/64工具、700k输入字符启发式（包含工具schema，不将仅checkpoint保存的ToolMessage.artifact再算一份模型输入）、32k输出/480s。十次读稿可并行调用，剩余用于抽查原文/数字/计算/反馈修正；不是要求把整案压为13调用。按已有任务规模估本次两位合计约2–5元，实际不确定；运行中查看真实usage/反复行为，不因便宜强切Flash，不自动整案重跑。授权沿用Owner已充值并允许完成全Dell和常规故障自修，不包含公开发布、S2写、Evidence admission。旧authority的Q1字段仍仅引导已有身份入口，新增case scope和真实目标明确为全案；审查角色不得冒充Lead/作者修订/报告交付。

真实本地数据已通过新原生工具投影读到本地文档目录与DELL FY2026 S2 revenue，bundle与当前case/snapshot/foundation/Owner数据门逐项一致。开发实测暴露MCP financial granularity原本只有str、错传annual后仅报opaque error：已将MCP参数改为领域原有六个Literal值并将requested_unit改为既有合法值，让模型直接得到正确schema，不改SQL/值/会计规则。calculator目前明确只解析归档Pxx:Sxxx；新查询S2/新网页仍可读，但尚无自动加入该计算器的原生观察绑定，不用假设绕过，实际需要时作定向适配。

验证：124项相关检查通过/11.75s，最后新增binding/原生schema检查6passed/5.28s。真实MCP2+两位零provider模型的并行多轮测试，10稿读取、错误source反馈、calculator、错误quote→修正均成立；native checkpoint中两份自己的reasoning各自完整、父图无私有messages，get_subgraphs能发现两者。真实ChatDeepSeek SDK+MockTransport双轮验证native function对象schema、10个tool_call_id配对、原reasoning_content原样续传、cache/reasoning/usage公开统计与私有文本分离（这是mock usage，非新增真实花费）。schema/state-read入口不打开资料/模型/credentials。开发失败另有partial coroutine类型注解和Python3.11 TypedDict来源，均在模型前修复；无用paid调试这些问题。

当前是**工程已接入/宿主已消费，DS全案语义尚待下一次fresh执行**。本轮不重跑九主题、不更改任何原稿；全案review出结果后才逐责任修订与中文报告。native模型消息的真实Postgres恢复/前端干预尚未资格证明，不把内存测试称为生产resume能力。

## 全案原生审查 A1 实测完成；仅定向作者修订与报告待做

实现738ff3ff、authority提交c39918a5，execution `20260906-dell-case-native-review-a1`，root `01a07462-90c3-74d2-82ac-54a9ca6fdb1f`，thread `2cb315d3-f50f-5a10-bb2c-abdf6acce4c1`。两位独立native Agent提交中文全案审查，终态 `case_review_ready_for_convergence`。**仅独立审查交接，不是底稿已修、报告或产品PASS。** Counter14次/893103tokens，Verifier10次/674187tokens，合计24实调/1567290tokens/52工具动作（含提交）。实际执行473.5s，构建启动158s另列；模型耗时累加882.01s因并行不能当wall time。LangSmith根已关闭，error=false，实查total_tokens一致。

按已核定当日价格估1.9244712元（非账单）：缓存输入0.2007552、新输入0.6833655、输出1.0403505。1490227输入中1338368为cache hit；77063输出中51177为reasoning。累计attempt目录审计200请求/197有usage/10696008tokens，191项有cache可估27.1707667元；另四次目录外诊断212237tokens/0.8537535元仍须单列，旧三次未知用量不能作0。新审计 `D:/temp/fin_dell_token_cost_audit_20260906_a4.json`；原始证据不改。这是开发/修复/审查累计，不是一次普通问答成本，也无等质对照省费比例。

Counter3条material涉及P05/P07的Q1毛利方向与最新Q2对照、P04把量产未开始误作从未交付；Verifier重复发现P04一条material。计数4含重复，非四类独立错误。P01调整后FCF加回不完整、P06单国<10%不等于Greater China合计<10%为两条advisory。宿主读审查全文再次发现：Verifier竟把订单/收入/backlog称为actual usage，Counter也未严格指出P08这一混淆；模型终审并非oracle。下一把P08与P06的逻辑问题作为**显式host-assisted补充意见**，不得伪称盲审已发现或模型全案无误；Q8全公司毛利不是完整价值池份额、客户首套交付不是规模利用率等同样传给最终写作/核验。

原生state实证：同一真实Agent Server `state?subgraphs=true` 两子图均可读；官方JS SDK1.10.2用两个fresh client重开得到counter/verifier独立PG checkpoint和自己的messages。Z实验 `workbench-stream-sdk-20260906/result-native-case-state.json` 只保存元数据，不导出私有reasoning。旧factory child state400问题在此新原生入口不再复现；这只证明子图持久化状态可读，**不证明进程重启后续跑、HITL或前端实时交互**。本次只订阅父updates，前端需要下一新run通过原生stream_subgraphs得到子节点事件，不新造总线。

本次5次提交退回：Counter3个引句错误依次发现，Verifier1引句+1claim ID。已在同validator最小修为一次返回全部独立错误，不放宽exact quote/ID/读稿覆盖。成本审计兼容native分开的request/response事件，修复之前response覆盖request使字符归因缺失（usage成本本身不受影响）。17定向测试通过/9.27s。旧A1所有失败反馈保持原样，未为这两个小修整案重跑。

### 下一有界实施：六份责任修订 → 中文综合报告 → 终审

复用同create_agent/MCP/Agent Server，不复活手工模型循环。只给P01/P04/P05/P06/P07/P08的责任作者其原稿、对应反馈与按需来源；P02/P03/P09/P10不再做研究重跑。作者提交带来源的修改与处理反馈说明，保留原稿和revision；不允许将审查意见当原证据。Writer在修订稿/原源上自由组织中文报告，覆盖九主题并直接回答主问题，重要事实/推理引用可回原片段，非S2数字显著标注但正文不沦为边界说明。Verifier另有独立上下文读报告与资料/修订原因，允许质疑作者和两位前审，不以字段合法充当语义通过。

预算依据：A1两角色14/10轮、8分钟、1.92元；单篇定向修订首屏约4–20k字符，预计每篇3–8轮，保留Pro/low，最多12模型/32工具/500k字符/24k输出/480s；Writer全案约141k字符按需读取，最多16模型/48工具/700k/32k/480s；终审最多16模型/48工具/700k/32k/480s。修订按原生图并行2，不启动新研究Agent；估全收口3–7元，非固定报价或质量保证。任务特定TokenBudgetBasis必须进入实际配置。硬错误先本地测试，模型截断/未知结果停止不重发；不因费用删去主题，不无限终审。若终审仍有重大问题，保留报告草稿并只按责任修复，不能宣称完整casePASS。UI下一工作包，新case仍在Dell通过之后。

### 定向修订/综合报告实际接入（真实运行前）

`dell_case_convergence_agent.py` 在同create_agent/MCP/StateGraph入口新增六份责任修订实例、Writer、Verifier；这是新的公开底稿交接上下文，不冒称resume原作者旧私有思考。静态原生子图两两并行三批，collect只传source-bound amendment与公开处理说明；自己的native messages留独立checkpoint。没有新队列、retry、provider transport或泛化任务协议。新MCP2与框架API已按官方文档和本地库检验。作者可据源反对审查意见，不把host反馈当gold；P08需求proxy与P06地域边界明确标记host-assisted。

原稿不改，新增当前视图合并claim_updates/删去显式旧claim，并同步替换thesis/mechanism/narrative等正文；变化的kind/numeric authority沿用既有SpecialistClaim，引用逐字验证、错误一次返回。新工具观察只传可引用源/数字，不传私有reasoning。Writer只能读当前workpaper入口，避免无意引用被替代的旧正文；报告自由中文，仅强制合法[Pxx:claim_id]引用可解析，不用自然语言模板判断真假。终审输出material或未解问题则留下needs_revision，否则ready_for_human_review，均不自动productPASS。原始bundle新增只读派生 `case-convergence-20260906-a1/convergence-input-a1.private.json`，10稿、6责任主题、host-assisted=true；旧review/失败run不变。

130近邻测试/13.63s；最后六项包含实际A1反馈/旧authority原digest兼容、source权限、未知引句同时退回、六作者→写作→终审、原稿不变/当前引用可解析、private上下文独立、报告仍需修改分支与只读schema入口，6pass/5.44s。一个fixture模型签名不符合异步BaseChatModel调用，已在本地修正，无付費试错。此时fresh模型运行未启动；后续事实见下节。

## Convergence A1 格式反馈失败；保全五份修订后仅补剩余角色

实现c7755cc5/authority a8b76b8b，`20260906-dell-case-convergence-a1`已failed，root `01a0748d-ea18-78a2-bba7-fe72e3b931a1`、thread `b981f76b-cbad-52e6-8804-d1f17b2cc227`。19次实际调用：P01/P04/P05/P06/P07/P08各3/2/5/2/3/4；tokens各84421/44097/144000/37564/83235/118964，合512281（424252输入/88029输出、51598reasoning）。估1.9249047元=0.696078新输入+1.1883915输出+0.0404352缓存输入，非账单；缓存269568、miss154684。执行630.719s/构建106.907s；无provider未知/网络失败。LangSmith根实查失败闭合、total_tokens一致。公开audit的success19仅指provider完成，绝非19个任务成功，后续明确拆出valid/invalid tool count。

根因：P07最后一次返回只有一个`invalid_tool_calls`，工具参数JSON在char10934出现Extra data；`create_agent1.4.0`的普通路由只看tool_calls，故错误结束、collect抛`case_agent_ended_without_submission:author_P07`，Writer/Verifier均未开始。原始参数/私有reasoning/failed-receipt保留，不手修模型JSON来假装提交。此问题有[官方仓库issue33504](https://github.com/langchain-ai/langchain/issues/33504)；使用[官方after_model middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)返回原call_id的简短解析位置/合法schema指引，invalid-only跳回模型、mixed合法部分仍走原ToolNode。仍受原模型预算控制，非transport retry，不添加新循环/调度器。

父图只有四份结果，但FIN-owned PG内P08已经原生接受；只读导出最新版channel与消息，按原PaperRevision/quote/authority校验重算并与native output相等。P01/P04/P05/P06/P08五份公共修订保存在`Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/20260906-case-convergence-a1-recovery/accepted-revisions.private.json`；没有访问任何Codex live SQLite/JSONL。原A1不resume/重签、卷不删；这里是已完成结果保全，不是运行恢复能力证明。常规API state?subgraphs=true本次pending tasks读回异常仍需单独确认，不能拿前审通过冒称本图也通过。

另两项实际小修：CaseClaim显示既有kind↔numeric_authority合同（非S2 reported_fact需not_applicable并在authority_note注明），不改变领域规则；Writer/Verifier的catalog工具也改当前视图，避免返回被修订的旧thesis。新seed明确保存五份已重验公共输出与origin，复用时native before_model直接结束、0新模型/工具，终态必须等于hash绑定seed；不伪造旧消息或新的作者工作。真实SDK MockTransport验证invalid-only及mixed错误原文/own reasoning续传、合法工具恰一次；实际P07反例仍保持非法；六节点中五复用的流程本地已通过。18相邻测试通过（终态反例补充后待本轮最终数）。

本包最终72项相邻检查/12.56s通过（含新增终态复用与seed不符的拒绝）；无全仓重算。A2派生seed SHA=`d7fe36bbfcbfd54250302f177b846719f0a4734aa787bcc6e9866fc22ea165af`。A1三个精确容器已停止，卷/原失败保留。

下一fresh A2仅P07定向作者与Writer/Verifier付费，五稿不重跑；角色上下文、24k/32k输出和480s、12/16模型预算不增，预计约1–4元/5–20分钟，非报价或质量保证。Writer自由中文整案，终审与宿主人读内容后才决定是否修；本次无最终报告/交互UI/Dell产品PASS，不开始新case。累计审计a5：219次attempt调用/216有usage11208289tokens/210cache可估29.0956714元；另4次目录外诊断仍212237tokens/0.8537535元，旧3未知不可记0。全部是开发/试错/研究累计，不是普通问答费用。

## Convergence A2：完整报告链已跑通，质量仍需一次定向修订

实现19909f08、authority588f71b8；`20260906-dell-case-convergence-a2`真实终态`case_report_needs_revision`，receipt pass仅指报告/独立审查已交接。12调用809854tokens：P07 3/82357/估0.3599397元，Writer4/278262/0.6749298元，Verifier5/449235/0.9497559元，共1.9846254元（非账单）。其余P01/P04/P05/P06/P08原生before_model止步，均0model/0tools并保留旧origin；没有重跑九主题研究。736778input/73076output，532736hit/204042miss，49700reasoning。执行1020.812秒，构建106.469秒另列。root01a074b1-dd8e-7123-b449-038e7d5e06c8、thread41b05be1-a34e-55b8-839a-b1d0238e2bf7；LangSmith正式收据确认闭合绑定。A2三个精确容器已停止、卷/报告保留。累计审计a6已落D:/temp（历史开发总数，不是每题开销）。

本次真实验证两种自修：Writer首稿27个引用ID被其缩写，本地拒绝后自行用完整ID重交；Verifier第三次提交JSON语法坏，在新middleware中收到原call_id反馈而继续，第四次又有三处引句不逐字，收到全部错误后第五次成功交review。共有35工具消息，其中3个local错误反馈；源码没有手改模型内容/放松引句。公开success只代表provider响应，invalid_tool_call_count实际记录1。原A1失败不变。

当前报告9300字符、56处不同claim引用；`report.agent-original.md`及`report-review.agent-original.json`已在A2attempt目录机械导出，只改引用展示为脚注，不改财务正文。Writer实际读了十份当前稿+方法、七份原源。独立Verifier提出五项advisory：企业整体盈利不代表AI价值池份额；Q2毛利反向不能忽略H1累计略降；70%集中度只是第三方转述的分析师情景；AI收入16.1B→16.4B环比近持平被遗漏；原P02把pull-forward从存在成分放大成主要驱动。三个未解请求涉及Q1 backlog51.3B/媒体18.1%的一手确认及未来Q2 SQL升级。它仍漏掉现金加回与真实回款方向、非S2≠non-GAAP、WWC把单一信号当因果证明；宿主已独立读稿记录这些**明确host-assisted**意见，绝不把模型当oracle或盲审gold。

报告仍重复内部typed gap/F_*收据术语、部分覆盖只剩限制清单；下一定向修改应提升读者实际可用性，不能以“数字多、链接都合法”冒称高质量分析。保留全部六份作者结果，原生Writer只收旧报告/独立意见/明确人工意见和目录，按需读受影响稿及原源，不复制私有模型history、不重新读全部研究。Verifier只收新报告和正常当前稿/源入口，不继承Writer私有reasoning。当前稿若有未成立的推断，Writer应依据已验证事实来源改正正文，不把旧inference当事实；原P02/P09底稿的意见保持可见、并非全部底稿金融认证通过。

“未解请求”语义澄清：只把对剩余重大结论不可缺的资料作为阻塞项；未来10-Q接入SQL、已明确标为非S2的披露、已删除/弱化的不可靠数值锚点不应永久阻断报告。仍有必需证据未补足则needs_revision；不自动删除模型输出，不放松source/quote/schema，不授权S2写或Evidence admission。让Verifier把可选增强放summary/advisory。引句schema也提示选短而连续的原始Markdown，不能引用另一份底稿。

这次薄适配32相邻测试/12.04s通过，包括六作者全复用0调用、公开报告反馈仅Writer收到、实际A2 seed校验/无private messages、机械来源链接导出；无全仓回归。A3输入`convergence-input-a3.private.json` SHA992d693e2b06832084e5f01227fcefbe20c0b4c5930bf1a97893503ff137994d。下一只Writer+Verifier各最多16模型/48工具/700k/32k/480s，预算不增；预计新增约1–3元，最多一次有依据报告修订资格，若仍重大失败先归因，不自动无限重跑。目标是可读且实质可靠的Dell报告，随后才真实交互UI和新case。

前端等待时的新实测：官方JS SDK1.10.2 `threads.joinStream` 默认参数两fresh连接均回放本次author_P07事件，explicit streamMode='updates'则0；两种结果在Z lab分别保留。事件只保存节点名/ID，不持久化私有文本。常规state?subgraphs=true这次忙碌中仍next/tasks=[]，与nativePG pending不一致，尚未修；因此没有宣称前端上线、子图实时展示、cancel/HITL/resume完成。不得将这些只读资格检查当产品交互增量。

## A3收口与真实审阅Workbench（2026-09-06 04:04Z）

实现92061de1、authority bdf894ab，execution `20260906-dell-case-report-revision-a3`，root `01a074d6-1c52-7b81-88df-9f769d9112c2`，thread `7a6e1fe4-add0-5892-962a-86569e7f0bc2`，terminal `case_report_needs_revision`。6次真实调用348262tokens，Writer4/189768、Verifier2/158494；六稿均0新模型/工具。执行383秒、构建99.562秒。按已核价格估0.9575262元（Writer0.455598、Verifier0.5019282），非账单；322830输入含192768cache hit，25432输出含16875reasoning。原稿/审查机械导出在原attempt，原文没有被宿主改写。receipt的pass只表示运行/交接，不是质量PASS。

独立终审提出AI服务器同比减速被误导表述（material）、融资应收加回M/B单位不一致、H100采购跨代/跨期、首套交付的证明强度三项advisory，0不可解决数据请求。宿主直接读稿发现更深的残留：收入环比与积压变化不能单独证明供应约束因果；具名采购承诺不等于已融资；季度毛利上升不能证明“唯一约束”；余额不能直接证明资本效率，年初至今余额变化不能精确归因单季度现金流下降。原P09推断卡仍过强，Writer没有完全执行此前公开反馈。报告可读性仍偏内部边界清单。因此不把引用合法/Verifier赞扬当最终事实，不继续无界整篇重写。

反向核查也纠正了宿主旧意见：P02:S004与P05:S002确为Dell官方托管Q1电话会，原句直接含$51.3B backlog；A3对此一手来源判定正确。不能照搬A2审查“只有第三方”结论。这是原始证据优先于审查者意见的实证。

累计离线审计a7：237请求、234已知usage共12366405tokens，228cache明细可估32.037823元；另4次外部诊断212237tokens/0.8537535元不在attempt目录，3失败未知usage与6旧请求不完整cache不记零。累计开发成本，不是单个正常任务收费。

### 接下来一个可运行产品包，不另开规划工程

- 产品入口先是**现有Dell报告的真实审阅/追问/定向修订**，非重新研究全九主题或已支持任意公司。打开时从A3公开结果和已接受底稿建立新native thread，0模型；UI显示真实未通过状态。
- 继续采用Agent Server原生PostgreSQL/Redis/thread/run/SSE/interrupt/Command和create_agent；官方子图默认per-invocation私有历史，各模型在本次任务内完整多轮；跨任务只交当前报告、公开反馈和按需资料，不复制私人CoT。底稿/来源不从浏览器接收任意路径。
- Writer根据用户问题自主工具调用；普通追问可交带引用回答，修订才交新报告并由独立Verifier复核。每轮后停在原生人工审阅，不自动为追求PASS继续耗费。取消走原生run cancel；中途取消不自动重发未知模型调用。实际恢复/重连必须实测后才宣称。
- 不再将once实验的FIN-to-server双身份和每attempt容器协议搬到交互入口：该本地pilot原生thread/run ID就是产品运行标识；旧资格authority不重用/不改签。固定Dell data gate、只读来源/MCP、模型用途预算、loopback/秘密隔离仍生效。
- 薄Workbench BFF按白名单输出报告/引用、公共反馈、模型与工具状态/用量；不提供任意Agent Server代理、原始state/messages、SQL或shell。前端用既有React/Vite、官方JS SDK、成熟Markdown渲染；不造消息总线/任务队列/恢复器。会话状态只在原生PG，不在Markdown/新SQLite。
- 首先0模型真实框架测试和浏览器验证，再以A3精确问题做一次有界真实交互验证；预算不高于A3原Writer/Verifier各16模型/48工具/700k字符/32k输出/480s，约1–3元仅是估计。任务特定预算依据落实际session配置；本段不是已经paid。Flash已实证用于Lead调度，复杂报告不盲目切Flash；普通问答待实测路由。
- 完成此包后仍需全研究入口、运行中干预/部署韧性及完整Dell人工验收；后续1–2新case仍后置。报告存在重大错误就保留，不能用UI完成掩盖。

官方依据：[原生子图与私有上下文](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)、[interrupt与Command](https://docs.langchain.com/oss/python/langgraph/interrupts)、[公开custom流](https://docs.langchain.com/oss/python/langgraph/streaming)。Z lab `probe-native-public-stream.py` 已零provider产生两条真实native custom子图事件，私有reasoning标记未入流；不是Agent Server浏览器端已验证。

### Workbench有界实现与第一轮零模型实测

实际新增`dell_report_session.py`是native StateGraph组合，不实现模型循环/队列/数据库：宿主固定A3公开成果→原生interrupt→用户ask/revise→已有create_agent Writer（问答不会重写报告）→仅新报告调用独立Verifier→原生interrupt。每次独立子任务保留自己的完整原生消息，跨请求只传公开会话/当前稿；本次最新用户提示不重复注入两份。没有自动“修到PASS”的循环，也没有另跑六作者。复用CaseModelAudit在原生custom通道发公开模型/工具状态，私有原文依然只在私有审计文件与PG。

`report_sessions.py`在既有Workbench后端提供窄thread/run/stream/cancel/来源投影，使用官方PythonSDK与HTTPX关闭本地代理/transport retry；原生PG保存会话，BFF没有自己的运行存储。只接受三种人类动作，不接受预算/graph/path/原始state输入。loopback本地试点、跨站POST拒绝、UI不暴露通用AgentServer路径或私有messages/reasoning。新前端是React/Vite的实际页面`/workspace/session`，官方JS SDK1.10.2读取native事件，react-markdown10.1.0+remark-gfm4.0.1渲染/引用展开；禁raw HTML、自动远程图片与非HTTP(S)外链。尚不声称运行中任意steer、已测试cancel/restart或完整新研究入口。

原生图37相邻测试通过/36.83s（含既有Workbench基线），新增预算JSON反例8测试/7.27s；前端typecheck/build通过。npm发现开发依赖Browserslist两条高危advisory（同一个package），定向update后全依赖audit=0；生产依赖原audit亦=0。锁定SDK/Markdown正式依赖，未引入UI框架迁移或AgentChatUI整站复制。现产物约636KB JS/191KBgzip有分包提示，不隐藏，不因此阻断有界本地功能验证。

本机Cua真实浏览器已打开新布局，未把构建结果当浏览器证据。第一次点击新建实际产生native thread `01a07505-088c-7f63-8897-ad96deee2aee`/run `01a07505-089a-7942-8ccc-180e9ccc0444`，因TokenBudgetBasis strict Python读法不接受JSON list为tuple而error，**0模型**；该失败保留。已改用该模型既有model_validate_json，并在准备阶段提前检查；schema-only图缓存避免每次状态读取重编译。前端补真实error状态，不伪装“载入中”。启动前Docker地址池已用完，经读取全部网络确认10.253.36.0/24未占用后固定给本地pilot，无删除旧网络/卷。

部署配置在Z `report-workbench-20260906-a1`，从A3输入/输出生成host/container路径映射及任务特定预算。服务启动只用标准命令：`python -m scripts.deployment.dell_report_workbench up --settings-directory <Z路径>` 与 `... serve --settings-directory <Z路径>`；helper只装配环境并调用Compose/uvicorn，不创建模型run。固定project `finsight-dell-report-workbench`、Agent Server18165、Workbench8766；同三容器/PG/Redis，不每次问题新建容器。首次重启验证仍待完成，后续真实paid未开始。

### 05:03Z 浏览器真实零模型闭环通过，开始有界交互验证

最新容器镜像config `5125a76f742084fe21e6d3411a74a96f7a65fef17b55fc2125a74609dca4173e` 已实际重建部署。31近邻测试通过/21.76s，前端build通过。浏览器新建thread `01a07515-e784-7480-b6b3-eb4105ca127b` / init run `01a07515-e868-7c20-8c4c-50c21485a417`，真实native run success/thread interrupted，phase needs_revision、can_respond true、can_accept false；报告10738字符/68引用/4审查finding，model_events=0，调用目录无模型文件。引用P01:C7→P01:S006实际展开已保存SEC原文，显示捕获范围与链接，不把不完整capture当全文。浏览器观察发现来源窗口在多卡片末尾不明显，增加React ref滚入可见区，无新组件/状态平台。

下一付费只经此真实UI的revise动作，输入公开A3审查+宿主具名意见（不是隐藏测试/标准答案）；Writer独立核原文，Verifier独立复核新稿，完成即停native人工点，不自动接受。重点是AI同比基数/单位/首套vs规模部署/采购vs融资/库存余额vs现金期间/价值池因果与可读性；不另跑十份研究。沿用配置中已存任务TokenBudgetBasis与Pro low 16模型/48工具/700k输入字符/32k联合输出/480s，不升级权限；成本和产品通过都以实测为准。当前仅零模型浏览器通过，paid交互、重连、取消、完整Dell人工产品验收仍待实证。

### 05:25Z 首次真实UI付费修订结束：工程闭环成立，报告仍待修订

实现 `ab3c790636f387755b4c888d07f5c9f7387e0018`；push遇远端ref竞态返回失败，但随后ls-remote精确确认远端已是同一commit，未force push。浏览器在既有thread提交公开反馈，产生native run `01a0751c-b4af-75a3-9a29-7d34502249d3`（05:06:53.938585Z—05:15:39.426097Z），Writer4/157300tokens、Verifier6/270859tokens，共10次428159tokens。0重新研究作者。模型事件原始文件在Z `report-workbench-20260906-a1/calls/<thread>/<run>/`；公开终态另保存 `public-session-after-revision1.json`，原A3与失败初始化不改。LangSmith实查同run根闭合、error=false、inputs/outputs均隐藏，384608输入/43551输出与本地完全一致。

费用按已有价格估 **1.0647609元**：新输入0.433584、输出0.5879385、缓存输入0.0432384；288256 cache-hit tokens，输出含33618 reasoning。成本审计实际路径 `D:/temp/fin_dell_workbench_cost_audit_20260906_a1_actual.json`。第一次给审计器传入父目录层级错误得到0请求，原零结果文件保留但无效，不当作0费用；用thread目录重跑离线审计得到上数，无新模型调用。全案约8m45s是修订+独立全报告复核，不是短问答时延。

实际浏览器已看见逐条模型/工具开始与返回、用量、Writer→Verifier交接。开始阶段等待模型时0条事件曾被怀疑为传输问题；随后真实Cua/原生SDK/HTTP都看到custom|子图事件，未发现须换框架的问题。原生resumable run的Last-Event-ID=0-0实际回放成功；修复BFF初次附加默认从该cursor读取，避免刷新漏掉已发生事件。已完成的公开工具状态同模型记录一起保存在原生PG根state，UI合并去重，不新增事件库，失败/中断未提交部分仍不冒称完整持久化。运行中显示“上一轮审查”以免混淆新稿与旧finding。

报告v2与原生人工点成立（run success/thread interrupted/report needs_revision），不等于质量通过。独立终审1material/4advisory：漏并列H1现金流方向；此外宿主发现情景段仍将采购承诺等同已融资。相反，审查者也有不严谨：H1现金流增长不能直接反证现金转化比率走弱；Q2 $8.208B基期是直接披露，非与Q1同样直减派生；订单/积压不必误贴需GAAP对账的non-GAAP会计指标；HPE低可靠性毛利不能为补表机械加入。以上均为公开开发审稿，不是隐藏gold。

### 有界局部编辑与下一次验证（尚未paid）

依据[Anthropic文本编辑工具的唯一exact str_replace语义](https://platform.claude.com/docs/en/agents-and-tools/tool-use/text-editor-tool)，FIN仅薄接当前报告old_str/new_str：1–24条替换、逐条精确唯一命中、临时字符串全部成功并通过既有CaseReport/引用校验才提交；无任意文件/路径、无模糊修复、无新runtime。旧稿和所有失败保留；JSON/命中错误用同原生ToolMessage返给作者。Writer仍可在确需大改时完整报告，但局部修订优先此工具。独立Verifier获得当前报告、实际文本diff和上轮公共审查，聚焦变更/未闭项且可检查未改上下文，不因“未改”自动判对。35近邻检查/31.59s与前端build通过，含真实native图中命中错误→引用错误→作者自修→Verifier；0新provider。

下一只在相同session发一次具体局部修订意见：H1与Q2现金/相对收入、采购与融资矛盾、AI收入与订单指标性质、基期派生标注、HPE建议是否必要、附录笔误。沿用host-settings内任务预算与Pro low profile，不重研究、不改数据门；假设差分输出/增量审查能减少重复输出和无关原文阅读，费用与质量需实测，不先承诺节省比例。该次结束即停人工点，不自动重写至PASS。完整新研究入口/任意中途干预/取消/服务重启恢复和新case继续待验收。

### 05:39Z 局部修订真实结束：v3待人工审阅，不再自动重写

实现226e8c7b，同thread原生run `01a07533-f6f1-7ff3-8cf5-673b82c4efae`，LangSmith根05:32:21.089976Z—05:39:20.587093Z闭合、error为空、inputs/outputs隐藏；本地/远端用量完全相等。Writer3调用95490tokens、Verifier7调用321489tokens，共10调用416979tokens（381141输入/35838输出，含30786reasoning），估0.8325603元，不是账单。Writer真实提交9处exact edits，本地重放这些修改与v3正文完全相同，旧v2和研究稿未变；0研究作者重跑。两次UI共20调用845138tokens/估1.8973212元。与前次1.0647609元相比下降约22%，但缓存、任务范围和审查行为也不同，不能当因果A/B或一般节省承诺。

报告v3为12595字符/69引用，终审0material/2advisory/0不可缺补源请求，phase=`ready_for_human_review`，仍非Owner人工通过/产品PASS。两条提示为：Q1 FY26 $1882M本有10-Q直接披露，正文误标成只有H1−Q2派生；旧P01:C7 authority_note未与AI收入/订单分类纠正同步。宿主已检查Verifier实际工具返回的Q1原表：AI-optimized servers 16132/1882，非盲信review。也不照抄review把所有运营指标称non-GAAP或把当前8-K写成已审计；现金绝对增长与转化率仍需区别。原始公开状态、报告机械导出在Z `report-workbench-20260906-a1/public-session-after-revision2.json` 和 `report-v3.agent-original.md`。费用明细在D:/temp/fin_dell_workbench_cost_audit_20260906_a2_actual.json。LangSmith新retrieve接口本次诊断因缺project_id未执行查询；使用仍受支持read_run完成只读核对，不增加模型调用。

同PG/Redis的API升级后已实际读回v2人工点，并在同thread继续生成v3；这证明已保存人工边界的重启续办，不等同运行中kill/recovery。前端工具/模型历史合并后按recorded_at排序，构建通过。尚无任意新研究UI、运行中干预/取消实证、完整Dell人工验收；新公司案例仍后置。

### 下一有界工作：同Dell快速问答的任务模式路由

采用既有create_agent与原生StateGraph分支，不新增分类模型/执行循环。UI明确选择快速问答Flash（thinking disabled）或深度追问Pro；旧API默认deep保持兼容，报告修订及Verifier仍Pro。这个阶段只称显式任务模式路由，不称自主难度分类器。快速问答不预塞完整报告/全报告审查，只给当前目录、公开对话与问题；完整报告通过只读工具按需查看，来源/SQL/计算工具保持原权限，私有历史隔离。简单问答不调用全报告Verifier、不得修改报告；实测内容由宿主回源核验。

首次问题预定为Dell FY2027 Q1总收入和经营利润，要求期间、单位与来源，不给答案、不重研究。TokenBudgetBasis：单问题/约10k字符目录、有限公开会话；8模型/24工具、350k输入字符、8k单次输出、240s请求超时，disabled，无transport retry/fallback。允许查当前claim、S2及原源和纠错，不要求耗尽预算。依据前两次复杂修订10调用/约417–428k总tokens，本次只查两个已有财务事实，不应继承整报告反复生成/审查成本；实际是否省钱/正确以新run为准。输出截断/未知结果停止，不为省钱隐瞒研究缺口。近邻测试、真实UI运行、源核验与token统计后再决定扩展；不先做新公司。

实现仅现有native图多一个quick_writer分支与薄只读报告工具，profile/TokenBudgetBasis随源码固定到镜像；旧部署seed/PG/source不变。原生测试实际证明quick调用、报告按需读、非法无引用答复反馈自修、Writer/Verifier零调用、随后deep独立上下文及无嵌套引用历史。40近邻pytest/22.71s、TS/Vite build通过（首次错误cwd未找到tsc属于宿主命令，正确frontend目录重跑通过）；637.15KB JS/191.16KBgzip既存分包提示保留。下一实际UI，不把fixture当金融答案质量。

### 06:04Z 首次Flash快速问答完成；发现并小修SQL参数反馈

33221126已推送/部署，API镜像config89f290d3、容器981ae05d375d，同PG/Redis未重建；新BFF进程42928。UI实际选择quick后提交预定问题，run `01a07551-5129-7b70-9f4e-3d23eb5c62a4`，06:04:18.603020Z—06:04:43.544068Z，约24.94秒。Flash disabled 6次调用85962tokens（83255输入/2707输出、65280cache-hit），估0.042408元；Pro/Verifier/研究作者均0调用，report_version仍3。第一屏19769字符/7190输入tokens，不预塞整报告/前审；最后回答正确绑定P01:C1/C2的S2保存源43842000000/3656000000 USD、FY2027 Q1/2026-01-31至05-01。公开状态保存`public-session-after-quick-answer1.json`，离线累计审计a3_actual为26调用931100tokens/估1.9397292元。thinking disabled未报reasoning明细，不能把unknown字段作为独立零推理计量证明。

不能说本次在线SQL成功：模型先后用REVENUE/GAAP_OPERATING_INCOME和REVENUE/OPERATING_INCOME大写字段且猜错财年日期，domain validator拒绝；MCP2把工具函数内未分类ValidationError视为意外异常，只回通用Error executing tool。模型转读当前底稿/存档NumericFact，第一次把source ID当claim ID又被拒绝，后来自修成功；6次provider success不等于0工具错误。宿主随后用真实MCP/真实SQL核对同两项，均resolved且期间/单位/source IDs与答案一致，0写入、0provider；保存`quick-answer-sql-host-check.json`。

根因修补只在既有MCP：metric_ids增加既有小写命名和合法例子的schema说明；构造Query的预期ValidationError转换为MCP2原生ToolError，回field/code与改正提示，不泄露输入/trace/backend，也不自动猜别名或降低约束。依据已安装MCP2.1.1官方exceptions.ToolError语义。22相邻检查通过/8.32s（原错误→具体反馈→合法请求，不是新NLP规则）。下一同Dell追问复核一次，沿用quick预算，不重写报告/新case；保留本次SQL失败而不回写成通过。

### 第二条Flash追问失败：SQL成功，计算器未消费真实NumericFact ID

18ee235d部署后的真实UI追问run `01a0755c-d8eb-7aa1-b581-c034bcbbeda8`（06:16:54Z启动）失败于ModelCallLimitExceededError 8/8；8次Provider成功不等于任务成功。实际99598输入/2095输出，共101693tokens，估0.0370709元。首轮已用合法小写metric与正确FY2027 Q1期间查询，SQL返回43842000000/3656000000 USD和真实NUMFACT ID；还查了未要求的上年季度。计算器只识别归档Pxx:Sxxx，拒绝SQL刚返回的NUMFACT；MCP又隐藏了未分类ValueError，模型改参数/去掉绑定仍失败，未交答案。不是网络、余额或应提高预算的问题。原native failed run、私有模型历史与`public-session-after-quick-answer2-failed.json`保留，v3报告不改。累计工作台a4_actual为34次1032793tokens/估1.9768001元，非单问题成本或账单。

最小修复：在现有MCP composition内投影已返回的typed SQL NumericFacts给既有simpleeval/Decimal计算器；只读数据源决定数值，模型不需要复制literal。新composition须重新查询，伪造ID/数值改写仍拒绝；无新存储/准入/SQL写。预期计算错误使用MCP2 ToolError说明实际原因与绑定方法。真实本地mart→MCP→计算器联测通过，非mock SQL；错误ID、未观察/跨composition ID、错误literal及non-authority输出均覆盖。最初宿主测试把Q1展示名当完整branch ID被拒绝，改用真实catalog ID后通过，不降低数据合同。

失败问答的交互收口采用[LangGraph原生error_handler](https://docs.langchain.com/oss/python/langgraph/fault-tolerance)和[checkpoint update](https://docs.langchain.com/oss/python/langgraph/use-time-travel)，已安装1.2.11，无依赖升级/新恢复器。已知调用上限/截断只停止本次ask，保留失败审计/旧报告，回原生人工点；报告修订/Verifier异常不借此跳过复核。旧版本已失败ask可在窄BFF/UI选择“返回审阅·不重试”：官方update_state as_node=finish，仅更新公开失败处置，再用零模型run进入human_review；不执行失败模型节点，不覆盖旧checkpoint，不让浏览器传state/节点/模型参数。原生fixture复证8/6次预算中止后新问题有独立上下文，legacy失败checkpoint保持可读。未知异常仍向上传播，未冒称通用故障恢复已完成。

76近邻测试通过/33.01s；TS/Vite build通过（637.50KB JS/191.24KBgzip，既有分包告警未隐藏），不是全仓回归。下一部署后仅原会话零模型返回审阅，再同季度SQL+计算追问一次Flash/disabled，沿用8模型/24工具/350k输入字符/8k输出/240s与现有TokenBudgetBasis；假设工具接通后可直接回答，无预算增加或研究重跑。若再次失败先读实际原因，不自动重发。尚未新paid、取消/中途干预/全案研究入口/Owner验收/新case仍未完成。

### SQL计算线上已通，但交付引用仍归档限定；直接引用本次工具结果

ca813dda已push/部署，同PG/Redis保留。UI“返回审阅·不重试”实际产生run `01a07577-e1ec-7d21-a7ca-65aabd57fdd6`，成功停人工点，0模型audit文件，v3完整不变，旧failed run依然error。随后同问题fresh run `01a07578-83a4-7fb0-be8d-97f5fa486013`，06:47:07.429066Z—06:47:20.392083Z，4Flash调用43760tokens（42430输入/1330输出），估0.024158元。SQL与计算器均成功，直接NUMFACT输入得到0.0833903562793668…比例，约8.34%。提交正文没有旧Pxx:claim引用，工具只回`report_citation_ids_missing_or_unknown:[]`，模型下一轮无工具地说“已提交”；原生agent正常结束但没有被接受的output，父图失败，不能算答案成功。原`public-session-after-quick-answer3-failed.json`保留，估费审计a5_actual共38调用1076553tokens/2.0009581元。

这不是靠自然语言模板判语义，应修现有交付合同：短问答可直接引用本次成功SQL的`[NUMFACT::...]`及计算器`[CALC::...]`，也兼容旧Pxx:claim。薄映射只从native成功ToolMessage.artifact绑定，拒绝模型/用户自述、失败工具、未观察ID；计算引用带实际操作数、表达式、authority_note并保持非权威，BFF/UI从已保存引用投影展开原值/计算依据，无新Evidence/SQL写或来源库。报告长文的现有引用规则不变。

预期拒绝明确说“Answer NOT saved”和合法引用方式；若拒绝后模型只说完成，官方after_model middleware把未保存状态返其自身原生循环，由既有预算止损，不解析修补模型推理/不自建循环。原生error_handler异常时API可能tasks=[]，已用最新native error run的server-owned ask/surface元数据识别可放弃追问，不能用于revise/Verifier/运行中任务。67相邻测试/32.68s与TS/Vite build通过；追加真实SQL→计算→native提交完整零provider测试，26项/13.31s通过。下一仅部署与原会话零模型放弃后一次同问题，模型/profile/8轮预算不变；不重跑研究或整报告。完整Dell仍未验收。
