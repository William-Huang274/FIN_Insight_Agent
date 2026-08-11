# WorkBuddy 专家 / Skill 配置变体 A/B 校准审计

- audit id：`workbuddy_expert_configuration_variants_20260712_v0_1`
- status：`pass`
- variant count：`2`
- 边界：只审可观察工具轨迹，不读取或保存 raw CoT；变体不覆盖基准 case；WorkBuddy 事实不得直接晋升 FIN pack。

## 总结

专家配置和渐进式 Skill 可以显著提升行业框架、报告结构与前端完成度，但当前两个变体仍只有一个可观察 Agent，且没有 claim-local lineage、来源打开核验、数值程序或写后语义修复。

## WB-S01B（基准 WB-S01）

- disposition：`redesign`；severity：`high`。
- 可观察 Agent：`1 -> 1`；subagent/handoff：`0 -> 0`。
- 模型调用：`16 -> 15`；工具调用：`28 -> 29`。
- WebSearch：`12 -> 4`；结构化金融查询：`0 -> 13`；source-open：`0 -> 0`。
- HTML：`46962 -> 36818` bytes；表格：`9 -> 9`；外链：`16 -> 0`。
- numeric cell claim-local linkage：`0.0 -> 0.0`。
- 实际调用 Skill：Deep Research, deep-research, neodata-financial-search, web-scraper。

### 能力发现

- 领域配置显著改善了 Decision Surface、传导链、What-Would-Change、缺口披露和报告结构。
- NeoData 认证失败后被识别并修复，构成真实但有界的工具恢复行为。
- 可观察轨迹中仍只有一个 cli agent；界面选中的专家标签没有产生独立 subagent 或 handoff。
- 实际只调用 deep-research、neodata-financial-search 和 web-scraper，多个界面选中 Skill 未调用。
- Writer 丢弃了 NeoData request id、as-of metadata 和 source URL，数字 claim-local link 仍为零。
- 凭证材料进入工具轨迹和 shell 命令，没有保持 runtime 持有和 trace 脱敏。

### 质量发现

- Salesforce 当前 ARR/用量指标与较早季度的付费交易数混用，使单客户 ARR 计算失效。
- 报告称 Salesforce cRPO 增速未披露，但当前官方季度已经披露。
- Datadog 客户数、Top 20 渗透率和百万美元 ARR 客户数被语义合并。
- Snowflake 全年产品收入和时点采用指标缺少 period-local binding。
- 报告列出多个来源家族却没有外部链接，并在缺少 suitability/permission gate 时给出组合权重。

### 允许吸收

- 四层产品采用到财务捕获 Decision Surface
- 将 What-Would-Change 作为一等研究界面
- 显式数据缺口与 proxy 表
- 席位制与用量制变现对比
- observe-failure-select-fallback 工具循环

### 必须重设计

- Writer 投影必须保留 evidence lineage 和 period metadata
- 区分 UI selected、context injected 与 actually invoked capability
- 强制 freshness reconciliation 和 NumericProgramTrace
- 凭证移出模型上下文并对 trace 脱敏
- 排名、权重和建议必须受用户授权及 approval policy 控制

## WB-S02B（基准 WB-S02）

- disposition：`redesign`；severity：`high`。
- 可观察 Agent：`1 -> 1`；subagent/handoff：`0 -> 0`。
- 模型调用：`19 -> 34`；工具调用：`47 -> 34`。
- WebSearch：`0 -> 12`；结构化金融查询：`17 -> 0`；source-open：`0 -> 0`。
- HTML：`51838 -> 83186` bytes；表格：`10 -> 23`；外链：`7 -> 7`。
- numeric cell claim-local linkage：`0.0 -> 0.0`。
- 实际调用 Skill：us-stock-analysis, earnings-tracker, deep-research。

### 能力发现

- 领域 Skill 组合生成了更丰富的银行本体、23 张表、2 个 SVG 决策图、显式 MISSING/STALE 标记和 7 个外链。
- 新版正确把 Wells Fargo 资产上限视为已解除，而非当前约束。
- 可观察轨迹仍只有一个 cli agent；6 个 task 是规划记录，不是独立 subagent。
- Runtime 执行了 12 次 WebSearch，但没有 source-open、官方 filing parser、结构化金融查询或写后研究修复。
- 报告只检查文件存在和大小，没有验证脚本语法、图表数据、claim 一致性和数值语义。

### 质量发现

- 报告依据低权威搜索摘要，把 0.25%、0.65%、0.56% 和 0.64% 标为 2024 年银行存款成本；官方文件显示总存款利率和定义显著不同。
- 市场价格、目标价、季度经营事实、2024 存款利率 proxy 和估算值混在一起，缺少统一 as-of 与 metric-definition contract。
- 数字表格单元格没有 claim-local link；7 个外链集中在脱离 claim 的来源清单。
- CRE、估值和目标价判断依赖二手摘要与估算，没有可执行计算或 row lineage。
- 报告诚实暴露缺失数据，但停止前没有执行邻居/来源扩展或 evidence repair loop。

### 允许吸收

- 银行专属存款-NIM/NII-信用-资本-ROTCE 传导机制
- 显式 MISSING 与 STALE 界面
- 资产负债表传导图
- 监管与压力测试事件面板
- 银行专属 What-Would-Change 阈值

### 必须重设计

- 每个银行指标绑定 entity level、合并口径/银行子公司、period、FTE 状态和计算定义
- 二手比较摘要之前必须优先 issuer、SEC、FFIEC 和 Federal Reserve
- 存款利率、NIM、资本和估值采用确定性程序
- 必须打开并验证一手来源，不能只复制搜索结果 URL
- 执行写后 contradiction、freshness、numeric 和 citation 检查

## 生态位与替代压力

### 当前高压区

- 零售与 prosumer 投资研究
- 通用分析师初稿
- 外观接近 client-ready 的 HTML 与 dashboard
- 广泛公开网页公司比较
- 通过 Skill 快速分发领域研究方法

### 尚未被替代

- claim-local provenance 与可复算 NumericProgramTrace
- 带 revision/supersession 的 point-in-time accepted fact memory
- 私有数据与商业授权机构数据集成
- 带权限的 durable workflow 与 reviewer accountability
- memo/model/deck/dashboard 跨产物一致性
- 受监管的 model-risk、retention 与 approval control

### FIN 必须响应

- 把领域 Skill 和精美多格式输出视为基础能力，而不是差异化。
- 差异化转向证据控制、数值可复算、point-in-time memory、私有数据集成和机构工作流。
- 显式展示 selected capability 与 invoked capability，并保留完整 trajectory provenance。
- 持续对标通用 Agent 平台，评估替代压力和用户画像匹配，而不只评报告正确率。
