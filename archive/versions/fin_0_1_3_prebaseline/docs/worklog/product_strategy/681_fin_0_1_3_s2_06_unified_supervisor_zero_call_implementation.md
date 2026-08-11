# 681 — FIN 0.1.3 S2-06 统一 Supervisor 零调用实现

日期：2026-08-07

状态：`shared implementation engineering pass / independent fresh proof pending / no admission or Provider execution`

## 本轮解决了什么

上一项 authority decision 识别出四个项目内 blocker：correction ID 跨案重复、三类 citation/coverage finding 没有可执行 owner、缺少依赖感知 corrected-candidate runner、缺少 candidate freeze 后再评分的硬边界。本轮只实现这一个共享零调用结构包，没有调用 DeepSeek、没有签 admission，也没有生成 paid corrected candidate。

历史 v1.1 boundary 保留；新增 v1.2 case-scoped compiler，将 correction ID 编译为 `DELL-CORR-* / MU-CORR-* / NVDA-CORR-*`，所有当前 v1.4 finding class 都必须具有 typed owner 和 action，未知新类别在 Prompt 生成前 fail closed。`writer_cross_case_unknown_or_wrong_id_role`、`writer_case_pack_coverage_incomplete`、`specialist_assigned_pack_coverage_incomplete` 现在明确返回 originating node，而不是落入 manual bucket。

SupervisorPlan 不再为 24–32 条 finding 逐条生成长叙事。Runtime 先按节点归并固定 correction/action，Supervisor 只能为受影响节点选择本案 Evidence、Numeric、Gap alias；prompt、output schema、validator、positive fake 和 failure descriptor 均由同一个 plan spec 编译。Supervisor 无权写替代研报、加入新金融事实、读取 hidden/Codex Gold 或看到其他案例。

corrected runner 以 originating node 为起点计算完整 downstream closure：Lead 会触发所有 Specialist、Synthesis、Writer、Verifier；任一 Specialist 会触发自身及三个下游；Writer 至少触发 Verifier。raw Run/Attempt 不得复用，运行目录必须 fresh；candidate admission 精确绑定 case/raw/corrected identity、容量和有效期，并通过 runtime 外共享 ledger 做 reserve/finalize，所以换 runtime root 也不能二次消费。每次 Provider 返回先保存完整安全 capture，再解析/校验。完整 candidate 先写入并计算 digest，terminal 再绑定该 digest；hidden scoring guard 在 terminal/candidate 双 digest 和 frozen 标记成立前拒绝评分。项目确定性代码只可对明确 path/tokens 做 source-bound 删除，不生成研究答案。

## 验证结果

三案 full-fake 都覆盖最坏 `1 SupervisorPlan + 10 corrected graph calls = 11` 路径，raw digest 前后不变，retry/fallback=`0/0`。污染与 mutation 覆盖跨案 Evidence、未知 Numeric alias、correction/dependency binding、hidden target surface、跨案 raw ID、8 Specialist 容量超限、Provider transport failure capture retention、Lead unit topology 改变、未冻结评分和未授权执行。

另外把三份真实 frozen raw 与 v1.4 finding boundary 代入新编译器做了零调用容量预检：DELL=`33,590 chars / 6 directives / 8 total calls`，MU=`28,104 / 8 / 10`，NVDA=`35,650 / 9 / 10`；均低于每案 `90,000 chars / 11 calls`。这只证明现有输入能被合同和预算容纳，不证明模型会遵循计划或修复内容。

测试结果：focused supervision/runtime=`24 passed`；S2-05/S2-06 扩大回归=`120 passed / 3,201 deselected`。外部 model/provider/network/admission/paid corrected candidate/raw mutation=`0/0/0/0/0/0`。

## 仍未成立的能力

本轮只能记为 `engineering_pass`。Supervisor 自然输出合同遵循、三案真实 corrected candidate、evaluator v1.4 `L1=0/L2=0`、counterevidence/threshold/Verifier 修复、hidden score、内容质量增益、qualified human acceptance、业务晋升和 release 均未证明。

下一步必须在 clean commit 上做独立 fresh zero-call proof；通过后再单独决定是否签发三案隔离 Supervisor admission。不得把本实现通过直接解释成 live authority。

机器记录：`configs/releases/fin_ia_0_1_3_s2_06_three_case_unified_supervisor_zero_call_implementation_v1_0.json`。
