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

## 最终本地验收

实现提交：`f34a04f4`，分支 `codex/fin-013-repository-cleanup`。发布使用该分支和 `archive/fin-0.1.3-before-cleanup-20260913` 标签；远端状态以 GitHub PR 和对应提交为准，不将文档提交当作产品发布。

| 检查 | 结果 |
| --- | --- |
| 完整 pytest A5 | **1448 passed / 134 skipped**，414.70 秒；跳过私有资料及可选环境，不计成功 |
| 默认浏览器 A2 / 真实 source-only BFF | **39 passed**，3.4 分钟；修复 `/auth` 开发代理后通过；研究界面的合成 API 场景仍按其原范围记录 |
| 独立公开浏览器 A1 | **36 passed**，7.0 分钟；合成 API，非金融效果验证 |
| 公开 Python 与交付 | **46 passed**；MD/PDF/DOCX/PPTX、图表和合成 JSON 成功生成，0 模型调用 |
| 抽离与边界 | 32 组估费精确对照；66 项初步回归、10 项节点/费率/目录回归、5 项依赖/环境回归通过；已包含相关完整套件覆盖，不累加为独立样本 |
| 代码与文档 | compileall、TypeScript/Vite build、活动依赖检查、中英主要入口链接、暂存 diff 格式检查通过 |
| 敏感模式 | 2331 文本文件无命中；二进制图片另作视觉检查，不声称历史/二进制全面安全审计 |

原始检查输出按 attempt 分开保留于 `D:/temp/fin213/`，合成交付在忽略的 `.local/fin213/public-check-a1/`。原始 private 数据、运行中数据库/卷、模型响应均未删除或上传。完整历史由冻结提交及外部 ZIP 保留，ZIP SHA256 为 `3b0fe3e59ec847f7090b4018532e83df5e426ce4a461e4152bc725250e6f0967`。

收口区分：**产品增量**无新增金融能力；**工程增量**为依赖解耦、淘汰代码退出、开发身份代理与回归同步；**研究证据**沿用 0.1.3 冻结结果；**文档**完成双语状态和实际功能图文；**剩余限制**为五个误触发历史私有重放的旧预期不兼容、生产安全/安装/恢复验收及 0.1.4 金融语义研究工作，均未改写为通过。GitHub CI 是另一个执行环境，须单独记录结果。

## PR #8 安全与兼容性修复

初次推送 `0b249dea` 后，GitHub run `34743254004` 的 engineering-and-product 成功，但 locked-supply-chain 失败：research profile 的 diskcache 5.6.3 命中 PYSEC-2026-2447 / CVE-2025-69872，无修复版本。run `34743253999` 的主工作台镜像构建成功，可选 control-plane 在获取冻结 libc6-dev 时失败。原始日志/审计存于 `D:/temp/fin213/github-*-a1*`，不覆盖失败证据。

Owner 明确回复“纳入本轮，修复兼容性后再合并（建议）”。这授权修复依赖及其兼容路径，不增加产品版本、不重跑付费研究、不部署生产。

- 存储采用已有 SQLite 成熟引擎，新增固定 JSON/旧基础类型映射适配器；移除 diskcache 依赖且 `uv lock --offline` 只移除该包，其他版本不变。保留提交原子去重、响应字节、未知调用阻断、向量复用和来源 TTL。迁移事务失败时不放行业务操作，保留全部原件。
- 已检查无修复 DiskCache、进程内缓存和外部缓存服务的适配差异，选择理由及停旧进程、备份和不能盲目降级的说明见[升级文档](../../architecture/repository/local_record_upgrade.zh-CN.md)。没有自造通用缓存/调度平台。
- Docker OCI 原始层清单验证 glibc 为 `2.41-12+deb13u3`；Debian 签名历史源 20260701T000000Z 有精确匹配的 libc6-dev 和 libc-dev-bin。保留现有 pin，补充历史来源及构建前后版本断言。
- 本地 cache-compat A1：21 passed，包含跨进程唯一 claim、恶意旧载荷拒绝及整体回滚、目录越界拒绝、旧完成/未知 provider 不重发。另用真实 DiskCache 5.6.3 生成四类临时记录（包含外部大值）对照新读取，全部相等，原文件 SHA256 不变，0 provider 调用；完成后从本地虚拟环境卸载旧包。测试没有迁移真实运行缓存。
- HTTP 旧提交重放测试已补充；完整回归与修复后的 GitHub CI 使用新 attempt，下文追加最终结果。

本地修复后验收：完整 pytest cache A2 **1457 passed / 134 skipped**（239.40 秒）；卸载 diskcache 后定向兼容性 A2 **22 passed**；活动依赖与锁一致性、编译、暂存格式检查通过；敏感模式扫描 2334 文本文件无命中。前端无新增行为改动，远端 CI 继续执行原完整浏览器套件。唯一 warning 为第三方 LangSmith import 弃用提示。
