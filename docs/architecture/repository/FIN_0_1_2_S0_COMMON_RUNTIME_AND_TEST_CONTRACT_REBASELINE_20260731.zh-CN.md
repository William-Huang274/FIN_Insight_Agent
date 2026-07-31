# FIN 0.1.2 S0：共同 Runtime 与测试合同重新基线

日期：2026-07-31

## 当前结果

FIN 0.1.2 已从 S0 开始，不再沿着 FIN 0.1 的 S4/T06 继续追加 R8、R9 或字段补丁。S0-T01 把共同 Runtime 的真值所有权、Provider 权限边界、单一来源消费者绑定，以及测试 proof class 做成可执行治理代码和机器清单。

S0-T02 已完成 hermetic dependency package、manifest-selected active-suite runner、typed per-test terminal result、完整内容寻址 stdout/stderr 和双 disposable-runtime parity。最终包在两个独立 root/进程中各执行 24 个选中测试，均为 24 passed，parity digest 相同；890 个仓库依赖文件、6 个显式只读外部证据对象和 Python distribution inventory 均被登记，目标仓库在运行期间未变化。因此 RC-P36-085/086 在 FIN 0.1.2 S0 范围关闭，S0 关闭，下一项进入 S1 StagePlan。没有模型、Provider、业务网络、admission、Run、业务 Artifact 或 release candidate。

## Runtime 合同

共同 source 固定五类本地真值：material number、reporting date、case identity、runtime ID 和 lineage。Provider 只能返回 request-local alias、closed enum 与 bounded judgment atom。prompt、server schema、local validator、fake Provider、selector、renderer、capacity、budget、typed failure 与 capture index 必须共享同一 contract ID、version 和 source digest。

本轮实现的是治理编译器：它会拒绝 truth owner 外移、Provider surface 扩张、消费者缺失、版本漂移、预算倒挂和 capture surface 缺失，并为十个消费者生成相同 source digest 的 envelope。十个生产消费者仍将在 S1 的 deterministic vertical 中逐一迁移并证明；S0 closeout 只证明治理 source、runner、capture 与可复现基线成立。

## 测试合同

测试被明确拆为五类：

1. immutable event：证明当时发生了什么，不得断言当前 next、最后一行 ledger、累积 store count 或当前 code digest；
2. current projection：证明当前版本、active slice、next action 与 mutable backlog；
3. current runtime：证明当前代码、当前 contract digest 和可复现行为；
4. historical audit：历史失败必须可见，但不得隐式代表当前 release gate；
5. release gate：单独汇总当前产品成熟度、L1–L4、Human acceptance 与发布资格。

manifest 中列出的 current suite failure 必须阻断；未列入 current suite 的历史失败仍保留审计可见性，不能批量放宽断言制造全绿。T02 还把 T10、S5 和 0.1.1 freeze 测试中残留的 mutable current-backlog 断言移入 0.1.2 current-projection 测试；历史事件文件继续验证原始 status、count、source binding 和当时 next，不再要求当前 active slice 永远停在旧阶段。

## Hermetic runner 与证据合同

- runner 只封装 manifest 选择的测试、required runner files、`src/sec_agent` Python source、明确 seed 及递归 JSON `*_ref`/`ref` 依赖，不再复制整个历史仓库；
- package 中所有仓库文件、外部只读证据、per-test stdout/stderr/detail 和 process stdout/stderr 都进入 SHA-256 对象库；
- 子进程使用显式 Python environment inventory，清除已知 Provider credential 环境名，禁用第三方 pytest 自动加载；
- historical-audit failure 必须可见，但只有 current-projection、current-runtime 和 release-gate failure 阻断当前门禁；
- 两个 disposable root 的去时长、去绝对路径语义投影必须同 digest；repository readback 不一致时 package 即使测试全绿也判 failed；
- failed package 和 failed test output 均不可晋升为业务 Artifact。

最终 package：`D:/FIN_Insight_Agent_recovery/packages/fin_0_1_2_s0_hermetic_active_suite_final_20260731T2135+0800_head_cee47c2a`；`verification.json` SHA-256=`4ba00673331abf7b0eabf51aa125765817315b9811b818215a39e3c5e0622b0c`。

## 下一门

下一项是 `FIN-0.1.2-S1-REALISTIC-THREE-CASE-DETERMINISTIC-VERTICAL-STAGE-PLAN`。S1 只规划并随后证明 DELL/MU/NVDA realistic fixture、cross-case/date/cardinality/permutation/multi-failure mutation、三案 full-fake 和 production consumer migration；StagePlan 本身不调用模型。FIN 0.1 仍未 release-qualified，DELL/MU R2 与 post-transfer NVDA/R3 仍归 S4 产品证明。

## 后续 S0 corrective stage 决策（2026-08-01）

上述 S0 closeout 与当时的双 disposable `24 passed` 仍是不可改写的历史结果。后续 S1/pre-S2 唯一证明包暴露了两个更早归属于 S0 测试与打包合同的缺口：host-only inventory assertion 被放进无 `.git` 的 disposable current gate；recursive JSON reference closure 又允许 Git-ignored `.codex_runtime` 历史状态进入 package。它们不否定 S0 当时完成的能力，但说明原 S0 的 proof topology 与 package data-minimization 合同不够完整。

项目因此选择新的 `FIN-0.1.2-S0C-HERMETIC-TEST-TOPOLOGY-AND-ALLOWLISTED-PACKAGE-CLOSURE-R1`，而不是重开或改写历史 S0。固定任务只有 `S0C-T01..T03`：当前 T01 只冻结处置；T02 最多一个零调用实现包，负责 host/disposable 分层、tracked/explicit allowlist reference closure、immutable-event/current-projection 分权以及 restricted-package 治理；T03 仅在 T02 全绿后允许一个新 stage identity 的双 disposable proof package。它不是第二次 `PRE-S2-RB-T03`。任一后续任务失败即 S0C honest block，不自动生成 T04、R-number 或 patch-then-rerun。

机器权威：`configs/releases/fin_ia_0_1_2_s0c_hermetic_test_topology_and_allowlisted_package_closure_scope_decision_v1_0.json`。当前下一项仅为 `FIN-0.1.2-S0C-T02-HERMETIC-TEST-TOPOLOGY-AND-ALLOWLISTED-PACKAGE-CLOSURE-MINIMUM-ZERO-CALL-IMPLEMENTATION`；S2、模型调用、产品重证与 release 均未授权。
