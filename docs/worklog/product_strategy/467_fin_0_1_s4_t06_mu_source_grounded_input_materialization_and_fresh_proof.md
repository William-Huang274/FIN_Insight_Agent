# 467｜FIN 0.1 S4-T06 MU source-grounded input 物化与 fresh proof

日期：2026-07-29

## 结果

`RC-P36-076` 的 source-pack 缺口已完成结构性修复：

- `S4SourceGroundedInputPack` 从 DELL-only 改为共享 schema 与案例专属约束；
- DELL 仍必须保持 11 条唯一 `p34_route::dell_` receipt；
- MU 必须保持 8 条唯一 `p34_route::mu_` receipt，并绑定 `CIK0000723125`；
- MU pack 已加入共享 loader；
- 未复制 DELL 事实、ID、route 或结论。

MU pack：

- source snapshot：6；
- route receipt：8；
- Evidence：7；
- Numeric：16；
- derived metric：4；
- context-only Graph：4；
- typed gap：9；
- source pack digest：`5fff74f742b038ead1718e449e3e4dafc4f04b55587256d98e619d05cf6c263d`。

## 金融真实性

公司、DRAM、CMBU、CDBU 和 SCA 均没有被归因到 HBM。HBM-specific revenue、profit、price-volume-mix、customer identity/concentration、demand durability、capacity/yield、export-control impact 和 independent counterevidence 全部保留为 typed gaps。

独立重算结果：

- GAAP gross margin：`84.56%`；
- GAAP operating margin：`80.37%`；
- adjusted free cash flow：`USD 18,304m`；
- net capital intensity：`17.09%`。

首次测试发现生成器把净资本强度写成 `17.08%`；已在 pack 接受前修正生成器并重新物化，未用 validator 放宽或质量 finding 掩盖。

## Fresh proof

- source-grounded input 双编译完全一致；
- proof input digest=`a6b9df3320b56d3a6ba47f67557ef490c20d81fae2ff407270e403152da56682`；
- wrong issuer、DELL route prefix、缺 route、MU pack 配 DELL binding 全部 fail-closed；
- 零调用 full fake=`6 nodes / 9 Artifacts`；
- focused/current proof=`24 passed`；
- S4-T06 transition=`110 passed`。

## 边界与下一步

本步骤没有调用 DeepSeek/model/Provider，没有签发 admission，没有创建 canonical MU Case/DecisionSurface、WorkUnit、Attempt、ResearchRun 或业务 Artifact。

当前下一子步骤：

`S4-T06-MU-CANONICAL-CASE-SURFACE-AND-FRESH-EXACT-ADMISSION-PREPARATION-ZERO-CALL-PROOF`

只允许物化 canonical MU Case/三 Cell DecisionSurface，并冻结 fresh input/preparation/identity 和 prospective admission；不得签发或消费 admission，不得执行 exact-live。
