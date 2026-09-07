# FIN 0.1.3 S3 — R15 启动前 Provider profile 校验集成修复

日期：2026-08-20
状态：`preprovider_failure_preserved / zero_paid_call / validator_repaired / full_regression_pass / clean_commit_push_preflight_pending`

## 发生了什么

R15 authority v1.14 在 clean／synced commit `71c4b840...` 和 fresh Project OS preflight 后签发，并通过完整 authority 校验。正式 runner 启动时，在任何模型节点、Provider attempt、网络调用或 Candidate promotion 发生前，本地通用 DeepSeek profile validator 拒绝了 Supply 专用 profile：该 profile 明确要求 `reasoning_effort=high`，旧 validator 却把所有标准分析 profile 都硬编码为 `max`。

该失败不是 DeepSeek、Supply Evidence、检索、研究判断或网络故障。R15 v1.14 authority 与公开 pre-provider failure result 保持不可变，执行计数全部为 0；这次启动不消费付费 live 权限。

## 最早责任层与修复

最早责任层是 S0 Provider profile validation integration。修复保持 fail closed：

- `validate_deepseek_ga_profile` 默认仍精确要求 `max`；
- 调用方只有显式传入 `expected_reasoning_effort` 才能使用任务级档位；
- R15 Supply repair 显式绑定 `high`；
- 其他现有调用点没有放宽，也没有改变 max token、Evidence、研究输入或产品权威。

这样 Provider profile 的任务差异仍由调用合同明确声明，而不是把 `high/max` 加入一个无条件宽松白名单。

## 验证与后续

新增回归同时证明：任务级 high profile 在显式期待下通过；如果仍按默认 max 校验，它会继续 fail closed。综合全仓为 `897 passed`，仅有既有 SWIG deprecation warnings。

下一步必须先将本修复、R15 v1.14 authority 和 pre-provider failure result 形成 clean commit 并推送，再重新执行 fresh Project OS preflight。之后签发新的 R15B authority；它仍使用同一 v1.14 schema 与既有 v1.10 scope，不新增 R16／R17 特例分支。R15B 才是唯一尚未消费的付费 Supply repair live。

即使 R15B 完成 Supply、Evaluator 和 Writer，也仍不代表 S1、S3、泛化、qualified-human、产品发布或 release 通过。
