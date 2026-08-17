# 019 S1 责任分层、纵向 release slice 与持续集成更正

日期：2026-08-17

状态：`owner_concern_accepted / source_docs_corrected / runtime_slices_pending`

## Owner 提醒

Owner 指出：上一轮虽然把 S1 拆成 A–J 十个责任层，但如果实施时把它们当作十个独立小项目，各自修完、最后再合并，仍然会重复此前的返工——每个组件局部变绿，真正的数据版本、接口和金融语义冲突到完整链才暴露。

## 本轮判断

该担心成立。A–J 对故障归责有价值，但上一版当前计划的线性表述容易诱导为瀑布式组件交付。这正是 RC-S1-020 的一部分历史根因：source、object、retrieval、ranking 和 Pack 曾分别有结果，却没有一条 task-relative 产品链持续证明它们组合后仍然正确。

本轮没有取消 A–J，而是重新定义它们：

- A–J 是横向责任坐标，用于找到最早错误层；
- VS1–VS5 是纵向交付单位，用于证明当前主线组合可用；
- 任何组件局部通过只记 `component_engineering_pass`；
- 真实资料贯穿当前 Pack／Workbench 后才记 `vertical_slice_integrated`；
- frozen test、异质留出和稳定性全部通过后才记 `S1_qualified_stable`。

## Canonical artifact spine

后续实现只允许围绕同一条内容寻址主链：

```text
SourceRouteDecision
  → RawSourceCapture
  → ParsedDocument
  → FinancialEvidenceObject
  → ObjectManifest / IndexSnapshot / S2SiblingBinding
  → EvidenceRequest / QueryFacetPlan
  → CandidateSet
  → CandidateDecision
  → EvidenceCoverageState
  → EvidencePackReadiness
  → WorkbenchProjection / FrozenConsumerProbe
```

每个转换绑定适用的 case、source owner、discussed entity、as-of、reporting period、locator、parent lineage、schema version 和 payload digest。未修改层复用当前 accepted 实现，但必须参加回放；不得为一个 attempt 复制 runner、schema 或 consumer。

## 纵向执行程序

1. **VS1 当前数字原生官方资料与决策账。** 用 HTML／文本 PDF／transcript 的真实资料贯穿 source→Pack→Workbench，同时实现 CoverageState、candidate ledger、reviewed binding 和 capture-bound promotion。
2. **VS2 复杂文档与数表。** 用扫描 PDF／OCR、跨页表格、脚注和修订／重述贯穿同一主链，证明数据地基修复不会在检索和 Evidence 阶段再次丢失。
3. **VS3 多路线检索与金融排序。** 在同一对象和候选边界比较 exact／BM25／dense／multi-vector／graph／SQL／official／external、rerank 和 Evidence evaluator，只以最终 Evidence Pack 业务增量决定晋升。
4. **VS4 Coverage 驱动第二轮补证。** 用 DELL 营运资金、发行人反方和上游反方验证 residual gap、counter-hypothesis、补源、晋升、Coverage delta 与 typed stop，再让 MU／NVDA 从自然问题走同核心。
5. **VS5 独立资格。** 对 DELL／MU／NVDA 做回归，在预注册 valid／frozen test／新异质留出上逐案过硬门和稳定门。

## 每个 release slice 的合并门

每个切片合并前同时要求：

1. 所改责任层的真实 fixture、gold、hard negative 和 mutation；
2. 上下游 schema／identity／period／locator／digest／lineage／失败码兼容；
3. 至少一份真实 raw source／Evidence Need 进入当前 Runtime 并物化到 Pack／Workbench；
4. 以业务语义说明 Evidence／gap／Coverage 发生了什么，而不只报测试数量；
5. DELL／MU／NVDA 适用非回归和跨案／错期／重复／排列 mutation；
6. 对 object／index 合同变化提供 rebuild manifest、迁移兼容和 rollback。

日常提交采用“定向测试＋一条 golden vertical replay”；每个切片关闭前运行完整当前 S1 回归和 Workbench smoke；只有 qualification candidate 才运行 frozen test 与新异质留出。这避免每次小改都跑最昂贵全套，也不把集成风险留到最后。

## 具体例子

- OCR 修复不能因为字符准确率提升就结束；还要证明表格／claim 对象正确入索引、正确命中查询、没有被错期或错公司候选压过、Evidence Gate 处理正确，并出现在 Coverage／Workbench。
- Reranker 提升 MRR 不能直接晋升；若目标根本没进 candidate pool、parser 已损坏对象，或它把错误 Evidence Role 推到头部，纵切仍为失败。
- CoverageState schema 写完不算 VS1；只有当前真实 candidate 逐一得到决策、Pack binding 正确、Workbench 能查看 lineage 和 rejected／unjudged 原因，VS1 才可能 integrated。

## 文档更新

- PRD 16.41：新增责任坐标、纵向交付和三层状态；
- S1 技术范式：新增 canonical spine、VS1–VS5 和六类集成门；
- 独立 S1 eval：新增组件局部通过不得关闭、真实纵切与消费者验收；
- FIN 0.1.3 当前计划 4E：从线性 A–J 改为纵向 release program；
- Project OS、capability／root-cause ledger 和当前 checklist：同步新边界。

## 本轮边界

- 0 Runtime／OCR／parser／chunk／index／Embedding／Reranker／model／Provider／network／source promotion／full-chain；
- 没有把任何组件或 case 追认为 S1 通过；
- 没有关闭 RC-S1-020、RC-S3-038 或 RC-S3-043；
- 下一项是 canonical spine／覆盖矩阵／split-safe gold program 和 VS1 设计、实现与确定性纵切，不是十个组件并行各修各的。

## 复证

- Project OS decision-bound tests：`31 passed`；
- capability ledger `124` 行、root-cause ledger `211` 行逐行 JSON 解析通过；
- active baseline：`138 Python／8 frontend／11 Runtime resources／0 forbidden reference`；
- repository secret scan：`6,873 files／0 findings`；
- `git diff --check` 通过；
- 0 Runtime／OCR／parser／chunk／index／model／Provider／network／source promotion／full-chain。
