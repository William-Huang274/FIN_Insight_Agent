# 800 — FIN 0.1.3 目录型物理存储 microcanary authority

日期：2026-08-10

阶段：S1

状态：authority 已签发、尚未消费

## 签发结果

从 clean/synced commit `90d8ac715e81d1270b29fce799afa8de58badd83` 重新执行 Windows issuer；Ubuntu-22.04 只读资格检查确认 pymilvus=`3.0.0`、milvus-lite=`3.0`、目录型 backend profile、working/final root 均不存在且磁盘空间充足。Project OS scoped preflight 通过。

authority attempt=`20260810_s1_physical_store_artifact_directory_microcanary_r1`，digest=`6c08008d44fe753d86e6ba5478a2cf97c60fba0c49cb31ea29659b67c08b7340`，状态=`issued_unconsumed`。

## 唯一允许的执行

- 只写 1 个手工 4 维 synthetic vector；不含公司、财务事实或 Evidence；
- 只创建 fresh private working root／collection，完成 insert、flush、count、close／reopen、identity、tree digest 与 whole-root rename；
- 在真实 Ubuntu 上自然执行 symlink rejection mutation；
- network／provider／LLM／BGE／vector search／rerank／Evidence promotion 均为 0；
- 最大执行 1 次，automatic retry=false。

## 边界

本 authority 不是 93 条业务索引 R2 权限，也不是检索质量或 Evidence 验收。执行成功后还需独立 two-clean-archive proof；只有该证明通过才能另行签发 R2。
