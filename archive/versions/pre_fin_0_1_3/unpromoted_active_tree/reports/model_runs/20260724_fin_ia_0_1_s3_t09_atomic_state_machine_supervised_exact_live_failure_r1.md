# FIN 0.1 S3-T09 atomic state-machine supervised exact-live failure r1

日期：2026-07-24

## 结论

fresh admission 已 exact-once 消费。12 次 DeepSeek 调用全部返回 `ok/stop`；Provider 正确满足四层 Verifier 状态机语义，但用 JSON null 表达 pass finding 的无修复 owner，与请求声明的 string shape 和本地非空字符串前置 gate 冲突。运行终态为 `failed/failed/failed`、Artifact=0。

失败路径的原子修复获得 live 正证据：单一 `RESEARCH_RUN_FAILED` 事件携带全部 12 个 restricted capture refs，且没有 preterminal capture event，orphan=false。另一方面，Windows detached wrapper 在 runner 继续运行时退出，exit receipt 缺失；runner 未被 signal，最终自然完成失败终态。这两个剩余问题分别登记为 RC-P36-052 与 RC-P38-053，均不能归为模型单点故障。

## 执行身份与环境

- Git branch：`codex/layered-data-source-expansion`
- Git HEAD：`54d2e072b30d`
- worktree：执行前已有 519 个历史 staged paths；未提交、未推送
- provider/model：`deepseek / deepseek-v4-pro`
- admission：`fin01-s3-t09-three-cell-deepseek-atomic-terminalization-verifier-state-machine-supervised-exact-admission-r1`
- admission digest：`2b87b9360ed53ec060670446125065497f2625f9384839cb65c4482ea8c381e1`
- ResearchRun：`research_run_fin01_1e49c5f66f867ce2ba5ab9e0`
- runtime root：`.codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1`
- supervision root：`.codex_runtime/supervision/fin01-s3-t09-atomic-state-machine-supervised-r1`
- output prefix：`atomic_state_machine_supervised_r1`
- process-local `LLM_GATEWAY_TRANSPORT_RETRIES=0`

执行命令：

```powershell
$env:LLM_GATEWAY_TRANSPORT_RETRIES='0'
python scripts/releases/supervise_fin_ia_0_1_s3_t09_exact_live_execution.py launch --admission configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_atomic_terminalization_verifier_state_machine_supervised_exact_admission_r1.json --issuance configs/releases/fin_ia_0_1_s3_t09_atomic_terminalization_and_typed_verifier_state_machine_fresh_exact_admission_issuance_v1_0.json --runtime-root .codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1 --output-prefix atomic_state_machine_supervised_r1 --supervision-root .codex_runtime/supervision/fin01-s3-t09-atomic-state-machine-supervised-r1
```

## 运行事实

- calls：model/provider/network=`12/12/12`
- source network/external tool=`0/0`
- transport attempts=`12`
- tokens：input/output/total=`53,346/5,527/58,873`
- estimated cost=USD `0.02481146`
- capture/readback=`12/12`
- retry/fallback/patch/replay/relaunch/rerun=`0/0/0/0/0/0`
- canonical states=`failed/failed/failed`
- orphaned run=`false`
- Artifact=`0`

## Supervision 事实

- launch receipt：存在
- child command receipt：存在
- supervisor PID：`46480`
- observed runner PID：`35312`
- exit receipt：缺失
- child stdout：25,690 bytes，SHA-256 `1dc0c3321865db910d7a3d7eedf85861c35a4e85ca1a275921eaafac19832a4d`
- child stderr：299 bytes，SHA-256 `0c735490bee8e9a8917cc9bcb4cd09fb45568e53c8460e99c93c18e676a96bc8`
- monitor signals/retries/relaunches：`0/0/0`

stderr 只有安全的本地 TestClient/API request log，没有 Provider body。credential 值、raw assistant output 与 private reasoning 都没有进入报告或审计结果。

## 治理判断

本次运行已消费 admission，禁止 relaunch 或 rerun。RC-P38-050 的 atomicity 部分和 RC-P36-051 的状态机语义部分得到 live 正证据，但 supervision receipt 与 typed Verifier shape/semantic convergence 尚未完成。T09 成品检查、paired comparison 和 owner acceptance 均未进入。

下一项是零调用 `S3-T09-VERIFIER-REPAIR-OWNER-SENTINEL-AND-WINDOWS-SUPERVISOR-EXIT-RECEIPT-LOSS-ZERO-CALL-ROOT-CAUSE-DISPOSITION`，需新的独立授权。
