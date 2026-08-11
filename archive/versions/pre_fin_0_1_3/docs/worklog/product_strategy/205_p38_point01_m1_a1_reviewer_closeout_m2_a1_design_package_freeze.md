# P38 Point 01 M1-A1 reviewer closeout 与 M2-A1 design/package freeze

日期：2026-07-14
状态：`M1_A1_complete_historical_claim_retained_without_authority_expansion; M2_A1_design_package_frozen_pending_independent_review`

## 决策

total reviewer `william/003/total_reviewer` 独立复核 M1-A1 的 package、admission、single-use receipt、actual gate、closeout 及两条 receipt ledger record 后，批准 `approve_and_retain_historical_m1_without_authority_expansion`。M1-A1 可以关闭为 reviewer governance execution point；既有 M1 historical claim 仅在原限定成熟度和 authority boundary 下保留，不扩大为 compiler、cutover 或生产 authority。

随后只授权 M2-A1 的 design/package freeze；没有授权 A0-M2-P01/P02/P03 actual probes。

## M1-A1 closeout

- reviewer acceptance receipt digest：`b925d2937bb4bd71fa52d33484445bf47b9629a4379f4c84d759e2d9f1a0ec6c`。
- final reviewer closeout gate：`pass`，result digest=`87eaf8ba806b370cb07cec7b60ac7ec5a6ec45e8a472675e22fbe2baa06854cd`。
- retained maturity：`full_calibrated_sqlite_first_postgresql_compatible_control_slice`。
- retained authority：`legacy_taskrun_authoritative_no_compiler_or_cutover`。
- single-use M1-A1 execution receipt 已消费；不重新执行。static closeout 不读写 store、不运行 M1，不创建任何外部/model/tool/provider activity。

## M2-A1 design/package freeze

- 新增 separated actual-input corpus、expected-cell oracle 与 owner/typed-stop matrix；四行业仅为 sanitized reviewer calibration contracts，oracle 标记 `runtime_input_forbidden=true`。
- package 使用 Git-index bytes 固定 compiler、packs、selection、serializer、legacy mapping、model admission、feature flag、shadow compiler/orchestration 及其 contract tests；排除 mutable docs/worklogs。
- M2-A1 package digest：`5e464a22aa77723cc15febb8d5a80357d4bc3fac1137da54dbdf25c49ae2a35c`；design gate digest：`968b5bd0e557c61312976a4e55930722fcb39e688bdc2041a95c44531e64871d`。
- 静态 gate 通过：四行业输入、oracle isolation、三 probe typed-stop matrix、future external admission + single-use receipt、required source bindings 全部成立。

## 验证与停止点

- 运行：`python -m py_compile scripts/engineering/run_point01_m1_a1_final_reviewer_closeout.py`、`python scripts/engineering/run_point01_m1_a1_final_reviewer_closeout.py`、`python -m py_compile scripts/engineering/run_point01_m2_a1_design_package_freeze.py`、`python scripts/engineering/run_point01_m2_a1_design_package_freeze.py`。
- 未运行：任何 compiler/shadow fixture、M2 pytest、模型、网络、工具、provider、store open/write、PostgreSQL、业务 Case 或 legacy authority mutation。
- 下一步仅为 independent reviewer 审计 M2-A1 design/package。新的 external admission 与 single-use execution receipt 之前，不得执行 A0-M2-P01/P02/P03，更不得进入 M3/M6/R3。
