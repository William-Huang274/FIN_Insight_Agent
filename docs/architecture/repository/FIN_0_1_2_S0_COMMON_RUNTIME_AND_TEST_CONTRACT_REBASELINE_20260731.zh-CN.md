# FIN 0.1.2 S0：共同 Runtime 与测试合同重新基线

日期：2026-07-31

## 当前结果

FIN 0.1.2 已从 S0 开始，不再沿着 FIN 0.1 的 S4/T06 继续追加 R8、R9 或字段补丁。本轮完成 S0-T01：把共同 Runtime 的真值所有权、Provider 权限边界、单一来源消费者绑定，以及测试 proof class 做成可执行治理代码和机器清单。

S0 尚未关闭。生产 Runtime family 尚未迁移，active-suite runner 尚未按 manifest 执行，RC-P36-085 的 hermetic package、完整 stdout/stderr 与 disposable parity 仍未证明。因此不会进入 S1，也不会调用模型。

## Runtime 合同

共同 source 固定五类本地真值：material number、reporting date、case identity、runtime ID 和 lineage。Provider 只能返回 request-local alias、closed enum 与 bounded judgment atom。prompt、server schema、local validator、fake Provider、selector、renderer、capacity、budget、typed failure 与 capture index 必须共享同一 contract ID、version 和 source digest。

本轮实现的是治理编译器：它会拒绝 truth owner 外移、Provider surface 扩张、消费者缺失、版本漂移、预算倒挂和 capture surface 缺失，并为十个消费者生成相同 source digest 的 envelope。它尚未宣称十个生产消费者都已改接新 source。

## 测试合同

测试被明确拆为五类：

1. immutable event：证明当时发生了什么，不得断言当前 next、最后一行 ledger、累积 store count 或当前 code digest；
2. current projection：证明当前版本、active slice、next action 与 mutable backlog；
3. current runtime：证明当前代码、当前 contract digest 和可复现行为；
4. historical audit：历史失败必须可见，但不得隐式代表当前 release gate；
5. release gate：单独汇总当前产品成熟度、L1–L4、Human acceptance 与发布资格。

manifest 中列出的 current suite failure 必须阻断；未列入 current suite 的历史失败仍保留审计可见性，不能批量放宽断言制造全绿。

## 下一门

下一项是 `FIN-0.1.2-S0-HERMETIC-PACKAGE-AND-ACTIVE-SUITE-RUNNER-MIGRATION`：建立完整 package inventory、typed per-test result、内容寻址 stdout/stderr 和 disposable-runtime parity，并让 runner 真正按 active manifest 选择当前门禁。只有 G4/G5 通过后才允许关闭 S0、进入 S1。
