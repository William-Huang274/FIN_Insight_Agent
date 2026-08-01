# FIN 0.1.3 统一 S0–S5 产品推进计划

日期：2026-08-01

状态：`accepted planning normalization / S0 exit-contract v3 proof-control-plane recovery selected / implementation pending`

当前版本：`FIN 0.1.3`

发布真值：`internal honest block / release qualified=false`

## 1. 本次规划修正解决什么

FIN 0.1.1 与 0.1.2 已冻结为历史内部工程基线；FIN 0.1.3 是当前唯一主线。它不新增 Earnings Review Alpha 功能，也不因为 S0 的一次终态失败自动产生 FIN 0.1.4。版本号、阶段和任务从现在起分别回答三个问题：

- 版本号说明哪一组产品承诺和工程债共同接受验收；
- S0–S5 说明产品能力从可信基础设施走到可发布候选的成熟顺序；
- Txx 只是某一阶段内有界、可停止、可审计的执行单元。

旧 T03 的失败、预算和证据保持不可变。当前决策只在 FIN 0.1.3 S0 下建立新的 `exit_contract:v2`，不把旧失败改名为 pass，也不把一次合同修订伪装成新版本。

## 2. FIN 0.1.3 的单一 S0–S5 主轴

| 阶段 | 用户最终能感知的目标 | 本阶段主要证明 | Exit 条件 | 不在本阶段做 |
| --- | --- | --- | --- | --- |
| S0 可信基础 | 同一个研究任务在宿主机和干净环境中使用同一套代码、合同和资源，不因隐藏文件或机器路径产生假通过 | Runtime resource、typed reference role、typed environment、proof-control-plane eligibility、active tests、capture/terminal result、两套 disposable parity | exact manifest 在消费前穿过同一 compiler boundary；host engineering proof 全绿；独立双-disposable formal proof 全绿；RC-P36-090–095 可关闭 | 模型比较、真实金融结论、DELL/MU/NVDA 产品验收 |
| S1 确定性三案 | DELL、MU、NVDA 在零模型条件下走过同一 `6 nodes / 12 interactions / 12 captures / 9 Artifacts` 链，数值、日期、身份、lineage 与失败留存可重算 | 三案 full-fake、mutation、compiled contract、selector/renderer、capture-v2 | 三案 current Runtime 全绿，无跨案污染或未类型化 authority | 用 fixture 结果替代真实模型质量 |
| S2 模型边界 | DeepSeek V4 Flash stable 与 Pro preview 的能力差异有小样本、可重复、低成本证据，并选出主线模型/降级边界 | 单节点自然输出 canary；必要时一个完整 cell；schema、数量、语义与成本对比 | 明确主线 alias、允许模型生成的 judgment atoms、必须由本地接管的表面；无逐字段 live 循环 | 三案 full-chain、为了比较而无限调用模型 |
| S3 单案例产品锚点 | 当前 Runtime 上的 NVDA 三 Cell 能生成可追溯九件套，并对分析师有可见增益 | exact-live、独立 L1、paired assessment、owner acceptance | NVDA current R2；九件套 coherent；L1 通过；Agent 增益和 owner acceptance 均成立 | 把历史 accepted 包当作当前 Runtime 迁移证明 |
| S4 跨案例迁移与工作台价值 | 同一冻结 Runtime 能迁移到 DELL/MU，并保持 NVDA；用户可审阅、修订、追溯并判断是否愿意继续使用 | DELL/MU R2、post-transfer NVDA、qualified-senior R3、Workbench dogfood、任务时间/编辑负担/信任 | 三案同时 R2、NVDA R3、当前回归全绿、真实用户价值证据成立 | 在 S4 重新发明共同 Runtime；把工程诊断当产品验收 |
| S5 发布判定 | 团队能安全复现、回滚、解释版本状态，并诚实签发或阻断内部候选 | RG1–RG5、证据 inventory、commit/rollback、release decision | 只有全部 release gate 成立才创建 candidate；否则形成可恢复 honest block | 用内部可恢复性覆盖产品质量门禁 |

## 3. 当前 S0 Exit Contract v3

当前最早阻塞是 `ref/*_ref` 同时承载仓库资源、外部内容、受限 Runtime 审计、模型运行报告和业务语义 follow-up，旧 compiler 依靠字段后缀与字符串形状猜测类型。新的合同必须从一个版本化 registry/schema 编译以下角色：

1. `repository_resource`：必须进入 tracked-or-typed closure；
2. `package_relative_audit`：只能指向包内受限审计证据，不能晋升为业务内容；
3. `external_content`：URL、外部文档或外部内容标识，不递归为仓库路径；
4. `restricted_runtime_audit`：`.codex_runtime` 等受限 lineage，只允许审计引用；
5. `model_run_report`：tracked model-run report lineage，按明确策略进入闭包；
6. `semantic_followup`：业务 follow-up 文本，禁止用路径形状重新解释。

未知角色继续 fail closed。v2 已把六类 reference role、collect-all validator、RuntimeResourceRegistry 与 typed environment 实现落地；其唯一 host proof 因 proof manifest 将 `fail_closed_collect_all` 当作 policy enum、而共享 compiler 只接受 `fail_closed`，在进入 Runtime 行为前终止。旧 T03 与 v2 的失败和预算均不重置。

项目级 disposition 选择同版本 S0 Exit Contract v3，不自动创建 FIN 0.1.4。v3 不重做产品 Runtime；它只建立 proof policy 单一来源，并把 `unknown_reference_behavior=fail_closed` 与 `unknown_reference_reporting=collect_all_typed_envelope` 分成两个语义，再增加一次 non-consuming exact-boundary eligibility。eligibility 必须在 clean/synced committed HEAD 上绑定 execution/active manifest、source digests 和 compiled inventory digest；只有 attestation 匹配后，host proof 才开始消费。v3 固定 `[implementation, eligibility, host, formal]` 各最多一次，任一新结构失败都冻结 FIN 0.1.3，禁止同版本 v4。

## 4. 计划变化规则

下列变化必须在执行前向 Owner 说明“为什么变、从哪移到哪、对版本/用户能力/预算的影响”，并更新产品计划、技术边界、backlog 与 Project OS：

- 改变某项能力的 S 阶段归属；
- 增减 live/model/proof 预算；
- 新增版本号、放宽 L1 或 release gate；
- 用本地确定性 planner 接管原本由模型生成的表面；
- 因外部 Provider/API 条件改变主线模型或 transport。

同一阶段内部不改变合同语义的测试补强、文档勘误和可逆重构可以直接执行，但仍记入 worklog。任何失败都先判断是当前 Exit Contract 内缺口、后续阶段质量问题，还是下一产品版本功能；不再默认把所有问题塞回当前任务。

## 5. 本次决策的真实影响

路线与验收合同之后，S0 已完成一次有界 taxonomy 实现，但 v2 host proof 暴露 proof packaging 与消费边界不足。项目级 decision 没有重跑、豁免 proof 或新建 0.1.4，而是把最后一次同版本恢复限制为 Exit Contract v3 proof-control-plane implementation。当前只是 planning/contract selection：v3 observed=`0/0/0/0`，没有实现、eligibility、host 或 formal evidence，用户可见金融研究功能无增量。FIN 0.1.3 S0 与 RC-P36-090–095 继续 blocked/open，S1–S5 产品能力顺序不变。

当前唯一下一项：

`FIN-0.1.3-S0-EXIT-CONTRACT-V3-PROOF-POLICY-SINGLE-SOURCE-AND-PRE-CONSUMPTION-BOUNDARY-MINIMUM-ZERO-CALL-IMPLEMENTATION`
