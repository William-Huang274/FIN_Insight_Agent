# FIN 0.1 S3-T09：Specialist model view 与 output budget 零调用修复

日期：2026-07-22

## 结论

用户以“继续”授权 `S3-T09-SPECIALIST-MODEL-VIEW-AND-OUTPUT-BUDGET-ZERO-CALL-REPAIR`。修复已通过本地确定性与 fake-provider 回归；没有签发 replacement admission，也没有真实模型、Provider、网络、source、tool 或业务写入。

原 canonical input v1 与历史 consumed r1 digest 均未修改。v2 admission 将从完整 canonical cell input 确定性派生 `fin01.s3.specialist_model_view:v1`：保留 T02 决策链/stop/WWC/branch observation/Domain Specialist authority，T03 candidate/promotion/typed gap/source boundary，T04 exact financial row/derived formula/input/result/support boundary，T05 product/method/edge/market/risk，以及完整 Evidence/Numeric/Candidate/Graph authority refs；candidate snapshot、tool selection/gateway preflight、重复 decision-cell list、其他角色 context 和纯审计 digest 不进入 Provider view。完整 canonical input 仍持久化，输出仍对原 cell authority 校验，node receipt 新增 model-view contract ref/digest。

冻结 exact input 的实现后复核显示，Demand/Value/Bottleneck 的 v2 request 为 8,331/12,461/8,969 bytes，相对 canonical payload 25,944/32,146/26,748 bytes 分别减少 67.9%/61.2%/66.5%。这些是本地序列化字节，不是 Provider token 实测，也不代表输出质量已通过。

output v2 现强制 fact≤3、explanation=1–3、judgment=1–2、gap=1–4、WWC=1–3、每条 narrative≤320 Unicode chars、完整序列化≤6,000 UTF-8 bytes；重复 fact/support ref、额外字段和越权 ref 均 fail-closed。Specialist cap=2,200，Lead/Writer/Verifier 保持 1,200/1,400/1,000，aggregate=10,200，总 cost cap 仍 USD 0.10，retry=0。

验证结果为快速 repair/decision/admission `20 passed`、慢速 exact-input/full fake-provider compatibility `5 passed`、历史 digest 与 S3 adapter selected regression `5 passed`；compile 与 diff check 均通过。真实 model/provider/network/source/tool/new admission/live run 全为 0。

## 边界与下一步

RC-P36-035 的项目内实现缺口已关闭，但 S3-T09 仍未 live-proven：consumed r1 继续保持 terminal failed，v2 尚无新 identity、未被 Provider 消费，也没有 Artifact 或 Human acceptance。

当前唯一下一项是 `S3-T09-REPLACEMENT-EXACT-ADMISSION-ISSUANCE-DECISION`。它只能重新冻结 exact input、审查 v2 contract/budget/credential/preflight 并决定是否允许另行签发；不得在同一步签发或执行 replacement admission，也不得进入 T10、S4、release 或 production。
