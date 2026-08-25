# FIN 0.1.3 DELL 信源闭环、模型环节与研报质量执行程序

日期：2026-08-25
状态：`owner_requested_program / execution_plan_documented / implementation_not_started`
规划基线提交：`e80429850212d6246f1feea416e6303ee304ec93`
产品范围：`FIN 0.1.3 / DELL current report successor`
不代表：S1、S2、S3、产品、publication、release 或 qualified-human 通过

## 0. 为什么需要这份程序

产品计划第 7C 节已经确定七步顺序，但此前仍停留在方向层：没有把每一步拆成需求票、精确依赖、
输入输出、工程验收、模型输出质量、最终研报质量、测试、停止条件和责任阶段。Owner 现要求先补齐
这一层，再进入具体实现。

本程序是第 7C 节的技术执行 source-of-truth。它同时消费：

- `docs/product/FIN_0_1_3_CURRENT_BASELINE_AND_S0_TO_S5_CLOSEOUT_PLAN_20260812.zh-CN.md`；
- `docs/eval/FIN_0_1_3_RESEARCH_CONTENT_OUTPUT_QUALITY_RUBRIC_20260806.zh-CN.md`；
- `docs/architecture/retrieval/FIN_0_1_3_DELL_REPORT_BOUNDARY_DENSITY_AND_SOURCE_SUFFICIENCY_AUDIT_20260822.zh-CN.md`；
- `docs/worklog/fin_0_1_3_s3/172_report_source_closure_and_quality_audit_gate_plan.md`；
- Project OS 的 proposition failure provenance、Evidence admission、动态研究、数值权威和报告质量门。

### 0.1 本程序冻结的关键纠正

1. **不承诺把 14 个 gap 全部关闭。** 每项只能在已有候选裁决或完整任务绑定来源梯子留下回执后，
   判为 `closed`、`narrowed`、`open_route_pending`、`proved_information_boundary` 或
   `S3_method_parameter`。没有回执的空结果不是信息边界。
2. **工程、模型节点和最终研报是三套独立质量门。** 工程测试通过不能补偿低质量模型输出；模型
   输出合格不能补偿错误事实、越权来源或不可读引证；报告写得顺畅也不能补偿 L1/L2 失败。
3. **4B embedding 进入混合 challenger，不直接替换 current；reranker 保留。** 当前 8GB GPU 已
   证明 4B Q4_K_M 可 full-offload。4B embedding 在受控池整体优于 0.6B、但 NVDA 回退；4B
   reranker 整体及 MU/NVDA 回退。因此下一轮只允许在同一候选池做分层混合实验，不能按模型大小
   晋升，也不能用 reranker 补偿 candidate ceiling 缺失。
4. **DELL 先形成一个完整、可核验的产品案例。** MU/NVDA 只保留回归和无特判验证，不在本轮把
   DELL 来源闭环扩大成三案完整补源或付费多 Agent live。
5. **human admission 与 qualified-human 产品验收是外部权限。** Codex 可以准备 packet、校验决定
   和物化 successor，但不能冒充 reviewer 签发 16 个 Evidence admission 决定或最终产品接受。

## 1. 当前冻结基线

| 基线对象 | 当前事实 | 本程序如何消费 |
| --- | --- | --- |
| DELL current Pack | `55 Evidence / 14 residual gaps`，`0 closed / 3 narrowed` | 作为 EP1 crosswalk、EP2 admission 和 EP3 residual ladder 的唯一 predecessor |
| current ProductReadiness | 8 个产品请求；`4 blocked_by_evidence_admission`、`3 partial`、`1 ready` | EP2 绑定 private packet digest，不重新挑候选 |
| candidate review packet | 18 个 review item，其中 16 个需 human review | EP2 逐项签发 accept/reject/rebind/defer；禁止自动晋升 |
| task readiness | 12 个请求；11 个 research-consumable；公司级 unit/share 唯一 not-ready | EP4 重算，不把 bundle 或四套采购系统当公司 units/ASP |
| R38 bounded unit | 第一轮 9 个 open gap；15 Evidence、17 NumericFacts | EP1 映射和 EP5 受影响单元选择基线 |
| S2 product bridge | 13 observations、7 derivations、4 open bridge gaps；PVM/profit 为 null | EP4 重编，任何缺权威输入继续 null |
| R17 report | 4 组 remaining gaps，实际引用 10 个 GAP；读者侧仅 EV/GAP | EP1 映射、EP6 非覆盖 successor、EP7 质量审计基线 |
| R17 质量审计 | `P0/P1/P2/P3=0/1/2/1`；engineering PASS_BOUNDED；report OPEN | EP6/EP7 必须关闭 P1、两个 P2；P3 进入可用性优化 |
| 4B shadow | 4B embedding 0.8481 vs 0.6B 0.8228，但 NVDA 回退；4B reranker 0.6962 vs 0.6B 0.7342 | EP3 只做混合候选与独立 reranker bake-off，不晋升既有失败路线 |

### 1.1 14／9／4 的冻结语义

- 14 个 Pack gap 是 S1 Pack 的材料边界全集；
- R38 的 9 个 gap 是该 bounded dynamic unit 实际选择的子集；
- R17 的 4 行是 10 个 GAP ref 的 report-facing 主题聚合；
- S2 另有 `dell-gap-product-profit-attribution`，它不能冒充 Pack gap，也不能被 14／9／4 隐去；
- R17 的 working-capital attribution 在 10 个 report refs 中，但不属于 R38 第一轮 9 个子集。

EP1 必须把这些层级逐项显式化；任何简单把 `14 -> 9 -> 4` 写成 gap 数减少都 fail closed。

## 2. 三轨 Definition of Done

每个 epic 只有在以下三轨都给出独立结果后，才可进入下游。

### 2.1 E 轨：工程、数据与 Evidence 管线

- schema、identity、digest、source/object/index/runtime、CandidateDecision、Evidence Gate、
  NumericFact／Relation、attempt immutable 和 replay 可验证；
- source、candidate、Evidence、estimate、scenario、method parameter 和 proved boundary 权限隔离；
- 所有失败用新 attempt ID 保存，不覆盖历史文件，不通过放宽断言或手工改输出追认成功；
- DELL 改动不得漂移 MU/NVDA 或 holdout predecessor；
- 定向测试、mutation、JSON/JSONL、compileall、静态检查、secret scan、diff check 和阶段性全仓门
  按风险执行。

### 2.2 M 轨：模型与排序节点输出质量

- embedding/reranker 评测先证明 target-in-pool，再评 useful@K、排序、跨案稳定性、资源和时延；
- 动态 Agent 每个节点必须输出公司专属、source-bound、period/unit/role 正确的判断，且不能把候选、
  行业背景、供应商 read-through、bundle、估算或模型记忆写成 Dell exact fact；
- 每个生成节点必须有 task-specific `TokenBudgetBasis`：目的、输入规模、必需输出、schema burden、
  materiality/quality risk、可比运行、reasoning profile、停止／截断行为；
- 模型分析、strict submission、feedback 和本地 validator 的职责分离；Harness 只保护身份、数字、
  引证和边界，不能替模型写研究观点；
- LLM-as-judge 只能 shadow，不能签 Evidence、formal score、product 或 release。

### 2.3 R 轨：最终研报与产品质量

- L1 Financial Truth 和 L2 Evidence Authority 先独立通过；
- 每个核心 Claim 绑定 Evidence／NumericFact／typed gap，读者能看到 publisher、title、source type、
  publication date、reporting/event period、speaker、page/section、URL/locator 和内部 lineage；
- units/share、ASP/mix、PVM、产品利润、营运资金归因、供应分配和需求持续性均按
  fact／estimate／scenario／gap 正确呈现；
- strongest counter-thesis、经过裁决的 cross-cell dependency/conflict 和可执行 WWC 齐全；
- WWC 至少含 metric/event、方向、窗口、阈值或 threshold authority、owner、证据路线和触发后的
  thesis/repair route；
- 八维总分 `>=24/32`，Q1–Q7 无低于 2，Q1/Q2/Q3/Q8 各 `>=3`，至少四维 `>=3`；
- 执行摘要不变成 gap inventory，同一 boundary 只在统一 register 主呈现一次，Facts 密度和重复
  不妨碍 senior reader 继续研究；
- qualified human 对内容价值和最终交付可用性单独接受。

## 3. 依赖图、release slices 与并行边界

```text
P0 计划冻结与基线封存
  -> EP1 14/9/4 crosswalk
       -> EP2 已有候选 Evidence admission -----+
       -> EP3 真实 residual 来源梯子与混合检索 --+-> EP4 Pack/Readiness/S2 重编
                                                       -> EP5 受影响动态单元
                                                            -> EP6 Writer/citation successor
                                                                 -> EP7 双轨审计与 qualified human
```

允许的有限并行：

- EP1 通过后，EP2 与 EP3 的 route program 可以并行；但 EP3 不得为 admission-pending 命题重复抓
  网页，正式 residual 清单必须等待对应 EP2 决定。
- EP6 的 citation schema、DocumentModel fixture 和审计 packet schema 可在 EP3/EP4 期间零调用开发；
  不能提前生成或验收报告内容。
- EP7 的 evaluator protocol 可预注册；reviewer 不得提前看到待冻结 hidden/final labels。
- EP5、EP6 的自然模型执行严格依赖 EP4；不允许用旧 Pack 先跑出稿再补来源。

禁止的并行：

- 运行完整多 Agent 与来源闭环并行；
- Writer 与 S2 bridge 重编并行；
- 作者同时担任 formal report scorer；
- reviewer 在审计 immutable target 时修改同一 target。

## 4. Gate 总表

| Gate | 必须交付 | E 轨 | M 轨 | R 轨 | 当前状态 |
| --- | --- | --- | --- | --- | --- |
| P0 | 本执行程序、基线 manifest、预注册质量协议 | 文档和输入 identity 完整 | 模型预算模板冻结 | 报告 Rubric 与阻断项冻结 | 本文完成后仅 `documented` |
| G1 | 机器可读 14/9/4 crosswalk | 全量、唯一映射、mutation fail | 模型可见 projection 不误导 | 读者能解释 14/9/4 与每项状态 | `not_started` |
| G2 | 4 请求／16 human item admission | 决定有身份、理由、Evidence Gate | 模型不得签决定 | 每个新增来源有实际 claim 用途 | `not_started` |
| G3 | residual source ladder | route/capture/object/candidate/admission 回执 | mixed recall/rerank 有跨案质量证据 | 来源改变／收窄判断，不是网页计数 | `not_started` |
| G4 | successor Pack/Readiness/S2 | 原子晋升、公式、typed null | 模型视图正确分隔 fact/estimate/scenario | 定量桥可复算且不伪精确 | `not_started` |
| G5 | 受影响动态单元 | exact authority、immutable attempts | 节点级内容门通过 | 公司专属判断、反方、WWC 候选可用 | `not_started` |
| G6 | 非覆盖 Writer successor | 引证／数字／引用拓扑可验证 | Writer 无越权、无模板化、无重复堆砌 | L1/L2 通过且具备正式 8D 评分条件 | `not_started` |
| G7 | 双轨审计＋human | engineering/evidence verdict | author-separated model/content audit | report verdict＋qualified-human verdict | `not_started` |

## 5. EP0：程序治理、基线与评测预注册

### DELL-RSQ-00A：执行基线 manifest

- **Owner／阶段**：S0 / Project OS；状态 `planned`；依赖：无。
- **问题与价值**：后续 14/9/4、admission、Pack 和报告必须指向同一 predecessor，防止读取 current
  漂移后仍声称在修 R17。
- **输入**：R17 private full result；R4/current Pack；R38 private full result；ProductReadiness
  v1.7/private packet；S2 product bridge；质量 Rubric；本文。
- **计划输出**：`configs/research/evals/fin_ia_0_1_3_dell_source_report_quality_program_baseline_manifest_v1_0.json`。
- **E 验收**：记录 ref、file SHA-256、canonical result/payload digest、Git blob/commit、case、as-of、
  schema；文件缺失、digest 漂移、R17/R38 身份错配均 fail closed。
- **M 验收**：记录所有未来模型节点为 `not_authorized`，不能因 manifest 存在获得调用权。
- **R 验收**：冻结 R17 P1/P2/P2/P3 和 8D `OPEN/NOT_ASSESSABLE`，不得回填作者 27/32。
- **测试／审计**：正向编译；任一输入 byte mutation；cross-case substitution；missing-private-file；
  dirty-worktree 与 output-collision。
- **停止／回滚**：任何 identity 不一致，P0 停止；修正引用后新 manifest 版本，不覆盖 v1.0。

### DELL-RSQ-00B：质量协议与 reviewer packet 预注册

- **Owner／阶段**：S0+S3 quality governance；依赖：00A。
- **输出**：`configs/research/evals/fin_ia_0_1_3_dell_source_report_quality_evaluation_protocol_v1_0.json`。
- **E 标准**：冻结评测对象、L1/L2 前置、八维阈值、P0–P3、dual verdict、reviewer identity、
  immutable target 和 reason-ref schema。
- **M 标准**：节点质量 reason 必须引用具体 claim/evidence/numeric/gap/WWC；模型自评分不得进入
  formal verdict。
- **R 标准**：成稿必须同时提供 claim-source matrix、14/9/4 crosswalk、numeric bridge、counter、
  WWC、citation appendix 和 final render，缺一项则 `not_assessable`。
- **停止**：正式 candidate 生成后不得为提高分数修改 Rubric；任何修改进入下一 evaluation cycle。

### DELL-RSQ-00C：模型、Provider、网络与 split 权限模板

- **Owner／阶段**：S0 runtime governance；依赖：00A。
- **输出**：每个实际节点独立 authority，不建立可复用的无限 authority。
- **E 标准**：attempt ID、输入 digests、最大逻辑节点、最大 Provider/network 路由、retry/fallback、
  capture-first、exclusive-create、failure disposition 全部显式。
- **M 标准**：每节点 TokenBudgetBasis 完整；valid/test/holdout 隔离；看过 expected label 的实现者
  不得再声称 blind。
- **R 标准**：不得为省 token 静默删掉核心 Evidence、数字桥、反方或 WWC 所需上下文。
- **停止**：预算依据缺任一字段、输入规模尚未物化、或 source ceiling 未过时，禁止模型／付费调用。

## 6. EP1：R17—Pack—dynamic—Writer gap crosswalk

### DELL-RSQ-01A：crosswalk schema 与枚举冻结

- **Owner／阶段**：S1/S2/S3 shared contract；依赖：00A/00B。
- **输入**：14 Pack residual gaps、R38 round-one 9 gaps、R17 4 groups/10 refs、S2 4 bridge gaps。
- **输出**：`src/sec_agent/research/report_gap_crosswalk.py` 中 provider-neutral schema；枚举至少含
  `technical_chain_closed`、`candidate_admission_pending`、`source_route_pending`、`narrowed`、
  `closed`、`proved_information_boundary`、`S2_numeric_or_bridge_gap`、`S3_method_parameter`、
  `not_selected_by_unit`。
- **E 标准**：Pack gap、dynamic gap ref、Writer group、bridge gap 分别有类型；同一 ID 不可跨层偷换。
- **M 标准**：模型可见 projection 只显示研究意义与权限，不暴露 private path/digest，也不能把
  `not_selected` 解释为 closed。
- **R 标准**：读者 projection 用业务名称解释层级，不要求读者理解内部 GAP ID。
- **测试**：枚举、缺字段、重复映射、14→4 假闭合、bridge gap 冒充 Pack gap、unknown ref。

### DELL-RSQ-01B：机器可读 crosswalk materializer

- **Owner／阶段**：S3 report control，S1/S2 提供只读输入；依赖：01A。
- **输出**：
  - private full：`data/workbench_private/fin_0_1_3_report_gap_crosswalk/dell-r1/full_result.json`；
  - public：`configs/research/evals/fin_ia_0_1_3_dell_report_gap_crosswalk_result_v1_0.json`；
  - runner：`scripts/research/materialize_dell_report_gap_crosswalk.py`。
- **E 标准**：14 Pack gaps 全部且只出现一次；9 dynamic facets 全部映射到 14 的子集；R17 10 refs
  全部映射；4 Writer groups 不丢 working-capital；S2 product-profit 独立；状态有依据 ref/digest。
- **M 标准**：输出给后续 Agent 的 compact view 保留 source-vs-method、company-vs-industry、
  exact-vs-estimate 边界。
- **R 标准**：每组包含 `reader_label_zh/en`、current disposition、why it matters、what evidence would
  change it、report placement；不把运营日志塞进报告。
- **测试**：预期 counts `14/9/4/10`；顺序无关 digest；R38 9 以外的 Pack gap不得丢失；R17 ref
  mutation、跨 ticker、同 facet 多义冲突 fail closed。
- **停止**：任何 ref 无法唯一归属时 G1 不通过；不得靠人工备注跳过。

### DELL-RSQ-01C：Workbench／reviewer／reader 三投影与 mutation gate

- **Owner／阶段**：S3/S4 contract；依赖：01B。
- **输出**：内部完整审计投影、模型有界投影、读者简洁 Boundary Register 三种视图。
- **E 标准**：三视图同一 content digest；reader view 隐去敏感 lineage 但保留可核验来源入口。
- **M 标准**：模型不能看到“期望关闭结果”；只能看到当前状态、合法 EvidenceRequest 和 stop 边界。
- **R 标准**：执行摘要最多一条综合不确定性；详细 gap 只在统一 register 主呈现一次。
- **测试**：视图字段白名单、private leakage、重复 boundary、closed 状态无 receipt、PVM null 被隐藏。

**G1 通过条件**：01A–01C 全部通过且独立 reviewer 能从产物解释 14/9/4；这仍不关闭任何 gap。

## 7. EP2：已有候选 Evidence admission

### DELL-RSQ-02A：4 请求／16 human item packet 冻结

- **Owner／阶段**：S1 Evidence admission；依赖：G1。
- **输入**：ProductReadiness v1.7，private packet digest
  `b586c09fc66051afbb434ffe5e357e1b7dbdd4827dc22464381dfb425bc2db32`。
- **范围**：只处理四个 `blocked_by_evidence_admission` 请求：
  - `REQ::e17c40f93e25438950673210` reported results；
  - `REQ::081c06389f9dcb8487886b57` margin/incremental profit；
  - `REQ::273bf40c53d28f49de438b41` cash generation；
  - `REQ::c21c10d6e8f13263cf69ffa5` working-capital risk。
- **输出**：identity-sealed reviewer packet；不复制完整未授权原文到 public artifact。
- **E 标准**：16 个 human-required item 按 ref/digest 唯一；source owner、subject、period、role、route、
  excerpt、license/citation right、requirement alignment 完整。
- **M 标准**：embedding/ranker 分数只作发现顺序，不进入 admission 理由；任何模型建议标
  `advisory_only`。
- **R 标准**：每项写明若接纳将支持／削弱哪个 report claim，若对研报无实质用途可直接 reject，
  防止 citation padding。
- **停止**：packet digest 或 source lineage 漂移；16 项不全；跨公司 context 被标 target fact。

### DELL-RSQ-02B：qualified-human CandidateDecision／Evidence Gate

- **Owner／阶段**：qualified human Evidence reviewer；Codex 仅提供工具与校验；依赖：02A。
- **输入／输出**：每项 `accept_existing/rebind/accept_new/reject/defer`，理由、Evidence Role、claim-use、
  period、polarity、authority、license 与 reviewer identity/time。
- **E 标准**：决定不能由默认值、模型或 Harness 生成；accept_new 必须形成 exact source passage 和
  Evidence Gate；defer 继续阻断，不能算穷尽。
- **M 标准**：无模型签权；如用模型整理 packet，其输出必须与决定字段物理隔离。
- **R 标准**：接纳不是数量目标；只有能改变、支持、反驳或收窄 material claim/gap 的来源才进入
  report source set。
- **停止**：reviewer 未授权、identity 缺失、理由不绑定 request/item、citation right 不足。

### DELL-RSQ-02C：Evidence successor 与原子 predecessor 保护

- **Owner／阶段**：S1；依赖：02B 至少有完整 16-item 决定。
- **复用代码**：`src/retrieval/product_evidence_successor.py`；只做通用 successor，不写 DELL ID patch。
- **输出**：新 private Pack candidate、public result、decision ledger、failure/zero-promotion receipt；
  具体版本在实现时 collision-check 后确定，绝不覆盖 R4/current。
- **E 标准**：candidate 仍不是 Evidence；accepted item 精确进入 Evidence；reject/defer 不进入；MU/NVDA
  保持；old/current Pack immutable；gap 变化必须有 Evidence→facet 规则。
- **M 标准**：新增 Evidence 的模型可见 excerpt 有完整上下文且不超越 admission role。
- **R 标准**：每个新增 Evidence 在 claim-source matrix 中有用途；同源多片段不虚增独立佐证数。
- **测试**：16-item completeness、decision mutation、source digest、role/polarity、duplicate source、
  auto-promotion、cross-case、output collision、current-registry premature write。

### DELL-RSQ-02D：admission 后 readiness delta

- **Owner／阶段**：S1；依赖：02C。
- **输出**：before/after requirement/request states 和 crosswalk delta；不做外源抓取。
- **E 标准**：只重算受影响请求；`blocked` 只能因完整 admission 结果改变；公开数字事实仍由 S2。
- **M 标准**：模型不可把 state transition 当新增事实。
- **R 标准**：说明哪些 R17 claim/gap 真正获得更强来源、哪些没有变化。
- **停止**：Evidence count 增加但 material readiness/claim use 无变化时，记录为 no-material-gain，
  不以数量宣称 G2 成功。

**G2 通过条件**：16 项全部有 qualified-human 决定，物化 successor 可重放；如果 human 尚未完成，
G2 保持 open，但 EP3 可继续处理与这 16 项无重叠的已确认 residual。

## 8. EP3：真实 residual 来源梯子与混合检索／重排

### DELL-RSQ-03A：逐命题 residual route manifest

- **Owner／阶段**：S1 source acquisition；依赖：G1，受 EP2 决定约束。
- **输出**：`configs/retrieval/fin_ia_0_1_3_s1_dell_report_residual_source_ladder_program_v1_0.json`。
- **E 标准**：每个 residual 记录 local data/object/index/SQL、official issuer/regulator、named customer、
  named supplier、industry primary、product/procurement/deployment、trusted context/counter route；search
  只作为 locator；每条 route 有 max attempts、capture policy、fallback 和 stop。
- **M 标准**：每条查询声明 target proposition、subject、owner、time、source role 和 forbidden inference；
  不用答案 URL/qrel 写入 query。
- **R 标准**：路线按 report materiality 排序：units/share、ASP/mix/PVM/profit/WC、demand durability、
  Dell-specific supply allocation 优先；valuation/price-in 只有产品范围确认后执行。
- **停止**：仍为 admission pending、非当前研报 material、或属于 S3 threshold 的项不得进入抓取。

### DELL-RSQ-03B：内部链、候选 ceiling 与路线真实性

- **Owner／阶段**：S1 retrieval；依赖：03A。
- **输入**：current source/object/index、SQL/NumericFact、BM25、0.6B dense、typed relationship graph。
- **E 标准**：逐 route 记录 source exists、object exists、index membership、query execution、target-in-pool、
  rank、candidate decision state；索引／绑定故障留在 S1 修。
- **M 标准**：先看 target-in-pool/semantic-equivalent coverage；target 不在池时停止 reranker 实验。
- **R 标准**：候选与 report proposition 有明确 claim-use；泛行业同义文本不算 Dell 材料覆盖。
- **指标**：material-group target-in-pool、useful@10、source-role precision、subject/period correctness、
  duplicate-source-adjusted coverage；不以总候选数作成功指标。
- **测试**：已知 reviewed target、反向关系、错公司、错期间、同源重复、空图、stale index、SQL
  authoritative fact 已存在但 narrative 未召回。

### DELL-RSQ-03C：外部原文 capture-first 梯子

- **Owner／阶段**：S1 acquisition/parser；依赖：03A/03B ceiling 处置。
- **输出**：每个 attempt 的 route receipt、raw capture、source object、parse/date/locator receipt、candidate
  proposal；public 只投影无敏感内容的摘要。
- **E 标准**：PIT/as-of、publisher、title、speaker、publication date、reporting/event period、page/section、
  URL/locator、license/citation/redistribution rights；HTML/PDF/OCR/table 原文坐标可重放。
- **M 标准**：若用模型做 OCR/抽取，必须 advisory、source-span-bound、逐字段可回原文；模型摘要不能
  成 Evidence。
- **R 标准**：来源层级与 claim-use 匹配；供应商可证明其自身供给背景，但没有关系边时不能证明
  Dell allocation；采购/bundle 不能证明公司 ASP/units。
- **停止**：transport/403、parser/date 冲突、付费墙或 license 不足均形成 typed receipt；不得改写为
  public-information gap。

### DELL-RSQ-03D：4B embedding 混合方案与 reranker bake-off

- **Owner／阶段**：S1 ranking experiment；依赖：03B candidate ceiling；不依赖报告写作。
- **基线／challenger**：
  1. BM25＋typed graph＋current 0.6B dense union；
  2. BM25＋typed graph＋0.6B dense＋4B Q4_K_M dense union；
  3. 对同一冻结候选池分别使用 deterministic financial rerank、current 0.6B reranker、预注册的
     alternative reranker challenger；历史 4B Q4_K_M reranker 保留失败参考，不自动重跑或晋升。
- **混合原则**：4B 可作为额外 semantic recall lane；0.6B 不因 4B 整体均值较高而删除。是否保留
  4B-only candidate 由 label-free union 规则决定，最终排序由独立 reranker/financial rules 决定，
  避免 embedding 同时当召回器和裁判。
- **E 标准**：同对象、同 query、同候选池、同 split、tokenizer/truncation/full-offload receipt；8GB
  串行加载；CPU learned fallback 为 0；valid/test 分离，冻结 test 不调参。
- **M 标准**：DELL/MU/NVDA 各案不得 material regression；不仅看 pairwise，还看 material-group
  target-in-pool、useful@K、top-k source-role precision、错公司/错期间率和 hard-negative 处理。
- **R 标准**：challenger 只有在能带来新 admission-worthy、report-material Evidence 或明显减少
  false context 时才有产品增益；排序分数本身不关闭任何 gap。
- **资源门**：记录 VRAM、latency、throughput、输入 token、truncation、模型/工具 identity；资源只作
  可运营性约束，不覆盖质量。
- **停止**：candidate ceiling 未过；任一关键 case 回退；4B-only 增量全是无关 context；reranker
  未达预注册 floor；资源不可接受。失败保留并继续 current 0.6B，不做无限模型搜寻。

### DELL-RSQ-03E：residual CandidateDecision、Evidence Gate 与 GapEligibility

- **Owner／阶段**：S1 Evidence；依赖：03C，03D 只在确有排序价值时消费。
- **E 标准**：所有 material proposals 100% judged；Evidence Role、support/limit/counter、source strength、
  subject、period、relationship direction、license 和 dedupe 完整；accepted 才进 successor Pack。
- **M 标准**：模型可提出候选角色但无签权；抽取内容必须 exact-span 可核验。
- **R 标准**：每个 route 结论写成 `closed/narrowed/open/route_exhausted/proved_boundary`，并说明对 thesis、
  bridge、counter、WWC 或 limitation 的实际影响。
- **proved boundary 最低条件**：local chain、reachable official/external routes、candidate/admission、
  non-disclosure/commercial boundary 全有回执；预算耗尽、工具失败、未审候选都不合格。
- **停止**：存在 unjudged material candidate 或未执行 mandatory route 时，禁止 proved boundary。

**G3 通过条件**：每个 report-material residual 都有完整路径回执和可审计状态；不要求全部 closed。

## 9. EP4：Pack、Readiness 与 S2 产品价值桥重编

### DELL-RSQ-04A：append-only Pack successor 与 current 原子晋升

- **Owner／阶段**：S1；依赖：G2/G3 的已完成部分。
- **E 标准**：完整 predecessor chain、accepted Evidence、retired replacement、anchor、readiness、policy、
  receipt、registry 一次原子提交；写前 exact predecessor 和所有 final/tmp collision guard；MU/NVDA/
  holdout digests 不变。
- **M 标准**：每条新 Evidence 的模型可见 anchor 与 admission role 一致；未接纳候选不可渗入。
- **R 标准**：crosswalk status 随 Pack 更新；Evidence 数增加但 gap 不变时照实呈现。
- **停止**：partial current、registry 回退、anchor 无 exact span、cross-case drift。

### DELL-RSQ-04B：CoverageState 与两种 readiness 重算

- **Owner／阶段**：S1；依赖：04A。
- **输出**：current ProductReadiness 与 12-request task readiness 的新 versioned successor。
- **E 标准**：source access、candidate coverage、retrieval quality、Evidence admission、numeric/bridge
  authority、S3 consumption 分账；两个 readiness 用途不互相冒充。
- **M 标准**：模型收到 actionable state 和下一合法 action，不收到“缺资料=不存在”的错误提示。
- **R 标准**：units/share 等 material not-ready 继续阻断相应精确结论；research-consumable 只表示可在
  明确边界下研究。
- **停止**：仅因新网页数量或 candidate count 将请求标 ready。

### DELL-RSQ-04C：S2 units/share—ASP/mix—PVM—profit—WC bridge

- **Owner／阶段**：S2 numeric authority；依赖：04A/04B。
- **复用／扩展**：`src/sec_agent/research/product_value_bridge.py` 与 source-bound fact executor；所有
  Decimal 操作继续 `localcontext()`。
- **输入类型**：reported exact facts、admitted company/industry observations、可审计区间、research
  estimate、scenario assumptions、typed gap/conflict；类型不得互换。
- **E 标准**：period/unit/entity/formula lineage；PVM identity 可复算；units×ASP 与 revenue reconciliation；
  profit bridge 的 revenue/cost/opex attribution；WC 的 AR/inventory/AP/cash 与 AI attribution边界；
  输入缺失时字段必须 null 且带 gap，不用模型补数。
- **M 标准**：S2 是确定性权威，模型只能解释 bridge 或提出 scenario，不得创建 NumericFact、选择
  冲突事实或把 bundle/sample 当公司输入。
- **R 标准**：报告明确区分 exact/estimate/scenario；PVM/profit/WC 若可算，给公式、假设、区间和
  sensitivity；若不可算，给经济含义和下一证据路线，而不是空泛“未披露”。
- **测试**：same-period、unit scale、flow/stock、PIT、conflict propagation、null invariant、bundle÷units
  禁止、行业 share→Dell units 越权、profit attribution、WC proxy、Decimal isolation。

### DELL-RSQ-04D：model-visible / report-visible bridge projection

- **Owner／阶段**：S2→S3 seam；依赖：04C。
- **E 标准**：projection 绑定完整 bridge digest；observations、derivations、assumptions、null gaps 分区；
  authority 字段不可由 Writer 修改。
- **M 标准**：动态 Agent 能说明数字意味着什么、不能说明什么，并在引用 exact number 时选择结构化
  ref；禁止把 scenario 语言写成 reported result。
- **R 标准**：形成 reader-ready bridge table 与 source footnotes；无权威的列显示“不可计算＋原因”，
  不显示假 0 或空白。

**G4 通过条件**：Pack/Readiness/S2/crosswalk 全部 current-consistent；只有 readiness 指定的受影响
单元可进入 EP5。G4 不等于 S2 stage qualification。

## 10. EP5：只运行受影响的 DELL 动态单元

### DELL-RSQ-05A：affected-cell resolver 与 scope authority

- **Owner／阶段**：S3 control plane；依赖：G4。
- **默认候选单元**：Demand、Supply、Value Capture、Cash；Lead 只在至少两个单元需要裁决时启动。
  Operating 若只有确定性事实刷新则不自然重跑。
- **E 标准**：由 Evidence/bridge/crosswalk delta 计算 affected set；未变化节点按 digest 复用；每个节点
  新 run/attempt/authority；不得直接重跑完整多 Agent。
- **M/R 标准**：每个被启动节点必须对应一个会影响 thesis、bridge、counter、WWC 或 boundary 的
  material delta；没有信息增量则不为“多 Agent 感”调用模型。

### DELL-RSQ-05B：逐节点模型输出合同与 TokenBudgetBasis

- **Owner／阶段**：S3 runtime；依赖：05A。
- **共同输出合同**：thesis、mechanism、support、limit、counter、confidence、remaining gap、WWC
  candidate、selected Evidence/Numeric/Relation refs、next action；所有自由 prose 禁止自带未绑定数字/
  日期/引用。
- **Demand 质量**：区分 orders、backlog、shipment、revenue；同季信号不是 cohort conversion；明确
  cancellation、pull-forward、digestion、customer concentration 与 duration evidence。
- **Supply 质量**：区分 supplier-owned capacity signal、Dell relationship 与 Dell-specific allocation；
  行业产能/良率/HBM read-through 不得变成 Dell units/profit。
- **Value 质量**：区分 reported AI revenue、ISG/company margin、ASP/units/mix、PVM 和 product profit；
  typed null 不得被机制文字绕过。
- **Cash 质量**：公司 AR/inventory/AP/cash facts 与 AI product attribution 分离；方向性 proxy 不得写成
  measured AI cash absorption。
- **Lead 质量**：检查跨单元事实存在性、冲突、dependency、strongest counter 和不确定性；不得把
  “某 cell 未见”升级成“全 case 不存在”。
- **预算门**：每节点依据实际 context bytes/tokens、输出字段和历史可比运行设置，不在计划阶段拍脑袋
  固定 token 数；reasoning exhaustion 或 visible output=0 为 terminal failure，不静默续费。

### DELL-RSQ-05C：bounded natural run

- **Owner／阶段**：S3；依赖：05B 零调用/mutation 全过和 fresh authority。
- **E 标准**：capture-first；analysis/submission 分开；strict schema；0 未授权 retry/fallback；每次
  EvidenceRequest/Response、FeedbackReceipt、PlanDelta、GraphDelta、StopDecision 可重放。
- **M 标准**：自然输出逐节点达到 05B；generic/ticker-swappable、source listing、gap listing 或只复述
  bridge 状态均失败。
- **R 标准**：节点输出形成可用于报告的公司专属判断，不直接等同最终段落；至少说明经营、利润、
  现金或估值含义之一。
- **停止**：schema/authority/quality failure 保留 terminal；修最早责任层后 fresh attempt。一个节点失败
  不自动重跑已通过节点，也不自动扩大到完整多 Agent。

### DELL-RSQ-05D：反馈、局部再裁决与合法停止

- **Owner／阶段**：S3 controller；依赖：05C。
- **E 标准**：反馈明确归 S1/S2/S3；已有来源漏召回回 S1，数值/bridge 回 S2，研究判断/WWC 回 S3；
  closed node 只在业务 payload 和原模型可见 context digest 一致时复用。
- **M 标准**：feedback 必须改变计划、置信度、claim、counter 或 stop reason；原文复述不算消费。
- **R 标准**：`stop_sufficient` 只在 material coverage 充分时成立；否则使用 `stop_no_progress`、
  `blocked_by_admission`、`route_exhausted` 等真实状态。

### DELL-RSQ-05E：节点级内容质量验收

- **Owner／阶段**：author-separated content reviewer；依赖：05C/05D。
- **E 标准**：exact refs、lineage、numeric authority、context digest、attempt immutable。
- **M 标准**：逐节点检查 Q1–Q7 的适用维度、事实遗漏、因果越权、反方强度、generic language、
  false absence 和跨 cell leakage；reason refs 指向具体输出。
- **R 标准**：只有通过节点可进入 Writer packet；失败节点保持其旧合法结论或显式 gap，不由 Writer
  自行修复。

**G5 通过条件**：受影响节点全部有有效输出或合法停止，且 author-separated node audit 无 material
finding；这仍不代表完整报告通过。

## 11. EP6：非覆盖 Writer successor、可读引证与交付质量

### DELL-RSQ-06A：reader citation / source appendix 合同

- **Owner／阶段**：S3 report authority + S4 delivery；依赖：G1，可提前零调用实现。
- **输出 schema**：每个 citation 至少包含 `citation_id`、publisher、title、source_type、speaker、
  publication_date、reporting_period/event_date、page/section/subsection、URL/locator、source tier、
  claim-use、citation/redistribution rights、EV/NUM lineage。
- **E 标准**：citation 从 admitted source/Numeric authority 确定性编译；同源聚合不丢 page/section；
  internal EV/GAP 仍保留但不作为唯一 reader surface。
- **M 标准**：Writer 只选择 refs，不生成 URL、标题或日期；未知 metadata fail closed。
- **R 标准**：正文脚注、Sources drawer 和 appendix 可相互定位；读者不访问 private artifact 也能识别
  来源。无 citation right 的材料不得伪装成可公开链接。
- **测试**：missing title/date/period/locator、speaker mismatch、source duplicate、URL substitution、
  claim-source mismatch、WWC Facts 无来源。

### DELL-RSQ-06B：DeliverableBrief、BilingualStylePack、VisualRequest、DocumentModel

- **Owner／阶段**：S3/S4；依赖：06A、G4、G5。
- **E 标准**：四类合同独立 versioned；DocumentModel 只消费 verifier-bound 内容；VisualRequest 的每个
  图表点绑定 NumericFact/derived formula/scenario，不从 prose 抽数字。
- **M 标准**：中英双语保持事实、期间、置信度和 limitation 等价；模型不能为了文风改变 thesis、
  数字、ref 或 gap 状态。
- **R 标准**：交付结构至少含 executive thesis、business/financial drivers、numeric bridge、
  counter-thesis、WWC、Boundary Register、source appendix；图表只有在比文字更清晰时使用。
- **停止**：无权威数据的图表请求、双语语义漂移、布局遮挡 limitation、内部运行日志进入客户报告。

### DELL-RSQ-06C：新 Writer successor

- **Owner／阶段**：S3 Writer；依赖：06A/06B/G5；新 run ID，不覆盖 R17。
- **输入**：通过的节点输出、current crosswalk、S2 bridge、citation catalog、quality feedback；禁止使用
  rejected candidate、旧 stale evaluator finding 或模型记忆。
- **E 标准**：protected identity/date/numeric/citation surfaces 由 Harness render；Writer refs 必须在
  allowed set；remaining gaps 与 crosswalk 一致；R17/private/history immutable。
- **M 标准**：公司专属 thesis；解释证据为何支持/削弱；有机制、替代解释和跨 cell 裁决；不输出
  模板化 research memo，不靠重复 Facts 填充；遇到 null 只能解释边界或场景，不能补造值。
- **R 标准**：关闭 R17 的 citation P1；14/9/4 P2；WWC P2；优化重复/Facts density P3。报告至少有
  strongest counter、一个可执行 WWC 和一个实质 numeric bridge；同一 gap 只主呈现一次。
- **停止**：finish_reason length、可见输出 0、无合法 Tool call、hard reference/authority finding、L1/L2
  failure、无新增产品价值。失败保持 immutable，不手工 salvage 为成功。

### DELL-RSQ-06D：deterministic renderer、citation drawer 与 verifier

- **Owner／阶段**：S3/S4；依赖：06C。
- **E 标准**：rendered Markdown/HTML、citation drawer、numeric table、crosswalk、WWC register 与 source
  appendix 同一 DocumentModel digest；链接、脚注、表格和双语切换可用；raw/private 不泄露。
- **M 标准**：renderer 不改模型观点，只负责保护表面和布局；检测 Writer 文本与结构化 refs 冲突。
- **R 标准**：senior reader 能在不读 JSON 的情况下回答：结论是什么、为什么、数字桥是什么、最强
  反方是什么、什么会改变结论、哪些仍未知、去哪里核验。
- **测试**：render snapshot、broken link/footnote、duplicate boundary、citation drawer completeness、
  mobile/desktop 可读性、中文/英文数字和含义一致。

### DELL-RSQ-06E：formal scoring 前置 packet

- **Owner／阶段**：S3 quality；依赖：06D。
- **E 标准**：candidate seal、L1/L2 results、claim-source matrix、numeric audit、gap crosswalk、WWC、
  final render、comparison baseline 全齐。
- **M 标准**：不向作者或 scorer 暴露 hidden expected outcome；模型 shadow score 与正式区域隔离。
- **R 标准**：只有 L1/L2 PASS 才进入 8D；没有完整 current report 时 verdict 为 `not_assessable`。

**G6 通过条件**：新 candidate 非覆盖生成、L1/L2 通过、reader citations 可核验、具备正式 8D packet；
G6 不授予 qualified-human 或 publication。

## 12. EP7：作者分离双轨审计、qualified human 与关闭决策

### DELL-RSQ-07A：immutable candidate seal

- **Owner／阶段**：S0 audit control；依赖：G6。
- **输出**：commit/tree、private/public/rendered artifact SHA、canonical digest、implementation refs、测试
  refs、reviewer packet digest；审计开始时 worktree 状态。
- **停止**：审计中 target 变化立即作废，重建新 seal；不得在同一 target 上边审边改。

### DELL-RSQ-07B：engineering and Evidence pipeline audit

- **Owner／阶段**：fresh author-separated read-only reviewer；依赖：07A。
- **范围**：source/object/index/runtime、candidate/Evidence、numeric/bridge、crosswalk、citation compiler、
  immutable attempt、tests、secrets、Git hygiene。
- **输出**：`engineering_and_evidence_pipeline_verdict` 与 P0–P3 findings。
- **边界**：PASS 只证明工程/Evidence，不得自动写 report/product PASS。

### DELL-RSQ-07C：report research-quality audit

- **Owner／阶段**：fresh author-separated content reviewer；可与 07B 是不同 reviewer；依赖：07A。
- **范围**：逐 Claim source/authority、14/9/4、L1/L2、units/ASP/PVM/profit/WC、因果边界、counter、WWC、
  citation/source appendix、八维、双语与最终 render。
- **输出**：`report_research_quality_verdict`、P0–P3、Q1–Q8 分数与逐维 reason refs、paired gain。
- **通过**：满足本程序 2.3 和冻结 Rubric；material finding 必须回最早责任 stage，不能让 reviewer
  直接改稿。
- **边界**：author-separated Agent 可签内容审计，不能冒充 qualified human。

### DELL-RSQ-07D：qualified-human product acceptance

- **Owner／阶段**：qualified human；依赖：07B/07C PASS。
- **输出**：独立 `qualified_human_product_verdict`，评价继续研究/复核价值、事实可核验性、交付可用性、
  unresolved boundaries 是否诚实和是否可进入下一产品门。
- **停止**：身份/资格未记录、只看总分、不看 final render、以“Agent 已审过”代替人工。

### DELL-RSQ-07E：closeout、repair 或 release handoff

- **Owner／阶段**：Owner + S0–S5 governance；依赖：07B–07D。
- **PASS 路径**：更新 current context、capability/root-cause/worklog、产品计划和 checklist；再单独讨论
  S3/S4/S5，不由本程序自动授予 release。
- **FAIL 路径**：按 finding 归 S1/S2/S3/S4，保留失败 target，开新 attempt；只有产品范围/兼容性变化
  才讨论新产品版本，不因审计失败开 FIN 0.1.4。

## 13. 逐 ticket 责任与状态索引

| Ticket | Owner | 依赖 | 交付形态 | 当前状态 |
| --- | --- | --- | --- | --- |
| 00A | S0/Project OS | 无 | baseline manifest | planned |
| 00B | S0+S3 quality | 00A | evaluation protocol | planned |
| 00C | S0 runtime governance | 00A | per-node authority template | planned |
| 01A | S1/S2/S3 contract | 00A/00B | crosswalk schema | planned |
| 01B | S3 control | 01A | private/public crosswalk | planned |
| 01C | S3/S4 | 01B | three projections | planned |
| 02A | S1 | G1 | sealed 4-request/16-item packet | planned |
| 02B | qualified human | 02A | item decisions | external_pending |
| 02C | S1 | 02B | Evidence successor | blocked_by_02B |
| 02D | S1 | 02C | readiness delta | blocked_by_02C |
| 03A | S1 acquisition | G1 | residual route manifest | planned |
| 03B | S1 retrieval | 03A | local/ceiling receipts | planned |
| 03C | S1 parser/acquisition | 03A/03B | capture/source/candidate | planned |
| 03D | S1 ranking | 03B | mixed embedding/reranker eval | conditional_planned |
| 03E | S1 Evidence | 03C/(03D) | decisions/gap receipts | planned |
| 04A | S1 | G2/G3 | current Pack successor | blocked_by_upstream |
| 04B | S1 | 04A | current readiness | blocked_by_04A |
| 04C | S2 | 04A/04B | numeric/product bridge | blocked_by_04B |
| 04D | S2→S3 | 04C | model/report projection | blocked_by_04C |
| 05A | S3 control | G4 | affected-cell scope | blocked_by_G4 |
| 05B | S3 runtime | 05A | node contracts/budgets | blocked_by_05A |
| 05C | S3 model runtime | 05B | natural outputs | blocked_by_05B |
| 05D | S3 controller | 05C | feedback/readjudication | blocked_by_05C |
| 05E | independent reviewer | 05C/05D | node quality verdict | blocked_by_05C |
| 06A | S3/S4 | G1 | citation/source appendix contract | planned_after_G1 |
| 06B | S3/S4 | 06A/G4/G5 | delivery contracts | blocked_by_upstream |
| 06C | S3 Writer | 06A/06B/G5 | non-overwrite successor | blocked_by_upstream |
| 06D | S3/S4 | 06C | final render/verifier | blocked_by_06C |
| 06E | S3 quality | 06D | formal packet | blocked_by_06D |
| 07A | S0 audit | G6 | immutable seal | blocked_by_G6 |
| 07B | fresh reviewer | 07A | engineering/Evidence verdict | blocked_by_07A |
| 07C | fresh reviewer | 07A | report/8D verdict | blocked_by_07A |
| 07D | qualified human | 07B/07C | product verdict | external_blocked_by_audits |
| 07E | Owner/S0–S5 | 07B–07D | closeout/repair decision | blocked_by_upstream |

## 14. 实现顺序与当前下一张票

计划完成后，具体实现严格从以下顺序开始：

1. `00A -> 00B -> 01A -> 01B -> 01C`：先把 14/9/4 和质量协议做成机器合同；
2. `02A` 冻结 admission packet，同时启动 `03A` residual route manifest；
3. 人工 02B 未完成时，可做 03B 和无重叠 residual 的 03C，不得做 02C；
4. candidate ceiling 证明有意义后才执行 03D 混合 embedding/reranker；
5. 02/03 都形成决定后进入 EP4；EP4 前不运行动态 Agent；
6. G4 后只跑 affected cells；G5 后才生成 Writer successor；
7. 最后按 07A–07D 做干净、作者分离审计与人工验收。

当前第一张可实施票为 `DELL-RSQ-00A`；当前没有 Runtime、来源网络、embedding/reranker、模型、
Provider、动态 Agent 或 Writer 执行权。

## 15. 本计划本身的验收

本计划只有同时满足以下条件，才记为 `program_documented`：

- 七项全部拆成可跟踪 ticket；
- 每票有 owner、依赖、输入/输出、E/M/R 质量门、测试和停止条件；
- 4B embedding 混合路线与 reranker 都被保留，且受 candidate-ceiling/no-case-regression 约束；
- 4 请求/16 human item、14/9/4、S2 四桥 gap、R17 P1/P2/P2/P3 均进入计划；
- 模型各环节与最终研报质量分别验收，不用工程门代替；
- 双轨独立审计和 qualified-human 权限分离；
- 明确本计划不等于实现、补源、报告或阶段通过。
