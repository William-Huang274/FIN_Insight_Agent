# S1 工作记录 089：DELL 03B R4 fresh dual-audit failure 与 R5 要求

日期：2026-08-26

状态：`R4 immutable / execution-integrity-privacy PASS_BOUNDED / semantic-material-route FAIL / R17 FAIL_NOT_FORMALLY_ASSESSABLE / same-stage R5 required`

## 1. 最终结论

全新、无上下文继承、作者分离、只读 reviewer 审计 immutable commit `3629272c9bf0717a755983d9b698041c25241056`。R4 新 finding 为 `P0/P1/P2/P3=0/1/1/0`；历史 R17 open finding 独立保持 `0/1/2/1`，合计为 `0/2/3/1`。Reviewer 起止工作树 clean，仓库写入、网络、source acquisition、Provider、生成、embedding、4B 与 reranker 调用全部为 0；它不是 qualified human，02B 仍是 `0/16`。

R4 的 exact Git、attempt、execution、integrity、privacy、R39 append-only repair、frozen v1 boundary 和实际六目标结果均为 `PASS_BOUNDED`。失败的是通用 semantic/material-coverage/route qualification；因此 `03B independent pass=false`，R4 不改写、不重跑，所有 03C/4B/reranker/Evidence/S2/report/product 权限继续 false。

## 2. 独立通过的边界

- HEAD/tree/branch/upstream 精确为 `3629272c...41056`／`65b94061...54ea1`／`codex/fin013-dell-s1-s2-product-bridge`，ahead/behind=`0/0`。
- HEAD 的唯一父提交为 authority `aa61687f...43d74`；authority 的唯一父提交为 implementation `14f11b8c...51789a`，且 authority 只改 R4 policy。
- 14 个 bound input、10 个 implementation binding 全部匹配；5 个唯一 request、5 个唯一 query、1 个本地 query batch；每 request 精确 96 union、16 final 和完整 rank。
- policy/public/private/receipt self-digest、raw execution SHA/validator、private exact recompile、public exact reprojection 与 private link 全部通过。
- R39 source=1,888、objects=34,199、只追加 1 object；frozen v1 compiler SHA 匹配，修复 family 从 `1 canonical gap / 2 occurrences` 变为 `0/0`。
- 实际 R4 结果可重放：ASP=`2/2/2/2` rank 15；supplier=`2/2/2/1` rank 2；其余四 target=`0/0/0/0`；external candidate=4、reranker candidate=1、target-specific 4B=0，但都不授予执行权。

## 3. P1：位置先去重与伪 exact anchor

`dell_report_internal_chain_ceiling_r4.py` 在给 source unit 编号前先对 normalized sentence 做全局去重。审计构造一个 price/configuration pair，中间放 20 条完全相同的 boilerplate：真实相隔 22 units，却在去重后压成 span 3 并被判 ASP complete；把 20 条改成不同文本则正确保持 partial。这违反 `absolute_corpus_positions_not_selected_only_positions`。

Material coverage 另用 raw substring 比较 numeric/time anchor。source 的 `15` 会被 compiled 的 `150` 视为覆盖；`16` 则仍报 gap。产品码 `H100` 也可能产生裸数字 fingerprint。这不是命名问题，而会改变 `source_complete`、coverage、local repair、external route 与 reranker eligibility。

R5 必须先为每个 raw occurrence 冻结位置，再做 display/canonical-family dedup；numeric/time anchor 必须是 typed、token-exact、单位和期间感知的标准化相等，不能再用 substring。

## 4. P2：polarity、direction、process 与 shipper 仍可绕过

以下 controlled negatives 均被 R4 错判 complete：

1. supplier：`no partnership`、`lack a partnership`、`denied a partnership`；
2. capacity/HBM：`not/never allocated to Dell`、`unavailable to Dell`（`available` 命中 `unavailable`）；
3. yield：`will reach`、`forecast to reach`、`planned to reach 90%`、`N2 pilot line`；
4. units：`Dell has not/never shipped`、`Dell denied it shipped`、`Dell said NVIDIA shipped four Dell AI servers`。

R5 必须增加 token-bound、scope-aware polarity；主客体和 reported-speech direction；Dell seller/shipper 与 counterparty action 分离；future/planned/forecast 双向 qualifier；pilot/wrong-process exclusion。每个攻击及肯定 control 都要冻结成 regression。

## 5. R17 研报质量的独立结论

审计确认 39 个 R17 surface、42 个 claim ref、18 个 unique Evidence ref 与 10 个 unique gap ref 全部能通过 R10 catalog/source binding 解析。Gross margin、operating margin、implied expense ratio、OCF/FCF 算术正确；FCF 明示 deterministic non-GAAP；guidance、概率、cohort、供应商、PVM/units 与因果/反方边界总体受控。

但报告仍不能验收：

- P1：正文只露出 EV/GAP 内部 ID，没有 URL、title、issuer/publisher、measurement/publication period、page/section locator、source role、bibliography/source appendix；
- P2：Pack=`55 Evidence / 14 gaps / 0 closure`，R17 未消费后来的 `14 Pack / 9 R38 / 4 Writer groups / 10 Writer gap refs` crosswalk；price-in、scenario/sensitivity、supplier-capacity read-through、valuation basis 四个 Pack gap 未被 Writer 引用；
- P2：六个 WWC 均缺 structured owner、frozen window、calibrated threshold/authority 与完整 evidence route；
- P3：20,574 字符有 71 次 fact occurrence、仅 38 个 unique fragment；inventory 15.052B 重复五次、revenue 43.842B 三次，六个 WWC theme 在正文与顶层重复。

因此 report research quality=`FAIL / formal assessment not yet valid`，formal eight-dimension score 与 qualified-human conclusion 都不能签。

## 6. R5 与停止条件

1. R4 policy/private/public/receipt/audit 全部保持不可变，新建 R5 contract、policy、attempt 与结果路径；
2. R5 继承 R4 已独立通过的 execution/integrity/privacy/R39/frozen-v1 seal，不重复改这些层；
3. 先实现并通过所有新 P1/P2 attacks、真实 R39 positive controls 和 exact route regression；
4. full author gate、clean implementation commit/push 后，才允许单文件 authority commit/push；
5. 只消费一个 fresh local 0.6B query batch；同 attempt 不重试；
6. immutable R5 结果仍需另一个全新 fork-none reviewer 同审工程与 R17 研报质量；
7. fresh R5 audit 前，03C、4B、reranker、Candidate/Evidence/NumericFact promotion、gap closure、public-information boundary、S1/S2/S3、报告、产品、publication、release 全部禁止。

审计收据：`configs/audits/fin_ia_0_1_3_commit_3629272c_dell_03b_r4_fresh_dual_audit_fail_v1_0.json`，digest=`908f0db0b0e4880b3f61cb893cbb6cd086eab2905305b1bb58a7b79d62ae13a8`。
