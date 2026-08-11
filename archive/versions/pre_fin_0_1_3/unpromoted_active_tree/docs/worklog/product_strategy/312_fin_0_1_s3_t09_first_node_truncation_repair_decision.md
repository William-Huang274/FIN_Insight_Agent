# FIN 0.1 S3-T09：首节点 truncation root-cause 与 repair decision

日期：2026-07-22

## 结论

用户以“继续”授权当前唯一的零调用 repair decision。本轮没有实现修复、签发新 admission 或调用模型。结论是拒绝 cap-only，也拒绝可能隐藏研究信息的 blind compression；选择“role-specific Specialist model view + closed output cardinality/length/byte budget + moderate Specialist cap headroom”。

## 零调用拆解

当前 Demand Specialist provider request 为 26,852 bytes，真实调用计为 8,973 input tokens。完整 cell pack 中同时携带候选 snapshot 与 bundle、EvidenceOperator 的 tool selection plan 与 gateway preflight、重复的单元素 Graph list/object，以及大量只服务审计的 ID、digest 和 persistence flag。它们应留在 canonical input 和 Trace，但不应全部进入 Domain Specialist 的分析窗口。

以不变 canonical input 派生的候选 model view 只保留实际分析所需字段：T02 决策问题/mandatory chain/stop/WWC/branch observation 与 Specialist authority；T03 候选元数据、promotion、typed gap、source boundary；T04 exact rows/derived metrics/支持边界；T05 method、product/edge/market/risk/typed gap；以及 exact Evidence/Numeric/candidate/Graph authority refs。三 Cell 请求可由 26,852/33,040/27,666 bytes 降至 6,659/12,796/7,989 bytes，分别减少 75.2%/61.3%/71.1%。候选 token 数仅按本次首节点 byte/token 比例估算，不冒充 Provider 实测。

## 冻结的 replacement contract

- canonical input v1 与 input digest 不变；新增 `fin01.s3.specialist_model_view:v1`，其 contract ref/digest 必须进入 node receipt；
- replacement output=`fin01.s3.bounded_agent_three_cell_output:v2`；fact 最多 3 条，explanation 1-3、judgment 1-2、gap 1-4、WWC 1-3；每条 narrative 最多 320 Unicode chars，总序列化输出最多 6,000 UTF-8 bytes；
- Provider 输出仍必须通过 duplicate-key、closed keys、authority ref 与 full original cell-input semantic validators；
- Specialist cap 由 1,400 调至 2,200；其他节点保持 1,200/1,400/1,000，aggregate 由 7,800 调至 10,200；最坏新增 output-only cost=`USD 0.002088`，总 cap 仍为 `USD 0.10`；
- provider、transport、retry=0、no-source/no-tool/no-live-head-write 与 consumed-r1 禁止复用全部不变。

下一项是 `S3-T09-SPECIALIST-MODEL-VIEW-AND-OUTPUT-BUDGET-ZERO-CALL-REPAIR`，需单独授权。它只能实现并用 fixtures 验证上述合同，不能同时签发或执行 replacement admission。
