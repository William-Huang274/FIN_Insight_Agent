# 仓库命名与当前入口

2026-09-13 · FIN 0.1.3 冻结代码树。[清理说明](frozen_cleanup.zh-CN.md) · [历史恢复](../../../archive/README.md)

| 类型 | 当前规范 |
| --- | --- |
| 产品 | FinSight Agent / FinSight 金融研究工作台 |
| 产品版本 | FIN 0.1.3 已冻结；FIN 0.1.4 规划中 |
| Python 分发 | `finsight-agent`，实现包 `sec_agent` 保持兼容 |
| 前端包 | `@finsight/workbench-frontend` |
| 当前文档 | 小写语义名称，语言后缀 `.zh-CN.md` / `.en.md`；中文首页统一为根 README |
| 当前代码 | 目录表达领域，文件表达用途；避免 final/new/连续 rN 副本 |
| 实验与版本 | 产品版本、合同版本、attempt 分开；历史执行用冻结提交恢复 |

## 当前入口

- `apps/workbench/`：FastAPI/React 工作台；`deploy/`、`compose.yaml`、`langgraph.json`：部署。
- `scripts/deployment/research_workbench.py`：统一 CLI，保留现有部署身份。
- `scripts/dev/`：公开检查、合成导出和截图；数据 CLI 见[脚本目录](../../../scripts/README.md)。
- `src/sec_agent/`、`src/retrieval/`、`src/ingestion/` 等：被实际入口引用的领域模块与薄适配。
- `tests/`：现用回归；`eval_sets/`：评测合同和 fixture，隐藏评测不普通全文检索。
- `docs/product/`：版本范围；`docs/architecture/`：实现；`docs/public/`：对外事实。
- `docs/worklog/`：实际进度与失败；`docs/project_os/current_context_pack.zh-CN.md`：短接续入口。
- `archive/README.md`：只提供恢复指针，旧代码不留在当前树。

旧资格脚本及兼容跳板已退出；需要重放时使用冻结提交，不把旧模块重新放回运行路径。仍被产品使用的 Dell/S1 命名模块、SQL 迁移、图 ID、数据库和来源合同不批量改名，避免破坏已验证的身份与来源关系。忽略的本地数据、索引、输出与运行状态不因源码清理而删除。
