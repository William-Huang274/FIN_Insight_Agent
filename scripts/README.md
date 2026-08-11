# 当前脚本入口
`scripts/` 只保留 FIN 0.1.3 当前基线会直接使用或维护的入口。历史实验、单次 attempt runner、旧 full-chain、旧 MCP/CLI 与发布证明脚本均已迁入 `archive/versions/`。

## 数据准备

- `data_sec/`：SEC filing 与 8-K earnings 的下载、manifest、chunk 和 source-gap 合并。
- `data_retrieval/`：Evidence Store 与 BM25 索引。
- `market/`：离线行情快照、事件、分析和 Evidence Pack 构建。
- `industry/`：受合同约束的行业来源快照。

脚本出现在目录中只表示“受维护的数据构建入口”，不表示外部来源、私有数据或相应研究能力已自动可用。Workbench `/operations` 只暴露 `src/sec_agent/workbench/data_build.py` 明确准入的步骤。

## 产品与治理

- `dev/run_workbench_backend.py`：唯一后端启动入口。
- `engineering/verify_active_baseline.py`：从产品、数据构建和前端入口重建活动 import graph，禁止旧版本/attempt/archive 进入活动图。
- `engineering/build_archive_redirect_index.py`：对所有版本归档重建逐文件 SHA256 重定向索引；对不可移植的长路径使用可逆 path map 和短路径对象名。

本次一次性迁移程序已经完成使命，并随执行前代码一起迁入 `archive/versions/fin_0_1_3_prebaseline/`；它不再是活动入口。

## 规则

1. 新的单次实验不能直接成为 `scripts/` 中的长期入口。
2. 新入口必须进入当前代码图、测试和 Workbench/CLI 的真实消费者之一。
3. 私有数据、生成索引、模型输出和凭据不进入脚本目录或 Git。
4. 归档脚本不可被当前 Runtime import；恢复功能要先建立版本中立 successor。
