# Milvus 与检索 Runtime 计划

## 当前状态

上一阶段 expanded retrieval 已在云端完成 typed Milvus vector build，并通过 retrieval-only A/B gate。当前事实：

- Milvus 仍在云端。
- 本地当前并不应假设 Milvus 可用。
- Milvus route 是显式 `milvus_semantic` / typed semantic recall supplement。
- Milvus 不能替代 BM25 / ObjectBM25 / exact-value ledger。
- Milvus rows 默认 `exact_value_authority=false`。

## vNext 目标

vNext graph 需要把 Milvus 作为 retrieval runtime capability 写进 inventory，而不是写死在 graph 内：

```json
{
  "milvus_runtime": {
    "status": "cloud_available | local_available | unavailable",
    "location": "cloud | local | none",
    "collection": "typed_sec_evidence_v0",
    "vector_kinds": ["narrative_chunk", "metric_object", "risk_text"],
    "claim_boundary": "semantic_recall_supplement_not_exact_value_authority",
    "fallback_routes": ["bm25", "object_bm25", "exact_value_ledger"]
  }
}
```

## 云端 / 本地决策点

后续实现需要支持两种运行模式：

### Cloud Milvus

适用：

- 603-company expanded full assets。
- 批量 retrieval A/B。
- 云端 full-chain gate。

要求：

- cloud endpoint / collection 只通过 env / profile 注入。
- 本地 prompt / docs 不写 endpoint secret。
- summary artifact 记录 collection id、vector count、as_of、schema digest。

### Local Milvus / Milvus Lite

适用：

- 本地 smoke。
- 小批 fixture。
- 离线 graph 测试。

要求：

- 本地 index path 必须进 private / ignored path。
- 只在 S0 chunk/retrieval asset quality gate 通过后使用。
- 本地缺 Milvus 时 graph 自动降级为 route unavailable，而不是偷偷用 semantic mock。

## Research Lead 行为

Lead 只知道 Milvus capability，不知道连接细节。

允许：

- 在 paraphrase / relationship / hard-to-keyword filing text 需求下请求 `milvus_semantic`。
- 在 exact numeric claim 下优先请求 `ledger_first`。

禁止：

- 用 Milvus 支持 exact value。
- 把 Milvus 设为默认所有 query 必走。
- 在 Milvus unavailable 时仍激活 semantic route。

## Reflection 行为

Reflection 可把缺口诊断为：

- `milvus_semantic_recall_gap`: BM25/ObjectBM25 未找到文本上下文，但 inventory 显示 Milvus 可用。
- `milvus_runtime_unavailable`: query 需要 semantic supplement，但当前 location 未启用。

第一类可以 second-pass repair。第二类进入 bounded gap 或 fallback route，不应假装已查。

## 验收条件

- Inventory 中明确显示 Milvus cloud/local/unavailable。
- `Research Lead` 的 evidence requirement 保留 route-selection reason。
- Milvus rows 在 Evidence Fusion 中带 `semantic_recall_supplement` boundary。
- Verifier 能阻断 Milvus row 支持 exact-value claim。
- 本地无 Milvus 时测试仍可 pass，并明确 route unavailable。
