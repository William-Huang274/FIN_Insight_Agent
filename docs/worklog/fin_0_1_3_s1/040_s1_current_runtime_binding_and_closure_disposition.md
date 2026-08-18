# S1 当前 Runtime 绑定与收口重定基

日期：2026-08-18

状态：`current_product_lineage_bound / route_truth_explicit / twenty_gap_disposition_complete / candidate_ceiling_open / S1_not_qualified`

## 为什么要做这轮

S1 已经积累来源库、金融对象、BM25、Qwen 向量、S2 SQL、reviewed Evidence Pack 和 Workbench，但“这些东西是不是同一版、当前产品到底用了哪几条路、旧覆盖矩阵还有哪些是真的没做”仍散落在不同结果与聊天记录中。若直接继续做 EvidenceDecision，会有三个风险：旧对象配新向量、声明过的路线被误当成已经执行、开发审计结果被误当成产品产物。

本轮没有新增模型调用或联网抓取，而是把当前真实主线重新绑定并对历史缺口逐项重定基。

## 当前真实数据链

1. 当前来源库有 1,841 条记录；
2. 当前编译对象有 20,761 条：12,055 个 claim、7,500 个 metric row、1,206 个 bounded parent context；
3. 对象直接 base source identity 为 1,812 个，另有 29 条来源只作为 deduplicated lineage 保留；把所有 `lineage_source_record_ids` 展开后，1,841／1,841 来源全部覆盖，0 缺失、0 外来身份；
4. Qwen cache 精确覆盖 20,761 个对象，1024 维、FP16；learned execution 继续 CUDA-only，不允许 CPU fallback；
5. S2 SQL mart 有 1,319 条 observation、3 个 ticker、12 个 metric，继续作为并行数值权威，不混入文本 Candidate 排名；
6. 当前 reviewed Evidence Pack、claim anchor、上述资产和 Workbench consumer 已注册到 Runtime registry R21，并由一张 current binding receipt 内容寻址。

这意味着旧问题不是“29 条资料没切进去”，而是此前没有一张产品级收据证明全部资产属于同一可执行快照。该问题由 RC-S1-032 关闭。

## 当前真实检索路线

策略曾声明六条路线，但当前产品候选面实际只有 BM25 和 Qwen dense。typed exact lookup 由 S2 独立执行；learned sparse、multi-vector、typed relationship graph 尚未配置。现在 Workbench 会返回每条路线的能力和执行状态，未配置或未执行路线明确标为不具备 public-gap 资格。该“执行真相漂移”由 RC-S1-033 关闭；缺少的能力本身没有被伪装成完成。

## 旧 20 项缺口如何重定基

`fin_ia_0_1_3_s1_implementation_coverage_matrix_v1_0.json` 保持不可变。successor disposition 对 20／20 项逐项登记当前证据、owner 和状态，只关闭三项：

- source identity；
- 历史 chunk 向当前金融对象归一化；
- 当前 source／object／index／S2／Pack 快照绑定。

其余没有因为代码很多而追认完成：

- S1 内部：route/source-role dispatch、candidate-ceiling provenance、产品 EvidenceDecision／GapEligibility／PackReadiness producer、Workbench drilldown、Graph 必选或 optional 决策；
- S2：产品／分部利润桥、PIT 估值和缺失 NumericFact；
- S3：自然问题到 Research Objective 与动态 EvidenceRequest；
- 外部门：自然扫描官方源、COST qualified-human、Git 外新 blind labels、最终 Pack 研究充分性人工验收。

## 当前最早责任层

下一项不是调 Embedding，也不是跑完整 S3，而是 RC-S1-035：让每个 requirement 能说明资料最早在哪一层丢失——来源不存在、解析失败、未形成对象、未进索引、查询不匹配、路线没执行、候选没进 union，还是已进入候选却在 ranking／review cut 被截断。

这个 receipt 完成后，才允许实现 RC-S1-034 的产品级 `EvidenceDecision + GapEligibilityReceipt + PackReadiness`。否则系统仍无法区分“免费公开资料真没有”和“我们自己没搜到／没执行／没排上来”。

## 机器证据

- binding policy：`configs/retrieval/fin_ia_0_1_3_s1_current_product_runtime_binding_policy_v1_0.json`；
- binding receipt：`configs/runtime/fin_ia_0_1_3_current_s1_runtime_binding_receipt_v1_0.json`；
- closure disposition：`configs/retrieval/fin_ia_0_1_3_s1_current_closure_disposition_v1_0.json`；
- Runtime registry：R21／22 resources；
- 新合同测试：snapshot digest mutation、route unavailable、route unexecuted 不得冒充 gap、20 项 predecessor gap 恰好处置一次、不得把 S1 重标为通过。
- 首轮全仓回归暴露 API response model 未声明新增的 binding／route truth 字段，有权限的 HTTP 请求会在序列化时报错；已在本包内同步 API 合同并增加接口断言。这正是只测服务层会遗漏的纵切集成问题；失败测试证据保留，修复后全仓 `725 passed`。
- `python -m compileall -q src apps scripts`：通过；active baseline：164 Python／8 frontend／22 Runtime resources／0 forbidden reference；secret scan：7,196 files／0 findings；receipt 重物化前后 SHA-256 均为 `3a34dd83492de45db4d5251e1be81414625a93cfd7ef4e7cd17a3747f764b66a`。

## 边界

本轮只证明当前产品资产身份和 route truth 可以 fail closed。它没有提高研报内容质量，没有执行外源检索或模型，没有自动晋升 Evidence，没有让开发期 DELL readiness 变成正式产品产物，也没有完成 qualified-human／blind 资格。`S1_qualified_stable=false`。
