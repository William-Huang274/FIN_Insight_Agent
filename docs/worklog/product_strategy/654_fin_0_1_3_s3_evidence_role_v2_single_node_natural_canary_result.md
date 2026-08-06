# 654 — FIN 0.1.3 S3 Evidence-role v2 单节点 natural canary

日期：2026-08-06

clean/synced commit `cd041665cbf20cf7c5fded8ca44b26320792fd90` 上签发并消费了一次 DELL demand fresh admission。结果为 `terminal_succeeded_exact_once`：`1 call / 1 capture / finish_reason=stop / 618 input / 120 output / 738 total / 0 retry / 0 fallback / 0 business promotion`。

DeepSeek Pro 自然选择：`cannot_infer`、`DELL_E01`、`DELL_G01`、`DELL_M_DURABILITY_GAP`、`DELL_W_DEMAND_BACKLOG` 和 `DELL_W_DEMAND_REVERSAL`。本地 v2 role projector 把收入观察 `DELL_E01` 归为 `boundary_only`，`observation_support` 与 `thesis_support` 均为空。因此模型可以保留真实观察，又不会让收入数字越权证明需求持续性。

原始 request/response、finish reason、usage 和 capture digest 留在 Git 外；secret scan 未发现 credential、Authorization 或 Cookie。Git 内公开结果仅含安全 alias、角色投影、digest 和 usage。R1 仍是旧 v1 合同下的失败，没有被追认或重放。

单节点通过只关闭 renamed-field 自然遵循风险，不证明九节点全链或最终研究质量。基于既有九节点 full-fake 与当前 canary，通过一次 fresh 九节点 v2 replacement admission 已获准；仍为 0 retry/0 fallback/首个可信失败停止。成功后才可生成 all-natural Claim/Lead/Workpaper 并执行三案 L1/L2、八维评分、paired 和 qualified-human acceptance；失败不得自动进入 R3。
