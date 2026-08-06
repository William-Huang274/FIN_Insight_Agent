# 643 — FIN 0.1.3 S2-02 三 family natural canary runner readiness

日期：2026-08-06
状态：`runner_engineering_pass / live_admission_not_issued`

## 目标

在 DELL demand、MU value/profit、NVDA bottleneck 三个预注册 request 上执行自然 DeepSeek 输出前，先建立可审计、可停止、不可重复消费的 runner，避免再用 live 调用发现本地确定性缺陷。

## 实现

- admission 绑定 clean/synced Git commit、runner SHA、S2-02 decision、policy 和三个 request digest。
- 使用 repository-independent shared SQLite ledger；`BEGIN IMMEDIATE` reservation 发生在任何 Provider 调用前，reservation 即消费。
- 每次调用先完整保存模型可见请求、无凭据调用参数、gateway result、assistant content、raw response、finish reason、usage 和 transport attempt，再解析与校验。
- Provider 只允许 alias/enum JSON；本地继续物化 Claim。首个 transport、JSON、合同或预注册 Rubric 硬失败立即停止。
- 固定 `deepseek-v4-pro`、official beta chat-completions route、3 calls、每 family 1、0 retry、0 fallback、每 call 最大 900 output tokens。

## 验证

- focused：`6 passed`。
- canonical＋runner：`167 passed / 1 historical event-time assertion deselected`。
- fake success：3 calls、3 captures、3 Claims、terminal receipt。
- fake first failure：1 call、1 capture、2 skipped、无 retry。
- replay：同 admission 第二次消费被 shared ledger 拒绝。
- 本项真实模型、Provider、网络、业务运行：`0 / 0 / 0 / 0`。

## 下一步与边界

先提交推送 runner，形成干净执行头；随后在 Git 外的受限 runtime 中签发并 exact-once 消费唯一 admission。原始 capture 不进入 Git，公开结果只保存安全摘要和内容 digest。canary 不是 full-chain、S3 研究质量、产品验收或 release 证明。
