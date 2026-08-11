# FIN 0.1.2 S4-T06-B current 前端、runtime mode 隔离与浏览器验收

日期：2026-08-05
状态：`engineering pass / current read-only frontend available / T06-C pending`

## 完成结果

本项新增独立 `/current` 成品入口。DELL、MU、NVDA 各自展示 Case、Run、Evidence、Numeric、Graph、Gap、Workpaper、Report、Trace 和 quality 十个只读视图。前端只调用 T06-A current API，显式携带 `X-Fin-Product-Mode: current` 与 `current_product:read`，不使用 `fixture_internal`，不提供业务写入按钮。三案没有 approved Graph edge，因此产品显示 typed empty，而不是补假关系。

RC-P36-127 的根因已关闭。`create_app` 现在有显式 `current/fixture` runtime mode：默认 current 保留共享 runtime 和后台 dispatch；旧 fixture workflow 必须显式选择 fixture，后台 dispatch 关闭，原 pending-before-compile 状态机得以保留。没有禁用 current runtime，也没有放宽 Evidence 校验。原回归由 `1 passed / 10 failed` 变为 `11 passed`。

## 验证

- T06-B + 历史 Evidence/VT2/VT3 fixture contracts：`17 passed`
- Playwright Chromium desktop/mobile：`6 passed`
- TypeScript：pass
- Vite production build：pass；保留单 chunk >500k 非阻塞 warning
- npm audit：更新 Vite 7.3.6、PostCSS 8.5.25、esbuild 0.28.1 后 `0 vulnerabilities`
- 扩大 T05/T06/Workbench 选择性回归：`148 passed / 4 failed`

4 个扩大回归失败没有归入 T06-B 修补：其中 3 个测试要求已经真实使用过的 MU R1 runtime root 仍“不存在”，属于一次性 fresh admission proof 的事后不可重放；另 1 个 T05 entry test 把后来在 T03/T04 合法演进的源码 SHA 当作永久历史锚点。删除真实 runtime 或重写历史 release decision 都会破坏审计真相。新 current 实现由 T06-B successor record 绑定，T06-A 历史 record 保留不动。

## 浏览器说明

用户授权在缺少依赖时安装 Playwright。本会话没有 interactive Playwright skill 要求的 `js_repl`，所以验收明确使用仓库 Playwright Test/CLI，而非冒充交互技能。浏览器覆盖三案与十视图、跨案切换、current headers、Graph 空态、报告、质量边界、未知案例回退及移动布局；本地截图仅作为忽略的测试产物，不进入 Git。

## 边界与下一步

本项没有模型、Provider 或金融来源调用，没有业务 runtime 写入；只有用户已授权的 npm/Chromium 依赖下载。T06-B 工程通过不等于 T06 产品验收。typed return/request-repair/replay 与 T07 handoff readiness 仍归 T06-C；qualified Human Review 和 NVDA R3 仍只归 T07；RC-P36-119/125 仍后传 T08–T10/S5，RC-P36-115 仍归 S5。

实现记录：`configs/releases/fin_ia_0_1_2_s4_t06_b_current_frontend_runtime_isolation_and_browser_zero_call_implementation_v1_0.json`，digest=`3eb7532aff2d7189d5b46c433735f5e675b8da6c43a1cfa5f2bfa11f04d958c4`。

下一项：`FIN-0.1.2-S4-T06-C-TYPED-RETURN-REQUEST-REPAIR-REPLAY-AND-T07-HANDOFF-READINESS-ZERO-CALL-IMPLEMENTATION`。
