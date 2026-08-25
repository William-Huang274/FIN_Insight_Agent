# S1 工作记录 083：DELL-RSQ-03B 内部链与候选 ceiling

日期：2026-08-25

状态：`implementation_and_preregistration_targeted_gate_pass / clean_commit_and_single_R38_attempt_pending`

## 1. 为什么不能复用旧“12/12 complete”结论

R30 的 `dell-proposition-internal-r3` 确实执行了 SQL、对象、BM25、Qwen-0.6B 与关系路线，但其
`12/12 material_set_complete` 是候选层材料范围，不是 03A 九个 residual target 的逐命题充分性。
对旧 final review 逐条抽查可见：

- ASP 高位候选是 traditional server ASP／richer configuration，不是 Dell AI-server ASP 或带分母的配置价；
- units 高位候选把 `$16.1 billion shipments/revenue`、orders 和 backlog 带入候选池，没有物理台数；
- capacity/HBM 候选主要证明供应商自身扩产、风险或 HBM 技术障碍，没有 supplier→Dell allocation；
- relationship 候选存在 generic supplier、generic OEM 和无关 customer-relationship 文本。

因此“候选多／材料轴有文本”不能回答“精确 target 是否在 source object、union 或 useful@10”。R38
又在 R30 后追加 9 个 reviewed objects，旧结果只能作为 comparable run，不能冒充 current 03B。

## 2. 本轮冻结范围

只执行 6 个 `currently_unoverlapped` target：ASP、units、capacity release、capacity utilization/yield、
HBM supply、supplier read-through。demand durability、product profit 和 working capital 三个 target 仍由
02B qualified-human admission 阻断，执行数必须为 0。

实际请求去重后为 5 个：price configuration、unit volume、supply subject execution、upstream capacity、
supply relationship。内部链消费 current R38 source records、compiled objects、SQL sibling、BM25、
Qwen3-Embedding-0.6B dense cache/query encoding 与 typed relationship graph。网络、Provider、生成模型、
外源、4B、reranker、重试、promotion 和 gap closure 均无权限。

## 3. 新合同与实现

- policy：`configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_0.json`；
- compiler：`src/retrieval/dell_report_internal_chain_ceiling.py`；
- runner：`scripts/data_retrieval/run_dell_report_internal_chain_ceiling.py`；
- tests：`tests/test_dell_report_internal_chain_ceiling.py`；
- model-run ledger：`reports/model_runs/FIN_0_1_3_S1_DELL_03B_INTERNAL_CHAIN_CEILING_R1_20260825.md`。

compiler 对每个 target 扫描全部 34,198 个 current object，再把完整／部分语义对象与 raw union seed、
final review 和 source lineage 精确连接。earliest loss 只允许四种：local corpus 缺对象、当前
BM25+0.6B+graph recall miss、post-union/review cut、或 useful@10 前无观察损失。

4B embedding 与 reranker 没有被删除，而是被分开：local object 存在但 union 漏召回才使 4B recall
challenger eligible；complete object 已在 union 但不在 useful@10 才使 reranker eligible；local object
根本不存在则两者都不能补源，应进入 03C。eligible 仍不等于 execution authority。

## 4. 当前验证

- 新 03B 测试：`17 passed`；
- 连同 03A、旧 internal runner、candidate ceiling 和 source-route 相邻测试：`64 passed`；
- 全仓：`1378 passed, 2 skipped, 2 warnings in 475.02s`；两条 warning 是既有 SWIG deprecation；
- 新 Python `py_compile`／compileall、精确 pyflakes、policy JSON parse 和 `git diff --check` 通过；
- active baseline：`213 Python / 8 frontend / 5 detectors / 28 resources / 0 forbidden`；
- `1125` 份 config JSON、8 个 Project OS JSONL／`1216` 行通过；
- secret scan：`8087 files / 0 findings`。

当前仍未执行 R38 03B、未产生 private/public result、未使用本地 embedding inference。下一门是完整
工程回归后形成 clean implementation commit，再从该 clean commit 消费唯一一次 R1 authority。

## 5. 不变边界

03B 的 deterministic semantic gates 只定位 candidate ceiling，不签 CandidateDecision、Evidence、
NumericFact 或 information boundary。02B 仍为 `0/16`；03C/03D 需根据 03B 结果另行授权；G2/G3、
Pack/Readiness/S2 重编、动态 Agent、Writer、formal Q1–Q8、S1/S2/S3、report/product/publication/release
继续为 false。
