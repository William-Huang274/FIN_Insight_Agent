# 685 — FIN 0.1.3 S2-06 DELL Supervisor R1 终止与合同漂移

日期：2026-08-07

状态：`R1 immutable terminal failed / project contract drift established / campaign stopped`

## 结果

clean/synced `61643293` 上唯一 DELL admission 已 exact-once 消费。SupervisorPlan 的 Provider transport 正常，`finish_reason=stop`，JSON 可解析；共 `1 call / 1 capture / 8,567 input / 1,228 output / 9,795 total`，估算 `USD 0.0072278`，retry/fallback=0。运行在 plan validator 以 `s2_06_supervisor_empty_case_authority` 终止，未进入七个 corrected graph node，candidate/hidden score/business promotion=0，raw mutation=0。

## 根因

模型准确返回 case/run identity、correction partitions 和六个要求的 node directive；五个 Specialist/Writer directive 选择了本案 Evidence/Numeric/Gap，Verifier directive 的 Evidence/Gap 为空。

这是项目内 Prompt/Schema/Validator 漂移：模型可见 JSON Schema 对三个 alias array 没有 `minItems`/组合约束，Prompt 只说“只能选择 supplied alias”，未说明每个 directive 必须至少一个 Evidence 或 Gap；本地 Validator 却在响应后强制这一隐藏规则。因此不能把 R1 记成 DeepSeek 不遵循指令，也不能把它计入 supervised recoverability 失败。

## 处置

R1 admission、capture、terminal 与 shared-ledger receipt 保持 immutable；不 retry、不重用 admission、不启动 MU/NVDA。按预注册 campaign 规则停止全 campaign，并使用唯一一个共享零调用结构修复包：将“Evidence 或 Gap 至少一个”从单一合同源编译进 schema、Prompt、validator、fixture、captured replay 和三案 mutation。通过 fresh proof 后才单独决定一次 DELL replacement；不得自动执行。

机器结果：`configs/releases/fin_ia_0_1_3_s2_06_dell_supervisor_r1_terminal_and_contract_drift_disposition_v1_0.json`。
