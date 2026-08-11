# 710 — FIN 0.1.3 S1-08 DELL R2 preflight shape repair 与 v1.1 proof

日期：2026-08-08
阶段：`013-S1-08`
状态：`pre-admission failure repaired / v1.1 clean proof pass / R2 unconsumed`

## 1. 第一次执行为何没有启动

在 clean v1.0 proof 后调用 runner，程序在 admission issuance 前返回 `Project OS preflight failed`。核心函数的真实返回包含 `open_full_chain_blockers=[]`，而 `open_full_chain_blocker_count=0` 只由 CLI compact 输出补充；runner 错把后者当成核心必有字段，将 `None != 0` 判断为失败。

因此此次 observed admission/network/model/provider/retry=`0/0/0/0/0`，R2 authority 没有消费，也不是 live attempt。

## 2. 修复与复证

新增统一 `project_os_preflight_passed`：核心 blocker list 必须为空；compact count 若存在也必须为 0，若不存在则由 list 长度确定。已有非空 blocker 时继续 fail closed。

clean/synced `e48ec1b3...97eb` fresh Git archive/fresh process 再次 `53 passed`、compile pass：

- Runtime SHA=`28034406...ce9e`；
- Runner SHA=`d4348fc8...ebb2`；
- R1 exists、R2 absent；
- external/admission=`0/0`。

v1.0 clean proof 标为 superseded-unconsumed；runner 只接受 v1.1 proof 和上述 exact SHA。当前仍只有一次 DELL R2 可执行，不自动 R3。
