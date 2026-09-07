# Model Run: FIN013-S1-DELL-03B-INTERNAL-CHAIN-CEILING-R1

## 摘要

- 目的：对 6 个不与 02B 人工 admission 重叠的 DELL 研报目标，执行一次 current R38 内部链与候选 ceiling 定位。
- 当前状态：`terminal_failed_no_retry / source_record_identity_field_assumption`。
- 允许节点：本地 Qwen3-Embedding-0.6B 只编码 5 个冻结请求，最多 1 个 query batch；R38 的 34,198 个 document embedding 只读复用。
- 禁止节点：网络、Provider、生成模型、外部 capture、4B embedding、reranker、重试、current mutation、Candidate/Evidence promotion 和 gap closure均为 0。
- 目标：区分“本地 source/object 根本不存在”“对象存在但 BM25+0.6B+graph union 漏召回”“已进 union 但未进 useful@10”以及“已进入 useful@10”，为后续 4B embedding、reranker 或 03C 外源梯子分别提供依据。

## TokenBudgetBasis

- node purpose：编码 5 个冻结 DELL 03B request query，并对照 6 个 report-material target contract。
- input scale：34,198 个 digest-bound current compiled objects；document dense cache 已存在，只运行 1 个 query batch。
- required outputs：每目标 source/object/index/SQL、corpus/union/final 三层匹配、rank trace、earliest loss、4B/reranker/03C eligibility。
- schema burden：绑定 03A R2、observable-input request program、R38 registry/receipt、全 union seed、source lineage 和 private/public digest。
- materiality/quality risk：传统服务器 ASP、美元 shipments、供应商自有产能、泛 yield 风险或泛 OEM 关系都可能被误写成 Dell AI-server ASP、物理台数、观测 yield 或 supplier→Dell allocation。
- comparable evidence：R30 DELL internal R3 曾以 1 个 0.6B query batch 产出 705 union candidates，但其 12/12 complete 只代表 candidate-level material scope；R38 又追加 9 个 reviewed objects。
- reasoning profile：non-generative embedding；目标判断由预注册的 conjunctive lexical semantic gates 确定性重放。
- stop/truncation：任一 SHA/digest 漂移、dirty tree、held target、请求数>5、query batch>1、source/object join 失败、任何越权调用或 output collision 立即停止；union=96/request、final review=16/request 不扩容。

## 预注册判定

- local corpus 有完整 target object、current union 没有：4B embedding recall challenger `eligible`，但仍需另行授权。
- complete target 已在 frozen union、但不在 useful@10：same-pool reranker `eligible`，但仍需另行授权。
- local corpus 没有完整 target object：embedding/reranker 不能创造信源，转入另行授权的 03C 原文梯子。
- complete target 已在 useful@10：先做 CandidateDecision/Evidence Gate；不能为“模型更大”而继续跑模型。

## 当前边界

R1 从 clean、remote-synced commit `7468e5c5...` 启动并消费了唯一一次本地 0.6B query batch；随后在
结果编译前失败。runner 假设 source-store JSONL 的身份字段为 `source_record_id`，而真实 1,888 行
全部使用 canonical `evidence_id`；compiled object 才把该身份投影成 `source_record_id`。因此
`dell_03B_source_record_id_missing` 是 S1 runner seam 缺陷，不是信源缺失或模型质量失败。

没有 private/public 输出、current mutation、网络、Provider、外源、4B、reranker、promotion 或 gap
closure。R1 不重试、不追认；失败回执为
`configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_r1_failure_receipt_v1_0.json`。修复后只能用新
attempt R2。该失败不等于 CandidateDecision、Evidence admission、真实补源、proved public-information
boundary、G3、S1/S2/S3、研报质量、产品、publication 或 release。
