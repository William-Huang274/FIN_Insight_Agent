# 469｜FIN 0.1 S4-T06 MU fresh exact admission issuance

日期：2026-07-29

## 结果

MU fresh exact admission 已签发且未消费：

- admission ID：`fin01-s4-t06-mu-fresh-exact-admission-r1`；
- admission digest：`56005ffb1227e9ec1ead1b73b780342dfeaeef06bbdb0eff01592d7cdc19c891`；
- provider/model：`deepseek / deepseek-v4-pro（Pro，不是 Flash）`；
- base URL：`https://api.deepseek.com/beta`；
- issued：true；
- consumed / execution started：`false / false`。

## 首次可信失败与修复

首次发行在任何 admission/issuance 文件写入前 fail-closed：

`s4_mu_admission_digest_mismatch`

根因不是模型或 DeepSeek。prospective generator 用 `admission.digest_payload()` 计算 digest，却把 `admission.model_dump(mode="json")` 写入 proof。后者包含 7 个未显式绑定的 null 可选字段；JSON 重载后这些字段进入 Pydantic `model_fields_set`，导致 `digest_payload()` 改变。

最小结构性修复：

- 持久化 payload 改为与哈希完全相同的 `digest_payload()`；
- generator 内新增一次 JSON model validation round-trip digest 检查；
- contract test 新增 round-trip digest 与未绑定 null 字段缺席断言；
- 历史 preparation test 允许后续合法 issuance，但仍要求 proof 当时未签发且当前 issuance 未消费。

没有修改模型、token/cost budget、financial truth、source pack、Case、DecisionSurface、Provider 或 transport。

## 发行重验

发行前再次通过：

- frozen proof regeneration byte parity；
- source pack SHA；
- canonical database logical digest 与 object tree 不变；
- predicted WorkUnit/Attempt/ResearchRun 全部 absent；
- canonical execution/Artifact counts 全部为 0；
- admission schema/profile/digest；
- live runner load；
- 6 个 exact code bindings；
- provider callback=0。

## 验证

- focused/current issuance chain：`25 passed`；
- S4-T06 contract regression：`121 passed`；
- Project OS issuance preflight：pass，open blocker=0；
- model/provider/execution-network/source/tool calls：`0/0/0/0/0`。

没有创建 model run ledger，因为本步骤没有训练、推理或 Provider 请求。

## 下一步

`S4-T06-MU-FRESH-EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-ASSESSMENT-AUTHORITY-DECISION`

该步骤仅允许零调用 authority decision，不消费 admission。未来 exact-live 必须另行授权、exact-once、retry=0、首个可信失败即停止；只有完整成功并生成 9 Artifacts 后才允许 paired assessment。
