# FIN Insight 当前上下文包

更新时间：2026-08-13
当前产品版本：FIN 0.1.3
当前工作分支：`codex/fin013-s1-retrieval-vertical-slice`（S0 权威基线仍为远端 `main`）
G12 代码复证提交：`cd9990ac7ea4586cc55af0bc77f41c3f797399cb`

## 一句话状态

FIN 0.1.3 的严格仓库重定基已合并远端 `main` 并通过 G01–G12。S1-A 已接入类型化查询与 Workbench 候选页，S1-B 已建立 28 parent / 1,805 child 的当前金融对象库。S1-C 已把 17 个 facet 拆成 11 类问题，把混合请求拆为叙事检索／数据库事实 sibling，并把全库编译为 20,340 个去重 claim／metric-row／context 候选。18 个 Runtime Query Atom 的同对象模型 shadow 已完成：Qwen Embedding 为 provisional first-stage winner（8/15 前十），BM25 为 lexical fallback（5/15），Qwen Reranker 只保留 shadow，Evidence Role F1=0.5818，故 S1 产品门仍未通过、禁止微调。数据库硬门没有后移：S2 已从三案 source-bound SEC capture 建成 1,319 条 observation 的 PIT 公司财务事实 mart，并已接入当前 request-scoped Research Runtime。真实 DELL 请求把 2 条叙事检索与 6 条 typed fact sibling 同时执行，数据库 6/6 resolved、0 gap、0 conflict；当前状态是 S2 Runtime integration engineering pass，下一硬门是 S3 真实 Research Objective／EvidenceRequest 与 S1 `Qwen + BM25` 联合候选共同完成 DELL S1/S2/S3 纵切。

## 当前唯一产品边界

- 产品入口：`/workspace`
- 运维入口：`/operations`
- 当前 API：`/api/v1/research-cases`、`/api/v1/research-cases/{case_id}`、`/api/v1/research-cases/{case_id}/evidence`、`/api/v1/research-cases/{case_id}/retrieval`、`POST /api/v1/research-cases/{case_id}/retrieval-requests`
- 当前案例：DELL、MU、NVDA
- 当前能力：展示经复核且与公司身份、研究截至日、case version、artifact digest 和 payload digest 绑定的 Evidence Pack；另可展示 9 个 Evidence Slot / 17 个 facet 的当前候选，以及四条排名路线在同一对象上的只读对照。request-scoped API 已能从 private S2 mart 执行 source-bound NumericFact 查询；当前 reviewed Pack 尚未复编译，前端也尚未消费这些事实，因此 reviewed 产品表面的结构化数值项仍为 0。
- 当前不声称：动态 Agentic Research、开放式联网检索、完整投资报告、实时行情、自动事实晋升、交易建议或 release-ready 产品。
- 数据边界：reviewed Evidence 对象、普通数据构建根和可写 Operations state 已分离；容器可把 Evidence 只读挂载。无对象时 `/api/readiness=503`，挂载正确对象时为 200。

## 当前活动代码

- 后端组合根：`apps/workbench/backend/app.py`
- 领域应用层：`apps/workbench/backend/application/`
- 当前前端：`apps/workbench/frontend/vite/src/`
- 稳定运行时：`src/sec_agent/`、`src/connectors/`、`src/ingestion/`、`src/evidence/`、`src/indexing/`、`src/retrieval/`、`src/financial_facts/`；S2 已被 request-scoped backend 消费，待 S3 与 UI 消费证明产品价值
- 受控数据构建：`scripts/data_sec/`、`scripts/data_retrieval/`、`scripts/market/`、`scripts/industry/`
- 活动图检查：`scripts/engineering/verify_active_baseline.py`
- 精确历史重定向：`archive/versions/FIN_0_1_3_REBASELINE_REDIRECT_INDEX.jsonl`

当前活动 import graph 为 94 个 Python 文件和 7 个前端文件；provider-neutral route/object compiler、共享 embedding/reranker adapter 与 S2 financial-facts 实现均已进入活动图。Runtime Registry 为 R6／7 个资源；R6 只更新了带显式 reporting-period binding 的当前候选快照，模型、人工标签、private mart 和 shadow 结果仍未注册为产品 Runtime resource。private mart 通过显式 Runtime path 挂载，而不是复制进 Git。活动基线现在从 Workbench data-build catalog 自动纳入所有动态启动脚本，Query Atom 与 S2 mart 构建入口不再因没有静态 import 而漏审。历史文件没有删除；完整旧 Project OS 账本也保存在 `archive/versions/fin_0_1_3_prebaseline/docs/project_os/`。

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

## G12 关闭的可复现性缺陷

1. archive digest 改为读取 Git index 中的 canonical blob；Windows checkout 的 CRLF 不再改变历史内容身份。
2. 后端只消费 `apps/workbench/frontend/dist/index.html`；未构建时返回 typed 503 `frontend_not_built`，不再退回旧源码 HTML。
3. Playwright 前端端口默认使用 4173，并允许通过经校验的 `FINSIGHT_E2E_FRONTEND_PORT` 覆盖；不再固定占用 Docker Desktop 常见排除区间内的 5173。
4. 前端冷启动以 `package-lock.json + npm ci` 为权威；本地 pnpm 只可作为 npm 启动载体，不得生成或提交第二份 lock/workspace。

## 尚未完成，不能提前宣称通过

1. 当前对象库已增加 PIT market role，private S2 公司财务事实 mart 也已被 request-scoped Research Runtime 消费；但 reviewed Evidence Pack 仍只覆盖 SEC 且结构化数值项为 0，S3 和前端尚未消费这些 NumericFact。对象候选不得伪装为已晋升 Evidence，数据库 Runtime integration engineering pass 也不得冒充研究产品通过。
2. Dell Q1 FY2027 transcript、Micron Q3 FY2026 prepared remarks 的官方文件已确认存在，但当前产品 transport 的有界 R1–R4 未取得原始 PDF；TSM 先进封装和新鲜估值也仍是 S1-D typed gap。
3. successor 后同对象比较为 BM25=`17/18`、BGE-M3=`14/18`、RRF／旧规则=`16/18`。现成 Cross-Encoder 同为 `17/18` 且提高 MRR，但会把 DELL 直接风险目标从第 1 降到第 19，不能晋升默认路线。
4. 规则 Evidence Role 虽减少三案 top3 显式不兼容项，却把 Recall 降到 `13/18`；对象级复核仍只有 F1=`0.507936`。根因不仅是对象形态，还包括 reported results、guidance、counterevidence、监管和财务桥接被旧 qrel 混成一个 query，当前规则禁止上线。
5. 当前 query compiler 已消费类型化 `EvidenceRequest`，按需选择 facet，并拆成 narrative／typed fact sibling；S2 mart 与 executor 已在真实 DELL request-scoped 请求中连接，但该请求仍由工程侧提供受控 facet 和 metric ID。自然语言问题到 Research Objective／EvidenceRequest、S1 联合候选选择以及 S3 对 NumericFact 的研究消费尚未进入 Runtime，仍不能称为真实用户查询理解或完整产品数值能力。
6. Workbench 镜像仍安装数据构建依赖，冷缓存构建成本偏高；依赖拆分是非阻断基础设施优化，不能回滚已验证的数据/状态隔离。
7. Python 基础镜像与依赖目前可从 clean-main 构建并通过；更强的镜像/依赖字节级锁定属于后续基础设施加固，不得被误写为当前研究能力，也不阻断已通过的仓库基线。

## 决策与停止规则

- 不用增加新版本逃避当前失败；失败留在所属 gate 修复。
- 不再为单个历史 attempt 增加活动 runner、配置或测试。
- 不把 archive 中的 proof、fixture 或报告称为当前能力。
- 私有数据继续外置或挂载，不复制进 Git。
- 若业务验收发现当前三案例数据本身不可信，停止发布并在当前 FIN 0.1.3 修复；若只是未来动态研究能力缺失，记录为后续产品范围，不把它偷偷塞回本次重定基。
- 任何 materially changed scope 都要先向 Owner 说明。

## 当前下一步

`FIN_0_1_3_DELL_S1_S2_S3_VERTICAL_SLICE`

S1-C Runtime Query Atom R1/R2 已完成，原始失败和诊断池结果均保留。当前路线冻结为 `Qwen3 Embedding provisional + BM25 lexical union`，Qwen Reranker 仅 shadow，Evidence Role 不通过，微调不授权；当前产品 endpoint 仍消费 immutable snapshot，联合候选尚未晋升。S2 数据库硬门已达到 Runtime integration engineering pass：typed exact lookup 可以从 1,319 条 source-bound observation 返回 NumericFact、typed conflict 或 typed gap，并保留 PIT、期间、单位、accession、accepted-at、vintage 和公式 lineage；真实 DELL request-scoped 请求为 6/6 resolved。下一项必须由 DELL 真实纵切连接 S3 Research Objective／EvidenceRequest、S1 联合 narrative 候选、S2 executor 与 S3 综合；不能因为离线 24/24 或 API 6/6 就关闭 S2，也不能用 S1 的残缺 qrel、Evidence Role 或 TSMC gap 重新拖回数据库实现。

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
