# 2026-08-13 DELL S1／S2／S3 零调用纵切与 Planner Canary 决策

## 问题

在不把 S1、S2、S3 各做各的前提下，验证真实 DELL 研究问题能否同时使用 Qwen＋BM25 叙事候选和 SQL/PIT NumericFact，并判断是否值得进行一次最小 DeepSeek planner canary。Owner 特别要求数据库线不得遗忘。

## 完成

- 新增 provider-neutral Research Objective、planner atom 和 EvidenceRequest 编译合同；模型只能选择小原子。
- 新增 Workbench 受控计划 API，保留每个 S1/S2 子请求结果。
- 建立 BM25＋本地 Qwen Embedding 懒加载候选 Runtime；普通 Workbench 启动不加载权重。
- 修复 filing/current-report date 与 issuer reporting period 混用；重建 compiled object v2，并只重算 16 个真正变化的向量。
- 真实 DELL 零模型纵切完成：5 requests、80 个联合候选、7/7 typed fact resolved、21 NumericFacts、0 gap/conflict。
- 新增 capture-first exact-once Chat Completions 通用 transport 与独立 DeepSeek profile；尚未执行付费调用。

## 业务结论

- 数据库线表现稳定，FY2027 Q1 收入、利润、现金和派生 FCF 均具有期间、单位、accession、capture digest 与公式 lineage。
- Qwen 擅长完整结果/需求语境，BM25 擅长精确风险、定义和业务措辞；联合有价值。
- 候选池仍过宽，年度 10-K 与表格行会压住当前 8-K 或机制证据，不能直接整包交给 DeepSeek。
- 一次 planner canary 值得执行，因为它测试的是当前唯一未观察过的自然规划能力；它不测试模型写报告，也不允许模型改写数据库数字。

## 验证

- 定向合同、Runtime、API 与 capture-first transport：`21 passed`。
- 真实 DELL 零调用 Runtime：5/5 narrative lanes nonempty；7/7 typed fact resolved；21 NumericFacts；0 网络／生成调用。
- 完整回归、active baseline、secret scan 尚待本 release slice closeout 执行。

## 下一步

先完成全量工程复证并提交/推送干净实现；随后以新 run/attempt 身份签发并执行唯一一次 DeepSeek Pro planner canary。自然输出 invalid 时保留 capture、停止且不做字段补丁；valid 时只执行确定性 S1/S2 successor 并审查计划与数据库消费，不自动进入完整报告。
