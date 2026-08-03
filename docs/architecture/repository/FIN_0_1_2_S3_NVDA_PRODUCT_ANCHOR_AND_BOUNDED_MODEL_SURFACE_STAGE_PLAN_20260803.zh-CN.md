# FIN 0.1.2 S3：NVDA 产品锚点与有界模型 Surface 计划

> 2026-08-04 closeout：S3-T03 replacement exact-live 与独立 L1 已通过（9 calls / 9 captures / 3 local Fact receipts / 9 Artifacts），但 S3-T04 paired product assessment 因 sparse `1/3` factual-cell coverage、limited/generic Agent gain、renderer internal-token/period/currency defects 和 final-preview verifier coverage 缺口被 Owner reject。S3 因 T04 honest-block，不具备 S4 entry；S3-T03 不重开且不得第三次 exact。权威 closeout 见 `configs/releases/fin_ia_0_1_2_s3_t04_nvda_paired_assessment_owner_rejection_and_s3_closeout_v1_0.json`。

日期：2026-08-03
状态：`S3-T01 pass / S3-T02 pass / S3-T03 replacement exact-live + independent L1 pass closed / S3-T04 Owner reject / S3 honest-block / S4 not eligible`

## 一、S3 到底要证明什么

S3 只做一件产品层面的事：让当前 FIN 0.1.2 Runtime 针对 NVDA 生成一套完整、可追溯、可独立复算的九件套，并证明它比同输入的确定性基线更有研究价值，最后由 Owner 对这套精确 Artifact 作接受或拒绝决定。

S3 不负责 DELL/MU 迁移，不负责 NVDA R3，不负责 release，也不重做 FIN 0.2 的广义合同编译器。

## 二、为什么不能直接跑 exact-live

S2 已经选出 Pro preview，但它只保留 Claim/WWC 两个有界模型 surface；Fact 的模型权限因 epistemic discipline=0 被收回。本轮代码审计却发现：

- v1.2 binding 明确写着 `S2_paired_canary_only`，尚不是生产 Runtime binding；
- 当前 `bounded_agent_executor.py` 仍会对每个 Cell 的 Fact、Claim、WWC 三段全部调用 Provider；
- owner-grade profile 仍按 12 次 Provider 调用校验预算；
- S1 的 NVDA 输入只是结构兼容 fixture，不是当前 S3 的 tracked exact product input；
- 历史 FIN 0.1 NVDA 九件套和 Owner acceptance 可复用为 schema、rubric 和产品参考，但不能冒充 FIN 0.1.2 当前证明。

因此，直接跑 live 会再次用付费调用发现一个已经能在代码中看见的入口矛盾。该缺口登记为 RC-P36-105，归 S3-T02，不重开 S0–S2。

## 三、新的调用形态

S1 的 `6/12/12/9` 是历史确定性基线：6 个逻辑节点、12 次 Provider 交互、12 份 capture、9 个 Artifact。S3 不改写这个历史结果，但不能继续照搬其 Provider 权限。

当前 S3 目标形态为：

- 6 个逻辑节点；
- 12 个逻辑交互；
- 3 个 Fact 交互由本地确定性 planner 完成并生成 typed receipt；
- 6 个 Specialist Claim/WWC 模型调用；
- 3 个 Lead/Writer/Verifier 模型调用；
- 合计最多 9 次 Provider 调用与 9 份原始 capture；
- 最终仍为 9 个业务 Artifact。

Lead、Writer、Verifier 可以贡献非权威的分析组织、表达与 finding，但不得创造或改写事实、重要数值、日期、身份、ID、lineage 或最终 L1 真值。

## 四、固定任务

### S3-T01：计划与入口决策

本文件对应的工作。冻结范围、资产复用、模型/本地权限、调用形态、成本、失败停止规则和阶段退出条件。没有改 Runtime，也没有调用模型。

### S3-T02：生产 Runtime 接入与零调用产品就绪

只允许一个初始实现包，完成：

1. 新建 S3 生产 binding/admission profile，不改写 S2 v1.2 历史；
2. 创建带来源哈希、输入摘要和不可晋升边界的当前 NVDA exact input；
3. 把三次 Fact Provider 调用替换为本地确定性 Fact 交互与 receipt；
4. Claim/WWC 精确消费 S2 选定合同与 Pro preview route；
5. 证明 Lead/Writer/Verifier 不能取得 L1 真值权限；
6. 以 full-fake、mutation 和 fresh process 证明 `6 nodes / 12 logical interactions / 9 Provider captures / 3 local Fact receipts / 9 Artifacts`；
7. 在任何凭据访问前跑完当前适用的 S0–S2 回归。

T02 结束时只允许在内存中编译 prospective admission，不签发、不消费、不调用 Provider。

### S3-T03：一次当前 NVDA exact-live

T02 通过且用户另行授权后，才允许一次 primary formal attempt。预算上限为 9 calls、60k input tokens、10k output tokens、USD 0.06、900 秒；每个 call 最多一次 transport attempt，retry/fallback/provider hopping/prompt-only retry 均为 0，source network 与外部工具为 0。

成功必须得到一个 coherent 当前版本九件套；失败必须先保存模型可见请求、最终 assistant 输出、receipt、capture 和 typed terminal result，再停止。

### S3-T04：paired、Owner 与收口

仅在 T03 形成完整九件套后执行。先独立复算 L1，再用同一 exact input 物化确定性 baseline，完成 L3/L4 paired assessment，最后由 Owner 对精确 digest 作接受、拒绝或 honest-block 决定。通过只建立当前 NVDA R2，不建立 R3、跨案例或 release。

## 五、如何避免再次无限修补

- 普通 L2 可恢复偏差只登记 finding；L3/L4 质量问题进入 paired/Owner，不自动改合同。
- primary live 的项目内 L1 最多允许一个合并结构修复包和一个 replacement attempt，并且必须有新 identity、admission digest 和用户授权。
- Claim/WWC 若发生真实 surface 不遵循，优先撤回该 surface 给本地确定性层，不能展开逐字段 prompt 补丁系列。
- replacement 再出现新 L1，S3 honest-block；没有第三次 exact attempt，也不新增 T05/R-number/产品版本。
- collect-all diagnostic 只能在正式失败后由 Owner 明确决定，始终隔离且不可业务晋升。

## 六、T02 实现结果与 T03 权限裁决

S3-T02 已按单一零调用结构包完成：新建独立 v1.3 生产 source/binding 和 v9 transport；三次 Fact 交互改为本地确定性 selection/rendering，并各自产生 typed receipt；Claim/WWC 继续绑定 Pro preview 的 alias/enum surface；当前 NVDA exact input 以来源、head、input 和六段 lineage digest 登记，且明确不是 admission 或当前产品证明。

full-fake 对当前 exact input 证明了 `6 nodes / 12 logical interactions / 3 local Fact receipts / 9 Provider calls and captures / 9 Artifacts`。输入、binding 和 Lead 叙事 mutation 均 fail closed；Research Lead 失败时仍保留已完成三节点、3 个本地 receipt、7 个 capture 和 typed terminal result。适用 S1/S2 与历史 S4 功能回归通过。真实 credential、模型、Provider、execution network、业务 Run/Artifact 与 live case head write 均为 0；内存 prospective admission 为 disabled，未签发、未消费。

RC-P36-105 因生产接入和当前输入门禁完成而关闭，但这不建立自然模型表现、当前 NVDA R2、paired 质量或 Owner acceptance。

`FIN-0.1.2-S3-T03-NVDA-EXACT-LIVE-EXECUTION-AUTHORITY-DECISION`

该零调用权限决策已完成，并有条件授权未来一次 primary exact-live；当前权限尚未生效。审计发现两项相连的执行前缺口：T02 tracked input digest 包含由 execution identity 派生的 Run/Artifact refs，使用 fresh T03 identity 复编译后 digest 从 `906111…c953` 变成 `b9cc74…e085`，因此“完全匹配旧 digest”和“fresh identity”目前不能同时成立；同时 T02 的 capture 保留是执行器内存累积、Runtime 在正常返回或捕获异常后再统一终态化，尚无 0.1.2 S3 专用的单次签发/监督 runner，也未证明每个 Provider 响应在解析校验前已耐久落盘。两项合并登记为 `RC-P36-106`，归 S3-T03 执行控制，不重开 S0–S2，也不归因 DeepSeek。

当前下一项严格限定为：

`FIN-0.1.2-S3-T03-NVDA-FRESH-IDENTITY-INPUT-BOUNDARY-BOUND-RUNNER-ATOMIC-CAPTURE-TERMINAL-SUPERVISION-AND-ZERO-CALL-PREFLIGHT-MINIMUM-IMPLEMENTATION`

该项只能在一个零调用收敛包中分离稳定业务输入摘要与 identity-bound execution envelope，并完成 runner/原子 capture/终态监督和预算 preflight；不得读取凭据、签发 admission 或执行 exact-live。通过后本次 conditional authority 才具备执行资格，但仍需新的用户续行才能签发并启动真实 attempt。

## 七、post-admission execution authority 复核

fresh identity、稳定业务摘要、capture-first runner library 与 admission issuance 已完成；admission=`eed177…d1c8`，当前仍为 issued/unconsumed，runtime root 与 execution identity 未 claim。Project OS 对 exact-live scope 返回 pass/open blockers 0，credential 只检查存在性且为 true，未读取值或 probe Provider。

但 execution authority 复核发现，现有 `fin_0_1_2_s3_t03_exact_live_runner.py` 只暴露库函数：它没有 admission-bound child command、DeepSeek transport 装配、父进程 launch/wait/timeout/exit supervisor，也没有真实父进程在子进程异常退出后自动调用 terminal recovery。现有测试由测试代码直接调用 recovery 函数，不能替代可执行监督路径。若此时启动 live，只能在执行轮临时拼装未审计入口，违反 exact-once 与 crash-terminalization 的既有要求。

该缺口登记为 `RC-P36-107-fin-0-1-2-s3-t03-bound-live-launcher-and-parent-supervisor-entrypoint-gap`，仍归 S3-T03；不重开 S0–S2，不归因 DeepSeek，也不改变 S3 的 T01–T04 任务结构。当前 execution authority fail-closed，admission 不失效。

当前下一项严格限定为：

`FIN-0.1.2-S3-T03-NVDA-BOUND-EXECUTION-LAUNCHER-PARENT-SUPERVISOR-AND-ZERO-CALL-PREFLIGHT-MINIMUM-IMPLEMENTATION`

只允许一个零调用实现包，将现有 runner core 接成单一 child command 与真实 parent supervisor，并证明 admission、fresh root、预算、retry-zero、timeout、异常 exit recovery 和 provider callback=0。不得修改模型 surface、业务 input 或财务合同，不得同轮消费 admission 或调用 DeepSeek；完成后 exact-live 仍需新的用户续行。

## 八、bound launcher / parent supervisor 实现结果

唯一零调用连接包已经完成。仓库现在有一个 admission-bound child command，负责在本地重新校验 admission、issuance、execution envelope 和 frozen exact input，并只在这些条件通过后装配既有 DeepSeek transport；另有一个真实 parent supervisor，在启动前原子 claim exact identity，只启动一个直接 child，执行 900 秒 timeout、异常退出恢复、stdout/stderr 内容哈希与 launch/exit receipt。

CLI 预检真实启动了一个本地 child 并重建 exact input，但 provider callback、模型、Provider 和执行网络均为 0。独立子进程 fault injection 证明了异常 exit 和 timeout 都会自动生成 typed terminal，第二次 identity claim 与 supervision root 重用都会 fail closed，凭据值不会进入日志或 receipts。旧 issuance 仍保持原始 runner SHA；本实现以新的不可变记录声明当前 runner 为受控安全后继，后续 execution authority 必须同时绑定当前 runner 和 launcher 字节，不能只复用签发时的旧代码绑定。

`RC-P36-107` 因真实可执行监督路径的零调用证明而关闭。admission 仍为 issued/unconsumed，target runtime root 仍不存在，S3-T03 execution 未开始。当前 exact input 仍是内部 frozen NVDA dogfood fixture，因此这一步不是外部用户查询、live source、自然模型输出、九件套产品、paired 增益或 Owner acceptance 证明。

当前下一项严格限定为：

`FIN-0.1.2-S3-T03-NVDA-EXACT-LIVE-EXECUTION-AUTHORITY-DECISION-R2`

该下一项仍是零调用权限复核：重新验证当前 runner/launcher hashes、Project OS blocker、fresh target/supervision roots、credential presence、预算与 retry-zero。它不得同轮消费 admission 或启动 DeepSeek；真实 exact-live 仍需之后新的用户续行。

## 九、exact-live execution authority R2

R2 零调用资格复核已经通过。immutable admission、issuance、受控后继 runner、launcher 与 launcher/supervisor implementation 的当前字节全部匹配；Project OS 对 R2 scope 返回 pass/open blockers 0。真实本地 child preflight 再次完成 frozen exact input 重建和 executor/transport wiring，但 provider callback、模型、Provider 和执行网络均为 0。

credential 只检查存在性，未读取值、未 probe Provider、未进入命令、日志或 receipt。target runtime root 与未来 supervision root 在复核前后都不存在；admission 仍为 issued/unconsumed，execution identity 未 claim。

R2 只授权在新的用户续行后执行一次 supervised exact-once：最多 9 次 DeepSeek Pro Provider calls，60k input、10k output、USD 0.06、900 秒，每次最多一个 transport attempt，retry/fallback/provider hopping/prompt-only retry 均为 0。首个可信失败立即停止并物化 typed terminal；成功必须形成 3 个 local Fact receipts、9 份 restricted capture 与 9 个业务 Artifacts。execution turn 不自动进入 paired、Owner 或 S3-T04。

当前下一项为：

`FIN-0.1.2-S3-T03-NVDA-EXACT-LIVE-EXECUTION-AND-TERMINAL-MATERIALIZATION`

该执行已具备条件授权，但仍必须由用户新的“继续”触发。当前 tracked exact input 仍是内部 frozen NVDA dogfood fixture；因此即使运行成功，也必须在 S3-T04 单独判断产品研究价值，不能仅凭执行成功宣布 NVDA R2。

## 十、primary exact-live terminal failure 与阶段归属

用户新的“继续”满足独立续行条件后，唯一 primary admission 已 exact-once 消费。真实 parent supervisor 启动一个 child，6 个 Specialist Provider segments 与第 7 次 Research Lead 调用均完成 `ok/stop`；Research Lead 本地语义校验随后以 `s3_bounded_research_lead_v3_semantic_fact_presence_summary_mismatch` typed terminal 停止。共保留 3 份 local Fact receipts、7 份 restricted captures、0 个业务 Artifacts；tokens=`37,107/2,310/39,417`，估算成本=`USD 0.01815124`，无 retry、fallback、replay、relaunch 或 replacement。失败输出没有晋升业务层，terminal 和 supervisor receipts 均完整物化。

受限审计显示并非 Provider transport 或 JSON 失败。真实 Claim 支撑关系为 C001=0、C002=0、C003=3、C004=0，但 Lead 把同一 value cell 内 C003 的事实与 bounded-inference 语义多处赋给 C002：两个 conflict row 的 summary 与 narrative 均因此错误，dependencies/gaps 也出现相同别名互换迹象。模型的字段级 semantic error 成立。

项目同时存在更早责任：FIN 0.1.2 当前 admission 绑定的是 Lead-v6，它把完全可本地计算的 `fact_presence_summary` 再次交给 Provider；而 FIN 0.1 S4-T06 的 RC-P36-078 已经用 Lead-v7 本地 materialization 做过 exact-live 正证明。当前 consolidated contract 没有把该已证明边界继承进来，也没有覆盖同一 cell 相邻 Claim alias 互换负例。因此登记 `RC-P36-108`，归 S3-T03 合同继承与 Lead semantic boundary；不重开 S0-S2，也不能只通过换一个 enum 或加一句 prompt 宣布修复。

当前下一项严格限定为：

`FIN-0.1.2-S3-T03-NVDA-RESEARCH-LEAD-LOCAL-FACT-PRESENCE-AND-CLAIM-ALIAS-SEMANTIC-OWNERSHIP-REGRESSION-DISPOSITION-DECISION`

下一项只做一次零调用处置：对账 Lead-v7 已证明资产与 FIN 0.1.2 当前合同继承，并决定防止 C002/C003 语义互换所需的最小本地 projection 或有限 Claim-role atom。不得改写本次失败、自动切换合同、签发 replacement admission、调用模型、paired、Owner 或进入 S3-T04。只有处置之后另行授权的单一 consolidated implementation、独立 proof、fresh admission 和 execution authority 全部成立，才可能讨论新的 live；不能回到逐字段循环。

## 十一、隔离 collect-all diagnostic 与 Lead-v8 结构修复

Owner 明确要求先修当前 blocker，再让 DeepSeek Pro 继续 Writer/Verifier，以一次隔离诊断尽量暴露后续链路问题。该授权没有改写 primary failure：正式 R1 仍是 7 calls、0 Artifacts 的 immutable failure，原 admission 没有再次消费，原 runtime tree digest 前后均为 `651b21…30ee`。

诊断精确重放 7 份受限 capture，只在隔离分支对 Research Lead 的 C002/C003 语义互换做一次路径级本地修复，然后真实调用 Writer 与 Verifier 各一次。两次均为 DeepSeek Pro、`ok/stop`、transport attempt=1；新增 tokens=`23,294/657/23,951`，成本=`USD 0.01070448`，无 retry/fallback/relaunch。Writer 与 Verifier 均自然通过现有合同，诊断形成 9 份 quarantined Artifacts；没有 downstream local repair、业务晋升、paired 或 Owner acceptance。因此，全链诊断没有发现新的下游 L1 合同阻塞，当前 T03 首因仍收敛在 Research Lead semantic ownership。

同时诊断暴露三项产品质量债务，但它们归 T04，不能继续塞回 T03：当前 frozen NVDA fixture 使四个 Claim 中三个保持 `cannot_infer`；最终本地 renderer 仍会露出 `__company_total__`、`FY2025-FY`、重复 `USD` 和粗糙拼接；Verifier 当前验证 Lead/Writer 对象，却没有看到最终本地渲染的 delivery preview，因此它的 `visual_delivery=pass` 不能替代最终成品检查。

T03 的合并结构修复已实现为 Research Lead-v8。v8 继承 v6 的 deterministic gap projection 与 v7 的 local fact-presence materialization，并进一步冻结权限：Provider 只选择 Claim/WWC 关系 alias；Claim 证据状态叙事、conflict fact presence、resolution status、gap projection、行 ID 和 scoped identity expansion 全部由本地 Claim Card 确定性生成。Provider 原始叙事仍保留在受限 capture 中用于审计，但不再成为 canonical Artifact 内容。v1.3 common Runtime binding 不变，因为它只拥有 Specialist judgment atom family；Lead 有独立的 transport version，不能为修 Lead 而改变 frozen Specialist business input。

零调用证明已覆盖：当前 NVDA full-fake 九件套、Provider 越权返回 runtime-owned field 的负例，以及把这次自然失败的 Lead 正文直接送入 v8。后者没有手工交换 C002/C003；v8 仍把所选 C002 正确渲染为 `cannot_infer`，并把 C001+C002 计算为 `no_facts_present`，证明模型关系选择即使质量不佳也不会再升级为 L1 假事实。这建立 `engineering_pass`，不建立正式 T03 pass。

当前下一项严格限定为：

`FIN-0.1.2-S3-T03-RESEARCH-LEAD-V8-LOCAL-SEMANTIC-MATERIALIZATION-INDEPENDENT-ZERO-CALL-PROOF-DECISION`

必须先由独立 fresh proof 复证 v8 与当前 frozen input、mutation 和九件套路径；之后才可另行签发 fresh replacement admission 与一次 execution authority。新的 live 仍需用户明确续行。若 replacement 出现新的 L1，S3 honest-block，不进入第三轮修补；L2–L4 继续归 T04。

## 十二、Lead-v8 独立 fresh proof 结果

独立复证已在两个不同 disposable root、两个新进程中执行；两个进程启动前清除 credential 环境，阻断外部 socket 网络，归一化输出一致。复证没有读取正式失败 capture、没有复用 collect-all diagnostic repair callback，也没有调用模型或 Provider。

两份进程均以当前 tracked NVDA input 到达 `6 nodes / 12 logical interactions / 3 local Fact receipts / 9 fake Provider calls and captures / 9 Artifacts`。相邻 alias mutation 令 Provider 选择 C002 及 C001+C002 并附带虚假 facts/resolved 叙事，但 canonical 输出仍由本地 Claim Card 生成真实 evidence-state、fact-presence 与 `unresolved`，Provider 叙事未进入 Artifact。runtime-owned field、未知 alias、重复 alias 三类 mutation 均在 Research Lead 阶段 fail closed；v6 gap projection 与 v7 fact-presence truth table 历史回归保持。

该结果只建立 Lead-v8 engineering proof。primary R1 仍为 immutable failed，RC-P36-108 尚未关闭；没有 replacement admission、DeepSeek call、paired、Owner 或 T04。当前下一项严格限定为：

`FIN-0.1.2-S3-T03-NVDA-REPLACEMENT-EXACT-LIVE-FRESH-ADMISSION-AUTHORITY-DECISION`

下一项只做零调用权限复核，不能同轮签发或消费 admission。未来 replacement exact-live 仍需之后新的用户续行；若出现新的 L1，S3 honest-block 且不存在第三次 exact。

## 十三、replacement fresh admission authority decision

零调用权限复核没有授权签发 replacement admission。Lead-v8 proof、implementation binding、primary immutable failure 和稳定业务输入均重新匹配，Project OS 对 decision scope 也为 pass；但 admission schema 可编译不等于存在可签发 payload。

现有 execution envelope、issuer 和 parent supervisor 都精确绑定已经消费的 primary R1。只读编译观察虽然得到 Lead-v8 profile-admissible candidate，但其 prepared execution identity 仍是历史 `fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1`，input digest=`906111…c953`；它没有 fresh replacement envelope、predicted WorkUnit/Attempt/Run 或 replacement supervision binding，因此明确标记为 non-issuable，digest 不得用于未来签发。登记 `RC-P36-111`，属于 S3-T03 execution-control binding，不是模型或 Provider 问题，也不重开 S0–S2。

为避免重复“先签 admission、后发现 supervisor 不可消费”的时序错误，下一项限定为一个零调用 controlled-successor bundle：一次生成 fresh replacement identity/envelope、精确 Lead-v8 admission payload、replacement-only atomic issuer、绑定该 payload/envelope/authority/code hashes 的 parent supervisor 与 provider-callback=0 child preflight，同时保持 primary R1 runtime 和失败证据字节不变。bundle 上限为 1；通过后仍需重新做一项独立 admission authority decision，不自动签发。bundle 失败则 S3-T03 honest-block，不存在第二包或第三次 exact。

当前 next：

`FIN-0.1.2-S3-T03-NVDA-REPLACEMENT-ADMISSION-ENVELOPE-ISSUER-SUPERVISOR-CONTROLLED-SUCCESSOR-MINIMUM-ZERO-CALL-IMPLEMENTATION`

本轮 admission issued/consumed、credential、model/provider/network、source/tool、Run/Artifact、paired/Owner/S3-T04 均为 0；下一实现项尚未授权。
