# 655 — FIN 0.1.3 S3 formal Anchor v2 R2 gapless-request failure

日期：2026-08-06

clean/synced commit `136225a9e5670cde7f984deceb1c53140325676c` 上的唯一九节点 v2 replacement admission 已消费。R2 在第 5 个 MU value/profit 节点停止：`5 calls / 5 captures / 4 passed / 1 failed / 4 skipped / 3371 input / 606 output / 3977 total / 0 retry / 0 fallback / 0 business promotion`。

前四项分别为 DELL demand、DELL value/profit、DELL bottleneck、MU demand，全部通过 renamed schema 与本地角色投影。第五项 Provider transport 成功、`finish_reason=stop`、JSON 和 v2 字段合法；DeepSeek 选择 MU 四条 consolidated/DRAM 事实、`MU_M_BASELINE_NOT_HBM_ECONOMICS`，并诚实返回 `cannot_infer`。问题在于该 request 的上游 `gap_options=0`，模型没有可选 gap alias，却被本地统一规则要求 `cannot_infer` 必须带 typed gap，于是以 `s3_evidence_selection_gap_required` 失败。

这不是放宽 typed-gap 门的理由。正确的结构处置是：当上游确实没有 gap option 时，由本地合同编译器生成唯一的 request-bound 默认 gap，表达“所选证据不足以回答当前 decision question”；模型不能编写其内容，local projector 只在 `cannot_infer + zero upstream gap option` 时自动绑定。若上游有一个或多个 gap option 而模型不选，仍应失败。与此同时，typed terminal 应保存已解析但未晋升的 raw alias output 摘要，不能只依赖 capture readback。

R2 不可改写，R3 未授权。本轮下一项限于上述零调用结构处置、mutation 和九节点 full-fake；通过后再另行决定是否值得执行 R3。正式 case score、paired、qualified-human acceptance、S3 product proof、S4 和 release 均未开始。
