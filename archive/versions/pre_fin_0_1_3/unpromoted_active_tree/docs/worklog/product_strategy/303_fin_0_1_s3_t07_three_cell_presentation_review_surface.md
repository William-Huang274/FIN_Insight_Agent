# FIN 0.1 S3-T07：三 Cell Workpaper / Report / Trace / Review surface

日期：2026-07-21

## 问题与授权

用户明确“授权t07”。本轮只允许完成 T07 的零模型、零网络、零外部工具 deterministic presentation 与 review-target 链路；不授权 T08、T09 live run、admission、自动补源、Human Review 决策、真实业务写入、S4、release 或 production。

T07 的五项验收是：Workpaper、Report、Trace、Workbench 共享 exact Run/Cell/Claim/Judgment/Artifact refs；Writer 只消费已裁决 heads；Workbench 展示 Evidence/Numeric/Graph/gap/WWC/repair/stop；why/gap/WWC 不自动发起研究；Verifier 与 Human review target 绑定 exact digest/profile/input/as-of/findings/decision。

## 根因与决策

T06 已在 deterministic 主 Artifact 内形成三 Cell Specialist/Lead pack，但 Workpaper/Report/Review 页面仍优先读取旧 `LocalAnalysisPreview`，canonical deterministic Run 也只有一个主 Artifact。最早缺口位于 `src/sec_agent/memo_llm.py` 的 presentation projection 与 `Fin01ResearchRuntime` 的 artifact commit，不是增加更多 verifier gate。

本轮复用既有 Runtime、Facade、ObjectStore、execution projection 和 Workbench Next，不新增平行 Runtime、Store、Registry、Writer 或 Gate family。模型 Writer 仍未执行；T07 只把 T06 已裁决、含明确 cannot-infer 的 heads 组织为可复核产品对象。

## 完成内容

- `src/sec_agent/memo_llm.py`
  - 新增严格的 T07 `S3ThreeCellPresentationPackVersion`。
  - 编译 3 个 content-addressed `SurfaceClaimVersion`；每个保留 Cell、Judgment、事实、Evidence、Numeric、Graph context、gap、WWC、repair 与 typed stop。
  - 生成三 Cell Workpaper、三段 Report、13-node/14-edge Trace、4 个 verifier findings 和 3 个 cell review targets。
  - Writer 的 source/retrieval/external-tool/raw-Candidate authority 全部 false；只消费 Lead + 3 Specialist adjudicated refs。
  - consumer 全量重编译 pack，nested tamper fail-closed。
- `apps/workbench/backend/application/research_runtime.py`
  - 在同一 deterministic ResearchRun 中提交 `s3_three_cell_workpaper`、`s3_three_cell_report`、`s3_three_cell_trace_review` 三个 canonical Artifact。
  - 主 Artifact manifest 与 pack 内 exact artifact refs 对齐；新增 memo_writer/verifier/workbench 三份 consumption receipt。
- `src/sec_agent/canonical_runtime/facade.py`
  - 在既有 deterministic profile allowlist 中加入上述三个类型，仍要求 profile 的 artifact type 集合精确匹配。
- `apps/workbench/frontend/vite/src/api/execution.ts`、`WorkbenchNext.tsx`、`workbench-next.css`
  - Workpaper/Report/Review 优先消费当前成功 deterministic Run 的 exact T07 pack。
  - 逐 Cell 展示 Graph drill-down、Evidence/Numeric、cannot-infer、WWC、repair ticket 和 stop semantic。
  - Review 页面显示 exact profile/input/as-of/content digests、findings、允许的 review action contract；不执行或代签 Human Review。
- `tests/contract/test_fin_0_1_s3_t07_three_cell_presentation_review_surface.py`
  - 覆盖 canonical artifact refs、逐 Cell 业务语义、Writer 权限、Trace/Verifier/Human binding、完整重编译与 Workbench source contract。

## 独立复核

1. T06 的 `writer_admission_recommended=false` 没有被改写：模型 Writer 未执行，T07 只是 deterministic bounded presentation。
2. Value Cell 的两项利润率仍为 company-total；Report 不把它们描述成 accelerator、segment 或 incremental AI profit。
3. Demand/Risk 的 Candidate/Graph context 没有被提升为 Evidence；Graph 明确为 `context_only_not_evidence`。
4. Workbench 的 why/gap/WWC 只读取已有 Artifact，`automatic_new_research=false`。
5. Machine verifier pass 不等于 Human acceptance；Human status/decision=`not_performed`，exact confirmation=false。
6. Playwright 交互技能要求 `js_repl`，当前会话未提供，因此 Visual finding 保持 `pending_browser_validation`。使用 TypeScript/Vite build 和响应式源码合同替代最低工程检查，但不宣称浏览器人工验收。

## 实际效果与边界

用户现在可以在同一 Workbench Run 上看到三个研究问题各自“结论是什么、事实有哪些、数字支持到哪里、Graph 只是何种上下文、缺什么、什么会改变判断、返修给谁、为什么停止”，并从 Workpaper 进入 Report 与 exact review target，不再需要从主 Artifact 的大段 JSON 中自行拼接。

本轮没有新事实、来源、模型判断或 Alpha。RC-P30-002、P33-019、P34-020、P36-030、P36-031 只推进 deterministic presentation/review runtime layer；paid output、真实 source depth、browser/Human acceptance 与 T08-T10 仍开放。

## 验证

- T06 compatibility：`7 passed in 25.42s`
- T07 focused：`7 passed in 22.89s`
- S2 current + S3 entry/T01-T07：`54 passed in 91.58s`
- FIN 0.1 S1-S3 contracts + Workbench Next final regression：`166 passed in 166.23s`
- TypeScript + Vite production build：`1695 modules transformed`，build pass；存在既有大 chunk warning。
- `python -m py_compile src/sec_agent/memo_llm.py apps/workbench/backend/application/research_runtime.py`：pass。
- release JSON `67` files + Project OS JSONL `486` rows：parse pass。
- model/provider/execution network/source network/external tool/automatic new research/live business write/Human Review write/paid run：全部 0。

## 下一步与回滚

下一项仅为 `S3-T08-DETERMINISTIC-THREE-CELL-INTEGRATION-AND-EXACT-LIVE-ADMISSION-READINESS`，需单独授权。回滚可移除 T07 models/compiler、deterministic profile 的三个 artifact types、Runtime T07 compile/consume/commit、Workbench exact projection和 T07 contract/test/worklog；T02-T06 packs 不需改写。
