# FIN 0.1.3 S3：successor v1.1 required-set 入口失败

日期：2026-08-16

v1.1 authority 在 0 Provider 调用处以 `dynamic_successor_bound_inputs_invalid` 停止。authority 已正确带上 current loop policy 和 dynamic micro policy，但 canonical required-set 仍是旧的九个 ref，因此把新增的两个合法绑定当成多余字段拒绝。

这不是历史 Git blob 修复失败，也不是 DeepSeek、R1、S1/S2 或金融判断问题，而是 authority JSON 和 Python required-set 两份手工字段清单漂移。v1.1 authority／run／attempt／output identity 保持已消费，不修改或重用。

修复只做两件事：把两个 policy ref 纳入 canonical required-set；用真实 v1.1 authority 文件直接测试 `_successor_bound_paths`，而不再只用缩小的手工 fixture。修复后必须新建 v1.2 proof、decision、preflight 和身份。
