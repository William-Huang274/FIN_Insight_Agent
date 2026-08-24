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
