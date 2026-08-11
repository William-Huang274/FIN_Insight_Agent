# 773 — FIN 0.1.3 S1 supplemental dense 真实 runner full-fake 与资源指纹

## 结果

真实 incremental builder、authority issuer、terminal-result materializer 与 post-build presence proof runner 已实现。实现证明复用 live 相同的 Milvus schema/writer、410 条 vector specs、13 个 outer insert transactions 和 terminal-count 路径，通过 fake dependency 精确终态 410；没有加载 BGE、创建私有 DB 或写 Milvus。

签发前复核发现共享 build plan 曾在校验与返回结果时重复读取 collection count，而冻结 ceiling 只允许一次 collection-stats read；现已把 terminal count 缓存后复用，full-fake 明确证明 `count=1`、`flush=2`。runner 也不再把 52 个 micro-batches 写成硬编码常量，而由每次实际输入和 batch size 累计。更新后的 implementation proof digest=`2e9cb6fd6166debde2da334aa4aceb679a490d63b357e8d1d81dbf23b640d30f`。

为降低 RTX 4060 Laptop 8GB 显存风险，source build contract 仍保持每个原子 insert transaction 32 rows，但 SentenceTransformer 内部 micro-batch 固定为 8，预期 52 个 GPU micro-batches。该调整不改变语料、vector identity、embedding model、维度、规范化或最终 batch/insert 计数，也不是模型调参。

## Authority 边界

真实 authority 必须在 clean/synced implementation commit 后单独生成，精确绑定 execution policy、zero-call proof、implementation proof、compiler、execution module、build runner 与 presence runner。除 Git 文件 SHA 外，还绑定本地非 Git 资源：BGE config/modules/tokenizer/2.27GB weights/Pooling config 的 bytes 与 SHA256，以及 pymilvus 3.0.0 METADATA 和 package init 指纹。实测完整资源指纹只需约 5.3 秒。

authority 只允许一个 R1：1 次本地模型加载、410 vectors、13 outer embedding/insert transactions、52 model micro-batches、一个新 DB、一个新 collection、0 retry/network/provider/LLM/document/vector-search/rerank/Evidence。任何失败写 immutable terminal result，保留私有 working root，不自动 R2。

## Post-build

成功的 410 entity count 仍不等于 10/10 presence。独立 read-only proof 将对 10 个唯一 selected identities 分别查询历史与 supplemental collection，共 20 个 metadata queries；必须达到 10/10 unique、18/18 rows，且不做 vector search。即使通过，也不自动授权 same-matrix ranking。

## 当前状态

- implementation full-fake：通过；
- real BGE load／embedding／Milvus write：0；
- authority：未签；
- private working/final target：均不存在；
- ranking、reranker、Evidence、current-quarter exact、external coverage、release：未授权或未完成。

下一步是提交并推送本实现，再从 clean commit 生成唯一 authority。
