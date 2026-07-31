# 529 FIN 0.1.2 S1 realistic three-case deterministic vertical StagePlan

日期：2026-07-31
状态：`S1_T02_G1_pass_T03_ready`

## 本轮结果

完成 S1-T01 StagePlan，G0 通过；G1/G2/G6 尚未执行。冻结 S1 为一个零调用确定性纵切阶段：迁移一个 bounded judgment-atom family 的十个真实生产 consumer，再用 DELL/MU/NVDA 九个 Case-Cell 对完成正向、mutation、permutation、collect-all、full-fake 与失败留存证明。

机器可读计划：`configs/releases/fin_ia_0_1_2_s1_realistic_three_case_deterministic_vertical_stage_plan_v1_0.json`。

架构说明：`docs/architecture/repository/FIN_0_1_2_S1_REALISTIC_THREE_CASE_DETERMINISTIC_VERTICAL_STAGE_PLAN_20260731.zh-CN.md`。

## 审计发现

1. S4 已有数值 authority、案例 identity、时间 alias、Claim support、WWC/Fact candidate selection、capture-v2 和 typed terminal result 等可复用实现；S1 不应重新逐字段开发。
2. S0 source 目前仍是 governance source，实际 Runtime 的十个 consumer 尚未统一绑定 FIN 0.1.2 contract ID/version/source digest。
3. T05/T06 的 fake 与局部测试存在“过于配合”的历史：清洗 ticker、只给合法候选、没有自然日期或没有最终 Artifact 对应突变。S1 必须用 realistic fixture 集中补齐。
4. 最新 issue 真值要求区分有限迁移与通用 compiler：RC-P36-083 的 generalized cross-family compiler 仍在 FIN 0.2；S1 只迁移并回归保护当前 bounded family。
5. DELL/MU 金融方法可以在 S1 声明 fixture 级 runtime slot/node consumption，不能声明 paid product 或 Human acceptance。

## 固定边界

- S1 最多 T01–T04，不允许 S1-T05 或 R-number 家族。
- T02 一个实现包；T03 一个零调用 proof package；T04 一个 closeout package。
- S1 不调用模型/Provider，不签发 admission，不生成 business Run/Artifact。
- DELL/MU R2、post-transfer NVDA 和 R3 保持 S4 owner。
- 新 shared L1 在 S1 closeout 后阻断下一阶段，不在 S1 内无限维修；L2–L4 正常后传。

## 验证

StagePlan 专项 `12 passed`；与 S0 current manifest、T10/S5/0.1.1 immutable event 和 T07 historical audit 合并回归 `36 passed`。覆盖 parent hash、G0–G6、十 consumer、三案九 Cell、候选数量、负向 mutation、根因归属、artifact/run budget、方法/模式非膨胀和 backlog/current context 投影。验证中唯一先发失败是 S0 current-projection 仍指向已完成的 StagePlan；已只更新可变 projection 测试为“S0 handoff 已消费、当前进入 T02”，未改写 S0 决策或历史 closeout。

本轮 credential/model/provider/business-network/admission/Run/business Artifact/paid reproof 均为 0。

## 下一项

`FIN-0.1.2-S1-REALISTIC-THREE-CASE-FIXTURE-MUTATION-COLLECT-ALL-FULL-FAKE-ZERO-CALL-PROOF`

## S1-T02 有界生产 consumer 迁移

T02 已完成唯一实现包，没有拆出逐字段补丁，也没有建立新的 T05 或 R-number 家族。新增 mandatory family binding，把 FIN 0.1.2 contract ID、version、规范化 source digest 和十个 consumer receipt 同时注入 admission、模型可见 prompt contract、server schema、local validator、fake provider、selector、renderer、capacity、budget、typed failure 与 capture index。历史 S4 contract refs 仍兼容，但不得混入 FIN 0.1.2 binding 字段；新 ref 若省略或漂移 binding/digest，会在 consumer 使用前 fail closed。

实现审计确认两处 T01 计划表述需要在当前证据层校正，但不应重写已冻结的 StagePlan：

1. `capture_index` 的实际方法 owner 是 `DeepSeekS3ThreeCellNodeExecutor._provider_interaction_capture`，不是计划里的概念名 `BoundedAgentExecutor._provider_interaction_capture`。binding manifest 和 Runtime 已按真实 owner 绑定。
2. StagePlan 中 `source_digest_must_equal=b9a0...283f` 实际是源文件物理 SHA-256；Runtime admission/consumer 使用的规范化语义 digest 是 `e2b8...7cd9`。两者现在同时留存并明确区分。

专项测试为 `18 passed`，覆盖 source file/canonical digest/contract ID/version/十 consumer owner、omission、drift、旧新 ref 混用、case-specific owner、budget、DELL/MU/NVDA full-fake、post-Provider failure capture/typed-failure receipt、StageCapsule 与 current projection。三案当前各达到测试内存路径 `6 nodes / 12 interactions / 12 captures / 9 diagnostic Artifacts`；这些不是 business Run 或产品 Artifacts。历史行为回归为 `39 passed, 1 deselected`；被排除的一项是历史 v2 implementation artifact 对旧代码字节 hash 的 immutable snapshot 断言，当前行为没有失败，历史 artifact/test 也未为求绿而改写。T01/S0/T07/T10/S5/0.1.1 current-boundary 与 T02 合并回归最终为 `54 passed`。

StageCapsule：`configs/releases/fin_ia_0_1_2_s1_stage_capsule_v1_0.json`。G1 已通过，G2 留给唯一 T03 realistic three-case proof package；G3/G5 仍不属于 S1，G6 留给 T04。credential/model/provider/business-network/admission/Run/business Artifact/paid reproof 均为 0，DELL/MU R2、post-transfer NVDA、NVDA R3 与 FIN 0.1 release truth 均未改变。
