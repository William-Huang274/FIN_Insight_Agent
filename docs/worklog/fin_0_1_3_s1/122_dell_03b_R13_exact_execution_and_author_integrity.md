# S1 工作记录 122：DELL 03B R13 唯一零调用执行与作者完整性复证

日期：2026-08-28

状态：`R13 exact zero-new-call execution success / immutable R12 raw reuse successor preserved / exact saved-formal replay pass / reviewed-result freeze materialized / case-correct manifest and fresh author-separated dual audit pending`

## 1. 冻结身份与唯一权限

- implementation commit/tree=`11caf389fdea3c96554dd4176c571c1bf12e14be` / `382f02cae8c0b6545bdfa7d08a00c3e79c5700c9`；最终 T1/T2/T3=`162/292/140`，真实全语料 preview digest=`5cd4fe82a987f571cf8844649faa1579c73a86b69d82a6c2f176951c17ed523e`。
- policy-only authority commit/tree=`492218a9237678f2d2cf63b6a77f1249dc9f1f55` / `54e598569bf9d3aec1a5104f6c6669ea26669f60`；唯一父提交精确为 implementation，唯一 changed path 为 v2.2 policy，formal 启动时 `HEAD==upstream` 且工作树 clean。
- policy digest/SHA=`cc84d3af62baccb71cb9a21422c11021c97e13ea1ed6e5e58c2879ad36a61427` / `ae519358edd9892abcfe05ae8486e59e9b6d571433b9d5f86273e3723175b0cb`；15/15 输入、41/41 implementation、R17 14/14 carry-forward 文件与 task-specific `TokenBudgetBasis` 全部通过；policy专项=`9 passed`。
- attempt=`dell-rsq-03b-internal-chain-r13`；receipt time=`2026-08-27T23:01:35+00:00`。执行前 canonical attempt directory 与 public v2.2 均不存在，D盘 free bytes=`691,515,392`，高于 `536,870,912` 下限。
- GitHub transport继续使用仓库级 `http.https://github.com.proxy=http://127.0.0.1:6696`。AtlasCore实际监听在 wildcard `0.0.0.0/[::]:6696`；因此只按 `LocalAddress=127.0.0.1` 统计 listener会误报0。默认 `git ls-remote` 与 implementation／authority 两次 non-force push均成功；formal本身禁止网络。

## 2. 正式执行与 raw lineage

R13没有重新执行检索、0.6B embedding或任何模型。它以 R12 为直接 predecessor，精确复用 immutable R12 raw successor中的 canonical raw execution SHA=`0e9e4456ba75ecd07bc2e3bd6d5deddafc1972ba19700b029b2e6793e99f7458`：5个 frozen request、跨请求去重 `338 union / 80 final`，再以 R13 compiler扫描 `1,888 source / 34,199 compiled objects`，形成 target-union occurrence=`794`。R11只作为 R12 capture内部的transitive candidate-generation来源，不是 R13 的直接输入或实现API。

R13 raw successor先于compile写入，schema=`fin_ia_dell_report_internal_chain_raw_reuse_capture_v2_0`。它绑定 R12 raw capture ref/SHA/digest、R12 attempt、冻结 request/union/final数量及candidate-generation equivalence proof；写盘后必须重读并重新验证才允许compile。query payload、source/object inventory、embedding/vector、candidate union与raw rank均不变，R13改动只发生在 post-candidate semantic compilation、persisted reconciliation与public projection。

R13新增 `local embedding/model/provider/generation/network/external/4B/reranker/retry/current mutation/Candidate/Evidence/gap closure=0`。canonical R11曾执行的一次0.6B embedding batch只作为不可变transitive lineage保留，没有在R12或R13重跑。五个request的`material_set_complete`只证明execution contract完整，不表示六个研究target都有Evidence。

## 3. 正式结果

| target | complete source/compiled/union/final | best final rank | partial source/compiled | active external route |
|---|---:|---:|---:|---|
| Dell company/bounded configuration price | 0/0/0/0 | — | 844/951 | 2 exact IDs，必须继续03C |
| capacity release | 0/0/0/0 | — | 381/347 | 2 exact IDs，必须继续03C |
| capacity utilization/yield | 0/0/0/0 | — | 5/8 | 3 exact IDs，必须继续03C |
| HBM→Dell bridge | 0/0/0/0 | — | 16/18 | 3 exact IDs，必须继续03C |
| supplier→Dell relationship | 3/3/2/1 | 2 | 71/65 | 当前complete；active external IDs为空 |
| Dell company-period physical units | 0/0/0/0 | — | 332/295 | 2 exact IDs，必须继续03C |

ASP 的两个 exact ID 仍为 `DELL-RSQ-03A-TARGET-ASP::official_issuer_regulator` 与 `DELL-RSQ-03A-TARGET-ASP::product_procurement_deployment`。五个external-required target的active route set均非空、可由冻结03A-R2 registry解析；supplier的恒常registry identity仍在，但没有误开external execution。

六target共`1,596`条transformation binding：`1,273 accepted / 323 failed`；unbound partial=`379`。所有六项`complete_transformation_coverage_pass=true`；failed-complete、unbound-complete、compiled-complete-without-source、proof-rebind failure和local source→object repair均为0。R13相对R12只收紧5条supplier partial binding；complete family/count/rank、route与downstream disposition不变。

作者结果复证没有只信summary：逐target从落盘的private source packages、compiled packages、coverage gaps与validated binding rows重算whole summary，6/6 exact；重新调用public projector得到的完整public dict与落盘public完全相等。323个failed binding和379个unbound partial是保留的结构边界，不得冒充Evidence或proved public-information gap。

## 4. Artifact、projection与replay完整性

- receipt digest/SHA=`19d10cb17c748fbd8e69481706695520db24fd48d737592c6c05dfc05bcab346` / `536a06f9d9cb4cc39fe5a8a5c3884317246a56500740b5d79771b7557a87b3ab`。
- raw successor digest/file SHA=`45bc59c65ea95bb3358ad9ba108d730a224d8380d92f0e0f32381700185034a6` / `5c9cece69e9fc5ab82aec790b4517a667ea6f8cb96ed05e2c80c9237e45674d8`；其内raw execution与R12 dict完全相等，SHA保持`0e9e4456...f7458`。
- private digest/SHA=`0d58e3ead80227df34c111b25882d8a055a47b4515d0eb9e1c24aea2ac68a055` / `9502e4988116253253c9b64c10416dcf08d9fdee2e646a32c426ac65e090e94c`。
- public digest/SHA=`d186be686d9293d4ebbb8e6d698cd223429ba65433df0a89f44f7b32224dbe8d` / `b841be686e52c3927accfe60186ea4584f4c1d61c2ef83fc3ee2455137546d63`；其private digest/SHA、policy digest与raw SHA精确反向绑定。
- receipt/raw/private/public四份self-digest独立复算一致；terminal failure absent；saved-formal replay通过`private_dict_and_bytes_equal=true`，没有再次消费attempt或发生调用。

formal与saved replay各约30秒。formal后R13 direct regression=`162 passed in 56.52s`；最终Project OS=`82 passed in 12.15s`，最后一次纯文档复查仍为`82 passed in 10.42s`；8份JSONL／`1,389`行全部解析，active baseline=`213 Python / 8 frontend / 5 detectors / 28 resources / 0 forbidden`，repository secret scan=`8,247 files / 0 findings`，public self-digest/SHA、`py_compile`、`pyflakes`与diff check全部通过。结果阶段只新增public result、model-run、工作记录和Project OS，没有修改shared/active runtime、dependency、pytest配置或current product pointer，T4 trigger=false。

## 5. 研究、模型与研报质量边界

本次formal只证明R13作者身份、R12 raw复用、已知语义攻击、持久化whole-summary重算和public projection闭环；不是fresh independent engineering PASS。它没有执行五条external source ladder，也没有产生changed candidate pool，因此0.6B/4B mixed embedding shadow与条件reranker仍未运行；CandidateDecision、Evidence admission、02B human decisions、Pack/Readiness、S2、S3与新报告都未开始。

R17固定14文件继续为`FAIL_GATE_OPEN_NOT_ASSESSABLE (0/1/2/1)`：reader URL=`0`、18个report EV exact passage/locator/URL binding=`0/18`、crosswalk未绑定、operational WWC=`0/6`、Facts=`72/36 unique`、formal 8D=null、qualified-human=`0/16`。fresh reviewer必须分别签发R13 engineering/Evidence-pipeline verdict与R17 report-source/content-quality carry-forward verdict；工程零finding不能替代研报质量或qualified-human验收。

## 6. 下一合法顺序

1. 冻结并推送public v2.2、本记录、model-run与Project OS，形成immutable reviewed-result commit。
2. 只从Git case-preserving `diff-tree`原始路径生成non-overwriting fixed audit manifest；严格校验implementation→authority→result提交链、tree、逐文件SHA与exact case-sensitive changed paths，然后提交并推送。
3. 启动全新`fork_turns=none`、作者分离、只读reviewer；禁止formal/model/network/写入，默认不跑pytest，先审R13工程与R17研报质量。只有具体material suspicion才做最小in-memory probe。
4. 只有fresh R13 engineering independent PASS后，才按五个exact target执行residual 03C外源梯子；随后在真实changed pool上做0.6B/4B mixed embedding shadow，并仅在存在同池eligible候选时启用reranker。
5. 再完成CandidateDecision/Evidence/qualified-human admission、Pack/Readiness、S2 `units/share→ASP/mix→PVM→产品利润/营运资金`、受影响S3、不覆盖R17的报告successor、reader citation appendix，以及工程、研报质量和qualified-human三重验收。

在第3步工程独立通过前，03B independent、03C、4B、reranker、G2/G3、S1/S2/S3、report quality、formal 8D、qualified-human、product/publication/release全部false。
