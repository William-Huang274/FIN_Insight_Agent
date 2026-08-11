# FIN 0.1 S2-T03 Bounded Agent 首跑失败记录

日期：2026-07-20
状态：`terminal_failed / no_automatic_rerun`

## Exact admission

T02 `22/22` 联合回归通过后，T03 绑定 isolated evaluation Case `case_87682fa72e72d7d042dabba0:v1`、as-of `2026-07-20T00:00:00Z`、3 个 repo-local SEC official candidates 和 input digest `ce6f5758ecb1e3f5d18d50028cf23214e2c1628ed00a99038c7a8bb5cec228ea`。Provider/model 为 `deepseek/deepseek-v4-pro`，最多 3 次语义/供应商/网络调用、每次 1 transport attempt、retry=0、总成本上限 USD 0.05；source network/external tool/commercial data/live business Case head write 均关闭。凭据仅检查环境变量存在与长度，未读取、打印或写入值；高置信 secret scan 为 0。

## 首跑事实

Canonical store 中精确存在：

- WorkUnit=1；
- Attempt=1；
- ResearchRun=1，ID=`research_run_fin01_9239b033666398bd8dece2a5`；
- terminal state=`failed`；
- terminal reason=`bounded_agent_profile_error:ValueError`；
- Artifact=0；
- fallback=0；
- rerun=0。

该失败发生在第一 bounded stage，未进入第二 semantic stage。旧失败路径在 schema/validation 终止前没有持久化 gateway usage receipt，因此 model/provider/network/transport/cost 不能从 durable truth 精确重建，只能记录为 0–1 次、费用未知但受 admission USD 0.05 cap 约束。不能把这个缺口写成 0 调用，也不能把首跑写成成功。

## 本轮修复但不重跑

1. future executor failure 现在携带 sanitized stage、model/provider/network counts、token、latency、transport attempt 和 estimated cost receipt；Runtime 将其写入 `RESEARCH_RUN_FAILED` event；
2. failure observation 不保存 raw provider response、private reasoning 或 secret；
3. runner 的 readback 路径修正为 canonical `/execution-projection`；
4. 增加 schema-failure regression，证明一次 mocked call 后可以持久化 secret-safe observation；
5. 本次已消费的 exact admission 不复用、不 retry。任何再次执行必须获得用户明确指令，并创建新的 execution identity 与 exact admission。

## 验证与边界

- T02 + T03 focused deterministic tests：`6 passed in 23.77s`；
- S1-T02 至 T06 + S2-T01 至 T03 + Workbench/API adjacent final regression：`34 passed in 43.75s`；
- 当前失败 store 检查：1 WorkUnit / 1 Attempt / 1 failed Run / 0 Artifact；
- source network=0、external tool=0、commercial data=0、live business Case head write=0、release admission=0；
- T03 未通过，T04/T05/T06、S3、RG1/RG3/RG4、release/production 全部保持 blocked。

模型运行账本：`reports/model_runs/20260720_fin_ia_0_1_s2_t03_bounded_first_run.md`。
