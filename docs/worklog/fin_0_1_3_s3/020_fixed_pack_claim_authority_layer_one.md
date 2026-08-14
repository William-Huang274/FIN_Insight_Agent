# FIN 0.1.3 S3 固定 Pack 第一层 Claim Authority

日期：2026-08-14

状态：`formal_zero_call_proof_pass / one_fixed_pack_chat_terminal_failed_no_retry / raw_content_materially_improved / layer_one_not_accepted / layer_two_blocked`

## Owner 决定

Owner 接受三层验收，但只批准先完成第一层并返回结果：fixed Pack 只测试给定资料下的模型分析能力；DELL 单单元动态纵切等待第一层结果后另行决定；DELL 五单元动态案例继续 blocked。

## 已实现

- 保留历史 v1.2 输入和 R2 不可变，以 overlay 方式新增 provider-neutral claim authority；
- 模型必须声明 claim scope、financial scope、causal bridge authority；
- 当前 Pack 未提供产品到分部／公司的直接桥，因此该权限不向模型暴露；
- 模型仍独立撰写 thesis、mechanism、counterargument 和 WWC；
- 固定 Pack loop 的 EvidenceRequest 预算收敛为零；
- 保存的 R2 强归因 Judgment 已纳入负向 replay；
- 定向测试已覆盖正向 bounded judgment、直接桥冒充、错 scope、管理层陈述缺引用和跨层强因果表面。

## 当前证据

- `tests/test_s3_current_research_consumer.py`
- `tests/test_s3_bounded_finance_loop.py`
- 定向 consumer／loop／canary tests：`66 passed`
- 全量 Python tests：`289 passed`
- active baseline：`124 Python / 8 frontend / 10 Runtime resources / 0 forbidden reference`
- secret scan：`6,561 files / 0 finding`
- formal zero-call proof：`engineering_pass_zero_call_fixed_pack_claim_authority`
- 保存 R2 负向 replay 的拒绝码：`claim_authority_cross_scope_causal_language_unbound`
- 固定 Pack fake loop：`2 steps / 3 tool calls / 0 EvidenceRequest / 0 model call`
- 新 DeepSeek live 尚未执行；本记录之后只允许签发一次固定 Pack Chat canary。

## 停止线

formal zero-call proof 已通过，唯一一次 Chat live 也已执行并终止。运行完成 Evidence／NumericFact 并行读取和一次 Judgment 提交，共 2 次模型调用、0 EvidenceRequest、0 retry；首个硬失败为 `research_consumer_thesis_atom_invalid`。

模型复述了 reviewed Evidence 明确允许引用的“中个位数”管理层目标，但旧叙事 validator 禁止汉字数值区间，且当前输入没有 typed range／management-target alias。零调用尸检证明仅移除该区间表面后，同一输出通过现有 validator；该回放只用于定位，不追认失败输出。

原始内容较 R2 明显改善：不再把公司／分部利润归因于 AI 服务器，不再发明半固定成本，明确限定为产品级 management assertion，并保留价格、数量和 PVM 缺口。原始内容诊断为 `21/24`，但因没有合同有效 Judgment，正式 L1、第一层 acceptance 和产品发布均为 false。

必须先返回 Owner。第二层继续 blocked；不允许自动修改后重跑。若 Owner 继续，建议先做 source-bound qualitative range／management-target alias 与结构化 claim relation 的零调用处置。
