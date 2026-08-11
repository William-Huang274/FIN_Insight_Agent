# 777 — FIN 0.1.3 S1 qrels 全文内容复核与五行 successor 提案

日期：2026-08-09

归属：FIN 0.1.3 / S1

状态：`zero_call_content_requalification_pass / 5-row owner reconfirmation pending / no qrels v1.4 or 410 build`

## 1. 结论先行

18 条 qrels 不是 18 条都能单独支撑完整研报，也不是上轮看到联系人／免责声明后就应判为无效。全文复核得到：

- `18/18` 仍是有效的候选级排序标签；
- `4/18` 的单个候选覆盖该行全部 target facets；
- `14/18` 是实质相关但只覆盖部分业务面；
- `5/18` 在同一冻结候选池内已有更干净的 child claim，建议替换 candidate identity；
- `0` 行需要因为“全文无相关内容”退回 typed gap；
- 模型、网络、embedding、vector search、rerank、Evidence promotion 均为 `0`。

因此当前真正的产品边界是：qrel 用于评价“有没有把相关候选排进来”，完整 Evidence Slot 需要多个候选、内外源补采和 Evidence Gate 联合满足。不能用 `18/18` 冒充研报资料充分，也不能要求每条 qrel 自己成为一份完整研究答案。

## 2. 为什么上轮两条 NVDA 判断需要纠正

上轮只看截断 preview 时，两条 NVDA supply target 从联系人和免责声明开始，因而被标成可能的 `qrel_business_semantic_defect`。本轮读取完整 chunk 后确认，后半部明确写到：NVIDIA 依赖第三方制造、组装、封装和测试，并把供应、生产和分销列入前瞻不确定性。

所以这两条不是“事实不存在”，而是“相关事实被模板噪声包住”。正确处置不是伪造 typed gap，而是保留历史 qrels/R2，再把 successor target 换成冻结池中同一段抽出的第三方制造依赖 claim object。这个纠正说明后续内容审计必须读取全文，不能把 preview 当全文。

## 3. 五个建议替换

### MSFT demand：三行

适用 DELL、MU、NVDA 三案的 customer-demand slot。旧候选是微软 10-Q 的宽段落，开头先解释云业务指标，后半部才写到微软云/Azure 增长、AI 基础设施持续投入和 AI 产品使用增长。它相关，但目标不够聚焦。

建议改成同一 10-Q、同一 bundle 已存在的 `MSFT_2026_10Q_ITEM2_BLOCK_0004_PART_01_OF_04_CLAIM_3A923AB6`。该判断原子直接说明微软云毛利受 AI 基础设施持续投入和 AI 产品使用增长影响。它仍未给出明确 capacity quantity，因此 relevance 保持 partial，不升级成完整需求证明。

### NVDA supply：两行

适用 DELL、MU 两案的 supply/counterevidence slot。旧候选全文相关，但联系人和安全港前置。

建议改成同一 NVIDIA 8-K bundle 已存在的 `...CHUNK_0001_CLAIM_EBFEA572`。它直接保留第三方制造、组装、封装和测试依赖，去除大部分模板噪声。它能回答 manufacturing reliance 和 supply counterevidence，但不能单独回答 platform demand，因此仍是 partial。

这五个候选都在 candidate generation 完成前已经存在，未通过 Gold URL、手工新增文档或运行后注入构造。初次复核又发现 R7 的两个 NVDA child claim 虽然正文与 accession 正确，`source_url` 却继承了母 8-K，点击后看不到所引句子；因此没有把“内容正确”冒充成“血缘也正确”。S1 来源投影改为从已绑定 SEC manifest 解析 Exhibit 99.1 URL，R8 在候选数量、rank 与 typed gap 不变的情况下，把两行稳定改为 `q1fy27pr.htm / exact_accession_exhibit`。

## 4. 18 行业务覆盖的主要形状

- DELL 当期业绩稿：AI 订单、AI server revenue、当前结果和 demand conversion 直接成立；相关三行是完整覆盖。
- DELL 10-K 风险段：直接连接大额 AI 订单、营运资金、组件采购、现金流、取消和库存风险；该行完整覆盖。
- MU 产品段：能证明产品送样和高量产爬坡，但没有 HBM capacity/tightness；部分覆盖。
- TSM 当期稿：能证明先进制程占比、强劲需求与 2nm ramp，但没有 CoWoS/advanced packaging 数量；部分覆盖。
- MU 当期结果：收入和毛利率成立，但缺 price-versus-bit 与 HBM bridge；部分覆盖。
- MU 10-Q 承诺段：客户存款/承诺、资本开支、采购义务与 DRAM 扩产成立，但缺库存和 price-volume bridge；部分覆盖。
- NVDA 当期结果第一段：收入、数据中心收入和毛利率成立，outlook 在下一分块；部分覆盖。
- NVDA 经营现金流对象：只回答 cash flow，不回答客户集中、采购承诺和出口风险；部分覆盖。

## 5. 工程实现与 fail-closed 边界

新增 `s1_internal_qrels_content_requalification.py` 和静态 policy。实现精确绑定 qrels v1.3、既有 Owner acceptance、R8 冻结 candidate observation 与上一轮业务语义审计；每行必须把 target facets 无遗漏、无重复地分成 covered/uncovered。

替换候选必须：

1. 存在于该行自己的冻结 bundle；
2. identity/period strict filter 已应用；
3. ticker 等于 evidence owner；
4. publication date 不晚于 as-of；
5. 仍是 `candidate_only_not_evidence`；
6. candidate digest 有效；
7. replacement 必须有 accession、manifest 与可访问的真实被引文档 URL；`8K_EARNINGS` child claim 只能接受 `exact_accession_exhibit`，不能继续引用母 8-K。

专项测试覆盖 assignment 缺失、facet 漂移、未冻结标准答案注入、digest 篡改、母 8-K URL 混入与越权 successor admission，结果 `8 passed`；连同 qrels review／successor／Owner acceptance和 period／lineage 回归共 `31 passed`。Project OS scoped preflight=`pass / open blocker 0`；当前环境没有安装 Ruff／Black，因此没有把“工具不存在”伪装成格式检查通过，改由 compileall、pytest、`git diff --check` 和尾随空白扫描完成本轮可执行验证。

## 6. 当前 gate 与下一步

历史 qrels v1.3、Owner acceptance 和 R2 指标全部保持不变。内容复核包状态为 `successor_owner_review_pending`，没有生成 qrels v1.4，也没有运行 410 build 或 ranking。

下一步只需要 Owner 确认或退回 5 个 candidate identity 替换；其余 13 行沿用既有接受。确认后才物化 qrels v1.4，然后进入 WSL BGE/GPU + Python + pymilvus + milvus-lite + Linux DB path 的 production binding。真实 410 build、10/10 presence 和 unchanged-matrix ranking 继续保持三个独立步骤。

current-quarter exact `0/6`、external official `4/12`、graph/tool 与 Evidence→Claim→Workpaper→Report 内容质量没有被本轮关闭。
