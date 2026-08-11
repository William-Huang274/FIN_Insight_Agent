# FIN 0.1.2 S0C-T02 hermetic topology / allowlisted closure implementation

日期：2026-08-01

任务：`FIN-0.1.2-S0C-T02-HERMETIC-TEST-TOPOLOGY-AND-ALLOWLISTED-PACKAGE-CLOSURE-MINIMUM-ZERO-CALL-IMPLEMENTATION`

结果：`engineering pass / host all-green / T03 ready but unexecuted / S2 blocked`

## 1. 本轮处理的 earliest owners

本轮没有再对旧 `PRE-S2-RB-T03` 打补丁。它的 `56 pass / 1 fail` 与 restricted package 保持不可变。唯一实现包同时处理四个同源 owner：

- host/disposable topology：Git discovery 和 living Project OS 校验只在 host；disposable 只验证冻结 inventory 与当前 Runtime；
- repository closure：每个 seed/recursive dependency 必须 tracked 或匹配 typed allowlist，existing-file-only 不再可用；
- event/projection topology：历史 event 不再竞争 mutable current-next；
- restricted evidence：raw content-addressed capture 不改，failed/quarantined package 不可业务晋升或分享。

## 2. 代码与合同变化

`src/sec_agent/hermetic_test_runner.py` 新增 host inventory compiler、typed reference classification、current-program projection validator和 frozen inventory digest。正式 policy 明确：

- tracked repository paths 可进入；
- explicit allowlist 必须同时给出 path、SHA-256、classification 与 reason；
- package-relative/external audit ref 必须显式分类，不能因字符串像路径就自动复制；
- `.codex_runtime`/`.git`、untracked/ignored、unknown repository ref、traversal、symlink escape 在 object storage 前 fail closed；
- disposable materialization 先验证排序 inventory digest，再验证每个对象 bytes/SHA，过程不需要 `.git`。

当前 Project OS 的 mutable truth 统一写入 `configs/runtime/fin_ia_0_1_2_current_program_projection_v1_0.json`。host validator 对 program backlog、S4 backlog、context、capability/root-cause/pattern ledgers 做一次对账，只把 projection snapshot 放进 future package，六个 living source 本身不作为 disposable inputs。

历史 S0/S1/pre-S2 测试改为按 ID/状态查找冻结事件，不再读取 ledger `[-1]`、当前 next 或当前 runner SHA。S1 deterministic proof 中的 frozen-stage assertion 单独迁到 immutable-event 文件；当前 Runtime 测试只负责当下三案例行为。

## 3. 零调用验证

- 初始复现：`101 passed / 7 failed / 2251 deselected`；7 项均为历史测试读取 mutable current projection；
- 最终 FIN 0.1.2 host matrix：`122 passed / 0 failed / 0 skipped / 2251 deselected`；
- inventory/projection mutation：`8 passed / 0 skipped`。有 symlink 权限时执行真实 symlink integration；无权限时直接对同一 resolved-path guard 执行 outside-root 负例，因此 tracked、typed allowlist、untracked、unknown、traversal、`.codex_runtime`、symlink escape、permutation、digest mutation 与 zero-Git materialization 全部有执行证据；
- 三案例 current runtime + frozen authority：`32 passed`，每案保持 `6/12/12/9`；
- 正式 T03 manifest host compile：`746 paths / 746 tracked / 0 explicit allowlist / 11 recursive refs / 0 forbidden-or-untracked paths`，closure digest=`efdb400c1ae053a1c1da8c4aa3a1f73cdaf7eebd6c20fed5b7bbcb9ba61febf0`。

未创建 output package，未运行两个 disposable，因此 corrective proof packages=`0/1`。credential read/probe、model、Provider、network/source、admission、business Run/Artifact 与 paid reproof 均为 0。

## 4. 真值与停止线

S0C-T02=`engineering_pass`，但 RC-P36-090/091 仍 open/full-chain blocker。DELL R2、MU R2、post-transfer NVDA、NVDA R3、S2 entry 与 FIN 0.1 release qualification 全部仍为 false。

下一项只能是：

`FIN-0.1.2-S0C-T03-INDEPENDENT-TWO-DISPOSABLE-CORRECTIVE-HERMETIC-PROOF-AND-CLOSEOUT`

最多一个新 stage identity 的双-disposable package。若 pass，只允许另做 S2 StagePlan scope decision；若 fail，直接 S0C terminal honest block，不产生 T04、R-number、第二实现包或第二 proof package。
