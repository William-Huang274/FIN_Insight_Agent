# 723｜FIN 0.1.3 S1-08：DELL R3 终态、来源质量失败与 P3 交接

日期：2026-08-08

阶段：`013-S1-08-R3`

结论：唯一 DELL R3 已在冻结 authority 下 exact-once 完成。运行、capture、typed gap 和 terminal 物化通过，但产品来源质量硬失败：`15 network / 0 model-provider-retry / 13 query attempts / 0 accepted candidates / 5 typed gaps`。R3 不重跑，不创建 R4；下一项仅为 `S1_08_P3_POST_R3_OWNED_SCHEDULER_CACHE_AND_PROVIDER_PRODUCT_SCOPE_DISPOSITION_DECISION`。

## 执行身份与不可变证据

- source commit：`a5b5038c8835a1c56e5c4d3f2d3ca98b0e624e85`；
- run：`fin013_s1_08_dell_r3_run_539a0a59c11d7cd46cb9`；
- attempt：`fin013_s1_08_dell_r3_attempt_de43fdcbef5f78f0f9ef`；
- admission：`fin013_s1_08_dell_r3_admission_a3f1c96343823f83883b`；
- admission digest：`a3f1c96343823f83883b1d29fa356c3e171b3bbe7e0ccbd7b2ec165dd26136de`；
- terminal：`complete / dell_current_search_r3_complete_with_typed_gaps`；
- terminal digest：`d55b36f536ff277c79d3c706cad8b12fc4a44a54c871432f003113aaa2d417b0`；
- candidate result digest：`ca6d3cfe8758f3a3e0dc10dfe93eeb9d0070de410e23cb75c3d193ed41c7f589`；
- shared receipt digest：`57e7f2a7ceb3835ca7ed0a86a6c034fc02b0d9d0a549cdecd93da1c1431d93b6`；
- result SHA-256：`731885330176f1d3a428ed3cdf62315e34c345f457ba39b749d60802d9c6b1d5`；
- quality evaluation digest：`d386523815aea5b5fe9fd83294dfd8c203ca7c841b5bb2a50278e15b17bfee07`；
- quality evaluation file SHA-256：`b8af0d6e6a573ce2365d544972bfb74bbdf6ba8927c4a29f1d33cae8a6b6c5f2`。

版本化 result 不包含 runtime contact 明文、Authorization、Cookie 或 raw body。受限对象存储中保留 `13 source request / 11 source response / 2 typed transport failure / 0 document request`，candidate 与 terminal digest 已独立重算，shared admission 为 terminal。

## 产品结果

机械控制面通过：exact-once、预算、capture-first、失败物化、typed gap、slot 首次机会、starvation=`0`、已知导航噪声 fetch=`0`。

来源产品门失败：

- qualified locator receipts=`229`，但 document request capture=`0`；
- accepted/selected/unique source=`0/0/0`；
- 五个 Evidence Role 全部只能以 typed gap 关闭；
- qualified unique-document yield=`0.0 < 0.5`；
- DELL target-in-pool、required-slot recall@8、selected-pack coverage 均为 `0`；
- ranking admission=`false`，不得运行 BGE/Milvus、MU/NVDA transfer、DeepSeek Experiment B 或 S3 下游研究。

终态字符串中的 `complete_with_typed_gaps` 只表示运行可靠地结束并保存了缺口，不表示 Agentic Search 产品通过。

## 根因复盘

主要根因属于项目内 S1 Runtime，而不是外部来源或模型：

1. candidate scheduler 给每个 slot attempt 一份 `network_call_allowance`；landing discovery、structured endpoint discovery 与最终 document fetch 共用这份 allowance。自然多 route discovery 会在正文抓取前耗完配额，虽然合同另行声明每 attempt 最多可抓两份文档。
2. `_fetch_and_parse()` 把 `response=None` 的本地预算停止也写入跨 attempt `_document_cache`。issuer attempt 对已合格 URL 形成的 budget-exhausted 结果会污染后续 regulatory attempt；后者即使拥有自己的 allowance，也直接复用失败缓存，不再发 document request。
3. deterministic fixture 没覆盖真实拓扑：round-robin fake 一次调用就直接返回 candidate；document-ceiling fixture 只有单 landing route 且预算充足。它们能证明公平排序和 ceiling 形状，却不能证明多 route discovery 后仍保留正文抓取机会，也不能发现本地预算停止被跨 slot 缓存。

本轮还观察到 Dell/Micron IR landing transport failure、`external_site_search` 未运营、current governed market snapshot 缺失；这些都是后续 P3 必须考虑的运营缺口，但不能解释“已有 229 个 qualified locator 却 0 document request”，因此不是本次零候选的唯一或首要根因。

本结果没有建立以下结论：DeepSeek 能力失败、reranker 失败、公开资料不存在，或“只购买一个 Provider”即可修复当前零正文路径。本轮模型调用为零。

## 止损与下一项

冻结的 no-R4 规则已触发：

- R3 result、captures 与失败评价保持 immutable；
- 不追加网络预算、不放宽 Evidence Gate、不先调 ranking、不重放同一 Attempt；
- 本任务不直接修改 SourceHunter Runtime，也不把缺陷转移给 S2/S3/S4；
- 唯一下一项是零调用 P3。P3 必须先处置 owned scheduler/cache defect，再比较运营 external/site-search、受控动态页、licensed source 与缩小 Internal Alpha source claim；任何新 live 都需要新的产品范围／stop-rule 决策，不能自动产生。

建议 P3 的最小工程候选是：为 document fetch 保留独立且受保护的预算；本地 budget stop 不得进入跨 attempt 成功/失败文档缓存；用本次 R3 captures 增加多 route、跨 slot cache-poison 和至少一次 qualified-document fetch 的自然拓扑回归。该建议尚未获得实施或新 live 权限。

## 收口验证

R3 完成后的首次 focused 回归为 `12 passed / 1 failed`：旧 successor test 把“result 在正式执行前必须不存在”编码成永久不变量。该测试现改为 phase-aware：pre-live clean preflight 继续单独要求 result absent；post-live 普通回归允许 immutable result 存在，但 import runner 前后文件 SHA 必须不变，并核对 R3 identity 与 ranking=false。修复后 focused=`13 passed`、compileall pass，未访问网络或修改 R3 result。

Project OS 负向复核：P3 registered scope=`pass / 0 blocker / 0 contract error`；direct R3、additional live、ranking、MU/NVDA、Experiment B 与 release 全部 blocked。result candidate、terminal 与 quality-evaluation digest 均独立重算通过，版本化结果 secret scan 为零命中。

## 证据

- `configs/releases/fin_ia_0_1_3_s1_08_v3_dell_current_search_r3_result_v1_0.json`
- `configs/releases/fin_ia_0_1_3_s1_08_v3_dell_current_search_r3_source_quality_evaluation_v1_0.json`
- `configs/releases/fin_ia_0_1_3_s1_08_v3_dell_r3_exact_live_issuance_authority_projection_decision_v1_1.json`
- `configs/releases/fin_ia_0_1_3_s1_08_v3_dell_r3_successor_clean_zero_call_preflight_v1_2.json`
- `src/sec_agent/s1_08_candidate_generation_runtime.py`
- `src/sec_agent/s1_08_official_discovery_adapter.py`
