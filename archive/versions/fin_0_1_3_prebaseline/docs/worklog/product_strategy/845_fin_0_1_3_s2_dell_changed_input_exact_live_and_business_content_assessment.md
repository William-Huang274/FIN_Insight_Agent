# 845 — FIN 0.1.3 S2 DELL changed-input exact-live 与业务内容审计

日期：2026-08-10

状态：exact-live `completed_with_findings`；研究内容有实质改善；交付门因 2 条 L1 未通过；raw candidate 不晋升，不自动重跑

## 这次到底跑了什么

clean proof 后签发的唯一 admission 已 exact-once 消费。DeepSeek Pro 从 corrected `27 Evidence／27 SourceMaterial／14 Gap` Pack 重新执行完整 13 节点链，没有复用旧模型节点：direct baseline、Research Lead、6 位 Specialist、跨单元综合、Draft、Red Team、Final Writer 和 compact Verifier。总计 `13 provider/model calls`、`0 source/tool`、`0 retry/fallback`，usage=`416,493 input／26,152 output／442,645 total tokens`，估算 USD `0.2943542`。所有调用均 `finish_reason=stop`，compact Verifier 本次没有再截断。

公开 terminal result=`c3ffde4e...f610`，完整 request／assistant output 继续只在受限 private capture；公开结果不保存报告原文。最终状态为 `completed_with_findings`，不是产品通过。

## 补源有没有真正改善研报

有，而且不是只增加引用数量。

- 需求：旧报告主要停留在订单和收入。新报告同时使用 Dell 管理层“需求大于供给、backlog 增长”和“内存不确定性促使客户提前锁定基础设施”，再用 HPE 订单消化作独立反证，因此能够区分需求强度与 pull-forward 风险。
- 利润：新报告引入管理层“AI server operating margin 目标为中个位数”，并与 ISG `10.5%` 经营利润率、AI mix 对毛利率的拖累连接，明确“强收入不等于同幅利润弹性”。
- 供给：Micron 对 DRAM/NAND 紧张延续至 2027 年以后、HBM 封装在 2027 上半年扩产，以及 TSMC/CoWoS 扩产进入同一机制链；同时保留 Dell 特定 allocation、交付和良率未知的边界。
- 竞争和反方：SMCI、HPE、客户集中、价格竞争、取消、出口管制和营运资金压力都进入报告，不再是单向 AI 乐观叙事。
- 估值：Alpha Vantage 的 `2026-08-06 USD 437.65/share raw close` 被正确限定为一个 PIT 输入；报告没有据此伪造目标价、便宜/昂贵或投资建议。

Final Writer 为 `8 sections／30 points／10 limitations`，使用 `24/27` 条 Evidence。旧 Pack 报告为 `8／33／14`；当前同输入 direct baseline 为 `8／42／5`，使用 `26/27` 条 Evidence。Agent 不是简单输出更多内容，而是把 direct baseline 压缩成较少判断点并增加边界。决策密度只算小幅改善：executive points 仍过载，供给、现金流和风险在多章重复。

## 为什么仍然有 2 条 L1

这三枚数字都不是凭空编造，但合同责任不同：

1. `16.1`：Dell 官方 transcript 确实写了 AI server revenue `$16.1B`，NumericFact 又保存了更精确的 `$16.132B`。当前编译器只允许 `16.132／161.32` 等展示，没有把来源自己的 rounded surface `16.1` 绑定到同一稳定事实。这是项目侧 presentation compiler 缺口，不是 DS 事实错误。
2. `97.8%` 与 `5000`：SMCI AI GPU 产品增长和 Dell 超过 5,000 位客户都在当前引用 Evidence 原文中，但它们没有进入 NumericFactView；Final Writer 又违反“material number 必须带 NUM ref”合同直接写出。因此这是两面问题：Harness 没有随 enriched Evidence 共编完整数字候选，DS 也没有在无 NUM ref 时克制输出。

由此得到的结构结论是：`Evidence 可见` 与 `数字可交付` 不能靠两套手工清单维护。每次 Pack 改变时，selected Evidence 中可能进入报告的 material number 必须同步生成候选 NumericFact／明确 non-output；来源自己的舍入表面也要自动绑定。否则补源越丰富，模型越容易“引用真实但合同未登记的数字”。

## Agent 链和 Verifier 表现

同输入 direct baseline 被本地门发现 8 条 L1；Red Team 对 Draft 给出 10 个问题和 5 个缺失反方，Final Writer 删除了 `$51.3B backlog`、pipeline multiple 等未获 Numeric authority 的表面，收紧供应商 read-through，并把最终 L1 降到 2。说明多节点链在本案确实带来控制增益。

compact Verifier 完整检查 30 个 claim 并返回全 pass，但漏掉上述 3 个 numeric tokens；确定性 numeric guard 随后拒绝晋升。旧 RC-P36-171 的“长输出截断”因此可关闭，但这次证明模型 Verifier 只能负责语义支持判断，不能替代本地数字、身份、期间和 lineage 门。系统最终没有 false promotion，分层门禁按设计工作。

## 阶段归属与下一步

- S1：bounded anchor 修复和信息增量利用已经在本次 DELL comparison 中得到证明，不因数字合同问题重开 parser。PIT 估值深度、Dell 特定供应 allocation 等 residual gaps 仍留 S1／后续补源。
- S2：RC-P36-170 重新暴露的是“新 Pack 的数字候选没有与 Evidence 共编”。下一项只做零调用的 selected-Evidence numeric candidate inventory、source-rounded alias 和 non-output/masking 处置；不因本次报告立即再付费重跑。
- S3：WWC 阈值、机制桥和内容密度继续归 RC-P36-172，不能塞回 S2 数字修复。

业务结论冻结为：`source increment materially utilized；research quality improved；delivery gate failed；no promotion／no Owner acceptance／no release／no automatic rerun`。

## 收尾验证

- changed-input compiler＋assessment 定向回归：`9 passed`；
- 全部 FIN 0.1.3 S2 contract：`215 passed／3776 deselected`；
- broad 回归首次发现一条历史测试仍要求 RC-P36-171 阻断旧 DELL canary。真实 compact Verifier 已完整 `stop／30 of 30 claims`，所以该容量根因按 live 证据关闭；旧 DELL canary、capture-reuse successor 与 changed-input comparison 改由仍 open 的 RC-P36-170 阻断，避免自动重跑；
- assessment canonical digest、current/prior result SHA、两份 Project OS JSONL 全量解析均通过；
- `repository_and_git_hygiene` scoped preflight=`pass／0 blocker`；
- 本次 post-terminal 审计和文档收口新增 Provider／model／source-network=`0／0／0`。
