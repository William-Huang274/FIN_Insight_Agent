# 645 — FIN 0.1.3 S2-03 Context Yield 零调用与自然复证 readiness

日期：2026-08-06

## 本轮结论

S2-03 的零调用工程包已通过，但阶段尚未关闭。新 role-scoped compiler 在 9 个代表性 Specialist request 上，把模型可见输入从 `40,326` 字符降到 `24,289` 字符，缩减 `39.7684%`；保留 `26` 条 Evidence alias、`2` 条 typed gap、`18` 个公司特定 mechanism 和 `18` 个 what-would-change alias，保留率均为 `100%`。

被移出模型输入的是本地治理字段：candidate/slot/gap ID、digest、S1 query lineage 等。它们没有被删除，而是保留在与 request/context digest 绑定的 local authority sidecar。模型仍能看到公司、研究 Cell、决策问题、方法步骤、全部证据与反证选择、claim boundary、financial/relationship authority、缺口边界和 closed output enums。

## 根因与 0.1.2 对照

FIN 0.1.2 三案例 full-chain 分别使用 `55,906–57,739 input tokens` 对约 `3,038–3,323 output tokens`。私有 capture 审计显示，旧链把同一 Cell 拆成 Claim/WWC 两次调用，并在 Specialist、Lead、Writer、Verifier 间重复 identity、numeric authority、compiled contract 和下游投影。

S2-03 不把历史 full-chain token 直接冒充同口径对照。本轮只证明代表性节点的模型输入可以去掉重复治理噪声，同时完整保留研究语义。按保守估算，9 个当前节点输入从约 `20,165` 降到 `12,147` tokens；这不是未来 S3 full-chain 成本承诺。

## 验证

- S2-03 focused：`22 passed`；
- S0–S2 canonical successor：`191 passed / 1 historical event-time assertion deselected`；
- mutation 覆盖 Evidence/gap/optional semantic 丢失、跨案例 alias、自由文本、local-field leak、lineage 漂移、capacity 越界、transport failure 和 admission replay；
- S2-02 三个真实自然输出已在零调用下重新通过 compact alias/enum contract；
- model/provider/network/source/business calls：`0/0/0/0/0`。

## 尚未证明与下一步

模型可见 bytes 已发生变化，因此不能只凭本地测试关闭 S2-03。下一步只允许对预注册最高负载 `FIN013-S2-NVDA-demand_authenticity_and_sustainability` 做一次 DeepSeek Pro 自然复证：`1 provider call / 0 retry / 0 fallback / 0 full-chain`，raw request/response capture-first，first failure stop。

该 canary 通过后才可关闭 S2-03。S3 动态 10–20 Cell、Lead/Writer/Verifier 跨 Cell 内容质量、八维研究质量和产品验收均未开始，不得由 context capacity 结果替代。
