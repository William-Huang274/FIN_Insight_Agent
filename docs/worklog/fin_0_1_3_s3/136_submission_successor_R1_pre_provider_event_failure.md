# FIN 0.1.3 S3 submission successor R1 调用前事件失败

时间：2026-08-23

状态：`R1_authority_consumed / zero_provider / canonical_event_seam_repaired / fresh_successor_required`

## 发生了什么

submission successor R1 在创建第一个 Specialist successor session 后，尝试写入新事件名 `predecessor_bound`。canonical Runtime 只允许既定事件字典，因此以 `runtime_event_type_invalid` fail closed。

- 0 次 Provider／DeepSeek 调用；
- 0 次新 S1/S2 请求和 retrieval round；
- 0 外源网络、Candidate promotion、retry 或 fallback；
- R1 predecessor 的 14 次调用、六轮 S1/S2、capture 和研究草稿均未改变；
- 本次 authority 和公开输出 identity 已消耗，不能复用。

失败 public result：`configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_submission_successor_live_result_v1_0.json`，result digest=`3f3b04612cef05c11a3d33861cb94933ec1d446a214300190c62963a2f4eb158`。

## 最早责任层

这是 S0 canonical Runtime 组合接缝漏测，不是 DeepSeek、S1/S2、信源、Reflection／Workpaper 合同或研究质量问题。工程 proof 验证了合同和 capture replay，却没有让新 successor 真正跨过 `AgentSession → append_session_event`。

## 修复与防复发

- 不扩张事件字典；predecessor lineage 使用已注册的 `plan_bound` 事件，以 `input_refs` 绑定旧 session、role program 和 round response digests；
- runner 通过共享 `_bind_predecessor_session_event` 使用该事件；
- 新测试真实创建 `AgentSession`、追加 `session_created`，再跨过 predecessor bind，并断言事件链为 `session_created → plan_bound`；
- R1 public/private failure terminal 已补齐，旧 authority 保持 consumed。

下一步必须先提交／推送修复，再重新运行 zero-call capture proof，签发新的 authority。不得把 R1 authority 或输出路径清空复用。
