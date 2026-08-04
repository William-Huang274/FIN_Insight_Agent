# 584 — FIN 0.1.2 S3-T04 verified delivery surface 与 Evidence density 边界

日期：2026-08-04

## 问题与决定

用户批准按 S3-T04 的零模型收敛顺序继续：修复最终 renderer、让最终预览重新绑定 Verifier、补强 fixture evidence density，并把通用 WWC 阈值换成 NVDA 案例判据。边界保持为不重开 T03、不改模型调用链、不运行第三次 exact。

实现前审计发现，“补强 fixture”不能直接照字面做。当前 Demand 与 Bottleneck Cell 只有 candidate metadata / graph hypothesis，Value Cell 只有 Numeric authority；三者都没有已晋升 Evidence Fact。把候选直接改成 Fact 会违反 candidate-is-not-Evidence 的 L1 合同。因此本轮把该项实现为 evidence qualification gate：只有经过 accepted Evidence refs 且被 Evidence Facts 消费的对象才能增加 coverage，当前结果必须诚实保持 0/3。

## 完成的工作

- 新增 `apps/workbench/backend/application/fin_0_1_2_s3_t04_product_surface.py`：
  - 只读消费 immutable replacement exact artifacts；
  - 从 exact numeric authority refs 重建 delivery clauses；
  - `__company_total__` 显示为“公司整体”；
  - `FY2025-FY` 显示为 `FY2025`；
  - 货币单位去重并增加千分位；
  - Numeric-only Claim 不再显示为“证据方向支持”，而是明确限制为只支持财务指标、不足以单独证明因果机制；
  - 7 个 WWC task 的判据来自 frozen input 的 `runtime_branch.what_would_change`；
  - 生成内容寻址 final preview 与本地 final-delivery Verifier；
  - 对 candidate 越权晋升、numeric authority mutation 和内部 token 泄漏 fail closed。
- 新增零模型 assessor 与 durable result：
  - `scripts/releases/assess_fin_ia_0_1_2_s3_t04_product_surface_convergence.py`
  - `configs/releases/fin_ia_0_1_2_s3_t04_product_surface_convergence_and_evidence_density_block_v1_0.json`
- 更新 S3 source plan、Project OS、program backlog 与 current projection v2.34。

## 结果与证据

- final delivery preview digest：`b8f5dc3d0c7ad85b0ef8417dea475ebad7af06d9d6b0b7a280709980fa10a07f`
- final delivery verification digest：`2e08604d70eea62bc4ff6b3fcfa9f30dcb943919f3b74b10276f4699b5d1351f`
- renderer L4 findings remaining：0
- case-specific WWC：7/7；generic：0
- Numeric Fact supported cells：1/3
- promoted Evidence Fact cells：0/3
- candidate metadata promoted：false
- model / Provider / external network calls：0 / 0 / 0
- replacement exact result SHA256 前后均为 `7f430356295c558f5158898d069905c3ce6d02b2585e87676c9252ebd5a3568c`
- targeted new tests + T03/T04 historical regression：`25 passed`

## 新的阶段判断

当前剩余 blocker 已不再是 renderer、WWC 或 Verifier，而是阶段循环依赖：S3 Owner gate 要求 source-grounded evidence density；但已经接受的 rebaseline 把 Retrieval readiness、Agentic Search、Evidence promotion 与自然 Case integration 放在 S4-T02/T03/T04，S4 又要求 S3 pass 才能进入。登记 `RC-P36-112`。

首选建议：Owner 把 S3 的通过含义收敛为“有限 frozen-input Runtime 与 verified delivery anchor”，明确不等于 source-grounded NVDA R2；真正 NVDA R2 验收放到 S4-T04，在 S4-T02/T03 完成 Evidence qualification 后执行。备选是在 S3 内再建 source-grounded fixture 和 product proof，但会复制 S4 范围并突破现有 attempt 止损边界，不推荐。

该范围含义调整尚未由 Owner 签发。因此当前仍是 S3 honest-block、S4 未进入、current NVDA R2=false。没有运行 product live reproof，也没有自动改写既有 Owner rejection。

## 下一步

`FIN-0.1.2-S3-T04-EVIDENCE-DENSITY-STAGE-OWNERSHIP-AND-BOUNDARY-REALIGNMENT-DECISION`
