# 761 — FIN 0.1.3 S1-08 external combined R1 零调用 successor

日期：2026-08-09

## 为什么仍留在 S1-08

R1 的两类失败都发生在候选检索执行面：official route 没有越过本机受控网络代理握手，Firecrawl 又在额度耗尽后被错误地继续调用且调度不公平。它们不是 DeepSeek 研究判断问题，也不是 BGE／reranker 可以修复的排序问题。因此本轮没有跳到内源、S2 或 S3，而是在原 S1-08 内完成一个结构性零调用 successor。

## 实现内容

1. combined runner 在联网前解析全部 official host，只在所有特殊地址都属于受控 `198.18.0.0/15` 时临时设置 synthetic-DNS handshake；真实私网、混合地址和异常解析继续 fail closed，执行结束后恢复原环境。
2. Firecrawl 将 `HTTP 429 + reason=credits` 识别为 systemic credit exhaustion。只保留第一次真实失败调用，后续计划 query 全部 no-network terminalize，不 retry、不假装质量失败。
3. shadow 调度改为 case-slot 公平轮转；前 3 个 query 覆盖 DELL／MU／NVDA，前 6 个覆盖三案 customer／supply。
4. query binding receipt 保存完整 effective bound query，并新增 planner view／dispatch truth 的审计语义，避免“attempt 显示旧 query、只有 digest 证明真实 query”的双真相。
5. v1.1 policy 明确绑定 immutable R1 result 与 assessment；旧 v1.0 policy 仍可重放旧行为，不改写历史。

## 零调用证明

- focused combined＋assessment：`15 passed`；
- 全部 `tests/contract -k s1_08`：`277 passed`；
- official／Firecrawl／model／embedding／rerank／Evidence 新调用：`0/0/0/0/0/0`；
- v1.1 plan 与 proof 已重新物化；本机 preflight 验证 8 个 official host 均只命中受控 synthetic range，并通过 Project OS blocker 检查。

首次在 Project OS 中投影 clean-proof scope 后，完整 S1-08 回归以 `projection_scope_unregistered` 拒绝 11 个治理断言；这是新 scope 未登记造成的真实配置缺陷，不是检索行为失败。已只在 v1 scope registry 中登记 `S1_08_EXTERNAL_COMBINED_SUCCESSOR_CLEAN_INDEPENDENT_ZERO_CALL_PROOF`，未改测试预期或扩大 live 权限；该失败与纠正保留在本记录中。

当前结论是 `zero_call_engineering_pass`，还不是 clean independent proof，也不是 external search 产品通过。下一步只能先提交干净实现并在 clean archive／fresh process 中复证；复证通过后才可另行签发唯一一次 recovery exact-live。若 Firecrawl 额度仍耗尽，新 Runtime 最多消耗一次 shadow 网络调用并诚实保留未观察状态；不得为了补齐三案反复 live。

## 已冻结的后续

外源一旦完成有界 closeout，下一项必须回到内源 Query Facet：exact SQL／object、BM25／ObjectBM25、dense／Milvus、relationship graph。随后扩大人工 qrels、证明 candidate ceiling，之后才比较 BGE、fusion 与 reranker，最后验证候选进入 Evidence Gate、Claim、Workpaper 和报告。该顺序记录在 `fin_ia_0_1_3_s1_retrieval_query_facet_external_internal_progression_plan_v1_1.json`，不能因上下文压缩或外源结果较好而跳过。
