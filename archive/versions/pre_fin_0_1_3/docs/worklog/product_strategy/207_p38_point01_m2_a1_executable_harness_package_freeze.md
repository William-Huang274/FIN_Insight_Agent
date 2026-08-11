# P38 Point 01 M2-A1 executable audit harness/package freeze

日期：2026-07-14

状态：`executable_package_frozen_pending_exact_admission`

## 本轮授权与停止线

total reviewer 已接受 M2-A1 v1.1 的 design contract，但本轮只允许实现 future audit 的 executable harness 和 Git-index package freeze；不允许运行 `A0-M2-P01/P02/P03` actual probes。本轮没有调用 compiler、shadow compiler、serializer、model、network、tool、provider 或任何 canonical/fixed/business/legacy store。

冻结包只为下一次 exact external admission 准备，不能代替 admission 或 single-use execution receipt。M2-A1、M2、M3、M6/R3 均未完成，也没有获得新 authority。

## 实现的 executable contract

- `M2A1ActualRunner` 只接收 corpus case、已冻结 policy/pack refs、显式 temporary root 与 injected canary；其公开 actual entrypoint 在本阶段固定抛出 `m2_a1_actual_probes_not_authorized`。
- assembly 不把 `CompilerInputSeed` 当作 `CompilerInputContract`：先调用 `adapt_legacy_research_objective()`，要求 adapter 产出的 `PackSelectionDecision` 为空，然后只用 seed 的 versioned `pack_selection` 显式合成 strict `CompilerInputContract`。合成前逐项验证 tenant、project、case、query、as-of、universe、language、policy、required cells 和 pack selection，任何 drift 都 typed fail-closed。
- `M2A1ImmutableActualResult` 先 terminalize 并形成 canonical digest；独立 oracle evaluator 只能读取该 immutable result 和独立 oracle mapping。actual runner 不接收、读取、hash 或 import oracle。
- reviewer gate 要求 exact executable package、immutable actual digest、independent oracle verdict、zero forbidden counts 和 valid single-use receipt；现 package 的 `actual_probes_currently_authorized=false`，所以 gate 只能 `package_admission_required`。
- oracle/store/ambient-path/transport/model canary 都为 injected no-I/O guards；它们在 constructor/open 之前 typed stop，不会以 hash-before/after 代替 access detection。
- receipt wrapper 是不持久化的 future-contract validator，当前既不登记也不消费 receipt。

## 冻结与验证

- package ref：`point01-m2-a1-executable-adversarial-audit-package-v1`。
- package digest：`1a51d745f14751a19add0d0f72d5296879fdab95d0ee84f837b481ddd9cf2061`。
- gate digest：`294a2206001bd552fc75644e089636297fb87ffa0102d54c41dcf5db4b2d70e7`。
- gate status：`executable_package_frozen_pending_exact_admission`；`actual_admission_status=package_admission_required`。
- package 以 Git-index bytes digest-bind v1.1 corpus/oracle/matrix、A0 design digest、fixed approval DB fingerprint/absence manifest、M2 runtime staged inputs、assembly/evaluator/gate/canary/receipt/test code 与全部 authority fields。fixed approval DB 的已知 fingerprint 仅作为 bytes 绑定值，未打开或读取。
- 定向回归：assembly/harness boundary `9 passed`，executable package static/tamper `4 passed`，合计 `13 passed`。

## 计数与下步

freeze gate 记录 compiler/shadow actual、model、network、external tool、provider、canonical/fixed/business/legacy store open/write、PostgreSQL write、business mutation 和 legacy authority mutation 均为 `0`。没有 external package admission、execution receipt 或 actual result 被写入。

下一步必须先由 total reviewer 对上述 exact executable package 给出 package-external exact admission；之后仍须单独登记/验证 single-use receipt，才可申请一次 isolated temporary SQLite 的 actual audit rerun。不得自动执行 P01/P02/P03，也不得进入 M3 或 M6/R3。
