# FIN 0.1.3 S1-06 MCP Operational Truth 实现

日期：2026-08-07

状态：`engineering_pass_clean_operational_proof_pending`

## 1. 最早根因

- registry 登记 9 个业务工具，stdio server 只暴露 SEC Search、Exact Ledger、market、industry 和两个 run-artifact 工具，Milvus、relationship、web 未暴露。
- `sec_search_filings` 即使请求 `rerank_budget=0`，interactive context 仍固定构造 BGE reranker；Windows 主机继承 Linux `/root/.../bge-reranker-v2-m3`，本地有界请求约 56 秒后才报路径错误。
- Exact Ledger 使用 canonical DuckDB 路径可在约 1.3 秒完成，故历史 timeout 不能继续笼统归为 Ledger handler 本身不可用。
- 旧入口没有进程级 timeout/cancel/no-orphan、cold/warm 状态或 handler phase receipt。

## 2. 实现

- 新增 `McpRuntimeProfile` 和 `McpToolProcessSupervisor`：显式参数→环境→版本化 profile 的资源优先级；缺资源在 handler 前 typed fail。
- worker 进程 cold 启动后可 warm 复用；超时或取消终止完整 worker tree，下一调用重新 cold start。
- 每次返回 resource binding、worker start、handler execution、elapsed、terminal status 和 worker identity。
- `rerank_budget=0` 编译为显式 BM25-only，完整保留 `rerank_budget=0`，不再把 0 当缺省值回填为候选预算。
- stdio server 现暴露 9 个 registry 业务工具；现有 web 工具仍只是 context-only snapshot request surface，真实 fetch/parser/capture 属于 S1-07，未在此冒充完成。

## 3. 验证

- focused MCP contracts/runtime/operational tests：`23 passed`。
- stdio smoke：`10 tools = 1 discovery + 9 business`，contract call pass。
- dirty-tree diagnostic：market、Exact Ledger、NVDA SEC BM25-only 均本地成功；SEC 首次 handler 约 12.2 秒，`candidate_sent_to_bge=0`。
- timeout/no-orphan、cancel→next cold、cold→warm same worker 均 deterministic proven。

## 4. 边界与下一步

本项未调用模型、Provider 或外部网络。BM25-only operational success 不证明 Agentic Search 质量。提交推送后运行 clean-commit proof script，验证 SEC cache cold→warm、Exact Ledger、market、missing-reranker typed failure 和 worker close；通过后才关闭 S1-06 并进入 S1-07。
