# 代码版本与历史恢复

2026-09-13 · [首页](../../../README.md) · [历史恢复](../../../archive/README.md)

本次整理保留 FIN 0.1.3 正在使用的代码，将一次性研究、已淘汰实现和旧归档从当前树移出。当前产品为 v0.1.3 本地预览版。

## 保留范围

| 目录 | 当前责任 |
| --- | --- |
| `apps/workbench/` | 工作台前后端、浏览器回归与构建配置 |
| `src/sec_agent/agent_runtime/` | 原生会话、研究、身份、审批、上下文、交付 |
| `src/sec_agent/research_foundation/`、`src/sec_agent/research/` | 当前 MCP/研究消费者实际使用的合同和领域逻辑；按模块导入 |
| `src/retrieval/`、`src/ingestion/` | 当前资料构建与查询实际需要的解析、评分、路由及证据关系 |
| `scripts/data_sec/`、`data_retrieval/`、`market/`、`industry/` | 可重复的数据构建和摄取 CLI，包括 Operations 准入入口 |
| `scripts/deployment/`、`scripts/dev/`、`scripts/engineering/` | 部署、源码与导出检查、截图、依赖边界和敏感模式检查 |
| `tests/` | 当前代码的合成/本地回归、明确 opt-in 的私有资料测试；保留受支持 Dagster 适配器测试 |
| `deploy/`、`configs/`、`eval_sets/` | 当前部署、资源合同、测试夹具及有限历史证明；历史结果文件不等于可执行入口 |

入口清单由[核验清单](frozen_cleanup_manifest.json)记录；`scripts/engineering/verify_active_baseline.py` 从现用入口检查 import、包初始化和动态调用路径。运行模块使用功能名称。已有图 ID、SQL 内容、数据库身份与来源快照保持兼容；模块目录见[命名说明](naming_and_entrypoints.zh-CN.md)。

## 解耦和退出

报告估费、候选评分与筛选、资料节点投影、部署环境读取、合成报告导出已分别落到维护模块。研究包不再通过初始化加载全部旧实验。Operations 的六个排名/qrels/shadow 资格按钮退出，正常数据构建保留。

`scripts/qualification/`、`scripts/research/` 旧入口及其独占实现/测试退出当前树。清理不保留指向旧脚本的兼容跳板，也不在仓库中再建一个放满旧代码的 archive 目录。历史重放使用冻结 Git 提交；失败、旧评测和人审修订保留原时点含义。

## 核验方式

清单基于 Git 追踪文件，结合运行入口依赖、子进程 CLI、importlib 路径和保留测试复核。先导出原 Git blob、验证 ZIP 完整性与逐文件 Git 对象摘要，再执行精确文件移除。独立迁移程序放在仓库外，不成为新的长期脚本。

静态依赖不能证明所有动态行为，因此清理后继续跑 Python 回归、当前入口检查、公开合成导出、前端构建与交互测试。实际结果、失败和修正见[工作记录 213](../../worklog/fin_0_1_3_s3/213_frozen_repository_cleanup.md)。没有借本次整理新增付费研究或声称金融能力提升。

已有本地工作台升级请先读[提交凭证与缓存兼容性说明](local_record_upgrade.zh-CN.md)，保留未知请求状态并停止旧进程后再切换。

## 后续代码准入

可重复使用且有产品/运维消费者的 CLI 才进入 `scripts/`。单次实验和迁移在隔离工作区执行，完成后保留证据及冻结提交。运行所需通用部分先抽取为有测试的维护模块，不能从一次性实验反向导入。文档和台账承担人类记忆，不承担第二套运行控制面。
