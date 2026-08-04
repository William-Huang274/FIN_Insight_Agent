# FIN 0.1.2 S4-T01：自然案例入口与精确绑定零调用实现

日期：2026-08-04
状态：`pass closed / S4-T02 not started`

## 结论

按用户“继续”的授权，本轮只完成 S4-T01，没有进入 T02、检索、模型调用或业务执行。当前 Runtime 已能把 DELL、MU、NVDA 三个自然语言研究目标编译为类型化案例入口，并精确绑定公司身份、as-of、三个 Program Cell、零调用预算、source/index snapshot 引用以及尚未 claim 的一次性执行身份。

T01 的产品增量是“用户给出一个自然研究问题后，系统能先建立不会串案、不会漂移、可追溯的研究任务外壳”。它还没有把历史 source pack 或索引内容认定为当前 Evidence，也没有执行检索；这些资格判断属于 T02。

## 实现与内容寻址

- 合同：`fin_0_1_2.S4.natural_case_entry_and_exact_binding:v1`。
- 当前 Runtime consumer：`load_current_fin_0_1_2_s4_t01_case_entry`。
- 类型化输出：`NaturalCaseEntryRequest`、`CurrentCaseRuntimeBinding`、`SourceIndexSnapshotBinding`、`ExactExecutionIdentityProjection`、`S4T01EntryReceipt`。
- 实现 SHA：`263db62b…892`；authority SHA：`2e43a84b…eda`；隔离 resource registry SHA：`e91d7fe…90d8`。
- DELL/MU/NVDA receipt digest 分别为 `5ffed755…b6c`、`422a6bfa…2ca`、`54ae8bcf…b12`。
- receipt 只保存元数据、引用和 digest，不包含 Evidence 正文；prospective identity 尚未 claim。

## 证明结果

- focused：`15 passed`。
- S1/S3/S4 相关回归：`71 passed`。
- closeout 与历史后继兼容回归：`34 passed`。
- 正向覆盖 DELL/MU/NVDA；负向覆盖 objective、as-of、case、cell、snapshot、budget、identity、Runtime head mutation、跨案例污染、重复身份和未知案例；候选排列变化后 digest 稳定，repository readback 一致。

## 发现的继承问题

更宽的 default S0 resource-registry 回归为 `44 passed / 2 failed`。首因是当前共享 consumer 已引用 `configs/runtime/fin_ia_0_1_2_s3_nvda_fact_candidate_pool_profiles_v1_0.json`，但默认 registry 尚未登记。该文字引用在本轮开始的 clean HEAD `9026b9f5` 已存在，因此不是 T01 新增，也不是 DeepSeek、检索或数据内容问题。

已登记 `RC-P36-113-fin-0-1-2-default-runtime-resource-registry-stale-after-s3-profile-addition`。它阻断 S4-T03 付费 canary 和 S5 hermetic release qualification，但不推翻 T01 的隔离 registry 证明，也不阻断 T02 的零调用确定性准备。修复必须作为 T02 内一个有界的 pre-T03 shared-resource prerequisite 完成；不得重开 S0/S3，也不得通过动态拼路径绕过 detector。

## 证据边界与下一步

DELL/MU 的历史 source packs、S3 NVDA manifest 与 `2026-06-11` shared public index 只作为内容寻址的入口 snapshot。T02 仍需负责 freshness、parser authority、company-specific route、candidate ceiling、accepted/rejected/gap/citation 输出以及零误晋升 Evidence；同时在进入 T03 前关闭 RC-P36-113。

本轮 model/provider/execution-network/source-network/external-tool/admission/Run/Artifact/Human 均为 `0`。下一项严格限定为：

`FIN-0.1.2-S4-T02-THREE-CASE-RETRIEVAL-EVIDENCE-DETERMINISTIC-READINESS-ZERO-CALL-IMPLEMENTATION`
