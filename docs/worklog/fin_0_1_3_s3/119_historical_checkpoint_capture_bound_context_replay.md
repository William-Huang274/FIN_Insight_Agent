# 119｜历史 checkpoint 的 capture-bound 上下文复证

## 为什么需要这次修复

Actionable Uncertainty 与 current consumer 接线完成后，全仓回归暴露出两条历史多 Agent successor 测试失败。失败不是旧 Agent 产物损坏，也不是当前研究合同错误，而是历史 R7／R8 workpaper 在复证时被重新套用了今天的 consumer overlay、来源政策和上下文编译结果。只要当前实现继续演进，重新编译得到的 context digest 就可能变化，从而把原本有效的不可变历史产物误判为损坏。

## 最早责任层

- 责任层：S0 Harness 的历史运行回放与 checkpoint 身份治理。
- 错误做法：用当前代码重建历史模型可见上下文，再验证历史 workpaper digest。
- 正确做法：历史结果必须绑定当次已经保存的 `model_visible_request_without_credentials` capture；当前新运行才使用 current policy。

## 实际实现

`multi_agent_preview_runtime` 现在对已完成的历史 specialist 节点读取原始 capture，并逐项校验：

1. capture 必须位于受控 `data/captures` 路径；
2. 不得包含凭据、Authorization 或 Cookie；
3. Run／Attempt 身份必须与 checkpoint 一致；
4. request body digest 必须与保存的 canonical request digest 一致；
5. agent、analysis envelope、context schema 和 context digest 必须匹配；
6. 当前运行仍默认使用 current consumer overlay，历史兼容路径不能反向冻结新产品。

这不是降低 digest 校验，也不是给旧结果打补丁；相反，它把“历史事实”与“当前编译逻辑”彻底分开。

## 验证

- 原两条失败 successor 测试：`2 passed`；
- 全仓：`997 passed`，仅 2 条既有 SWIG deprecation warnings；
- Python compileall：通过；
- Workbench TypeScript 与 production build：通过；
- active baseline：`197 Python / 8 frontend / 5 detectors / 28 Runtime resources / 0 forbidden`；
- archive redirect：6,059；
- repository secret scan：7,584 files／0 findings。

## 边界

本次修复只恢复不可变历史运行的正确解释与 successor 复证，不签发新的模型权限，不证明自然反思、S1／S3、qualified-human、Workbench publication 或 release 通过。下一产品门仍是单独授权的 DELL 动态 multi-agent 纵切。
