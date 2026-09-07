# FIN 0.1.3 S3 连续执行与异质泛化评测治理

日期：2026-08-16

状态：`owner_authorized / evaluation_contract_pre_registered_before_results / remaining_fragment_zero_call_current`

## 1. 本轮为什么先写治理

FAS-R1 只证明 DELL `value_capture.thesis` 在 fixed Pack 上能够自然形成 L1 合格判断。后续还要运行完整 fixed Pack、动态检索、五个研究单元和跨案例验收。若等看到 MU／NVDA 或留出案例结果后才挑案例、阈值和评分维度，评测会不可避免地适配测试集，也无法回答“同一内核是否真正泛化”。

因此本记录在后续结果出现前冻结执行顺序、失败续跑语义、案例分账、逐案硬门和报告要求。它不签发任何模型、网络或数据采购权限，也不把已知案例改写为真正盲测。

## 2. 连续执行顺序

1. 同步 PRD、当前计划、Project OS、根因／能力／方法账本；
2. 零调用扩展 mechanism 和 counterargument／WWC 的片段专属上下文与分析／交卷；
3. 运行一次完整 DELL fixed-Pack Judgment，执行 L1 和内容质量验收；
4. 闭合动态 Research Truth Spine；
5. 运行 DELL `value_capture` 动态单单元；
6. 迁移其余四个 RoleMethodPack／GraphContextPack，运行 DELL 五单元；
7. 执行 MU、NVDA 与异质留出案例的泛化评测并形成报告；
8. 完成八维绝对质量、paired gain、qualified-human 验收与 S3 决策。

顺序可因最早责任层缺陷在 1–8 内局部回退，但不得跳过前置产品门、创建新产品版本或偷偷进入 S4／S5。

## 3. 失败和连通性语义

- 业务／合同／L1 失败：保存完整 model-visible request、最终 assistant 输出、调用参数、model/profile、finish reason、usage、capture、terminal result 和规则命中位置；失败 attempt 不可变。修复后必须使用新 attempt ID 和新 authority。
- 连接失败：先判断本机代理／TUN、DNS、TLS、HTTP status 前中断、`IncompleteRead`、远端 HTTP 错误或限流；允许有界重连和 transport 修复，但不得把同一业务调用的多次发送伪装为 exact-once。
- 不自动暂停的情况：普通模型合同失败、内容 L1 失败、已知项目代码缺陷或可恢复连通性问题。
- 必须暂停的情况：产品范围、数据采购／外部授权、模型主路线、安全／隐私边界、S4 publication、S5 release 或不可逆外部状态需要改变。

## 4. 案例分账

| 分组 | 当前案例 | 可做什么 | 不可做什么 |
| --- | --- | --- | --- |
| development | DELL、MU、NVDA | 开发、定位、修复和纵切验收 | 不能单独证明泛化 |
| observed validation | ORCL、ASML、ANET | 检查跨产业迁移和已知错误非回归 | 不能称为未见测试；结果不得用于挑最终通过样本 |
| test-precut | HPQ、AVGO、INTC | 在输入、来源、评分和模型 profile 冻结后做一次测试 | 若结果用于修改核心合同，该案例须降级为 development／validation |
| true holdout | 执行前另从已具备合法来源和可审计真值的案例池机械选择 | 最终评估同核心迁移 | 不得由实现者在看过结果后人工挑表现好的公司 |

当前仓库只预切了 HPQ／AVGO／INTC identity-time 边界，并不自动说明它们具备完整 Evidence、NumericFact 或人工 Gold。若来源和真值不足，应如实保留 typed gap 或选择预先定义的机械替补规则，而不是伪造盲测。

## 5. 异质性覆盖矩阵

最终案例组合至少覆盖：

1. 产业／商业模式：OEM／硬件整机、存储周期、fabless／平台、企业软件／云、设备／制造、网络基础设施；
2. 关系方向：issuer 自述、客户需求 read-through、供应商／代工约束、竞争／替代、ecosystem 背景；
3. 来源形态：10-K、10-Q、8-K、6-K、官方 IR PDF、法说 transcript、结构化表格、正文 claim；
4. Evidence 状态：直接支持、bounded inference、冲突、需要补证、真实 typed gap；
5. 时间：当期、同比同 cadence、财年／季度、PIT、来源发布日期与报告期分离；
6. 判断难度：事实陈述、经营机制、产品→分部／公司财务桥、反方、WWC、不可推断；
7. 工具路径：SQL exact fact、BM25／semantic narrative、official source supplement、Evidence Gate、动态 repair。

不能以“公司 ticker 不同”代替异质性，也不能只用同一 SEC 表单和相同 value-capture 问题。

## 6. 预注册评测维度

### 6.1 逐案 L1 硬门

- case／issuer／evidence owner 身份正确；
- research as-of、reporting period、cadence 和 source date 正确；
- 来源、引用和 lineage 可回到真实承载内容；
- NumericFact 的值、单位、scale、sign、qualifier、公式和 bridge authority 正确；
- 无跨案例／跨单元污染；
- typed gap、Graph、Skill、候选或 proposal 不冒充事实；
- bounded read-through 不升级为公司特定订单、利润或强因果。

任何一案出现上述错误，该案不通过；总体平均分不能覆盖它。

### 6.2 检索与 Evidence

- EvidenceRequest 是否正确表达主体、owner、关系、期间、来源与 slot；
- required-slot target-in-pool 和 facet coverage，按 slot／route／case 报告；
- SQL、lexical、semantic、graph、official supplement 各自的独立贡献；
- candidate→Evidence 的 precision、rejection、abstain、needs-human-review 和 typed gap 诚实度；
- 旧期、错 owner、错来源、导航／免责声明、泛化风险段等噪声的头部稳定性；
- 新 Evidence 是否只触发受影响单元重裁决。

### 6.3 NumericFact 与桥

- exact fact 请求解决率、typed gap／conflict；
- same-cadence relation 与公式 lineage；
- operating metric 是否仍只是叙事 Evidence，还是已有 source-bound typed authority；
- 产品→分部／公司财务桥是否存在，缺失时是否正确 abstain；
- PIT 估值输入与完整估值能力是否分开。

### 6.4 Agentic Research

- 从用户问题到 Research Objective／DecisionSurface 的覆盖和误解；
- 动态 EvidenceRequest 的新信息价值、重复率和错误路线；
- residual gap 是否驱动有效 follow-up；
- 工具调用是否有进展，是否按预算停止；
- 五单元是否各自完成 thesis、mechanism、counterargument／WWC，并在综合时不跨单元污染。

### 6.5 内容质量与产品价值

每案按八维做绝对评分：问题定义、证据使用、机制解释、数值与财务桥、反方／WWC、决策密度、表达与边界、用户可用性。随后做：

- 与同输入 predecessor 的 paired gain；
- qualified-human 逐段验收；
- 具体错误、最早责任层和修复归属；
- token、调用、工具、网络、延迟和成本；
- 研究报告是否比原始 Evidence Pack 提供实质判断增量。

## 7. 报告形态

第 7–8 项必须产出：

1. 每个案例一份端到端运行与内容评估；
2. 一份案例×异质性覆盖矩阵；
3. 一份逐案 L1／八维／paired／human 结果表；
4. 一份跨案例业务错误和最早责任层矩阵；
5. 一份成本、延迟、调用与无进展停止报告；
6. 一份明确的 S3 `pass / conditional / fail` 决策，列出不能被平均值掩盖的 blocker。

报告必须用业务语义解释失败，例如“查询 DELL 客户需求时，前排是 Dell 自身收入披露，无法证明客户真实部署”，不能只写 Recall 或模型分数。

## 8. 当前下一门

在不调用模型或网络的前提下，把 FAS-R1 已证明的同一模式扩展到 mechanism 和 counterargument／WWC，并用三案例身份、缺权威、跨片段引用、关系冲突、QF 重复渲染和完整 Judgment 编译 mutation 复证。通过后才签发一次完整 fixed-Pack live。
