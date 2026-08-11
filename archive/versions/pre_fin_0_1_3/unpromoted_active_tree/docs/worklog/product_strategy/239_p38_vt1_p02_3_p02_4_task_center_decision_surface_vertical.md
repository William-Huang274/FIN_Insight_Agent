# P38 VT1 P02.3/P02.4 Task Center and DecisionSurface Vertical

## 1. Product Result

本批在 P02.1/P02.2 Case shell 上增加了第二个真实产品纵向增量：

`Task Center / Case Overview -> typed Case and Planning clients -> FastAPI -> CaseService / PlanningService -> RuntimeFacade -> SQLite canonical store`

内部 analyst 现在可以：

- 按 API 返回的 Case status 筛选 Task Center；
- 从 Case Overview 编译固定 P36 三-cell plan；
- 查看需求真实性、价值/利润捕获、瓶颈与反证三个 cells；
- 查看每个 cell 的 question、owner、materiality、stop rule、what-would-change 和两个 required EvidenceSlots；
- 修订 what-would-change/stop rule，生成新 immutable contract/cell/slot versions；
- accept 或 return 新 planning checkpoint；
- 刷新或重新打开同一 URL，恢复 canonical current projection。

## 2. Runtime Boundary

Planning persistence 新增 operation-aligned `RuntimeFacade` methods 与 `PlanningCheckpointVersion`，复用 Case-scoped append-only canonical store。它没有借用旧的 execution-bound bundle writer，也没有创建 WorkUnit、Attempt 或 Artifact；`CaseControlSummaryVersion.planning_authority` 仍为 `legacy`。

父级浏览器 Case `case_66e91e7c87bc8b3d1d22ab9a` 的最终持久状态：

- contract versions: `1, 2, 3`；
- checkpoint states: `v1 awaiting_review`, `v2 awaiting_review`, `v3 accepted`, `v4 awaiting_review`, `v5 returned`；
- cell versions: `9`；EvidenceSlot versions: `18`；
- WorkUnit: `0`；Attempt: `0`；Artifact: `0`。

## 3. Verification

- all Point 02 contract/API/frontend tests: `28 passed`；
- Point 01 DecisionSurface planning regression: `9 passed`；
- TypeScript and Vite production build: pass, `1679 modules transformed`；
- parent browser: create -> compile -> revise -> accept -> revise -> return -> refresh/reopen pass；
- desktop `1440x900`: `scrollWidth=clientWidth=1440`；
- mobile `390x844`: document/body `scrollWidth=clientWidth=390`，三个 cell right edge 均为 `374`；
- P02.4 contract digest: `83319c49d2c91616503e83a2fce31ff2837792ecbbdb6015aaa08f4c85cfffb7`。

## 4. Bounded Repair

父级代码审查发现 Case Overview 在已有 plan 时显示 `Compile new version`，但 backend compile 正确地只允许首次创建；该动作必然返回 conflict。P02.4 的首次 bounded repair 删除了这条错误动作，后续新版本只从 Decision Surface 的 revise 路径产生。没有派生新 milestone 或 gate。

## 5. Maturity and Next Step

P02.3 为 current-train full in live API fixture mode；P02.4 为 current-train full for the fixed three-cell internal fixture scope。owner-level 10-20 cell/calibrated closeout 仍 deferred，Point 02 尚未完成。

下一步是 P02.5：只做一个 bounded internal fixture WorkUnit start/cancel/typed-stop/activity restore slice，然后连接 P03 Evidence walking skeleton。RG1、operational qualification、FIN 0.1 release 与 production 均未授权。
