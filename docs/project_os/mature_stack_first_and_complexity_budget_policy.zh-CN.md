# 成熟技术栈优先与复杂度预算规范

日期：2026-08-30
状态：ACTIVE / REPOSITORY-WIDE / CROSS-SESSION MANDATORY
Owner correction：停止把通用工程治理和运行时继续扩写成 FIN 自研系统；先采用或实测成熟方案，把自研资源留给金融研究权威与产品差异化。

## 1. 为什么要有这份规范

FIN 在 R3–R14 期间逐渐把单次失败、attempt 恢复和局部语义修复固化成长期架构。到 2026-08-30：

- DELL R-number 版本化实现已约 55,032 行；
- R14 单轮增加 26,568 行，唯一 preview 仍有 239 个 case failure、277 个 event mismatch；
- `project_os_preflight.py` 约 14,870 行，tracked configs 约 1,190 份；
- 真正差异化的 `src/financial_facts` 反而只有约 1,804 行；
- 随后的产品迁移计划又膨胀为约 57 万字的自研 ticket/CAS/receipt/reducer 协议，而成熟栈安装、真实 slice 和产品集成尚未开始。

这说明问题不只是“文档太长”，而是责任边界错了：为了证明自研控制面本身正确，项目持续制造新的控制面；规划和治理开始替代产品交付。

本规范把这次反思变成跨任务硬约束。它不是新的审批协议，也不要求为普通动作再造一套 receipt 系统。

## 2. 三层责任边界

### 2.1 第一层：FIN 产品与金融研究权威——必须自己拥有

FIN 自研只聚焦这些决定产品正确性的能力：

- issuer/case/as-of/period/version/lineage；
- source role、使用权、citation eligibility；
- `Candidate`、`Evidence`、`NumericFact` 的权限分离；
- Evidence admission、GapEligibility、reject/reopen reason；
- PIT、unit、scale、dimension、vintage、revision、conflict；
- 产品/经营事实到收入、成本、利润、现金的 typed bridge；
- claim ↔ passage/page/table/cell locator；
- materiality、causal boundary、counterevidence、WWC；
- FIN gold、hard negatives、human rubric、report/release acceptance；
- 面向分析师的 Evidence/Gap/Review/Workpaper 产品交互。

“自己拥有”指 FIN 定义 canonical contract 和最终裁决权，不代表数据库、队列、工作流、模型传输、搜索引擎或 UI 基础控件也要自己实现。

### 2.2 第二层：工程治理与软件供应链——优先直接采用

以下能力默认交给成熟工具：

- Git branch/ruleset、CODEOWNERS、pull-request review、CI checks；
- 依赖锁定、license/SBOM、artifact signing、secret scanning；
- ADR 记录架构决定；
- 标准测试框架、静态检查、包管理和发布流水线。

Project OS 只保存当前事实、产品权限、根因和跨任务交接；不得复制 Git、CI、数据库或工作流引擎已经负责的状态。

### 2.3 第三层：运行时、持久化与可观测性——先资格验证成熟栈

以下能力不得默认自研：

- 工作流调度、重试、checkpoint、resume、HITL；
- 并发、锁、事务、队列、worker 和长任务恢复；
- canonical metadata store、artifact store、snapshot；
- experiment/run/trace/eval/lineage backend；
- crawl/WARC、XBRL、PDF/OCR/layout/table；
- hybrid retrieval、vector index、embedding/reranker serving；
- provider SDK、结构化输出 transport、通用 policy/IAM；
- citation/bibliography/report rendering。

FIN 在这一层只写薄 adapter、FIN canonical envelope 映射、幂等业务边界和 hard validators。

## 3. Build / Adopt / Hold / Retire 的默认判断

对每项能力按以下顺序回答：

1. 它是否直接决定 FIN 金融事实、研究质量或发布权威？如果是，保留 FIN canonical contract 与裁决逻辑。
2. 市场是否已有维护活跃、许可可接受、可退出、能在 FIN 环境实测的成熟组件？如果有，默认 `ADOPT` 或 `ADOPT_PILOT`。
3. 成熟组件缺失的是否只是 FIN schema 映射、权限边界或少量 hard validator？如果是，只写薄 adapter，不重写组件。
4. 是否有冻结 fixture/benchmark 证明成熟候选在关键金融 slice 上失败，且失败无法通过配置、adapter 或合理的组合解决？只有这时才允许提出 `BUILD`。
5. 能力需求或规模尚未出现时标为 `HOLD`；旧实现只有在 shadow/dual-read/rollback 证明后才 `RETIRE`。

任何新增通用自研系统必须在 ADR 中记录：成熟候选、实际测试证据、不可满足的 FIN 需求、最小自研范围、维护 owner、退出路径和删除哪些重复代码。缺一项则不得开工。

## 4. 复杂度预算与停止线

### 4.1 规划预算

- 一个新方向只允许先写一份足以开工的 bounded baseline：目标、非目标、候选、真实 slice、验收、停止、回滚。
- 计划不得模拟未来运行时的每个 ticket、CAS、reservation、reducer、receipt 和崩溃排列；这些属于所选工作流、数据库、CI 和测试系统。
- 同一决策只保留一个 current ADR/基线；旧文档原位标记 superseded，保留历史，不继续并行修订。

### 4.2 强制止损

出现任一情况必须停止扩写并向 Owner 说明：

- 连续两个有意义的工作包只有计划、review、schema 或治理文档，没有可执行资格结果、代码集成、产品证据或实测指标；
- 为了执行一个普通读取、测试或隔离 pilot，需要再造新的授权状态机；
- 自研控制代码/文档规模开始超过它保护的业务逻辑，且没有量化风险收益；
- 同一失败再次产生新 runner/schema/policy/successor，而不是修根因或采用成熟能力；
- 讨论“如何证明可以开始”所花的工作明显超过最小可逆 slice 本身。

止损后的默认动作是：缩小 slice、删除非必要流程、使用成熟组件的原生能力、运行一个可逆实验，再据结果决定。

### 4.3 安全与动作风险相称

高风险动作包括生产切换、删除、覆盖不可变证据、paid/external call、secret、公开发布和不可逆迁移；它们需要明确范围、回滚和 receipt。

普通读取、磁盘/依赖审计、文档更新、本地测试、isolated venv、固定 fixture 的无生产切换 pilot 不得套用删除级协议。安全的目的是真实降低风险，不是增加仪式数量。

## 5. 真实切片优先

每个成熟栈候选必须用一个最小但真实的 FIN slice 证明，而不是只比较功能表：

- 使用一组冻结、无私密泄漏的真实或 case-correct fixture；
- 固定版本、依赖、许可、环境和输入 digest；
- 记录成功和失败，不修改现有 truth、R14 failure 或 Evidence authority；
- 至少测正确性、恢复/退出、资源/延迟、隐私/日志和 adapter 厚度；
- 最终只给出 `ADOPT / CHALLENGER / HOLD / REJECT`，不长期维护所有候选。

资格实验优先使用候选的官方 CLI/API、标准 `pytest`、Git/CI 和数据库原生约束。不得为资格实验先造一套 FIN 专属实验执行协议。

## 6. 控制面选型必须先分清问题

不得把所有“流程”统称为 Agent orchestration：

- 批处理、数据资产、schedule、observable pipeline：比较 Prefect、Dagster 等数据工作流；
- 跨 worker、跨天、强恢复、signal/timer、SLA：达到触发条件后再比较 Temporal；
- 单次研究会话内的模型/tool state、interrupt/HITL：可比较 LangGraph 等 Agent runtime；
- 事务、唯一性、锁和权威状态：由 PostgreSQL 等数据库负责；
- run/metric/artifact/trace：由 MLflow、OpenTelemetry/OpenInference、OpenLineage 等成熟系统负责；
- 产品/S-stage/FIN admission/release：仍由 FIN domain kernel 负责。

一个项目可以组合这些能力，但每个责任只能有一个 primary owner；不得用 Markdown ledger 模拟其中任何一个运行时。

## 7. 仓库边界

目标结构原则：

~~~text
src/fin_domain/          FIN canonical contracts and authority
src/fin_adapters/        thin adapters to qualified mature components
src/fin_application/     use cases that compose domain + ports
src/fin_product/         Workbench/report-facing application surface
tests/domain/            FIN invariants and gold
tests/adapters/          component contract tests
tests/qualification/     isolated candidate slices, no production authority
configs/qualification/   exact small manifests; no secret or large artifact
docs/adr/ or architecture/repository/  current architecture decisions
Z:/...qualification...   venvs, images, models, databases, large results
~~~

这是迁移方向，不授权一次性移动全部代码。旧代码按 `retain / wrap / replace / regression / retire` 标记，并通过 adapter/shadow 分波迁移。

## 8. 进度汇报与完成定义

每次汇报必须分别写清：

- 产品增量：用户可感知能力是否改变；
- 工程增量：安装、代码、集成、迁移或测试增加了什么；
- 资格/研究证据：跑了什么、结果是什么；
- 文档/治理：只作为记录，不冒充实现；
- 未完成：当前最早 blocker 和下一真实动作。

“完成了一份计划”“通过了计划审查”只能算文档/治理进度。除非已有可执行结果，否则不得说“实施已开始”或“Phase 已完成”。

## 9. 本次纠偏的立即应用

1. 原 57 万字 Phase 0–7 自研 plan-execution protocol 降为 audit-only，不再修订其状态机。
2. 用简洁 ADR 和执行基线承接仍有效的产品事实、R14 冻结和迁移目标。
3. 在 Z 盘隔离环境运行成熟控制面/数据面的首个真实 FIN slice；不改生产，不删除 `D:\FIN_Insight_Agent\data\indexes`。
4. 复核既有 S1–S5 Build/Adopt/Hold/Retire 审计，给每项能力绑定旧模块处置和目标成熟 owner。
5. 只有资格证据支持的 winner 才进入 adapter 集成；失败候选退出，不追加长期治理表面。

## 10. 跨会话记忆位置

本规范通过以下位置共同生效：

- 根 `AGENTS.md`：最短硬规则，每轮任务自动读取；
- 本文件：完整判断与停止线；
- `current_context_pack.zh-CN.md`：当前纠偏状态和下一步；
- capability/root-cause ledgers：当前机器投影；
- source ADR、产品审计和工作日志：保留证据与历史。

以后若再次出现“连续规划但没有真实工作”，应把它视为本规范的执行失败，而不是继续补一份计划。
