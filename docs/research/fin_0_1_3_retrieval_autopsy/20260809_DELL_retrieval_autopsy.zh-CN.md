# FIN 0.1.3 DELL 检索尸检

日期：2026-08-09
冻结截至日：2026-08-06
归属：S1 检索与 Evidence Pack 准备；不评价 DeepSeek

## 结论

当前链路能找到 DELL 自身风险披露、Microsoft 的 AI 基础设施投入，以及 Micron、NVIDIA、TSMC 的部分供给信号，但不能自然组成合格的 DELL Evidence Pack。主要缺口不是“完全没有数据”，而是：DELL 当期核心业绩材料在自动排序中落到 top 10 之外；客户信号没有形成 DELL 归因；供应商材料没有补齐 HBM、CoWoS、部件约束和对 DELL 交付的直接连接。

因此当前 DELL 检索状态是 `material_candidates_present / complete_evidence_pack_absent`，不能进入产品级研报验收。

## 四路对照

### A：当前产品自动内源检索

- Microsoft customer-demand：目标候选排第 2，但第 1 是 Microsoft 365 / LinkedIn 等宽泛云业务内容。
- DELL issuer-results：真正的 Q1 FY2027 业绩候选排第 12，top 10 被供应链风险、定义、前瞻声明和历史表格占据。
- DELL regulatory：目标排第 1，能找到大客户、AI 订单、营运资金、现金流和取消风险。
- Micron supply：目标排第 2，但前排混有宽泛的行业供给和模板内容。
- NVIDIA supply：目标排第 2；可见第三方制造、组装、封装和测试依赖，但同时混有 outlook 和安全港文本。
- TSMC supply：只有 3 个粗粒度当前文档片段，主要是财务摘要和联系方式，没有 CoWoS 容量。

### B：Codex 监督、复用同一内源工具

只改变查询表达，不换索引、不增数据、不加载 qrels：

- Microsoft：第 2 升到第 1，首条变成 AI 基础设施持续投入和 AI 使用增长，证明查询编译确实影响结果。
- DELL issuer：第 12 降到第 13，说明长而具体的查询仍被底层按宽松 OR token 处理，不能稳定压过模板和风险词。
- DELL regulatory：保持第 1。
- Micron supply：第 2 降到第 7。
- NVIDIA supply：第 2 升到第 1。
- TSMC supply：第 1 降到第 2，但仍只有财务摘要，没有 CoWoS 实质内容。

这说明人工把问题写得更好只能改善部分排序，不能弥补源缺失、chunk 质量和检索语义问题。

### 外源工具／capture replay

现有外源正式选择只给 DELL 留下一份 regulatory filing。issuer results、customer demand 和 supply 三个 required slot 都是 typed gap。Firecrawl 第一次请求即因额度返回 429，后续 23 条查询按合同停止；这证明失败结果留存正常，但不证明外源覆盖可用。

### C：独立参考研究

独立研究在 A、B 完成后进行，没有向 A/B 注入 qrel identity 或标准答案 URL。参考资料显示，一份可用的 DELL 研究至少要同时处理以下事实：

- [DELL Q1 FY2027 业绩稿](https://investors.delltechnologies.com/news-releases/news-release-details/dell-technologies-delivers-first-quarter-fiscal-2027-financial)：收入 438.42 亿美元，AI server orders 244 亿美元、AI server revenue 161 亿美元，全年 AI server revenue 指引约 600 亿美元；ISG 收入 290.09 亿美元、经营利润 30.55 亿美元、利润率 10.5%。
- [DELL Q1 FY2027 电话会](https://investors.delltechnologies.com/static-files/b63ffff9-b729-403b-a231-c6af05667759)：backlog 513 亿美元、客户超过 5,000 家，pipeline 高于 backlog；同时管理层明确承认有为锁定供应和规避涨价而提前采购的成分，且 AI server operating income rate 目标只是中个位数。
- [DELL Q1 FY2027 10-Q](https://www.sec.gov/Archives/edgar/data/1571996/000157199626000030/dell-20260501.htm)：AI server mix 压低毛利率，应收账款从 176 亿美元升至 259 亿美元，经营现金流 41 亿美元；需求增长同时占用营运资金。
- [Microsoft FY2026 Q3 电话会](https://www.microsoft.com/en-us/investor/events/fy-2026/earnings-fy-2026-q3)：Azure 增长和大额 AI 基础设施资本开支能证明行业需求及容量约束，但不能直接证明这些订单属于 DELL。
- Micron、NVIDIA 与 TSMC 的最新披露能分别支持内存紧张、第三方制造依赖和先进封装扩产；但公开材料没有直接给出它们分配给 DELL 的数量。

由此得到的参考判断不是简单的“需求强”：需求确实强且客户面扩大，但部分订单包含提前采购；利润捕获受 AI server 较低利润率约束；供应与营运资金决定 backlog 转收入的节奏。需要持续观察 backlog 转化、取消、AI server margin、应收账款和部件供给。

## Evidence Pack 可用性

| Required slot | 当前材料 | 手工判定 |
| --- | --- | --- |
| issuer results / management commentary | 核心业绩候选存在，但 A/B 分别排第 12/13；电话会机制材料未被稳定带出 | 部分；自动 pack 不合格 |
| regulatory / financial reconciliation | 10-K/10-Q 风险、营运资金和现金流候选较强 | 可用，但仍需与当期业绩绑定 |
| customer demand / deployment | Microsoft AI 投入可见 | 只能证明行业需求，不能做 DELL 客户归因 |
| supply capacity / counterevidence | Micron/NVIDIA/TSMC 各有片段 | 缺 HBM/CoWoS 定量和对 DELL 分配关系 |

## 根因与归属

- S0：电话会／prepared remarks 和 TSMC 先进封装材料没有形成足够细、可检索的当前对象；模板、表头和宽 chunk 比例过高。
- S1：查询仍近似宽松 OR；一个 supply slot 同时承担多个独立 facet；graph 没有可靠期间；SQL 被错误地用于定性 bundle；dense 未投入当前产品检索。
- S3：即使候选都在池内，也缺少“强需求—提前采购—供应约束—营运资金—利润率”的动态追问与机制综合。
- S4：页面内容单薄是上游 Evidence Pack 不完整的结果，不是先改 renderer 就能解决的问题。

本轮未修改产品代码、未提升候选为 Evidence、未执行模型调用。
