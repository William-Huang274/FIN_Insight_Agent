# FIN 0.1.2 合并后统一 S0–S5 产品推进计划

日期：2026-08-02
状态：`current canonical plan / S0-S1 pass closed / S2-T03 pass / T04 authority pass, independent blind packet pending / S3-S5 not started`

## 1. 为什么重新建立本计划

FIN 0.1.1 已完整经历第一轮 S0–S5，并在 S4 暴露共同 Runtime、模型边界、跨案例迁移和验收节奏被混在一起的问题。FIN 0.1.2 原本就是把这些问题重新分配到新的 S0–S5 后完成第二轮产品迭代。

后续把多个 S0 测试失败分别编号为 FIN 0.1.3 和 FIN 0.1.4，错误地把测试尝试当成产品版本。用户已明确纠正：原 0.1.3 的实现和原 0.1.4 的规划全部并回 FIN 0.1.2；失败证据保留，但当前产品版本恢复为 FIN 0.1.2。

## 2. 当前产品真值

- FIN 0.1.1：冻结的第一轮内部 honest-block 基线；
- FIN 0.1.2：当前唯一开发版本，S0、S1 已通过并关闭；S2-T03 形成六份 hard-integrity pass 的公平能力输入；T04 的权限与范围已通过，但当前上下文因已知模型映射而无盲评资格，独立去身份化 packet、评分和模型/本地 surface disposition 仍待执行；
- 原 FIN 0.1.3：FIN 0.1.2 S0 的历史 recovery/proof attempts，不再是当前产品版本；
- 原 FIN 0.1.4：未执行的 S0 改进提案，不再是当前入口；
- FIN 0.2：继续是 Earnings Review Alpha，定义不变；
- FIN 0.1.2 本次 S0 收口没有新增用户可见能力，release qualified=false。

合并使用当前累计代码，不回滚原 0.1.3 已实现资产，也不继承其未成立的 proof pass。

## 3. S0–S5 的简单分工

| 阶段 | 用大白话描述的目标 | 通过条件 | 不在本阶段处理 |
| --- | --- | --- | --- |
| S0 可靠基础 | 当前代码在本机和干净目录中使用同一批已登记资源稳定运行，不靠隐藏文件、旧账本或机器路径碰巧通过 | 当前代码/资源/配置清单一致；本机测试通过；一个干净环境通过；最终两个独立目录复现一致；当前 S0 open issues 关闭或得到诚实边界 | DeepSeek 质量、真实金融结论、三案例产品验收 |
| S1 三案例确定性链 | 不调用模型也能让 DELL、MU、NVDA 走同一条 6/12/12/9 链 | 三案结构、数字、日期、身份、来源和失败留存可重算；mutation/permutation/跨案污染全绿 | 用 fixture 结果冒充模型或产品质量 |
| S2 模型边界 | 用少量真实调用确定 DeepSeek 可以可靠生成什么，哪些表面必须由本地程序掌管 | 对改变的合同家族做有界 canary；确定主线模型、允许的 judgment atoms、降级/本地接管边界和成本 | 三案 full-chain、逐字段 live 修补 |
| S3 单案例产品锚点 | 当前 Runtime 上的 NVDA 生成完整可追溯九件套并对分析师有增益 | exact-live 成功；独立 L1 通过；paired assessment 和 owner acceptance 成立 | DELL/MU 迁移 |
| S4 跨案例与工作台价值 | 同一冻结 Runtime 迁移到 DELL/MU 并保持 NVDA，工作台可审阅、修订和追溯 | DELL/MU R2、post-transfer NVDA、NVDA R3、三案回归和 Workbench dogfood 达标 | 在 S4 重做共同 Runtime 或模型基础合同 |
| S5 发布判断 | 团队能够复现、回滚并诚实签发或阻断内部候选 | RG1–RG5、证据清单、代码/配置 manifest、回滚和用户价值结论完整 | 用仓库可恢复性代替产品质量 |

## 4. 问题分配规则

发现问题后先问：它是否会使当前阶段目标不成立？

- 会：留在当前阶段修复，保留失败 attempt，以新 attempt 重验；
- 不会：记录明确 owner，传递到负责它的后续阶段；
- 不确定：先做最小只读/零调用定位，不立即扩展范围；
- 同类失败反复出现：暂停并重新审查当前阶段设计，不自动创建新产品版本。

失败测试、proof 或 run 不再自动冻结 FIN 0.1.2，也不自动创建 FIN 0.1.3。新产品版本只在完整迭代结束/战略终止，或产品范围与兼容性发生实质变化并经用户批准时建立。

## 5. 已有资产的处理

直接保留并重验：共同 Runtime 合同、十个 consumer、三案例 fixture/full-fake、capture/terminal result、RuntimeResourceRegistry、六类 reference role、typed environment 和 hermetic runner 的通用部分。

需要修复后再用：当前状态投影、manifest 与 current test ownership、proof control plane、版本专用 runner，以及旧 active suite 对 mutable backlog/next action 的绑定。

只保留历史、不再作为当前入口：0.1.2/0.1.3/0.1.4 的失败 authority、一次性预算、no-v4 版本冻结决定和 0.1.4 current projection。

## 6. 当前执行入口

S1 current evidence reconciliation 与独立 closeout 已通过。独立 host assessment 重新执行四个 S1 测试族=`56 passed / 0 failed`：十个实际 consumer 18 项、realistic 三案例 31 项、历史 authority 1 项、历史 assessment 6 项。S0 正式包的 verification、package manifest 和六个 phase terminal-result 哈希均重新匹配；两套 Git-free disposable 各有 realistic 三案例 `31 passed / 0 failed`。8 个关键 Runtime、合同、测试和 MU fixture 仍与正式包逐字节一致。

因此 G0/G1/G2/G4/G6 已按 current baseline 通过，S1=`pass_closed`。本次没有新增 Runtime implementation 或 clean/hermetic proof，也没有模型、Provider、网络、业务 Run 或 Artifact；旧 S1 T03/T04 失败、一次性 budget、assessment 和 closeout 保持不可变历史，未被改写。机器收口为：

`configs/releases/fin_ia_0_1_2_s1_current_evidence_reconciliation_independent_assessment_and_closeout_v1_0.json`

这仍只证明三案确定性链与故障留存，不证明 DeepSeek、exact-live 或产品质量。S2 StagePlan 已完成，冻结了 Flash stable 与 Pro preview 的同输入 paired comparison、Fact/Claim/WWC 三个 changed family、模型只输出 alias/enum/judgment atom、本地拥有 material truth，以及主要 6 calls、最多一个受影响 family 的 2-call replacement pair。replacement 只允许修复已证明的项目比较器缺陷，不能用来重试模型不遵循或弱质量结果。

StagePlan 同时发现 `common_runtime_contract_family_source_v1_0` 的状态文字仍停留在“尚未迁移”，而 admission 校验仍硬编码 Pro。T02 已通过新建 v1.1 source/binding、S2 model registry 和独立 paired-canary compiler 修复该漂移，并额外把 `program_cell_id` 收回本地注入、给 Fact 增加有界证据上下文、隔离 S2 与旧默认资源 registry。组合回归=`97 passed / 0 failed`，DELL/MU/NVDA 各 6 个 fake call、capture 和本地 assembly 全绿；RC-P36-098/099/100 已关闭。

这仍只证明比较器与本地安全边界，尚未证明 Flash 或 Pro 的自然输出能力，也没有选择 S3 主线模型。T03 权限审查已经冻结六个 exact call、硬预算和停止规则，但审计发现 T02 只有 compiler、本地 materializer 与内存 fake capture，尚无专用真实 runner，也未证明校验前原子写入受限 capture store。该项目内缺口登记为 RC-P36-101，不属于模型或 Provider 失败。

该执行前缺口已经由一个合并结构包关闭：专用 runner 从已登记 MU fixture 重建六个 exact call；原子对象仓先保存 capture 再做本地校验；网关显式锁定单次 attempt；语义失败继续、transport/auth/security/capture/budget 失败停止。实现证据=`28 focused / 61 combined passed`，加入结果与 current projection 闭环后最终=`30 focused / 63 combined passed`；preflight 外部调用为 0，RC-P36-101 已关闭。

六个已签权调用已经严格执行一次：6 次调用全部 `stop`，6 capture/6 terminal 均留存，Fact/Claim 两模型和 Pro WWC 通过；Flash WWC 被本地隐藏条件拒绝。模型可见 schema 允许 `review_date_alias=allowed alias or NONE`，本地 validator 却未公开“非 `bound_date` cadence 必须为 `NONE`”的规则，所以这不是可信的模型能力差异。调用总量=`9106 input / 1021 output`，估算成本 `USD 0.00484938`，无 retry、replacement 或业务 Artifact。

RC-P36-102 留在 S2-T03。进一步的受限 Pro 结果重放还发现本地 task assembly 把多 Claim atoms 错绑到循环结束时的最后一个 Claim，形成 terminal false green，登记 RC-P36-103。因此有效能力证据只有 Fact/Claim 四项，WWC 两模型都必须重新公平测量；T04、模型排名和主线模型选择均未进入。

唯一 WWC v1.2 零调用结构包现已工程通过。cadence/date 条件由同一声明投影到模型可见合同、wire、instruction、validator、fake 和 typed failure；最终 Claim 与 Authority 均从各自 selected atom 展开。测试矩阵在开发轮内达到 focused=`31/31`、相关回归=`138/138`，三案 fake 各 6/6，受限 Pro capture 重放不再把 `Q001/Q002/Q001` 压成单一 Claim。实现时还发现 `authority_refs` 与 Claim 相同地读取循环终态，已在同一根因、同一包内收口，没有开启第二补丁包。

旧 v1.1 资源和历史 S4 authority 没有改写；v1.2 只属于 S2 paired-canary。随后两个 fresh Python process 在两个独立 disposable roots 中完成零调用复证：凭据环境清除、网络硬阻断、8 项实现 binding、v1.1 immutable hash、日期正负矩阵、逐行 Claim/Authority、permutation、6→3 selection、三案 fake 和受限形状重放结果逐字节相同。独立 proof 因此通过，但 RC-P36-102/103 仍不关闭，因为还没有公平自然 WWC 输出。

现已签发“有条件的未来两调用 authority”：只允许 MU 的 WWC family，Flash stable 与 Pro preview 各一次；Fact/Claim 不重跑，retry/fallback/provider hopping 均为 0，总预算上限 `2 calls / 10k input / 2.8k output / USD 0.015 / 300s`。专用 two-call runner 与零调用 preflight 随后已通过：authority、MU fixture、v1.2 contract 和两个 request/equivalence digest 均重新绑定；happy、semantic-continue、transport-stop、capture/budget-stop、fresh identity 不可复用和 capture-before-validation 均已确定性证明。focused=`13 passed`，S2/历史不可变性组合回归=`86 passed`，外部调用为 0。

共享六调用 compiler 是旧 authority 和独立 proof 的哈希冻结资产，因此 pair 适配器被隔离在新 runner 子类中；共享 compiler 恢复并保持原 SHA256，旧六调用 authority/runner、v1.1 source/binding 和失败证据均未改写。

用户随后以新的“继续”消费唯一 replacement authority。Flash stable 与 Pro preview 各一次调用均以单次 transport attempt、`finish_reason=stop` 和本地 hard-integrity pass 终态化；capture/terminal=`2/2`，tokens=`3690 input / 779 output`，估算费用=`USD 0.00228288`，Fact/Claim rerun、retry、fallback、Provider hopping 与业务 Artifact 均为 0。两份输出都保留两个 Claim ID，Authority refs 逐 atom 展开，因此 RC-P36-102/103 关闭。与历史四份有效 Fact/Claim 结果组合后，T03 的公平输入为 `6/6 hard pass`。

未评分检查显示 Pro 的证据分组和状态迁移更有区分度，Flash 更保守且多次合并全部 Authority；两者都出现“不晚于 as-of 的 bound review date”这一合同允许但可用性存疑的现象。它属于 T04 的决策有用性评分输入，不是再开 T03 修复包的理由。当前下一项：

`FIN-0.1.2-S2-T04-BLINDED-PAIRED-ASSESSMENT-MODEL-LOCAL-SURFACE-DISPOSITION-AND-S2-CLOSEOUT-AUTHORITY-DECISION`

该零调用权限与范围决策已经完成。审计确认当前上下文已看到 Flash/Pro 映射和方向性观察，不能诚实承担盲评，因此登记 `RC-P36-104`。T04 已冻结：随机跨 family 一致 opaque labels、映射单独受限保存、评分记录先冻结取 digest 后解盲、四项 0–2 rubric、既有 Flash stable 优先规则，以及每 family 至少 4/8 且证据相关性/认知纪律/决策有用性各至少 1 分的模型 surface 保留阈值。未达标 family 转本地确定性 ownership 或 honest block。

下一项已获得一次性零调用实施与交接权限，无需再插入同类 authority decision：

`FIN-0.1.2-S2-T04-IDENTITY-SEALED-BLIND-ASSESSMENT-PACKET-AND-INDEPENDENT-EVALUATOR-HANDOFF-MINIMUM-ZERO-CALL-IMPLEMENTATION`

当前 quality score=0、model selection=0；S2 未关闭，S3 未进入。评分必须由未接触映射和本任务历史的新 Codex task 或人工评审完成。

以下 S0 收口说明保留为 preceding current-baseline evidence：

S0 的唯一 R2 formal qualification 已在 clean/synced HEAD=`6340aeef857ad3c48226a530ace6bb8204b8decd` 上执行一次并通过：host=`31 passed`，两套 Git-free disposable 各=`58 passed`，semantic/raw parity、content-addressed capture 和 repository readback 全部通过，789 个 package files 全部 tracked，未知宿主路径、allowlist 和外部依赖均为 0。历史审计单独保留 `23 passed / 1 non-gating finding`，没有被隐藏或计入 current gate。

因此 RC-P36-090/091/093/094/095/097 已关闭，FIN 0.1.2 S0=`pass_closed`。本结论不证明模型质量、exact-live、三案例产品等级或 release；S1 已由上方入口决策重新进入，S2–S5 尚未进入。

历史 S1 已存在大量三案例确定性资产，且本次 S0 package 已实际执行其中的 realistic three-case tests。为避免再次把“已有资产”误当“当前阶段已验收”，也避免从头重复建设，当时下一项先做 S1 入口与资产复用边界决策（已由上方决策消费）：

`FIN-0.1.2-S1-ENTRY-AND-HISTORICAL-ASSET-REUSE-SCOPE-DECISION`

以下内容保留为本次 S0 正式通过前的历史执行脉络，不再拥有 current next：

版本合并、计划、新起点、只读资产审计和 S0-04 本地零调用集中修复已经完成。S0-05 唯一 clean qualification 已在 clean/synced HEAD 上执行并终态失败：两套 disposable 均为 `45 passed / 54 failed`，其中 current gate 失败 41、历史 finding 13；29 项生产 Runtime 资源、14 项资源测试和 10 项 typed-environment 合同测试均通过，但 manifest 把运行前、host-only、disposable 与历史测试混在同一执行集合，且没有编译完整测试资源依赖。语义 parity 也因 escaped path、fixture URI 和 pytest 临时根边界得到每套 53 个未知绝对路径 finding。

这不是模型、Provider、金融判断或用户可见产品质量失败，而是 S0 测试拓扑与 hermetic dependency/environment closure 的项目内结构问题。不能通过补齐本次看到的单个 JSON 文件来宣布修复。

项目级零调用处置和结构实现已经完成：单一 TestExecutionContractRegistry 把检查分为 contract compile、host preflight、双 disposable current gate、非阻断 historical audit 和 post-run attestation；测试模块只引用逻辑 dependency bundle，compiler 负责闭合 current projection、Runtime registry、reference role、immutable event 和 fixture 资源。历史失败继续可见，但不再与 current gate 混算；`.git` 不进入 disposable；pytest 临时目录固定在每个 disposable 的 typed temp root；原始输出不改写，只在语义副本中做 URI-aware 和 escaped-path 规范化。工程 full-chain 已达到 host `31 passed`、两套 disposable 各 `58 passed`、semantic parity 与 post-run attestation 通过，仍不等于正式 S0 资格通过。

同时纠正 proof 节奏：本地零调用单测、fixture 和 mutation 是正常实现验证，不再被当成产品版本或一次性正式 attempt；提交后的双目录 qualification 才记正式 attempt，同一代码候选禁止盲重跑。失败后仍在 FIN 0.1.2 S0 修最早根因，不自动创建 0.1.3。

新的 R2 authority 已绑定 clean/synced engineering base HEAD、phase-aware registry、实现记录、正式 manifest R2.3、current projection v2.5、runner、attempt contract、唯一输出根和一次性预算；authority decision 本身没有启动 attempt。

当时下一项是（已由成功 formal attempt 消费）：

`FIN-0.1.2-S0-FRESH-CLEAN-ENVIRONMENT-QUALIFICATION-EXECUTION-AND-CLOSEOUT`

上一 R1 qualification attempt 与本次成功 R2 attempt 均按不可变事件永久保留；R2 已消费 `1/1` 且没有自动重试。正式审查已关闭 RC-P36-090/091/093/094/095/097，S0 已通过；S1–S5、模型/Provider、真实业务链和产品 Artifact 仍未因此自动获权或通过。
