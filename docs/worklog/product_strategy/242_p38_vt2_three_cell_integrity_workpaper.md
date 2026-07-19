# P38 VT2 Three-Cell Integrity Workpaper

日期：2026-07-18

## 1. 目标与范围

本增量不按 Point owner 横向铺开，而是在既有 VT1 产品链上继续一条用户可操作的纵向路径：

`Case -> accepted DecisionSurface -> WorkUnit -> Evidence -> bounded repair -> Numeric -> Workpaper -> LeadReview`

本轮只包含：

- `P03.4_fixture_repair_subset`；
- `P04.0-P04.4_three_cell_numeric_subset`；
- `P05.0-P05.4_three_cell_workpaper_subset`。

继续 deferred：P02.6 10-20-cell calibration、真实 internal retrieval、P03.5/P04.5/P05.5/P05.6、Writer execution、operational RG1、release admission 和 production cutover。

## 2. 产品能力增量

分析师现在可以在浏览器中：

1. 对 `thesis_counterevidence` 的 exact EvidenceSlot 发出带理由的 repair request；
2. 执行一次 deterministic local official-policy fixture repair，不 retry、不调用 network/tool/model/provider；
3. 在同一个 slot identity 下看到 repaired candidate 与 append-only repair outcome；
4. 以 repaired Evidence workspace exact version 编译一个 Numeric workspace；
5. 查看 `120000 units` 的 entity、period、unit、scale、row label、source coordinate、metric definition 和 parser program steps；
6. 明确看到该 fact 只被接受用于 internal fixture judgment，不可 writer-citable；
7. 组装 demand、revenue capture、counterevidence 三个结构化 Judgment；
8. 检查每个 Judgment 的 evidence refs、numeric refs、repair outcome refs、counter-thesis、what-would-change 和 remaining gaps；
9. 对 exact Workpaper version/content digest 执行 LeadReview；
10. 只签发 fixture-preview WriterAdmission，Writer execution 始终为 0。

## 3. 实现合同

Machine contract：

- `configs/releases/fin_ia_0_1_vt2_three_cell_integrity_workpaper_contract_v1_0.json`
- file SHA-256：`2cb328eb3c69c001621ee3fc86f900417362fdb15ced823a06269f55b4e7ab79`
- canonical digest：`4a484aed29c2c510cdb572543bb5cd4364a04b604559fd744a636bb484c6a153`

新增 routes：

- `POST /api/v1/cases/{case_id}/evidence/slots/{evidence_slot_id}/execute-repair`
- `GET/POST /api/v1/cases/{case_id}/integrity/numeric[/compile]`
- `GET/POST /api/v1/cases/{case_id}/workpaper[/compile]`
- `POST /api/v1/cases/{case_id}/workpaper/lead-review`

新增 canonical objects：

- `EvidenceRepairOutcomeVersion`
- `NumericWorkbenchProjectionVersion`
- `WorkpaperProjectionVersion`
- `LeadReviewDecisionVersion`

RuntimeFacade replay 新增 repair、numeric、workpaper、lead-review 四类事件投影。公开 API 对 repaired candidate 使用显式字段白名单，内部 `source_snapshot_ref`/`metadata_rank` 不泄露到 wire view。

## 4. 当前路径集成问题

父线程集成只修复三个当前主链问题，均留在原 VT2 范围：

1. Evidence 旧测试仍断言两个可用动作；更新为包含合同新增的 `execute_repair` 与 `repair_completed_count`。
2. 前端 repair/numeric wire 字段与后端服务返回存在命名偏差；统一 `attempt_state/boundary` normalizer 与 `promotion_status`。
3. 后端重建后，repair candidate 的两个内部审计字段触发严格 response validation；在 Evidence view 边界改为允许字段白名单。

没有新增 milestone、gate family、package family 或 adversarial test matrix。

## 5. 独立验证

- VT2 + Point3 + store/replay 定向回归：`46 passed in 14.20s`；
- VT2 纵向 API、权限、stale version、idempotency、后端重建恢复：通过；
- Python compile：通过；
- TypeScript strict：通过；
- Vite production build：通过，`1686 modules transformed`；
- OpenAPI 六条 routes：生成并可解析；
- browser vertical：Case -> plan -> accept -> WorkUnit -> Evidence -> request repair -> execute repair -> Numeric -> Workpaper -> LeadReview -> refresh，通过；
- desktop `1440x1000`：无页面级横向溢出、无 console error；
- mobile `390x844`：无页面级横向溢出、无 console error；
- backend reconstruction：恢复 Evidence v3、Numeric v1、Workpaper v1；
- Attempt/Artifact/network/tool/model/provider/writer execution/runtime promotion/release evidence：全部 `0`。

演示 Case：`case_b9fd79a9b6f41a54317fa2dd`。

## 6. 成熟度与下一步

Disposition：`VT2_THREE_CELL_INTEGRITY_WORKPAPER_CURRENT_TRAIN_FULL_APPROVED`。

- P03.4 fixture repair subset：current-train full；
- P04.0-P04.4 three-cell numeric subset：current-train full；
- P05.0-P05.4 three-cell Workpaper subset：current-train full；
- Point 03/04/05：未正式 owner closeout；
- runtime admission：`not_granted`；
- operational qualification：`not_qualified_deferred_to_REL_PROD_001_RG1`；
- production readiness：`not_admitted`；
- legacy global authority：`retained`。

下一产品步骤进入 VT3 Point 06：消费本轮 fixture-only WriterAdmission，生成 no-source Writer preview、HTML/Markdown、exact-version review 和 Trace。不得先返回 Point 02-05 横向补齐 deferred owner 能力。
