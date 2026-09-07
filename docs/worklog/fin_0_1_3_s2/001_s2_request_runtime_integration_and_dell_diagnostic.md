# S2 request-scoped Runtime 接入与 DELL 真实诊断

日期：2026-08-13
状态：`engineering pass / S3 and UI consumption pending / product gate open`

## 问题

S2 公司财务事实 mart 已有 1,319 条 source-bound observations 和离线 24/24 查询结果，但此前没有当前 Research Runtime 消费者。若直接进入 S3，数据库可能再次被遗忘，或者被文本表格、embedding 命中和模型自由数字替代。

## 决策

数据库作为 S2 并列权威通道保留，不与 BM25、embedding 或 reranker 竞争：

- S3 把用户语言规范成受控 Research Objective、facet 和 metric ID；
- S1 把同一 EvidenceRequest 拆成 narrative 与 typed fact sibling；
- S2 只执行标准 metric、identity、period、unit、PIT 请求并返回 NumericFact、typed gap 或 typed conflict；
- 文本候选、metric-row 和模型分数均不能授予数值权威。

实际业务证据又修订了 S1 路线：Qwen 对当前结果表和现金流事实更强，BM25 对 FCF 定义、AI server revenue 和毛利解释更强，因此纵切采用二者候选并集，不采用 Qwen winner-take-all。

## 完成内容

1. `RuntimePathRegistry` 增加显式 `company_financial_fact_mart_path`；private mart 不进入 Git 或 Runtime Registry。
2. `ResearchRetrievalService` 在 request-scoped 路径执行 ready typed fact sibling，并返回 `typed_fact_results`、resolved/gap/conflict 计数。
3. API 合同升为 `fin_ia_request_scoped_retrieval_projection_v1_2`。
4. candidate projection 增加 source-bound reporting fiscal year／period end，保留 source-record 原值和选择来源；关闭 8-K filing date／reporting period 混用。
5. 当前候选 snapshot 重建，Runtime Registry 升为 R6；resource count 仍为 7，private mart 未注册为 tracked product resource。
6. 增加 fake mart、missing mart、期间身份和当前 Registry 回归。

## 真实 DELL 结果

工程侧用标准 metric ID 向当前 Runtime 发出一个 results＋cash 请求：

- narrative lanes：2/2 非空，9 个去重候选；
- typed fact requests：6/6 ready，6/6 resolved，0 gap，0 conflict；
- FY2027 Q1 revenue：43,842,000,000 USD；
- FY2027 Q1 operating cash flow：4,081,000,000 USD；
- FY2027 Q1 capital expenditures：963,000,000 USD；
- 同 accession 确定性 free cash flow：3,118,000,000 USD；
- 公式、输入 NumericFact ID、accession、accepted-at、source digest 和 citation URL 均保留；
- 0 网络、0 模型调用。

聚焦回归命令：

```text
python -m pytest tests/test_current_runtime_registry.py tests/contract/test_fin_0_1_3_workbench_current_research_evidence_pack_projection.py tests/test_retrieval_vertical_slice.py tests/test_s1c_query_object_fact_route.py tests/test_s2_company_financial_fact_mart.py -q
```

结果：`45 passed`。

收口复证：全仓 Python `133 passed`，`compileall` 通过，active baseline=`94 Python / 7 frontend / 7 Runtime resources / 0 forbidden reference`，secret scan=`6,348 files / 0 findings`，`git diff --check` 通过（仅提示既有 Windows checkout 的 CRLF→LF 规范化）。

## 反思与边界

- 数据库已经进入当前 backend Runtime，但 reviewed Evidence Pack、S3 研究综合和前端尚未消费，不能称为 S2 产品通过。
- “capital expenditure”等自然表达不应诱发 S2 按词形逐项打补丁；S3 必须规范为 `capital_expenditures`，未知指标 fail closed。
- 当前产品 endpoint 仍消费 immutable narrative snapshot；Qwen＋BM25 联合候选尚未进入产品执行链。
- 第一次临时展示脚本因假定 NumericFact 有单一 `form` 字段而失败；产品请求实际已成功。诊断改为读取真实合同中的 `accession_numbers`，没有修改 Runtime 迁就脚本。

## 下一步

在同一 DELL 纵切中实现 S3 `ResearchObjective → EvidenceRequest/TypedFactRequest` 受控规划，接入 Qwen＋BM25 联合候选和当前 S2 NumericFact。先用零调用 fake/mutation 证明身份、期间、指标枚举、候选预算和跨案污染边界，再决定一次最小 DeepSeek 自然 canary。
