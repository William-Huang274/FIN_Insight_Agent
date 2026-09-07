# FIN 0.1.3 S1 VS5 统一对象与 split-safe Runtime 输入

日期：2026-08-18

状态：`qualification_objects_ready / runtime_inputs_frozen / evaluator_references_pending / learned_execution_not_started`

## 1. 七份来源进入同一对象链

资格对象构建只执行一次，共形成 7 个父文档、2,211 个 child，其中腾讯官方年报贡献 1,264 个对象；630 个表格对象全部边界平衡，0 oversized child。随后复用现有 claim／metric-row／bounded-context 编译器，将 2,211 个 source record 编译为 10,618 个去重候选对象：7,285 个 claim、1,678 个 metric row、1,655 个 bounded parent context。

本轮保留 1,469 条诊断：48 条重复 claim surface、1,033 个金融表没有可编译 metric row、388 个非金融表未被伪装成 metric row。它们不是 Evidence，也没有 NumericFact 权威。对象编译 0 网络、0 模型调用。

## 2. 为什么新增的是外层资格配置

预注册绑定的核心 kernel 只含 DELL／MU／NVDA 三个开发案例，且来源枚举没有腾讯 `ANNUAL_REPORT`。直接修改核心文件会破坏预注册时间边界。因此本轮建立外层 provider-neutral qualification overlay：

- 保留原 kernel 与 route policy 的内容摘要；
- 只追加 COST／JPM／CAT／NVO／SHEL／0700.HK 的公司身份、行业词包和查询面；
- 腾讯来源保持 `ANNUAL_REPORT` 原身份，只按“官方年度披露”允许进入候选，不伪装成 10-K／20-F；
- 30 个预注册命题全部编译为结构化 EvidenceRequest、QueryFacetPlan 和 RetrievalExecutionPlan；
- 运行输入不含 object target、gold、hard negative、expected outcome 或 qrel。

三个 split 已物理分开：COST temporal 5 条、JPM／CAT frozen test 10 条、NVO／SHEL／Tencent heterogeneous holdout 15 条。Evaluator-only reference 尚未建立，因此 learned execution 仍未获授权。

## 3. CUDA 与预算边界

Embedding、dense、learned-sparse、multi-vector 与两个 Cross-Encoder 继续强制 CUDA＋FP16。CPU 只可运行 BM25、SQL、tokenization、硬过滤和账本；CUDA、模型或缓存身份不满足时 fail closed，不允许 CPU 接管。

四个 learned 节点均新增 task-specific TokenBudgetBasis。资格对象数为 10,618，约为 VS3 33,085 对象的 32%；每命题 reranker pool 上限仍为 96，共 30 命题，最大 2,880 对／模型。限制依据来自对象长度、VS3 可比运行和角色误判风险，不以省时或省钱替代研究需要。

## 4. 当前边界与下一门

- 腾讯文档没有自然扫描页，预注册 natural-scan 硬门已客观失败，不能栅格化伪造通过。
- 预注册只捕获发行人官方年度资料，却要求若干 independent readthrough；若单一发行人来源无法支持，这将作为来源计划／覆盖门失败，而不是写成公开资料不存在。
- 下一步先从完整 source-bound 对象中建立独立盲审 reference 和 hard negative，绑定 CUDA device／model／cache identity；之后才允许先跑 valid temporal，再按冻结配置各跑一次 test 与 holdout。
