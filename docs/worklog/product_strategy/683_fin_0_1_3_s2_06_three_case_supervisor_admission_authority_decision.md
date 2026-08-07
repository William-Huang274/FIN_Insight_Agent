# 683 — FIN 0.1.3 S2-06 三案例 Supervisor admission authority decision

日期：2026-08-07

状态：`authority pass / bounded sequential campaign approved / admissions unissued / execution not started`

## 决策

上一项独立 fresh proof 已在两个 clean Git archive、两个 fresh Python process 和三案真实冻结输入上复现通过。更早的四个项目内签发 blocker——case-qualified correction、citation/coverage typed owner、dependency-aware corrected runner、candidate freeze 后评分——也已由唯一共享结构包关闭。因此继续拒绝真实测量已没有新的项目内证据；本轮批准一个有界的三案例 Supervisor 恢复实验。

本项只完成 authority decision，没有签发 admission、没有调用 DeepSeek/Provider/网络、没有生成 corrected candidate、没有 hidden score 或业务晋升。下一步仍需在 clean/synced commit 上单独签发并执行首案 DELL。

验证结果：authority focused=`4 passed`；Supervisor boundary/runtime/fresh-proof/前后 authority 组合=`35 passed`；S2-05/S2-06 扩大回归=`126 passed / 3,201 deselected`；JSON/JSONL parse 与 `git diff --check` 通过。

## 不是“三次调用”

DELL、MU、NVDA 是三个物理隔离案例，不是三次 Provider 请求。真实 frozen dependency closure 的预计调用为：

- DELL：`1 SupervisorPlan + 7 corrected graph = 8`；
- MU：`1 + 9 = 10`；
- NVDA：`1 + 9 = 10`；
- campaign 预计 `28`，硬上限 `33`，每案硬上限 `11`。

每案成本硬上限 `USD 0.18`，campaign `USD 0.54`；retry/fallback/provider hopping=`0/0/false`。每案使用新的 Run、Attempt、runtime root 和 case-local admission；只有上一案 terminal 已分类后才可签发下一案。

## 停止与继续规则

共享身份、权限、hidden/cross-case 泄漏、capture、预算、raw mutation 或 lineage 缺陷会立即停止整个 campaign，并留在 S2-06 修根因。已排除共享原因后的 case-local 模型/schema/内容失败会原样保存，不 retry、不现场改 Prompt；为了得到完整三案能力分布，可以继续另两个隔离案例。

不得再次进入逐字段 live 修补。若 campaign 暴露项目内共同根因，最多允许一个共享结构修复包；只有项目缺陷使某案测量无效时，才可另行决定该案最多一次 replacement。

## 验收边界

逐案必须有 fresh identity 与完整 lineage，evaluator v1.4 `L1=0/L2=0`，关闭空反证与未校准阈值，修复 citation-role，并由 Verifier 覆盖此前 material finding class。candidate freeze 后才可运行 hidden Gold 与八维内容质量评分。三案全过且保留实质内容增益才可称 `supervised_recoverability=proven`；部分通过不能平均为通过。

即使三案全过，也只证明同证据条件下的受监督恢复，不证明 autonomous raw success、Agentic Search、current-source 产品链、qualified-human acceptance 或 release。

## Portability finding

RC-P36-146 不阻断当前 Windows 同主机实验，但继续阻断跨平台与 release 声明。历史 CRLF 字节绑定保持 immutable；S5 必须为新合同改用 canonical JSON/normalized digest，并补 Windows/Linux clean-checkout parity proof。

机器决策：`configs/releases/fin_ia_0_1_3_s2_06_three_case_supervisor_admission_authority_decision_v1_0.json`。

下一项：`FIN-0.1.3-013-S2-06-DELL-SUPERVISOR-ADMISSION-ISSUANCE-AND-EXACT-ONCE-EXECUTION`。本项未自动授权执行。
