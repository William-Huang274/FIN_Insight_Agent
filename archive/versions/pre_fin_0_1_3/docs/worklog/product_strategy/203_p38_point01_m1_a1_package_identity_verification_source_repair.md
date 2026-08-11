# P38 Point 01 M1-A1 package identity / verification-source 修复

日期：2026-07-14
状态：`superseded_by_204_exact_admitted_audit_rerun_pending_independent_review`

## 问题与决策

total reviewer 复核发现上一轮 M1-A1 package 的 `input_bytes_source` 不在 package digest 中，validator 只核验文件哈希、不复算 package digest，且 gate 会按未绑定的 source 选择 Git index 或 working tree。因此攻击者可改为 `working_tree`、重写文件哈希、保留旧 digest，仍让 gate 误报 `pass`。该问题属于 audit package identity，不是 M1 runtime defect。

本轮只修 audit package validator、runner、oracle policy 和回归测试。M1 runtime、M2/M6/R3、PostgreSQL、网络、工具、模型、业务 Case 与 legacy authority 均未变更。

## 实现

- 新增 `m1_a1_audit_package.py`，冻结 v1.1 canonical manifest schema；`scope`、`package_ref`、`authority_boundary`、`input_bytes_source`、所有 input SHA、A0/fixture/oracle digest、fixed-store fingerprint/absence manifest 及 package-admission ref 均进入 payload digest。
- verifier 先重算 canonical payload digest；不一致立即 `package_digest_mismatch`。仅 `input_bytes_source=git_index` 被允许，删除 runner 的 working-tree verification fallback。
- 增加 package-external、显式注入的 total-reviewer admission contract。它必须精确绑定 admission ref、schema、package ref/digest、scope、authority boundary 与 `william/003/total_reviewer`。未提供、stale 或错绑 admission 均 fail-closed，且不运行 actual probe 或 scoped regression。
- package 输出升级为 v1.1，旧 v1.0 manifest/gate 保留为历史 staged evidence。

## 证据

- 新 package ref：`point01-m1-a1-isolated-adversarial-audit-package-v2-identity-bound`。
- 新 package digest：`c5169899e84a8eb0d99e49b3dbaa3dca0b963d9423364816605df8a49775bcf7`。
- 正式无 admission preflight：package staged-byte verification=`pass`，admission=`package_admission_required`，gate=`fail_closed`，probes=`0`，外部/network/tool/model/provider/PostgreSQL write=`0`。这是预期状态，不能伪造 reviewer admission。
- 四类对抗结果：source-only、file-hash-only、source+hashes（均保留旧 digest）全部为 `package_digest_mismatch`；自签新 digest 无 admission 为 `package_admission_required`，使用旧 admission 为 `package_admission_binding_mismatch`。
- targeted package/audit tests：`8 passed in 20.92s`。
- 仅在测试进程使用 synthetic admission 的隔离回归：scoped M1 `35 passed in 6.74s`；P01 package tamper=`package_digest_mismatch`；P01/P04 cloned-store tamper 均为 `IntegrityError:append_only_table`；fixed/ambient/transport negative 各 `1` 次 typed stop；fixed approval DB SHA-256 前后均为 `ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4`。

## 停止点

本修复记录已由 204 的 exact external admission 单次实际 rerun 所 supersede。不得将 synthetic admission 测试或 204 的 audit gate 当作 M1 retain / M1 complete；204 之后必须停止，等待 independent total-reviewer disposition。
