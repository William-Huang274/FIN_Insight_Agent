# P38 Point 01 M2.8 Model Admission / Trace

日期：2026-07-12

状态：`m2_8_full_implemented / calibrated_denied_path_no_model_execution / shadow_only`

## 完成

- 新增 provider-neutral compiler adapter protocol、DeepSeek-first/GPT-ready provider-family policy、prompt-context snapshot、provider/budget/permission/feature/approval admission decision、structured-output repair trace 与 audit digest。
- 当前 `model_execution_permitted=false` 是 hard deny：其它 admission 条件即使全部通过，仍返回 `policy_model_execution_disabled`，不会调用 adapter。

## 校准与验证

- denied fixture 覆盖缺 feature/approval/provider/budget/permission 的全部拒绝原因，以及其它条件就绪但 policy 仍拒绝的路径。
- Counting adapter 调用数为 0；model/external call 为 0；针对 M2.8 与旧 shadow compiler contract 的回归 `4 passed`。

## 边界与回滚

- 此项实现的是 future approved scoped node 所需的 admission/trace contract，不是 provider execution、model comparison 或 paid run。
- policy revision、显式 scoped approval、provider/budget preflight 仍是未来真实调用的前置，且不能由此处的 deterministic fixture 自行满足。
