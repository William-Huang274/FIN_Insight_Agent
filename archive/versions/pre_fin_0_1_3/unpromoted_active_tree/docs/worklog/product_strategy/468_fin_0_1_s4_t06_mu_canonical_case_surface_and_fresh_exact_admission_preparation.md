# 468｜FIN 0.1 S4-T06 MU canonical Case/surface 与 fresh exact admission 准备

日期：2026-07-29

## 结果

MU canonical admission 前零调用准备已通过：

- canonical Case：`case_ec7da8015386e7bfeda92c61`；
- accepted DecisionSurface：`p02_decision_surface_dd094559ce4c0f79d242e852:v1`；
- planning Cell：3；
- evidence slot：14；
- exact input digest：`7887b5bb447fc6a844c410751f2038a04a1c0b04dbbe7e5bde41b040135a12e1`；
- preparation digest：`5d506da117962a8174ab23cae9e857f67a12126884098cb81e23acf0f0ff363a`。

目标 canonical runtime 和隔离 clone 均执行双物化；第二次操作没有改变 prepared payload、DecisionSurface 或数据库 logical digest。

## Fresh identity 与 admission

冻结的 execution identity：

- WorkUnit：`wu_p02_5_fbe7fa234fce9f4c54403c56`；
- Attempt：`attempt_fin01_e4473dd705631f215159fe76`；
- ResearchRun：`research_run_fin01_c94013e1c3666739c35ff00c`。

三个 canonical identity 均确认尚不存在。prospective admission 绑定：

- provider/model：`deepseek / deepseek-v4-pro（Pro，不是 Flash）`；
- base URL：`https://api.deepseek.com/beta`；
- admission digest：`56005ffb1227e9ec1ead1b73b780342dfeaeef06bbdb0eff01592d7cdc19c891`。

admission 文件没有生成，未签发、未消费，也未开始 exact-live。

## 验证

- 当前链路与相邻 proof：`18 passed`；
- 全部 S4-T06 contract regression：`114 passed`；
- model/provider/new source calls：`0 / 0 / 0`；
- WorkUnit/Attempt/ResearchRun/business Artifact：`0 / 0 / 0 / 0`。

首次更新 backlog 时曾把顶层 `item_id/current_next_action` 直接替换为 issuance，导致 14 个历史 transition tests 失败。根因是这些 append-only 迁移证明把 DeepSeek mainline preparation 作为兼容 umbrella ID。最终保留该顶层 ID，只在内部 `required_in_scope_substep/current_next` 推进到 issuance；复跑恢复 `114 passed`。这没有改变 MU canonical payload、identity 或 admission digest。

## 边界与下一步

本步骤只物化 canonical planning/input head 和冻结 prospective admission。HBM-specific revenue/profit、customer identity/concentration、forward demand/capacity realization 仍不可推断；Graph 仍是 context-only；strict-schema transport 继续停放。

下一项：

`S4-T06-MU-FRESH-EXACT-ADMISSION-ISSUANCE`

该步骤只能重验并签发一次 frozen admission，不得在同一步消费 admission 或执行 DeepSeek exact-live。

## 后续修正

2026-07-29 issuance 前重验发现原 prospective proof 的 digest payload 与 JSON 持久化 payload 不同：后者包含 7 个未显式绑定的 null 可选字段。proof 在任何 admission 文件写入前 fail-closed。generator 已改为持久化 `digest_payload()` 并增加 JSON round-trip digest regression；重新生成 proof SHA=`6db5be1f9f10cb44b37d994e4936fee933cefbfc4a6a74e4838b81e2e1e75d86`，admission digest 保持 `56005ffb...c891`。完整发行结果见 worklog 469。
