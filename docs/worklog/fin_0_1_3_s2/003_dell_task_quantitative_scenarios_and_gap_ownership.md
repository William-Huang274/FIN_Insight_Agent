# S2 工作记录 003：DELL 任务级数值、情景与缺口归属

日期：2026-08-23
实现提交：`af33deab5ef96f2ea94416732c4d4de3f461fd90`

## 1. 为什么做这轮

DELL current Pack 已从 29 条晋升到 48 条 Evidence，但仍有 14 个 residual gap。进入动态 `value_capture` 研究单元前，必须把公司披露的精确事实、本地公式派生、行业区间、研究情景和真正缺口分开，否则下游很容易把行业增速写成 Dell 销量，或用一个情景误关 ASP／PVM／供应分配缺口。

## 2. 做了什么

- 绑定 current DELL Pack `46f37046...38640d` 和既有 source-route replay `ec597ce1...e1fe`，重新编译当前 S2 数值面。
- 保留 38 条 source-bound reported fact 和 27 条带公式 trace 的 deterministic derived metric。
- 从一条已审 TrendForce 行业材料生成两条明确非 Dell 事实的研究区间：2025 全球 AI server 出货基准 `27%–28%`、下行 `20%–25%`。
- 将两个区间编译为 base／downside scenario；没有给 bullish case 伪造数值，因为原资料没有给出 bullish 数值区间。
- 对 current Pack 的 14 个 gap 逐一指定 S1、S1/S2、S2 或 S3 责任层；全部保持 open，全部没有 public-information-gap authority。
- 新增通用 materializer，要求 clean worktree、精确文件 SHA、Pack digest 和 replay digest 后才允许生成 immutable private result 与 public projection。

## 3. 业务结果

- 当前 `value_capture` 单元已有可消费的公司精确事实、公式派生和行业量情景，可用于判断收入、利润、需求和敏感性机制。
- Dell 的精确 ASP、台数、PVM、供应商配额、AI 专属营运资金、PIT 估值等没有被行业材料填造，仍以 typed gap 保留。
- “缺信息”不再是一个混合桶：来源／商业边界回 S1，市场时点或公式输入回 S1/S2，情景计算回 S2，失效阈值与监控阈值回 S3。
- 这只证明一个有界 DELL `value_capture` 动态单元的 S2 输入准备完成，不等于 S1、S2 全阶段、S3、完整 DELL、多 Agent、Writer 或 release 通过。

## 4. 验证与产物

- 定向回归：`9 passed`。
- 全仓回归：`1046 passed`，仅 2 条既有 SWIG deprecation warning。
- materialized public result：`configs/financial_facts/fin_ia_0_1_3_s2_dell_task_quantitative_program_result_v1_0.json`。
- private full result：`data/workbench_private/fin_0_1_3_s2_task_quantitative_program/dell-r1/full_result.json`。
- public result digest：`8031335f656b3dd4598ecac7cfe7ff1f8e957606c308c35c4a23187cd6f3a9f6`。

## 5. 下一门

更新 DELL 任务级 EvidencePackReadiness，使新增 Evidence、S2 区间／情景和 14 个显式缺口共同进入同一任务视图。Readiness 通过后，才建立带 `TokenBudgetBasis` 的零调用动态单元 proof；再决定唯一一次自然 DeepSeek `value_capture` live。
