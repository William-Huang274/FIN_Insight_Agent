# FIN 0.1.3 S3 固定 Pack 第一层 Claim Authority

日期：2026-08-14

状态：`claim_surface_formal_zero_call_R3_pass / natural_replacement_not_run / layer_one_not_accepted / layer_two_blocked`

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

## Owner 继续后的零调用 successor

Owner 要求继续，但未授权新的 DeepSeek live 或动态第二层。本轮在同一第一层内实现 `Claim Surface Authority`：

- reviewed 管理层定性目标编译为 source-bound QF，而不是加入文字白名单或伪装成精确 NumericFact；
- thesis／mechanism／counterargument 三个判断原子分别提交结构化 subject、outcome、relation、attribution 和 scope；
- Tool Schema、model-visible view、validator、fake loop 与 deliverable 继续由同一 consumer 合同投影；
- Harness 只展示 QF surface／qualifier 和结构 receipt，不生成模型结论；
- 保存的失败 payload、DELL／MU／NVDA case 污染、source digest、错 relation、缺支持 Evidence 和强因果表面进入零调用回放／mutation。

working-tree 定向回归为 `76 passed`。回放还纠正了一个初始设计：单个 cell-level structured relation 不能覆盖三段文字；旧输出的 thesis、mechanism 与 counterargument 实际承诺不同，因此 successor 改为每个 narrative atom 一条关系。formal clean proof 必须在实现提交和上游完全一致后另行签发；在该 proof 前，第一层、第二层与 S3 产品验收继续为 false。

## Formal zero-call proof 尝试与最终结果

- R1：在写出结果前以 `claim_surface_mutation_disposition_invalid` 终止。原因不是产品合同失败，而是 proof runner 的“缺指定来源权威”mutation 同时移除了全部 generic support，导致先撞到 `research_consumer_supported_judgment_without_evidence`。authority、实际四个返回码和 0-call 边界已不可变保存。
- R2：修正 mutation 顺序后，核心工程证明通过；但公共结果的 `recorded_at` 仍沿用 predecessor 的 `2026-08-14` 固定值。R2 结果保持不可变，只登记为“证明逻辑通过、最终审计元数据需要 successor”。
- R3：把公共 `recorded_at` 确定性绑定到 signed authority `issued_at` 后，在 clean/synced commit `022fcfeb...f563` 正式通过。结果为 `engineering_pass_zero_call_claim_surface_authority`；source-bound QF、三条逐原子关系、三层旧失败回放、四类 mutation、source drift、DELL→MU/NVDA 隔离和 deterministic recompile 全部通过。

R3 的自然调用计数仍为 0。它没有证明 DeepSeek 能自然使用 QF／claim relation，也没有接受 fixed-Pack 第一层。下一步必须先返回 Owner；若 Owner 继续，只能另行决定是否值得签发一次 replacement fixed-Pack live。不能自动进入动态第二层或五单元。

最终仓库复证：S3 定向 `76 passed`，全量 Python `299 passed`；active baseline 为 `125 Python / 8 frontend / 10 Runtime resources / 0 forbidden reference`；secret scan 为 `6,580 files / 0 finding`。一次全量回归曾发生 Workbench 异步 import-graph 15 秒窗口超时，单独复跑通过，最终非并发全量也通过，因此记为负载抖动，不扩大本工作包或修改产品超时。
