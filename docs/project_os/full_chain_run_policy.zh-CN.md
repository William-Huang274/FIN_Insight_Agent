# Full-Chain / Expensive Eval Run Policy

## 默认原则

full-chain 是集成验收工具，不是日常 debugging 工具。

付费 full-chain 之前必须先证明：

1. deterministic / node-level tests 能覆盖的问题已经修完；
2. Project OS root-cause blockers 不阻断本次已注册运行范围；
3. token-budget preflight 通过或用户明确批准诊断性 override；
4. provider health preflight 通过；
5. 需要真实检索的 case 必须启用 real evidence operators；
6. 如果运行声称完整真实产品链或产品资格，S1 的 source／capture、OCR／parser／cleaning、chunk／object、index、query／route、recall、rerank、金融精排／Evidence admission、Coverage／gap、异质留出和稳定性独立资格已经通过；
7. 运行结果能写回 run audit / artifact refs / AIE / data-script audit。

DELL／MU／NVDA 的局部或节点 canary 可以在明确 decision-bound、diagnostic-only 且不声称 S1／完整链通过时单独签发。它们不能替代 S1 独立资格，也不能因为某个案例得到可用 Pack 就自动解锁完整真实产品链。

## 当前干净基线：decision-bound preflight（v1.1，2026-08-15）

严格重定基已经归档旧的多 Agent preflight 实现与全局 run-scope registry。当前基线不能恢复旧脚本和旧注册表来获得表面上的“预检通过”，而是通过
`scripts/eval_multi_agent/run_project_os_full_chain_preflight.py --decision <decision-ref>`
执行与当前决策绑定的预检。

当前预检必须同时证明：

- decision、零调用 proof、历史失败、Provider profile 与最近完整 Provider capture 的 SHA / result digest 不漂移；
- root-cause ledger 对该**精确 scope**没有阻断，或显式把该 scope 列为 allowed；
- 调用数、传输次数、每次与总输出 token、EvidenceRequest、retry、fallback 都有界；
- 只检查凭据是否存在，不读取、输出或保存凭据值；
- 对固定 Evidence Pack 的模型分析测试，必须明确标为 unit test，并将动态检索、五单元、发布和产品验收全部置为 false；
- 执行前仓库 clean 且与 upstream 同步。

这个 preflight 仍只是必要条件，不替代 exact-live authority、runner 输入 digest、capture-first 和 exact-once 约束。

## 历史规则：Typed state 与 scope registry（v1.0，只读）

- `configs/runtime/fin_ia_project_os_run_scope_registry_v1_0.json` 属于 pre-FIN-0.1.3 历史实现，已经归档，不得作为当前 Runtime 依赖；以下条款只用于解释旧运行证据。
- `v2_191` 之后的新 root-cause projection 必须写入 `blocker_state`、`run_scope_registry_version`、`owner_stage` 与 `previous_projection_sequence`；缺失、未知、版本漂移或 owner/scope 不匹配均为合同错误。
- canonical blocker state 为 `open / mitigated_open / blocked_external / closed / superseded`；前三者开放且阻断，后两者关闭。历史自由字符串只读兼容，未知的 historical full-chain blocker 按 open 处理。
- scope 的父级 block/allow 可覆盖注册子 scope；wildcard 只允许出现在 blocking side。
- diagnostic override 只能用于显式 open blocker 的受控诊断，不能覆盖 registry、state、owner 或 lineage 合同错误。
- Project OS preflight 是必要条件，不替代 exact admission、runner/source SHA、预算、result path 和 exact-once binding。

## 禁跑条件

- root-cause issue ledger 存在开放 canonical `blocker_state`，且该 issue 的注册 `blocking_run_scopes` 覆盖本次 `run_scope`。
- run scope 未登记、登记版本不匹配、scope non-executable，或 post-adoption projection 未满足 typed/lineage 合同。
- 未声明 `blocking_run_scopes` / `allowed_run_scopes` 的 open `full_chain_blocker` 默认阻断所有 paid/full-chain scope。
- broad full-chain、release eval、case expansion 不能借用单 case scope 通过。
- token 预算超限且没有用户明确批准。
- case 需要真实证据但只跑 dry-run evidence operators。
- 当前目标只是修 parser、formatter、selector、budget、schema 或 route，这些应先用 deterministic test。
- S1 标准范式或独立评测尚未通过，却准备运行声称产品资格的完整 `user→S3→S1→S2→S3→S4` 链路。
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
