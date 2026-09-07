# FIN 0.1.3 产品能力全面审计：Build / Adopt / Hold / Retire

日期：2026-08-30
状态：STEP 3 RECONCILED / MODULE MIGRATION BASELINE FROZEN / QUALIFICATION-ONLY / NO PRODUCTION ADOPTION
原审计基线：codex/fin013-dell-s1-s2-product-bridge @ 9f2b62834fa1bedcf48f353466f40f3ae75d4c43
Reconciliation 基线：codex/fin013-dell-s1-s2-product-bridge @ 088ab1bbcebb43057be6c328ccd73de32994b309
Qualification summary：`Z:\FIN_Insight_Agent_qualification\20260831_control_plane_slice_v1\manifests\qualification-summary.json`，SHA-256=`c6750a23b729b80b769cb6c850a7320cded818ca9d50443f680d5c6afbea8150`
R14 implementation freeze：7e25cad95ee84b39fb2a51063100405bc27da6e5

## 1. 先给不拐弯的结论

用户对项目“把 RAG 做成了 NLP，又不断自造通用轮子”的担心有事实依据。

市场上已经有成熟的官方数据接口、网页抓取、PDF/OCR、XBRL、混合检索、向量索引、reranker、LLM 结构化抽取、Agent checkpoint/HITL、模型 SDK、trace、eval、实验管理、对象存储、企业身份与报告渲染。FIN 没有必要长期自己维护这些通用基础设施。

但项目也不是“所有东西都应该买来”。FIN 真正需要自己拥有的，是一套通用 RAG 平台不会替我们负责的金融研究权威：

- 研究对象、公司身份、as-of、报告期、版本与 lineage；
- 来源角色、使用权、引用资格和原始获取回执；
- Candidate、Evidence、NumericFact 三种权限不得混同；
- 财务数值的单位、scale、期间、维度、vintage、修订与冲突；
- Evidence admission、Gap 资格、因果边界、materiality、WWC；
- 产品/经营事实如何桥接收入、利润、现金；
- claim 到 passage/page/table/cell 的准确定位；
- 人工审阅、失败不可变、阶段权限和最终发布标准。

因此，本次审计建议把项目重新定义为：

> 成熟数据面与运行时 + 很薄但严格的 FIN 金融权威内核 + FIN 自有的研究审阅产品表面。

成熟组件只能是“工人”，不能因为它会解析、召回、重排或生成 citation，就自动成为金融裁判。

## 2. 本次审计做了什么、没有做什么

本次审计从最终用户要得到的金融研究产品倒推，依次检查：

1. 产品定位、PRD、FIN 0.1.3 当前基线和 S0–S5 阶段责任；
2. S1 canonical evidence spine、S2 PIT numeric mart、S3 research runtime 和 Workbench；
3. capability ledger、root-cause ledger、外部模式 registry 和金融研究方法 registry；
4. 当前仓库的代码、脚本、配置、工作记录和依赖形状；
5. R3–R14 的版本化实现链和 R14 冻结失败；
6. 每个可替代通用能力的官方技术栈与产品边界。

本次审计没有：

- 修改 R14 生产代码、validator、corpus、failure receipt 或 oracle；
- 创建 R15/R16；
- 执行 formal、模型、Provider、外源抓取、embedding、reranker 或新报告；
- 删除历史 attempt、失败证据或旧实现；
- 授权迁移、采购或生产切换。

所有技术栈结论都是 owner-visible recommendation，不是 implementation authority。

## 3. 当前产品真实到哪一步

FIN 的产品定位仍然是“可审计的金融研究工作台 / AI junior analyst layer”，核心用户价值是帮助研究人员：

- 找到重要资料；
- 提取表格与事实；
- 对账数字和期间；
- 生成可追溯证据包；
- 形成有出处、有反方、有风险边界的研究稿；
- 由人审阅后交付。

当前已经有真实工程证据的产品表面，主要是三个 reviewed case 的只读 Evidence Workspace 和 operations 视图。当前不能宣称已经完成：

- 动态端到端研究任务；
- 自主开放网络研究；
- qualified-human Evidence admission；
- 产品级 S2 财务桥；
- 客户可读的完整 citation/source appendix；
- 完整研报、协作审批、publication 或 release。

最早仍未闭合的产品门，不是“再写一个 parser”，而是：

1. S1 blind qualification 尚未完成；
2. residual external source routes 尚未真实执行；
3. DELL 16 项 qualified-human admission 仍为 0/16；
4. 产品/经营事实到收入、成本、利润、现金的 S2 bridge 未闭合；
5. reader-visible citation、source appendix 和 passage/locator 绑定未完成；
6. WWC、反方和最终人工产品验收未完成。

## 4. 仓库量化结果

以下为 2026-08-30 对 clean 基线的 PowerShell 非空文本行统计（与本轮只读复算口径一致，不是包含空行的 physical LOC）。它们用于判断数量级和资源分配，不等同于“这些代码都没价值”。

| 区域 | 当前规模 | 审计含义 |
|---|---:|---|
| src | 205 个 Python 文件 / 170,511 行 | 产品核心代码已经很大 |
| src/retrieval | 118 文件 / 92,803 行 | 占 src 约 54% |
| DELL R-number 版本化模块 | 43 文件 / 55,032 行 | 占 retrieval 约 59.3%，占 src 约 32.3% |
| R14 当前生产模块 | 19 文件 / 16,816 行 | 单轮通用语义/治理实现已经很重 |
| R14 tests | 12 文件 / 6,362 行 | 尚不含合同和 runner |
| R14 implementation freeze commit | 37 文件 / 26,568 新增行 | Git 权威提交数字 |
| src/sec_agent/research | 37 文件 / 45,244 行 | 通用研究编排层非常重 |
| scripts/research | 43 文件 / 55,747 行 | 31 个 run_* 占约 94.3% |
| project_os_preflight.py | 14,870 行 | 大量 attempt/decision/successor 特例 |
| tracked configs | 1,190 份 | result/authority/policy/decision/profile 分叉显著 |
| 本机 ignored eval | 18,419 文件 / 约 2.055 GiB | 运行产物和 trace 已形成运维负担 |
| src/financial_facts | 约 1,804 行 | 真正差异化的金融事实内核反而很薄 |

最重要的结构信号是：

- 约三分之一 src 已经成为 DELL R3–R14 的版本化实现；
- retrieval 中约六成属于同一条 DELL 语义链；
- research runner 和 Project OS validator 的体量远超当前财务事实内核；
- 执行尝试的历史差异被逐渐固化成长期产品架构。

这不是简单的“代码多”。问题在于产品资源已经从“把可信研究交给用户”，偏到了“证明每一代自建运行时和 NLP 系统自身正确”。

## 5. KEEP_BUILD：FIN 必须继续自己拥有的能力

KEEP_BUILD 指“业务合同与最终裁决权必须由 FIN 拥有”，不代表底层数据库、队列、UI 控件和解析器也要自己写。

| FIN 必须拥有 | 为什么是产品护城河 | 当前边界 |
|---|---|---|
| Case、issuer、as-of、period、version、lineage | 决定研究对象和时间真相 | 动态 case 尚未产品化 |
| source role、许可、claim-use、citation eligibility | 抓到内容不等于可以引用或用于结论 | 真实外源路线仍未闭合 |
| Candidate ≠ Evidence ≠ NumericFact | 防止“召回到了”被误写成“事实成立” | human admission 仍未完成 |
| Evidence admission 与 reject/reopen reason | 决定什么材料能进入研究 | 16 项 qualified-human 为 0/16 |
| proposition-level coverage 与 GapEligibility | 空结果不能冒充公共信息缺口 | retrieval/runtime/source failure 要先排除 |
| PIT CompanyFact、unit、scale、period、dimension、vintage、conflict | 通用 RAG 不会替金融口径负责 | S2 产品资格仍 false |
| 产品/经营指标到收入、利润、现金的 typed bridge | 这是研究价值而不是检索 plumbing | 产品利润/现金桥仍开放 |
| materiality、causal boundary、counterevidence、WWC | 决定研究结论能说多强 | 仍需真实案例和人审 |
| claim ↔ source locator 与 citation admission | chunk ID 不是可读、可核查引用 | R17 reader citation 仍未完成 |
| FIN gold、hard negative、mutation、issuer-time split、human rubric | 供应商 benchmark 不能代替自己的正确性标准 | hidden qualification 未执行 |
| Workbench 的金融审阅交互 | 用户需要判断 Evidence/Gap/Readiness，不是看 trace dashboard | 当前表面主要只读 |
| product/S-stage/contract/attempt 分离与失败不可变 | 防止一次失败变成新产品版本或被覆盖 | 规则正确，但实现过度分叉 |

大白话概括：

> FIN 应自己定义“什么算可信金融研究”，不应该自己重写“怎么下载网页、怎么解析 PDF、怎么跑工作流、怎么存 trace、怎么调模型、怎么做向量搜索”。

## 6. ADOPT_MATURE：应该引入成熟技术栈的能力

| 通用能力 | 当前问题 | FIN 迁移后仍保留什么 |
|---|---|---|
| 官方数据 connector、HTTP/browser crawl、retry/rate-limit/resume | transport 和 source authority 混在一起 | source policy、capture receipt、as-of |
| WARC/原始响应归档 | 当前更偏清洗结果和自建 manifest | raw byte hash、来源身份和 retention authority |
| XBRL processor/validation | PDF/OCR 不足以表达正式财务事实 | canonical CompanyFact 与冲突处理 |
| PDF/OCR/layout/table/chunk 基础解析 | 自建 section/table 规则维护面大 | FinancialEvidenceObject 投影与财务验收 |
| PostgreSQL、对象存储、Parquet snapshot | JSON/JSONL/SQLite/DuckDB 和本地产物分散 | digest、parent lineage、PIT 和 admission state |
| lexical/vector/hybrid index 与 metadata filter | 自建搜索编排多，blind qualification 仍未完成 | query hard constraints、Evidence 权限 |
| embedding/reranker serving | GPU、batch、model version 不应重复自建 | FIN qrels、critical slice 和 promotion gate |
| LLM source-grounded semantic extraction/judging | 确定性英文 parser 承担了开放语义 | schema、span、hard validator、abstain/human |
| Agent graph、checkpoint、resume、HITL | 自建 runtime、runner、successor 不断扩张 | domain state、attempt identity、idempotency receipt |
| Provider SDK 与结构化输出 transport | 自建 HTTP/SSE/error/profile 分叉 | TokenBudgetBasis、capability allowlist、post-validation |
| trace、eval、experiment、artifact browsing | 产物散落，重复 result/authority 文件多 | immutable FIN receipt、gold 和 release gate |
| 通用 schema/CI/policy plumbing | preflight per-attempt 特例过多 | 少量全局不变量和金融政策 |
| 通用身份、SSO、SCIM、secret、audit-log 基础设施 | B2B 能力不应自建安全底座 | organization、financial role 和 domain permissions |
| 不可信网页/文档摄入安全 | crawl、PDF、Office、压缩包和 LLM-visible 内容会引入 malware、SSRF、资源耗尽和 prompt injection | source allowlist、privacy classification、content/tool authority 分离与安全失败回执 |
| bibliography、cross-reference、PDF/DOCX/HTML 渲染 | reader citation 仍未交付 | claim/evidence correctness 与 pre-render gate |

## 7. HOLD_EXPERIMENT：目前不应该默认建设

| 能力 | 为什么暂缓 | 重新开启条件 |
|---|---|---|
| GraphRAG / 通用知识图谱 | 当前 typed graph handler 不完整，普通 hybrid 尚未做合格 blind baseline | 预先冻结的跨文档多跳题证明 hybrid 系统性失败 |
| 4B/7B embedding 或 reranker | 当前资源受限，且现有候选 ceiling 已显示部分答案在 pool 内 | 新 pool/blind eval 证明排序是最早瓶颈 |
| 新模型微调 | gold、hidden split、错误归属和产品门尚不完整 | 稳定任务、足够人工 gold、baseline ceiling 明确 |
| autonomous multi-agent | 当前主要缺口是证据、人审和产品闭环，不是 agent 数量 | 单 Agent vertical 稳定且有可量化并行收益 |
| 自动 Evidence promotion | 模型、parser、reranker 都不能获得事实权威 | qualified-human 通过且高风险 slice 有明确自动化门 |
| OPA/Temporal/LiteLLM/Langfuse | 都成熟，但当前规模/多租户/多 provider 条件未出现 | 达到各自的生产触发条件 |

## 8. RETIRE_OR_SHRINK：应退出生产主路径或大幅收缩

退出生产主路径不等于删除历史。冻结 corpus、失败结果、回归 case 和旧 attempt 必须继续作为 immutable evidence 保存。

| 当前能力 | 建议 |
|---|---|
| R14 确定性英文 PredicateFrame/EventArgumentGraph 作为开放语料的生产语义裁判 | 冻结为 regression/adversarial fixture 和 baseline evidence；已知错误输出不得充当 truth oracle，不再默认扩写为通用 NLP 引擎 |
| DELL R3–R14 多套 active 版本化模块 | 迁移通过后只保留一个 canonical active adapter；旧版归档/fixture 化 |
| 每个失败新建 runner/schema/policy/authority/successor validator | 收敛成通用 state machine + typed failure envelope |
| project_os_preflight.py 的 per-attempt 特殊分支 | 只留跨版本不变量和少量阶段权限；其余数据驱动 |
| 自建 raw Provider HTTP/SSE gateway | 用官方 SDK/成熟网关承接 transport；保留薄 capability/budget/receipt adapter |
| 自建 trace/eval/result 文件堆作为主要实验平台 | 历史冻结；新 run 进入一个成熟 experiment backend |
| 用 regex/关键词/自建句法判断完整开放语义 | 只保留 ID、日期、金额、单位、主体硬边界等确定性检查 |
| 通用 Workbench runtime dashboard | 交给成熟 trace/experiment UI；FIN UI 聚焦 Evidence/Gap/Review/Release |

任何 retire 都必须先通过 adapter、shadow、dual-read 和 rollback gate，不能按行数直接删除。

## 9. R14 在这次审计后的新定位

R14 不是普通“RAG 调参”。它已经自己完成了：

- token/clause/predicate 切分；
- mention/event/role/scope graph；
- speech mode、semantic labels、event type；
- price attachment；
- validator/oracle/rebuilder；
- exact-once、transaction、privacy、manifest 和审计生命周期。

冻结实现一次新增 26,568 行，但唯一 preview 仍为：

- corpus 27,026；
- pass 26,787；
- fail 239；
- event-semantics 228；
- assertion-semantics 11；
- event mismatch 277；
- product capability delta = none。

两个根因在局部工程上可以修：

1. synthetic predicate 绕过 canonical semantic derivation；
2. assertion attribution 使用中间 mention snapshot，而 validator 使用最终 graph mentions。

S1/128 因此在局部根因充分的前提下，曾建议授权一次同 R14 revised implementation。那一建议并非错误，但它回答的是“这两个 bug 能否在同一 R14 修”，没有回答“FIN 是否还应长期经营一套通用英文事件解析器”。

本次产品级审计引入了新的、范围更大的证据：

- R3–R14 版本化模块已达 55,032 行；
- R14 单轮新增 26,568 行；
- 相同问题已有成熟 LLM 结构化抽取、span grounding 和 human escalation 模式；
- 当前最早产品缺口在 Evidence、人审、S2 bridge、reader citation 和报告，而不是 parser 继续扩张。

因此当前推荐更新为：

> 不把继续扩写确定性 parser 作为默认动作。R14 保持冻结，先由 Owner 决定它是只做一次最小局部修复后退役，还是把当前 parser 与失败冻结为 regression baseline，并在同一 S1 责任层证明一个模型辅助 replacement challenger。

两个待 Owner 授权的候选路线都不得创建 R15/R16，也不得提前进入 formal 或下游：

- 选项 A：一次极小的同 R14 deterministic correction，只修两项已冻结根因。完整验收不是只有 27,026/27,026，还必须同时满足 277/277 mismatch eliminated、zero new failure code、原 population/event/price/property/mutation/resource/transaction/privacy gates 不弱化、禁止 case/text/event 特例、禁止绕过 validator，并获得新的 author-separated read-only pre-formal PASS；之后停止功能扩写，转为 legacy baseline。
- 选项 B（本次审计推荐）：不再先修现有 parser，而是在同一 S1 责任层建立 source-grounded LLM replacement challenger。RC-S1-109/110 在 replacement 通过前继续 open，shadow pilot 不关闭任何根因，也不获得 downstream authority。当前 corpus、失败和 parser 输出只作为 immutable regression/baseline evidence，不能作为 truth oracle；真值必须来自 case-correct human-adjudicated gold。只有 exact span、strict schema、deterministic hard validators、abstain、关键金融 slice、human gold 和独立审计全部通过后，Owner 才能决定 replacement adapter 是否接管并关闭同阶段责任。

选项 B 不是让大模型自动准入 Evidence，也不是用“新架构”绕过 I2 或遗留项目内根因。它只是把开放语言语义候选交给更合适的工具，FIN 继续掌握主体、期间、金额、来源、admission 和人审；若 replacement 无法在同一阶段证明接管责任，RC-S1-109/110 仍保持 blocker。

## 10. 建议目标架构

~~~text
官方/成熟基础设施
  SEC/XBRL · crawl/WARC · document AI · hybrid search · rerank
  LLM structured extraction · workflow/checkpoint · SDK · trace/eval
  PostgreSQL/object store · identity/security · report rendering
                              │
                              │ typed adapter；进入对应层级的 unadmitted envelope
                              ▼
FIN 金融权威内核
  Case + issuer + as-of + source role
  EvidenceRequest + Candidate/Evidence/NumericFact authority
  PIT + unit/period/vintage/conflict + financial bridge
  Gap + causal boundary + materiality + counter/WWC
  human review + report/release gate + immutable receipts
                              │
                              ▼
FIN 产品表面
  Evidence Workspace · Workpaper · Review/Repair/Approval · Deliverable
~~~

这些 envelope 不应被压成同一个 Candidate：

- crawl/WARC → SourceCapture；
- parser → ParsedElement / TableCell / Locator；
- XBRL processor → unadmitted FactObservation；
- search/reranker → RetrievalCandidate；
- LLM extraction/judge → SemanticCandidate；
- 只有 FIN admission 之后才可能成为 Evidence 或 NumericFact。

架构上只允许：

- 一个 canonical FIN contract source；
- 每个责任层一个主实现：外层数据/研究 workflow 与内层 LLM Agent graph 不合并；
- 当前外层 workflow 的 primary candidate 为 Dagster、Prefect 为 challenger；LangGraph 只在单研究 vertical 中竞争内层 Agent graph；
- Temporal 只有真实跨 worker、跨重启长任务、timer/signal 或 Saga 需求出现后才进入；
- 一个主要 trace/experiment backend；
- 一个 canonical metadata store；
- 每类能力一个 default、最多一个 challenger 和一个 managed ceiling；
- 供应商 schema 永远不得渗透成 FIN 上层权威。

## 11. 建议的资源重新分配

如果 Owner 接受本次边界，后续工程资源应从“继续证明自建通用 plumbing”转向：

1. 真实来源和 XBRL/PDF dual-channel；
2. 难文档与表格的可追溯解析；
3. blind S1 retrieval/evidence qualification；
4. 16 项 Evidence 人审工作台；
5. S2 产品/利润/现金桥；
6. reader-visible citation/source appendix；
7. claim-level 反方、WWC 和最终报告验收；
8. 最后才是生产扩展、企业 IAM 和多租户。

这不是“少做准确性”，而是把准确性从“证明我们自己写的 NLP/运行时”重新放回“证明研究结论对用户可靠”。

## 12. 2026-08-31 Step 3 reconciliation：实测后的模块迁移基线

### 12.1 漂移复核与新增事实

从原产品审计提交到 Step 1 基线，生产代码、测试和依赖没有发生会推翻 Build / Adopt / Hold / Retire 结论的漂移；原统计已独立复算一致。新增的真实证据不是另一轮市场清单，而是：

- 整个 `scripts` 已达 169 个 Python 文件／103,967 非空行；其中 `scripts/data_retrieval` 为 103／43,818，不能只审 R14 与 `scripts/research`；
- Workbench backend/frontend 约 7,693 行，包含一套自建 store、job、process runner、operations 和 artifacts 通用运维面；
- 当前活动 import graph 中 DELL R3–R14 的 43 个版本模块活动数量为 0，因此它们应作为 regression/adversarial evidence，而不是下一条生产主线；
- 当前活动图仍有 `evidence_role_v2/v3/v4`、`financial_intent_v2/v3` 等 16 个版本家族／5,455 行，需要选一个 canonical implementation；
- `Dockerfile` 安装 `requirements.txt`，但 Workbench 顶层路径需要的 `pypdf` 和 `playwright` 只在 `pyproject.toml`，Pydantic 约束也分别为 `>=2.7.0` 与 `>=2.13,<3`；干净 `requirements.txt` 环境已实证在导入 Workbench 时因 `ModuleNotFoundError: pypdf` 失败；仓库也没有 Python lockfile。

### 12.2 成熟控制面确定性 fixture 切片结果

同一手工、确定性的 DELL-shaped revenue PIT fixture 被两个 workflow adapter 调用：截至 2026-06-01 选择 `40,000,000,000`，截至 2026-08-06 选择 `43,842,000,000`，保留 fixture 中的 accession 与占位 source digest。引擎只编排，未复制或改写 FIN `NumericFact` 权威。这证明真实 FIN fact-mart 代码路径可被成熟 workflow 调用，但 `real SEC source replay=false`、`data correctness qualification=false`、`source admission=false`。

| 能力 | Exact build | 实测结果 | 当前决定 |
|---|---|---|---|
| Dagster | `1.13.20` | 原生 retry 1 次后成功；持久化 run=`7b4015c2-c170-4bdb-aea8-c6acb9aed5b0`，新进程读回 `SUCCESS`；状态均在 Z 盘，遥测关闭 | 外层数据/研究 workflow `PRIMARY CANDIDATE`；不是 production PASS |
| Prefect | `3.8.4` | 原生 retry 1 次后成功；最终 run=`34c26437-b02c-4f5b-abf1-bae8d75ad3b8`；显式关闭 result persistence、固定 memo/state 后不再写 C 盘，状态重读为 `COMPLETED` | `CHALLENGER`；默认用户目录写入和临时服务启动开销是迁移 caveat |
| PostgreSQL | official `18.6` 目标 | Docker Desktop 因本机 listener 路径错误启动失败；未拉镜像、未伪造 SQLite 代替事务/锁/重启/备份证明 | `REQUIRED BUT ENVIRONMENT_BLOCKED`；生产 workflow/state integration 继续 blocked |
| MLflow | `3.15.2` | 本地 tracking server、artifact 写入、client readback 均通过；Windows job execution backend 报不支持 | 仅作 qualification backend；生产采用等待 PostgreSQL/object store 与安全阻断关闭 |
| OpenTelemetry | `1.44.0` | 每次 FIN slice 产生 1 root + 3 child spans，未写正文或 secret | 标准语义 `ADOPT`，collector/backend 后续资格 |
| OpenLineage client | `1.52.0` | FileTransport 的 START/COMPLETE 共 2 事件且 run ID 一致 | 标准 event `ADOPT`；当前不部署第二套 lineage backend |
| DVC | `3.67.1` | Windows 本地远端首次 `file://` 配置失败证据保留；改为受支持路径后 push，移走工作文件和本地 cache，再 pull 恢复，SHA-256 exact | 只对大型版本化 corpus/model/index `CONDITIONAL ADOPT`；小 receipt 不用 DVC |
| lock / SBOM / license | uv `0.10.7`；277 packages | hash-locked resolve/install、277-component CycloneDX SBOM、272-package license list完成 | 以后候选必须 lock + SBOM；本次 lab 不直接进入 production dependencies |
| vulnerability audit | pip-audit `2.10.1` | 3 个已知漏洞：cryptography 49.0.0、diskcache 5.6.3、pytest 8.4.2 | 当前组合 `PRODUCTION BLOCKED`；MLflow `<50` 阻止 cryptography 修复，diskcache 暂无修复，pytest 应升级或不进入 runtime |

实验目录逻辑大小约 1.94 GiB；结束时 D/Z 可用约 4.643/16.142 GiB，低于 5 GiB 实验预算且未触发任何索引删除条件。`D:\FIN_Insight_Agent\data\indexes` 未修改。

### 12.3 模块级 retain / wrap / replace / regression / retire

下表冻结“旧代码与成熟 owner 的关系”，不是声称迁移已经完成。`retain` 只表示保留 FIN 权威和可复用实现，不表示文件内每一行永久保留；`replace` 也必须先 shadow/dual-read/rollback，不能直接删除历史。

| Stage / capability | Current modules | Disposition / mature owner | FIN 保留的 port / authority | 前置、验收与退出 |
|---|---|---|---|---|
| S1 canonical contracts | `retrieval/contracts.py`、`artifact_spine.py`、`source_use_policy.py`、`evidence_admission.py`、`evidence_set_coverage.py`、`human_operability.py`、`evidence_role_contract.py`、`temporal.py` | `retain` | issuer/as-of/source role、Candidate/Evidence 分权、admission、Gap、locator、人工操作 | 供应商输出只进 unadmitted envelope；关键金融 slice 不退化 |
| S1 official capture | `connectors/sec_edgar_connector.py`、`ingestion/official_source_capture.py`、`source_intake.py` | `wrap`：SEC/Arelle + Scrapy/Playwright/warcio + intake security | SourceCapture receipt、许可、来源身份、PIT、安全分类 | raw hash/WARC round-trip、rate/retry/resume、SSRF/malware fixtures；旧 capture 可重放 |
| S1 PDF/layout | `ingestion/section_splitter.py`、`pdf_layout.py`、`official_pdf.py` | `replace`：Docling default、MinerU challenger、最多一个 managed ceiling | ParsedElement/TableCell/Locator 投影与财务表验收 | frozen hard-PDF、page/bbox/cell/footnote parity；不合格即回旧 parser |
| S1 object/search | `financial_objects.py`、`hybrid_candidate_runtime.py`、`candidate_retriever.py`、`embedding_runtime.py`、`cross_encoder.py`、Workbench `research_retrieval_service.py` | `wrap/replace`：PostgreSQL+pgvector vs OpenSearch；BGE vs managed ceiling | FinancialEvidenceObject、query hard constraints、qrels、Evidence gate | 同 corpus/query A/B、PIT/source filter、rebuild/rollback；index 可由 canonical objects 重建 |
| S1 活动版本链 | `evidence_role_v2/v3/v4`、`financial_intent_v2/v3` 等 16 文件 | 选一个 `canonical retain`；旧版 `compatibility/regression` 后 `retire` | 当前合同兼容与 gold | import/consumer 图归一；shadow parity 后才移除活动依赖 |
| S1 R3–R14 | 43 文件／55,032 行；活动 import=0 | `regression`，replacement 通过后 archive/retire | 27,026 corpus、239 failure、277 mismatch、validator、失败回执 | 不再扩写；不是 truth oracle；RC-S1-109/110 继续 open |
| S2 NumericFact/PIT | `financial_facts/contracts.py`、`sec_companyfacts.py`、`executor.py`、`mart.py` 及 numeric authority/bridge | `retain/wrap` | period/unit/vintage/conflict、formula lineage、产品→收入/利润/现金 bridge | 确定性 DELL-shaped fixture 已证明真实代码路径可被成熟 workflow 调用；真实来源、金融真值、完整 bridge/product acceptance 仍开放 |
| S2 XBRL | `sec_companyfacts.py` 中 transport/parse 与映射混合面 | `wrap`：SEC API + Arelle | FIN concept mapping、supersession、conflict、NumericFact admission | accession-bound raw filing、amendment 和 dimension parity |
| S2 physical mart | 当前 SQLite/DuckDB/JSON/Parquet 路径 | `replace physical owner`：PostgreSQL online + Parquet snapshot + DuckDB local audit | canonical schema 与 typed lookup port | PostgreSQL 16.15 本地单容器 transaction/unique/advisory-lock/restart/host-roundtrip backup/restore已有历史可行性证据，hardened clean-commit复证待跑；canonical cutover、HA/TLS/PITR/operator仍 blocked；旧 SQLite继续是 rollback |
| S3 research domain | `material_scope.py`、claim/report/research context、reviewed pack/anchor、finance tool contracts、actionable state/eval | `retain` | materiality、claim authority、counter/WWC、Evidence/NumericFact consumption、失败归属 | 人工 gold 与真实 report acceptance；workflow 不获得研究结论权威 |
| S3 mixed loops | `bounded_finance_loop.py`、`current_consumer.py`、`case_truth_reconciliation.py` | `split/wrap` | 抽出 FIN 决策与 evaluator；执行循环进入 outer workflow/inner agent ports | 逐 consumer shadow；不把 legacy loop state变成新框架 schema |
| S3 attempt runtimes | `multi_agent_preview.py`、`multi_agent_preview_runtime.py`、`multi_agent_successor.py`、dynamic/five-cell loops、17 个活动 research runner | `regression/retire` | 成功/失败案例、gold、TokenBudgetBasis 和必要领域合同 | 单 canonical vertical 接管后逐波退役；禁止再建 R-number 通用 runtime |
| S3 provider transport | 当前 HTTP/SSE/live transport package | `replace`：官方 SDK + thin capability adapter | max-retry policy、request hash、unknown completion、task-specific TokenBudgetBasis、post-validation | saved fixture parity；SDK internal retry默认 0；provider schema 不上渗 |
| S3 inner Agent graph | 当前 dynamic loop 中混合的 graph/HITL | `hold qualification`：LangGraph 单 vertical candidate | domain state、human decision、tool permission | 不承担 capture/index/experiment/outer pipeline；crash/interrupt/idempotency proof 后再选 |
| S4 Research Workspace | `ResearchWorkspace.tsx`、workspace/evidence services | `retain` | Evidence/Gap/Review/Repair/lineage/approval 产品交互 | 用户可完成 16 项 admission 与 citation drilldown；generic trace UI 不复制 |
| S4 generic operations | `sec_agent/workbench/store.py`、`process_runner.py`、`jobs.py`、backend/frontend operations、`artifacts.py` | `replace/shrink`：outer workflow + PostgreSQL + MLflow | case/evidence 产品投影和必要操作入口 | 功能逐项映射、dual-read、旧 job/history 导出后收缩 |
| S5 application stack | FastAPI/Uvicorn、React/Vite、Playwright、Pydantic、Docker、GitHub Actions、DuckDB、pytest/npm | `retain mature` | FIN API/UI contracts 和验收 | `pyproject.toml + uv.lock` 单一依赖 candidate已落盘；最终 clean full regression、Docker真实 job与供应链收据待签发 |
| S5 outer workflow | `scripts/data_retrieval`、`scripts/research`、Workbench jobs 中的调度/重试/状态 | Dagster `primary candidate`；Prefect `challenger` | typed job input/output、attempt identity、side-effect idempotency | 一条 S2 shadow adapter implementation candidate已落盘；最终 clean PostgreSQL run/event/restart/restore和Docker只读真实数据执行待签发；production daemon/operator未测 |
| S5 durable long jobs | 尚无独立成熟 owner；部分逻辑散在自建 runner | Temporal `HOLD` | external side-effect idempotency / Saga domain decision | 仅多 worker、长人工等待、跨重启 event history、timer/signal 或 Saga 触发 |
| S5 experiment/telemetry/lineage | result/authority/trace 文件堆与 runner 内自建记录 | OTel `adopt`；MLflow `pilot/blocker`；OpenLineage concepts/client `adopt` | immutable FIN receipt、artifact digest、gold、release gate | 漏洞与 PostgreSQL/object-store blocker关闭；删除 backend 不改变 Evidence |
| S5 large artifacts | ignored eval/corpus/model/index 与散落 manifest | DVC `conditional adopt` | frozen manifest/digest 与 retention authority | 只在大型资产使用；Windows path adapter；任何 artifact 可导出并由 canonical source 重建 |
| S5 dependency/supply chain | 根 `pyproject.toml + uv.lock`；旧 requirements已退出；locked Docker/CI | `retain mature process`：uv + CycloneDX/pip-audit/pip-licenses；镜像采用checksum-pinned Syft＋Grype；OSSF CVE Binary Tool稳定版因自身脆弱依赖闭包被拒绝，仅保留无`gsutil`上游commit作为隔离challenger；签名/来源证明后续独立门 | 本轮晋升的core/control-plane/qualification profiles与release gate | 当前lock157 records并隔离supply/build tools、含setuptools hashes；前端nanoid high已修复；候选全仓2628/5通过；Python 3.11.16＋OpenSSL 3.5.7 dirty v6镜像raw Grype各为236 matches（7 Critical/31 High），从v1的352/11/94实质下降但仍非PASS；剩余含待来源绑定triage的generic binary finding、Debian stable无修复项和NOT_PROVEN wheel native身份，final fresh env、同commit镜像、license/legal与production gate均未签发 |
| S5 identity/security | 客户端 `X-Fin-Case-Permissions` header、本地 secret/日志 | `replace`：部署战略确定后选 OIDC/IAM、secret manager、audit log | organization、financial role、domain permissions | 当前只算本地开发；企业部署前必须做 issuer/tenant/role 隔离 |
| S5 report rendering | 当前自建 report/output path | `adopt`：Quarto + Pandoc + CSL | typed report、claim/evidence/locator pre-render validation | HTML/PDF/DOCX visual QA；renderer 不判断 citation correctness |

### 12.4 当前迁移先后顺序

这张表不会触发一次性重写。Owner已授权以下第1–3项；当前是 implementation candidate，最终 clean证据仍待跑：

1. 先统一 Python 依赖源并完成 clean build/import/lock/SBOM；
2. 修复 Docker Desktop 或改用明确支持的 PostgreSQL 资格画像，完成 transaction/lock/restart/backup；
3. 只把一条外层数据/研究 vertical 接到 Dagster primary candidate，Prefect 保持同输入 challenger；
4. 同时保持 R14、Evidence、S2 bridge、报告和产品权限不变；
5. 再按 S1 parser、search、S3 agent、S4 operations 各自 frozen benchmark 逐波迁移，不做全仓大爆炸式重写。

当前第1–3项的代码候选已经形成，但旧034026/040515不绑定后续 hardening，不能签发完成；legacy code未删除、成熟栈未生产切换、产品未PASS。

### 12.5 Owner 授权后的候选实现与未关闭门

Owner 随后明确授权上述第1–3项。真实安装、历史可行性纵切和候选实现已经发生，但当前版本仍须从clean commit重跑最终证据：

- 单一依赖源/lock已进入代码，当前lock为157 records并含独立locked supply/build tooling与setuptools artifact hashes；v2实际环境33/86/88与当时0 known Python vulnerabilities只作pre-successor历史，这不是镜像、法律或最终签发；
- `control-plane`固定 Dagster `1.13.20`、dagster-postgres `0.29.20`、dagster-webserver `1.13.20`、filelock `3.32.4`；psycopg `3.3.4`已拆到qualification-only overlay；
- official PostgreSQL `16.15-alpine` exact digest已有 transaction、UNIQUE、advisory lock、restart、dump/restore历史可行性证据；最终runner增加了clean Git、runtime inventory、ownership cleanup、真实host-roundtrip restore和run/event校验，尚待新attempt；
- DELL/MU/NVDA本地 source-bound captures的历史纵切得到1,319 observations、24/24 qrels与legacy/Dagster业务投影 exact；最终Docker只读mount和最终commit复证仍待跑；
- domain-thin adapter进入 `src/sec_agent/adapters/`，用成熟filelock并执行路径/凭据/timeout/digest边界；默认Workbench不安装Dagster；legacy CLI仍是canonical business entrypoint与rollback，删除量为0；
- LangGraph因该确定性数据物化没有 checkpoint/HITL/Agent graph需求而继续 HOLD。

因此迁移矩阵中 `S5 outer workflow → S2 fact-mart shadow` 目前仍是 `implementation candidate / final qualification pending`，尚不能写成最终 bounded adoption。旧 `034026`/`040515`只作历史可行性证据。即使最终通过，也不是S2产品晋升、全仓production migration或用户功能完成；产品增量仍为0。

## 13. Owner 需要决定的事项

本审计完成后，没有任何迁移自动获得授权。Owner 已接受成熟栈优先边界，并授权实施 dependency/PostgreSQL/单 Dagster vertical 候选；最终 bounded adoption 仍须由 clean-commit 资格证据另行签发。剩余建议 Owner依次决定：

1. R14 选择 A 满足 S1/128 全门的最小修复后退役，还是 B 在 RC-S1-109/110 继续 open 的前提下，以 human-adjudicated gold 证明同阶段 replacement；
2. 是否选择“低运维本地优先”还是“较早采用托管云 ceiling”的部署取向；
3. 下一条具备用户价值的产品 vertical是什么，以及它自己的 benchmark/rollback；
4. 何时才允许逐步退役旧代码。

在 Owner 决定之前：

- R14 implementation change=false；
- R14 pre-formal/formal=false；
- R15/R16=false；
- external/model/reranker/Evidence/S2/S3/report/product/release authority=false；
- S2 fact-mart Dagster shadow implementation candidate=true；final bounded adoption=false；production stack cutover=false；legacy retirement=false。

## 14. 证据索引

- [产品定位](PRODUCT_20260628_finsight_tob_toc_positioning_and_product_line.zh-CN.md)
- [当前基线](FIN_0_1_3_CURRENT_BASELINE_AND_S0_TO_S5_CLOSEOUT_PLAN_20260812.zh-CN.md)
- [S1 canonical spine](../architecture/retrieval/FIN_0_1_3_S1_EVIDENCE_ACQUISITION_AND_PACK_QUALITY_PARADIGM_20260817.zh-CN.md)
- [S2 Company Financial Fact Mart](../architecture/financial_facts/FIN_0_1_3_S2_COMPANY_FINANCIAL_FACT_MART_20260813.zh-CN.md)
- [Agent runtime audit](../architecture/research/FIN_0_1_3_AGENT_RUNTIME_REFLECTION_CONTEXT_CONTINUITY_AUDIT_20260819.zh-CN.md)
- [R14 source plan](../worklog/fin_0_1_3_s1/124_dell_03b_R14_program_level_architecture_execution_plan.md)
- [R14 I2 closeout](../worklog/fin_0_1_3_s1/128_dell_03b_R14_I2_corpus_parity_governance_correction_and_reaudit_pass.md)
- [成熟技术栈详细决策包](../architecture/research/FIN_0_1_3_MATURE_TECH_STACK_LANDSCAPE_AND_ADOPTION_DECISION_PACKET_20260830.zh-CN.md)
- [技术来源快照清单](../architecture/research/FIN_0_1_3_MATURE_STACK_RESEARCH_SNAPSHOT_MANIFEST_20260830.zh-CN.md)
- [成熟栈优先架构决定与 Steps 1–3 基线](../architecture/repository/FIN_0_1_3_MATURE_STACK_FIRST_ARCHITECTURE_DECISION_AND_EXECUTION_BASELINE_20260830.zh-CN.md)
- [Steps 1–3 工作记录](../worklog/fin_0_1_3_s1/130_mature_stack_first_rebase_and_steps_1_to_3_start.md)
- [Dependency/PostgreSQL/Dagster 真实纵切面工作记录](../worklog/fin_0_1_3_s1/131_dependency_postgres_and_dagster_real_vertical_integration.md)
