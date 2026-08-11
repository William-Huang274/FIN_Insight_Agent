# 465｜FIN 0.1 S4-T06 MU DeepSeek admission 前零调用证明

日期：2026-07-29

## 结果

S4/T06 已沿 DeepSeek Pro 主线进入 MU 的 admission 前准备，但当前不具备签发或 exact-live 资格。

已经证明：

- MU Case Pack、`CIK0000723125`、三 Cell、HBM 方法合同与 runtime binding 一致；
- profile=`fin01.s4.research_profile.mu_hbm_three_cell:v1`；
- model=`deepseek-v4-pro`（Pro，不是 Flash）；
- 当前进程存在 `DEEPSEEK_API_KEY`，值未读取或输出；
- T03 fact-empty DELL/MU fixture 的 S4_T04 lineage 漂移已做最小修复；
- DELL/MU 本地 6-node/9-Artifact fixture 恢复；
- profile-aware lineage 与当前 MU proof 相邻回归合计 `22 passed`；
- S4/T06 transition 回归 `100 passed`。

## 首个真实 admission 前阻断

共享 source-grounded loader 当前只注册 DELL。对 MU 的零调用读取精确失败为：

`s4_source_grounded_input_case_unsupported`

因此当前不能生成：

- MU exact source-grounded input；
- input/preparation digest；
- fresh WorkUnit/Attempt/ResearchRun identity；
- prospective exact admission。

这不是 DeepSeek、credential、网络或模型质量问题，也不是 strict-schema transport 问题。它是 T06 应有的案例输入准备缺口。

## 边界

未伪造或复制 DELL 数据，未把 supervisor supplement 直接升级为 accepted runtime evidence；未调用 model/Provider/network/source/tool，未签 admission，未创建 Run/Artifact。

当前主动作仍是：

`S4-T06-MU-DEEPSEEK-MAINLINE-FRESH-EXACT-ADMISSION-PREPARATION-AND-ZERO-CALL-PROOF`

其中必须先完成的唯一 in-scope substep：

`S4-T06-MU-SOURCE-GROUNDED-INPUT-MATERIALIZATION-AND-FRESH-PROOF`

该 substep 只负责 MU 官方来源、Evidence/Numeric/Graph/typed gap/route receipt 的 source-grounded pack 和无付费验证；不得切 Provider、复活 strict-schema transport 或签发 admission。
