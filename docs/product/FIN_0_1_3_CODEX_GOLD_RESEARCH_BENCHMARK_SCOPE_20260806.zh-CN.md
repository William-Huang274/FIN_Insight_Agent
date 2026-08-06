# FIN 0.1.3 Codex 三案例 Gold Research Benchmark 范围

日期：2026-08-06  
状态：`active / three gold candidates complete / hybrid-tool truth recorded / shared benchmark evidence freeze next`

## 1. 决策

暂停把当前九次模型调用的 formal Anchor 当作 S3 产品级研究证明。当前 Anchor 继续保留为最小合同与链路诊断证据，不撤销、不追认产品质量。

在继续产品级 S3 证明前，Codex 先作为研究 supervisor，针对 DELL、MU、NVDA 三个案例执行一次真实研究，形成三份可追溯、可订正、可由合格研究者复核的参考研报。完成三份参考答案后，先让 DeepSeek 在相同冻结 Evidence Pack 上做零检索分析对照；待 MCP 与外部来源链修复后，再执行从检索开始的端到端 Agentic Search/Research 对照。

## 2. Gold 的诚实含义

`gold` 不表示 Codex 天然正确，也不表示已经获得 Product Owner 或 qualified financial reviewer 接受。它表示：

- 研究问题和截至时点冻结；
- 重要事实有原始来源、发布日期、抓取时间和引用；
- 重要数字经独立复算或与权威表格核对；
- 主结论、最强反方、冲突、缺口和 What-Would-Change 明确；
- 研究过程和修订记录保留；
- 三案例使用同一质量 Rubric；
- 合格人工 reviewer 可以逐条接受、退回或修订。

在人工接受前，对外只称 `Codex-authored gold candidate`。

## 3. 数据与工具范围

研究不局限于财报。允许且鼓励使用：

- 当前 FinSight MCP：SEC/本地检索、精确数值台账、市场快照、行业快照；
- 仓库现有 BM25/BGE/SQL、关系图、产品/供应链/客户部署和资本市场数据；
- 公司官网、SEC、监管机构、行业组织等一手公开来源；
- 公开网页搜索、网页/PDF 抓取与解析、RSS/GDELT 等发现工具；
- 必要的高质量二手来源，但必须与一手来源区分 authority。

工具或数据只是合同、fixture、历史 PoC 或未接入 runtime 时，必须如实标注，不能冒充当前 MCP 已执行能力。

### 3.1 2026-08-07 工具使用完成审计

三份 Gold candidate 是混合研究产物：Codex 使用了产品已有本地数据和研究合同、可正常工作的 MCP market handler，并通过允许的外部公开来源补足官方证据。当前 stdio MCP 的 initialize/list-tools 成功，但 SEC search 与 exact-ledger 出现资源绑定或超时，登记 RC-P36-140；因此不得把三份报告表述为“完全由当前产品工具自主产出”。

下一项不是直接比较最终报告，而是把 Gold 使用的重要官方事实、数值、来源和 lineage 编译成共享 Benchmark Evidence Pack；Gold 的 thesis、机制综合、反方结论、WWC 答案与评分保持隐藏。只有输入证据真正一致，Experiment A 才能评价模型分析能力。

## 4. 研究交付最低内容

每案最终报告至少包含：

1. 执行摘要、当前 thesis、信心与关键分歧；
2. 由 Research Lead 选择的高价值研究单元，而非固定栏目填充；
3. 产品/技术、需求/客户、供应链/竞争、财务传导、资本市场/估值和风险证据；
4. 关键数字、公式、时间口径和来源坐标；
5. 最强 counter-thesis 与支持它的真实证据；
6. 跨单元 dependency/conflict 的 resolve/defer/block；
7. 可观测 What-Would-Change、下一证据路线和监控项；
8. 集中的证据边界与未解决缺口；
9. claim-to-source lineage 和研究运行记录。

## 5. 调用与停止原则

不预先把模型调用固定为 9 次或 15–25 次。调用规模由研究问题、证据缺口和收敛状态决定。只有以下情况继续调用或检索：

- 能关闭一个 material evidence gap；
- 能验证或推翻一个核心机制；
- 能解决跨单元冲突；
- 能提高重要数字或时间口径的 authority；
- 能形成可执行的监控条件。

重复摘要、边界套话、无新增证据的改写和纯格式性调用应停止。费用不是首要目标，但每次调用必须产生可审计的信息增益。

## 6. 与现有版本和 S 阶段的关系

本工作不创建 FIN 0.1.4，也不把失败 attempt 升格为产品版本。它是 FIN 0.1.3 内的 pre-S3 产品基准与 dogfood correction：

- 当前 formal Anchor：保留为 `minimum formal anchor / diagnostic`；
- Codex 三案研报：`gold candidate`；
- DeepSeek 对照 A：共享 Evidence Pack 冻结后开始，只评价同证据分析与综合；
- 工具修复：RC-P36-140、当前外部来源和 Agentic Search 质量门归 S1 successor；
- DeepSeek 对照 B：工具门通过后，从检索开始评价端到端 Agentic Search/Research；
- S3 product proof：只有 DeepSeek/产品 runtime 在相同合同下形成可接受内容，并通过八维质量与人工接受后才成立。
