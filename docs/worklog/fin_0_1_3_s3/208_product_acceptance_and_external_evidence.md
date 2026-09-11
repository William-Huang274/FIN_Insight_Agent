# 208 · 产品验收、对外技术报告与简历证据

2026-09-11；Owner批准六项补测和必要修复，最终交付对外技术报告及可用于简历的实测成果。延续FIN0.1.3/S3与当前分支，避免将跨模块验收误作新产品版本。基线fe411d7a；旧失败和用户完成版不覆盖。沿用既有项目PRD及207工作，本文仅管理本轮验收证据。

## 工作包与验收

1. 人工修改持续生效：原生读新版底稿/报告、追问与关联修订、重启及多格式一致；来源与用户意见不混同。
2. 故障恢复：旧响应回放覆盖JSON/来源/并行失败、断流/重启/重复提交/未知请求，修复工程问题后重验。
3. 真实12–16轮跨主题工作：更正/撤回、摘要和跨窗口、重启，核对期间/原数/版本/取消项；Hermes仅做同能力范围对照。
4. 20–30条检索开发/验证查询：公司/期间/同义表达/版本/多来源/无结果，BM25、向量和混合重排同资料比较；明确候选覆盖、缓存、用量，验证集不得反向调参。
5. 实际双用户与sandbox：身份服务、后端归属、检索/导出/交接隔离、具体批准与拒绝、临时目录、少量并发。现有仅通用对话OIDC试点，不将尚未实现的产品隔离说成通过。
6. 固定最终部署版本，真实前端四题：普通问答、数据查询、自定义方向自由研究、中等研究加人工修订导出。

最终产物：docs/public中对外技术报告（架构、可复现实验、基线/样本/指标、改进和已验证边界），以及简历中文/英文可引用成果与逐条证据。只有工程原因排除后仍复现的模型指令遵循/语义能力问题可以作为边界；未修工程故障不以诚实披露替代修复。报告不使用真实秘密、私有原推理或虚构统计。

## 执行约束

优先回放和原生组件集成；真实模型调用前按现有preflight与逐节点TokenBudgetBasis登记，不重复整题追绿。第一/第二摘要不增加客户端输出上限。所有初始失败计入完整成本；修复后新attempt复验。权限测试仅使用隔离测试账号/容器/临时文件，无用户原件破坏。通用设施优先既有LangGraph/Assistant/Store、Pydantic、Docker和成熟OIDC，不自研工作流或认证服务。

## 当前进展

- 人工修改读取真实缺陷：human_edits已保存但read_current_workpaper仍返回原文。native图先复现，再通过版本化人工视图修复；原claims/sources保持原件且明确标作历史，后续作者修订保留已采纳人工版本。追问seed改为索引按需读取，避免重复携带两份正文。未知底稿引用在人工提交时拒绝。
- 回归136通过、1私有材料条件跳过；其中修正一个过时测试：unfinished_only接续禁止开启新任务，新增补研请求单独验证。零模型两追问脚本回归另1通过；这些不是独立真实题计数。
- HPE完成版冻结副本真实追问2/2提交，7次DS Flash thinking enabled/low，112863已知tokens，未知0。第一问正确区分并表/有机、CFO/两种FCF；第二问拒绝与原文冲突的新结论。逐项人工阅读，不冒称金融全覆盖。原前端报告v2/人工2次未改。证据D:/temp/fin208/human-followup-live-a2；a1因脚本调用方式import失败，0模型，保留failure；支持python -m入口。
- Docker实际3场景通过（临时写/宿主根只读/禁网/无凭据、另一任务空目录、超时停止）；native SQLite重开→真实HTTP MCP→Docker四权限场景通过，拒绝0执行、批准1执行、两委托模式各1执行。均0模型。证据D:/temp/fin208/docker-isolation-a1和sandbox-approval-a1；不当作前端或多用户验收。
- 尚需本轮部署和其余工作包；发现研究线程与配置缺owner隔离，先补齐再进行真实双用户验证。未形成最终报告或简历指标，不称本轮完成。

## 第二段实际证据（执行中，尚非最终交付）

- 产品增量：研究线程/运行/导出/底稿/配置读取与应用绑定服务端verified owner，原共享人工审阅入口在OIDC产品模式拒绝；前端身份门禁、owner分区浏览器记忆与项目分组。Keycloak26.7.3真实HTTPS授权码PKCE→Authlib→PyJWT校验issuer/audience→安全签名会话；Alice/Bob实际浏览器登录和退出通过。独立18815资格入口，不冒称公网生产部署。39项真实HTTP归属隔离与8并发读，0模型；证据identity-resource-a1、identity-browser-a1。Keycloak开发模式、TrustedHost正式域名、生产运维仍不在已部署声明内。
- 工程增量：模型调用最后一个已授权名额禁用进一步工具，要求交付已有结果并保留未核实项，不增加调用额度；浏览器持久提交UUID，BFF按verified owner+UUID+请求内容使用DiskCache原子回执。同内容失联重提交重放原结果；不同内容拒绝；未知结果不自动过期重发。5后端回执检查及真实浏览器网络断开/刷新复用key通过，13浏览器检查通过。无key的旧API保留兼容，不宣称所有外部客户端无条件exactly-once。
- 成熟组件选择：检查原生Agent Server0.13.3/SDK，未提供客户端run_id或幂等键；snok/asgi-idempotency-header缺owner隔离与payload冲突核对，且待定租约不能满足付费调用未知结果保留要求。因此沿用已采用DiskCache atomic add做本地薄HTTP回执适配，任务创建执行仍归Agent Server。多个主机未共享交易存储时不宣称可扩展此本地回执。
- 真实RAG：固定739原文叶节点/1105嵌入片段，28查询（开发14/验证14，各12有答案2无答案）。同资料BM25、Qwen text-embedding-v4（1024维）、BM25+向量候选再qwen3-rerank；167个请求全部已知完成，embedding317882tokens、rerank370916tokens。按官网两模型均0.0005元/千tokens的日期价格方案估算总¥0.344399，未扣免费额度，非实际账单。精确重复全部0新API请求。开发Hit@5：5/12、8/12、11/12；验证：7/12、9/12、12/12。固定锚点不是全部相关段落，不能把候选命中当回答正确率。
- 检索初始失败和修复：development-a1发现RFC no-cache/no-store标注漏0312，公开开发标注修正保留a1；validation-a1在R23纯中文问题被ASCII tokenizer误判空查询，尚未发对应API即失败。复用jieba0.42.1搜索分词修复，保留英语既有token行为；validation-a2重放复用已付款缓存，development-a3同代码重评0调用。因看过验证结果后修工程缺陷，不称盲测；没有按验证金融答案调参。原件D:/temp/fin208/retrieval-*。
- 长对话a1第二意图：8模型+1摘要、109185tokens，先取到正确财务数字后重复检索，耗尽调用无答案；原件保留。a2接续前三意图成功：正确交付MSFT数表，保存工作底稿，回读HPE人改2次/v2并保留财务区别。第四意图重写完整底稿时output3000截断，拒绝部分工具写入，旧v1保留。责任属于全篇写入接口和输出预算不适配，不能说是金融知识不懂。新增WriteWorkingNote mode=append，仅输出新增正文、原版本CAS合并，旧版/他人角色/并发冲突验证27通过；模型无严格章节模板。a3正在同一窗口接续，尚不能称12轮通过。
- 18796产品sandbox启动与两份配置接入：自动审批审查在执行前拒绝，Owner再次明确授权后再次拒绝，仅blocked by policy，无具体原因。未执行未写配置，没有绕过；与既有Docker/SQLite-MCP隔离审批资格分列。用户授权有效，不能反复索要同一授权；当前唯一此类环境阻塞。
- 原HPE完成版不改。本轮原生镜像先a8d2e68e、后6084c6c增加底稿追加，后端18795当前b3，18815身份资格入口独立；最终固定部署验收尚待执行。外部报告与简历结果尚未最终发布。

供应商映射/价格核查：https://api-docs.deepseek.com/zh-cn/quick_start/pricing/（2026-09-11）；旧deepseek-v4-flash当前映射V4.1-Flash，Pro仍V4-Pro-0813，公告09-14中午后Pro名也映射Flash；不以别名宣称独立模型对照。旧成本审计函数继续保留09-07方案；产品展示新请求按09-11核查价，未知不当0。

## 第三段：长对话故障收口与真实接续

- a3追加底稿v2成功；下一HTTP读取后，原生累计两次摘要耗尽，80k输入前置边界阻断。改为采用原生Summarization每个新用户回合最多一次按需摘要；摘要前以已有saved-result reader把已读旧工具参数/结果投影为定位符，保留未读批次、工具错误及原checkpoint。研究图摘要策略不随通用对话改变。真实失败checkpoint零模型回放208296消息字符→21544请求消息字符，原始digest未变；这是结构验证，不是摘要语义正确率。
- a4七次运行结束，其中两项未交付：工具上限提示、DSML工具协议被当正文。人工逐条阅读发现，修正资格脚本只看native success的漏检。采用原生ToolCallLimit continue阻止超额工具后允许在原模型额度内交付；公开投影把已识别协议/限额非答案标needs_attention、禁止导出，不执行文本里的工具调用。保留私有原件，不伪造结果。
- a5仅接续这两项，两次均交出正文：更新接续底稿v5；回读MSFT CFO136162、现金capex64551、FCF71611（百万美元）及HPE报告v2/人工2次。没有重跑取数。仍有模型呈现边界：用户要求百万美元而主表先列USD再补百万；原记录与旧摘要中的NumericFact ID有冲突，模型保留未决而未伪造新值。后续交接需读原回执，不能把摘要声明升级为原始事实。
- 此时同窗口17个真实用户回合（原12意图+5次有依据的局部接续），不是17独立用例或12题首遍通过。原报告仍v2/人工2，底稿历史版本保留。尚需真实重启后的新窗口交接、Hermes同能力对照和最终四类界面验收。
- 工程验证：最后集成85项Python通过（identity/receipts/conversation/delivery/notes/summary/context/Chinese/dated-cost），先前26交付定向检查包含其中；不得相加作独立测试总数。TS/Vite通过。原生镜像e7935a6a已部署、BFF18795 b4已加载；18796部署审核阻塞未绕过。

## 第四段实际结果与新定位（继续执行，未收口）

- 工程切片4645c383已提交并推送。最终公共前端36检查通过（final-ui-a1.xml），85Python与子组不相加。真实提交回执prepare→重启18165/18795→replay，三次均同一native草稿/零run，证据submission-restart-a1。
- 长会话：同窗口17回合含5个有依据的局部恢复；重启后真实前端开子窗口两回合，原数/百万美元/取消项/HPE人工版均回读成功。合计19个用户回合、81模型请求、1,231,464已知tokens、未知0，含初始失败与摘要成本；不是19独立题、不是首遍全部通过。handoff-a1原窗口CFO主NumericFact与FCF输入ID不同，但相同CFOBS/数值，模型通过原回执正确说明身份区别，未凭摘要改数。保留融资租赁金额未查等边界。
- Hermes同题三轮：假设ALPHA CFO120/capex40→更正50/FCF70，底稿v1→v2、回读原始更正、历史值撤回，原生与Hermes均交付。原生10调用65713tokens；Hermes原服务私有审计8调用44961tokens/未知0。原生另有计算器工具，Hermes仅五项工作记忆工具，因此不是严格等工具消融，也不是完整投研迁移；不把短三轮成功当无限长记忆证明。BFF原生审计没有Hermes逐调用记录却返回0，已修为None/未取得，原生Hermes阶段仍显示其累计用量，不能把0当费用；对应回归新增。
- HPE真实最终前端复验：hpe-final-ui-a3，原报告v2/人工修改2、角色底稿差异滚动、MD24095字节/PDF312658/Word105424均下载通过，0模型。a1资格选择器误匹配两个导出栏；a2脚本误读history滚动容器（真实容器是rs-heading），均只修资格脚本并保留原件，不算产品新缺陷。
- 自定义方向自由研究a1确实保存新Assistant版本并传入任务，但43请求/1,542,624tokens/未知0后research_needs_attention、3底稿均为本地数据缺口。**主要根因已确认是数据接入工程错误，不是模型金融能力**：通用对话读新增HPE/MSFT955行mart，研究仍读旧Dell/MU/NVDA1319行mart。原模型只是忠实返回各自库的不同覆盖；不得以人工签字消除该工程缺口。a1 thread01a08f18-0b40-7813-8f1a-df294d6a5b6f原件保留。
- 修复采用既有SEC parser与fact mart builder合并兼容源policy，构建新2274行/5公司只读快照；保留两个源policy/快照，定义或同发行人源冲突拒绝，无覆盖写入。新的host-approved runtime fact reader和planner均绑定同快照digest，冻结Dell源inventory及旧报告绑定不变。financial-route-parity-a3同5公司×2FY×3指标的10批MCP/通用工具查询，全部非空且数值/期间/单位一致，0模型；a1缺host环境、a2用旧两公司库测Dell为空的失败原件保留。数据/API17通过11私有跳过、研究startup/session37通过；真实parity不依赖跳过测试。
- 新快照D:/temp/fin208/unified-financial-mart-a1/financial-facts.sqlite，SHA256385485745a01dddc80c3201880a35d6eed948ad8fed174c656b87d86543894d8；只更新host-settings的conversation_fact_mart，备份host-settings.before-208-unified-mart.json，容器挂载位置不变。c1a1269e镜像/18795 b6已加载，容器读回5公司2274行。18796未启动，这次改的是既有取数数据绑定，不是绕过sandbox审核。
- a2重新使用同题/同自定义方向版本，因原三稿均描述失效的数据绑定而新开attempt，不把它们当现有数值证据。thread01a08f2e-422f-7b32-94a7-a799775216dd / run01a08f2e-4242-7350-97d4-0cecc92b5828正在运行；只一次有根因修复的新执行，不自动重试。新增源码尚待最终review/commit，仍须完成该题交付、必要人工修改、最终技术报告与简历证据。公开报告不能声称sandbox产品部署完成。

## 第五段最终交付（2026-09-11）

**产品增量**：MSFT自定义研究现为report v2 / human_completed /人工修改2次，两份责任角色底稿、1幅来源绑定数据图；实际前端修改并确认、保存个人研究记忆，0模型。完整数值FY2024→FY2025 CFO118548→136162、现金capex44477→64551、派生FCF74071→71611，均百万美元。修改未改来源事实/图表数值。原HPEv2人工2保持不变，最终部署再验MD/PDF/Word及角色底稿滚动通过。

**工程增量**：数据入口统一后，a2已交出两份正确数字底稿，但主Agent自行把历史Reviewed路线缺口写成当前question_coverage未解决；不是validator强制把所有历史路线做完。当前用户任务的scope与参数反馈明确旧路线仅作覆盖记录，不能假称已完成；实际必需缺数/冲突仍需处理。a3经明确范围确认进入独立review；review产生错误财年理解和超范围依赖。新增已有interrupt内的amend_reviewed_workpapers薄接续：CAS校验底稿/审查/人工历史digest，逐条处置material finding和unresolved request，修正必须落实到责任底稿，保留原结构化claims与review。human_edits传入convergence和writer，输出仍待最终人工确认。最终人工编辑新增图表interpretation字段、范围与引用检查，不能通过此入口改图表点/单位/来源；UI按写作角色列图表说明差异。

**真实模型与边界**：a1 43请求1542624tokens/¥1.573728；a2 27/927019/¥1.091936；a3 38/1321253/¥1.214529；a4 17/672006/¥.752876。合计125请求4462902tokens/估算¥4.633069/未知0，含首轮工程失败；成功交付窗口82请求2920278tokens/¥3.059341。均保留原件，Flash别名按调用日期解释。这个规模对窄题仍然偏重，不作为高效率或全自动成功的证据；已停止继续付费。a4终审仅两advisory无unresolved：其一误把sourceunitUSD+百万显示缩放视作单位错误（未采纳破坏缩放的改法），另一指出派生FCF被写作原始事实（人工修正文/角色底稿/图注）。最终UI的manual_complete native run01a08f64-f141-79c2-962d-b8c9a2c785dc成功且0模型。

**实际UI与文件**：custom-final-manual-ui-a1动作已成功，但脚本在异步checkpoint落盘前读取而误报未提交；新脚本加入有界只读轮询，a2使用verify-only，不重发修改，保存记忆成功。custom-final-export-a1真实MD34931/PDF302619/Word94061字节，PDF10页/Word1图1表；一般RFC回答final-general-export-a2三格式4735/151573/39552字节，数据回答final-data-export-a3为6465/143224/40324字节。PDF均渲染并逐页缩略检查无裁切；Word只验ZIP/OOXML表/图结构，机器缺少渲染器，不冒称视觉验收。普通回答的导出来源改为本轮已读+正文明确引用的旧来源，去掉更早无关金融题来源；相关13检查通过。来源/计算附录仍长，是呈现余量，不影响正文交付。

**工程验证**：final-integrated-a2为104通过/5私有fixture条件跳过；manual-caption-a1为24通过，桌面/移动图注编辑2通过，与其他组重叠不相加。TS/Vite成功。最终native image05f89122cffbdd95a56bfae9af0d5d5cfaea6c1e9cb4ced8be05c307e7f1a670与18795 b8 parent36148已部署。新实例在真实UI使用新chart_edits接受并保留完整图表provenance，证明非仅静态bundle更新。

**对外产物**：docs/public/technical-evaluation.zh-CN.md与英文版、evaluation-metrics.json、resume-evidence.md；真实HPE/MSFT完成版截图；evaluation目录公开28条问题、逐题top5和739节点manifest（正文/私人附件URL不公开）。verify_public_retrieval零API独立复算Hit@5及anchor Recall@5均一致，MRR20只保留原测量值不声称top5包能重算。README三语入口链接到产物。19真实对话回合含5恢复，不当19独立cases；24正例23/24候选命中不当答案准确率；Hermes三轮对照不当全研究图迁移。

**唯一当前外部部署阻塞**：18796产品sandbox自动审批两次执行前拒绝（第二次已有Owner授权），无更具体原因；未绕过/未再索授权。独立Docker与审批链已验证，但产品UI→真实sandbox端到端仍未部署。生产身份运维、跨主机配额/幂等/大并发、多Agent长期全局重排属后续范围，不以本轮本地证据冒称完成。新增代码和公开报告待本段最终Git核对后提交推送。

最终复验：同一前端构建36/36通过（final-ui-a2.xml）；hpe-final-ui-a5在最终05f89122镜像/18795b8上报告v2人工2与三个导出文件保持一致。最终状态回执final-deployment.json。工程源码/测试/操作脚本已提交cafa9d4c；公开CN/EN报告、可复核检索记录与日志在独立证据提交中落库。所有已授权可执行工作已交付；18796自动审核拒绝的部署仍未完成，不把隔离资格当产品接入。

## 18796 接入阻塞只读诊断（2026-09-11）

- 研究/诊断证据：回查原始工具回执，205 阶段一次、208 阶段两次启动请求均在 CreateProcess 前返回 `blocked by policy`；北京时间分别为 09-09 06:50:29、09-11 13:17:49、13:19:20。最后一次已有用户明确授权。此前“两次”仅指 208 阶段，不是全部历史尝试。
- 当前状态：18795、18165 有监听，18796 无监听；两份运行配置均未设置 conversation_sandbox_url/token，208 配置备份和 sandbox stdout/stderr 文件均未生成。这是部署命令未执行，不是服务启动后崩溃或已连接后的鉴权错误。
- 本机 Docker 命令当前可解析，固定 sandbox 镜像仍存在；已有 sandbox-approval-a1 的四项真实隔离/批准测试通过。上述证据不代替产品端到端连接验收。
- 可见用户规则共 502 条，均为 allow；用户配置为 never/danger-full-access，仓库无本地 .codex 规则。原始拒绝回执无具体理由；可读本地日志数据库未找到对应时间的策略判定详情。不能据此断言匹配了某条静态规则、端口被禁、Windows 权限不足，或确认自动模型审查的具体理由。
- 三次命令均把配置备份、生成服务凭据、写两份配置与后台启动 MCP 服务放在同一复合命令内。可定位到执行入口策略层，但无法从现有证据拆定是哪项操作触发拒绝。不通过改写或拆分被拒绝命令试探绕过；不再向用户重复索取相同授权。
- 本次只有诊断与记录增量，没有产品/工程实现增量、没有新付费请求。后续部署仍须取得可解释的执行许可或由操作者明确手动启动，再核验服务健康、容器访问、鉴权及前端批准到真实隔离执行的完整链路；当前继续标记未接入。

## 可审查的 sandbox 部署入口（2026-09-11）

- Owner 同意上一段可检查部署/必要时手动启动方案。工程增量：scripts/deployment/local_sandbox.py 复用现有 Docker/MCP/Uvicorn，默认只读 plan；configure 备份两份配置、保留其他字段、共享生成凭据且不打印、失败回退；serve 前台显示错误，不启动后台进程、不改权限/防火墙、不重启其他服务。已有配置冲突拒绝覆盖。不是新服务管理器。
- check 不执行代码：先核验宿主无凭据/错误凭据 401、认证工具目录，再可从已有 native 容器读取自身挂载配置、检查 MCP 连通及凭据一致性。容器挂载是单文件，宿主原子替换后是否读到新文件必须实际验证。Hermes 当前未注册 sandbox，不将 native 接入范围扩大。
- 验证：14 项定向 pytest 通过（部署配置/失败回退/鉴权/容器陈旧凭据与错误脱敏/原隔离适配测试）；真实只读 plan 验证固定镜像可用、configured=false、18796 无监听。此轮未运行真实 configure/serve，没有触碰两份实际配置，没有重试此前被拒绝动作，0 模型费用。
- [操作者步骤与检查边界](../../architecture/local_sandbox_operator.zh-CN.md) 已提供实际机器命令。剩余阻塞：由操作者手动启动后，才可运行宿主/容器真实 check 和产品前端批准到隔离执行验收。此轮是工程入口交付，不是已部署产品增量。

### 操作者 Python 启动失败修复

Owner PowerShell 截图显示 `.venv/Scripts/python.exe` 在加载 uv 缓存 CPython 时 `No Python at ...`，configure 未执行，if 条件跳过 serve；不同于此前 CreateProcess 策略拒绝。Codex 当前同路径及 Windows PowerShell 子进程可正常启动，文件存在且无目录链接，具体会话差异未复现，不宣称缓存被删除。为移除该部署依赖，将同一 CPython 3.11.14 复制到已忽略的 `.venv/sandbox-python311`，原 pyvenv.cfg 备份为 `.venv/pyvenv.cfg.before-project-python-20260911` 后仅修改 home；不删旧解释器、不改系统 Python、不重装项目依赖。新 Windows PowerShell 进程确认 base_prefix 指向项目目录、MCP/Uvicorn 可导入，真实只读 plan 通过，原 14 定向测试再次通过。操作文档补充失败时明确报错。真实 settings 仍未配置、18796 未启动，等待用户原终端实测；0 模型费用。本次是本机解释器依赖修复和文档增量，非 sandbox 产品接入完成。
