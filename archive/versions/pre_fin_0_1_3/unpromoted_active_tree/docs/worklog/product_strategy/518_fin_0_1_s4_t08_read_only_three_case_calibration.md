# 518｜FIN 0.1 S4-T08 三案例只读校准

## 任务

消费 immutable 的 NVDA accepted、DELL/MU blocked 和 T07 regression evidence，
校准 Agent 增益、L1–L4、调用成本、延迟、evidence yield 与 Workbench 产品价值。
本项不调用模型、不修复或晋升失败输出，也不把缺失的 DELL/MU R2 或 NVDA R3
改写为通过。

## Scope

以 SHA256 绑定 10 份不可变证据，覆盖：

- NVDA exact/paired 与 owner acceptance；
- DELL R10 exact、paired L1 failure 和 R11 latest failure；
- MU R2 exact、paired L1 failure 和 latest replacement failure；
- T07 current-worktree regression terminal result；
- S0–S4-T05 全局审计中的 Workbench value boundary。

缺失指标必须记录为 `not_measured`；失败或 quarantine 输出只能用于 failure
taxonomy 与 review-burden 分析，不能晋升为金融事实、产品或 paired pass。

## 结果

- NVDA：历史 S3 R2 owner accepted，L1/L2 pass，L3 Agent 增益可采信，
  L4 有简洁度与中英文交付债；不是 post-transfer R3。
- DELL：完整 `6/12/9` 曾成功，但 paired L1 因 Numeric authority 和
  DELL/NVDA identity 失败；Agent 增益存在但不可采信，R2 未证明。
- MU：完整 `6/12/9` 曾成功，但 paired L1 同样失败；Agent 增益存在但不可采信，
  R2 未证明。
- 三条完整成功 Run 合计 36 calls、212,618 tokens、USD 0.08207367、
  27 Agent Artifacts；最终 owner-accepted 的仅 NVDA 9 Artifacts。
- 当前树的三案工程兼容性有强信号，但 T07 为 `93/4` honest block，没有
  post-transfer NVDA exact product。

Workbench：

- trace/debug/audit surface 已证明；
- task time 与 continue-use 未测量；
- edit burden 与 trust 只有定性证据；
- 三案终端用户产品价值尚未校准。

## 验证与开销

- T08 合同测试：`7 passed`；
- `407` 个 release JSON / Project OS JSONL 机器源严格解析，duplicate/parse error=`0`；
- Project OS scoped preflight：`pass / open blocker 0`；
- credential/model/provider/network/source/external tool：全部 0；
- admission/WorkUnit/Attempt/Run/business Artifact/exact-live/paired/owner/R3：全部 0；
- 没有修改历史 exact、paired 或 owner evidence。

## 阶段处置

T08=`pass_read_only_calibration_complete`，但 S4=`not_passed`、FIN 0.1
=`not_qualified`。下一项：

`S4-T09-REAL-HUMAN-OWNER-REVIEW-AND-QUALIFIED-SENIOR-ELIGIBILITY-SCOPE-DECISION`

T09 必须保留 Human authority。当前可以审阅已存在的 product/blocked evidence，
但没有可签为 NVDA R3 的 post-transfer candidate；Codex、模型 Verifier 或 shadow
reviewer 均不能代签。
