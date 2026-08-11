# 796 — FIN 0.1.3 CandidateBundle 物理索引环境与 full-fake

日期：2026-08-10

阶段：S1／共享 CandidateBundle ObjectBM25＋BGE-M3／Milvus 物理索引

状态：Linux 环境资格与实现 full-fake 通过；干净提交后方可签发 exact-once R1 authority；真实建库尚未执行

## 1. 为什么不能直接复用旧 410-vector runner

旧 runner 消费的是已经被业务审计否决的 410 条片段形状，并把 Windows repo 私有目录作为发布目标。它证明过 BGE 能编码、也留下了 Milvus Lite 3.0 在 Windows `os.rename` 覆盖 manifest 时失败的不可变证据；它不能代表现在由六案 93 个业务审过 CandidateBundle 组成的新语料，也不能在 Windows 上重跑。

本 successor 不增加 ticker 分支。它只消费 manifest R4 的 93 个 spec，并把每个 spec 同时转换成现有 `ObjectBM25Retriever` 可读的记录和 BGE-M3／Milvus row。sparse 与 dense 的对象 ID、case、spec digest 必须完全一致；19 条自动叙事继续 quarantine，Candidate 不能借建库自动晋升为 Evidence。

## 2. Linux 环境事实

Ubuntu-22.04 WSL2 的 Linux 根文件系统约有 975GB 可用空间，working／final exact-once 目标均不存在。本轮新建独立环境 `/home/william/.cache/fin_insight/candidate_bundle_build_env_v1`，不修改旧 Milvus canary 环境：

- Python `3.10.12`；
- CPU-only Torch `2.10.0+cpu`、Transformers `5.2.0`、SentenceTransformers `5.2.3`；
- pymilvus `3.0.0`、milvus-lite `3.0`、rank-bm25 `0.2.2`；
- pip freeze=`59` rows，digest=`8c47414e...af00`；
- 本地 BGE-M3 的 config／modules／tokenizer／2.27GB weights／Pooling 文件与旧 authority 哈希一致；
- 当前 milvus manifest source 仍为 `os.rename`、SHA256=`59b45341...fcd6`，因此只允许 Linux root filesystem，Windows 路径继续不合格。

选 CPU 不是生产性能结论，而是首个 93-object 物理完整性证明的可复现执行面。后续 GPU 只能作为新资源资格，不得静默改变本 R1。

## 3. 实现与 full-fake 结果

新增 provider-neutral builder、一次性 authority issuer 和 Linux worker。物理发布合同为：新建 working root → 从 digest-bound manifest 构建 ObjectBM25 → 本地离线加载 BGE → 12 批编码／Milvus insert → double flush／count → close/reopen → 一次 metadata query 核对 93 个 `(vector_id, case, spec_digest)` → 写私有 receipt → 同文件系统 rename 到 final root。失败保留 working root、写 typed terminal result、0 retry。

full-fake 使用真实 ObjectBM25 序列化和现有 retriever 读取路径，dense 只用 fake 1024 维向量／writer。结果为 sparse=`93`、dense=`93`、12 batches、2 flush、2 count、1 reopen、1 metadata query，shared identity digest=`c0f984be...bdba`。duplicate identity、vector text drift、Candidate→Evidence 污染、cross-case population、partial dense ack、authority digest drift、preexisting sparse target 七类 mutation 均 fail closed。proof=`99b7f66e...cfdc`，真实 BGE load／embedding／Milvus read/write／network／Provider／DeepSeek=`0`。

## 4. 产品边界与下一步

物理建库成功也只表示“同一 93 个候选对象真实存在于 sparse 与 dense store”。它不证明查询能找到正确资料、排序有增益、Evidence Pack 完整、Workbench 已能从 Windows 调用 WSL store，也不证明外源补源或研报质量。

下一步必须先提交并推送本实现。从 clean/synced commit 再次只读核对 Ubuntu、package tree、BGE bytes、manifest、目标不存在、磁盘和 Project OS scope，签发唯一 R1 authority；authority 与执行必须分开。R1 成功后才允许只读 retrieval evaluation，失败则保留 terminal evidence 并停止自动 R2。
