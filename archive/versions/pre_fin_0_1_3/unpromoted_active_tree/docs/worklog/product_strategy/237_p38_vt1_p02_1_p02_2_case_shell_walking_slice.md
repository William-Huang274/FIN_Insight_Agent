# P38 VT1 P02.1/P02.2 Case Shell Walking Slice

日期：2026-07-18

状态：`P02_1_INTERNAL_FIXTURE_FULL / P02_2_CURRENT_TRAIN_FULL / APPROVED`

## 产品增量

内部 analyst 现在可以从 Workbench 浏览器创建 fixture Case、查看 Case 列表、打开 Case，并在刷新浏览器或重新打开后读取同一 `case_id/case_version`。链路为：

`AppShell -> typed CaseApiClient -> /api/v1/cases -> CaseService -> RuntimeFacade -> SQLiteCanonicalStore/FileCanonicalObjectStore`

默认环境仍 fail closed；只有显式设置 `FINSIGHT_P02_FIXTURE_ROOT` 才启用内部 fixture persistence。路由不直接写 DB/file，也没有自动启用模型、网络或 paid execution。

## 实现

- 后端新增 `apps/workbench/backend/api/v1/cases.py` 与 `application/case_service.py`，实现 create/list/get、idempotency、tenant/permission、expected-version conflict、ETag 和重开读取；
- `apps/workbench/backend/app.py` 注册 `/api/v1` Case router，并为 Task/Case 浏览器路径提供 SPA refresh entrypoint；
- 前端新增 `AppShell`、typed Case client、remote status 组件和 P02 shell CSS，覆盖 loading、empty、error、permission、stale、conflict 与 reconnect；
- `main.tsx` 只把 legacy Workbench 作为 `/legacy` 子路由注入，没有继续把 FIN 0.1 页面逻辑堆进旧 monolith；
- 新增两组聚焦 contract/API tests。

## 父级验证

- `python -m pytest -q tests/contract/test_point02_case_fixture_api.py tests/contract/test_point02_frontend_case_contract.py tests/test_workbench_backend.py -k "point02 or workbench_backend_health"`：`7 passed, 34 deselected`；
- bundled Node 执行 TypeScript 与 Vite production build：`1675 modules transformed`，build pass；
- 真实本地 browser/API fixture：create -> list -> open -> refresh/reopen，同一 Case identity/version 与 metadata 保持一致；
- permission 403、version conflict 409、offline/reconnect 状态均在 UI 可见并可恢复；
- 1440x900 desktop 无水平溢出；390x844 mobile Case Overview 无裁切；
- 首轮移动 Task Center 将 `shadow_created` 裁切，消耗 P02.2 第一次 bounded repair，仅修改 AppShell/CSS；复核后展示为 `Shadow created`，Case ID、状态、版本、时间均完整，`scrollWidth=390`。

## 成本与边界

本批真实增加 Case 产品主链和浏览器能力；治理增量只包含现有合同对齐测试、父级浏览器验收与一次 UI 修复，没有新增 milestone、gate family、package family 或测试矩阵。

未使用网络、模型、provider、paid/full-chain、商业数据、秘密持久化、authority/approval/receipt 或真实业务 Case。当前仅为 fixture/shadow/internal development；`RG1_vertical_path`、`runtime_admission=not_granted`、`production_readiness=not_admitted` 与 `legacy_global_authority=retained` 均不变。

下一产品批次为 P02.3/P02.4：完成 Task Center/New Case/Overview 的 feature ownership 与过滤交互，并交付 P36 三-cell DecisionSurface 的 compile/review/version/accept/return walking slice。
