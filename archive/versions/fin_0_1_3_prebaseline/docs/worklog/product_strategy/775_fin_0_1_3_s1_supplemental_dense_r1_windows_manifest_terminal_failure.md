# 775 — FIN 0.1.3 S1 supplemental dense R1 Windows manifest terminal failure

## 终态

唯一 R1 `20260809_s1_supplemental_dense_bge_m3_milvus_incremental_build_r1` 已消费并 terminal failed；result digest=`9ae78bf2096b3ee5ddaa731093c8bf05dbf0df99193ab35345788f93313d08a3`。BGE-M3 加载 1 次，13 个 outer batches／52 个实际累计 micro-batches 共编码 410 vectors；Milvus 新建 1 DB／1 collection，13 个 insert acknowledgements 共确认 410 rows。network/provider/LLM/document/vector-search/rerank/Evidence 与历史库写入均为 0。

失败发生在 `create_and_populate_working_milvus` 的 terminal-count flush：本机 `milvus-lite 3.0` 的 `storage/manifest.py`（14,646 bytes，SHA256=`59b45341edf6531e68736d37d7f93aba5355d8daa06b11ad120289b3e234fcd6`）调用 `os.rename(manifest.json.tmp, manifest.json)`，Windows 因目标已存在返回 `WinError 183`。working root 保留，final root absent；presence proof 没有运行，R1 不得按“410 已 insert”改判为成功。

## 根因与反思

这是 storage dependency portability failure，不是 BGE、语料、查询或 DeepSeek 问题。官方 milvus-lite main 的同一代码当前已使用 `os.replace`，说明本机 3.0 wheel 与当前 upstream 在 Windows atomic replacement 上存在已知语义差异：[official manifest source](https://github.com/milvus-io/milvus-lite/blob/main/milvus_lite/storage/manifest.py)。同时，R1 authority 只指纹了 pymilvus METADATA/init，漏掉真正执行的 `milvus_lite` package；因此即使 Git clean，storage engine 代码仍未被完整绑定。

## 下一步边界

R1 immutable，0 retry，不能直接把外部依赖中的 `rename` 改成 `replace` 后重跑。下一项只允许零 BGE、零网络的 successor qualification：

1. 对完整 milvus_lite package 建递归可重复指纹；
2. 在隔离临时目标上验证 1-vector create、insert、double flush、close、reopen、count 与 metadata query；
3. 比较官方 Windows-safe successor 与当前失败版本，不复用 R1 working root；
4. 资格审查通过后，再单独请求 fresh replacement authority。

新的 progression plan 为 v1.7，digest=`424da22b8984dd3fd3c4e585d507eedfbfff1a55b7d04bc89080e8dc91b7415c`。本项不授权 R2、presence、ranking、reranker、Evidence、current-quarter SQL、external provider、release 或 production。
