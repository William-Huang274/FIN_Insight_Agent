# 757 — FIN 0.1.3 S1-08 DeepSeek query-atom A2 终态与 local-only 处置

日期：2026-08-09

## 结果

replacement authority digest=`360ec6c4c7c2a83e21b9d388159c06414ec8709cfe45b2422fcbb8cd636a1b55`。clean/synced `a54b129876cd5df0131aadeb1abdb00bcb512696` 上签发并消费唯一 A2；DeepSeek v4 Pro 完成 1 次 Provider／network／model call，1 次 transport attempt，`0 retry / 0 fallback`，耗时 `13,377 ms`，usage=`5,235 input + 1,298 output = 6,533 tokens`。

模型返回 18 个字段形状正确的查询原子，其中 17 个绑定现有 typed plan；第 10 个把 MU 的 `regulatory_risk_and_financial_reconciliation` 写成不存在的 `regulatory_risk_and_financial_recovery`。Runtime 在 capture 后返回 `terminal_failed_no_retry / s1_08_query_atom_canary_output_plan_binding_invalid`，accepted atom=`0`，没有部分打捞、字段修补、自动重试、Runtime activation、document/retrieval/embedding/rerank/Evidence 调用。

## 处置

这不是继续修 Prompt 或新增 alias 的理由。Evidence Slot 是 Harness 结构身份，模型不得近似改写。当前 model-assisted variant 记为 rejected；冻结 raw/local A/B 中 `deterministic_local_compiler` 的 facet coverage=`1.0`、duplicate=`0`、contamination=`0`，因此选为 external combined live 与后续 internal retrieval 的唯一基线。

完整模型可见 request 与 raw gateway result 保存在本地受限 capture，Git 只保存 digest、终态、usage 和唯一非法绑定；credential／Authorization／Cookie／private reasoning 未保存。public result=`configs/releases/fin_ia_0_1_3_s1_08_deepseek_query_atom_canary_result_v1_0.json`。

## 下一步与边界

先实现 official routes＋Firecrawl shadow 的 local-only combined live runner、full-fake/mutation、authority；通过后执行一次 fresh combined live。外源收口后立即进入内源 exact SQL/object、BM25/ObjectBM25、dense/Milvus、relationship graph，再做 qrels/candidate ceiling，最后才准入 BGE、融合与 rerank。该顺序记录在 progression plan v1.1，不因聊天压缩丢失。
