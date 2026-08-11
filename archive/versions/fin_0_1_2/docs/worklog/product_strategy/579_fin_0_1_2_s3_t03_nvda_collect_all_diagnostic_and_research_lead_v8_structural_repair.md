# FIN 0.1.2 S3-T03：collect-all diagnostic 与 Research Lead-v8 结构修复

日期：2026-08-03
状态：`diagnostic complete non-promotable / Lead-v8 engineering pass / independent proof pending`

## 结论

按 Owner 明确要求，先在隔离分支修复 primary exact-live 的当前 Lead blocker，再让 DeepSeek Pro 继续 Writer 与 Verifier，以一次受控诊断暴露后续链路。正式 R1 没有被重放或改写，仍是 7 calls、0 Artifacts 的 immutable failure。

诊断在精确重放 7 份 capture 后，只对 Lead 做一次 C002/C003 路径级修复；Writer 与 Verifier 各一次真实调用均自然通过，生成 9 个 quarantined Artifacts。没有发现新的 downstream L1 合同失败，也没有对 Writer/Verifier 做本地 repair。

主线随后完成 Lead-v8：不再要求模型同时选择 alias、记住该 alias 的 Fact 支撑状态、再把状态写成长叙事。模型只保留关系 alias 选择，本地 Runtime 从精确 Claim Card 生成证据状态叙事、fact presence、resolution、gap projection、ID 和 scoped identity。即使模型选择了语义质量不佳的 C002，最终也只会诚实写成 C002=`cannot_infer`，不会再把 C003 的事实错配给它。

## 隔离诊断数据

- source replay：7；新增 DeepSeek Pro calls：2（Writer、Verifier）。
- tokens：input `23,294`、output `657`、total `23,951`。
- 新增估算成本：USD `0.01070448`。
- 每次 transport attempt=1；retry/fallback/relaunch=`0/0/0`。
- quarantined Artifacts=9；业务晋升=0；paired/Owner=0。
- source runtime tree digest 前后均为 `651b21…30ee`。
- diagnostic result SHA=`2e3d8b6a…98e7`；quarantined Artifacts SHA=`4df28e26…7e5`。

## 全链路问题归属

T03 只保留一个 L1 blocker：Research Lead 的 claim evidence-state ownership。Writer 与 Verifier 没有暴露新的硬合同故障。

以下三项移交 T04，不继续扩大 T03：

1. frozen NVDA fixture 使四个 Claim 中三个为 `cannot_infer`，研究价值偏弱；
2. 最终本地 renderer 仍露出内部 token、重复币种和粗糙 period/string 拼接；
3. Verifier 没有看到 exact final local delivery preview，因而 `visual_delivery=pass` 不是最终成品证明。

这三项合并登记为 `RC-P36-109`。它们会影响 paired 与 Owner acceptance，但不阻塞 Lead-v8 的 T03 工程复证。

## Lead-v8 证明

- 当前 NVDA full-fake：9 Artifacts。
- Provider 越权返回 runtime-owned `fact_presence_summary`：Research Lead hard fail。
- 本次自然失败 Lead 正文：去掉 v8 wire 已不允许的字段后直接输入 v8，没有手工交换 C002/C003；本地 canonical output 将 C002 渲染为 `cannot_infer`，C001+C002 为 `no_facts_present`。
- v6 deterministic gap projection 与 v7 local fact-presence 行为回归保留。
- 实现轮 model/provider/network calls=`0/0/0`。

## 边界与下一步

diagnostic success 不能记为 T03 pass，Lead-v8 当前也只有 engineering pass。下一项是独立 fresh zero-call proof decision；通过后才能讨论 fresh replacement admission 与一次 replacement exact-live。新的 live 若再出现新 L1，S3 honest-block，不展开第三轮逐字段修补。

持久证据：

- aggregate：`configs/releases/fin_ia_0_1_2_s3_t03_nvda_quarantined_collect_all_diagnostic_aggregate_and_stage_disposition_v1_0.json`
- implementation：`configs/releases/fin_ia_0_1_2_s3_t03_research_lead_v8_local_semantic_materialization_minimum_zero_call_implementation_v1_0.json`
- projection：`configs/runtime/fin_ia_0_1_2_current_program_projection_v2_30.json`
- model run：`reports/model_runs/20260803_fin_0_1_2_s3_t03_nvda_deepseek_pro_quarantined_writer_verifier_collect_all_diagnostic_r1.md`
