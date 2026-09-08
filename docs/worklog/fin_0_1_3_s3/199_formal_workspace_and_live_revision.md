# S3/199 正式工作台、运行双视图与真实修订验收

2026-09-08，FIN 0.1.3，codex/fin013-report-reader。Owner认可方案D为正式基线，授权自主补齐交互，要求先检查前端，再接后端，并从前端提交1–2条真实小意见。该授权覆盖本轮有界真实模型调用；此前设计-only/0模型停止点被替代。Hermes继续后置，公开分支不推送。

工程提交acd28b9f，19文件；只保存在本地分支，未推送公开codex分支，main未改。本轮结束无活动付费研究，v5等待Owner内容审阅。

## 实施切片

产品：正式工作台/全部研究/待审阅、当前任务六个子页、桌面折叠和原生dialog窄屏导航、来源资料/修订列表、准备草稿与明确开始研究、统一研究蓝和明暗/减少动效。报告章节→引用采用可访问CSS横向文档树，真实依据图仍用React Flow，正常字号无自动缩小；保留原文、checkpoint和目标修订。

工程：采用React Router声明式路由和useSearchParams（官方 https://reactrouter.com/api/hooks/useSearchParams 、https://reactrouter.com/api/declarative-routers/BrowserRouter）；浏览器前后退和定位不造路由器。UI草稿/阅读位置只存sessionStorage，按任务/报告基线隔离；不能当运行时状态。复用LangGraph SDK、原生Command/多任务reject和现有责任修订图，未造任务队列或推理规则平台。上传能力由BFF投影，不在前端按case_profile判断。

已发现范围边界：导航与目标绑定通用；现有真实runtime数据composition仍是已资格Dell数据配置。两个不同公司合成任务验证接口隔离，不构成任意公司真实研究资格。此轮不暗中扩展数据底座。

## 真实小修订TokenBudgetBasis与停止条件

计划live-a1：在当前已存报告v4选一条实际引用，通过图→意见→预览→确认提交；仅补清楚比值的分子/分母/期间及解释边界，不改变原始数据或整体研究结论。请求绑定真实citation_id、v4/digest/checkpoint；意见为用户主张，不是证据。提交前保存完整公开baseline，模型密钥留在已有服务。

- 目的：核实明确修订目标能进入原生human_review/research_revision，按既有责任图执行Writer及独立报告Verifier，并回传真实候选差异。研究责任节点仅在实际重大问题被路由时触发；不强制遍历全部专家。
- 输入规模：当前正文、已审综合判断、紧凑底稿目录和单条目标上下文，来源按需读取；不加载其他任务或私有思维历史。
- 必需输出：报告候选、独立审查、目标/基线/实际run、逐调用用量与旧版本可回读。用户未接受，不自动accept。
- Schema负担：沿用已资格Report/ReportReview、引用ID与责任字段；不新造金融关键词规则。
- 质量风险：原始引用主张可能早于正文；仅表述意见不能作为改数或证明因果的许可。任何额外研究问题必须保留并报告，不为节费标为通过。
- 对比依据：现有节点预算记录Writer局部编辑约3调用；不是本轮性能保证。原任务28runs、359请求，其中358已知；已知费用29.533684元、1未知，不计未知为0。外部导入修订费另列。
- 推理配置：保留configs/research/runtime/research_session.json中DeepSeek-v4-pro thinking enabled/low。Writer与report_verifier各20模型/64工具上限，每调用max_input_characters700000、max_output_tokens32000、timeout480秒、transport单次且无重试；触发repair/synthesis/research_verifier时沿用其各16/48的现有任务用途TokenBudgetBasis。无新增模型节点，不降低既有输出预算。
- 停止：本轮先1次小修订；只有首例完成且第二例有独立验收价值才考虑第2次。未知提交/transport失败/截断停止自动重发，保留原失败。观察到30分钟、5元已知增量、或转入明显超出小修改的全案研究时停止此资格尝试并保存未完成证据，不能把停止当内容通过；这些是本轮人工监护线，不声称原生服务有精确总费用硬闸。原生节点固有上限/失败闭锁继续生效。

## 资格记录

A1前端9项：图与新增导航6通过；原报告历史3失败，定位为旧测试选择器与新侧栏重复入口/移动导航不兼容。保留D:/temp/fin-formal-workspace-a1/results，修正测试操作为真实新导航，不削弱原文/版本/费用断言。后续A2待记录。

后续A2九项通过。加入Owner最新运行双视图需求后，A3前两项在BFF重启未就绪时连接失败；A3/A4运行测试fixture错误返回版本列表，修正fixture后A5抓到真实深链bug：报告状态reset将activity/review自动导航回graph。已将主动返回与版本重置分离，A6十项全部通过（35.1秒）。这些失败仍留在各attempt目录，不改写历史。另修正异步旧任务响应覆盖新任务、按任务/版本恢复阅读和草稿、单次工具成功与阶段成功混用标签，A7为最终回归。

Python targeted_revision + dell_report_session：34通过（16.77秒）。TypeScript与Vite通过；仍有既有大包警告，不宣称性能问题已解决。新增react-router精确7.18.3，npm依赖安装audit显示0 vulnerabilities（非全项目安全保证）。BFF按已核实命令行替换原4512，实际服务PID25116，原生18165/PG/Redis未重启、未清库，日志D:/temp/fin-formal-bff-a1.*.log。

## live-a1 实际结果

前端CUA实际操作：真实v4 → 现金专题 → P01:C9 → 填写小意见 → 预览 → 确认提交 → 运行与费用双视图 → 修订记录 → 比较基线与当前报告。没有用脚本代替前端POST，没有第二次模型调用尝试，没有自动accept。

- thread：01a077d8-a47c-7280-98f5-3df94b219488。
- run：01a0801b-0b5b-7c83-a16b-413ad918f450，2026-09-08 16:20:51 +08:00开始，success；原生耗时283701ms，返回ready_for_human_review。
- request_id：866754db-8de9-4b23-ba45-504b3b3ed60e；目标P01:C9，基线v4/digest00f61bb881fddeec261c81ebfad16d0bbf58e5955a75900e705a92fc980d9089/checkpoint1f1aafc7-f1c7-6505-803c-cd127da65489。原生run metadata与浏览器目标一致。
- 实际Writer 3模型调用、report_verifier 3调用，无其他研究作者模型被误激活；前端流实时显示读取当前报告、当前底稿与对应source等工具事件。
- 6/6请求用量已知：输入253543、输出18633、合计272176 tokens；输入缓存命中155008、未命中98535；本run未知请求0，已知估费1.436408元。费用不是账单；原任务旧未知请求仍保留，不能用本run零未知覆盖累计缺失。
- v4→v5只变正文第三节目标段落一处，新增Q2单季/合并/GAAP分子分母及“不是客户回款率”，保留非因果限定；引用对象和图表完全相同。按基线checkpoint读取的v4 report与提交前baseline完全相同。
- 独立Verifier确认口径修改落地，同时返回1条advisory research/P01：底稿C9的旧因果措辞尚未同步；无material或unresolved_data_request。该遗留不是前端/修订成功标识能消掉的问题，已显示为建议项；原始主张与当前正文的区别继续保留。Verifier自然语言摘要沿用输入report_version4，不覆盖服务端实际提交后的v5。
- CUA实际点击“比较基线与当前报告”，页面呈现上述同一处真实diff，未只看API成功。

证据：D:/temp/fin-formal-live-a1/baseline.json、baseline-versions.json、after-submit.json、progress-01/02/03.json、final.json、diff-verified.json。首次手动只读diff检查用了错误query名并得到422，保留diff.json；按实际API参数before核对成功，前端本来使用正确参数。

## 当前能力与剩余边界

最终A7：10浏览器全部通过（40.5秒），覆盖1440/1024/390、历史来源/计算/原文、目标提交、多任务隔离与刷新恢复、路由前后退、准备草稿零模型、运行目标/actor筛选/费用未知边界。CUA打开真实深色地图核对后恢复system；真实v5修订diff已在前端读回。构建index-WVv95HZR.js/index-DK3rPtL9.css。git diff --check及候选23文件凭据模式扫描0命中；非全仓扫描结论。

本轮完成正式界面工程切片及1条真实报告表述修订资格；不是仅文档或设计进展。运行现场是实际任务/阶段卡片＋可筛选公开事件流，尚非逐token自然语言进展、完整逐话题产物图、任意节点暂停或重排。历史缺失的细粒度工具事件不会补造；报告章节与runtime话题缺少明确关联时不猜配。

本次正确激活Writer→独立Verifier，不能据此声称任意前端判断已能精确触发最小作者重算。底稿C9旧陈述仍需research层后续同步；没有将其偷偷升为material来强迫多作者运行，也没有新增Dell关键词规则。通用UI/目标接口已实现，真实跨公司数据底座仍待资格。Owner尚未接受v5和最终交互；FIN0.1.3、公开main与Hermes边界不变。
