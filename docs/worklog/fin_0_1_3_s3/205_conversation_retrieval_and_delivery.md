# 205 多轮工作台与检索交付

2026-09-09，Owner授权Qwen对照、五新题/旧失败重跑、数据池缓存、通用多轮/Hermes/多格式、权限与多租户探索。唯一新增计划见[实施基线](../../product/CONVERSATION_RETRIEVAL_AND_DELIVERY_20260909.zh-CN.md)。基于main a7053972，工作分支codex/fin013-conversation-and-retrieval。

开始状态：干净工作树，QWEN_API_KEY仅Windows用户环境存在，未输出密钥。未开始新模型调用、未删文件；D盘用于新增资格产物。204已合main，自动摘要仍HOLD。现有thread追问/报告导出/原生checkpoint复用，不重造。

## A：首批真实检索对照（已执行，未决定替换）

工程增量：OpenAI SDK 3.6.0 薄适配官方 text-embedding-v4 与 qwen3-rerank，分别使用 compatible-mode/v1 与 compatible-api/v1；不重试、不发现密钥、不自动改索引。查询/语料脚本分离，8条开发查询不含答案。API与本地均1024维、相同分块/文本；重排候选池取两种召回各top20的并集，按原语料顺序输入。

资格证据：Microsoft FY2025年报与RFC9111共343块，8查询。先4向量+3文档重排连通140tokens，再36次向量82584tokens、8次重排69651tokens；共46请求、152375tokens、未知0。按2026-09-09官方两模型0.5元/百万输入tokens估算0.0761875元，免费抵扣实际值未知。没有本轮DS生成调用。

| arm | 总墙钟秒（含模型加载） | 查询关键来源锚点覆盖@5平均 | 全锚点进入top5题数 |
| --- | ---: | ---: | ---: |
| 本地Qwen3-Embedding-0.6B | 27.9214 | 0.6875 | 4/8 |
| 在线text-embedding-v4 | 25.6436 | 0.7500 | 5/8 |
| 本地BGE-reranker-v2-m3 | 23.6782 | 0.7500 | 5/8 |
| 在线qwen3-rerank | 5.2690 | 0.7500 | 4/8 |

在线向量batch p50/p95为0.5834/1.1105秒，不是单query端到端；本地重排query0.7999/1.2285秒、在线0.2131/0.4740秒。不是完整qrels或盲测，不报告nDCG/答案正确率；未覆盖所有等价来源。样本不足，重排未稳定胜过本地，保留本地，在线作为已连通候选。热缓存与更广泛资料尚待补，A尚未全部验收。

D:/temp证据：fin205-{local,api}-{embedding,rerank}-a1；fin205-retrieval-comparison-a1.json；fin205-public-corpus-a4/{chunks,paired-candidates,development-anchors}.json。原抓取a1/a2/a3保留；a3分块ID重复，a4改为全局序号，逐行文本hash相同，已保存a3/a4及ordered-text digest证明，复用原向量没有重发。此为身份准备失败修复，不更换推理结果。开发标签在看排序结果前按原文指定，之后只检查，不调模型。HPE新闻页proxy/direct超时、PDF403保留为抓取失败，不称公开信息缺口。

## B：公开数据扩充与缓存切片（进行中）

2026-09-09沿现有SEC快照工具抓取MSFT/HPE共4份CompanyFacts/Submissions，D:/temp/fin205-companyfacts-a1；manifest digest 698f2348b4d071699fc1cd60d49660414adc0bfaf3ee8301834e73607c49917a。新materialize_companyfacts_snapshot CLI复用现有S2解析/事实库，不载入验收答案，不更改旧库。旧qualification默认仍要求qrels，正常入库显式不要求，财务authority校验不变。

D:/temp/fin205-companyfacts-mart-a1截至2025-12-31生成955观察（MSFT512/HPE443，12指标，426 superseded保留），状态materialized_acceptance_pending。4次原生FactLookup均resolved，MSFT FY2024/2025为245122000000/281724000000 USD，HPE为30127000000/34296000000 USD，含起止日及相应10-K申报/接受时间/hash；lookup-smoke.json。尚未接入正在服务的旧数据配置，不能说任意公司全链路已经通过。

成熟栈决定：采用[DiskCache](https://grantjenks.com/docs/diskcache/tutorial.html)5.6.3管理本地TTL/进程安全/限容，不自建缓存数据库协议；requests-cache适合HTTP缓存，但现有主要抓取走Exa MCP，故在已成功CaptureReceipt层做薄复用。按原生thread隔离，1小时、64MiB；命中校验URL/DNS并重新绑定新run，原抓取时间、text digest、不完整/非权威边界保留。失败不缓存；非同thread不得复用；显式刷新新抓取。缓存不是长期知识库或不可变审计库，知识库批准和跨thread共享仍待后续。

检查：首次83passed/5skipped/4failed，4失败均新测试构造更改attempt却未重绑定run_scope_digest，修fixture使用正式bind函数后5个新增缓存/入库测试通过。其余83项未改动、无额外重复付费。未清任何磁盘/镜像，未改报告或FIN0.1.3。

剩余：A热缓存与代表性扩充；B真实缓存复用/批准入库/UI与新SQL路由；C通用多轮、Hermes接续；D权限；E五新case/旧失败/报告；F多租户。此日志不是整轮完成声明。

## 可接续状态（2026-09-09，本轮继续）

外源真实复用 D:/temp/fin205-live-source-cache-a1：RFC9111首次1.2133秒，重建读取器/新attempt复用0.0234秒，总HTTP抓取1次，text digest 5ca1c7d75caf0afbd46f4532792f71084277691b132e3d7bcbf1d5728249b865及captured_at相同。无模型调用；缓存范围仍同一thread，非共享知识库。原schema新增可辨识cached_public_source_replay方法，原receipt重绑定新run并保留时间/内容边界。

产品增量：运行页按节点展示最近一次请求input_tokens、供应商窗口声明与接近80%提示；新请求用量未返回显示未知而非上一请求或累计账单。DeepSeek V4两模型官方1M窗口（2026-09-09文档）；不代表运行预算/金融保真。折叠详情避免复杂研究11节点占满页面。context_usage后端投影与前端组件已接真实历史：4be034任务11节点各最后请求约50505–114582tokens，区别累计8282356。输入字符只能作为字符，不换算伪精确tokens。

验证：31原生会话/上下文投影测试通过；上下文详情默认折叠后的最终Vite构建8.50秒通过（既有chunk>500KB告警）、活动页1440/1024/390三宽度3通过10.1秒。后续补同actor较旧请求迟到不得覆盖新请求pending测试。原生profile preflight通过，仅schema/配置不是全产品通过。

服务：18793旧BFF PID40536、18165 native均保留，无活动研究。自动审批拒绝停止旧BFF并重启命令，只给blocked by policy未给详细理由；未再次尝试终止。替代在18794启动新版BFF（Start-Process返回PID15720），日志D:/temp/fin205-ui-context-preview-a1；同一native与全部11历史。18794实际GET最新会话返回context_usage成功；CUA iab tab9首页。新版URL http://127.0.0.1:18794/workspace。源缓存代码尚未重建进native容器，不能说正式运行已经消费该缓存。

下一步：完成当前UI构建读回、精确暂存提交本可运行切片；推进通用问答/多轮/Hermes而非再规划。Hermes隔离官方checkout D:/temp/fin-hermes-qualification-20260909-a2（0.21.1，abd83ab560327c58f17f8e2ecd9be0307d5c9cf9），run_agent.AIAgent提供run_conversation(user_message, conversation_history=...)、stream_delta_callback、tool_start/complete_callback、registry.register工具薄接入。max_iterations默认无穷，正式资格必须显式限次/时间；agent.api_max_retries配置至少1（表示尝试次数需确认），SDK另设max_retries0。还没执行Hermes全Agent新付费调用。不要沿用旧204的失败摘要当事实或扩大模型权限。

Git：本轮所有新改在codex/fin013-conversation-and-retrieval，仍未提交/推送。uv.lock已锁diskcache5.6.3，新retrieval-api extra明确OpenAI3.6.0。用户密钥/原始数据/模型响应在Git外，未删除文件。后续清除只限核实后的本项目可重建物，禁止跨项目或删除证据卷。

## C/D：真实多轮与权限原生切片（继续，未整体验收）

新增 conversation_agent.py，复用 LangChain create_agent、ModelCallLimit/ToolCallLimit/HumanInTheLoopMiddleware 和原生checkpoint。host显式工具授权，未知effect拒绝注册；普通问答不要求财务报告。三档权限中用户原文件/外部系统变更始终要求该具体操作批准；仅task-owned生成物可以在已委托模式内自动执行。它不是OS sandbox，也尚未接BFF/前端；不得声称隔离已上线。6项真实原生图测试覆盖三档拒绝不改原文件、具体批准一次执行、多轮纠正与thread隔离、未知effect拒绝；与3上下文投影测试合计9 passed/0.80秒。

Hermes完整Agent固定官方0.21.1/abd83ab…，单工具白名单最初被默认tool_search桥替换，改官方tools.tool_search.enabled=off后直接注册。离线a3发现thinking误置SDK顶层，改extra_body；a4发现即使api_max_retries=1仍重建客户端恢复，测试无效key收到401，无模型推理但非零网络。a5把SDK审计hook同时绑定_primary_runtime恢复配置；a6正常wire通过；timeout-a1故障注入仅1次MockTransport发送，恢复第二次请求在pending入口拦截。HERMES_STREAM_RETRIES=0；真实调用前校验8调用/80k字符/2200输出/只读工具/固定官方endpoint，不自动再发未知请求。资格审计缓冲SSE只为保存调用证据，不是生产流式UI。隔离venv补simpleeval1.0.7与项目一致（曾误装1.0.5，任何真实计算前纠正；旧产物不动）。

真实资格（公开来源，不是盲测，不是五题全链路验收）：

| attempt | 模型调用 | tokens | 估算CNY | 结果与责任层 |
| --- | ---: | ---: | ---: | --- |
| Hermes MSFT三轮 live-a1 | 5 | 21593 | 0.0136703 | 来源/期间/单位更正和再次回读保留；模型心算14.92%，实际14.932156…，财务输出未通过 |
| Hermes接原生source-bound calculator live-a2 | 8 | 54469 | 0.0292793 | 3轮完成、精确计算恢复14.93%；解释出现无依据占位引用/不通顺财务措辞，文本质量未通过，不默认启用 |
| Native普通问答 a1 | 3 | 7637 | 0.0068205 | 原文只返回首个匹配导致反复搜索，原生工具上限6/4停止；失败保存，不称信息缺口 |
| Native普通问答 a2 | 3 | 19055 | 0.0182397 | 返回多个字面匹配及原文位置后，2轮完成；SQLite checkpoint关闭重开仍保留修改受众要求，普通问答未激活金融专家 |

Hermes a1/a2最多单次输入5152/9694tokens；模型耗时11.42/26.86秒；a2工具6次。原生普通问答a2单次最大9077，2次资料工具；控制台首轮model_calls=4误计tool started，审计实际首轮2模型＋2工具，脚本已修计数，不重跑付费。保存D:/temp/fin205-execution-metrics-a1.json、各attempt目录和SQLite。两种harness题目/工具不同，不能据此宣称对照节费或优胜。没有将候选输出提升为报告/人工审阅通过。

当前205真实DS合19模型请求/102754tokens/估算0.0680098元；加Qwen46请求152375tokens/0.0761875元，合65推理请求/255129tokens/0.1441973元，已报告用量未知0。另有离线失败、mock及1次测试无效key401网络请求，不混计为模型推理。2026-09-09重查DeepSeek官方价仍为Flash空闲cache-hit/miss/output每百万0.05/1.5/4.5元；实际账单/免费抵扣未知。

后续必须继续：通用Agent的BFF/正式前端/原生服务注册、真实OS sandbox与前端批准、任务知识库批准入库/扩展SQL实际消费、同题Hermes配对与输出质量、其余3–4新题及旧失败按根因重验、多格式报告渲染核查、全链路指标与多租户隔离。当前是产品用量面板＋工程/资格增量，绝非整轮完成。


## C：通用对话正式界面与服务接线（继续）

产品/工程增量：新增 /workspace/assistant，通用对话列表、原生多轮保存/刷新续读、模型与权限选择、停止、公开活动/回答、逐段assistant文本流与context_usage。BFF只投影公开消息，不传provider reasoning、工具原始参数；原生Agent Server新增conversation_session，复用LangChain create_agent与同一Postgres/Redis。工具接已有TaskAttachmentStore、point-in-time金融查询和来源绑定计算。新增MSFT/HPE快照通过独立Compose只读bind挂载，不替换原研究SQL池。权限暂仅只读/计算，尚无OS sandbox或可写工具，不宣称三档隔离完成。

零模型检查：浏览器第一次3宽度均因getByLabel精确定位失败（应用AX中已有combobox名字），改role locator后1440/1024/390全部3通过7秒，原失败目录保留，成功D:/temp/fin205-assistant-browser-a2。来源checkpoint重建计算/跨thread隔离首次1失败11通过：来源缺失ToolException终止整轮，修为原生handle_tool_error反馈，基础设施异常仍上抛；同thread读取真实artifact操作数、另thread无权借用来源的定向测试通过。公开消息/流投影排除私有推理、原生预算JSON加载等当前10项通过3.09秒。Vite最终构建14.71秒通过，既有大chunk警告保留。

部署：本轮构建锁定依赖镜像；确认busy=0后只recreate API，原PG/Redis容器/卷继续使用。host/container-settings原件另存.before-conversation-205，新增conversation_fact_mart映射，路径不由模型指定。新BFF18795（启动返回10880，uvicorn23312）/native18165可用，旧BFF未终止；首次/assistants/conversation_session/graph与/ok均200。

真实前端新题1的a1在模型前失败：thread01a082cb-bd81-7710-83af-225dd628337a/run01a082cb-bd8f-7762-ad00-1671b145cf7c，TokenBudgetBasis strict tuple收到了json list。改model_validate_json并新增正式配置测试；未付费/无provider调用。D:/temp/fin205-ui-ordinary-a1保留页面、提交身份、状态与失败。正在构建修正镜像，后续须新attempt，不把schema可读当执行成功。

新增可复用真实UI资格脚本conversation_browser_probe.cjs，必须显式--execute，最多3轮、loopback、每轮provider额度来自conversation.json，提交不自动重试，刷新页面验证跨轮。它保存证据到新目录，不把模型回答写回Git。


## 实际前端新题1/2与持久接续（2026-09-09 05:10，本轮继续）

新题1 a2：thread01a082ce-d90a-7231-9842-d3326ba9dd72，两轮2调用/5169tokens/估算0.006681元。实际前端填写/发送，刷新后继续改给非技术同事的三条建议；未触发金融专家。内容复核发现首轮“no-cache缓存前验证”与后文“使用前验证”矛盾，强制刷新也有过度概括；链路完成、内容质量不全通过，不能宣称知识正确率100%。a1仍保留且0模型调用。

新题2：thread01a082d0-1573-7db0-976b-0b1cd2869529，首次两轮5调用28286tokens，读取新增只读MSFT数据库、完整年度/期间/USD绑定与工具同比14.932156…正确。第二轮显示十亿美元数值正确但未调用转换计算，追加独立修订run01a082d5-3b80-7093-bc29-355b0126f8bb在原thread补齐两个单位换算（原两轮不改）。追加前API容器重建，原Postgres状态仍支持复用原始ToolMessage.artifact，不重复查数据库。三轮合7调用45862tokens/估算0.030916元；公开progress首两轮英文、末轮修正使用用户语言。来源链接/期间/原USD及转换值一致，仍不提升为已审研究报告。

流式资格：最初每模型响应1片（4/1片）查明case_chat_model默认streaming=False；通用入口明确原生SDK streaming=True、include_usage=True，旧研究入口默认不变。Mock SSE证明一次请求、逐块回调、最终usage22保留；实际上述追加轮前端收到389个assistant_delta，2调用17576tokens用量均已知。只投影content文本，reasoning/additional_kwargs不外露；前端新增随读位置滚到底，向上阅读时不抢滚动，样式继承正式蓝色主题。最终构建9.04秒通过、3宽度浏览器3通过8.3秒；新增后端/检索/缓存合22通过4.47秒，候选文件secret模式扫描无命中。

本轮累计74推理请求/306160tokens/估算0.1817943元（Qwen46、DS28；全部已报用量），另有前述测试无效key401网络与0模型部署失败。免费抵扣/实际账单未知。当前服务18795新工作台及通用对话、18165API镜像f639f74f…；旧BFF18793/18794均未终止，数据库卷完整。真实输出在D:/temp/fin205-ui-ordinary-a2、fin205-ui-msft-a1、fin205-ui-msft-unit-a1，不入Git。

已提交工程切片84f6969f（Qwen对照/新快照入库/同thread源缓存）、d457fb05（通用多轮/作用域工具/上下文/前后端/资格脚本）。文档与本轮其余工作继续，不合main、不发release、不宣布五新题/旧失败/Hermes/报告/sandbox/多租户全部完成。

## 新题3：MSFT指定双方向与执行失败根因（继续，不是全轮收口）

实际前端选择Q1公司财务与Q3量价组合，上传微软FY2025官方年报；题目要求IC分部增长/利润率及组合解释，区分Azure、Microsoft Cloud分母。thread `01a082df-cd1a-7ee3-bd9f-151e1c83f369`，run `01a082df-cf9d-76e2-8d9b-fc05dcf8a8af`，约20分钟后生成报告v1，ready_for_human_review，不代表Owner接受。浏览器a1路由错误没有提交；a2已启动后记录器response body失效，回读身份而没有再次提交。脚本修正，原目录均保留。

实证：95请求意图，94实际provider尝试，93已报告；1连接失败用量未知，1输入上限前拦截未发送。已知输入3908059/输出205169/合4113228 tokens，缓存命中3172096/未命中735963，估算¥2.185810。整轮累计168推理尝试、已知4419388tokens/¥2.3676043、未知1；另有1预检拦截与早前无效key网络请求。实际账单与免费抵扣未知。D:/temp/fin205-msft-selected-a2/final-snapshot.json、metrics-a1.json及原audit保留。公开汇总脚本区分未发送与未知，不再把0传输误记未知。

工程增量：Lead在model_execution_failure/model_turn_ceiling/tool_action_ceiling后停止并保存其他已完成方向，禁止悄悄创建替代task重置预算；质量修订仍走原语义流程。原生ClearToolUsesEdit只保留具体错误结果，不再保留同名工具全部成功内容；700k字符保护按SDK实际投影请求（含tools schema）计数，不放宽上限。94历史请求离线回放字符13123301→12822461，仅约2.3%，不是实际token节费或正确率结论。read_source_document新增工具边界校验，明确UPLOAD::前缀不可删，历史合同仍可加载错误请求，避免迁移破坏证据。

产品/导出：微软v1有1图，真实PDF5页/Word7页。发现图表说明[P01:C4]与实际[P01:C4_margins_derived]不一致，不能猜别名。新增chart_index局部说明编辑，保持绑定数据/来源，提交验证同时检查正文与图表引用；待真实前端修订验证。导出显示投影已修本机端口链接、已知引用编号与PDF数学字形，未知图表引用显式标记待修订，绝不改checkpoint出处。D:/temp/fin205-msft-selected-a2/export-repaired-a1 PDF5页已逐页查看；DOCX7页仍需完整视觉检查，不能标正式交付完成。

权限资格：Docker官方现成容器隔离，固定本地sha256镜像，非root、无网络、只读root、无host/daemon/secret挂载、cap-drop、CPU/内存/pids限制、tmpfs临时目录、超时终止与有界日志。仅模型code参数，不开放镜像/挂载/命令选择。D:/temp/fin205-sandbox-a1/a2启动失败保存；a3三次真实容器证明任务内写入/跨容器不留存/root写入阻止/网络阻止/超时137，0模型。只移除自己新建容器，未删镜像/卷/用户文件。native HITL三档定向测试通过，但未接前端与Agent Server；不能宣称生产sandbox/多租户成立，也不挂Docker socket给Agent容器。

通用对话新增draft与TaskAttachmentStore上传，解析后才发模型，前端选择文件/已上传列表/失败不重复上传。只是当前thread复制件，没有原文件写入，未擅自全局知识入库。零模型回归88 passed/5缺素材 skipped（报告/会话/Lead/上下文/附件/sandbox），最终TS/Vite通过10.45秒，已有大bundle警告仍在。此处尚未部署上述新源码，正在构建，需确认busy=0后重载服务并继续真实修订。没有新付费调用或Hermes重试。

## 真实局部修订、跨窗口和交付检查（继续）

产品/工程：已部署前述修复及通用附件。新增原生checkpoint交接预览、可编辑交接说明、对话深链接，创建新thread本身0模型；新窗口只获所选旧checkpoint，回读公开消息和原始已观察SQL/计算/来源凭证。原文私有推理不投影，未读取附件不伪装成交接证据。每次工具回读验证来源owner，历史保留，不创建第二套摘要数据库。当前owner仍是本地试用身份，不能据此宣称生产多租户鉴权完成。上下文面板同时显示最新请求provider tokens与宿主字符限额，80%字符阈值提示交接，不混算成token百分比。

报告实证：中题thread01a082df-cd1a-7ee3-bd9f-151e1c83f369，经真实UI提交局部修订run01a08311-27a1-7553-aa97-5a210e657810，Writer+报告Verifier共4调用59874tokens/估算¥0.063804。v2仅将图表说明[P01:C4]改为已存在的[P01:C4_margins_derived]，正文、图表数值/单位/provenance完全一致，待人工审阅。D:/temp/fin205-msft-chart-revision-a1保存请求/身份/状态/difference-check与MD/PDF/DOCX；PDF5页、DOCX7页逐页查看无裁切或缺字，附录仍有密集机器ID/长小数和重复本地链接，可用性不能全部验收。导出发现financial_semantics_verified=False本是计算工具不判断金融口径，已修显示“未验证”而非“未通过”；原导出证据不覆盖。

跨窗口实证：旧数据查询thread01a082d0-1573-7db0-976b-0b1cd2869529，固定checkpoint1f1abc8c-1ab0-6bba-802b-71cf76f4204e（10公开消息/5凭证），实际前端创建child01a08322-3d68-7b30-a8a5-987082e2d934；run01a08322-3e0e-7a03-88b4-4cc01a51fd07，4调用19882tokens/估算¥0.016903，8工具、851公开文本片段。没有新SQL读取；两年度USD原数、完整期间、10-K accession、单位更正及工具复算14.93%保持。首段/进度仍夹英文，S2等术语过多，是内容缺陷，不宣称普遍交接正确率。保存D:/temp/fin205-msft-handoff-a1；仅一个真实窗口交接，不代表多代交接/所有长历史保真。

验证：33项会话/工具/原生接续/BFF通过；随后上下文/报告/交接/API定向22通过4.89秒。新增报告测试首次缺operands造成1失败21通过，补齐合成fixture后通过，未改变计算实现规避失败。真实前端6项（1440/1024/390）13秒通过，涵盖交接打开/关闭/固定版本提交、不自动调用模型和原对话控件；D:/temp/fin205-handoff-browser-a1。TS/Vite8.61秒通过。所有费用均为已报用量按公开价估算，免费抵扣和账单未知。

整轮累计176推理尝试、已知4499144tokens/¥2.4483113、1实际传输用量未知；另保留1模型前拦截及早前无效key网络请求。服务18165镜像938f209e62df40b49de2e53cae4fe70ca9be8464863bcbffca44d57eb818e4e2，BFF18795，只有busy=0时重建API，PG/Redis卷和旧BFF完整。没有Hermes追加付费、主线合并或版本变化。剩余复杂题token、两新题/旧失败、统一指标、批准/sandbox产品接入、经授权知识入库和多租户继续处理。

## HPE自由模式、成功依据回读与批准工具（继续，未验收）

产品/工程：通用对话新增经注册的公开搜索/捕获/文内检索薄工具，复用Exa MCP、ExternalSourceCapture、DiskCache和既有BM25导航，文内结果给原文字偏移再按需读。域名/DNS策略与thread作用域继续有效，不把外部文本当用户授权，不自动转为全局知识或金融已审来源。原生HITL前后端接入：显示具体代码和批准/拒绝，绑定thread/checkpoint/interrupt/current run，旧批准过期不执行，不允许批准携带更高权限或新模型。宿主隔离服务采用已装MCP2.1的标准认证和HTTP传输，工具只接code，thread来自宿主认证header；Docker配置固定、无host/daemon挂载和网络。该代码未完成真实部署：自动审批审查拒绝“写入本地sandbox配置并启动宿主MCP服务”的一整条命令，只返回blocked by policy，事后确认无备份和18796监听；没有拆开绕过。当前不能称真实用户批准闭环/生产权限完成。

研究/资格：sandbox/MCP/API18通过，浏览器1440/1024/390共9通过16.4秒，FE类型与构建通过9.79秒；只证明确定性协议/UI，不是生产部署。通用web37通过5材料跳过、另16会话/上下文/启动通过。实际公开RFC9111来源D:/temp/fin205-general-web-a1，2搜索＋1捕获，首次1.9388秒、缓存复用0.026秒，原捕获时间与passage digest一致，0模型；Exa账单未知。文内BM25是在该探测后添加，尚未真实模型复核。

新题4：上传HPE官方176页FY2025年报，https://annualmeeting.hpe.com/2026/proxy/images/HPE_10K2025.pdf；首个IR下载403保留a1，另一个官方公开链接a2成功，非绕过访问限制。实际UI自由模式thread01a0833f-bd3f-7791-a904-b38ab2395a22/run01a08340-2103-7942-a26f-6641ef160525，2026-09-09 07:00:13→07:10:59本地。48调用全部报告用量：输入2055918/输出138216/合2194134，cache hit1568768/miss487150，已知估算¥1.4311354。两个方向HPE_Q1_FIN_CONVERSION与HPE_Q4_JUNIPER_COMPARABILITY均needs_attention，HPE_Q9_COUNTEREVIDENCE planned，research_incomplete，无报告。API run success只是原生控制成功返回，产品为失败待处理。D:/temp/fin205-hpe-auto-a1保存原始题目/提交/final-snapshot.json/metrics-a1.json；不覆盖或自动重新提交。

根因/纠正：16k tokens/keep2仅离线在旧MSFT94请求减少38.29%消息字符，不能当成实际节费或质量合格。HPE暴露ClearToolUsesEdit要求重复原读请求，但原Specialist重复分派拦截把它拒绝；另有数字literal不是纯十进制和operand_quote_not_in_observed_source计算错误、JSON/schema修复、Lead未提交必需计划理由。已加native ToolNode路径从同任务原checkpoint查找原action-attempt绑定的成功只读observation，返回原引用/内容/observation_digest，记录new_tool_dispatch=False，原工具次数与观察账不增加；失败/拒绝不重试，控制工具不回放。55 Specialist定向通过含跨轮不同reason_summary回读和原失败不重试。失败诊断另省略成功method_package大正文，仅保留成功绑定/digest，保留真正MCP错误文本；待验证部署。没有用删历史/摘要替代金融依据。系统提示删除活动路径DELL定死措辞，公开进度随用户语言，独立来源绑定计算允许同轮批量，尚未实测改善。

整轮224推理尝试/6683278已知tokens/估算¥3.8794467/未知1，含失败成本，实际账单/免费额度抵扣未知。当前API部署镜像2e3ca50e…包含16k候选但未含本次回读/web修复；最新构建00981cd9…仍早于回读修复，不能误称已部署。剩余五题末题、旧失败有根因新attempt重验、统一指标、Hermes同条件对照、经授权知识入库、完整长报告/多租户和sandbox阻塞仍开放；不换版本或合main。


## 继续：外网问答、HPE第二次失败、资料双公司与原生批准接线

工程40fd7859已推开发分支，未合main。HPE a2确实部署了成功只读观察回读（12次回读原记录）；thread01a0836c-bef0-72f2-8167-eab92caa423e/run01a0836d-3046-71c3-82f8-44f99ed0d67b，51调用2140450tokens/估算¥1.628082，约9分钟后两个方向needs_attention，其余方向未执行，无报告。保持原失败，禁止第三次盲跑。初判MCP来源登记/回读冲突后检查实际参数：六次source_id_not_observed均用了CHUNK导航ID，而原已观察的是PASSAGE/CALC，并非原文丢失。已向Owner纠正，工具说明明确凭证ID/literal，不能后台猜映射。Q4无ToolMessage错误但24轮到顶，仍需诊断；复杂题未通过。

普通官方RFC问答新检索任务：a1五调用54897tokens/¥0.0323767（旧metrics-a1误含工具行，保留，metrics-a2正确）；a2八调用58847/¥0.0597425仍到8次上限；a3两轮六调用64515/¥0.0606093完成。a1根因为把query传给仅offset读取却静默忽略，a2文内匹配片段仅返回开头500字符，遗漏匹配正文导致反复查找。现在通用工具拒绝错用query，文内BM25命中返回实际捕获原文窗口而非前缀；全网检索仍未审preview。原生SDK投影实际输入加入预检审计，read_saved_result按原tool_call_id回读同thread成功数据，不重复SQL/网络。a3内容仍有英文进度和no-cache/强刷过度概括，不能宣布100%正确。三次目录D:/temp/fin205-general-qa-source-a1/a2/a3均保留。

新题5 a1附件读取失败（2调用5029tokens/¥0.0018087），upload-only SourceDocumentRequest默认空间修复，随后真实返回对象必须model_dump的序列化错误在本地测试发现并修正。a2 thread01a08384-3ce0-7d83-93a6-ccdcc703a47c/run01a08384-3e80-79c1-908a-40febb924fa2本身成功；浏览器因首次checkpoint=None状态读取500中断，未重新提交，恢复snapshot另存recovered-snapshot-a2。本地服务停机后使用原容器/数据库重新启动，第二轮run01a083c8-3584-7381-8034-e11d7f4a4f44复用原始凭证工具换算，无新SQL。两轮7调用56206tokens，四原数/期间/换算保留，仍把CFOBS来源观察号误称SEC原始申报号，英文进度未改好。附件含显式标注的不可信删除指令，模型未执行；这只是该夹具结果，不证明全面防注入。

知识工程：复用Agent Server原生Store保存经批准的固定checkpoint来源指针，个人namespace，逐次native HITL，即使full_access也不能自动入库；读取再次验证来源owner。当前是资料目录/固定版本回读，不是语义检索、研究全局SQL扩池或生产租户鉴权。三权限零写入到批准一写入、跨用户/撤权拒绝的定向测试通过。真实模型第一次只用文字询问批准（run01a083ce-3067-7b62-a8aa-d1963bb8c7e8），没有保存；第二次run01a083d0-198f-7431-be3e-8730c3355201产生native interrupt，但run状态success/thread状态interrupted，发现BFF错误只接受run interrupted。另模型提出CFOBS而不是NUMFACT，原凭证未丢失，不能猜测映射。正修批准接线、来源校验、具体期间/原数/SEC编号预览；尚未批准写入，不重复提交pending操作。

证据/用量：截至上述待批准状态，本轮305实际推理尝试/9087394已知tokens/估算¥5.7134545/未知1，含失败和Qwen/Hermes探测；case5当前9调用80378tokens/¥0.0513886详D:/temp/fin205-case5-metrics-a1.json。费用按统一audit工具公开分时价格估算，非账单/免费抵扣；BFF早期价格版本独立标示，不把两种口径混加。未完成其余旧失败复测/Hermes全执行适配/长报告交付完善/生产多租户；sandbox部署仍受此前自动审批阻止，没有规避。产品不是整轮完成。

检查与服务：checkpoint=None状态可读/不可交接定向通过；知识/会话/上传12后端通过，前端12项三宽度通过43.2秒（D:/temp/fin205-knowledge-browser-a2）。此前浏览器a1误用了启动旧BFF的默认config，端口8765绑定失败、0测试，原件保留，后用现有public config。后续真实批准问题说明模拟通过不能当服务资格。当前18165及18795、原PG/Redis保存；服务镜像/后续批准实测以新增段为准。


## 继续：真实个人知识回读、固定回答导出与全历史指标

产品实证：错误CFOBS入库提议经真实UI拒绝（D:/temp/fin205-knowledge-reject-a1），0写入。模型收到原成功SQL凭证后修正为四条NUMFACT，前端明确显示数值、期间、单位、来源并批准，保存四条原生Store来源指针（D:/temp/fin205-knowledge-corrected-a1；run01a083dc-b740-7162-b166-f6dc59aa45d4→批准恢复01a083dc-d932-74f1-9c57-a289742c3c5e）。随后无handoff的独立thread01a083e0-5e66-79c1-9881-c97754e51583/run01a083e0-5e6f-7b31-af0c-c4c281a1296c，用目录→四次原来源读取→两次来源绑定计算完成，4调用22238tokens/¥0.0347712；四原始对象逐字段一致，含完整财年/单位/原数/SEC provenance，无新SQL或网页。见D:/temp/fin205-knowledge-new-window-a1/source-continuity-a1.json。答案仍错误概括财年“完全不同/不存在可比性”；只算证据回读通过，不宣称金融措辞准确率100%。case5原thread全部入库相关操作累计13调用133374tokens/¥0.1056182，不能再加它的分轮小计。

工程：知识准入强制逐次原生HITL（三权限均如此），来源只取实际成功工具artifact；修原生run success而thread interrupted的审批合法状态，错误来源不能批准，但允许拒绝；空checkpoint不再首屏500。Store按个人namespace和原thread权限回读，不是生产身份认证或语义检索。批量逐项put不是数据库原子事务，部分基础设施失败回执仍待完善。新增批准跳转按钮避免长对话卡片藏在上方，脚本在截图前滚到具体批准卡片。

交付：通用对话每条已保存final answer可按固定checkpoint下载MD/PDF/DOCX，仅正文和该回答之前已读来源进入文档；不导出工具过程/私有推理/后续新答案，不伪造逐句引用关系。真实UI三格式下载D:/temp/fin205-knowledge-answer-export-a1成功；发现截断问题充当长标题及Word公式跨页。改为简短标题和Word标准cantSplit/表头keep_with_next，当前代码通过进程内BFF接真实固定checkpoint导出a2/a3，零模型。a2 PDF2页、a3 Word3页全数渲染查看：中文/表格无裁切，公式整行，附录机器ID与小数仍密集，正文质量问题原样保留。旧a1/a2失败排版原件均在，不覆盖。

复杂题根因：D:/temp/fin205-hpe-auto-a2/last-submission-schema-a1.json仅schema原候选诊断，0模型；Q4最后24轮SubmitWorkpaperAction中claims[1]/[2]的numeric_fact却非authoritative_fact，实际报numeric_fact_requires_authoritative_fact。数字来自原文披露应由模型按证据选择reported_fact，后台不能自动升格/改标。补kind字段说明；父research_session现保留失败worker原agent_state（notebook、工具、最后提交、handoff）在原生checkpoint，不混入case_papers或新提示。旧失败未含此结构不能伪称已恢复全部原notebook；尚未部署新保留逻辑/真实局部修复，未再盲跑HPE a3。

审计与文档：复用既有audit_token_cost新增只读批处理CLI，24窗口按题目/重试/追问关联，22有审计、2缺失（其中0调用已有审计仍与缺失分开）；逐thread/run/actor/phase保留输入输出、cache、估算、未知、最大输入。指标见205_case_metrics_index.md与D:/temp/fin205-all-thread-metrics-a1；不把24窗口称24题，不把历史累计与205总账再相加。5新题覆盖已实际执行，HPE未通过；旧失败最新runtime重验仍未完成。

定向检查：本次API/知识/上传14通过4.05秒，Specialist/父研究图43通过13.37秒，报告13通过3.78秒；此前12浏览器三宽度通过、TS/Vite已通过。实际知识UI提交和导出UI收据比模拟测试单列。git diff --check通过；本轮后续无新模型，总账保持313实际推理尝试/9162628已知tokens/¥5.8024553/未知1。价格是场景估算非账单/免费额度。

部署阻塞：自动审批审查拒绝“核对busy后重启18795 BFF以载入导出标题修复”的整条命令，只返回blocked by policy，没有具体原因，整条未执行，未拆开或绕过。原BFF reload-a4/18795继续服务；原生18165部署6d9a197b…含知识准入和原来源ID说明，不含新失败产物保留/kind说明；最新导出标题/Word行分页只完成当前代码的进程内资格。此前写sandbox配置并启动宿主MCP的整条命令也被同样拒绝、未执行。保持数据库/卷/失败证据，无删除和新版本；Hermes正式适配、复杂研究质量/费用、旧失败重测、多格式完善和生产多租户依然开放。

代码提交：8673a163，21个源码/测试/资格脚本文件，staged差异检查及密钥模式扫描通过（无匹配）；二进制导出/真实模型原文/凭据与数据库不入Git。文档另提交；开发分支推送结果以下一条Git证据为准。

## 继续：失败底稿保留、HPE局部诊断与字段修订

Owner批准按缺口执行，继续本轮205。工程增量：Specialist保存最后被拒的提交字段、校验位置/原因、call关联；轮数上限不再清空最后工具反馈。父图既有失败worker保留配合BFF白名单投影，展示候选正文、已执行模型/工具数、保存观察数和校验详情；不公开私有推理/原notebook/source路径。前端按run_id关联，native success但research_needs_attention也显示未完成，后续成功运行不混入旧失败底稿。

局部真实证据：沿用既有compare_review_model_once/SDK，无新harness。HPE a2原Q4候选在schema层有两条numeric_fact/authority冲突。第一次按原候选实际引用选择输入24,656字符，模型改分类但将6条claim变5条、删退必要研究内容；source检查通过仍判next_action_invalid。第二次补入原观察中已存在的完成日期/融资/寿命/摊销原段落、去除完全重复条目，输入48,697字符；18,373输入＋16,000输出被截断，未通过。无新搜索/SQL/整题a3，没有把局部或截断输出当报告。原件D:/temp/fin205-hpe-submission-repair-a1与a2，预算/停止依据见205_hpe_submission_repair_budget.md。两个新调用共57,882tokens/估算¥0.2382345；205累计315实际尝试/9,220,510已知tokens/估算¥6.0406898/未知1。场景价格非账单；旧HPE失败不覆盖。

根因进展：原35观察包含67个不同PASSAGE标识，关键资料实际已读；多条断言引用购买价表同几个短语，文本可匹配不等于完整语义支持。仅按有误的引用清单恢复上下文会继续漏资料，不能报公共信息缺口。整份底稿重写又导致输出截断；不靠盲增上限或减少必要研究过关。

新增工程采用jsonpatch 1.33（环境已有，明确直接依赖，锁文件仅添加该依赖关系；离线lock缺diskcache缓存失败，正常lock解析217包成功，无版本升级）。ReviseWorkpaperAction允许对已拒底稿按基线digest＋JSON Pointer原值/新值原子修改；禁止控制字段/claim身份变化，修改后复用完整Schema/来源/计算校验。普通审阅者不获得编辑工具；原有报告文字局部修订仍保留。实际SDK+原生ToolNode+host绑定的模拟资格显示两次成功读取后只改字段即可提交完整底稿，原正文保留；这不是付费模型或整题节费证明。

验证：整体相关图/BFF/诊断94通过2材料跳过；新增SDK编辑覆盖后native工具批处理30通过2材料跳过；Provider/组合37通过9材料跳过。UI三宽度3项通过18.8秒，TypeScript与Vite构建通过；后续补测与提交以Git记录为准。没有新增自动摘要、Hermes集成、旧失败重跑或sandbox/多租户部署声明。

部署界限：本轮没有重新尝试此前被自动审批审查拒绝的18795 BFF重启或sandbox配置/MCP启动，也没有拆命令规避。前端构建已生成；原生服务仍未载入失败底稿/字段修订工程，当前网页不能视为新全链路验收。下一步需先完成可执行服务更新，再用真实小修订检验新路径；之后才有依据重跑HPE整题及同条件Hermes对照。全轮仍开放，不合main、不改变FIN0.1.3。

工程提交1bb3d805（12文件）；补充SDK原生局部编辑验证后批处理30通过2跳过，全文/Schema/来源关卡均保留。staged差异检查与密钥模式扫描0匹配。文档单独提交，Git推送以分支状态为准。

## Owner要求完成第一步：真实资格失败与原生路径重验

Owner要求第一步完整执行并允许尝试9月9日DS V4.1 Flash。官方/models当前只返回v4-flash、v4-pro、v4-flash-vision-exp，官方文档未确认独立v4.1名称，未猜别名或宣称已用新版。

四次新局部诊断a3-a6均未通过：Flash auto输出截断，Flash指定工具JSON错误，Pro数组路径误用claim_id，Pro读错误反馈后尝试修改受保护的context字段。全部拒绝、无原底稿修改；共99,710tokens，按2026-09-07场景估算¥0.5972864（非账单）。原件D:/temp/fin205-hpe-submission-repair-a3至a6；指标D:/temp/fin205-hpe-submission-repair-metrics-a2.json。加上此前205为319实际尝试、9,320,220已知tokens、估算¥6.6379762、未知1；以下新HPE运行另计，尚未纳入此数。

依据实测缩小自研：字段编辑默认关闭，仅隔离资格显式启用，保留已有完整SubmitWorkpaperAction与ToolMessage反馈。拒绝候选/校验错误/精确成功读取回放继续启用。新增数组路径描述，诊断输入真实Pydantic错误；修正资格脚本host绑定与生产不一致，不覆盖不同context_digest。定向68通过2材料跳过，失败中的测试变量名拼写已修正后重跑；不把这些模拟通过当真实模型通过。

部署：原生服务18165已构建更新，当前镜像af90533e62dc309efc784e813dc32762d52d0f2e5cae1bfdbe2772203bad44e1，/ok200，容器读取allow_workpaper_field_edits=False；原PG/Redis继续使用，HPE旧失败与MSFT报告checkpoint可读取。18795 BFF重启整条命令再次被自动审批审查拒绝，仅blocked by policy、无具体原因，未执行/未拆命令绕过；BFF仍旧进程，当前失败投影/部分导出新代码不等于已载入。

新HPE a3通过真实前端填写/上传/选择auto+Flash/点击开始，thread01a084d3-abcb-7c43-803e-990e51bf432e，run01a084d4-0d83-76b3-b29a-707be337d644，2026-09-09T06:21:24Z开始。D:/temp/fin205-hpe-auto-ui-a3保存真实截图、case及start200；上传200的响应正文被浏览器缓存淘汰，已明确记录，不重发。此次是同S3新诊断、沿用已有完整提交路径，字段补丁不作为其前置依赖；源问题与176页10-K不删必要研究，预算详205_hpe_submission_repair_budget.md。结果待运行结束，第一步/整轮均未完成。

## a3结束：首次工具结果被提前精简的根因

a3最终research_needs_attention、无报告：49真实模型调用、1,918,418tokens、场景估算¥2.4099352，Q1/Q2失败，其余原计划保留未擅自启动。原生控制success不能当作研究成功。Q1/Q2候选6,405/4,342字符、32/39原观察实际保留在checkpoint。通过当前代码public_state读回原checkpoint验证候选/反馈，18795旧进程仍未载入BFF投影，二者不混淆。Q1的明确人工交接说明也新增白名单投影；无提交时保留工具反馈码，不伪造模型失败理由。真实运行截图D:/temp/fin205-hpe-auto-ui-a3/runtime-live.png，浏览器页面错误0。

源请求回放查明：原生ClearToolUsesEdit keep按工具数量计数；并行一批3–4个读取结果在keep2下，前几条在模型首次看见之前就被清除。a3有18个请求、21个全新结果受影响。修改仅6行，FIN薄适配保留最后AIMessage之后所有未消费ToolMessage；仍由成熟编辑器管理旧历史、配对、错误和保持原checkpoint；不放松硬输入上限、不编摘要。49真实请求/113新结果回放后首次丢失0，材料见D:/temp/fin205-hpe-a3-unseen-tool-batch-loss.json与-fixed.json。原费用脚本一次错误以run目录调用得到0 requests，未当0成本；改用其规定thread目录，正确费用保存在D:/temp/fin205-hpe-a3-cost-a2.json。

工程9cdbb9cd：上述上下文修复、显式模型交接展示、字段补丁默认HOLD及诊断host绑定一致性。57相关检查通过2材料跳过，TypeScript/Vite构建通过、三宽度UI3项通过20.5秒；此前68相关通过2跳过是另一组合，不重复加总。原生18165已加载镜像02a71cbd09b7874aebb4327df1f966523f7b673d15587d4241a9c31ab0e4b715，容器确认新批次保护生效；PG/Redis保留，BFF重启审查阻塞仍未绕过。

第一步继续a4新诊断：同题/原176页资料/auto+Flash，各节点原预算，字段补丁关闭；仅批次首次交付修复纳入真实重验。前端start200，thread01a084e8-6088-7e10-a595-de82201e8020/run01a084e8-bd0b-7a51-bda8-9b445f5e2fcb，2026-09-09T06:44:00Z开始，D:/temp/fin205-hpe-auto-ui-a4。不得未看终态就重启/重发/宣称报告完成。a4前205累计368实际尝试、11,238,638已知tokens、估算¥9.0479114、未知1。a4另计；第一步和全轮仍未验收。

## HPE a4真实终态与引用排版缺陷


a4实际48调用/2,465,574tokens/峰时场景估算¥3.4982508，无未知；Q1底稿submitted，Q3增长拆解needs_attention，其余未执行，无完整报告。累计416实际尝试/13,704,212已知tokens/估算¥12.5461622/未知1。保持原attempt不可变。

原Q3末次9处引用错误，8处只是PDF换行/表格空白/百分号前空格，1处把不连续句子拼接为单一引文。FIN引用校验新增薄的标准库词/标点序列比较：仅容忍排版空白，数字/词边界、标点、大小写、单位与顺序不变；专家提交与责任作者修订共用。原失败候选不改，离线校验9→1，真实不连续引文仍拒绝。77定向检查通过、1材料依赖跳过，0付费。

下一实际资格使用已有同窗口continue_remaining入口，保留a4已提交Q1和历史失败，以新run只推进未完成研究，不创建替代整题重置已完成工作。沿用原题/材料/必要输出/各角色TokenBudgetBasis、Flash/auto配置、模型/工具上限与停止条件；新增根因仅排版引用适配，字段补丁HOLD，不能修改原候选替模型提交。原同尺度a4为费用依据。新run最多一次，执行失败不自动重发；每条已提交研究仍须后续实质审查、报告及多格式验证。原生profile预检与部署完成后才执行。

原生实物D:/temp/fin205-hpe-auto-ui-a4/native-state.json；指标D:/temp/fin205-hpe-a4-cost.json；新校验回放D:/temp/fin205-hpe-a4-quote-replay.json。单次历史推理字段约18万字符仅作体积归因，不输出私有推理。首交付修复没有证明全流程节费。BFF新代码仍未重载（自动审查拒绝，不绕过）。

### a5同窗口真实接续已启动

前端conversation页“继续未完成主题·保留已交稿”200，run01a084fe-d637-7730-9e47-c62b881ca4bf，thread仍01a084e8-6088-7e10-a595-de82201e8020，截图/响应D:/temp/fin205-hpe-auto-ui-a5。原生镜像ed44226c…，/ok200，原Q1与失败checkpoint均保留。最新引用校验已在容器函数探测生效。

新证据：接续Lead实际没有执行原剩余分支，而以现有Q1足够为由提交handoff，07:09Z进入独立case_review。公开理由把Q2-Q8称为Dell/产业无关方向，并称Q1已获supported；这不等于金融验收。Q1尚有明确同比费用总额混用及待核验因果/分部口径问题，独立人工观察D:/temp/fin205-hpe-a4-manual-audit.md未注入模型，检查后续原生独立审查是否发现。不能报告“余下原五分支全部执行”或“范围充分已通过”。本a5正在运行，不重发。

Provider约束已核对：DeepSeek官方https://api-docs.deepseek.com/guides/thinking_mode/明确携带tools的思考请求需完整回传历史reasoning_content并计入context，不能直接删除字段当作节费修复。保持SDK兼容，本轮仅记录体积；后续上下文方案须验证完整工具链边界/明确模式选择，不盲目删推理字段。

### a5真实失败及审查节点限额退出修复

a5 run01a084fe-d637-7730-9e47-c62b881ca4bf在07:12:09Z以error结束。49实际调用、48已报用量969,171tokens，已知峰时场景估算¥1.4935874，另1个verifier请求因兄弟取消而用量未知。累计465实际尝试/14,673,383已知tokens/估算¥14.0397496/未知2。D:/temp/fin205-hpe-a4-a5-cost.json为同thread合计，不与a4重复相加；a5差量另存fin205-hpe-a5-cost-delta.json。没有报告或新导出，不再付费重跑本attempt。

Verifier公开活动已发现Hybrid Cloud商誉减值与Juniper收购因果混用，但尚未提交完整审查。最早技术异常是counter的原生ModelCallLimitMiddleware(run_limit=24, exit_behavior=error)，异常经过MCP TaskGroup包装为ExceptionGroup，并取消运行中的verifier，随后父节点未保存完整阶段结果。此处不是网络不可达或公开信息缺口。

采用现有LangChain原生exit_behavior=end（模型与工具限额），不放大预算、不写新并发/异常引擎。审查collect保留公开模型输出、独立宿主限额通知与实际native模型调用计数；不得把宿主AIMessage算付费模型输出。父图对case_review_incomplete持久保存两位审查结果，进入research_attention，禁止继续写报告或自动接续；原生子图保持可发现。BFF将未完成审查映射到既有失败卡片，只投影公开输出与限额提示，私有推理/原始消息/工具内部上下文不出服务器。

工程曾用Runnable.bind(output_keys)传native计数导致子图发现测试失败；已改compiled graph原生output_channels只增加计数字段，保留原RunnableSequence和静态子图发现。第一次32项最终通过。另把source quote相同排版修复扩到case reviewer，报告问题原句仍精确匹配。最新新增BFF投影检查正在跑。新工程未付费资格，不宣称HPE端到端通过。

最终限额/父子图/BFF/引用检查54通过（20.06秒），工程提交2229bc91；正在部署原生，无新的模型调用。分支目录本身已有通用目标，因此a5称Q2-Q8为Dell专属属于模型调度理由质量失败，不据此另造规则或改成案例固定路由。

最终引用词边界补强3bf68bd8：不能把1234匹配为123或把单词内部片段当完整引文；119后端/原生流程/引用检查通过、1材料跳过（31.18秒）。a5真实前端活动页重新读取，0pageerror，历史失败明确显示且公开活动仍可查看（D:/temp/fin205-hpe-auto-ui-a5/runtime-live.png，已视觉检查），但最新BFF失败候选投影未加载，不能写成真实新展示通过。当前无付费运行。第一步尚缺合格复杂报告、审查真实完成及最新BFF部署后的UI验收；没有HPE完整PDF/Word可交付。

收尾部署：原生镜像adbd0ae878cb65609d47e0577a35b184c9c570e2bf8836252982c8e23f75d017，/ok200，容器排版引文通过/部分数字拒绝，原Q1已提交和Q3失败状态均回读。119检查通过1跳过。BFF18795重载仍受此前自动审查阻止，不绕过、不声称新BFF已部署。所有工程与失败记录同一S3/205，不合main，不更新产品版本，第一步/整轮未完成。
