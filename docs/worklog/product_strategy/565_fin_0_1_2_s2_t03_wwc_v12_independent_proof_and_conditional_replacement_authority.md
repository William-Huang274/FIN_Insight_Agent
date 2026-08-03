# FIN 0.1.2 S2-T03 WWC v1.2 独立复证与条件 replacement authority

日期：2026-08-03
状态：`independent proof pass / conditional authority issued / execution not authorized`

## 问题与决定

上一包只证明当前工作树内的 WWC v1.2 工程实现通过，不能直接据此进行真实 replacement。用户以“继续”授权本项：独立零调用复证，并决定是否签发最多两次 MU WWC replacement 权限。

复证通过后选择“有条件签权”：两调用只有在专用 runner 与 atomic capture 零调用 preflight 通过后才生效；本项不读取凭据、不调用模型，也不进入 T04。

## 完成内容

- 新增 proof generator，在两个 fresh Python process、两个 distinct disposable roots 中运行；
- 清除 credential 环境并安装 network deny guard；
- 重验 8 项 implementation binding、v1.1 immutable source/binding、日期正负矩阵、逐行 Claim/Authority、provider permutation、6→3 selection、受限形状重放和 DELL/MU/NVDA 三案 fake；
- 两份 normalized output 逐字节相同，target binding fingerprint 前后不变；
- 冻结 MU WWC Flash/Pro exact two-call plan、request/equivalence digest、预算、capture 与停止规则；
- 保留 RC-P36-102/103 为 open，等待公平自然 WWC replacement 输出。

## 证据

- 独立 proof processes/roots：`2 / 2`；
- proof result digest：`5a0b542f...b7fa85`；
- request/equivalence digest：`0c52c9ab...81c2 / 543836b6...de90`；
- 三案 full-fake：DELL/MU/NVDA 各 `6/6`；
- focused proof/governance tests：`6 passed / 0 failed`；
- S1/S4 compiler/S2/T03 受影响回归：`144 passed / 0 failed`；
- credential/model/Provider/network/replacement/business Run/Artifact：`0`。

第一次工具启动使用 `python -I` 时在导入 pytest 阶段因用户级 `pygments` 被隔离而 fail-closed；未进入证明矩阵、未读取凭据、未调用模型，也未消费 authority。根因修正为 fresh interpreter + 独立 TEMP/TMP + credential scrub + network deny，再正式执行两次 proof 并通过。该启动兼容问题不属于 WWC 合同或模型失败。

## 条件权限

- case/family：`MU / what_would_change_atoms`；
- candidates：Flash stable、Pro preview，各一次；
- Fact/Claim rerun：禁止；
- retry/fallback/provider hopping/prompt-only retry：全部 0；
- ceiling：`2 calls / 10k input / 2.8k output / USD 0.015 / 300s`；
- 当前 execution：未授权；
- T04/model selection：未授权。

## 下一项

`FIN-0.1.2-S2-T03-WWC-V1.2-REPLACEMENT-PAIR-BOUND-RUNNER-ATOMIC-CAPTURE-AND-ZERO-CALL-PREFLIGHT-MINIMUM-IMPLEMENTATION`

下一项只实现和验证 two-call runner，不执行真实模型调用。runner/preflight 失败即停止；不得复用 v1.1 六调用 authority，也不得自动开启第二修复包。
