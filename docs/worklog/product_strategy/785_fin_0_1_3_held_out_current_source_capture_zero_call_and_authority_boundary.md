# 785 — FIN 0.1.3 留出案当前官方源 capture-first 零调用证明

日期：2026-08-09

归属：FIN 0.1.3 / S1 / 三案例 held-out generalization

状态：`zero_call_engineering_pass_live_authority_not_yet_issued`

## 1. 本项为什么仍属于 held-out proof

ORCL、ASML、ANET 的本地候选已经证明接口能够终态化，但冻结截至期所需的当前披露缺失。这里不是 broad Web Search，也不是为了补齐数量泛搜网页；只从公司 CIK、表单优先级、申报日期、报告期和正文 marker 编译 SEC submissions 路由，用来补本地官方 source inventory。

正式 policy 不包含 accession number、SEC Archives 成品 URL 或答案文档。最终地址只能从 live submissions 响应确定，因此不会把已知答案伪装成检索能力。

## 2. 零调用工程证明

新增独立、provider-neutral acquisition runtime，覆盖：

- ORCL：FY2026 10-K，USD；
- ASML：Q2 2026 6-K，可在同 accession 下选择一次结果 exhibit，EUR／PDF 路径保留；
- ANET：Q2 2026，优先 10-Q、后备 8-K，可选择一次同 accession exhibit；
- 每次请求和响应先保存，再做 submissions 选择、HTML／PDF 解析和 marker 校验；
- source capture 最高仍是 Candidate 输入，不是 Evidence；
- 任何 consumed failure 都必须保留 capture、生成 typed terminal 且禁止自动 retry。

fixture proof 使用 7 次模拟 source call，实际网络、Provider、模型、embedding、rerank 和 Evidence 调用均为 0。表单优先级、旧期间排除、same-accession fallback、capture-first、exact-once terminal 和异常 terminalization 均有专项测试。proof digest=`38be2a28...8254`；focused＋Bundle v2 adjacent=`12 passed`，完整 held-out adjacent 上轮=`33 passed`。

## 3. Project OS 门禁修复

首次物化前置检查发现根因账本已经引用 5 个后续 S1 scope，但作用域注册表没有同步登记，导致 `project_os_contract_invalid`。这不是 source runtime 失败，也没有绕过门禁。现已补齐 CandidateBundleV2、held-out reproof、current-source capture、future dense build 和 sparse/dense fusion scope；RC-P36-157 与 RC-P36-162 新增投影，明确只允许当前 exact SEC source capture，仍禁止 broad-web、embedding、Milvus、rerank、Evidence 和模型调用。修复后 scoped Project OS preflight=`pass`。

## 4. 预算与边界

- 唯一 live execution ceiling：1；
- network ceiling：9；
- retry：0；
- model／provider／embedding／rerank／Evidence：0；
- raw request、response body 与 parsed text：只保存在 Git 外私有 object store；
- public result：只保存 URL、日期、表单、digest、capture ref、typed gap 和 terminal receipt；
- 当前零调用证明不代表 2026 文件真实存在，更不代表 current source 已解析为安全 Bundle。

## 5. 下一步

先在 clean／synced commit 上签发唯一 admission，再执行一次 capture-first live。即使三案全部抓到，也必须另做 current source 的结构化对象重解析、currency/table/period 检查和六案 mutation reproof；这些通过前不得进入 sparse／dense build。

机器证据：

- policy=`configs/runtime/fin_ia_0_1_3_s1_held_out_current_source_acquisition_policy_v1_0.json`
- zero-call proof=`configs/releases/fin_ia_0_1_3_s1_held_out_current_source_acquisition_zero_call_proof_v1_0.json`
- runtime=`src/sec_agent/financial_research_held_out_current_source_acquisition.py`
- live runner=`scripts/releases/run_fin_ia_0_1_3_s1_held_out_current_source_acquisition.py`
