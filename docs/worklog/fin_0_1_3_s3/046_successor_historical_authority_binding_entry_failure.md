# FIN 0.1.3 S3：successor 历史 authority 绑定入口失败

日期：2026-08-16

## 实际发生了什么

v1.0 successor authority 在任何 Provider 请求发出前被入口门拒绝，失败码为 `dynamic_live_bound_input_drift:runner_ref`。模型、Provider、网络、embedding 和 capture 均为 0；R1 与它的五个成功模型节点没有被触碰。

R1 authority 在提交 `ba02a24b...` 上绑定的 runner SHA 为 `2290069f...fce5`。为实现 successor，当前 runner 已演进，因此当前路径 SHA 不再相同；但 Git 中 R1 提交的历史 blob 仍与 authority 完全一致。旧入口把“验证历史运行当时用了什么”错误实现为“历史代码今天还必须占据同一路径”。

## 结构性修复

- predecessor authority 的所有绑定输入改为从其 `implementation_commit` 读取 Git blob 并核对 SHA；历史事实不再依赖今天工作树的同名文件。
- successor 真正要执行的 current `loop_policy` 与 `dynamic_micro_policy` 改为在 successor authority 中直接绑定；不能因为历史 blob 合法就静默消费漂移后的当前 policy。
- v1.0 authority 与输出 identity 永久视为已消费的入口失败证据，不修改、不重用。
- successor authority/result schema 升为 v1.1；必须重新做零调用 proof、scope decision、clean preflight，并使用新 run／attempt／output identity。

对应根因是 `RC-S3-026-successor-historical-authority-current-path-drift`。该问题属于项目内 exact-once 治理，不是 DeepSeek、S1/S2 或金融内容问题。

## 边界

这次修复只让历史 authority 可被正确审计，并让当前执行依赖显式绑定。它没有运行 successor，也不证明 counter／WWC、动态 Judgment、五单元、泛化或 S3 acceptance。
