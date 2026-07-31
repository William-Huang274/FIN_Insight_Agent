# FIN 0.1 S4-T08 三案例校准与 Workbench 产品价值边界

状态：`T08 read-only calibration pass / S4 not passed / FIN 0.1 not qualified`

日期：2026-07-31

## 1. 结论

当前产品已经证明“一案可接受、三案均有分析增益迹象”，但尚未证明“三案均可交付”。

- NVDA：历史 S3 R2 已通过 L1，并由 owner 接受；它不是 post-transfer R3。
- DELL：完整 6 节点、12 次调用、9 Artifact 曾技术成功，但独立 paired review
  发现重要数字与绑定 authority 不一致、标题错写 NVDA，R2 不成立。
- MU：完整 6 节点、12 次调用、9 Artifact 曾技术成功，但独立 paired review
  同样发现重要数字不一致与标题错写 NVDA，R2 不成立。
- T07：当前代码下三案主路径在既有 package 内通过，但总回归为
  `93 passed / 4 failed`，因此没有新 NVDA exact product 或 R3 candidate。

这意味着 Agent 的“分析组织能力”和“金融产品可采信性”必须分别评价。三案都显示
Agent 比确定性底稿提供更多 what-would-change、跨单元依赖、冲突和 gap，但只有 NVDA
的这部分增益通过了 L1 并成为可接受产品证据。

## 2. 三案例产品校准

| Case | 最强完整结果 | L1 | Agent 增益 | 产品成熟度 |
| --- | --- | --- | --- | --- |
| NVDA | 6 nodes / 12 calls / 9 Artifacts | pass | 可行动性、跨单元综合显著优于 baseline | 历史 S3 R2 owner accepted；非 R3 |
| DELL | 6 / 12 / 9，随后 paired L1 fail | 数字 authority、案例身份失败 | 存在，但不具可采信性 | R2 未证明，owner 不具资格 |
| MU | 6 / 12 / 9，随后 paired L1 fail | 数字 authority、案例身份失败 | 存在，但不具可采信性 | R2 未证明，owner 不具资格 |

三条选定的完整成功 Run 合计：

- model/provider calls：36；
- input/output/total tokens：`192,515 / 20,103 / 212,618`；
- estimated cost：`USD 0.08207367`；
- 生成 Agent Artifacts：27；
- 最终 owner-accepted Artifacts：9，仅来自 NVDA。

这三个观察不能直接推导平均单案成本、规模化单位经济或稳定成功率。DELL 与 NVDA
没有在所绑定证据中保留可比延迟；MU 完整成功 Run 的 12 条 receipt latency
合计为 `120,474 ms`，因此目前也不能做三案延迟对比。

## 3. 重复出现的正向能力

相对于只保留事实和 typed gap 的确定性底稿，Agent 在三个完整 paired 输出中都产生了：

- 更多可执行的 what-would-change 任务；
- 明确的跨 Cell 依赖；
- 冲突裁决和剩余 gap；
- 更强的跨单元综合叙事。

这证明 Agent 层不是“没有价值”。它已经具备把结构化证据整理成研究行动面的能力。
但是这项能力只有在 L1 真实性、引用与案例身份全部通过之后，才可以晋升为产品价值。

## 4. 重复出现的负向能力

DELL 与 MU 的共同失败比单个字段错误更重要：

- 模型生成的重要数字没有与绑定 Numeric authority 精确一致；
- 报告标题由项目代码错误地继承 NVDA；
- machine Verifier 两次把这些错误误判为可供内部审阅；
- 用户若要使用结果，必须重新核对每个重要数字并修复案例身份。

因此，跨案例 transfer integrity 尚未成立。当前系统能够完成链路，不等于能够稳定生成
可采信的金融成品。

## 5. Workbench 产品价值

已证明的价值：

- 通过 immutable Artifact、lineage、restricted capture 和 typed terminal result，
  支持内部追踪、故障定位与审计；
- 能够把 Agent 输出与确定性 baseline 并排检查；
- 能揭示 machine Verifier false negative，而不是只保留“运行成功”状态。

尚未证明或仅有定性证据的价值：

| 维度 | 当前证据状态 | 结论 |
| --- | --- | --- |
| task time | 未测量 | 没有三案真实用户任务计时 |
| edit burden | 仅定性 | NVDA 中等；DELL/MU 高，但没有标准化或计时指标 |
| trust | 仅定性 | NVDA 有历史 owner acceptance；跨案信任因两次 L1 false negative 不成立 |
| continue-use | 未测量 | 没有真实用户持续使用观察或问卷 |
| trace/debug value | 已证明 | 对内部工程审阅和审计有效，但不等于终端研究产品价值 |

所以当前 Workbench 的准确定位是：
`内部研究工程 alpha 的 trace/review/debug surface`，不是已经完成三案校准的终端金融
研究产品。

## 6. 阶段处置

T08 以只读校准完成，不改变下列事实：

- DELL R2=false；
- MU R2=false；
- NVDA post-transfer product 不存在；
- NVDA qualified senior R3 未执行；
- S4 未通过；
- FIN 0.1 未达到 release qualification。

下一项是：

`S4-T09-REAL-HUMAN-OWNER-REVIEW-AND-QUALIFIED-SENIOR-ELIGIBILITY-SCOPE-DECISION`

T09 只能由真实 Human 完成。Owner 可以审阅已经存在的 exact product 与 blocked
evidence；但当前没有可供 qualified senior 签署为 NVDA R3 的 post-transfer
candidate。模型 Verifier、Codex、自评或 shadow reviewer 都不能代签。

## 7. 权威机器记录

- Scope：
  `configs/releases/fin_ia_0_1_s4_t08_read_only_three_case_calibration_and_workbench_product_value_scope_decision_v1_0.json`
- Result：
  `configs/releases/fin_ia_0_1_s4_t08_read_only_three_case_calibration_and_workbench_product_value_result_v1_0.json`
