# 876 — FIN 0.1.3 全仓基线盘点与“反复修”复盘

日期：2026-08-11

## 用户目标

暂停 S3 局部修复，盘点仓库建立以来所有未明确 archive/丢弃的代码、文档和数据；整理代码树与真实依赖图，以最新 FIN 0.1.3 进度建立新基线，再解释长期反复修复的根因。Owner 审阅前不制定或执行新的清理、重构与产品路线。

## 本轮执行

- 读取 Project OS、协作规范、PRD/TECH、当前 FIN 0.1.3 plan、历史主干审计与 repository inventory。
- 核对 Git 分支、commit、worktree、tag、历史增长和 clean/synced 状态。
- 覆盖 6,112 个 tracked 文件的顶层与关键子树盘点。
- 对本机 ignored/private/generated 数据只做路径、数量和大小盘点，不读取凭据或业务私有内容。
- 对 src/apps/scripts 下 1,229 个 tracked Python 文件建立 AST import 图；无解析错误。
- 区分当前 Workbench 主链、FIN 0.1.3 candidate、评测/证明面、历史/兼容面与显式 archive。
- 生成可读审计和紧凑机器基线；不删除、不移动、不归档、不执行模型/Provider/网络。

## 关键结果

1. 当前 Workbench 后端入口静态可达 150 个 Python 文件，稳定入口并集约 161 个；约 1,068 个 Python 文件不在稳定入口图中，但需按离线工具、candidate、历史兼容、一次性 runner 和 orphan 分别审查，不能批量删除。
2. Workbench 仍主要连接 FIN 0.1.2 S2/S3 binding、S4-T06/T07 projection/review 和历史 runtime；FIN 0.1.3 S1–S3 当前主要是候选/评测链，尚未产品 cutover。
3. configs/releases 955 个 JSON 中大量是 authority、admission、proof、result 和 disposition 证据，不应继续与真正 runtime config 混称。
4. 2026-07-19 之后约 12 天新增 3,006 个文件，增长主要来自 release config、runner、contract test 和 worklog，而非同等比例的产品功能。
5. 当前 FIN 0.1.3 的诚实状态为 engineering candidate at S3：S1/S2 有实质成果，最新 S3 natural canary mixed-root-cause failed，S4 cutover/dogfood 和 S5 release 未完成。
6. “反复修”主要由产品主线与 proof 主线分离、per-attempt 文件复制、合同缺少统一编译源、金融语义验收过晚、项目缺陷与 DeepSeek 缺陷混合、历史/current/candidate 生命周期未分层共同造成。

## 产物

- docs/architecture/repository/FIN_0_1_3_REPOSITORY_BASELINE_AUDIT_20260811.zh-CN.md
- configs/repository/fin_0_1_3_repository_baseline_v1_0.json

## 边界

本轮不恢复此前暂停的 S3 修复。下一项严格为 Owner 审阅基线；接受后再共同制定仓库规范、迁移/归档策略、产品 cutover 和 FIN 0.1.3 收口顺序。
