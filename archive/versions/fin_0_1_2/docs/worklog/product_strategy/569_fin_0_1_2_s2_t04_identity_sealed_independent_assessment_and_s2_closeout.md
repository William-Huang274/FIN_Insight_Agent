# FIN 0.1.2 S2-T04：密封身份独立评审与 S2 收口

日期：2026-08-03

## 问题与决策

当前上下文已经看到 Flash/Pro 映射，不能自行完成可信盲评。用户确认由当前窗口统筹，并使用不继承历史的 fresh subagent 评分，无需人工另开窗口。

本轮没有重新调用 DeepSeek，也没有生成业务 Run 或 Artifact。当前任务只从六份已保存的 hard-pass capture 构建评审 packet；独立 subagent 属于评估上下文，不是产品 Runtime 的模型/Provider 调用。

## Packet 与隔离

- packet：`.codex_runtime/fin012-s2-t04-blind-assessment-r1/assessor-packet.json`
- packet SHA256：`63296b6334629fd9fd293a64bfe7c8842d1f743bb089cc74ffc7b9652f8b4b4b`
- mapping commitment：`sha256:f69e7c40ef2c4376e2b740d2ddd5ecfb780a8dcd5d1cbac2599ed498e2ba47fa`
- 映射包含随机 256-bit nonce，避免只有两种映射时被枚举反推；nonce 与 mapping 均不进入 packet 或 Git。
- packet 只保留案例、source/alias 上下文、固定 rubric 和 canonicalized outputs；模型/候选、call、receipt、digest、路径、延迟、tokens、成本、生命周期和此前方向性观察均排除。
- 10 项 packet/authority 测试通过；identity leakage、映射方向、nonce commitment、readback 和 one-shot identity 均覆盖。

独立 assessor 使用 `fork_turns=none`，只获准读取上述 packet 并先验证 SHA。它未获准读取聊天历史、Git、其他仓库/runtime 文件、mapping，未使用网络、外部源或其他 agent。该隔离足以支持内部 S2，但因为 subagent 与主任务共享文件系统，不声明为物理外部审计。

## 评分、冻结与解盲

盲分：

| family | candidate A | candidate B |
| --- | ---: | ---: |
| Fact | 4 | 5 |
| Claim | 7 | 7 |
| WWC | 7 | 1 |
| 总分 | 18 | 13 |

tracked label-only score SHA256=`ecaef3c3...99864`；canonical score object SHA256=`e78c1b7f...18a06`。validator 校验三 family、两个 label、四维 0–2 分、family/candidate totals、evidence 和 assessor attestation；score receipt 原子写入并 readback 后才读取 mapping。

解盲为 candidate A=`Pro preview`、candidate B=`Flash stable`。Pro 领先 5 分，超过 StagePlan 的 2 分阈值，因此全局候选选择 Pro preview。

## 模型与本地 surface 结果

- `specialist_fact_atoms`：Pro 4/8，但 epistemic discipline=0，未达到预先冻结的单维最低值；转本地确定性 Fact candidate selection 和 terminal calibration。
- `claim_candidate_atoms`：Pro 7/8；保留 request-local alias/enum atom surface。
- `what_would_change_atoms`：Pro 7/8；保留 request-local alias/enum atom surface，但 D001 早于 as-of、D002 等于 as-of 的 actionability finding 后传 S3，不重开 T03。
- 不允许自动 runtime fallback；S2 只做选择，不修改当前 runtime mainline。Pro 是 preview，生命周期/兼容性风险必须由 S3 StagePlan 管理。

第一次 deterministic finalization 的成本字段把 8 次历史调用总成本错误标成 6 份有效结果成本。该 runtime R1 保留但不作为权威结果；代码在同一实现轮修正为“8 次历史执行总成本＋6 次有效评分 tokens/latency”，使用同一 frozen score/mapping 生成 R2。评分、映射、选择和 surface disposition 均未变化。

## 收口与边界

- focused T04 tests=`20 passed`；当前适用 S2 回归=`100 passed`。
- 唯一未纳入当前回归的历史测试仍是已消费 admission 的 pre-execution preflight；文件保持 `11370 bytes`、SHA256=`d987940dbe68fba0196bd804f5cf6e450cb60729b89848bd3b5982bfb5b01615`，未删除或改写。
- 产品 Runtime model/provider/network calls=`0/0/0`；独立 evaluator contexts=`1`；业务 Artifact=`0`。
- RC-P36-104 在内部 S2 评估等级关闭。
- S2-T01/T02/T03/T04 全部完成，S2=`pass_closed`。
- S3 仅具备 StagePlan 入口，尚未开始；九件套、NVDA 产品锚点、DELL/MU 迁移、owner acceptance、release 和 production 均未证明。

下一项：

`FIN-0.1.2-S3-STAGE-PLAN-AND-BOUNDED-MODEL-SURFACE-ENTRY-DECISION`
