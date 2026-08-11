# FIN 0.1.2 S2-T03 WWC v1.2 合并零调用实现

日期：2026-08-03
状态：`engineering pass / independent proof pending / replacement pair not authorized`

## 做了什么

按已批准的唯一 repair bundle，新建 S2 v1.2 source、binding 和三资源 registry，未修改 v1.1 历史文件。cadence/date 跨字段规则只有一份声明，并被模型可见合同、wire schema、system instruction、本地 validator、fake 与 typed failure 共同消费。

最终 WWC task 不再读取候选循环结束时残留的 Claim，而是从当前 selected atom 展开。多候选 permutation 测试又发现 `authority_refs` 也读取了同一个外层残留列表；它不是新功能需求，而是 RC-P36-103 同一个 loop-state-leak 的第二表现，因此在同一包内改为从当前 atom 展开，没有开启第二修复轮。

## 证据

- S2 compiler + WWC focused：`31 passed / 0 failed`；
- S1 realistic、旧 S4 compiler、S2、T03 相关回归：`138 passed / 0 failed`；其中旧 v1.1 admission 明确 fail-closed，不可复用于 v1.2；
- DELL/MU/NVDA full-fake：各 `6 calls / 6 pass`；
- 日期正向：每个 allowed alias + `bound_date`，所有非 bound cadence + `NONE`；
- 日期负向：`bound_date+NONE`、非 bound+已知 alias、cross-case alias 均 typed fail 且 capture-first；
- Claim/Authority：one/multi Claim、provider reorder、稳定选择、6→3 subset 均逐 task 对应；
- 真实受限 Pro capture（digest=`7f6fd685...f83ddc`）零调用重放后，raw `Q001/Q002/Q001` 最终覆盖两个正确 Claim ID；
- 新 WWC request/equivalence digest=`0c52c9ab...81c2 / 543836b6...de90`，Flash/Pro 逐字节相同；
- credential/model/Provider/network/replacement/business Run/Artifact=`0`。

## 边界与反思

旧 S4 changed-family canary runner 的 3 个 `canary_exact_template_drift:specialist_fact_atoms` 在本轮起点 clean HEAD=`2dba2e9a` 也可复现，所以不是 v1.2 引入。不能为了全绿改写历史 authority，也不能把它塞进当前 S2 comparator 包；已在实现结果中明确列为 pre-existing stage 外债务。

这次矩阵证明，逐字段单例测试仍不足以发现循环状态泄漏；必须把 multi-row、permutation、subset 和最终 lineage correspondence 作为 compiled-contract 的固定验收面。另一方面，历史冻结请求与新合同必须通过版本门隔离，不能让一个局部比较器修复静默改变旧 exact authority。

RC-P36-102/103 只推进到 `implementation pass / independent proof pending`，尚未关闭。当前没有公平 WWC 模型证据，T04、模型选择、S3 和 release 均未解锁。

## 下一项

`FIN-0.1.2-S2-T03-WWC-V2-INDEPENDENT-ZERO-CALL-PROOF-AND-AFFECTED-FAMILY-REPLACEMENT-PAIR-AUTHORITY-DECISION`

下一项只允许独立零调用复证并决定是否另行签发最多 2 次 MU WWC replacement authority；不在同一项执行模型调用，不重跑 Fact/Claim。
