# 001 R50 Product Doc Governance And ToB / ToC Positioning

日期：2026-06-28

## Prompt

用户提出：当前已经进入 ToB / ToC 产品分岔口，B 端更重视流程规范、减少重复工作、保质提效和降低人力成本；C 端更重视获得类机构投研服务和可靠 AI 辅助判断。用户要求判断是否需要单独开产品文档主线，并更新 worklog skill，明确产品经理文档和技术部门文档的规范与区分。

## Reasoning And Decision

需要单独开产品文档主线。原因：

- 近期讨论已经不只是技术实现，而是产品定位、用户分层、商业价值和工作流边界。
- 继续把产品判断、技术实现、工作日志混在同一编号体系里，会导致后续难以追溯 source of truth。
- B 端 / C 端分岔会影响功能优先级、成本控制、权限、合规、交互和输出形态，必须用产品文档维护。
- 技术实现仍需独立拆成技术需求单、架构文档、评测文档和交付记录，不能和 PRD 混写。

新的文档治理原则：

- `docs/product/`：产品经理向文档，维护定位、用户、场景、工作流、功能范围、产品验收和商业包装。
- `docs/architecture/` / `docs/eval/` / future `docs/engineering/`：技术向文档，维护架构、数据、API、DB、runtime、agent、eval、deployment 和交付合同。
- `docs/worklog/`：事实记录，维护每轮改动、验证、缺口和后续，不作为长期 PRD 或架构 source of truth。

## Work Completed

- 更新全局 skill：
  - `Z:/CodexHome/.codex/skills/project-worklog/SKILL.md`
  - 新增产品/技术/工作日志分离规则。
  - 更新 skill description，使它在产品文档治理和产品/技术文档拆分场景也会触发。
- 新增产品文档入口：
  - `docs/product/README.md`
- 新增产品定位草案：
  - `docs/product/PRODUCT_20260628_finsight_tob_toc_positioning_and_product_line.zh-CN.md`
- 更新总文档地图：
  - `docs/README.md`

## Product Positioning Recorded

产品定位：

```text
Evidence-backed Financial Research Workbench
可审计的金融研究工作台 / AI junior analyst layer
```

短期替代的是 junior analyst / associate 的资料搜集、抽表、对数、引用、底稿、first draft 和监控工作；不直接替代 senior judgment、客户关系、签字责任、投资决策和项目负责人。

ToB 主线：

- AI Analyst Workflow Platform。
- 重点是流程规范、审计、权限、复核、降本、提效、私有知识库和团队协作。

ToC 主线：

- AI Research Companion。
- 重点是让个人投资者获得类机构研究流程的公开信息整理、证据审计、风险提示和投资逻辑拆解能力。

战略原则：

```text
B 端底座，C 端体验。
```

## Result And Evidence

本轮是 docs / skill governance 更新，没有改 runtime、agent、parser、database 或 eval 代码。

## Follow-up

后续产品经理向任务优先进入 `docs/product/`；技术实现必须从产品文档拆出技术需求单和交付文档。历史混合文档暂不迁移，避免大范围断链；新建和触碰的文档按新规范执行。

## Verification

- `project-worklog` skill validation 已通过；Windows 默认 GBK 会导致中文 skill 文件解码失败，已用 `PYTHONUTF8=1` 重跑通过。
- `git diff --check` 已通过。
