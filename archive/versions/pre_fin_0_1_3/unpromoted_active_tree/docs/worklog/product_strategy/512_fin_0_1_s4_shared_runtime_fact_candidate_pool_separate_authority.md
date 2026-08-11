# 512｜FIN 0.1 S4 shared-runtime Fact candidate pool separate authority

## 结论

用户以“继续”授权当前
`S4-SHARED-RUNTIME-DETERMINISTIC-FACT-CANDIDATE-POOL-PLANNER-SEPARATE-AUTHORITY`。
本轮只完成权限裁决，没有修改 Runtime，也没有调用模型。

决策授权未来最多一个共享 Runtime 零调用结构包，将 Fact candidate generation
从模型权限移交本地确定性 planner。自动后续实现包为 0；实现成功后仍需单独
fresh proof authority，不自动获得任何 live、paired、owner、T06 closeout 或 T07
权限。

## 关键设计约束

- Provider-visible Fact aliases 最多 6 个，本地最终 Facts 最多 3 个。
- eligible supports 不超过 6 时必须完整保留。
- eligible supports 超过 6 时，必须由
  `(research_profile_ref, program_cell_id)` 的版本化 typed coverage profile
  稳定形成恰好 6 个候选。
- profile 使用 coverage slot、semantic role、authority/scope preference 和
  min/max，不允许 ticker 分支、自由文本关键词、embedding ranker 或 Provider
  返回顺序。
- 每个 eligible support 必须映射到唯一 slot，或有显式 audit-only reason；
  不允许静默丢失。
- eligible catalog、profile、candidate pool 与 slot counts 全部 digest/receipt
  绑定；公开 telemetry 不保存事实正文或数值。
- Provider 返回隐藏 alias、cross-case alias、duplicate 或第七个 candidate 时
  继续 L1 fail-closed，不做截断或 retry。

## 验证与边界

- Project OS preflight：`pass / open blockers 0`
- source failure/disposition SHA：匹配
- baseline Runtime/test binding：5 项匹配
- authority + prior disposition focused tests：`10 passed in 0.51s`
- authority/backlog JSON parse：通过
- root-cause/capability/pattern/method JSONL parse：通过
- 下一实现项 Project OS preflight：`pass / open blockers 0`
- Runtime code changes：0
- credential/model/provider/network/admission/live/paired/owner/T07：全 0
- maximum future zero-call bundles：1
- implementation bundles consumed：0
- Git：保留既有混合工作树；未新增 stage、commit 或 push

authority：
`configs/releases/fin_ia_0_1_s4_shared_runtime_deterministic_fact_candidate_pool_planner_separate_authority_decision_v1_0.json`

## 下一项

`S4-SHARED-RUNTIME-DETERMINISTIC-FACT-CANDIDATE-POOL-PLANNER-MINIMUM-ZERO-CALL-IMPLEMENTATION`

该实现已经获得未来执行权限，但没有在本轮启动。

## 后续状态

该未来实现已在 worklog 513 中完成；本文件继续作为权限来源，不应被解释为
Runtime 当前状态。当前 next 已推进到独立 fresh-agent 零调用复证决策。
