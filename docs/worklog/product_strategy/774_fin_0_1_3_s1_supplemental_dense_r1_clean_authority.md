# 774 — FIN 0.1.3 S1 supplemental dense R1 clean authority

## 结果

真实 runner/full-fake 已以 commit `6f2e11adc884b4f15c98f292970c3fd51b170b03` 推送到 `origin/codex/layered-data-source-expansion`。签发器随后在 clean/synced 状态生成唯一 R1 authority，digest=`fc8e7c44c5769d903d34235586f8240999ae54b0ac4e6223cf077ec04d665109`；authority 当前 issued/unconsumed。

## 精确边界

authority 绑定 implementation commit、7 个 execution 文件、execution policy、full-fake proof、410-row zero-call proof，以及本机 BGE config/modules/tokenizer/Pooling/2.27GB weights 和 pymilvus 3.0.0 package 指纹。执行上限是一次本地模型加载、410 vectors、13 outer batches、52 个按实际输入累计的 model micro-batches、一个新 Milvus Lite DB/collection、0 network/provider/LLM/document/retry/vector-search/rerank/Evidence。

签发没有加载模型、没有创建 working/final root、没有写 Milvus，也没有生成 terminal 或 presence result。authority 必须先作为独立干净提交推送，之后 runner 才能在 clean/synced 状态消费；失败必须 materialize typed terminal result 且不得自动 R2。

## 下一步

提交并推送 authority；随后执行唯一一次 R1。只有 R1 terminal success 才运行 20 次只读 metadata query，证明历史＋supplemental 对 10 个唯一 selected identities 达到 10/10、18 行达到 18/18。presence 通过仍不自动授权 same-matrix ranking。
