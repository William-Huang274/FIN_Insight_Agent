# 676 — FIN 0.1.3 S2-05 NVDA raw Experiment A authority

日期：2026-08-07

状态：`zero-call authority compiled / admission not issued / execution pending clean commit`

## 目标

在 DELL、MU 两案 raw 均已完整但质量失败后，用同一冻结模型可见合同测量第三案 NVDA 的自然 raw 表现。该动作只补齐 Experiment A 第三个公平样本，不执行前两案纠错、supervisor 扶正、formal score 或产品晋升。

## 公平性与权限边界

- NVDA 仅可读取自身 `13 Evidence / 3 derived numeric / 4 explicit gaps`，case digest=`45422727...81c5`；
- frozen blind input、runtime policy、DeepSeek Pro、temperature 0、thinking disabled、Lead＋6–8 Specialist＋Synthesis＋Writer＋Verifier 合同不变；
- evaluator v1.3 只在完整 raw 返回后评分，不进入模型 prompt；
- DELL/MU raw、correction ledger、supervisor prompt 和 hidden Gold 全部不可见；
- 只允许一份 admission、一次 exact-once execution、最多 12 calls、retry/fallback=0；
- raw capture-first，business promotion、automatic rerun/next-case、supervisor correction 均为 false。

## 零调用审计

- 仓库在 `d4262a1c...5c25` clean/synced；
- authority decision digest=`88bfd1f9...ff50`；
- Project OS `separate_NVDA_raw_admission_authority_decision` preflight=`pass / open blockers 0`；
- production runner preflight=`zero_call_layered_preflight_ready_admission_not_issued`；
- credential 只确认 presence=true，未读取或保存值；
- focused authority/MU result/S2-06=`17 passed`；S2-05/S2-06 broad=`84 passed / 3,201 deselected`；
- admission/model/provider/network/supervisor/business promotion=`0/0/0/0/0/0`。

## 下一步

提交并推送本 authority slice。之后才可签发 Git-ignored NVDA admission，重新执行 clean/synced、Project OS execution scope、production capacity/provider preflight；全部为 green 时 exact-once 消费。完成后保存 raw、用 evaluator v1.3 评分并物化 NVDA 独立 supervision boundary，然后停在三案统一 supervisor authority decision 之前。
