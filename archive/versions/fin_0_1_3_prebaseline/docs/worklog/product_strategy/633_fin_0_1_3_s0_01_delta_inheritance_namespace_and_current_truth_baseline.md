# 633 FIN 0.1.3 S0-01 delta inheritance、namespace 与 current truth baseline

日期：2026-08-06
状态：`S0_01_engineering_pass / RC_P36_133_closed / S0_02_next`

## 问题

FIN 0.1.3 作为新的修复收口版本重新启用，但仓库保留早先已合并/放弃的同名 S0 资产。如果只按文件名或版本号复用，会把旧 proof、失败处置或 projection 错当成本轮 current authority。同时 T07-C 的本地真实 accept 尚需在不泄露 reviewer 私有信息的情况下投影到 repo source of truth。

## 实现

- 新增 deterministic materializer：`scripts/releases/materialize_fin_ia_0_1_3_repair_closeout_s0_01_delta_baseline.py`。
- 生成 canonical delta baseline 和 active-suite successor，使用 `fin_ia_0_1_3_repair_closeout_*` 前缀区分本轮正式版本。
- 对 47 个旧资产逐文件记录 SHA 和处置：
  - 18 个 release config：历史事件，不是 current authority；
  - 11 个 runtime projection：已 supersede，只保留历史；
  - 5 个 version-neutral runtime：S0-02 exact-digest 复用候选；
  - 3 个 version-neutral test：S0-02 复用候选；
  - 10 个历史 test：保留历史断言，不是 current gate。
- 新 active-suite 当前只选择 S0-01 canonical test。8 个复用候选均 `selected=false / gates_current_release=false`。
- 以 SQLite `mode=ro` 投影 T07-C：只保存 `1 session / 4 security events / 1 decision`、NVDA accept、公开绑定和 acceptance flags；不查询 session row 内容，不保存 credential digest、session ID、reviewer ref 或 reviewer note。
- 将 FIN 0.1.3 research-content hard gate 作为 source binding 和 current requirement 继承，仍标记 runtime translation pending。

## 验证

- S0-01 focused contract：`5 passed`。
- S5 handoff adjacent regression：`5 passed`；修正旧 namespace 计数测试，使其明确排除新 canonical `repair_closeout` prefix，不修改 S5 decision 或旧资产。
- canonical 与两个系统临时输出逐字节 SHA 相同：deterministic materialization pass。
- secret-safe 字段扫描：pass。
- old acceptance mutation 和 old test authority promotion mutation：均 fail closed。
- 本轮 model/provider/network/source/business run/Artifact/private-store write 均为 0。

## 产品与研究边界

本项解决的是版本/证据权威和 current truth 一致性，没有改善 DELL 财务数字、检索覆盖、Graph、Claim、Writer 或最终报告质量。旧 bounded R2/R3 只作为历史/current truth anchor；一旦 input、data 或 contract 改变，不能自动晋升为新 candidate acceptance。

## 下一步

执行 `013-S0-02`：收口 shared runtime admission/replay 与 RC-P36-128 historical receipt vs living source debt；对 8 个 reusable candidates 做 exact-digest semantic/dependency revalidation，合格者再进入 active-suite successor。
