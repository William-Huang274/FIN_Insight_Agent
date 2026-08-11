# FIN 0.1.2 S3-T03：replacement fresh admission authority fail-closed

日期：2026-08-04
状态：`decision complete / issuance not authorized / one controlled-successor bundle pending separate authority`

## 问题

用户授权执行 `S3-T03 replacement exact-live fresh admission authority decision`。本轮只允许零调用权限裁决，不允许同轮签发或消费 admission、读取凭据、调用 DeepSeek、paired、Owner 或进入 S3-T04。

## 结论

权限裁决没有授权签发 replacement admission。Lead-v8 的独立 proof、implementation code bindings、primary immutable failure 和 stable business input 均重新匹配，Project OS 对 exact decision scope 也通过；但当前仓库没有 replacement-ready execution envelope、atomic issuer 和 parent supervisor。

现有三个执行控制对象都精确绑定已经消费的 primary R1：

- envelope：`configs/runtime/fin_ia_0_1_2_s3_t03_nvda_fresh_identity_execution_envelope_v1_0.json`；
- issuer：`scripts/releases/issue_fin_ia_0_1_2_s3_t03_nvda_fresh_exact_admission.py`；
- supervisor：`scripts/releases/run_fin_ia_0_1_2_s3_t03_nvda_supervised_exact_live.py`。

只读编译观察可以生成 Lead-v8 profile-admissible admission schema，但 prepared execution identity 仍是历史 `fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1`，input digest=`906111…c953`。它没有 fresh replacement envelope、predicted WorkUnit/Attempt/Run 或 replacement supervision binding，因此明确为 non-issuable；其 digest 不得作为未来 admission digest。

## 根因与处置

登记 `RC-P36-111`。这是项目内 execution-control binding 缺口，不是模型或 Provider 新失败。若现在先签 admission，会重复此前“先签 authority artifact、后发现 launcher/supervisor 不可消费”的时序错误。

下一项限制为一个零调用 controlled-successor bundle，一次性生成：

1. fresh replacement execution identity 与 envelope；
2. stable-business identity normalization 和新的 complete input digest；
3. exact Lead-v8 admission payload/digest；
4. replacement-only atomic issuer；
5. 绑定 replacement authority/admission/issuance/envelope/code hashes 的 parent supervisor 与 provider-callback=0 child preflight；
6. primary R1 runtime 与失败证据 bytes unchanged proof。

bundle 上限 1，通过后仍需重新做一项独立 admission authority decision，不自动签发；失败则 S3 honest-block，无第二包或第三次 exact。

## 验证与边界

- Project OS exact decision scope：`pass / open blockers 0`。
- replacement admission、issuance、envelope、runtime root、supervision root：全部 absent。
- admission issued/consumed：`0/0`。
- credential/model/provider/execution network/source/tool：`0/0/0/0/0/0`。
- Run/Artifact/paired/Owner/S3-T04：全部 0。
- 本轮没有执行新的模型、检索、Provider health probe 或产品作业。
- 新 authority、historical lifecycle、primary issuance/supervisor/failure、Lead-v8、T02 integration、current projection 与 Project OS 合并回归：`46 passed`。首轮四个历史 lifecycle assertion 只允许旧 next；已用 `launcher_supervisor_projection_assertion_test_controlled_successor_v5_0.json` 显式登记 v2_32 successor，未修改历史 Runtime 或通过结论。

持久决策：`configs/releases/fin_ia_0_1_2_s3_t03_nvda_replacement_fresh_admission_authority_decision_v1_0.json`。

当前 next：`FIN-0.1.2-S3-T03-NVDA-REPLACEMENT-ADMISSION-ENVELOPE-ISSUER-SUPERVISOR-CONTROLLED-SUCCESSOR-MINIMUM-ZERO-CALL-IMPLEMENTATION`，尚未授权。
