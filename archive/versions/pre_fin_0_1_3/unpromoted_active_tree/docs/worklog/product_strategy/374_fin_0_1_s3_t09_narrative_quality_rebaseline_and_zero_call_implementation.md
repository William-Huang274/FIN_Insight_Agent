# FIN 0.1 S3-T09 narrative quality 分级、S3 重基线与零调用实现

时间：2026-07-24（Asia/Shanghai）

## 结果

用户授权按“决策 → 零调用实现/回归 → 一次最终 exact-live → 硬完整性通过后 T10 交接”的顺序连续推进。本项先完成零调用根因和范围重基线，再实现通用 narrative quality policy；没有调用真实模型、Provider、执行网络、来源或外部工具，没有签发 admission 或创建 canonical Run/Artifact。

根因是 profile-v2 把单字段 320 字符同时当作写作质量目标和安全硬边界。上一真实 Lead 回答 JSON、引用、wire、aggregate 和 token 均合格，但 388/343/423 三个完整字段被终止；运行时又只报告首个失败，导致 count=1，而受限回放为 3。

## 合同修复

- 保留 Research Lead-v5，不制造 Lead-v6/v7。
- 新增 versioned research profile v3：Specialist 的 320 硬上限不变；Research Lead 320 变成质量目标，512 为硬安全上限，aggregate 3200、wire 8192、alias 6000、local 32768、Lead 1800 tokens、aggregate 16800 tokens 和 USD 0.10 均不变。
- 新增 Provider-neutral `NarrativeQualityPolicy`；Prompt 与本地 validator 从同一 profile 读取 target/hard。
- 320 < length <= 512 不再终止，生成不含正文和 item index 的闭合质量观察，并写入 Manifest/Judgment Artifact；>512、blank、non-string 仍 fail-closed。
- hard telemetry 从首错 count=1 修正为同 subtype 的完整安全计数；旧 profile v1/v2 保持可重放，不改写历史 admission、Run 或受限回答。
- 禁止 trim、truncate、drop、rewrite 或为满足 320 而删除必要限定。

确定性验证为 `27 passed`；v2/v3/v4、旧 live-result、Specialist-v7 相邻回归为 `64 passed`。旧 v2 对 388/343/423 报告 3 个硬失败，新 v3 报告 3 个非终止质量缺口；513 仍硬失败。完整 fake Provider 路径为 6 logical nodes / 12 calls / 9 Artifacts，3 个质量缺口持久化成功。

## S3 范围重基线

S3 只需交付完整三 Cell NVDA R2，可标记 `R2_with_known_quality_gaps`。普通文风、重复、因果措辞与 Alpha 不足不再触发 S3 的新 transport/profile 迭代。三 Case transfer、qualified senior R3、主动来源网络、deterministic financial calculation、market-consensus/variant-view/Alpha 和 release gates 分别由 S4、S5、FIN 0.2 承担。

用户只授权一次最终 fresh exact-live，retry/fallback/rerun 均为 0；任何新硬完整性失败立即停止。Codex 可以做独立产品复核和 T10 交接草案，但不能冒充用户签署 owner acceptance。

下一项为全新 profile-v3 exact proof 决策与 admission 签发，仍为零调用准备；随后只消费一次。
