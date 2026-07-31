# FIN 0.1.1 / 0.1.2 版本谱系与发布节奏决策

日期：2026-07-31
状态：`accepted_product_lineage / FIN_0_2_definition_preserved`

## 1. 产品大方向不变

原产品路线继续保持：

```text
FIN 0.1 bounded internal research workflow
  -> FIN 0.2 Earnings Review Alpha
  -> FIN 0.3 Review & Memory Beta
  -> FIN 0.4 Cross-sector Beta
  -> FIN 0.5 Enterprise Pilot
```

本次新增的 0.1.1 和 0.1.2 是 FIN 0.1 内部工程迭代号，不重新定义产品路线，也不把原本属于 Earnings Review Alpha 的 FIN 0.2 改成“偿还第一版架构债”。

## 2. 版本定义

| 版本 | 定位 | 包含 | 不包含 |
| --- | --- | --- | --- |
| FIN 0.1.1 | 第一轮 S0–S5 的内部工程基线 | NVDA historical R2、DELL/MU transfer diagnostics、完整 immutable evidence、S4 honest block、S5 decision-only、仓库/rollback manifest | 三案 R2、NVDA R3、release qualified、生产 |
| FIN 0.1.2 | 同一 FIN 0.1 产品范围的稳定化与 transfer qualification | compiled contract、provider surface reduction、完整 capture/hermetic proof、DELL/MU R2 reproof、post-transfer NVDA、R3、release slice | Earnings 新产品功能 |
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

## 4. FIN 0.1.2 的使命

FIN 0.1.2 不从 S4/T06 继续打补丁。它从 S0 重新执行“门禁验证”，但不是从零重写：

- 合同 hash、truth owner 和 proof type 仍匹配的资产可以 carry forward；
- 仅有声明、fixture 或旧 mutable-state binding 的证据必须重验；
- S0–S3 先关闭共同架构和模型能力边界；
- S4 只做冻结 Runtime 上的 transfer product proof；
- S5 只做 release engineering 与 decision。

### 4.1 0.1.2 必须完成

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

### 4.2 0.1.2 不应再发生

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

因此 0.1.2 是进入 FIN 0.2 前的工程稳定化，不是 FIN 0.2 本身。只有 Earnings 特有的新任务模板、财务/segment/guidance 方法和交付面进入 0.2。

通用 Runtime、contract compiler、DELL/MU transfer completion、proof hermeticity 和基础 Verifier 语义属于 FIN 0.1 未完成的质量承诺，不能用版本号平移来掩盖。

## 6. 当前执行顺序

```text
FIN-0.1 repository evidence freeze + safe classification
  -> S4-T10 honest-block closeout
  -> S5 decision-only honest-block
  -> freeze FIN 0.1.1 internal baseline
  -> FIN 0.1.2 S0–S5 with refined gates
  -> FIN 0.2 Earnings Review Alpha
```

当前唯一下一项：

`FIN-0.1-REPOSITORY-EVIDENCE-FREEZE-AND-SAFE-CLASSIFICATION-EXECUTION`

该动作只能生成内容寻址 inventory、分类和建议的 commit/rollback slices；不删除、不取消暂存、不提交、不打 tag，任何清理动作必须在 exact target list 形成后另行批准。
