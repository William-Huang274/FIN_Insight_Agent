# P38 Point 01 M2-A1 Phase B0.2：v2.4 dispatch incident 收尾与 v2.5 refreeze

## 结论

`REJECT_EXECUTION_RESULT_AND_APPROVE_PRECONSUME_DISPATCH_REPAIR_REFREEZE_ONLY` 已按边界落地。v2.4 baseline 没有重试，也不构成业务结果；receipt 仅在 receipt 与 admission 的实际 expiry 后转入不可逆 `expired_unconsumed`。

## 历史 authority 收尾

- exact receipt：`point01-m2-a1-v2-4-baseline-fe9658d04ca515924c568123`
- state：`expired_unconsumed`；`consumed_at=null`
- 原 receipt digest：`596fcf570a7abc1d4344ec6db354a4670e1c8a59e48f97396d5bf27c2401b870`（未改写）
- 事件顺序：`REGISTERED -> EXPIRED_UNCONSUMED`
- terminal artifact digest：`adf5a8f229e70f5aa6f7e27e31b2fb9699bcf470f64fd8ee2a6a3c3fadcedef6`

该终态不能 consume、renew、replay、delete、覆盖 payload 或改 expiry；没有 runtime/output、actual/oracle/reviewer、network/tool/model/provider 或 fixed/business/legacy mutation。

## v2.5 修复与冻结

- parent 只接受最多一个 leading `--`，有/无 separator 均生成同一 child argv；unknown/duplicate/missing value 在 child、ledger、runtime 创建前 fail-closed。
- package 将 v2.5 parent、clean child、registrar、JIT orchestrator、expiry runner、incident 与 terminal evidence 绑定进 Git-index inputs；生产 preflight 对无 admission 只允许 `package_admission_required`。
- package：`a23dac3931164b4910a6182b97fa37e10d788e893991e4bc1d079e78439ebe6a`
- package gate：`cd507c7dd55932866c954cd6001b2d33aa0b63801cec5d8168236fdcaae65de4`
- plan：`053cb47b47a67a97e5c4cebe5c0064a0cf556e7f1d1ec70dec0b1ca52eb1c507`；plan gate：`79728590e2a089c2a75b0f8f1fe2fbd26f42bcf52834814cb76187810368aff4`
- blueprint：`9d2ae58f371d57bd4e827eda398933623886f74126a015ee6a7a167a41ea3020`；blueprint gate：`9c79976e3ec5db0936c07a7cb014d73d0128906815cca334b91473c9b6b3d07d`

## 验证与状态

- targeted dispatch/expiry regression：`3 passed`
- package/plan/blueprint gates：`pass`
- fixed approval DB SHA-256：`ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4`
- 新 admission/receipt、receipt registration/consumption、baseline actual、network/tool/model/provider/store write：均为 `0`

M2 保持 `milestone_scope_status=complete_deterministic_shadow`，但 `operational_qualification_status=pending_dispatch_repair_refreeze_and_fresh_baseline`。下一步只能由 total reviewer 审核 exact v2.5 artifacts；不得自动签发新 authority 或重跑 baseline。
