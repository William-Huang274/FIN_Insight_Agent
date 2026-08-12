# FIN 0.1.3 S1-C2 当前对象库多检索器对照

日期：2026-08-13
状态：`BM25/BGE engineering comparison complete / Qwen transport blocked / no route promoted`

## 1. 对照边界

本轮使用同一批 20,340 个去重金融对象、同一公司／期间／来源硬过滤和同一候选预算，比较：

- BM25 lexical；
- BGE-M3 dense；
- BGE-M3 learned sparse；
- BGE-M3 multi-vector 候选并集细排；
- Qwen3-Embedding-0.6B（计划项，因模型文件传输失败未执行）。

所有路线只生成候选。标签在排名完成后才 join；候选不是 Evidence，metric-row 不是 NumericFact。本轮 0 次生成模型调用、0 次来源网络访问、0 次训练。

旧 18 条 qrel 只保留为 source-level 兼容诊断。它们的文字仍混合业绩、指引、风险、库存、收入确认和反方，不是当前产品 Runtime 的 `EvidenceRequest → QueryFacetPlan → query-family sibling` 合同。

## 2. 结果

| 路线 | 目标来源进入前 10 | 精确受复核对象进入前 10 | 已观察留出正例胜 hard negative | 处置 |
| --- | ---: | ---: | ---: | --- |
| BM25 | 13/18 | 6/14 | 60/86 | 保留为廉价 lexical 分支 |
| BGE-M3 dense | 15/18 | 6/14 | 57/86 | 保留为语义候选扩展 shadow |
| BGE-M3 learned sparse | 12/18 | 4/14 | 55/86 | 不进入 provisional stack |
| BGE-M3 multi-vector | 14/18 | 6/14 | 63/86 | 仅 shadow，不做 top-10 selector |
| Qwen3 Embedding | 未执行 | 未执行 | 未执行 | transport block，不评价模型 |

BM25 或 BGE dense 的前十并集覆盖 17/18；两路各取 64 个候选后，18/18 的目标来源都在候选池中。multi-vector 再压成前十反而只保留 14/18。当前 provisional candidate pool 因此是 `BM25 + BGE dense union`，不是任何单一路线，也还没有 Runtime 晋升权。

## 3. 大白话业务结论

当前的主要问题不再是“完全找不到那份财报”，而是“在已经找到的同公司、同季度、同一份财报里，挑错了句子或表格”。

- Micron HBM 供给：BGE 找到当前 8-K，却优先给出现金投资、NOR 费用和业务单元毛利表；真正的 HBM4 高量出货句没有进候选。BM25 则先给泛化的供应合同和缺件风险。
- NVIDIA 供给：BM25 能把制造生态产能爬坡句排第一；dense 却把产品保修、现金等价物和应计负债排在前面。语义相近不等于证据角色正确。
- Micron 当期业绩：BM25 先给旧季度表和晶圆利用不足风险；dense 回到当前 Q3 文件，但先给发布日期、Q4 指引和表格行，仍没有选中管理层综合陈述。
- Micron 旧 qrel 10：查询问 HBM、库存和收入确认，标签却是多年客户协议、220 亿美元承诺和约 180 亿美元现金存款。这是 query-target 语义错位，不能拿来惩罚模型或训练。
- TSMC：文档命中了当前 6-K，但受复核内容是领先制程需求和 2nm ramp，不是 CoWoS／先进封装容量。source hit 不能冒充问题已回答。

这说明下一步应使用已经拆开的 Runtime query atom，在同一 BM25+dense 候选并集比较 Cross-Encoder，并让独立 Evidence Role＋abstain 判断候选究竟能证明什么。不能在旧混合 qrel 上调参。

## 4. 数据库路线没有被检索模型替代

S1 文本检索负责 claim、表格语境和父级上下文。最终报告中的公司财务数字必须由 S2 公司财务事实 mart 按主体、指标、期间、单位、粒度和截至日返回 `NumericFact`。当前 7,500 个 metric-row 只能帮助找到披露位置；embedding、multi-vector 或 reranker 分数再高，也不能授予数值权威。

DELL S1/S2/S3 纵切前，S2 typed exact lookup 是硬前置项，不允许用 PDF/HTML 表格行降级替代。

## 5. Qwen transport block

Qwen3-Embedding-0.6B 首次 Hugging Face Xet 传输返回 HTTP 416；唯一一次普通 HTTP successor 在 1,158,146,098 字节权重尚未完成时由对端断开。本轮按止损规则不继续换镜像或无限重试。该结果只能说明模型资产未完整到达本机，不能说明 Qwen 质量差。

## 6. 下一门

1. 用 Runtime 拆分后的 query atom，而非旧混合 qrel，构造同候选 reranker 输入。
2. 复用 `BM25 + BGE dense` 候选并集；BGE/Qwen reranker 必须看同一批对象。
3. Evidence Role 与 reranker 分离；它必须支持多标签和 abstain，且不能授予 Evidence。
4. 若 Qwen 资产仍不可用，保存 partial matrix，不为补齐表格而反复下载。
5. 只有跨案例仍出现稳定、可重复的金融角色残差，才讨论微调；当前无训练权限。

完整逐候选机器结果以 content-addressed 文件保存在 Git 忽略的 `data/workbench_private/fin_0_1_3_s1c_compiled_object_retriever_comparison/v1/`；本轮文件名和 SHA256 由跟踪摘要的 `storage` 字段绑定。Git 只跟踪不含 candidate excerpt 的紧凑摘要 `configs/retrieval/fin_ia_0_1_3_s1c_compiled_object_retriever_comparison_result_v1_0.json`。业务审计见 `configs/retrieval/fin_ia_0_1_3_s1c_compiled_object_retriever_business_assessment_v1_0.json`。
