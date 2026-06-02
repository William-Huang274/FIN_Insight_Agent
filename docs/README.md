# 文档地图

这里是 FinSight-Agent 的公开文档入口。新用户不应该先去翻工作日志，也不应该从历史基准评测文档里猜当前系统长什么样；应该先从这里找到适合自己的阅读路径。

## 项目叙事

FinSight-Agent 是一个面向公开公司研究的可审计金融研究系统。它把用户的金融问题拆成可检查的研究步骤：判断问题类型、确定研究范围、检索证据、整理数值台账和关系/行业上下文、形成专家结论卡、汇总论证提纲、写投研备忘录，并检查来源边界和缺证结论。

公开文档里统一使用 `FinSight-Agent` 作为项目名。`SEC Agent` 只在说明早期 SEC 数据链路或历史文档时使用。

## 读者路径

| 你想做什么 | 先看 | 再看 |
| --- | --- | --- |
| 快速理解项目 | 根目录 `README.md` | 架构文档入口、质量评价体系 |
| 克隆后跑本地检查 | 根目录快速开始 | 演示入口、脚本发布面 |
| 接入自己的数据 | 自有数据快速接入 | 演示入口、数据来源边界 |
| 体验产品化界面 | Workbench 快速开始 | 数据包、数据构建、演示入口、运行产物说明 |
| 看质量标准和评测 | 投研质量评价体系 | 分层质量门控执行文档 |
| 查实现历史 | 工作日志索引 | 对应编号的工作日志 |

## 主要入口

- 根目录 `README.md`：项目定位、核心链路、快速开始、公开边界和文档地图。
- [CLI 演示入口](demo/sec_agent_demo_entrypoints_v1.zh-CN.md)：单轮演示、多轮会话、已保存运行检查。
- [自有数据快速接入](deployment/local_custom_data_quickstart.zh-CN.md)：用自己的 SEC、8-K、市场快照和索引跑完整链路。
- [Workbench 快速开始](workbench/workbench_quickstart.zh-CN.md)：本地界面入口、配置导入、数据包管理、数据构建、产物回填、运行和产物查看。
- [脚本发布面](../scripts/README.md)：当前主线保留的脚本入口和用途。

后续文档整理时，演示入口会从 `sec_agent_demo_entrypoints_v1` 改成更统一的 FinSight 命名；当前链接先保持不动，避免一次性移动文件造成断链。

## 架构文档

架构文档应该讲当前系统怎么工作，而不是复述每轮实验历史。

计划公开三篇：

- `architecture/fin_sight_agent_architecture.zh-CN.md`：整体架构，说明图运行、工具执行层、检索、数值台账、覆盖检查、备忘录写作和校验。
- `architecture/multi_agent_orchestration.zh-CN.md`：多智能体调度，说明研究负责人、智能体激活策略、主力/辅助/条件启动、上下文交接和修复循环。
- `architecture/data_and_tool_access_model.zh-CN.md`：工具和数据权限，说明每类智能体能看什么、能调用什么、不能越过什么边界。

在这些文档写完之前，[分层质量门控执行文档](eval/fin_agent_layered_quality_execution_plan_v0_1.md) 和最近的工作日志保留了更细的实现记录。

## 评测文档

评测文档要分清两件事：一类讲“什么叫好”，一类讲“怎么测”。具体运行编号、调用成本和失败排查不要放在公开入口里，应该放进工作日志或模型运行记录。

- [投研质量评价体系](eval/fin_agent_investment_research_quality_framework_v0_1.md)：定义好的金融研究回答应该满足什么标准。
- [分层质量门控执行文档](eval/fin_agent_layered_quality_execution_plan_v0_1.md)：说明每一层智能体怎么过门控，什么时候才能跑全链路。
- [全链路 / 多轮评测计划](eval/fin_agent_full_chain_multiturn_eval_plan_v0_1.md)：说明单轮、多轮和不同问题难度的测试思路。
- [S1-S8 用例矩阵](eval/fin_agent_s1_s8_agent_quality_case_matrix_v0_2.md)：当前分层用例覆盖情况。后续应把过细的运行编号和成本诊断移到工作日志。

早期 SEC 基准评测 v1/v2 文档属于历史资料，不再作为当前项目入口。

## 发布和历史资料

- `release/`：当前发布状态和公开就绪检查。
- `worklog/`：按时间记录的实现过程、排查记录和交接文档。
- 早期 `sec_agent_v0_1` 和 `sec_benchmark_v1/v2` 文档应保留，但后续会标注为历史资料或移动到归档目录。

## 写作规则

- 不在公开文档里写 API key、私有数据、云端临时路径、原始运行输出或私有供应商产物。
- 用户真正会复制的命令放在 README、演示、部署、Workbench 或脚本索引里。
- 实验失败、成本诊断、具体运行编号和调试细节放在工作日志或模型运行记录里。
- 多智能体调度、上下文交接、工具权限和数据边界是项目主线，不是内部细节，必须在架构文档里讲清楚。
