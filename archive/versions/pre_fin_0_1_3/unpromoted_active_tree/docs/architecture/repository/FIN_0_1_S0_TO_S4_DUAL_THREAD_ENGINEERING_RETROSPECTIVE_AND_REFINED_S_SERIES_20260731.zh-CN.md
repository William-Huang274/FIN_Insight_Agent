# FIN 0.1 S0–S4 双任务工程复盘与 S 系列重构建议

日期：2026-07-31
状态：`read_only_audit_complete / refined_S_series_accepted_for_FIN_0_1_2_planning`

## 1. 结论

FIN 0.1 第一轮 S0–S4 的主要问题，不是“DeepSeek 不够强”这一条，也不是某个 Validator 很难修。真正的问题是：

1. 自然模型能力、跨层合同编译、确定性事实所有权、proof harness、产品验收和 release engineering 没有在阶段入口前分开；
2. fake/full-fake 证明了理想输入下的代码路径，却没有尽早证明自然模型在真实最大候选数、自然日期、跨案例诱饵和长上下文下的能力边界；
3. exact-live 同时承担了产品证明和集成缺陷发现，fail-fast 每次只暴露最早一个问题；
4. 每个局部判断又被拆成新的 scope、authority、admission、proof、result、disposition 和 worklog，治理对象增长速度超过了产品能力增长速度；
5. 阶段退出规则写过多次，但没有由统一的机器预算和固定状态机强制执行，因此“这次以后不再进入下一轮”常被新的命名或新的合同家族绕开；
6. 仓库从一开始没有按可回滚 slice 收敛，导致历史证据、当前实现、状态账本和未来计划长期堆在同一 index。

正确改法不是放松金融 L1，也不是减少必要审计，而是把 S0–S5 保留为产品证明的宏观节奏，同时使用一套固定、有限的工程子门禁；将模型输出限制为判断原子和 request-local alias；把跨层合同、事实表面和 failure capture 提前到 S0–S2；把正式 live 恢复为产品证明，而不是逐字段 debugger。

## 2. 审计证据

### 2.1 双任务记录

本次通过 Codex task API 读取并分页到历史末尾：

- 当前任务：`019f91b7-662a-7f31-b71d-eb90d2ec32c2`；
- 相邻任务：`019f54fe-4b90-74c0-b5e7-6325c47b77ce`。

只提取工程模式和统计，不复制私密对话正文，不把聊天摘要当产品验收证据。

| 指标 | 当前 S 系列任务 | 相邻 Point01/Point02 任务 |
| --- | ---: | ---: |
| 已读取 turns | 199 | 135 |
| user-message items | 198 | 136 |
| final-answer items | 190 | 129 |
| context compactions | 121 | 59 |
| file-change events | 2,055 | 1,246 |
| completed / interrupted turns | 194 / 3 | 131 / 4 |

这些计数不是独立文件数，也不是质量分数；它们说明两个任务都经历了非常高的协调与状态维护成本。

### 2.2 当前仓库快照

审计时分支为 `codex/layered-data-source-expansion`，HEAD=`54d2e072b30d51cd7aaa3b55288d186782853a97`，相对 origin ahead 5。

| 指标 | 数值 |
| --- | ---: |
| Git status rows | 1,118 |
| staged / unstaged / untracked | 799 / 28 / 317 |
| S0–S4 release JSON | 376 |
| S0–S4 contract-test files | 255 |
| S0–S4 product-strategy worklogs | 261 |
| S4-T05 release JSON / tests / worklogs | 74 / 53 / 39 |
| S4-T06 release JSON / tests / worklogs | 92 / 68 / 66 |

T05 文件名覆盖 R2–R11，T06 覆盖 R1–R7。T05/T06 的 release JSON 中，exact/live、admission/authority、proof、root-cause/disposition 占了大部分。这是“治理表面膨胀”而不是“产品功能同等增长”。

## 3. S0–S4 实际成果与缺口

| 阶段 | 真实成果 | 被低估或遗漏的缺口 | 新归属 |
| --- | --- | --- | --- |
| S0 Foundation | canonical Case/Run/Artifact、权限/回滚、PRD 与 release ladder | contract compiler、完整 capture、provider capability envelope、可回滚 Git slice 未成为入口硬条件 | FIN 0.1.2 S0 |
| S1 One-cell fixture | Workbench→Runtime→Trace/Artifact 主链、失败终态、fixture cell | fake Provider 过于配合；没有真实最大候选数、自然日期、跨案污染、排列和多故障收集 | FIN 0.1.2 S1 |
| S2 One-cell real Agent | DeepSeek 单 Cell 九 Artifact、paired baseline、owner 接受 material gain | 通过后没有冻结“模型可做/不可做”的能力包络；transport/profile 修复没有沉淀成统一 compiler | FIN 0.1.2 S2 |
| S3 NVDA three-cell | coherent 6-node/12-call/9-Artifact、L1/L2、Agent 增益、owner accepted R2 | T09 吸收 schema、capacity、identity、conflict/gap、Verifier、capture 等大量共享问题；anchor 通过带有 NVDA 过拟合 | FIN 0.1.2 S0–S3 分层接管 |
| S4 T01–T04 | DELL/MU Case Pack、方法合同、source grounding、三案 deterministic path | 方法“写进 registry”与“被 Runtime 消费”曾被混淆 | FIN 0.1.2 S0/S1 contract closure |
| S4 T05 | DELL 可完成完整链并产生明显 actionability | numeric value correspondence、NVDA hard-code、Verifier false negative；DELL R2 未证明 | 当前诚实关闭；0.1.2 S4 重证 |
| S4 T06 | MU 有完整九 Artifact run、paired 能拒绝 L1；大量 truth owner 和 capture 已实现 | Fact/Claim/WWC cardinality、日期、身份、proof hermeticity 等共享架构问题被晚到 T06 才暴露；MU R2 未证明 | 结构问题回到 0.1.2 S0–S3；MU 产品证明回到 0.1.2 S4 |
| S4 T07–T10 | 三案只读校准、真实 Owner A、honest-block 真值已冻结 | all-green、post-transfer NVDA exact、NVDA R3 均未成立 | 0.1.1 decision-only closeout |
| S5 | 尚未正式执行 | hermetic package、Git/rollback、RG1–RG5、blocked release decision | 先完成 0.1.1 decision-only S5 |

当前最准确的产品状态仍是：

> `internal engineering alpha with one owner-accepted anchor case, two real transfer diagnostics, strong traceability, and no three-case release qualification`

## 4. 双任务对话反思

### 4.1 当前 S 系列任务暴露的问题

用户多次明确提出：

- 不要把单任务序列无限扩展；
- 属于下一阶段的问题应后传；
- 不要逐字段 live 修复；
- 保存完整原始输出，避免 telemetry 只有数字而无内容；
- 先集中暴露问题，再做结构性修复；
- T06 应重新划边界，而不是为了“通过”继续维修；
- 不要擅自改变 FIN 0.2 原来的产品定义。

这些方向后来都被局部采纳，但没有立即变成统一、可执行的 program invariant。于是出现了四个沟通与执行问题：

1. 多次口头承诺“最后一轮”，但任务状态机没有禁止用新 contract family、replacement、R-number 或 shared-runtime blocker 继续派生；
2. `engineering_pass`、`product pass`、`owner acceptance` 和 `stage closeout` 在不同回复中切换，造成“明明说快结束，为什么仍 gate failed”的合理困惑；
3. 用户授权“持续做到 exact-live 结束”，实际工作仍被大量 scope/authority 微步骤打断，用户不得不反复回复“继续”；
4. 初期把模型按 prompt 遵循数量、长度、日期、身份和长 JSON 的能力估计得过高，直到后期才正式收缩 Provider surface。

今后只说“注意边界”不够。边界必须有固定 artifact budget、run budget 和自动 stop state。

### 4.2 相邻 Point01/Point02 任务暴露的问题

相邻任务几乎没有 DeepSeek 质量问题，却同样发生了长链返工：

- M1–M6、P01-G2、P02.0 多轮出现 `REJECT_AND_REPAIR`；
- route map、canonical command、OpenAPI operation、typed response 和 owner mapping 在 closeout 后才发现集合未闭合；
- package、gate、preflight、blueprint、authority、receipt、candidate、bridge 和 closeout 形成多层版本家族；
- 测试早期更多验证 disposition 字段和自报状态，独立 review 后才增加 active set closure；
- staged input hash 与可变工作树长期耦合。

这证明返工不是模型专属问题。根因是“声明完成”早于“消费路径集合闭合与行为闭合”。严格治理本身是优点，但如果每次审计只验证又一层声明文件，治理会变成新的复杂系统。

### 4.3 应保留的做法

- 金融 L1、权限、证据 provenance、失败终态继续 fail-closed；
- 原始失败输出不可晋升为业务 Artifact；
- authority/receipt/exact input/digest 继续可审计；
- engineering、product、owner、release 四层状态继续分开；
- 独立 review 继续存在，但应在合同冻结前做 set closure，不应只在 closeout 后发现。

## 5. DeepSeek 的正确能力边界

FIN 0.1.2 不再把 DeepSeek 是否“听话”作为 L1 前提。

DeepSeek 可以负责：

- 在本地给出的 request-local aliases 中做有限枚举；
- 生成 bounded judgment atoms；
- 提供非权威的解释、反方、因果候选和 what-would-change 候选；
- 在 L1 事实已经由本地装配后改善 actionability 和跨 Cell synthesis。

DeepSeek 不负责：

- 重新书写 material number、period、unit、scale、sign、公式输入；
- 生成 canonical ID、ticker/entity identity、authority ref、lineage 或最终日期；
- 从 22 个候选中“记得只返回 6 个”；
- 依靠自由文本自行满足字符数、数组 cardinality 和跨字段状态机；
- 充当最终 Verifier 或 Human owner。

若当前 transport 只有 JSON object 而没有可靠 strict schema，所有数量、枚举、引用和长度约束都必须视为软提示，本地系统必须通过预选择、typed alias 和确定性 assembly 保证安全。

## 6. 重构后的 S0–S5

宏观产品节奏不变，仍使用 S0–S5。变化的是每个 S 内固定使用七个工程门禁，不再临时发明 R2–R11 或 H01。

### 6.1 宏观阶段

| 阶段 | 唯一使命 | 退出条件 |
| --- | --- | --- |
| S0 Baseline & Architecture | 冻结产品范围、truth owner、contract compiler、provider capability、capture、repo slice | 所有 L1 字段唯一 owner；合同可同源编译；完整失败 capture；可复现基线 |
| S1 Deterministic Vertical | 用 realistic fixture、mutation、full-fake 证明完整确定性链 | 三案正例、跨案/日期/数量/排列/多故障负例 all-green |
| S2 Natural Capability | 证明 changed contract family 在自然模型下的能力包络和 one-cell 价值 | 每个变更合同家族最多一个 canary batch；一个正式 one-cell product run |
| S3 Anchor Product | 证明一个三 Cell anchor，同时做 transfer-oriented mutation | anchor L1/L2、paired、owner；非 anchor identity/numeric/candidate mutation 全绿 |
| S4 Transfer Product | 在冻结 Runtime 上证明 DELL/MU/NVDA transfer 与 Human calibration | 不允许结构维修；三案 R2、post-transfer NVDA、qualified-senior R3，或 honest block |
| S5 Release Engineering | 做 hermetic、Git、rollback、RG 和 released/blocked decision | coherent commit manifest、完整 logs、reproducible package、RG1–RG5 decision |

S5 有一个 `shadow lane`：从 S0 起每个阶段都必须生成可提交 slice 和 proof inventory；正式 S5 只汇总，不再第一次处理数百个 staged files。

### 6.2 每个阶段固定七门

| Gate | 名称 | 只回答的问题 |
| --- | --- | --- |
| G0 | Scope & owner | 当前产品承诺、最早 owner、non-goal、stop budget 是什么 |
| G1 | Contract closure | prompt/schema/validator/fake/selector/renderer/capture 是否来自同一 source；active set 是否闭合 |
| G2 | Deterministic proof | unit、mutation、三案 full-fake、failure capture 是否通过 |
| G3 | Natural canary | changed contract family 的真实模型能力是否符合已声明 envelope |
| G4 | Quarantined diagnostic | 是否需要一次不可晋升的 collect-all 诊断来集中暴露下游问题 |
| G5 | Formal product proof | 唯一正式 exact-live 是否形成可验收产品 |
| G6 | Assessment & closeout | L1–L4、paired、Human、carry-forward 和 Git slice 是否闭合 |

不是每个 S 都运行全部 Gate，但 Gate 名称和语义固定。一个 Gate 失败不能通过改名再启动同类 Gate。

## 7. 反馈与工件预算

### 7.1 工件模型

每个阶段默认只允许：

1. 一个 `StagePlan`；
2. 一个可追加事件但内容寻址的 `StageCapsule`；
3. 每个真实调用最多一个 `RunCapsule`，内含 scope、authority、receipt、exact input、capture refs、result 和 terminal state；
4. 一个 `StageAssessment`；
5. 一个 `StageCloseout`；
6. 一个阶段 worklog。

零调用 proof 不再分别创建 scope、authority、admission、proof decision、result 和 disposition 六个家族。只有真实外部副作用、Human authority 或安全事件才单独保留不可变授权对象。

### 7.2 运行预算

- changed contract family：最多一个自然 canary batch；
- 一个产品 proof target：最多一个 formal exact-live；
- formal live 前允许一次 quarantined diagnostic，但结果永不晋升；
- G5 新出现 shared-runtime L1：立即 honest block，回到下一个 0.1.x 的 S0–S3，不在当前 S4 维修；
- L2–L4 默认形成 finding，除非 release rubric 预先声明为 blocker；
- 不允许自动 R-number、replacement family、provider hopping 或 prompt retry。

### 7.3 集中暴露问题

“集中暴露”不等于手工把失败 Artifact 改成通过。推荐流程：

1. 保留完整原始 request/final output/capture；
2. 在隔离 diagnostic namespace 中运行 collect-all validator；
3. 对无效节点使用明确标记的 deterministic placeholder 继续下游 shape 检查；
4. 汇总所有 contract violations；
5. 按共同 root cause 合并修复；
6. 清空 diagnostic namespace 后再执行唯一 formal proof。

这样既能一次看到多个问题，也不会污染金融事实和产品验收。

## 8. T05/T06 问题的最早归属

| 现象 | 不应归属 | 最早归属 |
| --- | --- | --- |
| prompt/schema/validator/fake 漂移 | T05/T06 某次 live | 0.1.2 S0/G1 |
| raw output/capture 不完整 | MU 产品任务 | 0.1.2 S0/G1 + S5 shadow |
| fake 自动清洗 ticker、未暴露全部候选 | DELL/MU field repair | 0.1.2 S1/G2 |
| DS cardinality、长 JSON、字符数不稳定 | prompt patch | 0.1.2 S2/G3 capability envelope |
| NVDA hard-code、跨案 identity/lineage | T05 Writer 补丁 | 0.1.2 S3 transfer mutation |
| Numeric membership 通过但 value correspondence 错 | paired 以后补 Verifier | 0.1.2 S0 truth owner + S1 mutation |
| DELL/MU 是否达到 R2 | shared Runtime 重构 | 0.1.2 S4 product proof |
| stale fixture/current-next test | T07 Runtime repair | 0.1.1 S5 decision-only + 0.1.2 S0 baseline |
| strict-schema Sub2API transport | 当前 DS 主线 | 外部接口待齐后单独 qualification；不得阻断 DS |

## 9. 本次工程决策

1. 当前 S4 不再重开 T05/T06，不在 T10 前继续修 shared Runtime；
2. 当前仓库先做只读 evidence freeze 与安全分类，再执行 T10 honest-block closeout 和 S5 decision-only；
3. 当前第一轮冻结为 `FIN 0.1.1 Internal Engineering Baseline`，不得声称 release-qualified；
4. 共同 Runtime、compiler、proof harness 和 transfer completion 进入 `FIN 0.1.2`，不是 FIN 0.2；
5. FIN 0.2 保持原定义 `Earnings Review Alpha`；
6. 0.1.2 从 S0 重新走门禁，但复用有效资产，不是从零重写代码；
7. 下一步仅为仓库 evidence freeze 与安全分类，不删除、不取消暂存、不提交、不打 tag。

当前唯一下一项：

`FIN-0.1-REPOSITORY-EVIDENCE-FREEZE-AND-SAFE-CLASSIFICATION-EXECUTION`
