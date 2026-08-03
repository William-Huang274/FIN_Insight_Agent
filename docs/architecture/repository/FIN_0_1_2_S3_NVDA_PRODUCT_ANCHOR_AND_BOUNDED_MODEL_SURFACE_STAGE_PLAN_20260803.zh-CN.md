# FIN 0.1.2 S3：NVDA 产品锚点与有界模型 Surface 计划

日期：2026-08-03
状态：`S3-T01 pass / S3-T02 engineering pass / S3-T03 admission issued-unconsumed / exact-live authority blocked by executable launcher-supervisor gap / zero model calls in authority turn`

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
