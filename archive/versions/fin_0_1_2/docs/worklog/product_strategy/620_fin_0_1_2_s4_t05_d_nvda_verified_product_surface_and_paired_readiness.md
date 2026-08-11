# FIN 0.1.2 S4-T05-D NVDA verified product surface 与 paired readiness

时间：2026-08-05

状态：`zero-call L4 pass / paired readiness pass / formal paired and Owner pending`

## 目标与边界

本项只读取 immutable T05-D NVDA exact result=`200907cf…bbc4`，用已验证的三案例 current-case renderer 形成 analyst-facing final preview、本地 Verifier binding 和独立 deterministic baseline。DeepSeek、Provider、Search、来源网络、外部工具和 exact rerun 均为 0。

## 结果

- final preview=`092e0f59…9fab`；
- local Verifier=`57bc4849…8aed`；
- 三 Cell Evidence/authority coverage=`3/3`；
- 内部 `__company_total__`、`FY2025-FY`、重复币种和英文 limitation 残留=`0`；
- deterministic baseline=`891e00a5…45df`，与 Agent 使用同 input/head，但 Run/Artifacts 独立；
- paired readiness=`a825f345…56ea / ready_for_formal_paired_assessment`；
- record=`6b6098cc…1ec8`；
- NVDA、DELL、MU renderer、跨案、lineage、Numeric、preview/verifier、pair mutation 与 current Evidence 回归=`45 passed`。

## 审计补强

首轮共享回归的唯一失败来自测试误用 DELL/MU 的 `s4_case_runtime` 字段；NVDA legacy Artifact 按设计不含该 overlay。没有把字段补进 NVDA，也没有放宽测试。进一步审计发现通用产品表面虽然比较 Artifact 声明的 input digest，却未重新计算 input body 的内容摘要。RC-P36-124 已在本轮关闭：所有 DELL/MU/NVDA input 先通过 canonical digest 自校验；正常三案输入均原样通过，stale-digest 的 NVDA `T04_financial_pack` lineage mutation 在渲染前 fail closed。正常产品输出 digest 未变化。

## 后续

当前可以声明 T05-D engineering、exact-live、independent L1、final delivery L4 和 paired readiness 通过；但 formal paired 尚未执行，Owner 尚未接受，因此 post-transfer NVDA R2 仍=false，S4-T06 仍未进入。下一项为 `FIN-0.1.2-S4-T05-D-NVDA-FORMAL-PAIRED-L1-L4-ASSESSMENT-AND-OWNER-DECISION`。RC-P36-119 后传 T08–T10/S5；RC-P36-122 保持 MU-specific，不偷换成 NVDA finding；RC-P36-115 继续阻断 S5/release。
