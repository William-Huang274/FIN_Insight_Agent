# 699 — FIN 0.1.3 S1-08 Agentic Search entry 与候选池 ceiling 审计

日期：2026-08-07
阶段：`013-S1-08`
状态：`entry_audit_pass / upstream_blocked_candidate_generation_before_ranking`

## 1. 为什么不能直接测排序

S1-07 已证明 DELL、MU、NVDA 各一条官方来源能真实 fetch/capture/parse/promote，但不代表 S2-04 Gold benchmark 所需的当前研究来源已经进入搜索候选池。S1-05 的 26/26 是 2026-07-26 curated governed pack；S2-04 则冻结于 2026-08-06，包含 10 个来源、33 条 Evidence 和 12 个隐藏目标组。两者不能直接视为同一候选空间。

按实验治理规则，本项先检查 `target_in_pool`。如果必需证据没有机会进入候选池，NDCG、MRR、BGE/Milvus rerank 或扩大 top-k 都不能解决上游缺口。

## 2. 预注册合同

新增 policy `fin_0_1_3.S1_08.agentic_search_quality_evaluation:v1`，冻结：

- 三案、2026-08-06 as-of、10 source / 33 Evidence / 32 mandatory Evidence / 12 target groups；
- `target_in_pool_recall=1.0`、`required_slot_recall@8=1.0`、`NDCG@8>=0.85`、`MRR>=0.75`；
- currentness、source-diversity-or-typed-exception、accepted/rejected/gap reconciliation 与 selected-pack slot coverage 均为 1.0；
- false promotion 必须为 0；
- 每 target group 最多两次 query revision，禁止原样 retry；revision 必须记录 trigger、changed terms/routes 和 stop reason；
- Gold expected insight/evidence IDs 永不进入 planner；模型/Provider 调用为 0；
- 任一案例 candidate pool 未达 1.0，立即 upstream-block，禁止 reranker tuning。

`selected_pack_required_slot_coverage` 只衡量 S1 pack 是否覆盖必需槽位；模型或报告是否真正使用 Evidence 属于 S3，不在 S1 冒充完成。

## 3. 审计结果

审计器只读取已冻结 benchmark、S1-05 governed pack 和 S1-07 live result，没有网络或模型调用：

- benchmark HTTP official sources：9；
- 当前 governed pack distinct URLs：6；
- S1-07 live distinct URLs：3；
- 合并 active distinct URLs：7；
- 与 benchmark 当前来源 exact URL match：`0/9`；
- legacy BM25 current authority：false；
- FIN 0.1.3 provider-neutral executable search contract：不存在；现有实现仍是 `fin_0_1_2.S4.T03...`；
- query revision runtime：不存在；
- ranking metrics admitted：false。

`0/9` 只是保守的 exact-URL 下界，不能推出其他权威来源绝对不存在；但当前也没有 alternative-source semantic equivalence 证据，所以不能把 curated pack 或旧合同当成 current Search success。

## 4. 根因与下一包

本轮新增 `RC-P36-154`，owner 留在 S1-08，不后传给 S3，也不归因 DeepSeek。下一包固定为：

`S1_08_CURRENT_SOURCE_CATALOG_CANDIDATE_GENERATION_QUERY_REVISION_AND_GOLD_SLOT_MATCH_RUNTIME`

它需要：

1. provider-neutral official source catalog，入口只给实体、官方 landing page、SEC CIK、许可与 authority，不给 Gold document URL；
2. Evidence Tool Planner 从 case objective、关系图和 typed missing roles 生成/修订查询；
3. source discovery、document fetch、parser 和 candidate promotion 分轨，capture-first；
4. evaluator-only Gold matcher 单独计算 target-in-pool、recall@8、NDCG、MRR、currentness、diversity、false promotion 和 gap reconciliation；
5. full-fake/mutation 通过后，才决定是否签发真实网络 canary；不得先训练或调 reranker。

## 5. 产物与验证

- policy：`configs/runtime/fin_ia_0_1_3_s1_08_agentic_search_quality_evaluation_policy_v1_0.json`；
- program：`src/sec_agent/s1_08_agentic_search_quality_program.py`；
- materializer：`scripts/releases/materialize_fin_ia_0_1_3_s1_08_entry_audit.py`；
- result：`configs/releases/fin_ia_0_1_3_s1_08_agentic_search_entry_and_candidate_ceiling_audit_v1_0.json`；
- contract tests：`tests/contract/test_fin_0_1_3_s1_08_agentic_search_entry_audit.py`。

focused=`4 passed`；连同 S2-04 benchmark freeze、S1-05 governed pack、S1-07 web/source runtime 的扩大回归=`34 passed in 67.81s`。materializer 重跑 byte-identical，result SHA-256=`9d8cc2730a87fe8af1827e63021c58609943d4969ddc8e4f02e4b1ff517ca830`。本项模型/Provider/网络/source call=`0/0/0/0`；没有训练、rerank、live canary、Evidence business promotion、S3 或 release 动作。
