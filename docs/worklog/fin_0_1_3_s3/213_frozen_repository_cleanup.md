# 213 · FIN 0.1.3 冻结代码树清理

日期：2026-09-13。Owner 要求清理 GitHub 全仓代码，一次性/淘汰实现退出当前代码树；仍被 runtime 使用的部分先解耦，再归档。中英文入口按 0.1.3 冻结范围同步，并补充实际功能截图。

## 范围与恢复依据

- 基线 `7b8287ab`；工作分支 `codex/fin-013-repository-cleanup`。这是 0.1.3 工程整理，不启动 0.1.4，不部署或新增付费调用。
- 历史保留在不可变提交与标签 `archive/fin-0.1.3-before-cleanup-20260913`；外部副本 `D:/FIN_Insight_Archive/fin_0_1_3_frozen_20260913/source-before-cleanup.zip`。删除前逐文件对照原 Git blob，ZIP 校验通过后才清出。
- 原 `archive/` 的历史源码也退出当前树；旧实验按原提交重放，当前 CI 不再承诺旧实验命令兼容。私有数据库、原始资料、运行中的数据卷不属于删除目标。
- 通过现用 API、Agent Server、MCP、部署、资料构建、开发检查入口计算依赖；补查 package 初始化、动态 import、subprocess 和 importlib 路径。保留仍服务当前产品的模块及回归测试，不按文件名里的 Dell/S1/旧版本号直接删除。

## 实际工程变化

1. 报告估费从一次性 token 审计脚本抽到 `sec_agent.agent_runtime.usage_pricing`，保持历史费率和日期切换逻辑。
2. 当前检索使用的候选评分与排除规则抽到 `retrieval.candidate_scoring`，解除与旧排名/qrels/shadow 实验的依赖。
3. 资料库节点投影抽到 `ingestion.retrieval_nodes`；部署环境读取抽到 `scripts.deployment.environment`。
4. 合成导出验证改用 `scripts.dev.export_synthetic_report`；研究包取消自动导入全部历史实验的初始化行为。
5. Operations 移除六个历史资格实验按钮，保留现用 SEC、市场、行业与财务表构建入口。原程序、失败记录和旧测试一起归档。

## 验证与局限

初步验证：历史估费 32 组新旧实现精确一致；检索/报告会话/资料库/部署回归 66 项通过；抽离后的原文节点、日期费率与构建目录回归 10 项通过。完整清理后的检查结果在本记录收口时追加。

归档核验发现 Windows 的 `git archive` 会应用换行属性，不能直接用该 ZIP 证明原始 blob 一致；已改为按 Git blob 原始字节导出，再逐项校验。没有以归一化后相等代替原件一致。

产品增量：本轮不新增金融研究能力。工程增量：解耦和淘汰代码退出。研究证据：沿用冻结结果，不重跑付费研究。文档：双语功能导览和归档恢复入口。剩余工作：完整回归、文档链接与 GitHub 发布核验。

## 清单复核与真实失败

- 最终清出 6,594 个文件：原 archive 6,075 个，当前目录 519 个。其中 Python 脚本 223、源实现 115、测试文件 159；另有旧浏览器/PowerShell 探针及原型 DDL。`scripts/data_retrieval/` 保留 14 个现用入口。原 archive README 改为恢复指针。
- 当前依赖检查通过：249 个 Python 文件、45 个前端产品文件、5 个资源检测器、28 个注册资源。另审阅前端测试/构建配置、部署 shell/PowerShell 和现用 SQL 迁移。移除路径逐一匹配原 Git blob；[最终清单](../../architecture/repository/frozen_cleanup_manifest.json)保留精确恢复依据。
- A1 完整 pytest 在收集阶段出现 9 个导入错误：旧测试中承载了现用合成模型/夹具。将 11 个混合测试文件中的产品回归保留，仅移除已退休 runner 对应测试；原始文件仍在冻结提交。原文节点、历史费率另保留独立回归。
- A2 结果为 7 failed / 1501 passed / 69 skipped。发现 `conftest.py` 被候选清单误包含，私有资料 opt-in 未生效；恢复原规则，仅去掉旧治理台账替换 fixture。5 个原本 opt-in 的历史重放发现旧引用/工具/指标预期与当前数据不一致，其失败保留，不宣称已修复私有历史金融案例。
- A3 恢复 opt-in 后，失败组为 2 failed / 65 passed / 19 skipped。剩余两项 SDK 工具清单预期过时：测试只绑定 evidence/finance 端口，冻结实现正确只暴露四个允许动作。A4 确认实际工具清单；更新精确断言，继续保留 actor 历史隔离和非法 JSON 反馈检查。相关 runtime 与原冻结提交一致，没有为通过测试扩大权限。
- 默认浏览器 A1 使用 11 workers，出现资源争用超时；三个真实后端入口还暴露 Vite 缺少 `/auth` 代理，身份 JSON 请求被 HTML fallback 接走。补齐同后端身份代理，保留原权限判定；限制默认浏览器 workers=2。A1 的失败 trace 保留于仓库外，A2 使用新输出目录。

已通过：公开 Python 检查 46 项及四格式合成导出；公开浏览器 36 场景；新增依赖边界/环境读取 5 项；类型检查与 Vite build；主要中英文入口链接检查；敏感模式扫描 2,331 文本文件无命中。完整 pytest A5 和真实后端浏览器 A2 在最终收口记录结果。全部是零模型工程验证，没有重新运行金融研究。

基线分支比 `origin/main` 领先 96 提交、无落后。Owner 本次要求 GitHub 代码树按冻结版本整理，因此通过 PR 一并同步已有冻结进度和清理；不直接提交 main、不强推、不改写历史。
