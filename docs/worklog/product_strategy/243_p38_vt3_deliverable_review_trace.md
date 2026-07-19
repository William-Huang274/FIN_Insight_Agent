# P38 VT3 Deliverable Review and Trace

日期：2026-07-18

## 1. 目标与范围

本增量继续消费 VT2 已接受的 exact three-cell Workpaper 和 fixture-only WriterAdmission，形成第一条可在浏览器中使用的 Point 06 纵向路径：

`Workpaper -> no-source deterministic composer -> immutable HTML/Markdown -> exact-version review -> bidirectional Trace`

范围只覆盖 `demand_signal`、`revenue_capture`、`thesis_counterevidence` 三个当前列车 cells。没有调用 Writer model、source、SQL research route、graph、tool、provider 或 network；没有 paid/full-chain、真实业务 Case mutation、runtime promotion、release admission 或 production cutover。

## 2. 产品能力增量

分析师现在可以在浏览器中：

1. 消费 exact Workpaper version/content digest 和 WriterAdmission；
2. 生成 deterministic no-source deliverable preview；
3. 查看共享同一 canonical presentation identity 的 immutable HTML 与 Markdown；
4. 查看三条 material claims，以及各自 evidence、numeric、repair outcome 和 explicit gap refs；
5. 对 exact artifact version/content digest/presentation digest 执行 comment、return 或 fixture-preview accept；
6. 在 claim-to-source 与 source-to-claim 两个方向检查 lineage；
7. 刷新页面或重启后端后恢复同一 artifact、review history、terminal decision 和 trace manifest。

演示地址：`http://127.0.0.1:5173/cases/case_b9fd79a9b6f41a54317fa2dd/deliverable`。

## 3. 实现合同

Machine contract：

- `configs/releases/fin_ia_0_1_vt3_deliverable_review_trace_contract_v1_0.json`
- file SHA-256：`5ada551c5d9a1a26717bdbb8083a08b9b1807ec62ae439529294879239e9bd99`
- canonical digest：`ba3c1e0a18f55a5c071424146c23d2bd6572e726f99683483906cf79590ade6a`

新增 routes：

- `GET/POST /api/v1/cases/{case_id}/deliverables`
- `POST /api/v1/artifacts/{deliverable_id}/versions/{artifact_version}/review-actions`
- `GET /api/v1/cases/{case_id}/trace`

新增 canonical objects：

- `CanonicalPresentationModelVersion`
- `DeliverableReviewActionVersion`
- `ArtifactProvenanceManifestVersion`

RuntimeFacade replay 新增 deliverable preview、review action 和 trace manifest 投影。HTML 与 Markdown 持久化各自 content digest，但必须绑定同一 canonical presentation digest。

## 4. 当前路径集成修复

父线程在同一 bounded integration repair 中关闭四个当前路径问题：

1. backend `renderings`/review/trace wire shape 与 frontend 类型不一致，且 frontend 最初本地重建 HTML/Markdown；统一为后端 exact immutable artifact，并使用 sandboxed iframe 展示 HTML；
2. mobile `390x844` 下 trace reference 和 100% tab 加外边距导致页面横向溢出；增加 grid min-width、长标识换行和 tab width 约束；
3. source-to-claim 切换沿用 claim selection，造成 source 列表无选中项、结果仍显示旧 claim gap；切换方向时重置为该方向首个合法 identity。
4. 独立 reviewer 发现 `TRACE_MANIFEST_COMPILED` 未携带 claim/source counts，导致 event replay projection 将非空 trace 记成 0；事件补入两个确定性 count，并在现有 happy-path 测试中断言 replay 与 manifest exact match。

没有新增 milestone、gate family、package family 或 adversarial test matrix。

## 5. 独立验证

- VT3 + VT2 + canonical store/replay 定向回归：`49 passed in 15.28s`；
- TypeScript strict：通过；
- Vite production build：通过，`1688 modules transformed`；
- browser desktop `1440x1000`：HTML/Markdown、comment、accept、双向 Trace、refresh 通过，无页面级横向溢出；
- browser mobile `390x844`：`scrollWidth=clientWidth=390`，terminal review 和 trace 可见；
- permission negative：缺 `trace:read` 返回 `403`；
- stale binding negative：错误 artifact content digest 返回 `409 artifact_content_digest_mismatch`；
- backend restart：恢复 artifact v1、2 条 review actions、1 条 terminal decision 和同一 trace manifest；
- trace artifact content digest 与 canonical presentation digest 均与 deliverable head exact match。

演示 artifact：

- artifact version：`deliverable_39e651b2963b70dfd6197eee:v1`；
- content digest：`fa072f4d0f5d48bb689b9a9ae315c4fa72b2905061d6745da3f873ac2b8bd689`；
- canonical presentation digest：`f188f0bcede971e861bf7859235d518caa52e0cb5cfb40a56e71932e586ee76b`；
- trace manifest：`trace_manifest_ec9cf7e984a465c3d7a88b0f`；
- terminal status：`accept_fixture_preview`。

Hard boundaries：network/model/provider/tool/source/SQL/graph/writer-model/paid-full-chain/runtime-promotion/release-evidence 均为 `0`；production cutover 与真实业务 Case mutation保持 forbidden。

## 6. 成熟度与下一步

Disposition：`VT3_THREE_CELL_DELIVERABLE_REVIEW_TRACE_CURRENT_TRAIN_FULL_APPROVED`。

- Point 06 three-cell no-source preview/review/trace subset：current-train full；
- Point 06 formal owner closeout：未宣称完成；
- P36 10-20-cell calibration：deferred；
- runtime admission：`not_granted`；
- operational qualification：`not_qualified_deferred_to_REL_PROD_001_RG1`；
- production readiness：`not_admitted`；
- legacy global authority：`retained`。

下一产品步骤进入 VT4 Point 07 的 internal fixture candidate freeze、完整 P36 dogfood、SaaS/Bank 结构回归、产品价值评估和 rollback/release decision preparation。RG1 bounded operational run 仍须单独授权并在 P07.5 前通过，不能由本轮 fixture accept 替代。
