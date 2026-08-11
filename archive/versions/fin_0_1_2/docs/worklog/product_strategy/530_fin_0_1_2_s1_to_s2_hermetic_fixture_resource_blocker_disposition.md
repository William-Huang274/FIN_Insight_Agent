# Worklog 530 — FIN 0.1.2 S1→S2 hermetic fixture/resource blocker disposition

日期：2026-07-31
状态：`decision pass / pre-S2 implementation pending / S2 entry blocked`

## 本轮结论

S1 保持 terminal honest block，不重开 S1、不创建 S1-T05，也不以主机绿或两套 disposable 的相同失败替代 G2。项目选择一个独立且有界的 pre-S2 rebaseline：

`FIN-0.1.2-PRE-S2-HERMETIC-FIXTURE-RESOURCE-REBASELINE-R1`

它只关闭 S1 与 S2 之间的 repository-owned dependency closure，不承担模型能力、金融产品验收或 FIN 0.2 generalized compiler。

## 三个最早 owner

1. MU realistic fixture
   - 当前 exact input 通过历史 S4 helper 读取 ignored `.codex_runtime` object；
   - 未来唯一 owner 为 `tests/fixtures/fin_0_1_2/mu_realistic_three_cell_exact_input_v1.json`，loader 为 `tests/contract/fin_0_1_2_realistic_fixture_support.py`；
   - fixture 必须绑定原 object SHA、input digest、case/version、provenance 与 failed-output non-promotion boundary，不得包含凭据、Authorization、Provider private reasoning 或可变 Run 状态。

2. Runtime non-Python resources
   - `research_skills.SKILL_FILES` 当前登记 16 项、总计 53,382 bytes；
   - future inventory 为 `configs/runtime/fin_ia_0_1_2_runtime_nonpython_resource_inventory_v1_0.json`；
   - path/bytes/SHA 必须与 registry 精确一致，missing、duplicate、path/hash drift 或 unknown runtime read 在 pytest 前 fail closed。

3. Semantic parity
   - raw per-test/process capture、ref 与 hash 继续 byte-exact，不重写；
   - 另建 semantic projection，只允许替换 exact disposable repository root、package root 和 hermetic temporary parent；
   - business values、nodeids、failure codes、relative paths 与 unknown absolute path 保持 comparison-significant，未知绝对路径 fail closed。

## 固定预算与 stop rule

- `PRE-S2-RB-T01`：本处置，已通过；
- `PRE-S2-RB-T02`：最多一个 minimum zero-call implementation bundle，尚未开始；
- `PRE-S2-RB-T03`：只在 T02 全绿后允许一个新的 two-disposable replacement proof package；它不是历史 T03/T04 重跑；
- T03 成功只授权另行编制 S2 StagePlan；失败则 pre-S2 honest block，不自动产生第二实现包或第二证明包；
- 不放宽 hermeticity 或金融 L1，不把 L2–L4 表达问题塞回本结构包，不在没有调用证据时归因模型、DS 或 Provider。

## 验证

- decision SHA-256：`f5b7abd6803220ddc3e9f7fce49889b6e75fdca8a9d7b25b0b0ed4375d10e62a`；
- decision、program backlog、S4 backlog 均通过 duplicate-safe JSON 解析；
- capability、root-cause、external-pattern 三份 JSONL ledger 全量逐行通过 duplicate-safe 解析；
- 新 disposition 合同及 S0/S1 current-projection 回归：`41 passed in 4.59s`；
- manifest-selected current host suite：`24 passed in 1.40s`；
- 全部 FIN 0.1.2 合同测试：`83 passed in 9.58s`；
- fixture materialization、resource inventory、parity Runtime mutation、replacement proof、credential probe、model/provider/network/admission/business Run/Artifact 均为 `0`。

## 产品真值

S1=`closed_honest_block_not_reopened`；S2 entry=false；DELL R2=false；MU R2=false；post-transfer NVDA exact product=false；NVDA R3=false；FIN 0.1 release qualified=false。

## 当前下一项

`FIN-0.1.2-PRE-S2-HERMETIC-FIXTURE-RESOURCE-REBASELINE-MINIMUM-ZERO-CALL-IMPLEMENTATION`

该项必须一次实现 fixture、resource inventory 和 semantic parity 三个 owner，再用 host full matrix 暴露结构问题；不得重新回到 one-by-one live 修补节奏。
