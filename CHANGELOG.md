# 更新记录 / Changelog

## FIN 0.1.4 — Planned / 规划中

2026-09-12：专业方法适用、假设驱动研究、信息/规则更新、专家有限委派与按期收敛，见[规划](docs/product/fin_0_1_4_research_plan.zh-CN.md)。No runtime implementation or release.

## FIN 0.1.3 — Iteration closed / 本地Internal Alpha收口

2026-09-13：冻结后代码树清理，解耦运行时与一次性资格脚本，移除旧实验和树内历史源码，保留不可变 Git 标签及校验清单。双语首页补充公司资料库、财务数据、人工报告交付的真实截图，同步 0.1.3 已验证范围；0.1.4 未实施。Frozen source-tree cleanup and bilingual product documentation; no new research capability or production deployment. [Details / 说明](docs/architecture/repository/frozen_cleanup.zh-CN.md).

2026-09-12：Owner正式结束本版，保留未通过的全自动金融质量及发布条件。补齐资料库与AI内存案例事实，整理资格代码/当前文档，旧脚本兼容；见[收口](docs/product/fin_0_1_3_closeout.zh-CN.md)。The following entries are historical milestones, not current service-status declarations.

FIN 产品版本、报告版本和执行 attempt 分开记录。产品代码的主线更新不自动表示正式 release 或报告已通过人审。
Product versions, report revisions and execution attempts are separate. Mainline publication does not imply a formal release or human acceptance of a report.

## FIN 0.1.3 — Historical development milestones / 历史开发记录

### 2026-09-08 · Agent activity and execution choices / 活动流与运行选择

- 资料按专题→判断→来源与地图共用真实绑定，自然语言名称保留底层引用身份。Evidence navigation shares the report map's topic/claim/source bindings and readable labels.
- 主栏公开 Agent 进展、可展开工具记录、历史切换、节点过滤与实时补充意见。Main-column public activity, expandable calls, saved-run selection, node filtering and live guidance.
- 新建、追问、修订可选完整/自由/指定/单 Agent 和已配置 Flash/Pro 模型；原生运行消费这些选择。单 Agent 产物明确未独立复核。Execution/model choices reach native runs; single-agent output remains explicitly unreviewed.
- 跨公司小题实测与财年文字微修订完成；含失败共九次尝试、93调用、1,856,553 tokens、估算1.457538元。Nine attempts including failures; no unknown/pending usage. One same-question history-on-demand comparison reduced tokens by42.1%; free-mode small research still required41calls, so this is not a general savings claim.
- Hermes 上下文接口已评估，尚未接入或替换运行时；先保留测量依据和独立复核边界。Hermes context interfaces reviewed; integration remains deferred. [Evidence / 实测记录](docs/worklog/fin_0_1_3_s3/203_research_activity_and_execution_modes.md).

### 2026-09-08 · Research workspace and public walkthrough / 研究工作台与公开展示

- **工作台 / Workspace:** 问题起始页、项目侧栏、报告总览→专题→判断与依据、完整来源阅读、可渲染且可收起的修订对比。Question-first entry, project sidebar, hierarchical report navigation, expanded sources and rendered/collapsible diffs.
- **运行界面 / Runtime:** 实际阶段与公开事件、用量和未知费用、运行中意见及停止、历史事件播放/暂停/定位。Actual stages/public events, usage/unknown costs, live guidance/cancellation and saved-event replay.
- **研究配置 / Research Studio:** 角色 Skill 正文与绑定、专家并行1–2、双审查顺序；原生 Assistants 配置快照，按任务应用、按运行固定。Editable methods/bindings, concurrency and review order, persisted native snapshots consumed per run.
- **实际接线 / Live evidence:** 前端定向修改 v4→v5；另一次已编辑 Skill 的短问进入真实模型请求，报告未改。A frontend-targeted revision produced v5; a separate edited-method short question consumed the configuration without changing the report.
- **公开试用 / Public verification:** 统一 research_workbench 启动名、零模型源码检查、独立 Playwright 公开交互配置、真实界面截图、中英文首页及走查说明。Neutral CLI, zero-model checkout checks, isolated browser tests, actual screenshots and bilingual onboarding.

报告状态 / Report state: Dell **v5** 待人工审阅，保留旧引用措辞意见。v4→v5修改当前目标段落，引用和图表未变。此前v4的54处引用、3张图、PDF15页/Word20页/PPT44页为历史渲染证据，不改称v5的新验收。Dell v5 awaits human review with a known citation-wording finding; prior v4 rendering counts remain historical evidence.

### Earlier in the same iteration / 同轮早期交付

- Dynamic Lead task DAG, independent experts, Counter/Verifier, accountable revision, synthesis, report writing and human review. 动态研究与多角色审查闭环。
- Native LangGraph/Agent Server, PostgreSQL, Redis, MCP and LangSmith; FIN research contracts and thin adapters. 复用成熟运行基础设施。
- Short/deep follow-up, task-scoped document/image uploads, cached vision and source-bound calculations. 短/深追问、资料上传、视觉与计算回读。
- Tool-output cleanup and checkpoint/artifact retrieval; automatic summarization remains HOLD and disabled. 上下文清理已验证，不承诺普遍等质量节费率。
- MD/PDF/Word/PPT from the same report, without export-time model calls. 同源四格式交付。
- Fresh-only startup without archived answers, while retaining required source data. 新研究不依赖旧答案，但仍需原始数据。

Earlier FIN 0.1.3 mainline exposed fixed Evidence Packs; later work added dynamic research. The old baseline is retained in Git and archive/versions. 旧固定证据工作台仍作兼容，不代表当前产品只能只读。

[Current capabilities / 当前能力](README.md) · [Verification / 验证](docs/public/quickstart.en.md) · [Evidence / 证据](docs/public/sharing-scope.md)

## FIN 0.1.1 — internal honest-block · 2026-07-31

Existing tag: `fin-0.1.1-internal-honest-block`, commit `b1f216d0`. Preserves an internal baseline and its failure boundaries; not retroactively described as a completed product release.
既有内部基线与失败边界保留，不追认为完整产品成功发布。

## v0.1.0 — resume demo · 2026-05-26

Existing tag: `v0.1.0-resume-demo`, commit `ac692bcc`. Historical SEC research demonstration; not the current architecture.
历史简历演示基线，不代表当前架构与能力。

No new version or release tag is created merely for UI cleanup, a report revision or a failed test. 界面整理不额外编造产品版本，失败历史不重写。上述Hermes后置为当时状态；其后已有局部普通对话/工作记忆资格，完整研究接入仍未通过，见0.1.3收口。
