# DELL / MU / NVDA 三案例交叉订正与基准冻结

日期：2026-08-06

状态：`codex_gold_candidate_cross_review_complete`

## 结论先行

三份报告已经达到“可作为 DeepSeek 对比参考答案”的候选水平，但尚不能自称经过投委会或行业专家复核的正式 gold。

这次研究证明，真正的产品级报告不能从“每家公司各挑几个财务数字”开始。三家公司位于同一条 AI 基建经济链的不同位置，必须互相验证：

```text
hyperscaler / enterprise capex
        ↓
NVDA accelerator + networking + software platform
        ↓
MU HBM / server memory + TSMC advanced node / packaging
        ↓
DELL rack-scale system integration + storage + service delivery
        ↓
customer deployment, utilization and application ROI
```

这条链同时解释了为什么三家公司收入都强，却不能得到同一个投资结论：NVDA 捕获平台租，MU 捕获短缺与产品代际租，DELL 捕获集成、交付和 attach；越靠下游越能验证真实订单与部署，越靠核心瓶颈越能捕获高利润。

## 三案对照

| 维度 | DELL | MU | NVDA |
| --- | --- | --- | --- |
| 当前最强证据 | 订单、收入、backlog、客户数和现金同时增长 | 价格、margin、FCF、SCA、HBM4 shipment | Data Center revenue、margin、FCF、networking、下季 guidance |
| 当前核心机制 | 系统交付、集成、storage/service attach | HBM 结构升级 + 全行业供给紧张 + ASP 杠杆 | GPU/networking/software 平台 + 快速迭代 |
| 最大误读风险 | 把 AI server 高收入当高利润平台 | 把价格周期全部写成 HBM 结构成长 | 把强收入当作终端 AI ROI 已经被证明 |
| 最强反证 | pull-forward、AI 中个位数 OI、营运资本 | bit 增长弱、ASP 峰值、供给响应 | 客户集中、生态融资反身性、自研 ASIC、出口与库存 |
| 当前业务立场 | constructive | near-term constructive | franchise constructive |
| 当前风险回报立场 | valuation cautious | cycle cautious | expectations high |

## 本轮自我订正记录

1. DELL 初稿将 AI 单元盈利写得过于未知。复核 earnings call 后，订正为：公司已披露 AI server profitability 符合中个位数营业利润率目标；缺的是精确当季 AI 独立 P&L 和 FCF，不是完全没有利润方向。
2. MU 初稿正确识别了价格主导，但 SCA 合同强度需要写得更具体。复核后补入 take-or-pay、约覆盖 20% DRAM volume 和三分之一 NAND volume；同时保留“合同不等于固定毛利率”的边界。
3. NVDA 报告没有使用受 USD 15.9B equity gains 显著影响的 GAAP net income 来证明核心运营质量，而改用 operating income、OCF 与简化 FCF。这避免把投资收益误写成主营利润。
4. 三案都取消了“看到 backlog/revenue 就自动给强推荐”的捷径，分别加入利润质量、周期均值回归、客户集中和 price-in。
5. 当前 market snapshot 只提供静态价格/市值/P/E，不足以构造一致的 forward valuation；因此三份报告都拒绝伪造目标价。

## 与旧 9-call 最小链的实质差距

旧链能证明：节点可调用、结构可验证、9 Artifacts 可物化、部分事实不会越权进入输出。它不能证明：

- 研究问题会随证据变化而重新规划；
- 会主动寻找财报以外的产业与下游验证；
- 会把订单、供给、价格、利润、现金和估值连成机制；
- 会用另两家公司给本案提供支持或反证；
- 会识别 MU 的价格/bit 分解、DELL 的 AI vs storage margin、NVDA 的客户集中和生态融资反身性；
- 会在写作后主动反查一手来源并订正结论。

因此，旧 9-call 结果只能叫 `minimum formal anchor / diagnostic artifact`。这三份 Codex 报告才是本项目第一次为三案例建立“研究内容质量优先”的可比较参考面。

## 质量框架复核

评分采用 `docs/eval/fin_agent_investment_research_quality_framework_v0_1.md` 的 0–4 级含义。

| 维度 | DELL | MU | NVDA | 说明 |
| --- | ---: | ---: | ---: | --- |
| D1 问题与边界 | 4 | 4 | 4 | 均以 standard/deep research 处理，无目标价或个性化建议越界。 |
| D2 证据与来源 | 3 | 3 | 3 | 核心事实有一手来源；MCP 全工具面超时、同行/终端面板仍不完整。 |
| D3 财务与指标 | 3 | 4 | 4 | 已完成关键比例重算和量价/利润/现金拆分；DELL 独立 AI P&L 仍缺。 |
| D4 产业传导 | 4 | 4 | 4 | 三案互证并引入 TSMC、Microsoft；没有把经济链假设写成客户事实。 |
| D5 thesis 质量 | 3 | 4 | 4 | 均形成可反驳 thesis；DELL attach/现金的可量化证据最弱。 |
| D6 风险与反证 | 4 | 4 | 4 | 反证进入主文，且有明确 what-would-change。 |
| D7 用户可用性 | 3 | 3 | 3 | 已是完整 memo，但仍需产品 renderer 和可交互证据下钻。 |
| D8 成本与过程 | 3 | 3 | 3 | 没有固定调用次数；MCP 两次长超时暴露运行时效率缺陷。 |

候选结论：三份报告均通过真实性、身份、期间、数值重算、引用、推断边界和 fair-balance hard gates；平均质量达到“可交付/可作为对比基准”区间，但由于 MCP 当前 operational gap、竞争面板与估值面板缺失，只冻结为 `gold_candidate`。

## DeepSeek 对比时的不可妥协节点

后续 DeepSeek 不能只拿最终文风对比。逐节点至少检查：

1. `Research Lead`：是否主动提出量价分解、利润捕获、现金、集中度、估值预期和反证，而不是把三个固定研究单元换个标题。
2. `Search / Evidence`：是否找到发行人、SEC、TSMC/Microsoft 等跨源证据；没有资料时是否保留 typed gap。
3. `Specialist`：是否能形成下列关键判断：
   - DELL：AI 需求已证实，但 AI server OI 只在中个位数、storage 帮助 ISG margin；
   - MU：Q3 爆发主要由价格而非 bit volume 驱动，SCA 强但不取消周期；
   - NVDA：强平台利润与客户集中/生态反身性同时成立。
4. `Lead / Conflict`：是否保留“业务强 ≠ 当前风险回报必然好”的冲突，不把所有证据压成 supported。
5. `Writer`：是否先给 thesis，再解释机制、反证、price-in 和 WWC；不得输出模板化“详见本地绑定事实”。
6. `Verifier`：必须验证数字、期间、引用和推断升级，也要检查报告是否有实质研究内容；不能只验 JSON/schema。

DeepSeek 若在任一关键节点偏离，应暂停该节点，用显式 supervisor correction 修正输入或方法后继续；修正次数、原因和剩余依赖必须进入对比 ledger，最终区分 `model_only`、`supervisor_augmented` 与 `runtime_deterministic` 的贡献。

## 尚未完成

- 合格人工 reviewer 尚未对三份报告逐项签字，故不是正式 gold。
- 尚未把三份报告编译成机器可评分的 claim/evidence/conflict/WWC gold objects。
- 尚未执行同输入、同 as-of、同工具权限的 DeepSeek 节点级对照。
- repo MCP 的 SEC exact-ledger/resource binding 超时尚需单独归因；它不应被误记为 Codex 或 DeepSeek 的研究能力失败。

