# P38 VT4 P36 Candidate Dogfood and Release Decision Preparation

日期：2026-07-18

## 1. 目标与范围

本轮把 VT1-VT3 的 three-cell walking slice 扩为 P36 ten-cell internal fixture candidate，并完成 Point 07 在不触发 RG1、模型、网络和发布授权前可执行的产品验证：

`candidate profile -> browser dogfood -> structural regressions -> observed product metrics -> rollback/release blocker ledger`

这不是 FIN 0.1 发布。P36 研究有效性、SaaS/Bank 行业研究有效性、人工效率提升、operational qualification 和 production readiness 均未宣称完成。

## 2. 产品能力增量

当前浏览器主链支持十个研究角色：

1. demand signal；
2. revenue capture；
3. thesis counterevidence；
4. server OEM orders；
5. server OEM margin/cash；
6. advanced packaging capacity；
7. HBM supply/pricing；
8. semicap capex cycle；
9. export policy risk；
10. customer concentration。

修复后 Case `case_80fb19038ebf44f5ef7ad5b5` 从创建、10-cell DecisionSurface、WorkUnit、Evidence、一次 bounded repair、Numeric、10-judgment Workpaper、LeadReview、10-claim Deliverable、review 到双向 Trace 全部在真实浏览器中完成。Lead 和 deliverable reviewer 均只接受 internal fixture preview，不接受行业结论或 release claim。

演示地址：`http://127.0.0.1:5173/cases/case_80fb19038ebf44f5ef7ad5b5/deliverable`。

## 3. Dogfood 发现与修复

第一轮 Case `case_5bf56ab01c61bcec73bcbec7` 暴露两个当前路径产品问题：

1. Evidence/Workpaper UI 仍写死 three-cell 文案；
2. candidate profile 的 `remaining_gaps` 是字符串，backend 将其按字符迭代，Deliverable 形成单字符 gap refs。

修复后 profile 将每个 gap 约束为 `list[str]`，contract/full vertical tests 断言每个 judgment/claim 只有完整可读 gap；前端标签改为动态 cell/judgment count。旧 Case 保留为缺陷证据，没有删除或重写。

## 4. 当前证据

- candidate profile canonical digest：`405ca48e251d04fac16c54e2afdc1133ff2fa24a35ba161cc181db1da943df17`；
- DecisionSurface：10 cells，checkpoint accepted；
- Evidence：10 slots、10 candidates、2 context-only、6 typed gaps、1 repair requested/completed；
- Numeric：1 fixture fact；
- Workpaper：10 judgments、10 explicit gaps；
- Deliverable：10 material claims、10 explicit gaps；
- Trace：34 nodes、48 bidirectional edges；
- observed case-to-workpaper：`82.830488s`；
- observed case-to-reviewed-deliverable：`167.553023s`；
- review decisions：4；
- network/model/provider/tool/paid/commercial-data/business-write/release counts：0。

P07.2 SaaS/US Banks sidecar 只验证结构角色、typed gaps 和无 P36 facts/numbers/rankings/source/ticker/issuer carryover，不验证两个行业的研究结论。

## 5. 产品评估边界

本轮只有单个内部 fixture dogfood，没有定义人工 baseline 或 cohort，因此不能写“节省时间”。首次缺陷导致一次完整重跑，已作为 repeated-work 观测记录。Desktop `1280x720` 与 mobile `390x844` 无页面级横向溢出；移动导航是容器内横向滚动。未运行正式性能 profile、screen reader 或自动 accessibility score。

机器证据：

- `reports/release_evidence/fin_ia_0_1_vt4_p36_internal_dogfood_result_v1_0.json`
- `reports/release_evidence/fin_ia_0_1_vt4_structural_regressions_v1_0.json`
- `reports/release_evidence/fin_ia_0_1_vt4_product_evaluation_v1_0.json`
- `reports/release_evidence/fin_ia_0_1_vt4_rollback_drill_v1_0.json`
- `reports/release_evidence/fin_ia_0_1_vt4_candidate_manifest_v1_0.json`
- `reports/release_evidence/fin_ia_0_1_vt4_p07_5_release_decision_v1_0.json`
- `configs/releases/fin_ia_0_1_vt4_rollback_release_note_v1_0.json`

## 6. 当前成熟度与下一步

- P07.1 fixture/full：通过；calibrated senior R2：pending；
- P07.2 deterministic structural-only：通过；calibrated sector-structure review：pending；
- P07.3 observed metrics：通过；human product-value baseline：pending；
- P07.4 bounded rollback：通过；新 lane 读写 fail-closed、legacy shell 可用、canonical audit bytes 保留；
- P07.5：blocked，不得写 `FIN_0_1_INTERNAL_ALPHA_RELEASED`。

P07.5 的当前决定是 `FIN_0_1_INTERNAL_ALPHA_BLOCKED`。发布仍有三类硬阻断：RG1 exact package identity + separately authorized bounded operational run；RG3 calibrated senior R2；RG4 human product-value baseline。RG2 internal fixture integrity 与 RG5 bounded rollback 已通过。`production_readiness=not_admitted`，legacy global authority retained。

## 7. RG4 可用性反馈修复：投研信息架构与中文阅读

用户实际浏览暴露两个直接影响试用的问题：第一，原界面以 Case ID、Activity、状态和审阅动作组织，视觉和信息架构更接近后台/OA 审批台；第二，界面及 P36 演示正文主要为英文，中文用户阅读成本高。两项问题均属于当前内部演示主路径的产品可用性阻断，而不是 production hardening。

本轮在不修改 canonical artifact、digest、权限、命令和存储语义的前提下完成：

1. 将导航重组为“研究框架 / 分析工作 / 结论与追溯”，以研究问题、证据台账、数字核验、研究底稿和研究结论为主对象；
2. Task Center 改为研究任务列表，研究问题为主标题，Case ID 和版本降为次级身份；
3. 新增共享 locale 合同，默认 `zh-CN`，支持页面内切换英文并持久化用户选择；
4. P36 canonical English fixture 增加只读中文阅读层，明确不改变原始 artifact 或校验摘要；
5. 失效 Case 不再泄漏原始 `case_not_found`/trace 文案，改为可返回研究任务的中文恢复状态；
6. backend/API projection 补充现有 Case query/language 的只读投影，不新增状态源。

验证结果：TypeScript strict 通过；Vite production build 通过（1689 modules）；当前前端/纵向合同回归 `35 passed`；真实 Chrome 在 desktop `1440x1000` 和 mobile `390x844` 下无页面级横向溢出；中文默认和英文切换通过。浏览器控制台中的四个 `404` 全部来自刻意打开历史失效 Case，且页面已正确转为恢复状态。

这次修复只关闭“后台化信息架构”和“缺少中文阅读能力”两个 RG4 试用阻断。候选来源原始标题、技术身份和 digest 仍保留原文或 token 以维持审计语义；RG4 human product-value baseline 仍需用户实际完成一轮研究任务后评估，因此 P07.5 继续保持 `FIN_0_1_INTERNAL_ALPHA_BLOCKED`。

## 8. 受限真实研究链与一次 bounded senior R2

在三栏 Analyst Workbench 稳定后，当前纵向不再继续扩展控制面，而是接入仓库已有的真实本地研究资产：3,035,688 条结构化对象索引、74,894 条 Gold Fact/Signal Mart 和 100,145 条 Research Graph edge。第一步先验证 demand reality、value/profit capture、bottleneck/counterevidence 三个最高价值单元；随后按既有 P36 gate 的六类必需范围一次扩展到 10 个研究角色。最终只读预览为 10 cells、31 candidates、10 repair decisions、10 judgments、10-section Workpaper/Writer；preview digest=`aa792b86fa5aed152ba38352eec54b08b8ad5a3603a553c57a66260eb389b093`，analysis digest=`9d47aa3b29db35839dd6aea10974747777dbf72177e7e54db5c4c9fb4311ee50`。

真实数值链从 FY2025 精确公司事实计算收入 `130497000000 USD`、毛利润 `97858000000 USD`、营业利润 `81453000000 USD`，派生毛利率 `74.99%`、营业利润率 `62.42%`。Workpaper 保留每个判断的候选、numeric、repair 和 remaining-gap lineage；no-source Writer 只消费判断文本，`writer_source_access_calls=0`。整条链 network/model/provider/Case mutation/canonical write/evidence promotion/release admission 均为 0。

一次独立 shadow senior R2 已完成，但没有冒充 human calibrated acceptance。覆盖、数字可复算、显式 gap 和 no-source boundary 通过；RG3 仍被 exact human LeadReview 阻断，并冻结三个 bounded 弱项：advanced packaging 仍是一般供给/产能依赖而非 CoWoS 证明，semicap 候选主要是 FY2023-FY2024，company-level profit 尚不能归因至 accelerator segment/全链。follow-up 预算只有一次，只允许 exact human review 以及最多两个 current-period source substitution；不得新增 gate/package family 或 broad source expansion。

机器证据：

- `reports/release_evidence/fin_ia_0_1_p36_real_candidate_shadow_senior_r2_v1_0.json`
- `reports/release_evidence/fin_ia_0_1_p36_human_task_baseline_protocol_v1_0.json`
- `tests/contract/test_p36_local_research_preview_api.py`
- `tests/contract/test_p36_real_candidate_review_evidence.py`

RG4 human baseline 已冻结为 4 步真实用户任务，但当前状态仍是 `ready_not_started`。在用户完成 Evidence -> Numbers -> Workpaper -> Deliverable 并给出 exact-digest review 前，不申请 RG1、不改变 P07.5 blocked decision。

## 9. 可持续产品前端与 Exact Human Baseline Capture

为支持未来发布和长期本地调试，Workbench 不再依赖一次性的手工启动或离线概念图。当前产品前端落为同一套 React/Vite 页面和 FastAPI 合同，支持两种运行模式：Dev 模式由 `127.0.0.1:5173` 提供热更新并代理 `8765` API；Built 模式由 `8765` 直接托管生产构建。`scripts/workbench/start_internal_alpha.ps1` 负责验证 fixture、启动服务、记录 PID/日志并等待健康检查；`stop_internal_alpha.ps1` 只终止命令行精确属于本仓库的受管进程，保留日志与人工评测记录。

产品界面当前包括：

1. 任务中心：队列和所选研究摘要并列，只对所选 Case 读取真实本地链，展示真实 cells、candidate、fact、judgment、gap 和 digest；
2. Analyst Workbench：任务队列、Case 内研究标签和证据/复核上下文保持三栏，可在概览、研究问题、证据、数字、底稿、结论、记录和基线评测间切换；
3. Evidence：P36 十单元真实本地候选和既有 Evidence Ledger 同屏，研究问题为主标题、Case ID 降为审计身份；
4. Human Baseline：四个可计时任务、浏览器草稿恢复、分析师提交、Senior Review、exact digest attestation 和 JSON 导出。

人工评测记录写入独立的 `.codex_runtime/internal-alpha/human-baseline.sqlite3`，不会修改 canonical Case、Evidence 或发布权威。每个 session 冻结 Case/version、research preview、analysis、Workpaper、Writer 和总 binding digest；产物漂移时拒绝后续提交；事件只允许按 `baseline_started -> analyst_baseline_submitted -> exact_human_senior_review_recorded` 追加。当前目标 Case session 数仍为 `0`，因此状态更新为 `product_ui_ready_not_started`，不能写成 exact human review、RG3/RG4 或 release pass。

验证：Human Baseline/API/前端/真实本地链定向回归 `12 passed`；TypeScript strict 和 Vite production build 通过（1693 modules）；Chrome desktop `1600x1000` 与 mobile `390x844` 的任务中心和基线页均无横向溢出、无 console/page error。Built 和 Dev 两种启动/停止流程均完成真实切换。network/model/provider/paid/commercial-data/real business Case mutation/release admission 均为 0。

## 10. Case 主工作台从计划列表切换为真实研究指挥台

用户复查发现 Case Overview 仍以十张 DecisionSurface 问题卡纵向平铺，虽然真实本地研究链和三栏 shell 已存在，主路径却没有消费这些产物，因此视觉和使用方式仍像后端/OA 页面。本轮修复最早投影缺口，而非继续增加 gate 或控制面：

1. Case Overview 优先读取 `local-research-preview` 与 `local-analysis-preview`，只有真实链不可用时才回退到原研究计划编译页；
2. 首屏展示当前候选判断、收入、毛利率、营业利润率、31 条候选证据、3 个精确事实和 10 个待复核判断边界；
3. 默认展示六个优先研究单元，可展开查看决策问题、当前判断、反证、两条优先候选证据和 remaining gap，并可切换全部十单元；
4. 右侧上下文改为同一真实链的候选证据、精确事实、判断边界和 Senior R2 状态；
5. 补齐七个扩展研究问题和十个 remaining-gap 的中文只读映射，原始来源标题/摘录保留英文；
6. `<=1480px` 时右侧上下文下沉，避免挤压中央工作台；移动端指标保持两列。

验证：TypeScript strict 与 Vite production build 通过（1693 modules）；当前相关合同回归 `20 passed`。另一次包含历史 Point 02 源码字符串断言的宽回归为 `24 passed / 2 failed`，两项失败分别要求 `AppShell` 直接持有 Case API 和 TaskCenter 保留旧过滤器源码，不属于本轮运行缺陷，未为通过旧断言倒退架构。真实 Chrome 验收覆盖 `1920x1080`、`1280x800`、`390x844`：展开/折叠、六到十单元切换、右侧复核 tab 均通过，无 console/page error、无页面横向溢出；1280 主工作台宽度由 536px 提升到 868px，移动首屏 summary 高度降至 535px。

本轮未开始 Human Baseline，session 仍为 0；未发生 network/model/provider/paid/commercial data/真实业务 Case mutation/evidence promotion/release admission。RG3/RG4 与 P07.5 状态不变。

## 11. 概念图到产品视觉基线的纠偏

用户将早期批准的蓝色任务中心概念图与当前绿色 Case 工作台截图直接对照，确认两者不仅是不同路由，而是实现没有把概念图的视觉系统和任务台账密度作为验收条件。此前迭代沿用 P02 绿色 shell 做局部增量，虽然真实研究数据已经进入页面，但全局导航、颜色、任务列和右侧摘要仍保留旧骨架，形成“功能增加、产品形态不收敛”的视觉漂移。

本轮不增加治理或后端状态，直接修复最早前端投影：

1. 共享顶栏改为蓝色 FinSight 标识、全局搜索、`INTERNAL ALPHA`、中英文、数据源状态和用户身份；
2. 左侧导航恢复分析师工作区、工作底稿、证据、复核、交付物和研究资产层级；未进入 FIN 0.1 的公司/主题与指标库置灰并注明后续版本；
3. `/tasks` 从大卡片列表改为列式任务台账，包含研究问题、优先级、阶段、cell 进度、候选证据、开放缺口和下一步；只有当前选中任务读取真实本地链，未加载任务显示 `准备中/—`，不伪造指标；
4. 右侧研究概览消费真实首要判断、`10/10 cells`、`31 candidates`、`3 exact facts`、`10 remaining-gap boundaries`、六个活跃研究单元、证据质量和关键动作；
5. Case 指挥台继承同一蓝色导航和交互强调，成功状态仍使用绿色、缺口仍使用橙/红，避免单色化；
6. 空的待复核/阻断/完成视图保留 tabs 和返回动作，避免 0 结果时整个任务台账卸载。

浏览器复核同时暴露一个集成问题：Case Overview 与右侧 Context Drawer 会同时读取同一 research/analysis preview，主页面还把显示真实链绑定在 DecisionSurface 请求之后。在本地数据链较重时，这会让页面超过 90 秒仍停留在 loading。修复后 `EvidenceApiClient` 仅合并同 Case/tenant/project/actor 的 in-flight 只读请求，settle 后立即释放，不形成持久缓存；`CaseOverview` 让 local chain 和 planning 各自完成、各自渲染。修复后 `1600x1000` Chrome 中 Case 指挥台约 `15.6s` 可见。

验证：TypeScript strict 通过；Vite production build 通过（1693 modules）；相关前端、Point 02/03、VT4、local research 和 Human Baseline 合同/API 回归 `22 passed`。Chrome `1600x1000` 任务中心、Case 指挥台和 `390x844` 移动任务中心无横向溢出、无 console/page error；Case 标题按钮尺寸为 `132x36` 与 `116x36`，没有文字换行或裁切。截图保存在 `.codex_runtime/ui-qa/task-center-blue-final-1600.png`、`case-command-blue-final-1600.png` 和 `task-center-blue-final-mobile.png`。

该切片只关闭视觉基线漂移、0 结果导航缺陷和本地只读请求重复问题。Human Baseline session 仍为 0；exact human Senior R2、RG3、RG4、RG1、FIN 0.1 release admission 和 production readiness 均未通过。

## 12. 底稿与结论从摘要骨架恢复为可审阅研究文档

用户在实际浏览中发现，`底稿` 和 `结论` 虽然各自有十个 section，但每个 section 只有一句判断，无法完成 Senior Review。根因不在上游数据缺失：当前只读研究链已有 10 个研究单元、31 条候选证据、3 个精确事实、10 条判断、反证、repair decision 和 remaining gap；缺口出现在组合与前端投影层。backend 的 Workpaper section 只保存引用 ID，Writer 又只复制 judgment 文本，旧前端因此把已有研究上下文压缩成一段摘要。

本轮保持 canonical artifact、Writer no-source authority 和所有 digest 不变，只在浏览器只读层联结既有 `local-research-preview` 与 `local-analysis-preview`：

1. 底稿按十个研究单元展开研究问题、当前判断、全部引用候选、来源日期/类型/摘录、claim boundary、精确数字 lineage、反证、what-would-change、repair decision 和 remaining gap；
2. 结论增加执行摘要、需求/利润/反证三段主判断、精确数字与公式，以及十个展开章节；每章保留原 Writer 文本，同时把证据依据、结论边界和待核验项明确标为 reviewer-only context；
3. 页面继续显示 `source_access_calls:0`，没有让 Writer 读取来源，也没有进行 Case write、Evidence promotion、模型调用或发布准入；
4. desktop `1600px` 和 mobile `390px` 均无横向溢出；底稿有 10 个 section / 31 条 evidence row，结论有 10 个 section / 10 组 reviewer evidence note。

验证：TypeScript strict 通过；Vite production build 通过（1693 modules，只有非阻断的 chunk-size warning）；定向合同/API 回归 `10 passed`；Chrome desktop/mobile 无 console/page error。截图保存在 `.codex_runtime/ui-qa/workpaper-rich-viewport-1600.png`、`deliverable-rich-viewport-1600.png`、`workpaper-rich-mobile.png` 和 `deliverable-rich-mobile.png`。

该切片把已有研究链恢复为人可以审阅的文档，不等于研究质量已获接受。Human Baseline 仍未开始，exact human Senior R2、RG3、RG4、RG1、P07.5 release decision 和 production readiness 均保持未通过。
