# FIN 0.1 代码主干、归档与断连审计

日期：2026-07-19

状态：`inventory_frozen / cleanup_in_progress / no_release_authority`

机器清单：`configs/releases/fin_ia_0_1_code_mainline_manifest_v1_0.json`

## 1. 审计目的

这次工作停止继续增加 FIN 0.1 功能，先回答四个仓库问题：

1. 更新 PRD、TECH 和 Point 01-07 以来，哪条代码链是当前产品主干；
2. 哪些代码是可复用底座、历史证明、发布复现、设计参考或本地生成物；
3. 哪些已经成功实现的能力没有接入当前 FIN 0.1 产品链；
4. 如何把一个超大未提交工作区切成可审查的提交，而不破坏历史 digest 和用户改动。

本审计不授权 paid LLM、真实网络/工具调用、operational run、Case mutation、release 或 production。

## 2. Git 基线与风险

当前分支为 `codex/layered-data-source-expansion`，HEAD 为 `e8596d88`（`Add P26 product evidence depth split gate`）。审计开始时工作区有约 1365 个状态条目，其中约 1303 个已暂存；cached diff 约为 1303 files / 428,376 insertions / 4,060 deletions，另有 59 个文件存在 unstaged diff。

这不是“当前一轮小改动”，而是 P26 之后的 Point 01 Foundation、Point 02-07 纵向列车、Workbench、产品设计和 release evidence 尚未形成提交切片。此时直接 `commit`、批量 unstage、目录搬迁或 `git clean` 都可能混淆用户已有暂存选择、历史证明和当前产品实现。

因此本轮采用：

- 不重置 index；
- 不删除未知未跟踪文件；
- 只删除能够证明为误生成的包管理文件；
- 只忽略明确的本地运行/渲染输出；
- 先冻结主干清单和提交顺序，再单独执行提交切片。

## 3. 当前产品主干

当前 FIN 0.1 可运行产品主干是：

```text
apps/workbench/frontend/vite/src
  -> apps/workbench/backend/app.py
  -> apps/workbench/backend/api/v1
  -> apps/workbench/backend/application
  -> src/sec_agent/canonical_runtime reusable interfaces
  -> local BM25 / Gold SQL / research graph read-only assets
```

主要产品入口：

- React/Vite：`apps/workbench/frontend/vite/src/`；
- `/next`：当前 internal-alpha 产品呈现；
- FastAPI：`apps/workbench/backend/app.py`；
- Case/Plan/Execution/Evidence/Numeric/Workpaper/Deliverable/Human Baseline：`api/v1` 与 `application`；
- 本地研究链：`P36LocalResearchService`，固定 10 cells、8 次对象 BM25、1 次 Gold SQL、1 次图谱 SQL，并确定性生成 numeric/repair/judgment/workpaper/writer projection；
- 运维入口：`scripts/workbench/start_internal_alpha.ps1` 与 `stop_internal_alpha.ps1`。

该链已经能支持内部浏览、调试和人工基线界面，但当前 model/provider/network/tool calls 为 0，Human Senior Review 仍无 exact accepted record，RG1/RG3/RG4 未通过。

## 4. 不应删除的三类“旧代码”

### 4.1 历史 Multi-Agent 引擎

`src/sec_agent/langgraph_orchestrator.py`、Research Lead、specialists、skills、graph、tool controller、Memo Writer 和 verifier 是已实现且经过历史 stepwise/paid/deterministic 验证的能力资产。它们没有进入当前 FIN 0.1 主链，但并非一次性垃圾。

处理：保留为 `historical_agent_engine_reuse_candidates`，下一步只允许通过一个版本化 runtime adapter 接回，不允许在 Workbench 内再造第三套编排器。

### 4.2 Point 01 proof/closeout support

`canonical_runtime` 内 `m1_*`、`m2_a1_*`、`m6_*`、`p01_g2_*`，以及 `configs/engineering_handoff` 和 `data/manifests/point01_*`，有大量 milestone-specific 内容。结构上应与通用 runtime 分离，但历史 package/manifest/digest 绑定了当前路径。

处理：本轮不移动、不重命名、不压缩；标为 path-stable historical proof support。只有未来建立版本化 path/digest migration 后才归档。

### 4.3 Release reproducibility 与 evidence

`scripts/releases` 是可复现命令，不是应用 runtime；`reports/release_evidence` 是小型持久证据，不是 raw output。

处理：两者保留并补 README。原始日志、截图、SQLite、provider response 留在 `.codex_runtime`，不得提交。

## 5. 已实现但与当前主干断连的能力

### D1. 历史 Multi-Agent 编排与当前 FIN 0.1 产品链断连

已实现：Research Lead 规划、激活校验、evidence operators、coverage reflection、specialists、judgment aggregation、Memo Writer、verifier、renderer。

当前断点：`P36LocalResearchService` 直接执行固定检索和确定性合成，`Workbench Next` 只消费这些 read models，没有调用历史 LangGraph。

原因：为了尽快得到可检查、无 paid/operational authority 的纵向产品，FIN 0.1 选择了 bounded deterministic chain；之后没有补统一 adapter。

影响：现在的 Agent 主功能不是“已接入但关闭”，而是“历史引擎存在、当前产品未消费”。

当前代表性校验 `tests/test_multi_agent_agent_registry.py` 为 `6 passed / 1 failed`。失败点是实现已给 Product/Technology Analyst 增加 `relationship_graph` source family，而旧测试仍锁定此前三项列表。这证明历史引擎不是无法导入的死代码，但它存在未裁决的合同漂移；本轮不通过顺手修改测试来伪造收口。

### D2. Skill Registry 与当前运行链断连

已实现：`research_skills.py` 的版本化 skills/role bindings，历史 Research Lead、specialist 和 writer 会读取它。

当前断点：本地 10-cell service 把判断逻辑写在 Python 中；DeepSeek 三-cell runner 直接冻结 prompt，不解析统一 skill registry。

原因：两个新 slice 分别追求 deterministic preview 与 exact paid package，绕过了旧运行时依赖。

影响：当前 UI 不能选择 skill，也不能证明某个结果消费了哪个 skill/version。

### D3. 图谱数据已使用，但 Agentic Graph Research 断连

已实现：本地 research graph 规模较大，历史引擎支持 relationship planning/lookup。

当前断点：FIN 0.1 只执行一个固定 graph SQL 来生成 counterevidence，不允许 Agent 自适应遍历。

原因：当前 slice 将图谱限定为 read-only bounded input，尚未定义图谱工具权限、预算和结果合同。

影响：可称“使用图谱候选”，不能称“Agentic knowledge graph research”。

### D4. ReAct/Agentic Search Controller 断连

已实现：`DeepSeekToolController` 有 bounded steps 和 tool trace。

当前断点：它仍是 SEC-oriented，默认 `execute_tools=False`，既没有接 `P36LocalResearchService`，也没有接 standalone DeepSeek runner。

原因：FIN 0.1 尚未冻结产品 tool registry、authority 和可见 trace contract。

影响：ReAct/agentic search 属于历史基础设施，不是当前 Workbench 能力。

### D5. DeepSeek 三-cell runner 与 Case/Workbench 断连

已实现：v1.1 exact contract、provider preflight、三次语义调用预算和 fail-closed accounting。

当前断点：runner 是 `scripts/releases` 下的独立 CLI，只写 `.codex_runtime`；没有 API、Case artifact 或 UI projection。

原因：它等待显式 paid approval，且当时优先冻结调用边界而非产品集成。

影响：即使未来单独跑通，也不能自动等同于 FIN 0.1 integrated model chain 或 RG1。

### D6. Human Baseline 与 canonical Case 断连

已实现：计时任务、草稿、Senior Review、exact digest attestation、JSON export。

当前断点：记录写独立 `.codex_runtime/internal-alpha/human-baseline.sqlite3`，不写 canonical Case/store。

原因：为了让用户先试用，同时避免在 acceptance 前扩大真实业务 Case authority。

影响：适合内部基线，不足以单独关闭 RG3/RG4；以后需要明确的 review import contract。

### D7. 独立 UX prototype 与 React runtime 不直接相连

已实现：八屏可点击 prototype 和截图。

当前断点：它是设计参考，React 只选择性实现；不会被构建或 import。

原因：prototype 的职责是冻结信息架构和交互，不是生产代码。

影响：二者视觉不一致应作为 acceptance drift 处理，而不是把 prototype 文件拷入 runtime。

### D8. 旧 Workbench/R53-R60 与 FIN 0.1 同进程共存

已实现：历史 profile/job/session/eval、R53-R60 reviewer/deliverable API 和静态前端。

当前关系：它们并非完全断连，而是继续由同一个 `backend/app.py` 承载；新 `/api/v1` 和 `/next` 只是当前产品主路径。Vite `dist` 缺失时，服务仍回退到 `frontend/index.html` 与 `frontend/static`。

原因：Point 02 采用渐进迁移并保留 rollback，没有做一次性替换。

影响：一个进程中存在两代产品面，`app.py` owner 过宽；但发布前直接删除会破坏兼容和回滚。应在 FIN 0.1 release 后先抽成 legacy router bundle，再决定退役。

## 6. 重复造轮子的准确判断

仓库存在重复实现，但不是所有并行代码都应删：

- **真实重复/绕行**：当前 deterministic research chain、standalone model runner 和历史 Multi-Agent engine 分别拥有部分 planning/synthesis 逻辑；skill 解析、tool execution 和 result projection 没有统一入口。
- **合理并存**：旧 `/tasks` 与 `/next` 是迁移/rollback 关系；release scripts 与 app runtime 职责不同；prototype 与 React runtime 职责不同。
- **结构债务但暂不能移动**：`canonical_runtime` 混有通用 runtime 与 Point 01 proof modules，受历史 digest/path 约束。

因此清理目标不是删掉旧 Agent，而是确定“唯一产品入口 + 唯一未来 Agent runtime adapter + 明确历史/证明/复现边界”。

## 7. 本轮可安全清理

1. `.codex_runtime/`：本地 run、日志、截图、SQLite、freeze output，加入 `.gitignore`，不删除本地内容；
2. `output/`：生成的 UI concept preview，加入 `.gitignore`，正式 design assets 仍在 `docs/product/design_assets`；
3. `apps/workbench/frontend/pnpm-lock.yaml` 与 `pnpm-workspace.yaml`：误生成；当前仓库依赖权威是已跟踪的 `package-lock.json`，删除这两个未跟踪文件；
4. 为 Workbench、canonical runtime、release scripts、release evidence 增加 README，避免再次把兼容层、证明代码和应用主干混写。

## 8. 暂不执行的清理

- 不运行 `git clean`；
- 不批量删除 data/manifests 或 configs/engineering_handoff；
- 不移动 canonical runtime 中 milestone-specific modules；
- 不重写 1303 个已暂存文件的 index 选择；
- 不把 1365 个状态条目一次提交；
- 不将 historical Multi-Agent engine 宣布 deprecated 或删除。

## 9. 建议提交切片

1. repository hygiene + mainline inventory；
2. Point 01 contract/runtime proof；
3. FIN 0.1 release contracts + vertical train；
4. Workbench Case-to-Deliverable vertical；
5. VT4 local research + Workbench Next + Human Baseline + release evidence；
6. PRD/TECH/Point stage review + Project OS ledgers。

每个切片必须用 path-exact staging，不能用 `git add .`。由于当前 index 已混合 1303 个文件，执行提交前应先单独确认是否允许保留 working tree、重建 index；这一步不在本轮自动完成。

## 10. 后续主干决策

下一轮产品开发前应先冻结一个 `Fin01ResearchRuntime` adapter：输入为 exact Case/DecisionSurface/skill/tool/data profile，输出为 versioned Run/Artifact/Trace。它可以在 deterministic fallback、historical Multi-Agent engine 和 bounded model provider 之间选择，但 Workbench 只消费这一种结果合同。

在该 adapter 存在之前，不应再新增新的 Agent 编排器、skill registry、graph query abstraction 或 standalone writer path。
