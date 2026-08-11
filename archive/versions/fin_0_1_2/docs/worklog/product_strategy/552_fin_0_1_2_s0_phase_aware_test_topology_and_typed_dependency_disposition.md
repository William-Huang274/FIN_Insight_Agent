# FIN 0.1.2 S0 phase-aware test topology 与 typed dependency 项目级处置

日期：2026-08-02

任务：消费用户“继续”，执行 `FIN-0.1.2-S0-CLEAN-QUALIFICATION-FIRST-CREDIBLE-FAILURE-PROJECT-LEVEL-DISPOSITION-DECISION`。本项只决定结构修复、测试归属、依赖合同和后续验证节奏，不实现 runner/registry、不创建 manifest 或 qualification attempt、不调用模型或 Provider。

结果：`project disposition pass / FIN 0.1.2 remains in S0 / one structural implementation pending`

## 1. 为什么不能继续逐文件修

上一 clean qualification 的两套 disposable 均为 `45 passed / 54 failed`，且失败分布一致。只读审计至少发现 19 个 selected-test 直接 repository dependencies、6 个 current projection source paths 和 2 个组合 exact-admission dependencies 未打包。继续把这些路径补进 allowlist，只能使本次快照通过；下一个测试或 projection 一变，同一问题会再次出现。

更早的问题是 phase 所有权：

- pre-execution authority test 在它授权的 attempt 内验证“尚未执行”，必然自我否定；
- host-only Git inventory test 在明确无 `.git` 的 disposable 中执行，必然失败；
- historical audit 与 current Runtime gate 同批运行，使 non-gating findings 与 current failure 混算；
- pytest 临时目录落到宿主 temp，URI 与 escaped Windows repr 又被通用绝对路径扫描器误解。

因此 54 个失败不是 54 个业务缺陷，核心是一个 test execution topology 和 runtime-data dependency contract 缺口。

## 2. 外部模式对照与本项目取舍

按“重复失败先查成熟实现”规则，本轮只读对照了三项官方合同：

- Bazel test rule 的 `data`/runfiles：测试运行时需要的文件应声明为依赖并随运行环境传递，而不是依赖宿主目录碰巧存在；
- pytest registered custom markers 与 strict marker：phase 标签应集中登记，拼写/未知标签在执行前失败；
- pytest `--basetemp`：可把所有 `tmp_path` 固定到一个专用测试根下。

本项目不引入 Bazel，也不把 pytest marker 变成新的隐形权威。采用的最小适配是：机器可读 registry 是单一来源；marker 只镜像 phase 供 collection audit；dependency bundle 提供类似 runfiles 的显式、传递闭包。

## 3. 选定合同

合同 ID：`fin_0_1_2.S0.phase_aware_test_execution_and_typed_dependency:v1`。

五个 phase：

1. `contract_compile`：host 上只编译 registry、phase、dependency bundle 和 exact plan，不执行测试；
2. `host_preflight`：只处理 Git inventory、clean/synced HEAD、current projection 与 authority，不进入 disposable；
3. `disposable_current_gate`：两套 Git-free package 只执行当前 Runtime、contract/mutation、三案例 zero-model、capture 和 environment；
4. `historical_audit`：host 上只读执行，失败必须可见但不阻断 current candidate；
5. `post_run_attestation`：验证 repository 未变化、内容寻址 readback、raw capture、terminal materialization 和双目录 semantic parity。

一个 selected test module 只能属于一个 phase；当前混合模块必须拆分。`gates_current_candidate` 从 phase 派生，不再在 suite 中重复声明可漂移布尔值。

## 4. Typed test dependency compiler

每个 test module 只引用逻辑 dependency bundle ID。第一版 resolver 只保留六类：

- Python import closure；
- RuntimeResourceRegistry closure；
- reference-role repository closure；
- current projection bindings 与 source_paths closure；
- immutable event root closure；
- tracked fixture prefix。

selected disposable tests 读取非 Python repository resource 时必须通过 typed test-resource helper。静态审计发现未声明 repository-shaped literal、unknown/duplicate/cross-phase bundle，或 compiler 遇到 untracked/ignored、`.git`、`.codex_runtime`、traversal、symlink escape、digest drift 时全部 fail closed。禁止把上一轮看到的文件逐个列成例外。

保留已有 29 项 Runtime resources、六类 reference roles、八类 environment roots 和原始内容寻址 capture，不重新实现这些已证明资产。

## 5. 环境与结果合同

- 每个 disposable 的 pytest `--basetemp` 必须是其 typed temporary root 的专用子目录；
- URI 先按 URI 解析，不能把 `fixture://case/evidence` 的 path component 当宿主绝对路径；
- escaped Windows repr 只在 semantic projection 中规范化；
- raw stdout/stderr/detail/collection/terminal 永远保持字节不变；
- 投影后仍存在的未知宿主绝对路径继续 fail closed；
- host、current、historical、post-run 四类结果分别物化，只有规定的 gating phases 参与 S0 candidate 判定。

## 6. 对工程节奏的主动修正

此前把每个零调用测试或 eligibility 当成一次性 product-version budget，造成失败后不断出现 0.1.3/0.1.4 和复杂 authority state machine。这不保护付费证据，反而让测试治理本身成为失败源。

新规则是：

- 本地 unit/fixture/mutation/contract test 是同一实现 slice 内的正常迭代，不算 product version 或 formal attempt；
- 下一项只做一个结构实现 slice；
- 实现工程通过后，formal 双 disposable qualification 仍需用户独立授权；
- 一个 committed candidate 最多一个 formal attempt，同一 candidate 不盲重跑；
- 有根因修复的新 candidate 仍属于 FIN 0.1.2 S0，不自动建 0.1.3；
- formal 再出现新的结构失败族时，先回到计划审计，不自动继续 patch/rerun。

这既保留停止规则，也避免把廉价确定性测试人为变成产品版本生命周期。

## 7. 状态与下一项

- RC-P36-090/091/093/094/095/097：open，已分配到单一结构实现包；
- RC-P36-092/096：保持 closed，不重复重证；
- FIN 0.1.2 S0：blocked，disposition pass、implementation pending；
- S1–S5：not started；FIN 0.2 定义不变；
- implementation/qualification/credential/model/provider/network/business calls=`0/0/0/0/0/0/0`；
- Project OS preflight=`pass / 0 missing / 0 blockers for scope`。

确定性验证：

- disposition/current projection/terminal history/version consolidation/Project OS focused matrix 初轮=`20 passed / 3 failed`；三项失败均为同一 phase-ownership 问题：S0 计划漏机器入口、terminal event test 读取今天 backlog、version-consolidation test 把旧 capability ID 当永久 current；修正为历史事件只验当时事实、current test 验今天 projection 后=`23 passed`；
- 另行执行旧 repository evidence freeze 的全 release JSON/JSONL audit，终态=`1 failed`，在 JSON parse 前因历史固定计数 `409` 与今天实际 `458` 不一致而停止；该测试保留为 historical finding，不修改旧快照、不计入 current gate。这一结果进一步验证 historical audit 必须与 disposable current gate 分相；
- 本轮没有执行新 runner、manifest compiler、fake disposable、formal qualification、模型或业务链。

下一项：

`FIN-0.1.2-S0-PHASE-AWARE-TEST-TOPOLOGY-AND-TYPED-TEST-DEPENDENCY-COMPILER-MINIMUM-ZERO-CALL-IMPLEMENTATION`

本次“继续”没有授权该实现、第二次 qualification、S1 entry、模型调用或版本跳跃。
