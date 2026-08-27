# S1 工作记录 111：DELL 03B R10 fresh 双审计失败与 R11 要求

日期：2026-08-27

状态：`R10 identity/route PASS_BOUNDED / engineering FAIL P0-P1-P2-P3=0-0-2-0 / R17 FAIL_GATE_OPEN_NOT_ASSESSABLE 0-1-2-1 / same-stage non-overwriting R11 required`

## 1. 审计身份与只读边界

fresh `fork_turns=none` reviewer 从固定 manifest 重建结论，没有继承作者对话。其核对 engineering 20 项与 R17 14 项，共 `34/34` SHA/byte size；manifest self-digest=`37ec7a1794138bb9fcbb8270f3a8e43acb16f349389e588b06eb82c5ea233377`，file SHA=`618df627dc1134ee4b049ce744fb9801571f55a404cfc650b712b520d3ef3fc7`。

审计起止工作树 clean/synced；implementation→authority→result→manifest 为 `70015d11→d3ab2456→b4a04fec→06604f58`。全程 0 writes/commits/pushes、0 formal、0 model/provider/network/external/embedding/4B/reranker、0 targeted/full pytest。

## 2. 通过面：只签 bounded integrity

- policy self-digest、14/14 bound inputs、29/29 implementation hashes通过。
- attempt目录精确只有 receipt/raw/private，terminal failure absent；receipt/raw/private/public自摘要和链接闭合。
- 5 requests、1本地0.6B batch、每项96/16、aggregate 338/80、全部 forbidden counters=0。
- saved-formal replay字典与canonical bytes全等，private digest=`46517a69…54c2`。
- R9 Acme/Supermicro、普通未见单/多词 owner、真 shared-subject offset-zero、compound/shared subject、bare `later` 均通过。
- R10实际 ASP=`0/0/0/0`、supplier=`3/3/2/1 rank2`；六target complete transformation coverage全真；public attacks/valid controls=`14/14, 3/3`。

这些只能给 identity/integrity/actual route `PASS_BOUNDED`，不能抵消语义 finding。

## 3. P2-1：clause ownership 仍非真正开放词

责任路径：`src/retrieval/dell_report_predicate_frames_r10.py:356,374,460-484,499-517`。

最早原因：R10把“第一个 predicate-hint 前的非空 prefix”直接当显式 owner。它没有分别证明 shared-subject continuation 与 independent owner：

- `NVIDIA provides GPUs and in Q2 ships them to Dell.` 把 `in q2` 当 owner，错误拆成两个 partial；`later in Q2`、`under the agreement`同样 false split，丢失原本完整 supplier relation。
- `Dell quoted support for USD 150 and Rose Systems offered PowerEdge XE9680 hardware for USD 15.` 中 `Rose`与 predicate `rose`撞词，first predicate落在offset 0，R10 `no_split`，跨事件错误生成 complete ASP。
- 显式右 owner 使用未见 predicate `cost` 时也可 false merge。

因此“去掉公司白名单”不等于开放词 clause parsing；主体和谓词仍受首个有限 hint 位置控制。

## 4. P2-2：product-price relation 仍由共现 fallback 伪造

责任路径：`src/retrieval/dell_report_predicate_frames_r10.py:1204-1212,1242-1304,1456-1474,1601`；传播路径：`src/retrieval/dell_report_frame_transformation_r10.py:148-168`。

当没有显式 attachment 时，`single_typed_object_in_argument_group` 把“组内只有一个已识别 hardware object”与price的共现直接转成 `hardware_product_price`。以下均被错误接受：

- `PowerEdge XE9680 hardware under a global contract amount of USD 15`
- `... with maintenance costing USD 15`
- `... with a delivery fee of USD 15`
- `... under a lease payment of USD 15`

精确词面 `service/freight/financing` controls 会拒绝，反而证明 admission 依赖封闭排除词表，不是肯定式关系证明。错误 relation 随后进入 semantic signature 和 transformation mapping，使下游无法识别其最早伪造点。

## 5. R17 与产品边界

R17 14/14 文件 byte-identical，继续为 `FAIL_GATE_OPEN_NOT_ASSESSABLE (0/1/2/1)`：

- 59 EV occurrences / 18 unique，reader URL=0、无source appendix、claim→passage/title/issuer/date/period/locator/stable URL=`0/18`；source pack虽有55/55 passage+URL，但report EV与pack source ID交集为0/18。
- 14/9/4/10 crosswalk及4个S2 gap未被R17 digest-bound；`price_in`、scenario/sensitivity、supplier-capacity、valuation basis缺失。
- 6个WWC没有完整 trigger/direction/horizon/threshold/observable/owner/response route；method register=0 frozen/2 pending。
- frozen重复口径=72 Facts/36 unique；fresh简单复数=71/32，均证明material repetition。
- formal 8D=null；8 requests/18 items/16 human-required/0 decisions，qualified-human=false。

## 6. 决定

R10 engineering=`FAIL`、03B independent=false。R10 implementation/policy/attempt/raw/private/public/result/manifest/audit全部保持不可变。不得把 formal成功、ASP纠偏或transformation coverage写成独立通过。

下一合法阶段仅为同一 S1/03B 的 non-overwriting R11：建立“shared continuation proof / explicit owner proof / ambiguous barrier” clause-ownership合同，并删除共现 fallback、要求 affirmative product↔price attachment proof。R11 fresh pass前，五条外源、4B/reranker、CandidateDecision、Evidence、Pack/Readiness、S2/S3、报告 successor、产品/publication/release全部false。

审计失败与R11计划物化门：audit self-digest/manifest cross-binding通过；Project OS=`82 passed in 17.10s`；8份JSONL/`1,340`行解析通过；repository secret scan=`8,203 files / 0 findings`；diff check通过。未运行全仓pytest。
