# 797 — FIN 0.1.3 CandidateBundle physical-index R1 authority

日期：2026-08-10

阶段：S1／ObjectBM25＋BGE-M3／Milvus exact-once build authority

状态：authority 已签发、未消费；真实构建待独立执行

## 签发结果

物理 builder、full-fake、policy 与 Project OS scope 已随 clean/synced commit `566d5223dca1d6d28dc802cd4bfa4fa6cc1a477e` 推送。签发器重新读取 Ubuntu-22.04 WSL2 环境，而不是复用工作记录中的旧结论：Python／8 个直接包版本、四个关键 package tree、59-row pip freeze、本地 BGE-M3 五文件、milvus manifest source、93-spec private manifest、约 975GB free disk 与 fresh working/final targets 均再次通过。

authority=`0ca08fecf6d759fbea23b83b5efee0052ac9072302fbe8475a43c37dc2dd4260`，状态=`issued_unconsumed`。只允许唯一 R1：真实 ObjectBM25 93 records；本地离线 CPU BGE-M3 1 次加载／93 vectors／12 batches；新 Milvus DB＋collection／12 inserts／double flush／close-reopen／identity metadata query；0 network／Provider／LLM／document fetch／vector search／rerank／Evidence／retry。

## 执行前仍需满足

authority 必须先作为独立提交推送。执行 worker 会再次计算当前 environment identity，与签发快照逐项比较后才创建 working root；签发后 package、model、manifest、source bindings 或 fresh target 任何漂移都会在 BGE load 前 fail closed。

authority 不等于物理索引存在，更不等于检索质量。R1 terminal success 后只能进入 read-only sparse／dense same-matrix evaluation；Windows Workbench 到 WSL store 的调用接线、Evidence、外源补源、DeepSeek 研究与 release 仍是后续 gate。
