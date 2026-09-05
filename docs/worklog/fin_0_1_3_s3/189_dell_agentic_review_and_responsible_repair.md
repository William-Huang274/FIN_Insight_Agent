# S3/189 Dell 多 Agent 审查与责任回派

状态（2026-09-06）：A5 已真实达到 Q1 `review_cycle_accepted`，两位独立 reviewer 均 `no_material_finding`；A1–A4 原失败保留。下一跨主题任务交接已本地消费真实 A5 底稿并经实际 MCP 查询通过，尚无自主 Lead/完整产品 PASS。起点 863f7ab4（clean/pushed），FIN 0.1.3 / 同一 S3。

## Owner 方向与最小真实增量

2026-09-05 Owner 明确授权：单 Agent 跑通后继续多 Agent、完整产品，普通实现/网络问题自行修复后继续，DeepSeek 额度充足。安全/金融事实标准不放松，不无限重试或提权。

本包直接落实现有详设 Wave 3 / §§6、10、11：将 R11 原底稿和实际观察作为不可变输入，两个独立、可自主查询的 Counter / Verifier 子 Agent 并行审查；finding 回到原 Specialist 的新 revision，自主补查/修订，再复审。此包不是 R12 单 Agent 重跑，也不是 Q1–Q9 全产品 PASS。

## 实施边界（先冻结，允许据真实证据修正）

- 复用同一个 LangGraph Specialist tool loop、ToolNode、MCP、SDK、Agent Server/PostgreSQL/Redis/LangSmith。外层使用标准 StateGraph/Send；不添加依赖、scheduler、queue、rule engine 或第二种 runtime。
- 审查角色以专门 SubmitReviewAction 返回 finding；确定性层只核对 JSON、目标 revision、原文 anchor、已观察引用与责任身份。语义/完整性/因果判断交给模型，不将本作者 R11 中文复核注入模型。
- 审查可读取原 Agent 的完整已观察 source context、底稿/claim 和简短依据；不能读私有 provider reasoning。各子 Agent 的 SDK 对话隔离，同一子调用保留自身原 reasoning/tool messages。跨 Agent 移交显式 artifact，不冒充 durable conversation resume。
- 原失败及 R11 文件不修改；新修订单独保存，引用权限仍是 Reviewed / S2 / 已读 PASSAGE；不新增网络入口、Evidence admission、S2 写或发布权限。
- 首个可执行切片只审查 Q1；最多一次责任修订和一次复审，两 reviewer 每次最多 6 模型轮/8 数据动作，原作者修订最多 12 轮/16 动作。这是异常停止上限，不要求用满。每节点记录实测依据的 TokenBudgetBasis；失败不能被吞掉成为 no-material finding。
- 真实执行仍走现有一次启动 runner 和服务器身份绑定。允许在现有 authority 增加显式 workflow/seed/node budget 字段，不新建另一套执行协议。输入 seed 只读绑定文件 SHA；所有输出在新 attempt。
- 定向检查：真实 R11 移交不改原件、不同 reviewer 上下文隔离、审查权限/引用/target 绑定、finding→责任修订→复审、任一失败不能 aggregate PASS、旧单 Agent 回归。通过后实际 DeepSeek 调用并读原稿，不以测试数代替内容验收。

## 后续方向

本闭环有真实结果后继续既定动态 Lead / 并行专业 Agent / Q1–Q9 覆盖与报告，再到 Workbench/HITL/运行后交互。避免回到单个语义问题无限修补；仅将经源上下文证明的根因回归，不能把 reviewer 自评等同最终人工产品验收。

## 成熟参考

- https://docs.langchain.com/oss/python/langgraph/workflows-agents （orchestrator-worker / evaluator-optimizer）
- https://docs.langchain.com/oss/python/langgraph/use-subgraphs （子图隔离与父级持久化）
- https://docs.langchain.com/oss/python/langchain/tools （ToolNode）

## 代码候选验证

实际接入 `dell_workpaper_review_graph.py`（标准 Send/StateGraph evaluator-optimizer）、既有 Specialist graph/composition/DeepSeek adapter 的 review terminal 和 artifact handoff、既有 Agent Server 入口与一次启动 runner 的显式 review workflow。原单 Agent 五工具不变；reviewer 五工具仅以 SubmitReviewAction 替换 SubmitWorkpaperAction。没有新依赖或另一套 runner。源 seed 单文件只读挂载，逐 reviewer/repair 节点有独立 TokenBudgetBasis 和 SDK 会话；原 provider reasoning 仅续传本角色且保留在私有审计。

最终相关 11 文件测试：`215 passed in 16.28s`。包含真实 R11 原件不变/完整 observations 移交、实际 reviewer MCP catalog 返回、实际 SDK 模拟 transport 的 review 工具 schema、同角色 reasoning 续传/跨角色隔离、finding 精确目标/引用/anchor、并行 barrier、责任作者修订和二次复审，以及失败不得变 PASS。纯离线测试发现的 JSON tuple 序列化、LangGraph reducer 初始空列表、审查不应增加作者 revision 的边界均在付费前修正。Client 测试改为比较 Pydantic 显式默认值归一化，未更改 client 行为；legacy 单动作五选一 schema 保持。

2026-09-05 22:13 本地 Docker R11 三服务 healthy；磁盘 C/D/Z free=3.46/25.14/14.16 GiB。本包未删文件/改代理。当前未执行新模型；R11 的 runtime bounded PASS / 内容未 PASS 保持。此为 Q1 有界协作 qualification，不是昂贵完整 Q1–Q9 full-chain；后者仍须其专用全链 preflight/节点授权和产品门，不能用本包替代。

## A1 真实结果与按责任修订（2026-09-05）

A1=`20260905-dell-q1-agentic-review-repair-a1`，implementation `ac359ea9ff8622c40fd416e3e8f78fcfa73f53e9`、authority HEAD `1ba8a114f9e143c40df80fc6dece9d1abc3ba9f5`。run/root `01a071f7-b134-71f1-90cb-e15396284922`，server thread `5da962c1-5f7e-5bef-81fd-c712f040cc26`，port18163。唯一入口正常完成，无网络/代理问题、无 retry/resume/fallback。

- 工程增量真实成立：两个 reviewer 并行 → 原作者两轮修订（第一次被准确的原文匹配拒绝、第二次收下）→ 两个 fresh reviewer 复审；三种角色、五次独立 Agent invocation、六次真实模型调用。继承已读材料后本轮**新增数据工具动作=0**，不能宣称 reviewers 主动做了外源搜索；现有自主工具权与实际零模型 MCP 资格证明分开。
- 模型 input/output/total=`400636/98599/499235`tokens；累计模型1278.190391s（并行累计，不是墙钟），图命令871.859s，Docker构建159.234s。token/耗时是实测，本文未伪造实际账单。
- 第一轮抓到 C7 Q2订单/积压、C8 Q3指引和C9精确分部值的引用覆盖缺口。原作者第一份修订的 C7 原文引文正确，C8/C9却重排表格、用省略号拼接，原严格substring检查正确拒绝；旧反馈只给同一个PASSAGE ID且去重，未告诉模型是哪条claim失败。作者随后把对应断言移到正文逃避引用，仍英文。
- 复审真实发现比第一轮更深的问题：Counter 找到应付账款增加被写成吸收现金的方向错误；Counter/Verifier均发现将Q1毛利率下降泛化为整体趋势，遗漏Q2毛利率回升反证。未把Codex事先问题清单注入模型。模型 finding 是审计输入而非真理：仍需区分余额变化与现金流表桥接，不能凭余额差精确归因OCF。
- 终态 `review_cycle_needs_attention / material_findings_remain_after_one_revision`，正确 bounded_handoff，未假PASS。RC-S3-121仍open；本轮证明多Agent能指出语义问题和停止，并未完成其修复，更非完整Dell产品。

不可变源在 `Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/q1_specialist_paid_shadow/attempts/20260905-dell-q1-agentic-review-repair-a1/`：terminal receipt SHA `7745f1b374861a83394415dc40d022cbf49efc191b0e647a60ae7f46d14366ee`；state SHA `2c35ffc6bda74df19050df9a21812efa78a4135a463339f7d211225b8a50e5ce`。`workpaper.agent-original.md` / `reviews.agent-original.json` 为机械原文导出，未人工改写/翻译成模型成果。私有rawreasoning不在这些导出中。

### 有证据的小修补与下一次 A2

1. `citation_quotes` 兼容旧字符串，同时允许独立逐字引文列表；每段仍严格匹配原文。错误精确到claim ID/quote index；不接受拼接、伪引文，也不放松自然语言事实标准。
2. 明确正文仍保留的材料性断言不能通过移出claim来免除引用义务；修订需中文化整个工作底稿，而非只翻译review备注。语义继续由模型审查，不加NLP规则。
3. 现有同一个图允许**显式新授权attempt**读取已经停止的review artifact，校验最后两份review的目标/引用/原文anchor和author责任，直接将真实未解决finding交回作者，再fresh review；不重新跑旧review、不resume服务器/对话、不复制旧模型计数。每次仍最多一次责任修订；不存在后台无限重试。共享BoundBranchTask/ToolLaneResult的revision改为与Notebook同为0..100，预算仍由图/authority约束，避免第二次合法修订被旧Literal[0,1]拒绝；旧固定workflow不因此自动加轮。

修补后7个相关测试文件 `115 passed in 17.24s`，含A1原件精确复现（C7合法、只有C8/C9应报错）、独立引文列表正反例、stopped artifact→revision2且不重计旧调用、错误目标/anchor/责任拒绝、实际rev2 MCP catalog成功。本次不做全仓回归、不增加依赖/数据权限/框架。下一次A2只修并复审真实A1 findings，保留原失败。更广Lead/并行专业研究/完整Q1–Q9与前端仍在后续既定方向，不能以此小修补宣称已完成。

## A2 实测：中文责任修订成立，审查截断与剩余语义保留

A2 implementation `1539a85624b19f7f2e5ed32ed47f67aca1273b24`，authority HEAD `1e0412d58d017f052aa5d0afda351dfddee6df07`；run/root `01a0721e-1ac0-7c72-a62f-8f70e4e4229f`，thread `432b9e97-0730-53e8-93bd-2ca59966ffe7`，port18154。启动前发现生成JSON的integer/float标准化造成authority digest不匹配，在未启动/零调用时修正；不是模型或网络失败。

作者两轮完成中文revision2：应付现金方向与Q2毛利反证已改；15条claims，C12–C15新增PASSAGE逐行引文，其中C14显式承认余额差是作者简单算术且不是现金流精确归因。第一轮C12–C15引文失败后，第二轮按精确claim/quote反馈使用多个独立原文行成功，不再删掉这四条。新可读产物见A2目录 `workpaper.agent-original.md`，未人工翻译/改数。

Verifier**自主新增一次source search、两次模型轮**，定位Q1电话会候选，指出GAAP17.75%数值与非GAAP18.1%的AI mix归因口径不能混用；同时抓到正文订单/积压、Q3指引、精确分部值仍缺locator。其两项findings真实保留。Counter同次调用input62470/output24000，恰好达到配置上限，`provider_output_truncated`，无有效最终review；不得按另一个reviewer成功冒充两人都通过。A2整体failed，网络和Docker正常。

完整调用事实：5次已发送/收到usage（4success+1truncated），input/output/total=`373817/79838/453655`，累计模型979.620513s，图命令684.078s，构建243.485s。一次资源采样API527.7MiB/Postgres55.76MiB/Redis4.168MiB（不是峰值）。无retry/resume/fallback。

原runner在terminal校验失败之前未导出state，已用只读Agent Server状态补存原错误checkpoint；源文件SHA `ba87de43547e1f212eea217b62986f3ca74d4a4e53784e3a941b95f1e94b4762`，原failed receipt/audit不改。后续小修为先存state再判terminal，防止一个失败子Agent掩盖已完成的兄弟输出。既有导出器提供仅本机/error checkpoint的exclusive-create补存，不成为另一个runtime。

下一A3基于这份真实revision2与Verifier findings，直接责任作者修订后重新由**两个**fresh reviewer审查；不重做R11，不用Codex人工答案修正。读取部分失败制品只在有error checkpoint且有合法已完成review时允许，活跃未完成态不能启动继任；最终放行仍须两角色真实完成。Counter/reviewer容量按已消耗24k并截断的实测调至32k，其余既有任务/工具/权限/预算不变。此是明确根因的一次容量修正，不自动后台无限重跑。语义与正文覆盖尚有待修，RC-S3-121保持open；动态Lead/全产品仍未完成。

### A3 模型前错误与普通修复

A3=`20260905-dell-q1-agentic-review-repair-a3`，implementation96e5e469 / authority HEAD49258f67，port18158。三个服务healthy，但宿主driver在6.547s后模型前failed；provider=0、无Agent Server research run。只读容器重放 `_contracts_and_input` 显示 `canonical_v1_2_phantom_a03_forbidden:session_id`：旧regex把A03中的0写成可选，误杀当前合法新workflow的a3。此非代理、数据、DS额度或模型问题。

最小修复：保留历史A03（含Unicode/分隔符变体）限制，0不再可省略；普通作用域中的第三次attempt不等于不存在的历史A03。全部旧A02只读/身份保留/付费权限隔离仍适用，不靠ID命名获得授权。相关canonical/runner `51 passed in 4.39s`，加真实A3启动输入只读复证（0provider/0writes）。原A3失败不改、不resume。下一fresh A4沿用A3全部内容/容量/seed，实际完成尚未发生的修订与复审；不扩研究或工程范围。

## A4：第三版中文稿已保存，审查 JSON 容错缺口（2026-09-06）

A4 implementation `fc0a4b537c51532174ca86ea1abd6361bd93341b`，authority HEAD `e5270951d1827a021fe6ab0a179663c2c3bb73a1`，execution `20260905-dell-q1-agentic-review-repair-a4`。run/root `01a07249-6c78-7ad1-8d1d-64c8dac1601a`，thread `39beb7b5-152d-5625-b5ca-768dd6df22b2`，port18173。构建112.156s、图589.781s；三服务healthy，无网络/代理错误。

- 原作者1轮完成中文revision3，16claims，正文3055字符；已去掉未获引用支持的GAAP毛利率因果断言，并补订单/积压、Q3指引和精确分部值的PASSAGE及逐字引文。它是已通过结构/引用检查的工作稿，不是金融质量或产品PASS。原样导出 `workpaper.agent-original.md`。
- Verifier自主读1份原文；Counter自主同轮读2份原文，多工具批次确实执行。Counter第2轮提交完整但非法JSON（内部中文引号未转义），SDK `invalid_tool_calls` 已准确记录，finish_reason=tool_calls，不是输出截断。标准parser定位line1/column2998/character2997。
- FIN adapter却将可纠正参数错误当成fatal模型失败，LangGraph fail-fast取消并行Verifier。Verifier第二次provider响应有usage，但父图未收集其最终review，**0份已收集review**，不能冒充两个审查通过。runner失败为`review_cycle_terminal_missing`；全部失败/私有reasoning/第三版稿仍保存。
- 真实模型5次（4success+1structured_parse_failed），input/output/total=`401213/76166/477379`tokens，模型累计900.216106s；没有unknown outcome、retry/resume/fallback。新增数据动作3次，非旧观察重复计数。

### 小修与下一真实动作

沿用官方SDK `invalid_tool_calls` 与LangGraph ToolNode/ToolMessage：无效JSON只作为不可执行的关联记录，返回原call ID及准确parser位置，由同一模型纠正后完整补交；不使用json_repair、不改数字/观点、不接受部分JSON。SDK原始回复与reasoning保持原样续传。合法同批read不被丢掉；terminal混批、未知工具、重复/缺失ID、真实截断与引用权限检查仍有效。旧合法action模型序列化不变，不改历史Notebook digest。

现有review seed读取允许已error的fan-out在0份收集review时，仅继承已接受author artifact并从两人fresh review开始；不接受取消或非法JSON中的finding、不重写原件、不重做作者revision3。定向SDK/ToolNode/review三文件`68 passed in 14.39s`，相邻graph/composition/authority/runner四文件`49 passed in 7.76s`（前一命令误写runner测试文件名，0tests，已纠正）。含原A4完整非法参数的离线反例、精确错误回传、下一轮合法补交、跨角色reasoning隔离与无数据副作用。真实A4seed只读验证：revision3/16claims/9observations/0继承findings，SHA `fb89a53387338f9537be1aff0d25fd0afa895ac2c646306c4af236c47e9fc04f`。

下一A5仅对这份稿重新真实审查，必要时最多一次原作者修订和fresh复审；保持32k输出、500k输入chars、480s和现有工具/数据权限。已知JSON失败由正常Agent反馈循环处理，而不是后台重发旧请求。RC-S3-121仍open，动态Lead/全Q1–Q9/Workbench及完整产品仍未完成。本次不创建新框架/runner/依赖，不全仓回归，不删除Docker卷、缓存、数据或旧证据。

## A5：Q1 双 Agent 语义复核真实通过（2026-09-06）

implementation `1a4e2d796cd7fa8b08f7c4e5d4cff8af1c668ba4`，authority HEAD `de5099c281a6eb1abd11b60ab9284d0567c48059`；execution `20260906-dell-q1-agentic-review-repair-a5`。run/root `01a07272-f829-7dd3-93d4-c4c27b1c1f1a`，thread `50f9c5c8-cc48-5679-b5a0-3720864accab`，port18168。

- 真实 `review_cycle_accepted`：Counter 1 模型轮、Verifier 3 模型轮，均完成且 `no_material_finding`、findings=[]。直接审查 A4 已接受的中文 revision3/16 claims，无新作者重写，无人工改稿。Verifier 新读 1 原文，Counter 使用继承来源；不能称两人都新增搜索。
- Verifier 的第二次提交“无重大问题”与 finding 列表矛盾，被本地 `review_verdict_findings_mismatch` 拒绝；下一轮自行将非阻断观察移入 coverage_notes 后提交。原始模型回复/ToolMessage/私有 reasoning 保留。A4 非法 JSON 修复已有真实反例离线证明，但 A5 未再次产生非法 JSON，不能声称该分支已 live 触发。
- 仍保留两项非阻断意见：部分公司披露同比百分比可补更直接引注；电话会对非 GAAP 毛利率的 AI mix 解释可补入，不能与 GAAP 派生比率混为同一口径。不为这些整洁度问题再开 Q1 无限重写。
- 实际 4 模型调用，input/output/total=`342778/52828/395606` tokens；模型时长累计684.972930s，并行图墙钟390.312s，Docker build303.187s。不是账单费用或全部产品时延；无 retry/resume/fallback/unknown outcome。
- 原始产物在 `Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/q1_specialist_paid_shadow/attempts/20260906-dell-q1-agentic-review-repair-a5/`：`terminal-receipt.json`、`specialist-final-state.private.json`、原样可读 `workpaper.agent-original.md` / `reviews.agent-original.json`。state SHA `92a578a22d88baa8e9f1cf24ef6ac19369f09f0a76eb9fa3d0c90b970833e104`；底稿 digest `065ab5080e76cf447c041b0b76ac802ff4b4d72d8b5770e7c63cb12dd9481b96`。LangSmith 有该 root 的 runner 记录，本段未另做 SDK 全 span 读回复核。

RC-S3-121 获得 **Q1 有界关闭**，不是跨主题/全金融文本百分百正确性证明。下一主线转动态 Lead/跨主题研究；原 R11/A1/A2/A3/A4 仍为各自原结果，不重写成成功。Q1–Q9、最终报告、人工交互、部署产品验收仍未完成。

## 下一实际增量：任务与依赖底稿交接，不新造调度协议

复用既有 `ResearchTaskSpec`、Specialist agentic graph/composition/SDK，在真实 composition 接受语义任务、任务目标/验收要求/角色和已完成依赖底稿。模型首轮看到完整 task_context，后续 SDK 历史不重复注入；任务标识保留为依赖名，宿主 receipt/digest/私有 reasoning 不作为跨 Agent 思考传递。依赖只是未验证研究上下文，新 Agent 引用必须自行读原始来源。

FIN 仅验证任务覆盖、依赖身份、同 case/as-of/批准数据范围以及现有 capability；不授新权限，不继承观察/执行计数。目前一个任务对应一个既有 Q 覆盖项，符合现有 branch-scoped MCP compiler；不伪称多主题任意混合已打通。BoundBranchTask objective 上限对齐已存在 TaskSpec 的4000字符，不截断合法目标。实际 Lead 提案/动态 dispatch/收敛仍待下一步，不将 scripted driver 冒充自主规划。

真实 A5 底稿→Q5 supply/price 任务→既有 MCP catalog + S2 查询的零模型测试暴露一个老 S2 缺陷：`exact_period_end` 未带 start 时仍应用 open-period 最新财报 cohort，将6月披露的5月期末季度排除。最早错误在 `financial_facts/executor.py`，不是信息缺口/代理。只令 cohort 策略用于 `latest_on_or_before`；精确日期匹配、research_as_of、vintage/conflict、单位/身份校验不放松，旧 SQL 数据不写。两条确定性反例先失败后通过；真实 MCP 收到正确 S2 结果，原 A5 文件不变。

定向验证：S2/任务交接/composition/review/tool-batch 五文件89项，graph/SDK/deployment三文件71项，共 `160 passed`。一次误写 SDK 测试文件名导致0tests，已纠正重跑；没有全仓回归或额外 DS 调用。工程另采用 Docker 官方依赖层缓存顺序，固定依赖先于源码，依赖/镜像基线/安全配置不换；首次缓存建立真实成功，源码实际变更后的第二次构建也成功，third-party install与API restore两层均CACHED，FIN editable安装5.4s。registry metadata/resolve仍各约43s，不能称整体离线构建。镜像 `finsight-dell-runtime:task-handoff-20260906`，manifest-list SHA `5cdfe46e6ac275c8def6a5b92ef079226b2fe0ca7c9a2c3b89bf6cb239f1924e`。无网络/只读/cap-drop/no-new-privileges的临时容器内task handoff与S2导入通过；LangGraph1.2.11/Agent Server0.13.3/LangChain Core1.6.1/MCP2.1.1不变。临时容器自动移除，无用户数据挂载，所有旧服务/卷/镜像不删。参考 https://docs.docker.com/build/cache/optimize/ 。
