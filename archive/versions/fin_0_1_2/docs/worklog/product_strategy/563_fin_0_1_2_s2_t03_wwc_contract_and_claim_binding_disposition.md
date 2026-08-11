# FIN 0.1.2 S2-T03 WWC 合同与 Claim 绑定零调用处置

日期：2026-08-03
状态：`decision pass / one consolidated repair selected / implementation not authorized`

## 问题

上一轮证明 Flash WWC 被模型不可见的 cadence/date 跨字段条件拒绝。用户同意先做合同一致性结构处置，而不是直接把 Pro 判为胜者。

## 新发现

处置期间检查最早 owner 时发现 `_assemble_wwc` 还有一个同 family 的项目缺陷：最终创建 tasks 的循环读取外层候选循环结束后的 `claim_alias`，而不是当前 selected atom 的 alias。

使用 Pro 受限 capture 零调用重放确认：raw aliases=`Q001/Q002/Q001`，映射本应覆盖 `local_claim:001/002`，但三个最终 tasks 的 `claim_id` 全部为 `local_claim:001`，同时 terminal 仍为 pass。这使 Pro WWC 也不能作为公平能力证据。原始内容没有复制到公开决定，只记录 capture digest、alias 和绑定计数。

## 决定

RC-P36-102 与新 RC-P36-103 属于同一个 S2-T03 WWC comparator owner，不拆成两轮修补。唯一实现包=`fin_0_1_2.S2.WWC_model_visible_contract_and_row_local_claim_binding:v2`：

- 同一 typed rule 生成 cadence/date 的 prompt/schema/validator/fake/mutation 语义；
- `bound_date` 必须有 allowed date alias，其他 cadence 必须为 `NONE`；
- 每个 task 只从自己的 selected atom 展开 Claim ID；
- 覆盖 DELL/MU/NVDA full-fake、日期正负矩阵、多 Claim、重排、permutation、subset 和受限 Pro replay；
- 不改 Fact/Claim、不放宽 numeric/date/identity/lineage，不做广义 compiler 重写。

六调用历史 terminal 不改写，但公平能力证据从 5 个 pass 更正为 4 个有效 Fact/Claim outcomes；WWC 两项均无效。实现和独立 proof 通过后，才可单独审查最多 2 次 MU WWC replacement calls。若再出现新项目缺陷，S2 honest block，不开启第二实现包。

## 本轮边界

runtime code、credential、model、Provider、network、replacement admission/call、T04、Artifact=`0`。本轮只生成 decision、current projection、Project OS/计划/backlog 和 deterministic governance test。

当前下一项：

`FIN-0.1.2-S2-T03-WWC-CONTRACT-PARITY-AND-ROW-LOCAL-CLAIM-BINDING-CONSOLIDATED-ZERO-CALL-IMPLEMENTATION`

该实现尚未由本决定自动授权。

## 验证

- decision、projection、backlog JSON 解析：pass；
- root-cause、capability、external-pattern JSONL 全量解析：pass；
- T02/T03 历史证据、exact result 与本次 disposition 闭环：`37 passed / 0 failed`；
- Project OS 当前 disposition scope：`pass / 0 blockers`；
- `git diff --check`：pass。
