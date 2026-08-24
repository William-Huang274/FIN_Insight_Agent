# S1/S2 工作记录 078：DELL not-ready 补源与关系路线修复程序

日期：2026-08-24
状态：`implementation_ready / runtime_root_causes_repaired / direct_capture_pending_clean_commit`

## 1. 用户目标与当前基线

用户授权按以下主线继续 FIN 0.1.3：先修复 S1 内部拥有的检索缺陷并处理 DELL 三个
`not_ready` EvidenceRequest，再让 S2 建设 ASP／units→PVM→产品利润桥；8GB 量化 4B
只作为 development shadow，不得替代来源完备性或正式 S1 资格。

本程序从已独立审计通过的 commit `f8cc99b57e6173d14f9ee9920948ec6e1f431aa6`
及其 append-only 审计记录 `384c2d2a` 开始。原分支已经同步远端；新 release slice
使用 `codex/fin013-dell-s1-s2-product-bridge`。当前 48-Evidence Pack、14 个 residual gap、
历史失败 attempt 与 R17 全部保持不可变。

## 2. 当前事实与纠正

- 14 个 gap 已在 S2 task quantitative result 中完成阶段归属，不重复分类；本轮执行其处置。
- 三个 `not_ready` 请求为价格／配置、Dell 台数、当前双边供应关系。
- `RC-S1-049` 已证明存在 reviewed upstream relationship target，而动态关系路线未召回；
  在该项目内部缺陷关闭前，不得把供应关系空结果解释为公开信息边界。
- S2 v1.5 requested／automatic／derived comparable conflict route 已独立通过；没有新的真实
  反例时，禁止继续堆期间 identity 小修。
- R17 已获得 fresh independent content pass；本程序不创建 R18，也不授予 qualified-human、
  S3、产品、publication 或 release 权限。

## 3. Release slice 与依赖

### Slice A：关系路线最早责任层修复

1. 用现有 DELL current Runtime 和 reviewed relationship target 复现 `RC-S1-049`。
2. 定位最早失败层：关系资产、route compiler、reader、candidate identity、排序或 Evidence Role。
3. 修复最早拥有层；保留 gate 作为回归保护，不以 exact-reader fallback 冒充修复。
4. 加入真实 target、反向关系、错公司、错期间和空关系 mutation。

退出条件：动态路线自然召回已存在的 reviewed target；来源／对象／关系／candidate lineage
可重放；没有通过放宽 authority 或硬编码目标 ID 获得通过。

### Slice B：三个 not-ready 请求的有界补源

1. `REQ::DELL::PRICE_CONFIGURATION::V1`：发行人产品目录、公共采购、渠道配置／报价和可信
   成交区间；不得把 MSRP／单一配置冒充公司 ASP。
2. `REQ::DELL::UNIT_VOLUME::V1`：发行人披露、公共采购、渠道／行业份额代理；不得把行业
   出货增长变成 Dell 台数。
3. `REQ::DELL::SUPPLY_RELATIONSHIP::V1`：Dell 与供应商双方官方披露、当前 delivery／allocation
   或明确时点材料；历史点名或行业供给不得升级成当前双边配额。

每个请求执行预注册的 source route、capture-first、parse/object、candidate decision 与 Evidence
Gate。所有失败必须有 reachability／transport／parse／candidate／admission receipt。只有项目
内部 A/B 类故障排除后，才允许形成公共或商业信息边界。

退出条件：请求变为 `ready`／`research_consumable`，或保持 `not_ready` 但拥有完整的 typed
boundary receipt；Evidence 数量不是目标。

### Slice C：current spine 与 S2 handoff

补源裁决完成后，原子重编 Source→Object→Index→Evidence Pack→Readiness。S2 只消费
精确事实、可审计区间／scenario 或 typed gap，随后建设 ASP／units→PVM→产品收入／利润／
营运资金桥。不可用输入不得由模型或 Harness 反推。

## 4. 实验与资源治理

### 关系／补源程序

- **Hypothesis**：修复已知关系召回缺陷并执行三条任务绑定 source ladder，可减少项目拥有的
  假缺口，并把剩余缺口收敛为有凭据的来源／商业边界。
- **Decision target**：`RC-S1-049` reviewed target 自然进入动态候选；三个请求均有完整 route
  与 decision receipt；无 unjudged material candidate；current lineage 完整。
- **Ceiling**：若目标不在关系资产／source capture／candidate pool，停止下游 reranker，回到
  acquisition／object／route 层。
- **Baseline**：当前 R32 BM25＋Qwen dense、48 Evidence、12 请求中 1 ready／9
  research-consumable／3 not-ready。
- **Leakage guard**：禁止读取 COST、hidden、frozen、holdout、qrel expected outcomes；只用
  DELL current task request 与公开来源。
- **Stop conditions**：来源路线无新增信息且所有 owned failure 已排除；商业数据不可得；或
  candidate ceiling 不支持排序实验。
- **Decision label**：`proceed`，但仅限上述三个请求和 `RC-S1-049`。

### 8GB 量化 4B shadow

量化实验另建 sibling program，不修改冻结的 24GB CUDA／FP16 challenger。它只允许
DELL／MU／NVDA development、同候选池、candidate-ceiling-first、Embedding／Reranker 顺序加载，
且不得晋升 Evidence、NumericFact、current Runtime 或 S1 qualification。正式评分须等待本轮
current snapshot 稳定；在此之前最多做 acquisition／load smoke。

## 5. 验证、审计与停止规则

- 每个 slice 运行定向测试、接缝回放、DELL／MU／NVDA 适用回归、JSON／JSONL、compileall、
  pyflakes、active baseline、Workbench、secret scan 和 `git diff --check`。
- 任何网络、模型或 Provider run 使用全新 attempt ID；失败结果保持不可变。
- 进入自然动态单元或付费 full-chain 前，先运行 Project OS full-chain preflight 与任务级
  TokenBudgetBasis。
- 新实现完成后由全新、作者分离、只读 subagent 审计；它不是 qualified human。
- 单个 DELL 动态单元只算 canary，不授予完整产品验收。

## 6. 当前执行记录

- `git push origin codex/fin013-s1-retrieval-vertical-slice`：成功，远端更新到 `384c2d2a`。
- 新分支：`codex/fin013-dell-s1-s2-product-bridge`。
- 截至本记录创建：0 新网络补源、0 模型／Provider、0 Evidence promotion、0 NumericFact。

## 7. Slice A 实际结果：关系与召回最早责任层

### 7.1 已复现的失败

1. 已知、当前期间内的 NVDA 上游 source object 在原宽查询 BM25 中排名约为
   `666/697`，在全局 `first_stage_limit=64` 前被截断；这不是 reranker 能修的排序问题，
   而是 typed query 的召回面与多 owner 候选联合同一责任层故障。
2. 原 material selection 会把普通 Dell 文本经 BM25／dense 命中后当作
   `counterparty_direct_mention` material complete；关系候选路线未执行，却能形成完成状态，
   属于关系 authority 接缝错误。
3. 非周期 `PUBLIC_WEB` source 在 `fiscal_year=null` 时被财政年度过滤提前排除，即使其
   `publication_date` 位于请求窗口内；这是 date/request eligibility 的最早失败层。

第一次四请求真实诊断因 successor ontology evaluator 仍只接受 v1.3 而以 `KeyError` 终止。
该失败没有写结果、没有模型或网络调用；修复归属 `financial_intent` evaluator，并使用新的
诊断执行重跑，不改写失败事实。

### 7.2 修复

- `query_atom_shadow`：非周期、无 fiscal year 的公开来源改由 publication-date 请求窗口约束；
  周期财报继续使用原财政年度规则。
- `financial_intent`／`query_plan_v3`／`balanced_lexical_recall`：新增 candidate-only grouped
  disclosure surfaces 与正分 BM25；ontology v1.4 覆盖当前 DELL program 的全部 intent。
- `hybrid_candidate_runtime`：新增按 owner 保留候选的 bounded union，以及基于当前 compiled
  object、registered entity alias、显式关系词、原 as-of／owner／period hard filter 的 typed
  relationship graph。它只产生 candidate，不推断边、不授予 Evidence 或 Numeric authority。
- `material_evidence_runtime` 接缝：`counterparty_direct_mention` 必须由同 owner 的 typed
  relationship graph 资格命中后，才能参与 material requirement 完成；BM25／dense 共现不能
  单独完成关系请求。
- `current_runtime_binding`：声明路线与真实执行状态分离；legacy hybrid 只报告 BM25＋dense，
  不再从声明反推 graph 已执行。
- current policy／binding／receipt／registry 以 successor ID 推进到 hybrid v1.6、binding v1.8、
  receipt v1.9、registry R33；`S1_qualification=false`、外部盲测仍为 false。

### 7.3 诊断结果

- 同一已知 NVDA source 的 owner-local BM25 排名改善到约 `5/6`，并自然进入 96-candidate
  owner-balanced union；没有使用 reviewed ID、qrel、COST、hidden 或 holdout。
- 四请求重跑：`4` 请求、`319` unique union candidates、`64` selected、`11` numeric candidate
  facts、`4` typed facts、`17` typed gaps；embedding 批量为 `1`，网络／Provider／generation 为
  `0`。这些仍是 development diagnostic，不是 Evidence Pack。
- 关系专用重跑在当前 source store 中 graph first-stage 为 `0`，material set 不再伪完成；2023
  NVIDIA–Dell 历史页仍被 2025-02-01 至 2026-08-06 请求窗口正确排除。当前状态由“假 ready”
  纠正为“需要当前原文补源”。

定向回归先后通过 `12`、`21`、`16`、`62`、`38` 项；收紧配置读取与辅助函数后，关系／分组
召回／current binding／registry 合并回归再次为 `21 passed`。新增直达补源合同后，直达合同、
旧 ladder runner、关系与分组召回合并回归为 `21 passed`。`git diff --check` 与定向
`compileall` 通过；pyflakes 发现并移除了一个历史遗留的 unused `hashlib` import。

第一次扩展回归为 `113 passed / 1 failed`：冻结的 VS5 successor policy 对
`src/retrieval/financial_intent.py` 保存了 SHA-256，本轮最初直接在该祖先实现上增加 grouped
schema，导致身份测试按设计失败。该失败不是通过更新旧 policy SHA 关闭；祖先
`financial_intent.py` 与 `financial_intent_v2.py` 分别恢复到冻结 SHA
`07fd827c...89cacd` 与 `bf59884c...0b469`，新能力迁入独立 successor
`financial_intent_v3.py`。current query planner 使用 v3；需要调用冻结 v1/v2 evaluator 的 material
接缝只消费显式、candidate-only 的 v1.3→v1.2 projection。重跑相同扩展集合为
`114 passed`，证明历史冻结实验身份和 current successor 能力同时保留。

第一次全仓测试为 `1228 passed / 2 skipped / 5 failed`。五个失败均由本轮 current 版本接缝
拥有：一个 Workbench contract 仍固定期待 registry R32；另外四个 S3 零调用 consumer 绕过
hybrid，直接把 grouped ontology 交给冻结 material compiler。修复为：current registry contract
显式推进到 R33；`ResearchRetrievalService` 在 material compiler／material scope 入口使用同一
v1.3→v1.2 projection，但仍把原 v1.3 ontology 交给 grouped query/hybrid runtime。五个失败用例
定向复跑为 `5 passed`；两条 warning 是既有 SWIG deprecation。全仓终检须在 clean commit 前
再次运行并记录最终总数。最终全仓复跑为 `1233 passed / 2 skipped / 2 warnings`；两个 skip
为既有受限 symlink 场景，两条 warning 仍为既有 SWIG deprecation，无失败。

## 8. Slice B 直达原文补源门

新增 `FIN-0.1.3-S1-DELL-DIRECT-SOURCE-CAPTURE-R1`，它不再扩大 provider 搜索，而是把五个
已人工定位的 HTTPS 原文走现有 capture-first 与 candidate compiler：

1. Principled Technologies 2025 Dell quote／TCO PDF：只用于捆绑报价和可售配置观察，
   禁止称为单机 ASP 或 Dell 公司 ASP。
2. Mississippi IHL 2025 Board Book：公共采购的系统数量、配置与合同总额，只是有界成交／
   部署样本，不是 Dell 公司出货量。
3. CMBI 2026 public research PDF：尝试恢复按品牌 server shipment 图表及其 TrendForce 定义；
   若图表不可解析或底层数据付费，不得伪造 Dell share。
4. Dell 2025 newsroom 与 NVIDIA 2025 official blog：当前双向点名、产品可用／shipping scale；
   可支持当前合作和交付语境，但不得自动升级成私有 allocation 或合同条款。

执行合同记录完整 `TokenBudgetBasis`：`0` provider、`0` model、`0` generation，最多 `5`
original routes、无 retry。每个 direct locator 仍为 locator-only；只有 original capture、
publication-date receipt、source object、exhaustive CandidateDecision 与 Evidence Gate 全部通过后，
才能进入 current Pack。执行器要求 clean worktree、唯一 attempt ID、exclusive-create 私有结果和
public projection；任何 capture／date／parse 失败均原样保留。

本节截至 clean execution 前没有把网页搜索观察写成 Evidence。下一次材料结果必须记录实际
transport、parse、proposal、review 与 admission 数量，而不是按预期宣布“补源完成”。

### 8.1 R1 clean execution、CandidateDecision 与 Evidence Gate

工程基线已冻结在 local commit `ca4adff7`，分支为
`codex/fin013-dell-s1-s2-product-bridge`。该 commit 上最终验证为：全仓
`1233 passed / 2 skipped / 2 existing warnings`，active baseline `213` Python、`8`
frontend、`5` detectors、`28` resources、`0` forbidden，`1017` 个 config JSON 有效，
secret scan `7930` files／`0` findings，`git diff --check` clean。远端 push 与
`git ls-remote` 均遭遇连接 reset，因此只能确认 local commit，不得宣称远端已同步。

clean execution attempt：`fin013-dell-direct-r1-20260824-ca4adff7`。实际结果为：

- `5` 个唯一 locator、恰好 `5` 次网络 attempt、`0` retry、`0` provider、`0` model、
  `0` generation；
- `4` 个 capture／source object、`8` 个 candidate proposal；
- PT、Mississippi IHL、CMBI、NVIDIA 原文成功；Dell newsroom 原 URL 以
  `official_source_http_403` 失败并保留；
- public result digest：`1ed793b4...3592f`；private terminal digest：
  `6a522682...661cd`，terminal SHA-256：`47725c2e...a61`。

exhaustive CandidateDecision 对 `8/8` proposals 给出 disposition：`5` 个接受或替换为
reviewed candidate、`3` 个拒绝、`0` 未裁决，review result digest 为
`d9db1024...d193d`。CMBI Figure 17 另经 PDF 页面渲染与图像复核：图中只明确标出
OEM Others／Self-build 与 ODM Direct／White brand 两个聚合序列，Dell 是无单独数值标签的
灰色堆叠区，不能可靠恢复 Dell share；因此相关 proposal 被拒绝，没有用视觉估读补数字。

Evidence Gate 接受 `5` 条 bounded-context Evidence：Pack 从 `48` 增至 `53`，direct
target-company Evidence 增量为 `0`，exact numeric authority 增量为 `0`。`14` 个 residual
gap 全部保留，`0` gap closed，只把以下 `3` 个 gap 标记为 narrowed：

1. `dell-gap-pricing-asp`：有两套 XE9680＋交换机＋五年支持／部署的 757,231 美元推荐价样本，
   以及四套系统＋交付／安装／培训／五年维护的 2,278,577.28 美元公共采购合同；均不是裸机
   成交 ASP 或 Dell 公司 ASP。
2. `dell-gap-pricing-units`：有单一高校项目四套系统的配置化数量观察；不是 Dell 公司
   shipments、orders 或 share。
3. `dell-gap-supplier-capacity-readthrough`：NVIDIA 官方证明当前 Dell 合作、GB200 shipping
   scale 与案例级交付能力；不证明私有 allocation、合同、公司 server units 或利润转化。

Evidence successor result digest 为 `9c66530d...40d5`；coverage 为
`48 + 5 = 53`、`14 -> 14` gaps。该 gate 只是 internal engineering admission，明确不授予
qualified-human、S1 qualification、publication 或 gap closure。

### 8.2 Dell 403 的 R2 failed-route successor

R1 的 403 不是“官方原文不存在”。同一发行人控制的 Dell Technologies Investor Relations
站提供 2025-03-18 新闻稿官方 PDF：
`https://investors.delltechnologies.com/node/17471/pdf`。本轮新增 successor 合同和执行器：

- digest 绑定 R1 plan、terminal、失败 URL、`official_source_http_403` 与失败 locator；
- 保持四个成功 URL 与 capture 不变，只退休一个失败 URL并加入一个 Dell IR 官方 URL；
- 执行时必须观测 `4` 个 immutable capture reuse 与恰好 `1` 个 fresh network route；
- `0` provider、`0` model、`0` generation、`0` retry；任何绑定或 route delta 改变即停止；
- 新 Dell 原文仍先是 candidate-only，必须另做 exhaustive CandidateDecision 与 Evidence Gate；
  新闻稿的产品／availability 表述不得生成 Dell units、ASP、NVIDIA allocation 或利润权限。

截至本记录，R2 合同与代码已完成定向单测，尚未执行网络 capture；必须在 clean commit 后用新
attempt ID 运行，R1 不得改写或重跑。

R2 随后以 attempt `fin013-dell-direct-r2-20260824-b5ace0f5` 执行：严格观测到 `4` 个
predecessor capture reuse、`1` 个 fresh route、恰好 `1` 次网络 attempt、`0` retry／provider／
model／generation；Dell IR PDF capture 成功，五条路线均形成 source object，合计 `10`
candidate proposals、`0` parse reject、`0` unresolved date。

但在进入 CandidateDecision 前，人工核验发现 material defect：Dell IR PDF 正文标题与 provider
telemetry 均为 `2025-03-18`，编译器却优先选择 PDF `/CreationDate=2026-06-06`。R2 public
result digest `03cbb776...00e54`、private terminal digest `a5b4c1ed...f8fe9` 与全部 raw capture
保持不可变；另建 defect receipt `6eefdf33...3148a`，明确 R2 Dell source object 及两个 proposals
均不可进入 CandidateDecision／Evidence Gate。

根因归属 original-source publication-date adjudication：旧规则只从 PDF 前四页识别数值型
`YYYY-MM-DD`，未识别首屏 `March 18, 2025`，同时把文件生成 metadata 放在更高优先级。修复为：

- PDF 第一页前 1,200 个规范化字符识别英文全称／缩写的 month-name 与数值日期；
- explicit visible header date 的优先级高于文件 `/CreationDate`；
- metadata 与正文候选全部保留在 receipt，provider date 仍只可 corroborate，不能单独授权；
- 新回归固定“可见 2025-03-18、文件创建 2026-06-06”的真实缺陷形态。

定向回归为 `32 passed`。由于 raw response capture 本身有效，后续 R3 不再发网络请求，而是
用新 attempt ID 做 `5` 个 immutable raw captures 的 zero-network compilation replay；必须证明
四个无关 source object digest 不变、Dell source date 纠正为 `2025-03-18`，然后才允许重新进入
CandidateDecision。

第一次 replay attempt `fin013-dell-direct-r3-replay-20260824-1478c9bf` 在写出任何结果前被
`dell_direct_source_compilation_replay_unaffected_source_changed` 保护性断言终止，网络／provider／
model／generation 均为 `0`。逐源只读复现显示，初版 1,200-character header window 过宽：PT
PDF 在字符 309／426／503 出现 research-conclusion 与 AWS price-update 日期，不能当作 publication
date；同时 Mississippi Board Book 标题开头的 `February 20, 2025` 确实比旧的
`/CreationDate=2025-02-19` 更有权威，且 provider telemetry 同为 2025-02-20。

因此不通过放松 unchanged 断言关闭失败，而是：将 PDF explicit-header window 收窄到前 `240`
个规范化字符；登记两项显式 correction（Dell `2026-06-06 -> 2025-03-18`、Mississippi
`2025-02-19 -> 2025-02-20`）；要求 PT、CMBI、NVIDIA 三个 source object digest 保持不变。
preflight finding receipt 为 `d36c10eb...4542d`，successor replay plan v1.1 为
`46405378...d5a6b`。修正后的只读复现已经得到恰好 `2` 个 date/object identity change 与 `3`
个 unchanged digest；正式 zero-network replay 仍须等 clean commit 后使用新 attempt ID。

正式 replay attempt `fin013-dell-direct-r4-replay-20260824-0d31f720` 通过：`5` 个 immutable
raw captures 全部复用，`0` network／provider／model／generation，重新生成 `5` 个 source
objects 与 `10` 个 proposals。delta receipt `b176c98e...8a084` 证明：

- Dell IR：`2026-06-06 -> 2025-03-18`，新 source ID
  `PUBLIC::DELL-EXT::518D98AA635617191E58`；
- Mississippi Board Book：`2025-02-19 -> 2025-02-20`，新 source ID
  `PUBLIC::DELL-EXT::3F7981CD8B953FA5A0E6`；
- PT、CMBI、NVIDIA 三个 source object digest 不变。

R4 exhaustive CandidateDecision 覆盖 `10/10` proposals：`3` 个 replaced、`7` 个 rejected，另有
`1` 个 capture-bound supplemental candidate 用于重建 Board Book 合同总额；最终 `4` 个 reviewed
candidates、`0` unjudged、`0` network/model。两个 Dell candidates 为 issuer
`target_company_exact_fact`，两个 Mississippi candidates 仍为 bounded market context；全部保持
exact numeric authority 为 false。

R4 Evidence Gate 使用 correction successor，而不是在 Pack 中叠加冲突日期：从前序 `53`
Evidence 精确退休 `2` 条旧 Mississippi target/material identity，加入 `2` 条 2025-02-20
replacement 与 `2` 条 2025-03-18 Dell issuer-direct Evidence，得到 `55` Evidence／`55`
materials。旧 source ID 在 successor 中为 `0` 条；两条 Dell item 均为
`accepted_direct_source_evidence`。`14 -> 14` residual gaps、`0` closed，只继续 narrowed
`pricing-asp`、`pricing-units` 与 `supplier-capacity-readthrough`。Pack payload digest 为
`1654b68f...e2a98`，Evidence successor result digest 为 `9ec7bdef...052c9`；仍不授予
qualified-human、S1 qualification、NumericFact 或 publication。
