# S1 工作记录 087：DELL 03B R3 fresh audit failure 与 R4 要求

日期：2026-08-26

状态：`R3 immutable / execution seal independently passed / semantic-route audit FAIL / same-stage R4 required`

## 1. 最终结论

全新、无上下文继承、作者分离、只读 reviewer 审计 immutable commit
`28158e049f547657b20a4ca7092fa650e58e720d`，最终为 **FAIL**。R3 新 finding 为
`P0/P1/P2/P3=0/1/1/0`；连同仍 open 的 R17 研报质量项，当前合计为 `0/2/3/1`。Reviewer 起止工作树
均干净，仓库写入 0；它不是 qualified human，02B 仍为 `0/16`。

R3 的 execution/attempt seal 与 integrity/privacy 独立通过，但 semantic route 不能接受。R3 private/public、
attempt receipt、原始 trace、ASP/supplier 当前正例都保持不可变；`03B pass`、`local repair targets=3` 与后续
执行 authority 不成立。03C、4B、reranker、Evidence、gap closure、S2、新报告与产品验收继续暂停。

## 2. 独立通过的工程封印

Reviewer 复核了 authority commit 的 exact implementation parent、唯一 policy path、4 个 implementation SHA、
6 个 R1/R2 predecessor SHA/digest、canonical distinct output pair、exclusive attempt consumption 与第二 hard-link
失败 rollback。Public/private/attempt self-digest、private/attempt SHA、raw SHA/projection digest 和 exact public
reprojection 全部一致。

原始执行精确为 5 个唯一 request、1 batch、每 request 96 个唯一 union 与 rank 1..96、16 个唯一 final 与
rank 1..16，final 均属于 union。R2 的 zero-batch、重复 request、95/15、rank 重复、12 类 nonzero authority、
promotion 和 reranker-route mutation 均 fail closed。Focused suite 为 `29 passed`。因此 R4 应继承 R3 execution
seal，不重复推倒该部分。

## 3. P1：coverage materiality、去重与 route 错分

R3 public 写 `local_source_to_object_repair_target_count=3`，来自 capacity/supplier/units 的 `4/4/5` occurrence。
审计证明 units 的 5 条全部是错误修复义务：3 份 NVIDIA 出口许可 shipment 文本，加上 parent/slice 两份行业
AI-server shipments growth；它们都不是 Dell company-period physical units。本地重编不能把这些上下文变成
Dell units，units 应在 R4 route 更正和 prior-capture crosswalk 后进入 bounded 03C。

Capacity/supplier 的 occurrence 同样混有 parent/slice 重复与非 material tail。`NVIDIA and Dell are partnering`
的 material core 已在 compiled object，coverage 不应因 source 后面多一段“Read what customers…”而判缺。
真正的本地缺文是 source parent/slice 1887–1888 的 Dell 美国工厂一周可 ship 数千 Blackwell GPU 句子；它没有
进入 objects 34197–34198。R4 必须按 canonical source family 去重，同时保留这一真实 loss。

## 4. P2：通用语义仍可绕过

Reviewer 逐项复现四个当前测试未覆盖的 bypass：

1. `not partnered / do not collaborate` 仍被判 supplier relationship complete；
2. yield 先出现、`future A14 SRAM` 后置时，仍被判 current observed yield complete；
3. 大学收到四台 Dell AI systems 被判成 Dell company-period shipments；
4. price object 与 configuration object 中间插入 300 个同源无关对象，仍被拼为 ASP complete。

现有测试只覆盖肯定关系、前置 future qualifier、GPU/purchase 和跨 source 隔离；名为 adjacent 的 fixture 没有
位置或距离合同。R4 必须增加 negation/hedge、双向 wrong-process/future、seller/company-period versus buyer/
deployment、以及 ordered source span/window 的真实 adjacency。

## 5. 六 target 可保留与必须撤回的部分

| target | 独立可保留观察 | R4 后续 |
|---|---|---|
| ASP | real bounded packages `2/2/2/2`，final 15/16 | 保留 bundle/company-ASP 限制；R4 audit 后才可单独授权 reranker |
| capacity release | complete 0；factory sentence 是真实本地 loss | 去重、重编真实 loss，再做 allocation/timetable bounded 03C |
| capacity utilization/yield | complete 0 | 先修后置 future guard，再做 bounded 03C |
| HBM supply | complete 0，无 Dell bridge | bounded residual 03C |
| supplier→Dell | real relationship packages `4/4/4/2`，best rank 2 | 不重复补 relationship；capacity/allocation 仍 open；occurrence 不是独立 facts |
| units | complete 0；5 个 repair occurrence 全部驳回 | 不做这五条本地修复；R4 后 prior-capture crosswalk + bounded 03C |

Aggregate 的 external complete-target routes=4、same-pool reranker target=1、target-specific 4B recall target=0、
residual boundaries=6 暂可作为观察，但必须由 R4 重新签名。4B=0 只针对这六个 target，不取消通用 mixed-4B
development program。

## 6. R17 报告质量继续独立开放

R17 仍只有内部 `EV::/GAP::`，没有读者级 issuer/title/date-period/page-section/URL/claim role 或 source appendix；
14 Pack／9 dynamic／4 Writer／10 Writer-ref crosswalk 未被正文消费；WWC 多数缺 observation window、threshold
authority、owner 和 evidence route；重复与事实密度仍有 P3。故 report quality 为 `OPEN/NOT_ASSESSABLE`，Pack
仍为 55 Evidence／14 gaps／0 closure。

综合 execution plan 已有这些报告门，R4 不必把它们重复写成 S1 classifier 代码。正确做法是继续记录为下游独立
开放门，不能因旧 R17 尚不合格而阻塞上游 S1 修复，也不能用 R4 通过冒充报告通过。

## 7. R4 验收合同

1. R3 保持不可变；R4 使用新 policy、attempt、private/public result 与新 authority commit；
2. 继承已独立通过的 exact execution/attempt/Git/output seal，并绑定 R3 failure audit SHA/digest；
3. coverage 必须先满足 target-required material role，再产生 repair；输出 occurrence 与 canonical source-family
   deduplicated count；非 material tail 不制造 gap；
4. units 三份 NVIDIA export-control 与两份行业 shipments occurrence 必须为 0 repair obligation；
5. partnering material core 视为已覆盖，factory weekly-shipping sentence 保持 true local loss；
6. negated/hedged relationship 不 complete；wrong-process/future 在 yield 前后都不 complete；
7. buyer/customer deployment 不得成为 Dell company-period shipments；
8. same-source package 必须有 ordered span 与冻结 window，300-object separation 必须失败；
9. 当前 real ASP `2/2/2/2`、supplier `4/4/4/2` 与既有 Wendell/A14/GPU/bundle limits 不退化；
10. 重算六 target route，并由另一名 fresh reviewer 同时审工程、语义、source route 与 R17 open 状态。

审计收据：`configs/audits/
fin_ia_0_1_3_commit_28158e04_dell_03b_r3_fresh_audit_fail_v1_0.json`，digest=
`2cc497f2a03fb40878b09415077ac00c1e3b2a25756aa7a05332862c5e7e2fc9`。
