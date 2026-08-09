# 787 — FIN 0.1.3 ASML 同 accession 详细附件 successor 零调用证明

日期：2026-08-09

归属：FIN 0.1.3 / S1 / held-out generalization

状态：`zero_call_engineering_pass_live_authority_not_yet_issued`

## 1. 这次解决的业务缺口

上一轮准确抓到了 ASML Q2 2026 的 6-K，但正文只有 2,263 字符，实质是封面和附件清单。它能支持净销售额、净利润和毛利率等 headline，却不能支持 bookings、EUV／High-NA、系统销量、installed base 与现金流等研究问题。不能把“表单抓到了”冒充“详细季度披露抓到了”。

本项没有重跑 ORCL／ANET，也没有 broad Web Search。新 successor 只从已保存且 digest-bound 的 ASML live result 读取 accession 与 primary-document lineage，动态派生 SEC 同 accession `index.json`，再从目录中选择最多两份详细附件。

## 2. 合同边界

- accession、CIK 路径和 index URL 均从已绑定 source result 派生，policy 不包含成品 exhibit URL；
- primary document 与 XBRL 文件从候选中排除；
- 最多 `3 network`：一次 index、最多两份候选文档；
- `retry/model/provider/embedding/rerank/Evidence=0`；
- 每次 request／response 先保存，再解析或评价；
- 附件必须同时命中 ASML、Q2 2026，并覆盖七类研究 facet 中至少四类；只有 headline 的文档必须拒绝；
- 抓到的附件仍是 Candidate source，不自动晋升 Evidence，也不授权 sparse／dense rebuild。

## 3. 零调用验证

fixture 模拟了“第一份附件只有 headline、第二份附件有详细季度结果”的真实拓扑：第一份被拒绝，第二份通过。unexpected consumed failure 也会在保留 capture 后把共享 admission terminalize，不能遗留 running 状态。

- proof digest=`ba514c52460da1a5b760980e87cefa49026714fdb7d85771ee8539893d0c00f4`
- policy digest=`1200d21a719c2f3f6e4c9ff7945db77fb1df4ae120088b3c8c0bbaf10516dd41`
- focused＋adjacent=`38 passed`
- actual network/model/provider/embedding/rerank/Evidence=`0/0/0/0/0/0`
- scoped Project OS preflight=`pass`

## 4. 下一步与止损

先提交并推送干净实现，再签发且只执行一次 ASML same-accession exact-live。成功只关闭 ASML 详细 source capture；之后仍必须将 ORCL／ASML／ANET 一次性做 table-preserving reparse、CandidateBundleV2 与 mutation 复证。若目录没有合格附件，保留 typed source-detail gap，不改 marker、不猜 URL、不自动重试，也不提前建向量。
