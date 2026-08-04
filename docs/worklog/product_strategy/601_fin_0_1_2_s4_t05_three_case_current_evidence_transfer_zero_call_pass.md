# FIN 0.1.2 S4-T05-A 三案例 current-evidence transfer 零调用通过

日期：2026-08-05

结论：T05-A 已工程通过，但没有执行 DELL/MU/NVDA 的新真实搜索或模型调用，也没有形成任何新的产品 R2。

这轮把原来只对 NVDA 可执行的 T03/T04 surface 收敛为 DELL、MU、NVDA 三案例 closed profile。每案现在都能从三份 EvidenceRequest 出发，经模拟官方来源身份、真实本地只读 BM25/SQL/Graph、Evidence Gate、current Agent input、Specialist/Lead/Writer/Verifier，最终生成 9 个测试 Artifact。统一形状为 `18 candidates / 15 Evidence / 3 exact Numeric / 3 typed gaps`；Agent 测试链为 `12 Provider callbacks / 9 compiled interactions / 12 captures / 9 Artifacts`。

本轮暴露并一次性关闭了三个结构问题：数值 metric family 过去依赖 NVDA 展示标题解析；current pack 的通用 semantic roles 与旧案例专用候选池 profile 不相容；DELL/MU 与 NVDA 的合法 lineage 家族不同。修复分别采用 typed numeric 字段、独立内容寻址的 T05 current-evidence profile，以及 DELL/MU S4 overlay、NVDA legacy lineage 的显式分派。没有修改模型 prompt 来掩盖问题，也没有放宽财务数值、Evidence、Verifier 或最终 Artifact 门禁。

容量诊断显示最大单请求估算为 DELL `19,505`、MU `16,165`、NVDA `19,460` tokens；累计估算分别为 `99,031 / 91,725 / 98,528`，均低于既有 `108,000` 编译边界，未调高上限。关键测试共 46 项通过：T05-A 行为与状态合同 10 项、冻结 NVDA T03/T04 回归 18 项、旧候选池与三案例最终 Artifact mutation 18 项。

下一步只进入 T05-B 的 DELL fresh zero-call proof 与 admission authority decision。它需要重新证明 current DELL search input、source/adapter/capture、current Agent input、容量和 exact ceiling；在另行签发前不允许 source live 或 DeepSeek live。DELL current R2 仍为 false，MU 与 post-transfer NVDA 继续被顺序门禁阻断。
