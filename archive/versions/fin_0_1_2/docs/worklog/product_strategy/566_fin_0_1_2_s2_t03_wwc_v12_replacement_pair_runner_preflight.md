# FIN 0.1.2 S2-T03 WWC v1.2 replacement pair runner/preflight

日期：2026-08-03
状态：`engineering + zero-call preflight pass / exact pair not executed`

## 问题与决定

前一项只给 MU WWC Flash/Pro replacement pair 条件签权；真实执行前仍缺少与该 authority 精确绑定的 two-call runner、capture-before-validation、terminal materialization、预算和 identity 证明。用户以“继续”授权本零调用实现项，没有授权读取凭据、调用模型或进入 T04。

开发初版曾把 family-pair 编译入口加到共享 paired-canary compiler。受影响回归立即出现 3 个 immutable hash failure，因为该文件已被历史六调用 authority 和 WWC v1.2 独立 proof 冻结。该改动未提交并在本项原地撤回；共享 compiler 恢复原字节和 SHA256。最终把 authority call-ID 适配器隔离在新专用 runner 子类中，不改写历史证据。

## 完成内容

- 新增独立 two-call RuntimeResourceRegistry，绑定 conditional authority 与 MU exact fixture；
- 新 runner 从 fixture 重建 current v1.2 compiler，只投影 WWC Flash/Pro pair；
- authority call ID、model、request/equivalence digest、route、预算和 zero-retry 逐项 fail-closed；
- 完整保存模型可见 request、最终 assistant output、finish reason、usage 和安全调用参数，排除 credential/header/cookie/private reasoning/raw Provider envelope；
- capture 原子落盘后才做本地 validation，terminal result 再独立物化；
- semantic failure 继续第二个独立候选；transport/auth/security/capture/budget failure 停止剩余；
- execution identity 原子 claim 且不可复用；默认 live 路径还要求显式执行 flag；
- disposable preflight 覆盖 happy、semantic、transport、identity、对象仓 readback 和预算，未触及 canonical execution root。

## 证据

- focused replacement runner tests：`13 passed / 0 failed`；
- S2 与历史不可变性组合回归：`86 passed / 0 failed`；
- 加入 result/projection/backlog/Project OS current-state 治理检查后的最终受影响回归：`90 passed / 0 failed`；
- exact pair digest matched：`2/2`；
- worst-case estimated cost：`USD 0.006786 < 0.015`；
- credential/model/Provider/network/replacement/business Run/Artifact：`0`；
- 共享 compiler SHA256：`f6d43215...10fb5`，与冻结值一致。

## 产品与工程增量

产品功能没有新增，模型也没有被选择。工程上，下一次真实 pair 即使语义失败，也能保留完整受限原始输出和 typed terminal，不再依赖 telemetry 猜测；同时旧六调用证据链保持不可变。

## 当前边界与下一项

RC-P36-102/103 仍 open，因为公平自然 WWC 输出仍为 0。现有 conditional authority 已满足 runner/preflight 技术条件，但本项没有自动消费它。当前下一项：

`FIN-0.1.2-S2-T03-MU-WWC-V1.2-FLASH-STABLE-VS-PRO-PREVIEW-REPLACEMENT-PAIR-EXACT-EXECUTION`

该执行需要用户新的“继续”；只允许 Flash/Pro 各一次，不允许 Fact/Claim 重跑、retry、fallback、Provider hopping、业务 Artifact、T04 或模型选择。若再次出现新项目内比较器缺陷，按已冻结 stop rule 进入 S2 honest block，不再开第二修复包。
