# FIN 0.1.3 S1-C 保存 Planner 残差与 S1-D 官方来源传输结论

日期：2026-08-13
状态：`S1C_engineering_slice_closed / S1_product_open / S1D_transport_blocked / no_S3_execution`

## 1. 这轮到底证明了什么

DeepSeek Planner R1 保存的 10 条自然 atoms 没有重跑。预算分层后，本地稳定选择 8 条执行、延期 2 条；8 条请求都进入当前 S1 联合候选与 S2 typed fact 路线。最新零网络运行得到：

- 8 个 EvidenceRequest、5 个 required slot；
- 128 个 `BM25 + Qwen` 候选位置；
- 28 个 typed fact request，其中 19 resolved、9 typed gap；
- 45 个 NumericFact；
- 0 网络、0 生成模型调用。

这证明自然 Planner 输出可以成为真实产品输入，但候选仍不是 Evidence。

## 2. 八个研究问题的业务归责

1. **订单与积压**：Dell Q1 FY2027 的 244 亿美元 AI 订单、161 亿美元 AI 服务器收入和 600 亿美元全年目标已经在库，但只排第 7；前面是逾期应收账款表。主因是 S1-C 选择/角色，不是缺网页。订单、积压、客户数、出货量没有进入 S2 非标准经营指标 mart，继续保留 typed gap。
2. **转化与持续性**：已有客户采用、采购时点波动和 backlog 定义，但缺 244 亿订单如何转成 161 亿收入、积压消化与取消节奏；Dell 法说会是合理的 S1-D 增量源。
3. **已报告业绩**：Q1 FY2027 当期对象已在候选第 2、4、5，六项数值都由 S2 解析；年度材料仍会压过当季材料，属于 S1-C 排序残差。
4. **利润与增量利润**：FY2026 年报已说明 AI 服务器组合令 ISG 经营利润率下降 110bp 至 11.7%；当季数值齐全，法说会只用于补当季机制解释。
5. **现金生成**：Q1 FY2027 经营现金流 40.81 亿美元、自由现金流 31.18 亿美元已存在并解析；无需补源。
6. **营运资金风险**：Dell 已直接披露大额订单需要更多关键组件和营运资金，并带来延期/取消导致的过剩和陈旧库存风险；无需补源。
7. **发行人反方**：同一风险披露已经给出反方机制；当前角色规则仍会对部分真实反方 abstain，因此只能 advisory，不能硬过滤。
8. **上游/需求反方**：NVDA、MU、MSFT 已分别提供产能承诺风险、AI 内存供需与分配、AI 基础设施投资信号；TSM 当前 6-K 不能证明 CoWoS 产能、瓶颈或分配，Q2 2026 transcript 是合理的 S1-D 增量源。

完整机器处置见 `configs/retrieval/fin_ia_0_1_3_s1c_business_residual_disposition_v1_0.json`。

## 3. 为什么没有晋升新排序器

- 确定性金融 ranker 把正例 top10 从 7/15 降至 4/15，MRR 从 0.322 降至 0.227。
- Qwen Cross-Encoder 安全组合没有提高 7/15 recall，MRR 降至 0.136。
- facet-aware Evidence Role 正例兼容率 71.4%、hard negative 拒绝/abstain 77.8%、F1 0.522，仍有 10 个实质角色错误。

所以当前只保留 owner-balanced `BM25 + Qwen` 候选生成和 advisory role；没有 Runtime 晋升，也没有用规则逐句补丁追指标。

## 4. S1-D 两次真实补源

### live-r1：API request transport

- Dell 直连官方 transcript：60 秒 Playwright API request timeout；
- TSM 直连官方 transcript：HTTP 403，返回 HTML；
- 2 次请求、0 retry、0 模型、0 PDF。

### live-r2：真实 Edge 页面会话

- Dell 官方活动页：HTTP 403，尚未点击下载；
- TSM 官方季度结果页：HTTP 403，尚未点击下载；
- 两份 403 页面均在判断链接前保存为 immutable preflight capture；
- 2 个 discovery 请求、0 download、0 retry、0 模型、0 Evidence。

因此，当前根因不是 DS，也不是官方文件不存在，而是本机/当前网络环境无法与两家官方 IR 站点建立被接受的会话。继续换 HTTP 客户端、加重试或写 per-site selector 已不再可信。

## 5. 为什么现在不能直接回 S3

S3 要消费的是合格 Evidence Pack 与 NumericFact，不是 128 条候选。当前：

- NumericFact 路线可用，但 9 个非标准经营指标仍是 typed gap；
- Evidence Role 尚未获得硬门资格；
- Dell transcript 与 TSM advanced packaging 仍未进入产品对象库；
- search index 摘录不能替代 capture-first 原文。

因此没有签发 S3 模型权限，也没有重跑 Planner。下一步需要项目级选择：引入 provider-neutral、可审计的正式 source-acquisition adapter/人工官方文件上传入口，或明确接受两个 typed gap 后只做降级 fixed-pack S3 实验。两者都不等于 S1 产品通过。
