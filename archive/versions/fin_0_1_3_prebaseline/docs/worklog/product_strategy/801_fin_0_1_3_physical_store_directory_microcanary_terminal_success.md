# 801 — FIN 0.1.3 目录型物理存储 microcanary terminal success

日期：2026-08-10

阶段：S1

状态：terminal succeeded；authority 已消费；0 retry

## 真实执行结果

Ubuntu-22.04 exact-once 消费 authority=`6c08008d...7340`，attempt=`20260810_s1_physical_store_artifact_directory_microcanary_r1`。运行只创建 1 个手工 4 维 synthetic vector；它没有公司身份、财务数字或 Evidence 资格。

- Milvus database／collection／insert batch／vector=`1／1／1／1`；
- flush／count／metadata query／reopen=`2／2／1／1`；
- 真实 Ubuntu symlink mutation 按预期 fail closed；
- close／reopen 后读取到同一 synthetic `vector_id` 与 `spec_digest`；
- directory tree、collection manifest／schema、data 与 FLAT index 校验通过；
- whole working root rename 后 working absent、final present，发布前后 artifact digest=`6fd72c7836f7062a5b6bfac8c40c2bded2bc51b8e48130e0796bc9a211b103ea` 一致；
- terminal result=`b7042cebaf191cabd05eae9c8dc92188cd702c4d350fa67b6bf626efaf514e77`，随后只读复核再次通过。

network／provider／LLM／BGE／document fetch／vector search／rerank／Evidence promotion 均为 0，未发生 retry。

## 业务解释

R1 的实质问题现在被真实证明已经修复：当前 backend 的 `.db` 路径确实可以是目录，产品能识别目录内部的 manifest、数据和 index，并把整个目录作为一个不可变 artifact 发布，而不会再把“不是单文件”误判成“数据库不存在”。

这仍不是研报能力或检索质量。它只证明存储发布管道可靠；93 条 DELL／MU／NVDA／ORCL／ASML／ANET 业务对象尚未构建为 R2，也没有执行任何查询。

## 下一门

先把本结果提交推送，再从 clean Git archive 独立重现两次零调用 proof，并只读复核已发布 microcanary。clean proof 通过后才能签发 fresh R2；不得再次执行 synthetic microcanary。
