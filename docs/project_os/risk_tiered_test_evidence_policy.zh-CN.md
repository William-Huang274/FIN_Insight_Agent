# FIN_Insight_Agent 风险分层测试证据策略

版本：`v0.1`

生效日期：2026-08-27

## 1. 目标与不变量

本策略解决“把全仓 pytest 当成每次小改后的默认保险丝”造成的高等待成本，同时不把少跑测试误写成质量提升。

不变量：

1. 验证范围由变更可能影响的失败面决定，不由追求更少的测试数量决定。
2. 任一未能解释的失败、依赖关系不明或共享合同漂移都向更高一级升级；不得为了省时缩小范围。
3. 历史失败、正式 attempt、结果和审计继续 immutable；测试优化不放宽 identity、lineage、privacy、evidence、financial semantics 或 report-quality gate。
4. 默认回归不得调用网络、Provider、付费模型或消费一次性 authority。
5. 测试证据绑定其覆盖的代码、测试、配置和环境输入；覆盖输入未变时可以复用，发生相关变化时必须重跑对应层级。

## 2. 五级验证模型

### T0：变更分类与廉价静态门

每次变更都执行适用项：`git diff --check`、Python compile/static check、JSON/JSONL parse、secret scan、active-baseline/import-graph check。T0 不能替代行为测试，但负责尽早阻断语法、格式、秘密、非法引用和活动树漂移。

### T1：直接责任测试

运行直接拥有被改模块、runner、schema、validator 或 renderer 的测试，包括该改动新增的正向、负向和 mutation controls。仅文档/账本变更运行读取或验证这些文档/账本的测试。

### T2：合同邻接测试

运行直接 predecessor、successor、同一版本族以及共享输入/输出合同的测试。版本化 successor 不能只证明新文件自身；例如 R7 必须覆盖 R1/R3/R4/R5/R6/R7 邻接合同。

### T3：受影响子系统与消费者测试

当变更触及共享 stage contract、active consumer、Project OS、Workbench 入口、数据迁移或跨模块编排时，运行相应子系统集成门。只运行明确的正向路径清单；在 marker 覆盖完成前，不使用 `-m "not ..."` 之类负向排除来假定未标注测试是安全快速测试。

### T4：全仓 pytest

全仓只在以下任一条件成立时运行：

1. 生产代码/测试完成一个高风险实现冻结，且尚无覆盖该冻结代码面的有效全仓证据；
2. 修改公共基础设施、共享 schema/validator/compiler/gateway、依赖或 pytest 配置、active pointer、迁移语义，影响面不能由 T1–T3 有界证明；
3. T1–T3 出现无法归属或跨子系统失败；
4. 合并主线、产品/release 候选或用户明确要求全仓复证；
5. 上一次全仓证据所绑定的可执行/测试/配置输入已经变化，且该变化属于上述高风险面。

下列变化本身不触发 T4：worklog 叙述、append-only Project OS 状态行、注释、尚未被活动 Runtime 消费的 immutable policy/result/audit artifact。它们仍必须通过各自 T0/T1/T3 validator。

## 3. 证据复用与升级规则

每次里程碑记录：命令/测试清单、通过/跳过/警告、耗时、覆盖的变更集、相关 Git identity、环境/依赖是否变化，以及未运行范围。复用旧证据前必须证明：

- 自该证据产生后，相关生产代码、测试和运行配置没有语义变化；
- 新变化由更窄但完整的责任测试覆盖；
- 没有新失败、未知依赖或活动消费者漂移。

任一条件不能证明时，自动升级一级；仍不能界定时运行 T4。测试失败保持在最早责任层修复，不能用更宽套件的偶然通过覆盖窄门失败。

## 4. 当前 marker 与并行化边界

`pyproject.toml` 已声明 `fast_contract`、`fixture_integration`、`full_chain` 等 marker，但截至本策略生效时，关键 marker 尚未系统标注；只有少量 `requires_local_data` 使用记录。因此：

1. 当前选测以每个工作项显式写出的测试路径/节点为权威；marker 仅在其覆盖率审计通过后参与自动选测。
2. 下一次确有必要的 T4 统一附加 `--durations=50` 并保存慢项清单；先从真实耗时热点优化 fixture、重复初始化和子进程。
3. `pytest-xdist` 或人工并行分片只有在共享文件、端口、数据库、模型缓存和一次性 artifact 均证明 hermetic 后才启用；不得用并行竞争换取不稳定通过。

## 5. 独立审计的成本控制

干净 reviewer 默认消费 immutable implementation/result、测试证据和明确 finding matrix，不重复运行全仓 pytest。审计分两段：

1. identity/integrity/semantic/privacy/route 的差异与攻击面审查；只在发现具体可疑点时运行对应 targeted/mutation tests；
2. 研报的 claim-to-source、citation/source appendix、crosswalk、WWC、密度/重复、typed gap 和财务推导质量审查。

若第一段发现 material engineering finding，先停止产品结论并回 owning stage；若工程通过但研报失败，只回 S1/S2/S3/Writer 的实际责任层。审计不以“重跑所有作者门”代替作者分离的判断。

审计效率补充（2026-08-27 R7 实证纠偏）：

1. 作者在 immutable result commit 中同时提供 hash-bound audit manifest：exact files/hashes、predecessor findings、positive controls、actual-route expectations、report checklist、允许命令与禁止范围。Reviewer 必须独立复验 manifest，但不自行重新做项目发现。
2. AGENTS 要求的 Project OS/context/policy 仍须完整读取；该要求不授权递归扫描所有历史 ledgers、worklogs 或 archive。只读取 manifest 明确引用的最新状态行和 predecessor artifacts。
3. Engineering 与 report 两段各完成后先交 checkpoint；若固定 bundle 缺 source passage/locator 或 qualified-human evidence，标 `NOT_ASSESSABLE` 并写清缺件，不扩大搜索。
4. Supervisor 可在 reviewer 越出 manifest、重复无关历史或未按 checkpoint 交付时中断；恢复后用已收集证据交付，不把“独立审计”解释成无限时长。

## 6. R7 的即时适用

R7 production/test implementation 冻结后已经完成一次 T4：`1726 passed, 2 skipped, 2 existing SWIG warnings`，耗时 `1319.73s`；同时 T1=`151`、T2=`357` 已通过。随后仅追加 Project OS/worklog 与本策略，不改变 R7 executable semantics，因此不再重复 T4：

- 当前提交前补跑 Project OS 及 JSON/JSONL、compile/static、diff 等适用门；
- policy-only authority 运行 R7 policy/identity targeted gate，不跑 T4；
- immutable R7 result 运行 exact replay/reprojection、R7 result/integrity tests 与 Project OS gate，不跑 T4；
- fresh reviewer 使用固定 R7/R17 双审计清单，不重跑 T4；仅 material finding 才升级相应测试范围。

如果后续实际修改 R7 production/test semantics、共享 validator 或 active consumer，上述复用立即失效，重新按 T1→T4 的升级条件判断。
