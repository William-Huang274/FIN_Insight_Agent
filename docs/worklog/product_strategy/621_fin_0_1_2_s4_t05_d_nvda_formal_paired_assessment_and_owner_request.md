# FIN 0.1.2 S4-T05-D NVDA formal paired assessment 与 Owner request

时间：2026-08-05

状态：`paired L1-L4 pass / limited Agent gain / Owner decision pending`

## 目标与边界

本项对 immutable post-transfer NVDA Agent result 与同 input/head、不同 Run/Artifact 的 deterministic authority-only baseline 做正式配对评估。没有调用 DeepSeek、Provider、Search、来源网络或外部工具，没有重跑 baseline/exact-live，也没有自动替 Product Owner 签字。

## 配对结果

- pair：同 input/head，Agent/baseline 分别为 9/1 Artifacts，baseline body 未暴露给 Agent；
- L1：identity、Numeric、citation、lineage、capture 与 Artifact topology 通过；
- L2：三个 NVDA 研究 Cell 的 Evidence/authority coverage=`3/3`；
- L3：baseline→Agent 的 Claim/dependency/conflict/gap/WWC=`0/0/0/0/0 → 6/1/2/4/9`，属于有限但真实的结构与审计增益；
- L4：analyst preview、本地 Verifier 与 NVDA case identity 通过；
- assessment digest=`ff93cea5292921b78627f93ac61fc8be942d802f5aabeef29b325557258c4f21`；
- 三案例 formal pair 与 MU/NVDA surface mutation regression=`35 passed`；
- new model/provider/network/source/exact rerun=`0/0/0/0/0`。

## 主动审计与需求建议

NVDA 的 9/9 WWC 仍是通用阈值，继续归 RC-P36-119。更重要的是，唯一 dependency 主要复述 claim 的 epistemic state，两个 conflict 均 unresolved，四个 gap 中两个指向 fact-supported claim。这与 MU 的 RC-P36-122 不是两个孤立案例，而是共享 Lead 合同只保护结构、未充分要求公司特定综合的跨案例问题。

因此新增 RC-P36-125，吸收后续跨案例质量校准范围；RC-P36-122 仍作为 MU 首次触发的历史证据保留。合理产品边界是：不重开已经 L1/L2/L4 成功的 T05-C/T05-D，不再付费重跑；在 T08–T10/S5 用跨案例 rubric 校准 dependency、conflict resolution 与 gap priority。这是对既定需求的及时修正：若继续把每个案例都当独立字段缺陷处理，会再次回到逐项修补和无限 live 的旧路径。

## Owner gate

建议接受 `post-transfer NVDA R2`，但只作为 bounded internal R2，并显式后传 RC-P36-119/125。接受不等于 strong NVDA thesis、qualified Human Review、NVDA R3、S4 整体验收、S5、release 或 production。Owner 尚未明确选择，因此当前 `post_transfer_NVDA_R2=false`，T05-D closeout 与 S4-T06 entry 仍 blocked。
