# FIN 0.1 S3-T09 transport-v4 fresh decision 与 exact admission 签发

日期：2026-07-23

## 授权与结果

用户授权连续完成 transport-v4 fresh proof decision、exact admission issuance、付费前预检和一次真实执行。决策阶段仍保持零调用、目标只读：同 Case/input-head 的 7 个历史 Run 全部列入 nonreuse，隔离副本 double-prepare 一致，新 WorkUnit/Attempt/Run 均不存在，canonical counts 保持 `7/7/7/13`。

冻结的新 admission ID 为 `fin01-s3-t09-three-cell-deepseek-owner-grade-v3-segmented-transport-v4-exact-admission-r1`，digest `e85202b8adfa28274c7c90a78eb2a7c2c95518b74aeef83b657fe475fc332b62`。它显式而非默认绑定 `fin01.s3.provider_output_capture.assistant_final_text_only:v1`，历史 transport/admission payload 和 digest 未改写。调用上限仍为 model/provider/network `12/12/12`、output 16200、USD 0.10、retry/fallback/rerun 0。

专项 v4 与相邻历史合同共 16 个测试通过；Project OS decision 与 exact-live scopes 均为 zero open blockers。签发时 admission issued/unconsumed，模型、Provider、网络、canonical execution write 均为 0。

## 边界

用户的连续授权允许随后一次 exact-live consumption，但不授权失败后修复、v5、重跑、paired comparison、owner acceptance、T10、S4、release 或 production。完整 live 结果另记于 worklog 343。
