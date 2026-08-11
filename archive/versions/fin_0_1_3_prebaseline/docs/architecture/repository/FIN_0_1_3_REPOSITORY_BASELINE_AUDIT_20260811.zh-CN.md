# FIN 0.1.3 全仓代码、文档、数据与依赖基线审计

日期：2026-08-11

审计基线：分支 codex/layered-data-source-expansion，提交 7cd373885a2f5958baa69a285d15e9b1b72f72d4

状态：baseline_candidate，等待 Owner 审阅后再制定清理规范与下一步实施路线

## 1. 这次审计回答什么

这次不是继续修 S3，也不是给仓库再加一套抽象层。目标是回答四个基础问题：

1. 从仓库建立以来，未明确归档或丢弃的代码、文档和数据到底有哪些。
2. 哪些文件真正进入当前产品入口，哪些只是 FIN 0.1.3 候选、测试、一次性运行器或不可变证据。
3. 当前 FIN 0.1.3 到底做到哪里，能否作为后续工作的诚实新基线。
4. 为什么项目长期出现“修完一处又冒出一处”，哪些是合理探索成本，哪些是仓库与工程治理造成的返工。

本轮只做盘点、定界和记录。没有删除、移动、归档、重构、模型调用、Provider 调用或网络检索，也没有把任何失败 attempt 改写成成功。

## 2. 结论先行

当前仓库存在一个可工作的产品骨架，也积累了相当多有价值的金融控制面和检索研究成果；问题不是“什么都没做”。真正的问题是四类资产长期混在一起：

- 用户实际进入的 Workbench / API / CLI 产品主干；
- 尚未正式切入产品主干的 FIN 0.1.3 S1–S3 候选能力；
- 为每次 proof、admission、exact-live 和失败终态建立的运行器、配置、测试和记录；
- 历史版本、兼容实现、原始数据、派生索引和本机临时资产。

现有自动架构清单把几乎所有非 archive 脚本都叫作 active_script，把全部 release JSON 都叫作 runtime_config，再把文档引用和 Python import 混成一张图。因此它能回答“仓库里谁提到了谁”，不能回答“当前产品实际执行了谁”。这也是用户打开仓库后看不到主干的直接原因之一。

本次审计给出的基线判断是：

- FIN 0.1.3 可以作为新的工程基线名称，但只能记为 current engineering candidate，不能记为 product/release pass。
- 当前 Workbench 后端入口的静态 Python 可达集是 150 个文件；几个公开 CLI/MCP 入口合并后约 161 个。仓库中 src/apps/scripts 下共有 1,229 个 tracked Python 文件，约 1,068 个不在这些稳定入口的静态可达图中。
- 未可达不等于无用：其中包含离线数据管道、评测、迁移和必要工具；但也包含大量一次性 release runner、历史兼容实现和未晋升的 S1–S3 candidate。它们必须按职责和生命周期重新分层，不能继续统一叫“active”。
- FIN 0.1.3 的 S1 检索与证据、S2 数值控制和 S3 动态研究均已有实质成果；但当前 Workbench 仍主要消费 FIN 0.1.2 的 S2/S3 binding、S4-T06/T07 projection/review 以及历史 runtime。FIN 0.1.3 候选尚未完成产品切换。
- 当前 S3 最新自然 canary 是 immutable failed：传输和 JSON 正常，金融判断部分有价值，但项目没有完整编译 enum / Evidence role / Numeric selection 合同，DeepSeek 也违反了明确的 no-numeric-band 约束。完整修复后报告、八维质量、paired、qualified-human 和 Owner acceptance 均未完成。
- 仓库膨胀主要不是业务代码本身，而是执行证据被放入 configs/releases、scripts/releases、tests/contract 和 docs/worklog。自 2026-07-19 主干审计后约 12 天增加 3,006 个文件，绝大多数来自这些证明面。

## 3. Git 与版本真相

| 项目 | 观测 |
| --- | --- |
| 当前分支 | codex/layered-data-source-expansion |
| 当前提交 | 7cd373885a2f5958baa69a285d15e9b1b72f72d4 |
| 上游 | origin/codex/layered-data-source-expansion |
| 当前状态 | clean、与上游同步 |
| 首个提交 | 4893e4bc7e726b302b0d8ed21126c2681fd67211 |
| 提交数 | 588 |
| main worktree | D:/FIN_Insight_Agent_main_merge @ 179be9b1 |
| 现有版本标签 | fin-0.1.1-internal-honest-block、v0.1.0-resume-demo |
| FIN 0.1.3 标签 | 不存在 |

因此，当前工作真相是“分支＋精确 commit”，不是 main，也不是一个已经签发的 FIN 0.1.3 tag。后续若 Owner 接受本基线，应另行决定是否创建 baseline tag；本轮没有创建。

### 3.1 FIN 0.1.3 同名文档冲突

仓库里存在两个不同含义的 FIN 0.1.3：

- 2026-08-01 的 FIN_0_1_3_CANONICAL_S0_TO_S5_PRODUCT_PROGRESSION_PLAN 是历史 S0 recovery attempt，后来已在版本治理中冻结。
- 2026-08-05 起的 FIN_0_1_3_REPAIR_CLOSEOUT_SCOPE_AND_DELTA_S0_TO_S5_PLAN 才是当前 repair-closeout 路线，并持续更新至 2026-08-11。

本基线采用后者。前者保留为历史，不删除，也不再作为 current plan。

## 4. 全仓资产盘点

### 4.1 Git tracked 资产

当前共 6,112 个 tracked 文件，约 153.6 MB。以下表按顶层目录覆盖全部 tracked 文件，不把“文件数量”误当作“产品能力数量”。

| 顶层目录 | 文件数 | 约大小 | 实际职责 |
| --- | ---: | ---: | --- |
| configs | 1,409 | 46.56 MB | runtime policy、release authority、attempt/result/decision 等；名称为 configs，但大量内容实为不可变执行证据 |
| docs | 1,630 | 24.88 MB | PRD、TECH、Project OS、1,220 份 worklog 和历史审计 |
| tests | 970 | 9.39 MB | 单元、contract、mutation、clean proof；contract 子树 668 个文件 |
| scripts | 802 | 11.04 MB | 数据运维、评测、release runner、CLI；release 子树 359 个文件 |
| data | 493 | 39.95 MB | 主要为 489 个 tracked manifest；不含大体积私有原文与索引 |
| src | 408 | 12.63 MB | 核心库、canonical runtime、历史 runtime、FIN 0.1.3 candidate |
| reports | 246 | 3.45 MB | 224 个 model run 记录、retrieval eval 和 release evidence |
| apps | 104 | 3.06 MB | Workbench 前后端；后端 51、前端 39，其余为包与说明 |
| eval_sets | 23 | 2.57 MB | 评测集 |
| archive | 6 | 0.03 MB | 明确归档的 retrieval prototype |
| 其他根文件/目录 | 21 | 约 0.6 MB | README、pyproject、锁文件、规则等 |

### 4.2 本机 ignored / generated 数据

这些资产不是 Git 权威，但会影响真实运行、磁盘、索引新鲜度和复现。盘点只读取路径、数量和大小，没有读取凭据内容。

| 路径 | 文件数 | 约大小 | 生命周期判断 |
| --- | ---: | ---: | --- |
| data/indexes | 75 | 27.26 GiB | 派生索引，可重建但成本高；必须绑定 source/manifest digest |
| data/staging | 34 | 16.41 GiB | 中间加工层；不应作为事实权威 |
| data/processed_private | 246 | 13.99 GiB | 私有加工结果；需 lineage 和 retention 规则 |
| data/raw_private | 10,622 | 12.79 GiB | 私有原始来源；事实根之一，不进入 Git |
| data/workbench_private | 600 | 1.73 GiB | Workbench 私有运行/展示资产 |
| data/manifests（含 ignored） | 755 | 1.69 GiB | tracked 与本地生成 manifest 混合 |
| eval | 18,419 | 2.06 GiB | 本地评测产物 |
| .codex_runtime | 20,639 | 0.70 GiB | attempt/capture/runtime 临时权威 |
| reports（含 ignored） | 4,980 | 0.47 GiB | 本地报告与运行结果 |
| artifacts | 198 | 4.47 MiB | 本地产物 |

根目录还存在多个 .tmp_* 目录、tar/tgz、patch、DuckDB 和截图。这些没有被本轮删除；它们属于 cleanup candidate，不属于 FIN 0.1.3 产品基线，后续必须先建立保留/可重建/可删除证据再处置。

### 4.3 明确 archive 的范围很小

仓库中只有 9 个明确 archive 路径：

- archive/README.md
- archive/code/v0_1_retrieval_prototypes 下 README 与 4 个 Python prototype
- scripts/archive/README.md
- scripts/archive/v0_1_free_query/score_sec_agent_free_query_quality.py
- scripts/archive/v0_1_vllm_diagnostics/check_vllm_blackwell_env.py

这意味着“没有放进 archive”绝不能被等同为“当前产品主干”。大量历史资产只是被保留，却没有明确生命周期标签。

## 5. 当前真实代码树

### 5.1 产品执行面

~~~mermaid
flowchart LR
  U["用户 / Reviewer"] --> FE["Workbench frontend<br/>Vite 页面 + legacy static fallback"]
  FE --> API["FastAPI<br/>apps/workbench/backend/app.py"]
  API --> V1["API v1 / application services"]
  V1 --> CR["canonical runtime / facade"]
  V1 --> BE["bounded agent executor"]
  V1 --> LG["langgraph / multi-agent legacy runtime"]
  V1 --> P12["FIN 0.1.2 S2/S3 binding<br/>S4-T06/T07 projection/review"]
  CR --> TOOLS["BM25 / SQL / Graph / MCP / source adapters"]
  TOOLS --> DATA["raw / processed / manifests / indexes / captures"]
~~~

关键事实：

- apps/workbench/backend/app.py 的静态 Python 闭包为 150 个文件，其中 src 119、apps 31。
- 它直接或间接触达 FIN 0.1.2 的 S2/S3 runtime binding、S4-T06/T07 projection/reviewer，以及 src/sec_agent/s4_case_runtime.py。
- 它没有把当前 FIN 0.1.3 S1 SourceHunter / Candidate Pack、S2 co-compilation、S3 dynamic successor 作为一条已切换的产品主链消费。
- Workbench 同时承载新版 Vite surface 和 legacy static fallback；一个进程中仍有多代实现。

### 5.2 FIN 0.1.3 候选能力面

~~~mermaid
flowchart LR
  Q["研究问题"] --> S1["S1<br/>source / query / retrieval / Evidence Pack"]
  S1 --> S2["S2<br/>selected Evidence / NumericFact / model view / local renderer"]
  S2 --> S3["S3<br/>dynamic cells / repair requests / judgment atoms / quality packet"]
  S3 --> CAND["candidate report / assessment"]
  CAND -. "尚未正式 cut over" .-> WB["current Workbench product mainline"]

  S1 --> EV["configs/releases + scripts/releases<br/>tests/contract + docs/worklog"]
  S2 --> EV
  S3 --> EV
~~~

当前阶段真相：

| 阶段 | 已有成果 | 仍未成立 |
| --- | --- | --- |
| S0 | shared control plane、clean/proof 规则和版本治理已形成当前 repair 基础 | 不能把所有历史 proof ceremony 当成未来默认开发流程 |
| S1 | Query Facet、official-first、capture-first、关系方向、本地六案 Evidence Pack、sparse/dense/qrels 诊断均有实质实现 | external official coverage 仍约 4/12；residual valuation/supply 证据、chunk/index 语义和 production Provider 承诺未闭合 |
| S2 | selected Evidence 与 numeric candidate 共编、本地展示/公式/lineage、bounded model consumption 已关闭关键 L1 类问题 | unrestricted full-report autonomy=false；不能宣称模型可自由写全部数字和结构 |
| S3 | dynamic-research successor、information economy、quality packet、小判断原子和 deterministic cell projection 已实现并有零调用证明 | 最新 natural canary failed；完整 repaired report、L1、八维绝对质量、paired、qualified-human、Owner 均未通过 |
| S4 | 历史 0.1.2 Workbench surface 可打开且可审查 | current FIN 0.1.3 candidate 尚未做完整 Workbench dogfood/cutover |
| S5 | 历史 honest-block/release 规则存在 | current FIN 0.1.3 RG1–RG5 和版本收口未执行 |

因此 FIN 0.1.3 新基线的正确状态是 engineering_candidate_at_S3，不是 release_candidate。

## 6. 依赖图与可达性

本轮对 tracked 的 src/apps/scripts Python 做 AST import 图，1,229 个文件全部可解析，无 SyntaxError。结果只代表静态 import；动态加载、配置引用和外部消费者需在未来迁移前单独验证。

| 入口 | 静态可达文件 |
| --- | ---: |
| Workbench FastAPI app | 150 |
| cloud interactive CLI | 20 |
| cloud graph runner | 70 |
| context session CLI | 9 |
| src MCP server | 14 |
| MCP launcher | 15 |
| 上述入口并集 | 161 |
| 未进入并集的 tracked Python | 1,068 |

1,068 个未可达文件不能批量删除，原因包括：

- 一部分是合法的离线 ingestion/index/eval/operator 工具；
- 一部分通过命令行、配置、反射或测试使用，静态 import 看不到；
- 一部分是 FIN 0.1.3 未晋升 candidate；
- 一部分是历史/兼容/一次性 runner；
- 一部分才可能是真正 orphan。

后续 cleanup 应以“产品调用、运维调用、评测调用、历史复现调用”四类 runtime trace 补全静态图，再逐组件决策，不按单文件猜测。

## 7. 证明面为什么压过了产品面

configs/releases 共有 955 个 JSON，均可解析；文件名和字段表明其中大量不是可复用 runtime 配置，而是 execution governance/evidence：

| 观察 | 数量（名称可重叠） |
| --- | ---: |
| authority / admission | 242 |
| decision / disposition | 230 |
| proof / preflight | 181 |
| result / terminal / outcome | 179 |
| plan / policy | 54 |
| manifest / registry | 36 |
| capture / observation | 29 |

常见顶层字段是 status、next_action、recorded_at、authority、observed_counts、known_boundary、decision_id、result_digest、attempt_id 和 admission_id。这些本质上是控制记录和不可变证据，不应与少量真正运行时配置混在同一个 configs/releases 平面。

自 2026-07-19 主干审计 commit 54d2e072 之后：

- 约 12 天新增 3,006 个文件，修改 93 个文件；
- 增加约 1,265,665 行；
- configs/releases 单独增加约 930 个文件和 813,598 行；
- docs/worklog 增加约 629 个文件；
- tests/contract 增加约 547 个文件；
- scripts/releases 增加约 354 个文件。

这说明仓库增长主要来自“每次尝试都新建一套 authority/result/runner/test/worklog”，而不是产品功能按相同比例增长。

## 8. 复杂度热点

以下不是删除名单，而是后续模块化和所有权审计的优先热点：

| 文件 | 约行数 | 风险 |
| --- | ---: | --- |
| apps/workbench/backend/application/bounded_agent_executor.py | 16,761 | 运行、合同、节点编排和修复容易互相牵连 |
| src/sec_agent/langgraph_orchestrator.py | 10,948 | 多代编排逻辑集中 |
| scripts/cloud/sec_agent_interactive.py | 10,806 | CLI/交互承担过多职责 |
| src/sec_agent/multi_agent_runtime.py | 8,970 | 历史和当前 runtime 边界不清 |
| src/sec_agent/memo_llm.py | 8,145 | 写作、合同和 Provider 行为耦合 |
| scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py | 6,318 | 评测 runner 过大，易变成第二套 runtime |
| apps/workbench/backend/application/bounded_agent_contract_policies.py | 5,301 | 合同策略集中且模型 profile 边界难辨 |
| src/sec_agent/multi_agent_contracts.py | 5,239 | 多合同代际共存 |
| src/sec_agent/canonical_runtime/facade.py | 5,100 | canonical facade 已成为高风险枢纽 |

“大文件”不是自动错误，但当前结构使一个字段或阶段修复容易穿透多个层面，是反复回归的重要放大器。

## 9. 文档与状态源问题

当前文档治理原则本来要求：

- Product 文档只管用户目标、范围和产品验收；
- Architecture/TECH 管实现合同；
- Worklog 管执行事实；
- Project OS 管当前恢复锚点。

实际已经发生漂移：

- Product README 仍把 FIN 0.1.2 写为 current plan，把早期 FIN 0.1.3 写成历史，却没有索引当前 repair-closeout FIN 0.1.3。
- PRD、repair plan 和 current_context_pack 都持续追加具体 run/attempt/parser/authority 细节。
- current_context_pack 约 964 KB，capability ledger 约 2.18 MB，root-cause ledger约 2.98 MB；它们是完整历史，却不再是“短上下文包”。
- docs/worklog 有 1,220 个文件；worklog README 自身也已经很难承担导航。

因此，聊天压缩后重复造轮子并不只是模型记忆问题：仓库没有提供一个足够短、唯一、能区分 current/candidate/history 的恢复入口。

## 10. “反复修”的根因复盘

### 10.1 产品主线和 proof 主线分离

大量 candidate 在独立 runner/fake/clean proof 中通过，却没有同步进入 Workbench 产品入口。后续真实产品链第一次消费时，才暴露输入容量、数字展示、身份、日期、证据密度和内容质量问题，于是看起来像“前面明明修好了，为什么又错”。

### 10.2 每个 attempt 被实现成一组新文件

immutable attempt 是正确原则；但项目把它过度实现为新 authority JSON、新 runner、新 test、新 result、新 worklog，而不是“同一通用 runner＋不可变数据记录”。失败越多，代码和配置面越大；后续审计又需要理解更多旧实现。

### 10.3 合同没有单一编译源

Prompt schema、validator、fake provider、local renderer、terminal result 和 Workbench projection 多次各自演化。某处改为五字段、另一处仍请求三字段；某处允许 alias、另一处逐字比较；这类 drift 不是模型推理差，而是项目合同未共编。

### 10.4 金融语义验收太晚

早期大量 gate 证明的是 shape、digest、exact-once、cardinality 和 capture；这些很重要，但不能证明：

- 搜到的是不是研究问题真正需要的材料；
- 同公司同期间的通用段落是否挤掉了具体证据；
- 数字有无正确口径与经济含义；
- 报告是否形成机制、反方、WWC 和决策密度。

直到真实 DELL/MU/NVDA 报告或人工查看 Workbench 时，业务问题才集中暴露。

### 10.5 项目缺陷与 DeepSeek 缺陷经常混合

最近 S3 canary 就是 mixed root cause：项目没有列全 enum/互斥角色/选择规则，DeepSeek 又违反明确数字禁写。过去有时把两者统称“DS 不遵循”，然后继续扩大 Prompt 或增加 validator；这样既没有修合同编译，也容易把 provider-specific 拐杖写进核心 Harness。

### 10.6 阶段边界在执行中被 run ceremony 取代

一个工程修复常被拆成 decision、implementation、clean proof、admission、execution authority、live、audit 七八个资产。安全边界本身有价值，但普通本地确定性修复也沿用同样 ceremony，导致阶段推进被 attempt 流程吞没。用户看到的是大量“继续”，产品看到的却仍是同一个未切换 candidate。

### 10.7 历史真相、当前真相和兼容真相没有分层

旧失败需要保留，旧 digest/path 不能随便移动，这都正确；但“保留”被误读为“继续 active”。同名版本文档、0.1.2 projection、0.1.3 candidate、r53_r60 compatibility 和一次性 release runner 同处一个命名空间，恢复上下文时很容易取错入口。

### 10.8 数据层问题发现晚于模型层修复

Query 编译、chunk 边界、dense index 新鲜度、qrels 语义、SourceHunter 质量、外源候选覆盖等问题，会直接决定模型看见什么。过去多轮先优化 9/12/13 次模型调用，再回头发现 candidate pool 和 Evidence Pack 本身不够好，形成了高成本返工。

## 11. 哪些成果应该保留

本次反思不等于推倒 Harness。以下属于长期金融产品骨架，应保留并收敛：

- capture-first、exact-once、Run/Attempt/Call identity；
- 原始证据与业务晋升分离；
- 公司身份、期间、币种、单位、NumericFact、Formula 和 lineage；
- Evidence Gate、typed gap、cannot-infer 和反方边界；
- provider-neutral SearchIntent / Query Facet；
- 来源权威、关系方向、as-of 和 point-in-time；
- local deterministic renderer 与 L1 硬门；
- 内容质量 rubric、same-input comparison 和 qualified-human acceptance。

需要被收敛的是实现方式：通用 runner、合同 compiler、provider profile、状态存储和产品 cutover 应各有唯一入口；不再为每个字段、每个 attempt 或每个 Provider 复制一套主链。

## 12. FIN 0.1.3 新基线的边界

Owner 若接受本审计，FIN 0.1.3 baseline 应冻结为：

### 纳入基线

- 当前 clean/synced commit 的全部 Git 历史与不可变失败证据；
- current Workbench 作为 inherited product skeleton；
- S1–S3 已证明的 provider-neutral contracts、金融控制面和候选实现；
- 当前私有数据、索引和 capture 的路径级 inventory 与 lineage 要求；
- 最新 S3 failed canary 及 mixed root cause；
- S1 external coverage、S3 content quality、S4 cutover/dogfood、S5 release 作为明确 open items。

### 不冒充已完成

- FIN 0.1.3 已切入 Workbench；
- 三案例动态 Agentic Research 已通过；
- 外源检索已达到生产覆盖；
- DeepSeek unrestricted report autonomy 已通过；
- qualified-human / Owner / release acceptance 已通过；
- 所有未归档 Python 都是 active mainline。

### 暂不做

- 不批量删除或移动 1,068 个未可达 Python 文件；
- 不把 configs/releases 或 docs/worklog 直接搬家，避免破坏 digest/path 引用；
- 不重写历史失败、不清理本机私有数据；
- 不继续 S3 修复，直到 Owner 审阅本基线并批准新的仓库规范与迁移顺序。

## 13. 审阅后应作的四个决策

本节是决策议程，不是已经批准的实施计划。

1. 是否接受“FIN 0.1.3 engineering candidate @ 7cd37388”为新基线，并给它创建明确 tag。
2. 是否先做 repository recovery/cutover program：建立唯一产品 runtime、通用 exact-once runner、合同 compiler 和 evidence store，再恢复 S3。
3. 历史资产采用何种策略：原路径 immutable 保留＋新索引，还是分批迁入 history/evidence store 并保留 redirect/manifest。
4. FIN 0.1.3 收口的产品门是否固定为：三案/扩展案 Evidence Pack → 动态研究 → 高质量报告 → Workbench cutover → qualified-human → S5；不再用“单节点 proof 通过”代替版本推进。

## 14. 审计方法与限制

本轮使用：

- git ls-files、Git history/tags/worktrees/status；
- 路径、文件数、大小和扩展名统计；
- tracked Python AST import 图；
- 现有 repository inventory 的只读重建；
- Workbench/CLI/MCP 稳定入口静态闭包；
- PRD、TECH、Project OS、worklog、release JSON 和旧主干审计交叉核对；
- 本机 ignored 数据只做路径/数量/大小盘点。

限制：

- 静态 import 图不包含反射、字符串动态 import、shell 调用、外部自动化和未运行的配置路由；
- 本轮没有执行 runtime trace、测试、模型或网络；
- “未可达”是复核候选，不是删除结论；
- 本轮不对私有数据内容、凭据值或 Provider SLA 作再验证。

机器摘要见 configs/repository/fin_0_1_3_repository_baseline_v1_0.json。旧的 data/manifests/repository_architecture_inventory_v0_1.json 继续保留为全文件引用原始图，但其 active/reachability 分类不得再直接用于清理决策。
