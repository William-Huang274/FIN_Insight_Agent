# 646 — FIN 0.1.3 S2-03 自然复证结果与关闭

日期：2026-08-06

## 结果

S2-03 已关闭。clean/synced commit `489ec11260cf1847cca29008ce29cc89450f78b1` 上签发的 fresh admission 由 shared ledger exact-once 消费；预注册最高负载 request `FIN013-S2-NVDA-demand_authenticity_and_sustainability` 使用 DeepSeek Pro 完成一次 compact-context 自然复证：

- `1 provider call / 1 transport attempt`；
- `finish_reason=stop`；
- `927 input / 149 output / 1076 total tokens`；
- `0 retry / 0 fallback / 0 business promotion`；
- raw request/response、finish reason、usage 和完整 terminal result 先保存到 Git 外私有 capture；公开结果只保留安全的 alias/enum 选择、digest 和 usage。

模型选择 `NVDA_M_DURABILITY_REQUIRES_REPEAT_EVIDENCE`，使用 6 条本案 Evidence，保留 `mixed_evidence / mixed / medium`，并选择“重复部署证据”和“需求消化”两个可观察的 what-would-change 条件。输出没有跨案 alias、自由叙事、模型自造数字/日期/身份或 lineage，并成功物化回本地 NVDA demand Claim。

## S2-03 总结

9 个代表性节点的模型可见上下文缩减 `39.7684%`，四类研究语义保留率均为 `100%`。最终 S0–S2 canonical successor 为 `195 passed / 1 historical event-time assertion deselected`。

因此可以关闭 `013-S2-03`，下一项为 `013-S3-01` 动态 DecisionSurface 入口审计。这里不能宣称最终报告已经有研究深度：动态 10–20 Cell、跨 Cell Lead/Writer/Verifier、八维研究质量、产品验收和 release 都仍未开始，必须由 S3 负责。
