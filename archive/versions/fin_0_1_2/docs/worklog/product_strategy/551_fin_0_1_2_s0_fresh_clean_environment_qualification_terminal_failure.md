# FIN 0.1.2 S0 fresh clean-environment qualification 终态失败与项目级处置入口

日期：2026-08-02

任务：消费唯一一次 `FIN-0.1.2-S0-FRESH-CLEAN-ENVIRONMENT-QUALIFICATION-EXECUTION-AND-CLOSEOUT` 权限，在 clean/synced Git 基线上执行冻结的双 disposable qualification，独立读回全部受限证据并形成诚实终态；失败后不重跑、不现场修补、不自动创建 replacement attempt。

结果：`1/1 attempt terminal failed / no retry / S0 blocked / project-level disposition required`

## 1. 执行事实

- Project OS execution-scope preflight 通过，missing/blocker=`0/0`，摘要=`6a280dd...f9ff`；
- 执行前 branch=`codex/layered-data-source-expansion`、HEAD=`162ba5f...a1e`、HEAD=upstream、worktree clean；
- authority decision 摘要=`ec1b96e...027`，固定 attempt ID 与唯一离仓 output root 均匹配；
- 冻结命令仅执行一次，约 83 秒后终态 `failed`；attempt=`1/1 consumed`、retry/replacement=`0/0`；
- 凭据、模型、Provider、网络、业务调用=`0/0/0/0/0`；没有产生或晋升任何金融研究 Artifact；
- 运行前后仓库内容未变化，受限结果保存在 `D:/FIN_Insight_Agent_recovery/qualifications/fin_0_1_2_s0_clean_environment_qualification_20260802T080750Z_head_56732cd9_r1`，不得作为业务事实或产品结果使用。

## 2. 结果与可复核证据

两套独立 disposable 的结果完全一致：

- tests=`45 passed / 54 failed`；其中 gating failures=`41`、historical findings=`13`；
- current suite all-green=`false`，raw parity=`false`，semantic normalization valid=`false/false`；
- 每套 semantic unknown absolute paths=`53`；
- 29/29 注册生产 Runtime resources 均存在，resource/compiler tests=`14/14 passed`；
- typed environment contract tests=`10/10 passed`，但真实 diagnostic projection 仍暴露路径规范化缺口；
- package 含 789 个 repository files；独立 readback 校验 897 个内容寻址引用、15,827,581 bytes；
- `.git`、`.codex_runtime` 被打入 package 的数量为 0，credential environment keys 已从子进程环境移除；
- reference-role compiler 记录 1063 observations、unknown=`0`，但 15/15 目标测试在到达预期行为前因依赖缺失而失败，故 RC-P36-094 只能记 partial，不能关闭。

关键证据摘要：package manifest=`b223219d...0f9`，verification=`d040be21...cf7`，disposable A terminal=`225d3e66...e6b`，disposable B terminal=`0f8ffadb...de8a`。

## 3. 第一可信根因

这不是 54 个独立字段问题，也不是 DeepSeek 不遵循指令。当前 manifest 把四种不同生命周期的检查当成同一个可在离仓 package 中执行的 suite：

1. 只在运行前成立的 authority 检查；
2. 依赖宿主机 `.git` 的 full-repository inventory 检查；
3. 应在 disposable 中执行的 current Runtime/contract 检查；
4. 只应读取和报告、不能反向阻断 current gate 的历史审计。

与此同时，package inventory compiler 只闭合 tracked Python prefix 与 JSON `ref/*_ref`，没有闭合 schema-owned `current_projection.source_paths` 和测试代码直接声明/组合出的 repository resources。只读审计至少发现 19 个直接测试依赖、6 个 current projection source paths，以及 2 个运行中组合出的 exact-admission dependencies 未入包。因此：

- authority test 在它授权的执行内部检查“attempt 尚未开始”，必然自我失效；
- host-only Git test 在无 `.git` 的 disposable 内执行，必然失败；
- 多个 current/历史测试在到达目标断言前先因文件缺失失败；
- Windows repr 双转义、`fixture://` path component 与未绑定 basetemp 又共同制造 53 条 semantic unknown path findings。

下一修复不能列 19 个文件做 allowlist，也不能为每个失败测试逐一 live 复证。正确边界是先做 project-level zero-call disposition，定义 phase-aware test topology 与 typed test-dependency compiler，再决定是否授权一个全新的资格 attempt。

## 4. 问题处置

- `RC-P36-090`：open，host-only Git inventory test 在 disposable 中复发；
- `RC-P36-091`：open，selected-test dependency closure 不完整且范围扩大；
- `RC-P36-092`：closed，29/29 注册 Runtime resources 与两套 14/14 resource tests 构成真实关闭证据；
- `RC-P36-093`：open，两套各 53 条 unknown absolute path findings；
- `RC-P36-094`：open/partial，compiler observation unknown=0，但目标测试没有完整到达；
- `RC-P36-095`：open，manifest 精确绑定成立，但 phase/dependency 不完整；
- `RC-P36-096`：closed，授权态被正确消费，attempt 在 current projection 外终态化，且没有自动版本升级；
- `RC-P36-097`：new/open，current manifest phase 与 test dependency closure 不完整的结构性首因。

## 5. 产品与阶段边界

- FIN 0.1.2 仍是唯一当前版本，没有创建 0.1.3、0.1.4 或改变 FIN 0.2 定义；
- S0 终态为 `blocked_project_level_disposition_required`，不是 pass，也不是 engineering pass 后可直接进入 S1；
- 合并后 FIN 0.1.2 的 S1–S5 尚未开始；
- 用户可见金融研究能力增量为 0，release qualification 仍为 false；
- 本次受限 raw evidence 只用于工程审计，不得自动进入 Artifact、产品比较或金融事实层。

## 6. 下一项

`FIN-0.1.2-S0-CLEAN-QUALIFICATION-FIRST-CREDIBLE-FAILURE-PROJECT-LEVEL-DISPOSITION-DECISION`

该项只允许零调用地决定结构修复范围、测试阶段归属、依赖编译合同和新的有限 proof budget；它不授权修复、第二次 qualification、模型调用、S1 entry 或版本跳跃。
