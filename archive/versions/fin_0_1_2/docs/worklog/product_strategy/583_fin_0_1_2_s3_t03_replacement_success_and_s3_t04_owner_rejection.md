# 583 — FIN 0.1.2 S3-T03 replacement success 与 S3-T04 Owner rejection

日期：2026-08-04

## 结果

按用户确认的顺序完成了唯一 controlled-successor、fresh admission authority、原子签发、execution authority、replacement exact-live 和 S3-T04 产品验收。

S3-T03 replacement exact-live 成功：9 次 DeepSeek Pro 调用、9 份 restricted captures、3 份本地 Fact receipts、9 个业务 Artifacts；输入/输出 tokens 为 56,613/2,296，估算成本 USD 0.02662417；retry、fallback、replay、relaunch 均为 0。独立 L1 复算通过，NVDA identity、numeric/support/lineage/capture 均无新 L1，gross margin 74.99%、operating margin 62.42%。RC-P36-108 与 RC-P36-111 关闭，S3-T03 pass closed。

S3-T04 同 input deterministic baseline 与 paired review 没有接受产品：仅 value/profit cell 有本地 Facts，另外两个 cell 保持 cannot-infer；Agent 新增 7 个结构化 WWC 和有限 cross-cell 组织，但 7 个阈值均属泛化模板。最终报告暴露 `__company_total__`、`FY2025-FY`、重复 USD，且 Verifier 没有绑定最终本地 delivery preview。结论为 L1 pass、L2 limited、L3 limited-positive、L4 fail；Owner reject current NVDA R2，S3 honest-block，S4 不可进入。

## 工程判断

这轮证明“运行链路终于能完整走通”和“产品值得接受”是两件事。不能因为 9 Artifacts 成功就把 S3 记为 pass；也不能把 T04 的展示/fixture/最终预览问题倒灌回 T03，再开第三次 exact。下一项必须是独立的 T04 disposition：决定是否只做零模型 renderer、fixture evidence density 与 final-preview verification 收敛，或终止/重基线当前 S3。

## 证据

- `configs/releases/fin_ia_0_1_2_s3_t03_nvda_replacement_exact_live_execution_success_result_v1_0.json`
- `configs/releases/fin_ia_0_1_2_s3_t04_nvda_same_input_deterministic_baseline_v1_0.json`
- `configs/releases/fin_ia_0_1_2_s3_t04_nvda_paired_assessment_owner_rejection_and_s3_closeout_v1_0.json`
- `configs/runtime/fin_ia_0_1_2_current_program_projection_v2_33.json`
- `reports/model_runs/20260804_fin_0_1_2_s3_t03_nvda_deepseek_pro_replacement_exact_live_r2.md`

## 下一步

`FIN-0.1.2-S3-T04-OWNER-REJECTION-DISPOSITION-AND-S4-INELIGIBILITY-HANDOFF`。在新用户决定前不自动修复、不运行第三次 exact、不进入 S4、不改产品版本。
