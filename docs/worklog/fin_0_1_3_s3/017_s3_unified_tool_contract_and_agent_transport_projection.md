# S3 统一工具合同与 Agent 协议投影

日期：2026-08-14
状态：`formal_clean_replay_pass / paid_Chat_Responses_pair_complete / both_transport_contracts_pass / content_L1_failed / five_cell_blocked`

## 为什么做

标准 Tool Calls R2 已证明 DeepSeek 能正确读取本单元 Evidence 与 NumericFact，也能识别“销量还是价格驱动收入”的真实补证方向。失败发生在项目合同：模型看到的是全局 facet／metric 和模糊的“concise”，本地却另有 120 字符及 facet→query-family→metric 约束。该状态会让一个 Schema 合法的动作在 Harness 内必然失败。

同时，DeepSeek V4 Pro GA 已提供 Chat Completions、Responses 和 Anthropic Messages 兼容协议。协议选择若继续散落在金融循环里，会把 Provider 协议差异和金融真实性控制面再次耦合。

## 本轮实现

1. 新建唯一 `FinanceToolContract` 编译源。它从当前 Case、Cell、visible gap、Evidence Slot、facet、关系方向、target entity、route family 和 metric route 编译四个工具；Schema、运行时 validator 和 repair surface 不再手工对齐。
2. EvidenceRequest 的数组数量、唯一性和文本长度现在对模型可见；每个 facet 只暴露本 family 可用 metric 和本案允许 target。DELL／MU／NVDA 的 `pricing_and_mix` 均只能指向各自主体。
3. proposal-only 的字段、facet、metric family 和长度错误返回 `rejected_not_executed`，不执行检索、不晋升 Evidence/NumericFact、不关闭 gap；模型只能在原 step／tool／no-progress 预算内修正。跨 Case/Cell、身份、引用、Judgment 和真实性错误仍 hard fail。
4. 新建 provider-neutral Agent 协议层：核心 Runtime 只保留规范化 message、tool definition、tool call 和 tool result；Chat、Responses、Anthropic 只负责外层投影。
5. Responses executor 使用无状态全历史重建；同一 loop 所需的 reasoning output item 只在内存继续传递，保存的 request／response capture 和公开结果均删除私有推理。Provider 静默忽略的 `max_tool_calls`、`parallel_tool_calls` 等字段禁止发送，本地预算仍是唯一权威。
6. Anthropic Messages 当前只有 schema/transcript shadow，dispatch 会以 typed failure 阻止它进入 live。Chat control 与 Responses candidate 共用 `execute_finance_loop_transport_lane`，没有复制第二套金融循环。
7. 新增永久零调用 replay runner 和同输入 Chat/Responses paired runner；后者仍要求 clean proof、fresh authority 和 exact-once Git boundary，不能因代码存在自动执行。

## 当前验证

- 聚焦协议／合同／runner 测试：30 passed；全仓：271 passed。
- active baseline：122 Python／8 frontend／10 Runtime resources，0 forbidden reference；两个新 runner 已进入正式 manifest。
- secret scan：6,526 files，0 finding。
- 本地零调用 R2 replay：旧 R2 proposal 先被安全拒绝，随后一个 facet-compatible repair 被接受并完成 Judgment；总计 4 step／5 receipts，旧错误请求没有成为 proposal、Evidence 或 NumericFact。
- DELL／MU／NVDA 跨案 target mutation 均以 `finance_loop_evidence_request_target_out_of_scope` hard fail。
- 同一 canonical tools／transcript 可投影到 Chat、Responses、Anthropic，并逐协议 round-trip 回同一 canonical contract。
- network/model/provider/embedding calls 均为 0。

绑定干净远端提交 `17bb0c5a...` 的正式 R1 已通过：research input digest=`6505a58e...89b4c`，当前合同 digest=`e4164404...d967a`，旧 R2 合同 digest=`2ead2aa4...e423`，result digest=`fe188a89...d5eb`。正式结果再次证明旧请求被 `rejected_not_executed` 后，合法 repair 可完成 Judgment；4 step／5 receipts，只有 1 个有效 proposal，错误请求 0 晋升。authority 额外绑定当前 Runtime Registry 与 Evidence Pack，避免通过未绑定运行时输入制造伪 clean proof。

formal authority/result 纳入后 secret scan 为 6,528 files／0 finding。

## 尚未证明

- Responses 的真实 DeepSeek Tool Use、长程 continuation 和自然内容质量尚未观察；
- Anthropic live 未资格化；
- DELL 五单元、完整八维报告、qualified-human、S3、Workbench 和 release 均未通过。

## Chat／Responses 同输入真实结果

绑定干净远端提交 `aafd8be3...` 的 paired authority 已签发并 exact-once 执行。Chat control 与 Responses candidate 都在同一 DELL `CELL::value_capture` 输入上完成 5 个 Provider step／6 份 tool receipt：先读取 reviewed Evidence 与 NumericFact，再分别记录 ASP、单位量和 PVM／增量利润三条补证，最后提交一个本地合同有效的 Judgment。两路合计 10 calls，0 retry/fallback/external retrieval/embedding/publication；20 个 capture JSON 中 15 个含 reasoning 形态的 block 均只保存 redacted placeholder，0 私有推理泄漏。

Responses 真实完成了无状态全历史 continuation，故协议可用性已经观察；但没有形成主链晋级理由。Chat 总 token=`74,885`、耗时约 `169s`；Responses 总 token=`102,176`、耗时约 `267s`，分别约为 Chat 的 `1.36x` 与 `1.58x`。Responses 的机制和反方略丰富，但也更强地把多驱动的公司／分部利润改善归因于 AI server cycle；两路都没有通过内容硬门。

paired authority/result、独立内容 assessment 与报告纳入后，仓库 secret scan 为 6,532 files／0 finding；本轮未新增代码，沿用执行前已通过的 271 tests 与 active-baseline 证明。

共同首因不是 wire：当前 judgment 使用的 NumericFact 只显式绑定 FY2027 Q1 与 FY2026 全年，模型却生成“同比上升／正在扩张／毛利压缩”等比较性语言。原始 reviewed 表格含上年同期数据，因此方向可能正确；但当前输出没有 same-cadence relation、公式和期间 lineage，Harness 不能证明它不是 Q1 对 FY 的错误比较。第二个项目缺口是 gap 提示允许行业出货数据，而编译后的请求只允许 10-K／10-Q／8-K；模型无法看到或选择 source class，导致“请求行业数据、实际只能走 SEC route”。

因此正式八维评分没有签发：FIN 0.1.3 要求先过 L1/L2。Chat／Responses 只保留 diagnostic-only 节点分 `17/24` 与 `18/24`，不能冒充产品分数。Chat 继续作为 provisional primary，Responses 降为已跑通的 shadow/candidate，Anthropic 仍禁止 live；五单元不授权。

## 下一门

只允许一个零模型结构包：补 same-cadence comparable NumericFact／relation trace；让比较词绑定 relation/direction 并本地验证；把 allowed source class 与 route availability 编入 EvidenceRequest；重放本轮 capture 并覆盖 DELL/MU/NVDA 错期间、错来源和因果越界 mutation。通过后最多签发一条 Chat 单单元复验，不再做第二组协议对照；复验过 L1 且保留研究增益后，才重新决定五单元。
