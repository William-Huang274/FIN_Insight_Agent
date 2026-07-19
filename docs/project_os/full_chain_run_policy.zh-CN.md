# Full-Chain / Expensive Eval Run Policy

## 默认原则

full-chain 是集成验收工具，不是日常 debugging 工具。

付费 full-chain 之前必须先证明：

1. deterministic / node-level tests 能覆盖的问题已经修完；
2. Project OS root-cause blockers 不阻断本次运行范围；
3. token-budget preflight 通过或用户明确批准诊断性 override；
4. provider health preflight 通过；
5. 需要真实检索的 case 必须启用 real evidence operators；
6. 运行结果能写回 run audit / artifact refs / AIE / data-script audit。

## 禁跑条件

- root-cause issue ledger 存在 `full_chain_blocker=true` 且 status 为 open/active/blocked，并且该 issue 的 `blocking_run_scopes` 覆盖本次 `run_scope`。
- 未声明 `blocking_run_scopes` / `allowed_run_scopes` 的 open `full_chain_blocker` 默认阻断所有 paid/full-chain scope。
- broad full-chain、release eval、case expansion 不能借用单 case scope 通过。
- token 预算超限且没有用户明确批准。
- case 需要真实证据但只跑 dry-run evidence operators。
- 当前目标只是修 parser、formatter、selector、budget、schema 或 route，这些应先用 deterministic test。
- 上一轮 full-chain 暴露的问题还没有 root-cause row 和修复证据。

## 可跑条件

- 单 case 已通过 Project OS preflight，且本次 `run_scope` 与 case objective contract 一致。
- 对 P33 AI/Semis gold case，允许的受控 scope 是 `p33_single_gold_case`；它只能进入 token / provider / real-evidence / AIE / data-script preflights 和一个 real-evidence paid case，不能扩大为 20-50 case 或 release eval。
- token budget / paid call budget 在限额内。
- data/script audit 和 AIE 的已知 blocker 已关闭或与本 case 无关。
- 运行目的明确：验证修复后的真实 artifact，而不是泛泛“看效果”。

## 输出要求

每次有效 full-chain 必须产出：

- run id / case id；
- token/cost/provider events；
- evidence/operator trace；
- Research Lead / specialist / Memo Writer / Verifier route summaries；
- Claim/JudgmentCard、MemoLogicPlan、rendered memo；
- AIE audit、data-script audit、output-quality audit；
- 如果失败，写入 `root_cause_issue_ledger.jsonl` 或更新已有 issue。
