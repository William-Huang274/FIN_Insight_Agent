# FIN 0.1.3 S3：完整片段 Chat R1 的表面合同失败

## 结果

正式 R1 在 clean/synced `f2924eb3...` 上执行，authority、18 份输入、三类工具 schema、6 个全新 attempt ID 与输出身份均在 Provider 前通过校验。运行没有网络故障：thesis 分析返回可见内容，随后交卷节点返回一个完整 Tool Call。系统在第 2 次模型调用后按 `0 retry` 停止，mechanism 与 counterargument/WWC 未被调用。

终态为 `terminal_failed_no_retry`，失败码为 `finance_loop_micro_narrative_invalid`。已用 2/6 次模型调用，0 个片段被晋升，所有请求与原始响应已先保存到本地 capture；私有完整结果留在 Workbench private store，公开仓库只保存红acted 结果、摘要、digest 与处置。

## 业务上模型做对了什么

这次不是 AI 利润归因再次越界。模型选择了 Dell 管理层产品目标关系，只引用对应法说 Evidence 和 source-bound QF，把权限限定为“管理层说法”，并明确该表述未经独立审计、不能证明产品到分部或公司利润桥。也就是说，当前可观察到的金融判断方向是受约束的，不能把本次失败记成内容 L1 已失败。

## 为什么仍然失败

模型在 `thesis_atom` 中重复了 QF 的“中个位数”定性区间。长期终局合同要求模型只选择 QF，最终报告由 Harness 在 atom 外渲染定性数值表面，避免文字区间在不同片段被复制、改写或悄悄锐化成点估计。因此本地 Validator 正确拒绝了这段文字。

真正的最早责任层是片段合同编译：

1. 分析上下文允许模型读取和讨论该定性区间；
2. 交卷 system 只说“不要新增数字”，没有说“不要复制分析中已有的文字数值区间”；
3. Tool Schema 只写了 `without digits or refs`，没有说明文字区间同样禁止；
4. 完整 model view 原本已有“选 QF、本地渲染”的规则，但片段投影 v1.0 丢掉了它。

所以模型遵守了它真正看见的大部分合同，Validator 也遵守了长期金融真值合同；两者冲突来自项目自己的投影不完整。不能把它归咎为 Provider 连通性，也不应为 DeepSeek 在核心 Runtime 增加特殊字段分支。

## 处置

- R1 authority、结果和本地 capture 均保持不可变，不手工删除“中个位数”后冒充成功。
- 片段上下文升级为 provider-neutral 的 surface contract：明确区分“分析可看值”和“交卷只选引用”。
- thesis、mechanism、counterargument 和 WWC 共用同一禁止表面说明；Tool Schema、submission prompt 和本地 Validator 必须一致。
- good path 必须证明：模型 atom 只写“其所述目标”，QF ref 仍被选择，最终 deliverable 仍会展示 source-bound 定性区间与 qualifier；这不是删除数字信息。
- 对保存的 R1 Tool Call 做零网络 replay，确认仍按原原因拒绝；再做三片段 full-fake、mutation、两个 fresh process 复证。
- 只有 clean/synced proof 通过后，才以 R2 新 Run/Attempt ID 执行一次完整 fixed-Pack；不在 R1 内 retry。

## 阶段边界

本次仍属于第一层 fixed-Pack 模型能力隔离测试。完整 Judgment、动态 Truth Spine、DELL 五单元、MU/NVDA 与异质留出案例泛化、人工内容验收及 S3 均未通过。

## Surface Contract v1.1 复证

provider-neutral 修复已提交并推送为 `9e1c80b6...`。片段 projection v1.1 现在把相同的 structured surface contract 注入 thesis、mechanism 与 counterargument/WWC；Tool Schema、submission system 和本地 Validator 对 digits、单位、日期、ref、URL 与 verbal numeric band 使用同一边界。Authority v1.1 还必须绑定 FFJ-R1 失败结果及独立 assessment，不能绕过旧失败签发新身份。

两个 fresh process 的输出逐字节一致，proof digest=`aed78f40...20f2`。保存的 FFJ-R1 Tool Call replay 仍以 `finance_loop_micro_narrative_invalid` 拒绝；同形 verbal-numeric mutation 也拒绝。合法 full-fake 的模型 atom 不含该表面，但最终 deliverable 继续确定性展示 `QF::DELL::AI_SERVER_OPERATING_INCOME_RATE_TARGET::FY2027Q1` 的“中个位数经营利润率目标”，证明修复没有丢失金融信息。

定向 60 tests、全仓 332 tests、compileall、active baseline `127 / 8 / 10 / 0` 和 secret scan `6,624 / 0` 通过；模型、网络、Provider、外源与 embedding 调用均为 0。正式 v1.1 proof、disposition 与 R2 scope decision 已物化；下一步是 clean commit/push、真实 Project OS preflight 和一个全新 R2 authority。
