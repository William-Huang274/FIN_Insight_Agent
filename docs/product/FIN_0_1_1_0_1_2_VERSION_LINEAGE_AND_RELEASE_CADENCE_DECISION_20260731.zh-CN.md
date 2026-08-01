# FIN 0.1.1 / 0.1.2 / 0.1.3 / 0.1.4 版本谱系与发布节奏决策

日期：2026-07-31
更新：2026-08-02（FIN 0.1.3 正式冻结并设立 FIN 0.1.4 S0 bounded qualification patch）
状态：`accepted_product_lineage / FIN_0_1_3_frozen_internal_honest_block / FIN_0_1_4_S0_stage_plan_ready / FIN_0_2_definition_preserved`

## 1. 产品大方向不变

原产品路线继续保持：

```text
FIN 0.1 bounded internal research workflow
  -> FIN 0.2 Earnings Review Alpha
  -> FIN 0.3 Review & Memory Beta
  -> FIN 0.4 Cross-sector Beta
  -> FIN 0.5 Enterprise Pilot
```

本次新增的 0.1.1、0.1.2、0.1.3 和 0.1.4 是 FIN 0.1 内部工程迭代号，不重新定义产品路线，也不把原本属于 Earnings Review Alpha 的 FIN 0.2 改成“偿还第一版架构债”。0.1.4 只接收 0.1.3 未完成的共同 Runtime/hermetic 与 proof-lifecycle 质量承诺，不增加新产品功能。

## 2. 版本定义

| 版本 | 定位 | 包含 | 不包含 |
| --- | --- | --- | --- |
| FIN 0.1.1 | 第一轮 S0–S5 的内部工程基线 | NVDA historical R2、DELL/MU transfer diagnostics、完整 immutable evidence、S4 honest block、S5 decision-only、仓库/rollback manifest | 三案 R2、NVDA R3、release qualified、生产 |
| FIN 0.1.2 | 同一 FIN 0.1 产品范围的第一次稳定化尝试；现已冻结为 internal honest block | compiled contract、provider surface reduction、capture/hermetic 结构与失败证据；S0C terminal failed、S2 未进入 | release qualified、三案 transfer qualification、Earnings 新产品功能 |
| FIN 0.1.3 | hermetic Runtime dependency closure 与 proof-control-plane 稳定化尝试；现已冻结为 internal honest block | 单一 RuntimeResourceRegistry、typed reference role/environment parity、v3 pre-consumption control-plane 工程实现、不可变失败与终态证据 | 已完成 eligibility/host/formal proof、RC-P36-090–096 closure、新产品功能、历史 proof 重跑、同版本 Exit Contract v4、自动 0.1.4、Earnings 功能 |
| FIN 0.1.4 | FIN 0.1 最后一次有界共同 Runtime qualification patch；当前仅 S0 StagePlan ready | proof lifecycle 状态机、immutable event/current projection 分离、RC-P36-090–096 原样重验、最多一个实现包/一个 host proof/一个双-disposable formal package | 新产品功能、0.1.3 v4/retry、模型比较、自动 0.1.5、Earnings 功能 |
| FIN 0.2 | 原定义的 Earnings Review Alpha | B1、Earnings Task/Workpaper/Report、精确三表、segment、guidance、同比环比、市场反应与反方 | 为 0.1 未完成的通用 Runtime 基线兜底 |

## 3. FIN 0.1.1 的冻结语义

FIN 0.1.1 只能在以下顺序完成后冻结：

1. 当前仓库 evidence freeze 和安全分类；
2. S4-T10 honest-block closeout；
3. S5 `decision_only_honest_block`；
4. exact package、完整 logs、Git slice/rollback 和 issue ledger manifest；
5. 明确写入 `FIN_0_1_release_qualified=false`。

建议内部标签为：

`fin-0.1.1-internal-honest-block`

本次决策不创建 tag、不提交、不删除或取消暂存。标签只能在仓库恢复和 S5 decision 完成后创建。

FIN 0.1.1 的价值是保存一条真实、可追溯的工程基线，而不是把 blocked 改写成 pass。它证明：

- 一个 owner-accepted NVDA anchor；
- DELL/MU 两条真实 transfer diagnostic；
- 真实模型增益、失败模式、成本和 27 个 coherent Agent Artifact 的对照证据；
- canonical terminal truth、capture、paired review 和 Human evidence disposition；
- 当前为什么不能 release。

## 4. FIN 0.1.2 的原始使命与终态

FIN 0.1.2 不从 S4/T06 继续打补丁。它从 S0 重新执行“门禁验证”，但不是从零重写：

- 合同 hash、truth owner 和 proof type 仍匹配的资产可以 carry forward；
- 仅有声明、fixture 或旧 mutable-state binding 的证据必须重验；
- S0–S3 先关闭共同架构和模型能力边界；
- S4 只做冻结 Runtime 上的 transfer product proof；
- S5 只做 release engineering 与 decision。

截至 2026-08-01，0.1.2 已在 S0C 唯一双-disposable proof 的 collection 阶段终态失败，implementation/proof budget=`1/1` 已耗尽。它冻结为 `internal honest block / release qualified=false / S2 not entered`，不得通过 S0D、H、R 或第二 proof package 改名续跑。下列未完成目标原样转交 0.1.3，不因版本推进而降级。

### 4.1 0.1.2 未完成、由 0.1.3 原样继承的承诺

- 一个 source 编译 prompt、server schema、local validator、fake、selector、renderer、budget 和 capture index；
- material number/date/identity/ID/lineage 本地确定性 owner；
- DeepSeek 只消费 request-local alias/enums 和 bounded judgment atoms；
- 真实最大候选数、自然 ISO 日期、跨案污染、排列、duplicate 和 output-capacity mutation；
- 完整 request/final output/call metadata/capture ref/terminal result；
- DELL、MU、NVDA current Runtime all-green；
- DELL/MU R2；
- post-transfer NVDA exact product；
- 真实 qualified-senior NVDA R3；
- coherent commit manifest、rollback、hermetic package 和 RG1–RG5 decision。

### 4.2 后续 FIN 0.1.x 不应再发生

- 在 S4 为共同 Runtime 新建 R2–R11；
- 每个字段分别 live 一次；
- fake 通过就假定自然模型会遵循数量/字符/跨字段约束；
- 一个工程修复分别生成 scope、authority、admission、proof、result、disposition 六套文件；
- immutable 历史测试绑定 mutable `current_next`；
- 将“Agent 有增益”解释成 L1 或 owner acceptance；
- 因 FIN 0.1 未收敛而改写 FIN 0.2 产品定义。

## 5. FIN 0.2 的入口仍按原路线

FIN 0.2 的进入条件仍为：

> `FIN 0.1 Runtime and exact artifact mainline stable`

因此 0.1.2/0.1.3/0.1.4 是进入 FIN 0.2 前的 FIN 0.1 工程稳定化 patch line，不是 FIN 0.2 本身。只有 Earnings 特有的新任务模板、财务/segment/guidance 方法和交付面进入 0.2。

通用 Runtime、contract compiler、DELL/MU transfer completion、proof hermeticity 和基础 Verifier 语义属于 FIN 0.1 未完成的质量承诺，不能用版本号平移来掩盖。0.1.3 必须在 Project OS 中继续绑定同一四项 open blocker 和同一产品 non-inflation truth，不能把 0.1.2 的失败改写成 pass。

## 6. 当前执行顺序

```text
FIN-0.1 repository evidence freeze + safe classification
  -> S4-T10 honest-block closeout
  -> S5 decision-only honest-block
  -> freeze FIN 0.1.1 internal baseline
  -> FIN 0.1.2 S0/S1/S0C terminal internal honest block
  -> FIN 0.1.3 S0 terminal internal honest block
  -> FIN 0.1.4 S0 bounded proof-lifecycle and hermetic qualification
  -> FIN 0.1.4 S1–S5 only after S0 pass
  -> FIN 0.2 Earnings Review Alpha
```

截至 2026-08-01，FIN 0.1.3 S0 的 v2 reference-role implementation 已工程通过；v2 唯一 host proof 因 proof manifest policy enum 与 shared compiler 不一致，在 import/collect/pytest 前终态失败。v2 observed=`1 implementation / 1 host / 0 formal`，RC-P36-090–095 均继续 open，S1/S2 未进入，模型调用为 0。

Owner 项目级决策继续保留 FIN 0.1.3 为唯一当前主线，不自动创建 0.1.4。v1/v2 StagePlan、proof 结论和预算保持不可变；同一 S0 下建立最后一次 `fin_0_1_3.S0.exit_contract:v3`，只修 proof policy 单一来源与 host 消费前 exact-boundary eligibility。v3 不重做金融 Runtime，固定 `[implementation, eligibility, host, formal]` 各最多一次；任一新结构失败都冻结 FIN 0.1.3，禁止同版本 v4。

v3 proof-control-plane 最小实现已工程通过，observed=`[1 implementation, 0 eligibility, 0 host, 0 formal]`。实现建立了唯一 policy source、manifest/compiler 同源编译、content-addressed eligibility attestation 与 host pre-consumption recompute boundary；它不是 clean-head eligibility、host/formal proof 或金融产品验收。

2026-08-02 的授权前 exact transition audit 发现冻结 runner/active manifest 只接受授权前 pending projection，不能接受授权后必须成为 current truth 的 `eligibility_authorized_not_executed`。诚实推进会以 `current_v3_projection_status_invalid` 在 eligibility 前停止；保留 pending 会造成 split-brain；修改 runner 会超过唯一 implementation budget。按上文已经冻结的 terminal/no-v4 规则，没有签发 eligibility authority，也没有执行 eligibility、host/formal proof。observed 保持 `[1,0,0,0]`，eligibility budget 未消费，RC-P36-090–095 继续 open并新增 RC-P36-096。FIN 0.1.3 因此冻结为 internal honest block，S1/S2 未进入，模型调用为 0。

版本处置选择正式冻结 FIN 0.1.3，不重开 v4，也不把 RC-P36-090–096 转交 FIN 0.2。新建 FIN 0.1.4 作为 FIN 0.1 最后一次有界共同 Runtime qualification patch，但本次只建立 S0 StagePlan 入口，不写实现、不运行 proof。0.1.4 必须把 proof lifecycle 明确建模为可编译状态机，在任何 authority 或 budget consumption 前证明 `planned → implementation_pass → eligibility_authorized → eligibility_pass → host_authorized → host_pass → formal_authorized → terminal` 全部合法；immutable event snapshot 与 mutable current projection 必须分离，禁止再用历史测试拥有 current truth。

FIN 0.1.4 复用 0.1.3 中 hash-compatible 的 RuntimeResourceRegistry、六角色 reference taxonomy、typed environment、proof policy 和 deterministic three-case 资产，但不得把 0.1.3 的工程通过写成 0.1.4 proof。未来 S0 预算固定为一个 StagePlan、一个 implementation bundle、一个 host engineering proof 与一个双-disposable formal package；无自动 T05/R/H/replacement 或 FIN 0.1.5。S0 通过后才可进入既有 S1–S5 产品主轴。

当前唯一下一项：

`FIN-0.1.4-S0-PROOF-LIFECYCLE-STATE-MACHINE-AND-HERMETIC-QUALIFICATION-STAGE-PLAN`

该动作只允许冻结 FIN 0.1.4 S0 的问题、状态机、任务、预算、证明顺序和停止条件。它不得自动写 Runtime/runner、执行 eligibility/host/formal、进入 S1/S2、读取凭据或调用模型。FIN 0.2 Earnings Review Alpha 的产品定义保持不变。
