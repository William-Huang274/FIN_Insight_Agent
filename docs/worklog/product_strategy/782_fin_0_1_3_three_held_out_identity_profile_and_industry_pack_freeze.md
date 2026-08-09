# 782 — FIN 0.1.3 三个留出案例身份、问题与 Industry Pack 冻结

日期：2026-08-09

归属：FIN 0.1.3 / S1

状态：`identity_and_profile_freeze_pass / candidate_inspection_not_started`

## 1. 为什么先冻结再检索

留出测试若先看仓库里有什么，再选择容易命中的公司，就只能证明配置迎合数据，不能证明泛化。因此本项只冻结公司身份、研究问题、来源形状、mutation、Industry Pack overlay 和 CaseResearchProfile；retrieval、qrels、Gold、网络、模型、embedding、rerank 与 Evidence promotion 全部为 `0`。

最初曾在用户可见更新中暂定 MSFT／TSM／ANET。随后读取冻结基线合同发现 MSFT 和 TSM 已作为三案关系实体及 reserved tokens 出现，继续使用会虚高盲测成绩。因此在正式冻结前剔除这两个已见身份，最终选择：

- ORCL：美国非半导体、云基础设施与资本强度；
- ASML：非美国、20-F／6-K、欧元、IR PDF 与出口管制；
- ANET：披露相对稀疏、客户集中与 AI networking 关系链。

初始声明后的仓库 presence probe 只显示了已知 MSFT SEC metadata；没有读取 ORCL／ASML／ANET 的候选、qrels、Gold URL 或答案。该偏差与纠正均写入机器结果，不被隐藏。

## 2. 新增的扩展边界

冻结核心合同原本只有 AI compute infrastructure Pack，但已经提供 `compile_external_case_profile`。本项没有改该核心，而是用外部 registry overlay 新增三个最小行业 Pack：

- hyperscale cloud infrastructure；
- semiconductor equipment；
- data-center networking。

overlay 只能选择已有 Evidence Slot 并增加行业 facet、query atom、mechanism、source role 和 forbidden substitution；不能修改 kernel、插件、身份、期间、关系、来源权威、预算或 Candidate／Evidence 边界。三份 profile 均编译为 `8 required + 1 optional` Slot，并共享原 core fingerprint=`94af69dc...b458`。

## 3. 三案冻结的问题

ORCL 聚焦 OCI／云收入和 RPO 到真实消费与收入的转换、capex／折旧／电力／加速器约束到利润和 FCF 的机制，以及集中度、融资承诺和交付延迟反证。

ASML 聚焦 EUV／High-NA bookings、backlog、系统出货与客户验收，系统数量／ASP／mix／installed-base service 到毛利的桥，以及出口管制、中国收入、客户 capex 消化和欧元现金流。

ANET 聚焦大型云客户与 AI cluster Ethernet 部署、产品／服务／平台 mix、新平台和组件交期，以及客户 capex 消化、技术替代和供应／出口风险。

问题中没有 target ID、accession、URL 或标准答案。

## 4. 验证与下一步

selection result=`held_out_identity_and_profile_freeze_pass`，digest=`c25f6ba9a9a129c3eb6b3d9c7f8fd3e9a627de46c4c67fb04962323ace401792`；28 项本项及相邻合同测试通过。四份上游锁定资产前后 SHA 一致。

下一步才允许只读盘点 ORCL／ASML／ANET 的本地 source、parent/object、period／currency／PDF 和关系资料，并运行 Gold-blind candidate generation。若无资料，保留 zero-result／typed gap；不得换案。若新增案例必须修改冻结 kernel，留出门失败。

证据：

- `configs/runtime/fin_ia_0_1_3_s1_three_held_out_profile_selection_policy_v1_0.json`
- `configs/releases/fin_ia_0_1_3_s1_three_held_out_profile_selection_result_v1_0.json`
- `src/sec_agent/financial_research_held_out_profile_registry.py`
- `tests/contract/test_fin_0_1_3_s1_three_held_out_profile_selection.py`
