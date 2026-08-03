# FIN 0.1.2 S3：NVDA 产品锚点与有界模型 Surface 计划

日期：2026-08-03
状态：`S3-T01 pass / S3 entered / S3-T02 pending / zero model calls`

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

## 六、当前入口

S3-T01 已通过并进入 S3；S3-T02 尚未获本轮实现权限。当前下一项：

`FIN-0.1.2-S3-T02-NVDA-BOUNDED-SURFACE-PRODUCTION-RUNTIME-INTEGRATION-AND-ZERO-CALL-PRODUCT-READINESS-IMPLEMENTATION`
