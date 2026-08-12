# 2026-08-13 FIN 0.1.3 S1-C Runtime Query Atom 模型 shadow

- 将 customer／supplier 经济角色从旧混合 target 语义中拆开，新增 provider-neutral query/object route successor。
- 建立 18 个 Runtime Query Atom，并保持 label 在候选生成后才 join。
- 本地完成 BGE-M3、Qwen3-Embedding-0.6B、BGE-Reranker-v2-m3、Qwen3-Reranker-0.6B 对照；0 网络、0 生成模型调用、0 训练。
- 拒绝 Qwen Reranker 的错误 sequence-classifier 适配，改用官方 yes/no CausalLM surface。
- R1 自然池没有足够 hard negative；R2 保留自然池不变，增加不可晋升的诊断对照池。
- 冻结 Qwen Embedding provisional、BM25 fallback，Qwen Reranker shadow；BGE 不晋升。
- Evidence Role F1=0.5818，不通过；数据量不足，禁止微调。
- 发现残缺 `-based manufacturing...` 正例和错误 downstream 关系绑定，转 qrel/object 复核，不以改标签追分。
- 全量测试发现当前 Workbench 检索快照仍绑定旧 plan digest；已用同一 current object store 重建快照并同步 Runtime Registry，124 项测试恢复通过。
- Query Atom materializer 与 model shadow runner 已接入 Workbench Operations 的 Retrieval Eval catalog，避免形成无消费者的 attempt 脚本。
- 下一硬门为 S2 公司财务事实 mart；旧年度 9/9 可复用，但 current-quarter 0/6 和旧期 manifest 必须修正。
