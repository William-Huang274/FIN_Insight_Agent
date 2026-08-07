# 682 — FIN 0.1.3 S2-06 统一 Supervisor 独立 fresh zero-call proof

日期：2026-08-07

状态：`independent fresh proof pass / admission authority pending / no external call`

## 目标与决定

上一项只达到 shared implementation engineering pass。本项在不签 admission、不调用 DeepSeek/Provider/网络、不生成 corrected paid candidate 的边界内，验证当前干净提交、三案真实冻结输入、case isolation、容量、exact-once、capture-first、mutation 与 raw immutability 能否在两个隔离环境重复成立。

受限 raw 不进入 Git。proof generator 从 clean/synced commit `60b66bc9cdda6ac4130c1e2f44d357313bdac0ef` 生成两个 Git archive，再把 DELL/MU/NVDA 各 11 个 immutable terminal/capture 文件按字节复制到各 archive 的 `.proof_inputs/<CASE>`。两个 fresh Python process 均安装外部 socket hard-block、清除 credential 环境变量，并独立运行相同 proof matrix。

## 结果

两份归一化 worker 输出完全一致，digest=`7580b244b6bf1e0d2cca91550c685f42b417971bffc161f058cc79df0cc61f8f`。每份运行 24 个 supervision/runtime tests，failed/skipped=`0/0`；覆盖跨案/hidden alias、未知数值、依赖 closure、8-unit capacity、transport capture、Lead topology、source-bound deletion、跨 runtime exact-once 和 pre-freeze scoring。

三案真实 raw 由当前 evaluator 和 compiler 重算：

- DELL：`27 findings / 27 corrections / 6 directives / 33,590 request chars / 7 corrected graph + 1 planner = 8 calls`；
- MU：`24 / 24 / 8 / 28,104 / 9 + 1 = 10`；
- NVDA：`32 / 32 / 9 / 35,650 / 9 + 1 = 10`。

三案 evaluation digest、raw terminal digest、raw-output digest 和 prospective admission digest 在两个进程中一致。prospective admission 只在内存编译且 `provider_execution_authorized=false`；没有写 admission 文件。源 raw tree 与 `.codex_runtime/fin013_s2_06` 目标 tree 前后 manifest 完全一致。model/provider/network/source/tool/admission/candidate/score/promotion=`0`。

正式机器结果：`configs/releases/fin_ia_0_1_3_s2_06_unified_supervisor_independent_fresh_zero_call_proof_result_v1_0.json`，result digest=`8b13a14cd3e124136a126e95132cf5b5e4abdc9411a3944401c1f005fa8c03b6`。

## 新发现与边界

第一次 archive worker 在读取 blind input 时统一失败。根因不是 Supervisor：历史 runtime policy 绑定当前 Windows 工作树 CRLF bytes SHA=`689a4f95...bdb59`，而 Git blob/archive 是 LF bytes SHA=`0c2a1bbc...e9be0`。Git 将工作树判定 clean，且 CRLF→LF 后逐字节等于 blob。proof 因此只对这一份历史冻结输入执行 fail-closed byte projection，并在结果中同时记录 worktree/blob SHA 与 normalized equality。

该问题登记为 release portability debt：当前 Windows 同主机 exact execution 的冻结字节合同仍成立，不阻断下一项 admission authority decision；但它不能作为跨平台可复现或 release 证明，S5 前必须将 future contracts 迁移到 canonical JSON/normalized digest，历史运行保持 immutable。

本项只证明工程可重复性。DeepSeek 是否能自然生成有效 SupervisorPlan、纠正三案 L1/L2、关闭 counterevidence/threshold/Verifier 问题、提高研究内容质量或通过 qualified-human acceptance，均未执行、未证明。

## 下一步

单独执行 `FIN-0.1.3-013-S2-06-THREE-CASE-SUPERVISOR-ADMISSION-AUTHORITY-DECISION`。本项不自动签发、不自动消费、不自动进入三案 Provider execution。
