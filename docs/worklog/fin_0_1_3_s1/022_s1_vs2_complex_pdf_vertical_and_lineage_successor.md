# FIN 0.1.3 S1 VS2 复杂文档纵切与 lineage successor

日期：2026-08-17
状态：`VS2_vertical_slice_integrated / VS3_next / S1_qualification_false`

## 1. 这轮要回答的业务问题

VS2 不是做一次“OCR 能不能识别文字”的演示，而是检查一份复杂官方年报能否从原始来源一直走到当前候选、决策、Coverage 和 Workbench，并且不在表格、脚注、跨页关系或数值权限处失真。

开发样本采用 Infineon 2025 官方年报。IFX 只属于 `train_internal`，不是 DELL／MU／NVDA 产品案例，也不承担隐藏泛化资格。选页覆盖：

- 第 164 页的 segment structure change／previous-year reclassification；
- 第 166 页复杂多层表头、Segment Result 总计与脚注；
- 第 167 页跨页 reconciliation。

## 2. 实现结果

新增 provider-neutral layout parser 和金融对象编译器，保留 raw capture digest、页码、bbox、表区、metric-row、脚注、修订上下文和跨页关系。当前正式结果包括：

- 192 页 source-level 审核；
- 5 个复杂表区；
- 56 个 metric-row；
- 1 个脚注；
- 1 个 revision／reclassification context；
- 1 个真实 cross-page relation；
- 合计 67 个候选金融对象。

第 166 页另做官方页面栅格化 OCR mutation。`Segment Result`、`2,560`、`3,105`、`14,662`、`14,955` 和 `previous year` 均保留，material token 没有低置信漏失。但该样本不是自然扫描文件，因此只记 mutation engineering pass，不记真实扫描资格。

所有 parser／OCR／table 输出仍是 candidate。表格行不成为 NumericFact；VS2 只生成 `S2_source_bound_numeric_adjudication_required` typed sibling，数值、期间、单位和公式仍由 S2 裁决。

## 3. 实际暴露的业务失败

4 个 evaluator-reviewed complex targets 中，只有 previous-year adjustment 的重述上下文进入当前前 20 并被接受。以下三项对象已经存在，但没有被当前查询／排名呈现：

1. `Total | 2,560 | 3,105` 的 Segment Result 总计行；
2. previous-year figures adjusted 的财务脚注；
3. 第 166→167 页 Segment Result 到 operating profit 的跨页关系。

当前 20 个候选形成 `1 accepted / 19 needs-review / 3 reviewed-not-recalled`。这说明“事实在 PDF 解析前丢失”已经不是最早问题；下一责任层是 VS3 的候选增量、parent expansion、semantic rerank 和金融 Evidence Role。不能继续用 parser 特判、盲目增大 top-k 或手工标准答案 URL 掩盖。

## 4. canonical spine 完整性修复

VS2 回归时发现旧 R14 VS1 有一项未被历史测试捕获的缺陷：部分 envelope 的 result-local `payload_ref` 指向 `/payloads/...`，但真实 payload 只存在于 sibling `cases` 区块。Workbench 仍能显示，所以表面运行正常；审计者和 successor 却不能按引用取回被声明的对象。

处置没有原地改写历史：

- R14 VS1 和首次 R15 VS2 结果保持不可变；
- 首次 R15 VS2 结果移入 `archive/versions/fin_0_1_3/s1_vs2_r15_dangling_inline_refs_20260817/`，不再位于活动 Runtime；
- R16 生成 v1.1 successor；
- 所有 result-local JSON Pointer 必须真实可解引用；
- envelope digest 必须等于完整被引用 payload 的 canonical digest，而不是 payload 内部去掉自摘要字段后的另一个摘要；
- 缺路径、digest drift、跨 case 和 NumericFact 权限突变全部 fail closed；
- VS1 golden vertical 重放后业务结果未变。

## 5. 评测与消费者

VS2 input 仅暴露来源、选页、研究问题和 OCR mutation 指令；page/table/anchor/target 期望只保存在 evaluator reference。评测 program 从“每 split 只能一个 catalog”更正为“active split 可有多个独立 catalog；reserved split 仍只能有一个空 catalog”。

Operations Workbench 新增“复杂文档纵切”永久只读面，展示来源身份、对象数、决定数、权限边界和 1/4 reviewed target 的业务失败。它不把 IFX 展示成产品案例。

## 6. 状态与下一项

本轮仅记录：

- `component_engineering_pass=true`；
- `vertical_slice_integrated=true`；
- `real_scanned_source_qualified=false`；
- `S1_qualified_stable=false`；
- `complete_product_chain_authorized=false`。

下一项是 VS3：在同一 CandidateSet／split／对象 snapshot 上比较 exact、BM25、dense、graph、SQL、official／external 的增量，再分别验收 semantic rerank、parent expansion 和 finance-aware Evidence evaluator。VS1 的 accepted 位于第 5／6 位和 VS2 的 1/4 complex target 是必须逐行解释的业务回归门；平均分不能补偿关键对象未进入审阅窗口。
