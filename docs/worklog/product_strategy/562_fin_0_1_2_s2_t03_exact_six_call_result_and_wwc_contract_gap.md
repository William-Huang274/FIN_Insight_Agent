# FIN 0.1.2 S2-T03 exact 六调用结果与 WWC 合同缺口

日期：2026-08-03
状态：`six terminal results complete / capability ranking blocked / zero-call disposition next`

## 本轮做了什么

在 clean/synced HEAD `0872f8d2cd1cb1ce5cb838881ce159638491cd1a` 上消费既有 exact authority，通过专用 runner 执行 MU 的 Fact、Claim、WWC × Flash stable、Pro preview 共六个调用。没有额外 health call、retry、fallback、provider hopping、prompt-only retry、replacement pair 或业务 Run/Artifact。

六个调用均一次 transport 返回 `finish_reason=stop`；原子保存 6 个受限 capture 与 6 个 terminal result。总 usage=`9106 input / 1021 output`，冻结费率估算成本=`USD 0.00484938`，Provider 账单为外部最终真值。

## 结果

- Fact：Flash、Pro 均本地 hard pass；
- Claim：Flash、Pro 均本地 hard pass；
- WWC：Pro hard pass；Flash 在 post-provider local semantic validation 失败，code=`s4_compiled_wwc_unbound_date_alias_forbidden`；
- 受限原始证据完整保留，但不进入 Git、Artifact 或金融事实。

审计发现 Flash 没有输出 raw date 或未知 alias。它为 `next_authority_event` / `next_reporting_event` cadence 选择了已允许的 `D002`。模型可见 schema 明确写的是 `review_date_alias: exact allowed date alias or NONE`，却没有写本地 validator 的跨字段条件：只有 `bound_date` cadence 可以携带日期 alias，其他 cadence 必须为 `NONE`。Pro 恰好满足隐藏条件，不代表比较公平。

## 判断与边界

登记 `RC-P36-102-fin-0-1-2-s2-t03-wwc-review-cadence-date-alias-model-visible-contract-parity-gap`。这是项目内 prompt/schema/validator semantic parity 缺口，未建立 Flash、Pro、DeepSeek 或 Provider 过错。

本轮完成“六个 terminal/capture 物化”，但没有完成公平的三 family capability measurement。不得进入 T04 盲评、不得选择 Pro、不得自动修补后重跑。按 StagePlan 已冻结的止损边界，最多只允许一个合并零调用 repair，以及经另行授权的一次 WWC Flash/Pro replacement pair。

当前下一项：

`FIN-0.1.2-S2-T03-WWC-REVIEW-CADENCE-DATE-ALIAS-MODEL-VISIBLE-CONTRACT-PARITY-AND-AFFECTED-FAMILY-REPLACEMENT-PAIR-DISPOSITION-DECISION`

该项只做项目级零调用处置，不在同一轮实现或调用模型。

## 收口验证

- T02 compiler、T03 preflight 历史投影与本次 execution-result/current-projection/backlog 定向合同回归：`33 passed / 0 failed`；
- Project OS 对当前零调用 disposition scope：`pass / 0 blockers`；
- JSON/JSONL 全量解析：pass；`git diff --check`：pass；
- 扩展到整个 `tests/contract -m fast_contract` 的非必要检查因长时间无终态被人工终止，不记录为通过或失败，也不替代上述定向门禁。
