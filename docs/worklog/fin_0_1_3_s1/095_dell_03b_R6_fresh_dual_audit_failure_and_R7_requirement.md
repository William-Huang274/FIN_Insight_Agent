# S1 工作记录 095：DELL 03B R6 fresh dual-audit FAIL 与 R7 要求

日期：2026-08-26

状态：`R6 immutable execution/integrity/actual-route observations retained / general proposition-anchor-public-content qualification FAIL / R17 report-quality gate remains FAIL / same-stage non-overwriting R7 required`

## 1. Reviewer 身份与总判定

全新的 fork-none、作者分离、只读 reviewer 对 immutable result commit `9ca3c83087644496c08ddcc43b5a7d871efa52ef` 完成 R6 工程、语义、anchor、privacy、route 与 R17 研报质量双审计。Reviewer 没有写仓库、联网、调用 Provider、生成模型、embedding、4B、reranker 或 external capture，也没有委派其他 agent。

Overall=`FAIL`：

- R6 新 finding：`P0/P1/P2/P3=0/0/3/0`。
- R17 open finding：`0/1/2/1`。
- combined：`0/1/5/1`。
- R6 integrity=`PASS`；当前 public cleanliness=`PASS_BOUNDED`；actual route=`PASS_BOUNDED_FOR_ACTUAL_IMMUTABLE_EXECUTION`；general semantic/anchor/privacy qualification=`FAIL`；03B independent pass=false。

审计 artifact：

`configs/audits/fin_ia_0_1_3_commit_9ca3c830_dell_03b_r6_fresh_dual_audit_fail_v1_0.json`

self-digest=`11935696805f386364661f95c0ab1ae3076f86f5edc562d8d58f339e39516342`。

## 2. 通过并保留的 immutable R6 事实

- result/authority/implementation Git topology、24/24 bound inputs、14/14 implementation bindings、policy/receipt/private/public self-digest、private link 与 raw-execution SHA 全部独立通过。
- 5 个唯一 request；每个精确 96 union／16 final 且 rank 唯一连续；唯一 local 0.6B batch；所有禁止的 network/provider/generation/external/4B/reranker/retry/mutation/promotion/closure counter 为 0。
- Reviewer 用保存的 raw execution 做零模型全量 deterministic recompile：1,888 sources／34,199 objects，耗时 `126.711s`；private exact equal、public exact reprojection。
- 当前 immutable public 没有实际泄漏；allowlist 的 unknown-key、literal locator 与 absolute-path controls 在已测路径有效。
- 当前 actual observations 可保留：ASP=`2/2/2/2` rank 15、reranker challenger eligible；supplier=`2/2/2/1` rank 2；capacity/yield/HBM/units 均=`0/0/0/0`；coverage gaps=0；external candidates=4；target-specific 4B eligible=0。

以上均为 bounded facts，不等于通用 classifier、anchor compiler、public projector、03B、S1 或研报通过，也不授予任何后续执行权限。

## 3. R6-P2-1：仍未形成单一命题内的 typed role binding

R6 把 clause 切分和部分 guard 包装成 typed 结构，但完成判定仍主要依赖枚举正则，并可把 package 内不同 clause/sentence 的组命中做 existential union。Fresh reviewer 复现的 false complete 包括：传闻、否认、暂停、能力态、零分配、撤销分配、预测/撤回/模拟 yield、橙汁 yield 串入 HBM、客户转述 Dell 出货、Dell 否认出货、can quote、alleged/withdrawn quote，以及 HPE 的价格与 Dell 的数量跨句拼接。

同时，以下真实同义正例会 false negative：`NVIDIA is Dell's supplier`、capacity `earmarked for Dell`、PowerEdge `incorporated HBM`、yield `achieved`、Dell `sent` servers、Dell `sold` servers for a price。

这继续归属 `RC-S1-079`。R7 不能再追加零散 regex；必须使同一个 typed proposition 同时绑定 actor/subject、predicate、object/recipient、polarity、modality、status/revocation、reported-speech owner、quantity/measure/currency、product、period 和 process。任一必要槽不在同一命题内，complete 必须 fail-close；不同 clause/sentence 不得做完成组并集。

## 4. R6-P2-2：material anchors 仍未绑定到命题角色

Reviewer 复现了产品码、期间和货币语法的不一致：部分 H100 分隔/复数形式丢失或泄漏裸数字，FY apostrophe 与四位 fiscal year 不等价，`USD$15`、`15 dollars`、`$15m` 不能稳定归一；`about`/`at most` 又丢失限定语义。

更重要的是，anchor 仍可能从整段非目标文本收集：无关 support/freight 的 `$15` 可制造假覆盖或假 gap，无关 HP/B200/100 units 可污染 Dell/H100 命题，改变命题价格为 `$150` 再附带无关 `$15` 可得到 false zero gap。

这继续归属 `RC-S1-080`。R7 必须只从被接受的同一个 proposition role 输出 role-labeled anchors，例如 `price/currency`、`quantity`、`product`、`fiscal_period`、`process/yield`；实体内部数字、第三方数字与无关从句不得进入目标 anchor set。等价语法必须归一，限定和单位必须保留。

## 5. R6-P2-3：public key allowlist 已有，但字段内容仍不 fail-close

R6 的递归 key allowlist 阻止了未知 key、literal locator 和 absolute Windows path；当前 immutable public 也没有泄漏。但 reviewer 在允许的字符串字段中复现了 credential-like assignment、secret-like/high-entropy payload、secret-like identifier/binding ref、percent-encoded locator 和 parent traversal 通过投影。

这继续归属 `RC-S0-105`。R7 必须增加 field-typed content validator：canonical ref/identifier 使用严格 grammar；文本字段拒绝 credential assignment 与 secret-like/high-entropy token；验证前先 percent-decode；拒绝相对 parent traversal、backslash traversal、absolute/local/network locator。合法金融文本中的货币值不能被误杀。

## 6. R17 研报质量仍未通过

- P1 citation/source appendix：39 rendering receipts、42 unique claim refs、18 EV、10 gaps、32 presentation authorities 在 repo 内可解析，但读者侧 URL=0、source appendix=false，且 2 个事实型顶层 WWC 无 source block。
- P2 crosswalk：R17 早于 accepted crosswalk v1.2，绑定数=0；14 Pack gaps、9 dynamic gaps、4 Writer groups、10 Writer refs、4 S2 bridges 均未被消费，price-in、scenario/sensitivity、supplier-capacity read-through、valuation basis 等 facet 未进入 R17。
- P2 WWC：6 项 operational=`0/6`，缺 metric、direction、frozen window、threshold、threshold authority、owner、evidence route 和 response route；method parameter frozen=0、pending=2。
- P3 density：20,574 chars、71 fact occurrences、32 unique fact strings；inventory 重复 5 次，AI revenue/orders/GM/OM 各重复 4 次，WWC 重复展示。
- 正向边界保留：24 numeric presentations 与 9 relations 可重算；margin bridge `-3.3680pp + 6.7238pp = +3.3557pp`；FCF 明确为 deterministic non-GAAP；PVM/ASP/units/product/working-capital 未被虚假关闭。
- 02B 仍为 8 requests、18 items、16 human-required、4 blocked requests／8 blocked items、qualified-human decisions=0；formal 8D 不成立。Fresh reviewer 不是 qualified human。

R17 修复必须作为单独的 report-quality successor；R7 只能修 owning-stage S1 语义、anchor 与 projection。R7 成功也不会自动修复信源、S2、Writer、citation、WWC、密度或 human gate。

## 7. Authority 与下一合法动作

1. R6 不覆盖、不重试；唯一执行、保存 raw、private/public bytes 与 bounded actual observations 均保持不可变。
2. 先写 R7 program-level execution plan，将三项 owning-stage root cause 拆成需求票、依赖、输入输出、工程门、模型环节质量门、研报边界、adversarial/positive controls、停止条件与 authority transition。
3. 再开 same-stage non-overwriting R7：新 module/runner/tests/schema/policy/attempt/result；不得在 R6 上原地修补或追认。
4. R7 exact attempt 前必须先做全部审计攻击回归、全 corpus zero-call preview、完整仓库门与 clean implementation/policy commit topology。
5. R7 immutable result 完成后，必须换另一个全新 fork-none、作者分离、只读 reviewer，继续做 R7 工程审计和 R17 研报质量双审计。
6. 03C、4B、reranker、CandidateDecision、Evidence、NumericFact、gap closure、G2/G3、S1/S2/S3、新研报、产品、publication 与 release 继续 false。

## 8. 审计记录固化门

- Project OS preflight=`82 passed`。
- config JSON=`1,149`；Project OS JSONL=`8 files / 1,284 rows`，全部可解析。
- audit self-digest 重算一致；artifact SHA-256=`bc2a9299774de27d366472f9fad8e8cf982d5dee5eb9119c19ea8c32ea7b4dad`。
- repository secret scan=`8,143 files / 0 findings`；`git diff --check` 通过。
