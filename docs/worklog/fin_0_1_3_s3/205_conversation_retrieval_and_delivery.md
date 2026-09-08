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
