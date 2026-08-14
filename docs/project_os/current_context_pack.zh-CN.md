# FIN Insight 当前上下文包

更新时间：2026-08-14
当前产品版本：FIN 0.1.3
当前工作分支：`codex/fin013-s1-retrieval-vertical-slice`（S0 权威基线仍为远端 `main`）
G12 代码复证提交：`cd9990ac7ea4586cc55af0bc77f41c3f797399cb`

## 一句话状态

FIN 0.1.3 的严格仓库重定基已合并远端 `main` 并通过 G01–G12。S3 的 10>8 预算缺陷已由 provider-neutral proposal/execution 分层关闭，Planner R1 未重跑；保存的 10 atoms 稳定选择 8、延期 2。S1-D 已把 TSM 官方 PDF 两条 bounded read-through 和 Owner 上传的 Dell Q1 FY2027 官方托管 transcript 三条 issuer-direct Evidence 提升到当前 DELL Pack，当前为 20 Evidence／14 gaps；MU、NVDA 与留出案例不变。历史 DELL `value_capture` Chat／Responses paired exact-live 两路均通过传输但未过内容 L1。Research Context Closure v1 先由 formal zero-call R3 完成结构证明，再由 R4 绑定当前 16,000-token profile；DELL 为 19 Evidence／25 NumericFact／10 relation，MU 为 14／14／0，NVDA 为 13／15／0，三案污染为 0。唯一 Chat 自然复验 R1 的第一步正确读取 Evidence＋NumericFact，第二步含完整 relation／RoleMethodPack／GraphContextPack 的请求在约 175 秒后发生 `IncompleteRead`；0 retry，没有 Judgment。故当前 L1 与内容质量均未取得可评结果，五单元继续禁止。RC-S3-012 的 provider-neutral 工作树修复现已让普通 Chat／Tool Calls 共用同一 capture-first 终局：保留 HTTP metadata、partial 长度和原始 SHA-256，安全 JSON 经 reasoning redaction 后保存，malformed fragment 只留 digest／长度；任何 incomplete body 都禁止合同解析和业务晋升。全仓 280 tests 通过，但 formal clean replay 与 replacement authority 尚未签发，Provider 与本地代理谁导致 R1 断流仍不能归因。S1 产品门、完整八维研报、Workbench 报告面和 release 仍未通过。

## 当前唯一产品边界

- 产品入口：`/workspace`
- 运维入口：`/operations`
- 当前 API：`/api/v1/research-cases`、`/api/v1/research-cases/{case_id}`、`/api/v1/research-cases/{case_id}/evidence`、`/api/v1/research-cases/{case_id}/retrieval`、`POST /api/v1/research-cases/{case_id}/retrieval-requests`、`POST /api/v1/research-cases/{case_id}/controlled-research-plans`；Operations 另有 `/api/operations/source-intake/routes`、`/attempts`、`/uploads/{route_id}` 和 `/automatic/{route_id}`
- 当前案例：DELL、MU、NVDA
- 当前能力：展示经复核且与公司身份、研究截至日、case version、artifact digest 和 payload digest 绑定的 Evidence Pack；DELL 当前 Pack 已包含 SEC、Dell IR 官方托管法说和 TSM IR 官方托管法说，MU/NVDA 暂保留旧 Pack。另可展示 9 个 Evidence Slot / 17 个 facet 的当前候选，以及四条排名路线在同一对象上的只读对照。受控计划 API 已能把 Objective/atoms 同时送入 S1 联合候选与 private S2 mart；Operations 可按预登记官方 route 自动抓取或人工上传 PDF，并保证原始字节先进入私有不可变 source-only capture。当前 S3 consumer 已能在离线证明中消费 reviewed Evidence 与 NumericFact 并产出结构化底稿/报告预览，但尚未被自然模型或 Workbench 产品面验收；reviewed Evidence 页面本身的结构化数值项仍为 0。
- 当前不声称：动态 Agentic Research、开放式联网检索、完整投资报告、实时行情、自动事实晋升、交易建议或 release-ready 产品。
- 数据边界：reviewed Evidence 对象、普通数据构建根和可写 Operations state 已分离；容器可把 Evidence 只读挂载。无对象时 `/api/readiness=503`，挂载正确对象时为 200。

## 当前活动代码

- 后端组合根：`apps/workbench/backend/app.py`
- 领域应用层：`apps/workbench/backend/application/`
- 当前前端：`apps/workbench/frontend/vite/src/`
- 稳定运行时：`src/sec_agent/`、`src/connectors/`、`src/ingestion/`、`src/evidence/`、`src/indexing/`、`src/retrieval/`、`src/financial_facts/`；S2 已被 request-scoped backend 和当前 S3 consumer 消费，待自然模型与 UI 消费证明产品价值
- 受控数据构建：`scripts/data_sec/`、`scripts/data_retrieval/`、`scripts/market/`、`scripts/industry/`
- 活动图检查：`scripts/engineering/verify_active_baseline.py`
- 精确历史重定向：`archive/versions/FIN_0_1_3_REBASELINE_REDIRECT_INDEX.jsonl`

当前活动图新增 provider-neutral Research Objective／planner atom 编译、hybrid candidate Runtime、capture-first Agent transport、Source Intake、共用 official-PDF Evidence successor、registry-atomic current-Pack promotion和 `reviewed Evidence + NumericFact → judgment/workpaper/report` consumer。金融循环只消费一份 canonical Tool Contract；Chat Completions、Responses 与 Anthropic Messages 是可替换的外层投影。formal R3 已证明 consumer policy v1.2 的 provider-neutral RoleMethodPack／GraphContextPack 合同，但它们不注册为独立产品资源：前者只为 value_capture 提供方法，后者只从当前 Case／Evidence／NumericFact／typed relation 即时编译。Runtime Registry 仍为 R11／10 个资源；模型权重、人工标签、private mart、raw source capture、attempt 和 shadow 结果仍不注册。当前 route policy 声明 `typed_relationship_graph`，但 hybrid candidate Runtime 只执行 BM25＋Qwen，完整图查询 handler 仍未实现；S3 当前 GraphContextPack 不得被误称为关闭该 S1 缺口。

## 已完成的重定基事实

1. `main` 的有效语义已先合入候选分支，避免最后一次盲 merge。
2. Case 公司身份合同和 Case→Evidence Pack digest 绑定已经实现。
3. `/workspace` 已成为唯一研究产品入口；旧产品页面重定向，旧产品 API 返回 typed HTTP 410。
4. `/operations` 独立保留运行配置、来源包、受控数据构建、运行记录与基线检查，不承诺旧 Agent 产品能力。
5. S0 冻结时 Runtime Registry 只有三个活动资源；S1-A/S1-B 增加当前检索快照，S1-C 增加剥离 qrel identity 的排名安全投影，当前基线清单共六个活动资源。对象构建、embedding cache、角色复核标签和 live attempt 仍不进入产品 Runtime Registry。
6. 6,052 个旧实现/证明/尝试文件、被替换的规范快照、旧 HTML 原型、脱敏 fixture 以及已完成使命的一次性迁移程序，均已按推断版本非破坏性迁移到 `archive/versions/`；逐文件保留 source、archive、SHA256、原因和替代物。156 个过长路径已用可逆 path map 改为可移植短路径，两份冲突的旧 S0–S5 流水账也已归档。
7. S1-B 收口时 59 个 Python tests、TypeScript、Vite production build，以及桌面/移动 × 无数据/挂载数据共 12 个 Playwright tests 均通过；真实挂载数据曾自然暴露移动端长检索字段横向溢出，修复后两种模式均为 6/6。
8. 三案业务验收继续受其有界范围约束；本轮 secret scan 扫描 6,254 个文件为 0 finding。
9. Dockerfile、Compose、无数据容器 503、只读 Evidence 挂载容器 200 与 DELL `15 Evidence / 16 gaps` 均已真实 smoke。
10. G12 从两份独立 clean-main 工作树执行。第一份自然暴露归档换行摘要漂移、旧前端 fallback 和 Windows/Docker 保留端口问题；修复进入 `main` 后，第二份 clean-main 在无历史 `dist`、无 `node_modules` 的条件下完整通过。
11. 当前 S1-C 对象角色收口复证为 91 个 Python tests、Python compileall、active baseline 79 Python／7 frontend／6 Runtime resources 且 0 forbidden reference，以及 6,298 files secret scan 0 findings。Workbench 排名投影仍不含 gold target、命中结果、业务评测码、qrel 编号或本轮人工角色标签；本轮未改前端，因此未重跑历史 Playwright 产品面。
12. S1-C 对象级角色 successor 已建立 label-free `EvidenceObjectView`、独立 `EvidenceObjectAnnotation` 与 query-specific relation。DELL／MU／NVDA 24 object／35 relation 已由 Codex 做开发复核，ORCL／ASML／ANET 未参与；三案 Pack 另识别出 45 个仅有 source segment、尚无 claim/metric 精确训练表面的条目。
13. 固定本地 reranker 在对象级批次上 35 pair、0 网络、0 训练、0 生成调用；正负 pairwise=`0.50`、可比较 query top1=`0.60`、top3=`1.0`。旧规则角色 positive compatibility=`0.705882`、hard-negative suppression=`0.416667`、multi-label F1=`0.507936`。预注册门因此拒绝微调、独立角色训练、Runtime 晋升和 S1-D 自动执行。
14. S2 公司财务事实 mart 已从 DELL／MU／NVDA immutable CompanyFacts＋Submissions capture 零网络构建：1,319 observations、12 个直接指标、591 个保留的 superseded observations；最近财年 9/9、当前 interim 15/15、PIT／跨案／季度-YTD／派生公式／披露批次 mutation 全过。第一版自然暴露“最新 Q1 拼接旧 Q3 YTD”的业务错误，现已按同一 10-Q accession 锁定 disclosure cohort。该结果只授权 engineering route，不授权 Workbench 数值产品能力。
15. compiled object temporal projection 已统一区分 filing/current-report 日期与 issuer reporting period；20,340 个 v2 对象中 713 个时间元数据校正，只有 16 个模型文本需要重新编码，其余 20,324 个 Qwen 向量安全复用。
16. DELL 受控零调用纵切已完成：5 个 EvidenceRequest、80 个联合候选、7/7 typed fact resolved、21 NumericFacts、0 gap/conflict、0 网络和生成模型调用。数据库被证明为当前纵切的独立数值权威，但自然 planner、候选选择、研究综合和 UI 仍未通过。
17. S3 当前 consumer 零调用 R1 已完成：DELL 当前 20 条 reviewed Evidence 中 19 条进入五个研究单元，含 5 条已复核 transcript Evidence；45 个 request-level NumericFact 先合并为 35 个经济事实，再按最新季度／财年／时点选择 25 个模型可见事实；14 个 Pack gap 中 10 个与本轮单元相关。fake 输出成功编译结构化底稿/报告预览，未知引用、跨单元数值、自由数字叙事和缺单元 mutation 均 fail closed；0 网络、0 模型、0 provider、0 embedding，且 fake 结果未发布到产品面。
18. 绑定干净远端提交 `b4016469...` 的零调用 R2 已复现同一 research input digest `440987e2...968` 与同一 deliverable digest `d915a4a2...c0c0`；R2 result digest 为 `90574540...5974`。自然 canary runner 已通过 no-retry terminal、case binding 和 capture-first 测试，当前全量为 231 passed，活动图 111 Python／8 frontend／10 Runtime resources，0 forbidden reference。
19. 唯一 DELL DeepSeek Pro 综合 canary R1 已执行并 terminal failed：HTTP 成功、exact JSON、5/5 cells、usage=`14,141/2,643/16,784`，但首个硬失败为 envelope 缺字段。零调用完整诊断还发现 model-visible 枚举缺失、跨 cell 引用、复合 Evidence 二元角色冲突、自由数量级表述，以及 AI 归因、现金归因和供应缓解等内容越界。R1 0 retry、0 fallback、0 检索、0 发布；不能只补 envelope 后追认。
20. 历史角色 Skill 与图谱只读重新资格已完成：20 个旧 Skill 全部审阅，fundamental／industry／product／valuation／risk／lead／writer／verifier／shared boundary 的方法可选择性迁移，旧对象接口、重复版本和静态多 specialist 运行方式不恢复。旧 6 GraphPack／16 SkillPack／6 MemoryPack 结果只证明 registry/injection-plan 范围；旧物化数据、期间和 digest 不进入当前 Runtime。
21. 当前 Chat／Responses paid requests 的 model-visible prompt 和 captures 均没有 RoleMethodPack、specialist rubric、GraphPack 或 ProductIntelligenceGraph；因此协议资格仍成立，但内容失败不能只归因于 DeepSeek。官方 `deepseek-harness` 当前 scoped Skill、progressive disclosure、context log 和 preset 接缝只作为同一 FIN pack 合同的未来 shadow adapter，不整体导入开发预览 Runtime。

## G12 关闭的可复现性缺陷

1. archive digest 改为读取 Git index 中的 canonical blob；Windows checkout 的 CRLF 不再改变历史内容身份。
2. 后端只消费 `apps/workbench/frontend/dist/index.html`；未构建时返回 typed 503 `frontend_not_built`，不再退回旧源码 HTML。
3. Playwright 前端端口默认使用 4173，并允许通过经校验的 `FINSIGHT_E2E_FRONTEND_PORT` 覆盖；不再固定占用 Docker Desktop 常见排除区间内的 5173。
4. 前端冷启动以 `package-lock.json + npm ci` 为权威；本地 pnpm 只可作为 npm 启动载体，不得生成或提交第二份 lock/workspace。

## 尚未完成，不能提前宣称通过

1. 当前对象库已增加 PIT market role，private S2 公司财务事实 mart 已被 request-scoped Research Runtime 和零调用 S3 consumer 消费；DELL reviewed Pack 已扩展到 Dell/TSM 官方法说，但 Workbench Evidence 页面结构化数值项仍为 0，自然模型与前端尚未消费 NumericFact。对象候选不得伪装为 Evidence，报告也不得从 transcript 叙事重新发明精确数值权威。
2. Dell Q1 FY2027 transcript transport gap 已通过绑定 route 的人工官方 PDF 入库关闭；TSM 先进封装 source gap 也已关闭。仍保留 14 个 DELL residual gaps，包括提前采购幅度与消化、ASP/PVM 桥、供应商分配与容量释放时点、HBM 供给、利用率/良率和估值。Micron prepared remarks 与新鲜估值不在本次提升范围，不得因 DELL `core_research_ready` 一并视作 S1 完成。
3. successor 后同对象比较为 BM25=`17/18`、BGE-M3=`14/18`、RRF／旧规则=`16/18`。现成 Cross-Encoder 同为 `17/18` 且提高 MRR，但会把 DELL 直接风险目标从第 1 降到第 19，不能晋升默认路线。
4. 规则 Evidence Role 虽减少三案 top3 显式不兼容项，却把 Recall 降到 `13/18`；对象级复核仍只有 F1=`0.507936`。根因不仅是对象形态，还包括 reported results、guidance、counterevidence、监管和财务桥接被旧 qrel 混成一个 query，当前规则禁止上线。
5. 当前 provider-neutral planner compiler 已能把自然 Planner R1 的 atoms 变成 EvidenceRequest，并执行 S1 联合候选与 S2 typed fact sibling；当前 consumer 也已在 fake 证明中把 reviewed Evidence 与 NumericFact 变成结构化判断。尚未证明的是 DeepSeek 能否在同一合同下自然选择引用、形成经济机制、保留反方和 WWC，也未完成用户输入、动态追问或前端报告消费，因此仍不能称为完整 Agentic Research。
6. 当前 paid consumer 没有消费角色方法包或单元级图上下文；`typed_relationship_graph` 也只有 route 声明而无当前执行 handler。Skill／Graph 不能被旧归档材料假装补齐，也不能因缺失而把所有失败归因于模型。
7. Workbench 镜像仍安装数据构建依赖，冷缓存构建成本偏高；依赖拆分是非阻断基础设施优化，不能回滚已验证的数据/状态隔离。
8. Python 基础镜像与依赖目前可从 clean-main 构建并通过；更强的镜像/依赖字节级锁定属于后续基础设施加固，不得被误写为当前研究能力，也不阻断已通过的仓库基线。

## 决策与停止规则

- 不用增加新版本逃避当前失败；失败留在所属 gate 修复。
- 不再为单个历史 attempt 增加活动 runner、配置或测试。
- 不把 archive 中的 proof、fixture 或报告称为当前能力。
- 私有数据继续外置或挂载，不复制进 Git。
- 若业务验收发现当前三案例数据本身不可信，停止发布并在当前 FIN 0.1.3 修复；若只是未来动态研究能力缺失，记录为后续产品范围，不把它偷偷塞回本次重定基。
- 任何 materially changed scope 都要先向 Owner 说明。

## 当前下一步

`FIN_0_1_3_S2_S3_RESEARCH_CONTEXT_CLOSURE_V1`

Dell 人工入库、共用 PDF successor、有限 S2 回归和 current Pack 提升均已完成；Runtime Registry R11 与 Workbench 三案消费复验通过。当前基线已补上唯一 provider-neutral `Evidence Pack + NumericFact → research judgment / workpaper / report` consumer；归档中的旧 9-call/attempt runner没有复活。

旧综合 R1、GA paired R1 和标准 R1/R2 均保持不可变。唯一 Tool Contract Compiler、typed proposal repair 与三协议投影已通过正式零调用 replay；同一 DELL `value_capture` 的 Chat control／Responses candidate paired 也已 exact-once 完成。两路都能读取 Evidence／NumericFact、记录三个 open-gap 请求并提交 Judgment，但共同暴露 same-cadence numeric relation 无确定性 lineage，以及 model-visible source class 与实际 route 不一致。协议资格通过没有覆盖内容 L1，五单元继续 blocked。

Research Context Closure 的结构门和当前 profile 容量门已通过，但唯一 Chat R1 已以 `IncompleteRead` terminal failure 消费，不能自动重跑。Owner 已授权先修 partial capture、做零调用回放，再执行一次真实 replacement。当前工作树工程修复和 mutation 已通过；下一步必须先形成干净远端提交并签发 formal zero-call replay。只有 replay 绑定旧 R1、共享 transport 与隐私／不晋升边界后，才可另签发唯一一次新的 Chat Run／Attempt。第 7 步五单元、其他 RoleMethodPack、Responses 和完整图 handler仍不自动开始。

历史标准 Tool Calls successor 已在干净远端提交 `4daaa894...` 完成，并由 fresh zero-call R2 复证；R1 live 暴露的 wire `index` 与安全并行缺口由 v1.1 successor／fresh zero-call R3 关闭。真实 replacement R2 进一步证明 tool-result continuation 和两份 receipt 成立，同时暴露 Schema/Validator/route 非同源编译。R2 永久 failed。当前统一合同、协议投影和 Research Context Closure 均已达到 formal clean replay pass；Chat/Responses paired single-cell 的旧内容 L1 未通过。五 cell 现在只等待新 Chat 单单元复验后的 L1／内容质量与 scope decision。

仓库基线通过后回到 [FIN 0.1.3 当前 S0–S5 计划](../product/FIN_0_1_3_CURRENT_BASELINE_AND_S0_TO_S5_CLOSEOUT_PLAN_20260812.zh-CN.md)，不能把 baseline merge 写成 FIN 0.1.3 产品 release。
# 2026-08-12 S1-A/S1-B/S1-C 当前增量

- 当前分支已接入 provider-neutral 类型化本地检索纵切：9 个 Evidence Slot、17 个独立 facet、DELL/MU/NVDA 同核心 Case Profile，以及 `/workspace` 的“检索候选”消费者。
- 零改动基线尸检确认：旧活动链只有建 BM25 索引，没有查询→候选解释→Evidence Gate→Workbench 入口；中文 DELL 问题在旧 tokenizer 中几乎只剩 `dell`、`ai`。
- 当前工程结果不是 S1 产品通过：历史 SEC candidate store 的 reviewed target 对照命中 DELL=4、MU=0、NVDA=6，PIT 行情角色三案均缺。MU=0 的主因是 latest prepared remarks / supplemental objects 不在该历史候选库，而非模型失败。
- S1-B 当前对象库已收敛到 28 parent / 1,805 child；current-object missing=0，表边界与 child 容量门通过，NVDA 当前 10-Q 已接入。
- S1-B 原始 lexical 快照的 reviewed target 入池为 `6/3/4`，具体表现为现金槽错排、旧期压新期和关系共现污染；该数字只作为进入 S1-C 前的历史定位基线。
- S1-C successor、缓存复跑和请求级 Runtime 入口已完成；BM25=`17/18`、BGE-M3=`14/18`、RRF／旧规则=`16/18`。
- BGE reranker 历史 shadow=`17/18`、MRR=`0.608480`，有增益但逐题反转；对象级 successor 已进一步证明 fixed reranker pairwise=`0.50`、top1=`0.60`，规则 Evidence Role F1=`0.507936`。角色数据合同已经完成，当前下一项是 query-family decomposition 与 deterministic object-view compiler；不自动微调或进入 S1-D。
- 检索栈治理已进一步确认：当前只测试过 BGE-M3 dense，尚未测试 learned sparse／multi-vector 或 Qwen challenger；数据库旧路线 annual `9/9`、current-quarter `0/6` 只属于归档诊断。当前必须先实现 query/object＋typed fact route，再执行有界模型对照；公司财务事实 mart 的物化归 S2，但其路由合同不能从 S1 遗忘。
- 权威说明：`docs/architecture/retrieval/FIN_0_1_3_S1B_CURRENT_FINANCIAL_OBJECT_STORE_20260812.zh-CN.md`。
- S1-C 权威说明：`docs/architecture/retrieval/FIN_0_1_3_S1C_SAME_OBJECT_RANKING_COMPARISON_20260812.zh-CN.md`。
- S1-C 检索栈／数据库权威说明：`docs/architecture/retrieval/FIN_0_1_3_S1C_RETRIEVAL_STACK_AND_DATABASE_LANE_DECISION_20260812.zh-CN.md`。
- S2 公司财务事实 mart 权威说明：`docs/architecture/financial_facts/FIN_0_1_3_S2_COMPANY_FINANCIAL_FACT_MART_20260813.zh-CN.md`。
