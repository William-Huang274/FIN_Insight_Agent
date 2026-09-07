# 当前脚本入口
`scripts/` 只保留 FIN 0.1.3 当前基线会直接使用或维护的入口。历史实验、单次 attempt runner、旧 full-chain、旧 MCP/CLI 与发布证明脚本均已迁入 `archive/versions/`。

## 数据准备

- `data_sec/`：SEC filing 与 8-K earnings 的下载、manifest、chunk 和 source-gap 合并。
- `data_retrieval/`：Evidence Store 与 BM25 索引。
  - `build_current_compiled_object_views.py`：把当前 source-bound child 编译为去重的 claim、metric-row 与 bounded-context 候选，并显式保留 S2 数据库事实路线；输出没有 Evidence 或 NumericFact 权限。
  - `run_s1c_compiled_object_retriever_comparison.py`：在同一编译对象、硬过滤和预算上运行 BM25／BGE／Qwen shadow；模型资产不完整时必须写 typed block，不能生成伪结果。GPU／reranker 依赖仍属于未晋升的隔离 qualification 候选，不进入产品 Runtime lock。
- `market/`：离线行情快照、事件、分析和 Evidence Pack 构建。
- `industry/`：受合同约束的行业来源快照。

脚本出现在目录中只表示“受维护的数据构建入口”，不表示外部来源、私有数据或相应研究能力已自动可用。Workbench `/operations` 只暴露 `src/sec_agent/workbench/data_build.py` 明确准入的步骤。

## 产品与治理

- `dev/run_workbench_backend.py`：唯一后端启动入口。
- `engineering/verify_active_baseline.py`：从产品、数据构建和前端入口重建活动 import graph，禁止旧版本/attempt/archive 进入活动图。
- `engineering/build_archive_redirect_index.py`：对所有版本归档重建逐文件 SHA256 重定向索引；对不可移植的长路径使用可逆 path map 和短路径对象名。
- `research/run_s3_multi_agent_report_remap_live.py`：当前 S3 的通用 protected-report terminal remap CLI；它只消费不可变报告与 typed authority，不得重跑研究，并在 S3 closeout 后随对应执行证据一起归档。

本次一次性迁移程序已经完成使命，并随执行前代码一起迁入 `archive/versions/fin_0_1_3_prebaseline/`；它不再是活动入口。

## 规则

1. 新的单次实验不能直接成为 `scripts/` 中的长期入口。
2. 新入口必须进入当前代码图、测试和 Workbench/CLI 的真实消费者之一。
3. 私有数据、生成索引、模型输出和凭据不进入脚本目录或 Git。
4. 归档脚本不可被当前 Runtime import；恢复功能要先建立版本中立 successor。
