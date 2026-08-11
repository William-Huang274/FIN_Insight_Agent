# 798 — FIN 0.1.3 CandidateBundle physical-index R1 directory-store failure

日期：2026-08-10

阶段：S1／ObjectBM25＋BGE-M3／Milvus exact-once physical build

状态：R1 authority 已消费；terminal failed；0 retry；失败现场保留

## 结果与业务含义

唯一 R1 在 clean/synced authority 提交 `e63c2958f48449f242460e2d0202d4437aef93f6` 后执行。执行前 environment identity、93-spec manifest、模型文件和 fresh Linux targets 再次通过。BGE-M3 从本地离线加载，93 个 CandidateBundle 分 12 批生成向量；Milvus 创建 1 个 store／1 个 collection，并确认 12 批、93 个 insert acknowledgement。随后发布器以 `Path.is_file()` 检查 `milvus_lite.db`，得到 false，终态失败：`candidate_bundle_physical_dense_database_missing`。result=`3d26e82a...0af5`。

这不是“向量没生成”或“Milvus 没写入”。只读取证确认当前 Milvus Lite 3.0 把 URI 建成目录型 store，而不是单一 SQLite 文件：目录 manifest 的 `current_seq=93`，Parquet=`93 rows／15 columns／625,086 bytes`，FLAT/COSINE index=`381,056 bytes`，整个 store 约 `1.1 MB`；ObjectBM25 的 `records.slim.jsonl`、`bm25.pkl` 和 metadata 也留在失败 working root。失败点是发布合同把后端物理形态写死成 file，无法生成受合同认可的 receipt 和 final publication。

因此产品状态仍是 `physical index=false`。插入确认、Parquet 行数和失败现场不能替代成功终态；失败 working root 不得改名、复用或接入 Workbench，R1 不得重试。

## 同轮发现的审计缺口

失败 envelope 保存了 BGE load／batch／vector、Milvus create／insert 数量，但没有保存 writer 已发生的 flush、count、reopen 和 metadata-query 计数，也没有保存最后一个已验证 dense snapshot。这个问题与 file／directory 误判属于同一个物理发布合同缺口，应一次结构化修复，不能逐字段补日志。

## 下一处置边界

下一步只准做零模型、零网络、零业务索引写入的 S1 结构处置：

1. 把 Milvus artifact 抽象为 `file | directory`，由受支持的 backend profile 声明，不由扩展名猜测；
2. directory store 生成 canonical tree manifest，逐相对路径记录类型、大小和 SHA256，并绑定 collection manifest／row count／identity digest；
3. receipt 与 failure envelope 保存完整阶段快照和全部 writer counters；
4. 以临时目录 fake 和 1-vector isolated micro-canary 验证 directory close／reopen／count／metadata／tree digest／whole-working-root same-filesystem rename；
5. clean proof 后才可另行决定 fresh R2 authority。R2 不能复用 R1 working root、authority、attempt ID 或 terminal result。

检索排序、Windows Workbench→WSL 接线、Evidence Pack、外源 residual supplement、DeepSeek 动态研究与 release 继续保持 false。
