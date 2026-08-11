# FIN 0.1.2 S4-T06 Workbench current product projection 入口与依赖决策

时间：2026-08-05

状态：`entry pass / current product projection blocked by RC-P36-126 / T06-A authorized next`

## 盘点结论

三案例已有可进入产品投影的 immutable anchors：合计 45 Evidence、9 Numeric、9 typed gaps、27 business Artifacts 和 3 个 Owner acceptances。现有 Workbench 也已有 Case、Run、Evidence、Numeric、Workpaper、Deliverable、Trace 的 typed API 和 React components。

真正缺口是两边没有绑定：CaseService 是 fixture-only，默认需要 `FINSIGHT_P02_FIXTURE_ROOT`；EvidenceService 读取 fixture contract；前端 principal 仍是 `fixture_internal`。T05 current assets 没有被编译成 Workbench current read model。该问题登记为 RC-P36-126，属于 T06，不归因模型或 Provider。

入口回归还揭示了一条独立历史漂移：选定的三案例验收＋旧 Workbench 回归共 `54` 项，`44 passed / 10 failed`；10 项都因 `exactly_one_pending_evidence_fixture_work_unit_required` 失败。最小对照证明默认 `create_app` 自动挂接共享 runtime 后，旧 fixture WorkUnit 在后台调度中先变为 `succeeded`，Evidence compile 随后 409；显式 `runtime=None` 时则保持 `pending` 且 compile=202。该问题登记为 RC-P36-127。它不否定 T05 current assets，也不阻断 T06-A 的只读投影；归 T06-B 的 current/fixture runtime-mode 隔离处理，不能在 T06-A 顺手修旧链。

三个 current Evidence Pack 的 approved Graph evidence 都是 0，所以 Graph 产品态必须显示 typed empty；存在本地 snapshot 或历史 graph candidate 不等于可晋升 Graph Evidence。raw capture 继续只用于受限审计。

## 范围调整建议

不重做整套 Workbench，也不把 API、前端、Human Review 一次塞进一个包。T06 固定为：

1. T06-A：三案 current manifest、只读 compiler/service/API；
2. T06-B：frontend current mode、current/fixture runtime-mode 分离、RC-P36-127 收敛和 browser/cross-case mutation；
3. T06-C：typed return/request-repair、replay 和 T07 handoff readiness。

T07 才执行 qualified Human Review/NVDA R3；RC-P36-119/125 后传 T08–T10/S5；RC-P36-115 后传 S5。decision=`55d06706…5527`，SHA=`941bc7c6…de3b`，聚焦 mutation=`6 passed`；历史选择性回归=`44 passed / 10 failed`，失败已由 RC-P36-127 如实隔离。本项 model/provider/network/source/tool/runtime-write=0。
