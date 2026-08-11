# 316 P0-P10 Execution Policy Hardening

日期：2026-06-14

## Prompt

用户要求补充 `12_integrated_execution_plan.zh-CN.md`：

- 除非经过资源调度、内存/CPU/GPU、脚本、数据写入等优化后仍无法在本机运行，否则不要把数据库 / SQL / Milvus 做成折中或 toy 级最小方案。
- 遇到慢任务时不要被动等待，先主动优化算法、批处理、并发、索引、模型加载、写入方式和资源利用。
- 各 P 系列任务遇到问题时不能优先降级或 fallback；先定位并修复真实问题，解决不了再记录本机资源限制或公开数据缺口。
- Eval 体系要下探到数据处理和清洗层：chunk 切分、截断、表格抽取、结构化抽取、正确率、provenance 和下游检索影响。
- 以上要求要固化到 12 文档并融入 P 系列计划。
- 更新 `project-worklog` skill：从当前阶段开始，技术文档和工作日志按工作树 / 工作阶段建立子目录；工作日志命名包含编号、内部阶段号和主题。

## Decision

本轮只做治理和规划文档修订，不改 runtime。

核心决策：

- “最小”只表示首批字段 / 接口 / runner，不表示最小化存储能力或长期 SQLite-only / JSONL-only 路线。
- SQL / ObjectStore / Redis / Milvus 按企业级 Agent Runtime 分工设计：SQL 是审计源，ObjectStore 保存原始和大型 artifact，Redis 做协作状态，Milvus 是 passage-level semantic recall supplement。
- Fallback 不是默认方案。只有产品定义的有界行为、诊断保护，或带 removal condition 的临时 workaround 可以存在；其产出不能提升为 mainline metric。
- P4/P6/P10 eval 要覆盖 parser/chunker/table/structured-extraction 的数据质量，不能只看最终 memo。

## Work Completed

- 更新 `docs/architecture/agent_graph_vnext/12_integrated_execution_plan.zh-CN.md`：
  - 新增“执行纪律：资源、存储、根因和数据质量”。
  - 在 P0/P1/P2/P4/P6/P9/P10 的任务和门控里补充企业级存储、resource-blocked 例外、慢任务 profile、data-quality eval 和 parser/chunker/table 归因。
  - 调整首轮实施顺序，把 P2 改为 SQL-backed eval store，把 P4 扩展为 retrieval + role-visible + 数据处理质量 eval。
  - 扩展最终闭环定义，要求 SQL/ObjectStore/Redis/Milvus 边界清楚，并能记录数据处理 failure。
- 更新 `Z:/CodexHome/.codex/skills/project-worklog/SKILL.md`：
  - 新增阶段子目录规则。
  - 新增 `编号 + 阶段号 + 主题` 文件命名规则。
  - 要求父 README 建索引，不为风格批量迁移旧文件。
- 新建本阶段工作日志目录：
  - `docs/worklog/integrated_execution_p_series/`
- 更新 worklog README 和 master checklist。

## Result And Evidence

- 本轮是 docs-only / skill-only 更新。
- 未运行 runtime tests。
- 后续实施 P0/P1/P2/P4/P6/P9/P10 时，应以 12 文档新增执行纪律作为共同门控。

## Follow-up

- 下一步进入 P0：Eval Registry + B0 技术路线冻结。
- P0 必须先明确 SQL/ObjectStore/Redis/Milvus 职责边界、local adapter 边界和 `resource_blocked_scale_up` 记录格式。
- P2/P4 需要把 parser/chunker/table/structured-extraction eval 接入 eval store，而不是等 full-chain 输出浅后再回头追查。
