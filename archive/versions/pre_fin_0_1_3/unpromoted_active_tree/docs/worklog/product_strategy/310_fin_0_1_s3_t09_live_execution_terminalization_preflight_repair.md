# FIN 0.1 S3-T09：live execution 终态闭环预检修复

日期：2026-07-22

## 结论

用户已授权执行唯一的 `S3-T09-EXACT-THREE-CELL-DEEPSEEK-LIVE-EXECUTION`。在消费真实 admission 前，新建的 exact runner 先用假 Provider 验证失败路径，发现一个项目自有 blocker：S3 executor 正确产生了 `s3_bounded_...` typed failure，但 canonical `fail_research_run` 仍只允许 S2 的 `bounded_agent_` 前缀，导致失败观察被拒绝，后台异常逸出，WorkUnit、Attempt 和 ResearchRun 不能可靠关闭。

本轮先完成零真实调用修复，没有消费 admission。canonical validator 现在只允许 `bounded_agent_` 与 `s3_bounded_` 两个显式命名空间，并额外要求 failure code 符合小写字母、数字、下划线、冒号、点和连字符组成的 1-256 字符闭合集。未知命名空间、包含空格的内容和超长内容继续 fail-closed，未把 allowlist 放宽为任意 Provider 文本。

## 验证

- typed namespace 与历史 secret-safety 回归：`3 passed in 24.11s`；
- exact runner 全量假 Provider 回归：`3 passed in 119.23s`；
- 假 Provider 的首节点坏 shape 只产生一次模拟调用，随后 WorkUnit、Attempt、ResearchRun 均为 `failed`，Artifact=0；
- 同一 execution identity 的后续 preflight 被拒绝，证明 admission 不可复用；
- 真实 model/provider/network 调用均为 0。

RC-P36-034 已以 append-only 方式记录并关闭。下一步仍是同一已授权 live execution 的最终 Project OS 与 exact zero-call preflight；只有两道门通过才允许消费一次 admission。成功或失败都必须停在 canonical terminal truth，不允许 retry、fallback、rerun、来源扩张或进入 T10。
