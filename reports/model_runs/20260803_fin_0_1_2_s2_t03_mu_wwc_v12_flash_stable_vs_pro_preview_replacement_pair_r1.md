# FIN 0.1.2 S2-T03 MU WWC v1.2 Flash stable vs Pro preview replacement pair R1

- 日期：2026-08-03
- 类型：paired natural-output affected-family replacement canary
- 状态：`two terminal complete / both hard-integrity pass / fair T04 input restored`
- Git：`5d94754a`
- 路由：DeepSeek official beta Chat Completions JSON-object；thinking disabled；temperature 0；stream false
- 模型：`deepseek-v4-flash` stable、`deepseek-v4-pro` preview
- 输入：MU `demand_authenticity_and_sustainability` 的 WWC v1.2 同一请求；Fact/Claim 未重跑

## 运行结果

两次固定调用均以一次 transport attempt 返回 `finish_reason=stop`，并在本地 semantic validation 前分别原子保存完整模型可见请求和最终 assistant 输出。Flash 与 Pro 都通过 native JSON、alias/enum、cadence/date、容量、row-local Claim/Authority、本地 assembly 和 terminal-result 门禁。

Flash usage=`1845/425/2270`，延迟 `3291 ms`；Pro usage=`1845/354/2199`，延迟 `3840 ms`。合计 input/output=`3690/779`，按冻结费率估算 `USD 0.00228288`，最终费用以 Provider 账单为准。restricted capture/terminal=`2/2`；retry/fallback/provider hopping/prompt-only retry/Fact-or-Claim rerun/business Artifact=`0/0/0/0/0/0`。

## 结论

RC-P36-102 的模型可见 cadence/date parity 与 RC-P36-103 的逐 atom Claim/Authority 绑定均获得真实自然输出正证据，公平 WWC pair 已恢复。结合原六调用中有效的四份 Fact/Claim 结果，T04 现在有六份 hard-integrity pass 输入。

本项不做正式盲评或模型选择。仅记录未评分观察：Flash 的三个任务多次把全部 9 个权威来源合并，主要选择 `unknown/no_change`；Pro 将正向、反向和图谱证据分组，并给出 `strengthen/weaken/resolve_cannot_infer`。两者都出现合同允许的 `bound_date`，其本地日期不晚于输入 `as_of`，应在 T04 的“决策有用性”中评价，不能事后改成 T03 硬失败。

受限原始证据位于 `.codex_runtime/fin012-s2-t03-mu-wwc-v12-replacement-pair-r1`，不追踪、不晋升为业务事实。T04、模型选择、S2 closeout、S3 和 full-chain 均未在本项执行。
