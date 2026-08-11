# P38 VT1 P03.0-P03.3 Evidence Workbench

日期：2026-07-18

## 1. 目标与范围

本增量把 P02.1-P02.5 已有的 Case、accepted DecisionSurface、EvidenceSlot 和 pending `p36_evidence_fixture_entry` WorkUnit 接到首个可用的 Evidence Workbench。范围严格限定为 `P03.0-P03.3 VT1`：

- 固定消费三格中的 `demand_signal`、`revenue_capture`、`thesis_counterevidence`；
- 用 canonical `EvidenceRequestCompiler`、`BoundedToolPlanner` 和 `CandidateBundleCompiler` 生成 deterministic metadata-only fixture；
- 不执行 retrieval、tool、network、model、provider 或 paid/full-chain；
- 不创建 Attempt/Artifact，不做 Evidence promotion 或 numeric parsing；
- 允许分析师筛选、检查、拒绝 candidate 和请求 repair；
- 不提供 force accept。

P03.4 official SourceHunter repair execution、P03.5 calibration/正式 Point03 owner closeout 不属于本列车增量。

## 2. 产品能力增量

分析师现在可以在浏览器完成连续工作流：

1. 创建 Case；
2. 编译并接受固定 P36 三-cell DecisionSurface；
3. 创建唯一 pending fixture WorkUnit；
4. 从 Activity 打开 `/cases/:caseId/evidence`；
5. 准备三格 Evidence fixture；
6. 查看 2 个 candidate、2 个 context-only candidate 和 1 个 typed gap；
7. 按 cell/status 筛选，并检查 source、authority、citation、published date、entity/period、document/table address 和 applicability boundary；
8. 带理由拒绝 candidate；
9. 对 typed gap 发出 repair request；
10. 刷新页面或重启后端后恢复 workspace、rejection 和 repair state。

界面始终显示 `Candidate review only` 与 `Not promoted`，不会把 fixture candidate 写成已接受证据或事实。

## 3. 实现合同

Machine contract：

- `configs/releases/point03_vt1_evidence_workbench_contract_v1_0.json`
- SHA-256：`77f8cf2baa455e1c032283d618da1e2767a16fb67b07e8e46eaedb53d175a56e`

Backend routes：

- `GET /api/v1/cases/{case_id}/evidence`
- `POST /api/v1/cases/{case_id}/evidence/compile`
- `POST /api/v1/cases/{case_id}/evidence/candidates/{candidate_id}/reject`
- `POST /api/v1/cases/{case_id}/evidence/slots/{evidence_slot_id}/request-repair`

Persistence：

- immutable `canonical_evidence_workbench_projection_versions`；
- append-only `canonical_evidence_review_action_versions`；
- `EVIDENCE_FIXTURE_COMPILED`、`EVIDENCE_CANDIDATE_REJECTED`、`EVIDENCE_REPAIR_REQUESTED`；
- RuntimeFacade replay 能恢复 workspace version 和 review action identities。

## 4. 纵向集成修复

父线程独立集成发现并修复两个当前路径问题：

1. 后端 wire projection 与前端 view model 最初不一致，导致 compile command 422 和读取后无法渲染；修复为 typed client 显式 normalizer，并让后端返回 UI 所需的 route/entity/period metadata。
2. canonical replay 最初不识别三个 Evidence 事件；修复 replay event registry 和 evidence workspace projection，并补入 replay regression。

两项都属于当前 VT1 主链缺陷，没有新增 milestone、package family 或 gate family。

## 5. 父线程独立验证

- Point 01-03 定向合同/API/frontend 回归：`62 passed in 24.96s`；
- Point 3 replay 修复后定向回归：`30 passed in 17.59s`；
- Python compileall：通过；
- TypeScript：通过；
- Vite production build：通过，`1683 modules transformed`；
- desktop `1440x1000`：`scrollWidth=1440`，无横向溢出；
- mobile `390x844`：`scrollWidth=390`，无横向溢出；
- browser vertical：Case -> plan -> accept -> WorkUnit -> prepare fixture -> inspect -> reject -> repair -> reload/restart recovery 通过。

演示 Case：`case_dedc8375bff047c0317e969e`。

持久化计数：

- Research Case versions：`1`；
- WorkUnit versions：`1`；
- Evidence Workbench projection versions：`1`；
- Evidence review action versions：`2`；
- Attempt：`0`；
- Artifact：`0`；
- external calls：`0`；
- replayed workspace version：`3`；
- replayed review actions：`2`。

## 6. 成熟度与下一步

Disposition：`P03_0_P03_3_VT1_CURRENT_TRAIN_FULL_APPROVED_POINT03_FORMAL_CLOSEOUT_DEFERRED_TO_VT2`。

- P03.0-P03.3：VT1 current-train full；
- P03.4/P03.5：deferred to VT2；
- Point 03：未正式 owner closeout；
- runtime admission：`not_granted`；
- operational qualification：`not_qualified_deferred_to_REL_PROD_001_RG1`；
- production readiness：`not_admitted`；
- legacy global authority：`retained`。

用户可以先试用当前 Evidence Workbench。下一产品开发决策应基于试用反馈和纵向版本列车：优先进入 P04 的 parser/numeric/evidence-promotion fixture slice，而不是在 Point 3 内继续横向扩展 retrieval owner 或生产治理。
