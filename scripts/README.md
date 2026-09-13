# 当前脚本入口

这些命令用于数据准备、本地部署、开发与测试。运行条件见[快速开始](../docs/public/quickstart.zh-CN.md)。

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

依赖和部署参数见[快速开始](../docs/public/quickstart.zh-CN.md)。`research_workbench` 提供完整部署实现，复用已有图 ID、数据库及数据卷。

Workbench `/operations` 只暴露 `src/sec_agent/workbench/data_build.py` 提供的构建步骤。资料库扩充使用 `data_retrieval/expand_case_source_library.py`，节点投影由 `src/ingestion/retrieval_nodes.py` 提供。

数据、索引、模型输出与凭据写入独立的本地目录。开发模块与入口说明见[代码目录](../docs/architecture/repository/naming_and_entrypoints.zh-CN.md)。
