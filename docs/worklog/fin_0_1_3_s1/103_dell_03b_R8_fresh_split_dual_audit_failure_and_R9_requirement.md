# S1 工作记录 103：DELL 03B R8 fresh split dual-audit 失败与 R9 要求

日期：2026-08-27

状态：`R8 immutable integrity PASS_BOUNDED / general 03B qualification FAIL / R17 report quality FAIL_GATE_OPEN_NOT_ASSESSABLE / same-stage non-overwriting R9 required`

## 1. 审计身份与监督方式

审计对象为 result commit `aa58a503d5d1416ff2d778808875667b904e6ce4`，其 authority=`f4c3c629c789fa8d61deda2f4375eb887f5f8ce4`、implementation=`a9403e327e2de740015d63223ee6fbeace0f93a6`。固定清单 commit=`4db3c4bf74e5075201997ed61340aa8f4bef67a3`，manifest digest=`024d0dc0ade945ac4df7f0bb08d5d2229fc585c697f3c6a2f87985482d46491f`。

首名 fresh fork-none 双审计 reviewer 在 Phase A 后连续未按 checkpoint 合同回报，被主 Agent 中断。其已报告的哈希/拓扑检查只作为辅助证据，不作为最终唯一 reviewer 结论。随后审计拆为两名全新、作者分离、只读 reviewer：一名只审 R8 工程/语义，一名只审 R17 研报质量。

最终审计 artifact：

- ref=`configs/audits/fin_ia_0_1_3_commit_aa58a503_dell_03b_r8_fresh_split_dual_audit_fail_v1_0.json`
- digest=`d8f2176e3f0972976ed601c5f0d261617e372df2c3a8de88097f18ed3e5cb612`
- SHA=`14745de67c075f74bdf9ef1bfc3e70247b61ae2418fc7d79b7b8d61b00cd7ce4`

两名最终 reviewer 均为零写入、零 commit/push、零网络/Provider/模型/embedding/4B/reranker/external/formal attempt、零 targeted pytest、零全仓 pytest。工程 reviewer 的 C 阶段在完成约定检查但未及时回报后被中断；恢复时只允许报告内存中已完成结果，不再执行命令或读文件。超出已完成证据的两项明确记为 `NOT_ASSESSABLE`。

## 2. R8 保留的通过事实

Phase A=`PASS_BOUNDED`：

- fixed engineering bundle `15/15`、policy inputs `34/34`、implementation bindings `21/21` 的 SHA/size 通过；implementation→authority→result 的 parent/tree/changed paths 精确。
- policy、receipt、raw capture、private、public 自摘要和互链通过；raw execution SHA=`0e9e4456...9f7458`。
- private 重新投影 public 后 dict 与 canonical bytes 精确相等；attempt 目录只有 receipt/raw/full_result，terminal failure receipt 不存在。
- 5 requests、1 local 0.6B batch、aggregate union/final=`338/80`；每 request `96/16` unique 且 rank 连续。network/model/provider/external/4B/reranker/retry/mutation/Candidate/Evidence/gap closure 均为 0。
- 实际 route 保留为 bounded observation：ASP=`1/1/1/1 rank2`、supplier=`3/3/2/1 rank2`，capacity/yield/HBM/units 均=`0/0/0/0`；coverage/local repair=`0/0`、external=`4`、4B/reranker eligible=`0/0`。

冻结面也通过：R7 negatives `63/63` 无 false complete，R8 fresh negatives `8/8`，6/6 fresh positives、选定 11/11 R7 positives，冻结 `$150 support + $15 hardware` 攻击正确绑定 `$15`；15/15 public attacks 被拒绝、3/3 valid controls 被接受。R8 public privacy 因此为 `PASS_BOUNDED`。

这些通过项证明当前正式执行完整、当前固定用例与 public threat contract 有效；不能证明通用 predicate-frame、scope 或 anchor 资格。

## 3. R8 三项新 P2

### P2-1：无逗号并列谓词仍可跨事件拼角色

`Dell shipped marketing materials and NVIDIA delivered four PowerEdge XE9680 AI servers in Q1 2026.` 被当成一个 frame 并 complete：Dell/shipped 来自 marketing event，quantity/product/period 来自 NVIDIA server event。只去掉 R7 冻结反例中的逗号即可绕过。

同族还包括 financing + capacity、HBM→HP + Dell earnings。根因位于 `dell_report_predicate_frames_r8.py:106-109,325-374`：coordinator boundary 依赖标点，未拆分后 role extractor 扫描整个 record。

R9 必须做 predicate-aware coordination split，不能再以是否存在 comma 决定事件边界；每个 required role 必须只从 owning frame 提取。

### P2-2：epistemic/reporting/revocation scope 仍非合同完备

以下都错误成为 `complete/affirmative/actual/active/direct_assertion`：

- `...; this partnership was later suspended.`
- `Dell discontinued its partnership ...`
- `Dell is exploring a partnership ...`
- `According to an analyst, Dell partnered ...`

根因位于 `:131-169,343-385,535-692`：coreference、状态、speculation 和 leading attribution 仍是枚举 grammar，缺 demonstrative revocation、exploring/considering 与 leading report owner。

R9 必须把 frame-local semantic state 设计为可组合状态机，覆盖 assertion owner、actuality、modality、status/revocation 与 coreference，不得只追加四个词。

### P2-3：price→product anchor locality 仍可绕过

`Dell quoted support for USD 150 and PowerEdge XE9680 hardware for USD 15.` 被 complete 且 hardware price 错绑 `$150`；`Dell quoted a support package for USD 150 for PowerEdge XE9680 hardware.` 的单价 support 也被晋升为 hardware price。

根因位于 `:851-879`：多价 heuristic 只看当前价至下一价的右侧词面；单价不做 role locality。

R9 必须让 price argument span 绑定 hardware object span；support/freight/service 等非硬件 role 必须排除。多候选无法唯一绑定时返回 typed ambiguity/partial，不能挑第一项。

## 4. 两项未评估边界

- 实际 source 与 compiled complete rows 的 `accepted_frame_digest` 有差异；审计停止前没有完成逐文本 transformation binding，因此不能判为合法表示变换或 provenance gap。
- 六个 fresh＋十一 selected controls 以外的广义同义词 recall 不外推。

R9 计划必须把 source→compiled frame identity/provenance 作为独立验收项，并定义受审 positive recall 样本边界。

## 5. R17 研报质量独立结论

R17=`FAIL_GATE / OPEN_NOT_ASSESSABLE`，open finding=`P0/P1/P2/P3=0/1/2/1`：

- fixed report bundle `14/14` identity/hash 通过；实际 reader report 为 21,118 chars、59 次 EV／18 unique、25 个 `[Sources:]`，但 reader URL=0，source/citation appendix=false。
- 底层 DELL pack 的 55/55 source_text、digest、绝对 HTTP(S) URL 与 Evidence→material ref 都可解析；报告 18 个 EV 在 pack 中 exact occurrence=0，authority rows 又无 source_record_id/material_ref/url/quote/locator。因此 claim→原文 passage/URL 的语义支持是 `NOT_ASSESSABLE`，不是 PASS。
- crosswalk=`14 pack / 9 dynamic / 4 writer groups / 10 writer refs / 4 S2 bridges`。R17 只有 4 groups/10 GAP refs，无 crosswalk digest/binding，遗漏 price-in、scenario/sensitivity、supplier-capacity read-through、valuation basis。
- WWC=`0/6 operational`，6 条 receipt 全部 EV=0/GAP=0；owner/source/window/threshold/response 不完整，两项 method threshold 仍 pending/null。
- material numeric/公式、company/segment/product use boundary 与 strongest counter-thesis 均通过或 bounded pass；但 72 fact items 只有 36 unique，WWC 在 section/array 重复。
- 02B=`8 requests / 18 items / 16 human-required / 0 decisions`；formal 8D=`NOT_ASSESSABLE, score=null`。

因此“底层有 55 条带 URL 的材料”不等于“上一版研报信源问题已解决”。真正缺口是 EV/claim→原文 passage/locator 的一对一合同与 reader-visible source appendix，随后才是 crosswalk、WWC 和编辑质量。

## 6. 风险分层测试与审计效率

本轮未重复作者的唯一 T4 证据 `1823 passed, 2 skipped in 508.75s`，也没有跑 targeted pytest；哈希、投影、内存反例与固定报告包已足以证明 material failure。生产/测试/shared validator 未变化，因此原 T4 receipt 未失效。

审计的耗时问题由监督规则处理，而不是靠更多测试掩盖：

1. 工程与报告拆成独立固定包，可并行、可单独停；
2. 每阶段必须 checkpoint；连续不回报即中断；
3. 中断后只报告已完成证据，未完成写 `NOT_ASSESSABLE`；
4. reviewer 不重复 full pytest，只有 production/test/shared seam 改变或影响面未知才 fail-up；
5. R9 要为每个审计 phase 写正向 command/wall budget，不能只写“禁止全仓”。

## 7. 门禁与下一合法动作

Overall=`FAIL`；R8 new=`0/0/3/0`，R17 open=`0/1/2/1`，combined=`0/1/5/1`。R8 不覆盖、不重试。

下一合法动作是先写 non-overwriting R9 program-level execution plan，拆出：

1. punctuation-independent coordination/frame split；
2. frame-local epistemic/reporting/revocation state machine；
3. product-role-bound price anchor 与 ambiguity；
4. source→compiled frame provenance seal；
5. 冻结旧面、同族 mutation、positive recall 与 bounded audit；
6. 风险分层测试与一次性 freeze receipt 复用规则。

R9 fresh independent pass 前，03C external、4B mixed embedding、reranker、CandidateDecision、Evidence/NumericFact promotion、gap closure、Pack/Readiness、S2、R17 successor、qualified-human、product/publication/release 全保持 false。R17 修复必须保留在后续 source/Evidence/S2/report 链，不能混入 R9 或被 R9 成功自动解冻。
