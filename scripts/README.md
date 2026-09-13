# 当前脚本入口

FIN 0.1.3 冻结代码树，2026-09-13。这里只保留当前产品、部署、数据构建和工程检查实际使用的入口。一次性资格、单次 attempt 和旧研究 runner 已清出，使用[冻结提交恢复](../archive/README.md)。

| 目录 | 用途 |
| --- | --- |
| `data_sec/` | SEC filing、20-F/40-F、8-K earnings 的下载、manifest、chunk 与来源记录 |
| `data_retrieval/` | 原始来源捕获、资料库扩充、检索节点/对象/索引、财务事实表与公开向量准备 |
| `market/` | 行情快照、事件、分析和市场证据构建 |
| `industry/` | 受合同约束的行业来源快照 |
| `deployment/` | 本地工作台部署、数据发布与环境读取 |
| `dev/` | 无模型源码检查、合成四格式导出、实际界面截图、source-only BFF |
| `engineering/` | 当前依赖边界和敏感模式检查 |

## 常用命令

```bash
python -m scripts.dev.verify_public_checkout --output-directory .local/public-check-01
python scripts/engineering/verify_active_baseline.py --pretty
python scripts/engineering/check_repository_secrets.py
python -m scripts.deployment.research_workbench --help
```

依赖和部署参数见[快速开始](../docs/public/quickstart.zh-CN.md)。部署入口沿用现有图 ID、数据库和卷身份；`dell_report_workbench` 仍是当前实现，不因命名删除。

Workbench `/operations` 只暴露 `src/sec_agent/workbench/data_build.py` 准入的构建步骤。资料库扩充使用 `data_retrieval/expand_case_source_library.py`，节点投影由 `src/ingestion/retrieval_nodes.py` 提供；运行时不再 import 资格脚本。

新单次实验不直接成为长期入口。可复用能力须有真实消费者和适当回归；私有数据、索引、模型输出和凭据不进入 Git。保留根和退出清单见[清理说明](../docs/architecture/repository/frozen_cleanup.zh-CN.md)。
