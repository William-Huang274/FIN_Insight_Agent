# P38 Point 01 M2-A1 Phase B0：operational-qualification v2.4 refreeze

日期：2026-07-16

状态：`phase_b0_refrozen_pending_independent_review`

## 已授权范围

仅执行 superseding execution package、compatibility plan 和 baseline blueprint 的静态重冻结；没有签发 admission、receipt 或 nonce，没有登记/消费 ledger，没有创建新的 runtime namespace，也没有重跑 baseline 或任一 16-scenario actual probe。

## 冻结证据

- execution-ready package v2.4：`be4b8e787ebe788cefe1c868010b73395401b42b0f1810b996b01e5bfeacc553`
- package gate：`d8dbebdf61c9674f0204cb7c6c3a482a5fdb59dd54cdf7231230aa77bf5ddf45`
- receipt-plan compatibility v1.1：`c393d3c8229f6ecba88e62d47bbfe6257671b781e7f205ff5ef4e8b155fc9eb2`
- plan gate：`a0db8eb6b3641202692809e99fb4b4ad57615719ed116d74f44786715db4642c`
- baseline blueprint v1.1：`6a6ec4f4ddd0a663b15b133758793ae858fead459a2b14cbbae077c36ea24a50`
- blueprint gate：`82b4157cffd814fffe3560e4a4df0c4175d1ec23a7eb56c8bc16f2d2f61316d7`

v2.4 package 绑定 RC-P38-024 classification/package/gate，并将 v2.3 package、v1 blueprint 与已消费 baseline actual 标为 historical-only、expired/consumed/non-replayable。计划仍为 P01/P02/P03=`4/6/6`，baseline-first、每场独立 JIT admission+receipt、checkpoint 和 fail-fast/no retry/no replay。由于 P03 transport 语义已改为 context/constructor/connect/request 分层，旧 plan 不能用于 v2.4。

## 验证

- M2-A1 targeted suites：`59 passed in 150.37s`。
- M2 runtime/planning/serializer/shadow adjacent suites：`40 passed in 19.74s`。
- `compileall`、`git diff --cached --check` 通过。
- 新 clean-child regression 证明父进程 `requests` preload 不污染 `python -I` child；canary 在 harness import 前安装。
- 显式加载 M6 transport-owning module 只记录 context；无 admission 时 `requests.Session` constructor 被阻断，connect/request/success 均为 0。
- fixed approval DB before/after SHA-256：`ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4`。

## 边界与下一步

M2 的 milestone scope 仍是 `complete_deterministic_shadow`，operational qualification 仅为 `pending_superseding_package_and_baseline_requalification`。M3–M5 仍保留既有 scoped closeout，adversarial operational requalification pending。

不得把这次 refreeze 记为 baseline success、M2-A1/M2 complete 或 M3–M5/M6 closeout。下一步必须等待 total reviewer 对 exact v2.4 package/plan/blueprint 的独立审核；只有新审批才可能开启唯一 fresh baseline JIT window。

## B0.1：production preflight / authority schema repair（2026-07-16）

初版 B0 被独立审计退回：v2.4 package 不能被 production preflight 读取、plan/blueprint 漏 cross-gate binding、authority template 非 runtime-compatible field contract。整改将 version dispatcher、Phase-A artifact/hash/transport/nonreplay/cross-gate 复核放入 production `m2_a1_execution_receipt`；v2.4 clean-child/registrar 直接拥有 v2.4 identity，不再动态加载或 monkeypatch v2.3 entrypoint。

- package：`615a73da64eff69a56a13b42d6c59c892820f15c4de7dc3a2be3c425d2aee68e`
- package gate：`14b09fe4900b7cfddc6c2862449ba308094c58e9556ae3d6c154833560e273f8`
- plan / gate：`b10ccce186912fb1a34f8c714269e813d07929f1d1ac0457b207ab6c709f9b15` / `d7d88be750dd82b18316e3e1528b4f0abe9ecdc5aaddcb3de09b1da504b66a76`
- blueprint / gate：`09ee9176a8090f1c42885fb2fab33c118a2d7b41cab2b66d694e478ff0b873a8` / `42814b706de7095ca42e3016fd12f3e36dbd8ae8fd0e6bff81139478cb501e22`

验证：production-path synthetic preflight=`9 passed`，v2.4 static/isolation=`4 passed`。覆盖 missing admission（`package_admission_required`）、synthetic v2.4 admission read-only preflight、v2.3 admission/unknown mixed schema/cross-gate/repair-gate tamper、pre/post-consume staged drift；post-consume synthetic fixture 只记录 `outcome_unknown`，未 materialize runtime/output 或运行 scenario。所有真实 authority/receipt/baseline/actual/external/model/tool/provider/fixed/business/legacy write=0；fixed DB fingerprint 仍为 `ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4`。

当前仅可写 `phase_b0_1_production_schema_repair_refrozen_pending_independent_review`。B0 初版 artifacts 仅保留历史证据；本轮不得签发 admission、登记/消费真实 receipt 或重跑 baseline。

## 唯一 v2.4 baseline JIT 窗口：pre-consume dispatch incident（2026-07-16）

总审计批准后，已按 binding 生成 fresh v2.4 admission（digest `1906d86bb5a419cceaa3a83cf27ef5ca5cd85e23b263a6818db322d22c7f054c`）、authority wrapper（`07757f63f73d0084271352a0a10a4ef0b0d3c68087bc581cad67dc8bd3ea565a`）和 single-use receipt（`596fcf570a7abc1d4344ec6db354a4670e1c8a59e48f97396d5bf27c2401b870`）。registrar 的 exact v2.4 preflight 与 `REGISTERED` event 成功。

但 frozen v2.4 parent supervisor 的 `argparse.REMAINDER` 会把 delimiter `--` 原样转发给 clean child；child 在 `consume_before_run` 前以 unrecognized arguments 终止。因此此窗口没有 actual/oracle/reviewer，ledger 仅有 `REGISTERED`，receipt 仍 active-unconsumed 但已 quarantine，禁止 direct-child fallback、retry、replay、renewal 或第二场。runtime/output 未 materialize，network/model/tool/provider/fixed-store/business/legacy mutation=0，fixed hash 前后仍为 `ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4`。

incident digest=`a59076a127c0b76902dc362aee94980427660fbc695b47e9c94fd73228cb9a18`。需 total reviewer 决定 receipt expiry/disposition 与 parent dispatch owned repair/refreeze 范围；本次窗口不构成 baseline attempt success、M2 operational qualification 或任何 downstream authority。
