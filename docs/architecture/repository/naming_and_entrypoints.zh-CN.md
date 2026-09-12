# 仓库命名与当前入口

2026-09-12 · 0.1.3收口整理。

## 名称

| 类型 | 规范 |
| --- | --- |
| 产品 | FinSight Agent，中文可用“FinSight 金融研究工作台” |
| 产品版本 | FIN 0.1.3已收口；FIN 0.1.4规划中 |
| Python分发 | `finsight-agent`，实现包`sec_agent`保留兼容 |
| 前端包 | `@finsight/workbench-frontend` |
| 文档 | 新当前入口用`fin_0_1_4_research_plan.zh-CN.md`等小写语义名称；历史日期/大写文件保留 |
| 代码 | 目录表达领域/阶段，文件表达动作；版本优先由Git/合同表达，避免文件名堆叠final/new/v2 |
| 实验 | 产品版本、协议版本、attempt分离；已执行目录和冻结代码不改名、不复用 |

## 当前目录

- `src/sec_agent/`：领域合同、Agent适配与研究逻辑；稳定导入名不随品牌改变。
- `apps/workbench/`：FastAPI/React工作台；`deploy/`、`compose.yaml`、`langgraph.json`为部署入口。
- `scripts/dev/`：零模型公开检查；`scripts/deployment/`：本地部署与检查。
- `scripts/qualification/`：隔离资格脚本；AI内存研究统一在`ai_memory/`，旧文件仅兼容。
- `tests/`：本地回归；`eval_sets/`：公开评测合同与fixture，隐藏评测不得普通全文检索。
- `docs/product/`：版本范围和规划；`docs/architecture/`：实现；`docs/public/`：对外事实和指标。
- `docs/worklog/`：实际进度及失败；`docs/project_os/current_context_pack.zh-CN.md`：短接续入口。
- `archive/versions/`：历史内容，不能用旧“当前”状态覆盖新版本决定。
- `output/`、`artifacts/runtime/`、本地数据/索引/cache/临时目录：忽略的运行产物，不因Git清理而删除。

旧AI内存模块导入与`python -m`命令保留；新代码使用`scripts.qualification.ai_memory.*`。历史脚本的精确重放使用原attempt冻结副本，当前兼容入口仅保持调用方式，不冒充旧代码摘要。

本次未批量改名数千份历史合同、图ID、数据路径和配置，以免破坏来源绑定及恢复。当前入口的规范化与历史兼容分别处理。
