# R53-R60 Program Execution And Git Hygiene

日期：2026-06-28

## 问题

用户希望在继续拆 R53-R60 前，先明确成熟产品研发中 PRD、技术方案、需求单、测试、反馈之间如何衔接，并把该标准固化到项目文档治理规则中。同时用户指出当前仓库长期处于脏工作树，担心后续版本管理混乱。

## 决策

1. R53-R60 不应作为彼此孤立的技术文档并行推进，而应作为一个 program 管理。
2. 高层 R 文档视为 epic；需求单按能力域和依赖关系拆分，不按 R 文档编号机械串行。
3. 产品验收和工程验收分离但必须链接：产品验收看用户工作流是否成立，工程验收看 schema、API、数据、权限、eval、性能和运维门控是否通过。
4. Git 管理应进入 release slice 的完成门槛：每轮开始和结束都要记录 branch / dirty status / candidate files，不使用 `git add .`，代码、文档、eval fixtures、generated artifacts 分开 stage。

## 完成内容

- 更新 `Z:/CodexHome/.codex/skills/project-worklog/SKILL.md`：
  - 新增 “Convert product and technical plans into execution programs before implementation” 规则；
  - 固化 `PRD -> technical plan/RFC -> program roadmap -> epic/feature/story/task -> test/eval -> integration -> release -> feedback` 流程；
  - 明确需求单字段、门控和反馈记录要求。
- 新增 `docs/architecture/agent_graph_vnext/27_r53_r60_engineering_execution_program.zh-CN.md`：
  - 定义 R53-R60 epic 边界；
  - 明确依赖图、可并行工作、需求单模板；
  - 定义 Design / Data Contract / Implementation / Integration / Eval / Release gates；
  - 拆 P0-P5 program 排期；
  - 补入 Git 和 artifact 管理要求。
- 更新 `docs/architecture/agent_graph_vnext/README.zh-CN.md`，加入 27 文档索引。
- 更新 `docs/worklog/00_internal_master_checklist.md`：
  - 标记 R53-R60 program 总控计划完成；
  - 增补 R55-R60 技术计划占位。

## Git 状态

本轮开始前仓库已存在大量既有 modified / untracked 文件，主要集中在 `docs/`、`scripts/`、`src/`、`tests/` 和 `data/manifests/`。本轮只新增/修改文档和本地 skill，不做 stage、commit 或 push。

当前建议后续单独做一次 Git hygiene closeout：

1. 把可提交的代码、脚本、测试和文档分组；
2. 把大规模 runtime output、临时 retry 文件和 raw/generated artifacts 分类为 ignore / external storage / tracked contract；
3. 对候选提交文件做 secret scan；
4. 分 commit 提交，而不是一次性 `git add .`。

## 验证

- 未运行代码测试；本轮是 docs-only / skill-only。
- 待后续运行 `git diff --check` 覆盖本轮 markdown 改动。

## 后续

1. 从 `28_r53_research_to_quant_lab_technical_plan.zh-CN.md` 开始拆 R53 技术方案。
2. 在 R53-R60 每份技术文档中先落 demand list 和 gates，再落 implementation details。
3. 在进入实现前先做 Git hygiene closeout，避免继续扩大脏工作树。
