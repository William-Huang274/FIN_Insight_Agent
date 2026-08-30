# FIN 0.1.3 成熟栈优先架构决定与执行基线

日期：2026-08-30
状态：ACCEPTED BY OWNER / STEPS 1–3 ACTIVE
性质：人类可读的架构决定与有界实施基线，不是 runtime authority source，不定义 ticket、epoch、CAS、receipt 或 reducer。

## 1. 决定

1. 停止继续设计和实现旧 Phase 0–7 中 `E0-Cj/H/F/S/T/G/Z`、ticket、CAS、reservation、reducer、receipt 组成的自研计划执行协议。
2. 原约 570 KB 执行程序完整保留为 audit-only 历史，失去执行权；不删除、不追认 PASS，也不再补它自己的 protocol finding。
3. 工程治理使用 Git/CI/CODEOWNERS/ADR/SBOM 等成熟能力；事务、锁、唯一性、工作流、checkpoint、HITL、trace、experiment 和 lineage 分别由经过资格验证的成熟组件负责。
4. Project OS 回到“当前事实、产品权限、根因和跨任务交接”的最小记忆层，不再承担并发运行时或自授权控制面。
5. FIN 自研范围收缩为金融研究 domain kernel、canonical contracts、hard validators、thin adapters、FIN gold 与产品验收。

## 2. 为什么停止旧方向

旧方向的出发点是保护 R14 的真实高风险边界：失败不可隐藏、责任层不能后传、删除必须谨慎、不可逆动作要可恢复。这些原则仍然有效。

错误在于把删除/生产级安全强度推广到读取、计划、review、Git 和隔离实验，并把“计划可审计”误等同于“先自建一套授权计划本身的 runtime”。每个 review finding 又增加状态、票据和转换，最终控制面成为主要产品。

证据包括：

- 旧工作区草案约 `570,727 bytes / 2,182 LF lines`，包含大量自定义 lineage、状态、CAS 和 action family；
- 它在成熟组件尚未安装、真实 qualification 尚未运行、产品增量仍为 0 时已迭代到多轮 working candidate；
- DELL R-number 版本化实现约 55,032 行，R14 单轮新增 26,568 行但 product capability delta 为 none；
- `project_os_preflight.py`、1,190 份 tracked configs、research runners 和 ignored eval artifacts 已形成显著维护面；
- Owner 明确指出“做了一天仍在制定 Phase 0–7 技术文档”，要求第二、第三层先借鉴/采用成熟方案并立即实测。

这是一种架构责任错误，不是准确性要求太高。Git、CI、PostgreSQL、工作流引擎和实验平台已经为通用问题提供成熟实现；FIN 应在它们之上表达业务不变量。

## 3. 仍然有效的历史事实

- branch=`codex/fin013-dell-s1-s2-product-bridge`；本次起点 HEAD/upstream=`1472ecef4f02adfb51f5fcd1474dc844554ab5dd`；
- R14 frozen commit=`7e25cad95ee84b39fb2a51063100405bc27da6e5`；
- 唯一 preview=`27,026 total / 26,787 pass / 239 fail / 277 mismatch`，event/assertion=`228/11`；
- RC-S1-109/110 保持 open，旧 parser/output 只作 regression baseline，不作 truth oracle；
- 不创建该责任命名空间的 R15/R16，不进入 R14 formal；
- 成熟组件输出不能自动成为 Evidence、NumericFact、Gap closure 或 release verdict；
- 历史失败不可覆盖；旧代码退役要经过 adapter/shadow/rollback；
- `D:\FIN_Insight_Agent\data\indexes` 当前不删除。若未来实测证明 D 盘空间确是 blocker，只能按 Owner 已授权的严格范围删除其下文件、保留根，并接受旧 retrieval 暂停和新架构重建。

## 4. 三层责任和当前候选

| 问题 | Primary owner | 当前动作 | FIN 保留 |
|---|---|---|---|
| Git/review/CI/supply chain | Git hosting + CI + standard scanners | 复用现有 Git；补规则/ADR，不造状态机 | product/stage authority annotations |
| 数据/批工作流与可观测资产 | Prefect vs Dagster qualification | 用同一最小 FIN slice 比较，只留一个 primary | FIN job input/output contracts |
| 长时跨 worker durable execution | Temporal | trigger-gated；没有多 worker/长时/SLA 证据则不安装为主栈 | external side-effect idempotency |
| Agent session/HITL | LangGraph | 与数据工作流分责；后续单研究 vertical 再测 | domain state and human decision |
| transaction/locking/canonical metadata | PostgreSQL | transaction/constraint/locking/backup smoke | FIN canonical schema/authority |
| run/metric/artifact/trace | MLflow + OTel/OpenInference | actual run + metric + artifact + trace/export smoke | immutable FIN receipt remains authority |
| cross-system lineage | OpenLineage concepts/client | 优先采用标准 event；真实跨系统 consumer 出现后才部署 backend | FIN source/artifact digest mapping |
| large data/model versioning | DVC | 达到 large-artifact trigger 才 pilot；不管理小 receipt | frozen dataset manifest/digest |

LangGraph、Prefect/Dagster、Temporal 不是“三选一全局框架”：它们分别面向 Agent session、数据/研究 pipeline、长时分布式 durable workflow。PostgreSQL 负责事务权威，MLflow/OTel 负责观测；任何框架都不获得 FIN Evidence 或产品版本权威。

## 5. 当前三个真实工作包

### 工作包 1：旧方向收口

- 根 `AGENTS.md` 与 Project OS guideline 写入成熟栈优先、复杂度预算、风险分级和真实切片优先；
- 旧执行程序只加 supersession banner 和失效状态，不重写全文；
- 本文件承接当前决定与执行基线；
- 更新 context、ledgers、worklog，并以普通 Git commit 保存；
- 不运行旧协议自己的 Phase 0。

### 工作包 2：成熟运行底座真实资格切片

在 Z 盘建立隔离 lab，用同一冻结、公开、无 secret 的 FIN fixture 运行：

~~~text
fixture（issuer/as-of/period/unit/locator + valid/invalid candidate）
  → Pydantic/FIN contract validation
  → Prefect or Dagster workflow
  → PostgreSQL state/metadata/unique/transaction
  → deliberate failure and native recovery observation
  → MLflow run/metric/artifact
  → OTel span and optional OpenLineage-compatible event
  → digest-bound export that remains rebuildable
~~~

每个实际候选记录 exact version、Python/OS/profile、license、dependency snapshot、安装大小、启动方式、fixture result、failure behavior、资源、export/cleanup。资格代码优先使用候选官方 CLI/API、标准 pytest 和数据库原生约束，不发明 FIN 专属实验执行协议。

Temporal 本轮只核对触发条件与部署成本；没有多 worker、跨重启长任务、timer/signal 和 SLA 就保持 HOLD。DVC/OpenLineage backend 也只有在 large-artifact/跨系统 lineage consumer 触发后才实装，不能为了“栈完整”强行部署。

### 工作包 3：S1–S5 迁移审计 reconciliation

复用已经完成且作者分离复审过的产品审计和 mature-stack landscape，只做：

- 检查审计基线以来代码、依赖和产品事实是否漂移；
- 补充工程治理、数据工作流、Agent runtime、数据库、experiment/trace/lineage 的分责；
- 对模块标记 `retain / wrap / replace / regression / retire`；
- 为 Adopt 项绑定 mature owner、thin adapter、qualification evidence、migration dependency、rollback 和产品验收；
- 给 Owner 一张可读的差异表，不再从零扫描一天。

## 6. 资格验收和停止条件

通过要求：

- FIN critical fields round-trip exact；
- 成熟组件只拥有其责任层，不改变 Evidence/release authority；
- 失败可观察、可解释，恢复/重试不静默重复外部副作用；
- adapter 足够薄，不复制框架核心；
- 小型结果可进 Git，大型环境/数据留在 Z 盘并可清理；
- 卸载、替换和 canonical rebuild 路径明确。

停止条件：

- 候选无法在目标 profile 安装或运行：保存失败，测试 challenger，不立即自研；
- 两个成熟候选在同一 FIN-specific requirement 上都有可复现失败，配置、组合和薄 adapter 也不能解决：才允许提出有限自研；
- 资格实验还没开始却准备写第二轮治理文档：立即停止文档工作；
- 需要改 R14 truth、隐藏失败、弱化 FIN validator、生产切换、付费调用或删除数据：停止并单独处理授权；
- adapter 厚度接近重写组件，或组件明显不匹配责任层：停止该候选。

## 7. S1–S5 迁移矩阵最小字段

| 字段 | 含义 |
|---|---|
| stage/capability | 产品阶段与能力 |
| current modules | 当前代码/配置/数据消费者 |
| FIN authority | 必须保留的 FIN 裁决 |
| disposition | retain/wrap/replace/regression/retire |
| mature owner | 选定或待资格候选 |
| adapter/contract | 供应商与 FIN 的边界 |
| qualification evidence | benchmark/result/unknown |
| migration dependency | 前置与 consumer |
| rollback/exit | 可恢复路径 |
| product acceptance | 用户可感知完成标准 |

## 8. 完成标准与提交节奏

Steps 1–3 完成必须同时满足：

- 旧协议明确 superseded 且历史完整；
- 硬规则和 guideline 生效；
- Z 盘至少一条真实成熟运行底座 slice 已安装并跑通，或失败有可复现证据；
- workflow、PostgreSQL、MLflow、OTel 至少获得实测结论；
- S1–S5 Build/Adopt/Hold/Retire 完成 delta reconciliation 和模块级迁移矩阵；
- 没有继续 R14、formal、production cutover 或索引删除；
- Owner 看到的是实际候选数据，不只是新计划。

Git 使用三个普通 release slice：A=guideline/收口，B=qualification 代码与结果，C=迁移矩阵/closeout。每个切片正常 diff、test、secret scan、commit、push；没有额外的自定义生命周期。

## 9. 重新考虑有限自研的条件

只有冻结 benchmark 证明成熟候选无法满足关键 FIN 需求，且配置、组合与薄 adapter 都不能解决时，才可提出有限自研。提案必须说明：实际测试过的候选、可复现 failure、最小 FIN-specific gap、维护 owner、退出路径，以及将删除哪套重复旧实现。
