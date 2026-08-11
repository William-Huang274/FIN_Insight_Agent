# 767 — FIN 0.1.3 S1 内源补采、候选池与排序边界

日期：2026-08-09

## 结果先行

内源问题已经从笼统的“关键词可能太弱”拆成三层：查询投影已经能表达主体、证据披露方、关系方向、期间和负向过滤；当前主要缺口是本地语料与索引不够新；BGE／fusion／rerank 尚未被证明有问题，因为 8/18 目标根本不在候选池里。排序器只能重排已有候选，不能把不存在的官方材料救回来。

R3/R4 资产比较保留旧 D 盘 BM25 基线，同时选中更新的 Z 盘 full ObjectFTS。通过四份 immutable SEC manifest 恢复 1,105 份文档的 accession、filing date 和 URL 后，strict current target-in-pool 从 9/18 提升到 10/18，新增命中是 NVDA Q1 FY2027 10-Q。剩余八行只对应三个缺失的官方 source family：DELL FY2026 10-K、MU Q3 FY2026 results／remarks、TSM Q2 2026 results。

## 当前一次性补采

补采 Runtime 只通过 SEC submissions 里的 issuer、form、filing/report period 和 same-accession exhibit 发现文档，禁止用 benchmark exact URL 作为搜索种子。预算为最多一次 admission、一次 execution、八次网络、零 retry、零模型、零 broad provider、零 embedding、零 rerank、零 Evidence promotion。请求与响应先 capture，解析后仍只记 candidate；失败也会保留 capture 并物化 typed terminal，不自动补跑。

这项工作只修复本地语料，不关闭外源 broad-search 的独立 release blocker。外源当前仍为 official 4/12、hidden target-in-pool 0/12；Firecrawl credit 受限，Tencent 同矩阵 0/6。以后拿到新 Provider 仍要用同一外源矩阵重新资格化。

## 内源后续 TODO（持久边界）

1. 补采成功后建立小型 supplemental successor corpus/index，不复制或原地覆盖 14GB 历史全量资产；
2. 将 supplemental 与 full ObjectFTS、旧 BM25 以 federated route 合并，重跑同一 18-row candidate gate；
3. qrels 保持 `agent_curated_pending_owner_review`，不得由自动化自签；
4. 将 SQL 从“18 个研究目标都要命中”的错误统一门槛拆出，建立只覆盖精确数值、单位、期间和口径的 numeric fact qrels；定性机制目标由 lexical/dense/graph 负责；
5. 候选池完整并完成 qrels review 后，依次比较 sparse baseline、BGE-M3 dense、facet-aware fusion；只有本地 reranker 资源资格化后才增加 rerank lane；
6. 评测至少报告 target-in-pool、Recall@k、MRR/nDCG、cross-case/period/direction contamination、重复率、稳定性、延迟与成本；
7. 排序通过后才允许 Evidence Gate 与下游研究消费。当前不宣称内源检索、BGE、rerank、S1 或产品 release 已通过。

## 反思

本轮暴露的关键不是“应该让模型多生成一些查询词”，而是要先分清查询、语料、索引和排序分别拥有哪类责任。把所有定性问题都要求 SQL 命中，或在候选缺失时直接调 BGE/reranker，都会制造虚假的工程进展。模型查询原子仍保留为受控 A/B 方案，但只有在相同语料、相同候选预算下稳定提高召回且不扩大实体、期间和关系污染时，才进入正式 Runtime。
