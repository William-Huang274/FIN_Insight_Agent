# FIN 0.1 Point 02-07 纵向版本列车 Overlay

日期：2026-07-18

状态：`FIN_0_1_VERTICAL_RELEASE_TRAIN_OVERLAY_V1_0_APPROVED`

## 问题

既有 Point 02-07 backlog 正确描述了能力 owner 和最终 closeout，但容易被执行者按 Point 编号理解为横向瀑布。Point 01 已证明：先冻结大量局部合同、过晚运行纵向路径，会让真实 entry-to-consumer 集成缺陷在一次性 operational attempt 前才暴露；随后 reviewer 又可能把新发现不断扩为新的 milestone、package 和 gate。

## 决策

新增 `configs/releases/fin_ia_0_1_vertical_release_train_overlay_v1_0.json`，把 Point 02-07 的实际建设顺序改为五个 tranche：

1. `VT0`：只关闭 P02.0 route/action/command/read-model/OpenAPI/owner set；
2. `VT1 / W1`：浏览器创建 P36 Case、三 cell plan、bounded fixture WorkUnit、Evidence Workbench；
3. `VT2 / W2`：candidate -> numeric -> judgment -> Workpaper -> repair -> LeadReview/WriterAdmission -> bounded follow-up；
4. `VT3 / W3`：Writer no-source、HTML/Markdown、exact-version review、bidirectional trace；
5. `VT4 / W4`：candidate freeze、dogfood、regression、product-value baseline、rollback、RG1-RG5 release decision。

Point/backlog 继续拥有能力和最终 closeout；overlay 只拥有版本列车的 first consumption、当周 maturity、tranche artifact 和 integration probe。`skeleton/fixture/full/calibrated` 是证据成熟度，不再被解释为每个 EP 的四道串行审批 gate。三 cell full subset 可以被下游消费，但不能写成整个 Point complete。

## 早期集成与停止规则

- W1 probe 必须穿过 browser -> `/api/v1` -> application service -> SQLite/ObjectStore -> plan -> fixture retrieval adapter -> CandidateBundle -> Evidence Workbench；
- W2 probe 穿过 CandidateBundle -> parser/numeric -> promotion -> judgment -> Workpaper -> RepairTicket -> LeadReview/WriterAdmission；
- W3 probe 穿过 WriterAdmission -> WriterBrief -> no-source writer -> canonical presentation -> exact-version review -> TraceGraph；
- RG1 bounded operational run 最早在 VT3 full fixture candidate 完成后单独申请，不允许自动授权或失败后自动重试；
- blocking finding 必须引用当前 tranche acceptance、RG1-RG5 或 P0 数据/权限/证据安全底线；未来路径 hardening 默认进入 deferred backlog；
- 同一预声明 blocker 最多两次 bounded repair，P02.0 本次已有更窄 override：只允许一次 existing-EP set-closure repair。

## 独立审计

第一次只读审计发现三项 P1：

- `P05.6` first consumption 早于 `P05.5`；
- W1 `P03.3=full` 但上游 `P03.1/P03.2=fixture`；
- P02.0 一次性 repair 和失败后不启动 P02.1/P02.2 的语义未机器锁定。

修复后第二次审计又发现 `P05.6` 的 first-consumption map 仍残留 VT3。最终修复增加“declared first consumption 必须等于 earliest stage target tranche”的测试。独立复审结果：`approve`，remaining P0/P1=`0`。

## 验证

- overlay 和所有绑定 JSON 可解析；
- 38 个 EP first-consumption 无遗漏、无重复，且不早于 backlog dependency；
- `P001-F01`-`F15` 在四周增量中精确覆盖一次；
- 六个 source contract/file SHA-256 匹配；
- `python -m pytest -q tests/contract/test_fin_ia_0_1_vertical_release_train_overlay.py`：`7 passed`；
- `git diff --check`：pass；
- ReleaseContract v1.2、FeatureScope v1.0、backlog v1.0/v1.1 未修改；
- runtime、network、model、tool/provider、authority/approval/receipt、业务 Case 写入均为 0。

## 下一步

恢复原 parent-thread worker，但只授权原 `P02.0` 的一次 bounded set-closure repair：关闭 planning accept/return wire semantics、ResumeWorkUnit owner/API、main-path typed response schemas 和 actual-set closure tests。失败则保持 P02.0 not approved，不启动 P02.1/P02.2，不自动发起第二轮 repair。
