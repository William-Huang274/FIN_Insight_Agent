# 783 — FIN 0.1.3 三个留出案例候选生成、业务复核与索引重建阻断

日期：2026-08-09

归属：FIN 0.1.3 / S1

状态：`held_out_generalization_blocked_before_index_rebuild`

## 1. 本项实际做了什么

在 ORCL、ASML、ANET 的身份、问题和 Industry Pack 已经预先冻结后，本项没有查看 Gold URL、没有调用网络或模型，也没有做 embedding、rerank 或 Evidence 晋升。它只用当前本地 source／object 索引执行 Gold-blind candidate generation，再由人工可解释的业务规则逐 lane 检查候选到底能回答什么。

候选生成结果为：

| 案例 | Query lanes | Candidate rows | Unique refs | Required Slot 有候选 | 当前期来源 |
| --- | ---: | ---: | ---: | ---: | --- |
| ORCL | 11 | 130 | 97 | 8/8 | 缺 FY2026 Q4／全年 |
| ASML | 11 | 112 | 81 | 8/8 | 缺 Q2 2026 6-K／IR PDF |
| ANET | 13 | 154 | 137 | 8/8 | 缺 Q2 2026 10-Q／8-K |

所有结果仍是 `candidate_only_not_evidence`。三案 required Slot 都有候选，不等于这些候选能回答问题。

## 2. 业务上真正发现了什么

### ORCL

本地库能支持 FY2026 Q3 的云收入、OCI 增长、RPO、部分融资承诺、经营现金流和 Q4 指引，因此不是“什么都搜不到”。但冻结的问题要求 FY2026 Q4／全年实绩，当前资料只能写阶段性更新，不能写完整年度结论。

更重要的是，NVIDIA 的一般 AI 云需求材料不能证明 NVIDIA 给 Oracle 分配了多少 GPU、何时交付；Oracle 的数据中心租赁和融资承诺也不能直接等同可交付算力。这些必须保留为公司特定 attribution gap。

业务复核结果：`2 strong / 5 partial / 4 off_target`，有用 source ref 为 10。

### ASML

FY2025 20-F 的父段本身很有价值：能回答订单、收入、EUV／High-NA、毛利、现金流、2030 情景和 AI 需求。但当前 child table／metric 往往只剩表头、脚注或脱离上下文的数值，单独返回时无法安全引用。

本项还发现两个 L1 级问题：

1. 现金流父表明确是 `€, in millions`，child metric 却被标成 `usd_millions`；
2. 一个经营现金流 child object 被链接到 remuneration report 父段，属于 parent-child lineage 错配。

因此现有对象不能直接进入向量重建，否则只是把错误币种和错误父段更快地召回。业务复核结果：`3 strong / 4 partial / 3 usable_with_parent_context / 1 parser_unsafe`，有用 source ref 为 14。

### ANET

FY2025 和 Q1 2026 的 issuer 资料能支持收入、毛利、客户集中、供应链、现金流与反证；Microsoft／NVIDIA 材料能说明 AI 基础设施环境，但不能冒充 Arista 自身订单或收入。冻结问题要求 Q2 2026 实绩，而本地库尚无对应 10-Q／8-K。

业务复核结果：`9 strong / 2 partial / 2 off_target`，有用 source ref 为 18。ANET 是三案中当前对象可用度最高的一案，但仍因当前期资料缺失不能产品通过。

## 3. 泛化结论

接口级泛化成立了一部分：

- 三个此前未作为开发案例的公司可以只通过外部 Case profile／Industry Pack 运行；
- 冻结 core fingerprint=`94af69dcc875ba285afca587d36622dfa859b092c7a2bf686141c5e43308b458` 未改变；
- lane 均能终态化，wrong-ticker 为 0，缺当前期能够保留 typed gap；
- candidate、raw source ref、digest 和 preview 均可追溯。

产品级泛化没有通过：

- 当前检索单位不是可靠的 `child object + parent semantic context + table path` bundle；
- foreign issuer 的币种／单位没有 fail closed；
- typed gap 只能表达“没有当前资料”，不能表达“源存在但对象语境或排序不足”；
- ASML 的 alias／多语言／PDF-only 变异尚未由真实对象链证明；
- 三案当前期官方资料都不在现有本地 corpus。

所以第 5 步 sparse／dense 重建被正式阻断。此时重建只会固化旧对象缺陷，不能提升研究质量。

## 4. 下一步边界

仍留在 S1 的 held-out generalization，不新建产品版本，也不进入模型研究。只允许一个 provider-neutral、case-neutral successor：

1. 检索单位升级为 source child、parent block、table header／row／column path 和三层期间组成的 bundle；
2. parent／child 的 currency 或 unit 冲突必须在 Candidate 阶段 fail closed；
3. 新增 `retrieval_quality_gap` 与 `object_context_gap`，区分“没有源”和“源存在但当前对象不能安全回答”；
4. 用 DELL／MU／NVDA 和同一批 ORCL／ASML／ANET 重放，不允许 ticker 特判；
5. 结构门通过后，再补入截至日所需的官方 current sources；这属于本地 source inventory 完整性，不等同后续 broad-web residual supplement；
6. 上述门全部通过后才允许决定 sparse／dense 对象集合。

## 5. 机器证据

- candidate result=`configs/releases/fin_ia_0_1_3_s1_three_held_out_candidate_generation_result_v1_0.json`
- candidate digest=`14c944646a4967baf3187c8d1beafe6a1f23996a140e12dbd46f3ff4616cf201`
- business review=`configs/releases/fin_ia_0_1_3_s1_three_held_out_business_review_result_v1_0.json`
- review digest=`368146b11717b2cfbafba33262986fe45c3eb7868d7367c85ad090566a2f66be`
- focused tests=`21 passed`
- observed network／provider／model／embedding／rerank／Evidence=`0/0/0/0/0/0`

本记录不声称 Evidence Pack、当前期覆盖、index admission、外源补源、DeepSeek 研究、报告质量或 release 通过。
