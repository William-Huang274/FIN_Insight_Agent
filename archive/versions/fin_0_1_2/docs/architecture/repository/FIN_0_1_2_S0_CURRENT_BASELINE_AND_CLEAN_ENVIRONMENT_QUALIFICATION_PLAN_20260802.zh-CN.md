# FIN 0.1.2 S0 当前基线与干净环境验收计划

日期：2026-08-02
状态：`S0-04 engineering pass / S0-05 terminal failed / S0-06 disposition complete / S0-07 structural engineering pass / S0-08 authority consumed / S0-09 formal pass and S0 closed`

产品计划：`docs/product/FIN_0_1_2_CANONICAL_S0_TO_S5_PRODUCT_PROGRESSION_PLAN_20260802.zh-CN.md`

## 1. S0 只回答什么

S0 只确认当前代码、配置、Prompt、fixture、测试和原始运行记录在本机与干净目录中可复现。这里的 clean-environment acceptance test 只是 S0 验收手段，不是独立产品、版本或复杂治理平台。

## 2. 新起点

以当前累计代码 HEAD 为基础，不回滚原 0.1.3 实现。S0 当前状态是“实现资产存在但最终验收未通过”，不是从零开始，也不是继承历史 proof pass。

首个资格运行后 open S0 问题为 RC-P36-090/091/093/094/095/097；RC-P36-092/096 当时已关闭。它们全部留在 FIN 0.1.2 S0 修复，并已由 S0-09 正式正证据关闭；模型质量、真实研究结果和 Workbench 用户价值不进入本阶段。

## 3. 执行顺序

### S0-01 版本与当前状态归并

已完成。恢复 FIN 0.1.2 为当前产品版本；原 0.1.3/0.1.4 仅保留为历史修复与提案；建立单一 current projection 和 supersession mapping。

### S0-02 当前代码资产盘点

已完成只读初审。详细结果见 `FIN_0_1_2_S0_CURRENT_CODE_ASSET_AUDIT_20260802.zh-CN.md`。

### S0-03 Owner 审核（已完成）

用户以“继续”批准保留、修复和退出当前入口的分类，并授权严格限于本地零调用 S0-04 集中修复。

### S0-04 集中修复（工程通过）

已完成一轮按根因分组的修复：

1. 当前状态与历史事件分权：历史测试只验证当时发生的事件，current projection 独立表达今天的版本和下一步；
2. 简化 clean-environment runner：不把产品版本、用户授权和一次测试运行编织成复杂硬编码状态机；
3. 统一当前资源和引用入口：复用已实现的 29 项资源、六类引用和八类环境路径，但建立版本中性的 current manifest；
4. 清理测试归属：S0 只收当前基础测试，S1 三案例逻辑作为依赖回归，不让旧 closeout 测试拥有 mutable truth；
5. 对当时的 RC-P36-090–096 最早责任代码做集中修复，并给每类根因增加确定性回归；后续 qualification 证明其中 092/096 已关闭，其余问题仍需结构性处置并新增 097。

本地验证结果为：current manifest selected suite=`95 passed`，FIN 0.1.2/0.1.3 全部 S0 兼容合同=`147 passed`，DELL/MU/NVDA 零模型链=`31 passed`。这些结果只建立 S0-04 engineering pass；尚未执行干净环境 package、双目录比较或 S0 closeout。

如果实现中发现新问题，先判断阶段归属。S0 问题修在 S0；S1–S5 问题只登记后传。不会自动增加产品版本。

### S0-05 本机与干净环境验收

资格授权与唯一 attempt 均已消费。runner 在 clean/synced HEAD 上接受 exact authority，成功构建 789-file 内容寻址 package 并执行两套 disposable 测试；终态为每套 `45 passed / 54 failed`，repository readback 未变化，897 个内容引用/15,827,581 bytes 复核通过，模型与网络调用为 0。

首个可信失败不是某个业务字段，而是 current manifest 的 phase/test dependency closure 不完整：

1. pre-execution authority 测试被放进它自己授权的 disposable 运行；
2. host-only Git inventory 测试被放进无 `.git` 的 package；
3. selected tests 直接声明的 tracked JSON/JSONL/Markdown 依赖，以及 `current_projection.source_paths`，没有进入 typed closure；
4. pytest basetemp 未绑定 disposable temporary root，escaped Windows repr 与 `fixture://` URI 又造成语义路径误报。

因此不能逐个把本次缺少的文件加入 allowlist。该结论触发了下方 S0-06，由项目级处置先决定统一的 phase 分类、typed test-resource dependency compiler、pytest temporary-root 绑定和 raw-preserving diagnostic projection 边界；S0-05 本身没有授权直接实现或第二次 qualification。

顺序为：

1. 当前核心单元/合同/mutation 测试；
2. 本机 import、collection、三案例 full-fake 和失败留存；
3. 一个干净目录完整运行；
4. 最终两个相互独立目录运行并比较业务语义；
5. repository readback 和原始失败证据留存检查；
6. S0 closeout 与当前 open RC-P36-090/091/093/094/095/097 逐项处置。

失败 attempt 永久保留。允许在定位根因、完成修复并添加回归测试后用新 attempt ID 重验；禁止不改任何条件直接碰运气重跑。

### S0-06 项目级根因处置（已完成）

选定 `fin_0_1_2.S0.phase_aware_test_execution_and_typed_dependency:v1`，不增加产品版本，也不重做已经 live-proven 的 29 项 RuntimeResourceRegistry、六类 reference role 或 current/event/attempt 分权。

实施边界如下：

1. 单一 `TestExecutionContractRegistry` 同时拥有 test module 的 phase、是否阻断 current candidate 和逻辑 dependency bundle；同一 selected module 只能属于一个 phase，混合模块必须先拆分；
2. `contract_compile` 在运行前验证注册表、阶段和依赖闭包；`host_preflight` 独占 Git/current authority 检查；`disposable_current_gate` 只执行当前 Runtime、mutation、三案例 zero-model、capture 和 environment；`historical_audit` 单独只读且不阻断；`post_run_attestation` 负责 repository/readback/parity/terminal；
3. dependency bundle 使用 typed resolver 闭合 Python import、Runtime resources、reference-role repository refs、current projection bindings/source_paths、immutable event roots 和 tracked fixture prefixes；禁止按本次缺失清单逐文件加例外；
4. disposable test 对非 Python repository resource 必须通过 typed test-resource helper 访问；未声明的 repository-shaped literal、unknown bundle、untracked/ignored、`.git`、`.codex_runtime`、traversal、symlink escape 和 digest drift 均 fail closed；
5. pytest `--basetemp` 固定为每个 disposable temporary root 的专用子目录；URI 先按 URI 解析，escaped Windows repr 只在 semantic projection 中规范化，raw stdout/stderr/detail/collection/terminal 保持字节不变；
6. current gate、historical findings 和 post-run attestation 分开物化，历史失败既不能被隐藏，也不能再被统计为 current Runtime failure。

本次处置还纠正了旧 proof 预算：本地 unit/fixture/mutation 是实现期正常验证，不算产品版本或 formal attempt；正式双 disposable qualification 只针对 committed candidate，每个 candidate 最多一次且需另行授权。同一 candidate 不重跑；修复产生新 candidate 时仍留在 FIN 0.1.2 S0。出现新的结构失败族，先修改计划，不自动创建新版本。

上述结构包已由 S0-07 实现。该实现仍不等于 clean qualification 或 S0 通过。

历史机器入口：

`FIN-0.1.2-S0-PHASE-AWARE-TEST-TOPOLOGY-AND-TYPED-TEST-DEPENDENCY-COMPILER-MINIMUM-ZERO-CALL-IMPLEMENTATION`

### S0-07 phase-aware topology 与 typed dependency 实现（工程通过）

已完成选定的单一结构实现，没有逐文件补缺失清单：

1. `TestExecutionContractRegistry` 成为五阶段、module ownership、gating 和六类 dependency bundle 的机器权威；旧 suite schema 仅保留兼容投影，runner 执行时按 registry 分类；
2. host preflight、两套 Git-free disposable current gate、historical audit 和 post-run attestation 分别执行与物化；历史 finding 继续可见但不能升级为 current gate failure；
3. typed dependency compiler 从 Python import（含 lazy registry 与 relative import）、29 项 Runtime resources、reference-role repository refs、current projection bindings/source_paths、immutable event roots 和 tracked fixtures 编译 closure；candidate 不使用 broad repository prefix 或逐文件 allowlist；
4. selected disposable test 的直接非 Python repository read 使用 typed helper；未声明 bundle、direct ROOT read、unknown/duplicate phase、mixed module、traversal 与 forbidden root 均有负向回归；
5. 每个 disposable 的 pytest basetemp 都位于其 typed temporary root 下；`fixture://` 先按 URI 分类，双转义 Windows repr 只在 semantic projection 中规范化，raw evidence 不改；未知宿主路径继续 fail closed；
6. 最终显式 inventory 工程 full-chain（不是 formal qualification）为 784 tracked files / 0 allowlist；host=`31 passed`，两套 disposable 各=`58 passed / 0 failed / 0 collection error / 0 unknown path`，semantic parity=true，post-run attestation=pass；historical audit=`23 passed / 1 finding`，唯一 finding 是旧 R2.1 authority 已被历史 attempt 消费，按预期 non-gating。

实现记录：`configs/releases/fin_ia_0_1_2_s0_phase_aware_test_topology_and_typed_test_dependency_compiler_minimum_zero_call_implementation_v1_0.json`。

RC-P36-090/091/093/094/095/097 已达到 engineering repaired，但仍保持 open，等待 separately authorized、clean/synced、committed candidate 的正式 qualification 复证；本轮没有关闭 full-chain blocker，也没有使用 formal attempt 预算。

历史下一项（已由 S0-08 消费）：

`FIN-0.1.2-S0-PHASE-AWARE-CLEAN-ENVIRONMENT-QUALIFICATION-AUTHORITY-DECISION`

### S0-08 phase-aware clean-environment qualification 授权（已签发，未执行）

用户以“继续”授权本项。Project OS 对该 authority scope 的预检为 pass，当前 engineering base HEAD=`16a5d4da0b2dd387a9d6564a8f9b60a17803da12`，当时分支 clean 且与远端一致。新 authority、formal manifest R2.3 和 current projection v2.5 共同固定：

1. 只允许一个新 attempt：`attempt_fin_0_1_2_s0_phase_aware_clean_environment_qualification_20260802_r2`；
2. 只允许输出到预先冻结的 repository 外受限目录；同名 final/failed/partial 任一存在即视为已消费；
3. exact manifest 使用 phase-aware registry 和 typed dependency closure，formal runner 默认入口已指向 R2.3；
4. contract compile、host preflight、两套 Git-free disposable current gate、独立 historical audit 和 post-run attestation 必须按阶段物化；
5. model/Provider/network/business 调用上限均为 0，失败输出不可晋升；
6. 同 attempt 重试和自动 replacement 都为 0，失败不创建新产品版本。

authority=`configs/releases/fin_ia_0_1_2_s0_phase_aware_clean_environment_qualification_authority_decision_v1_0.json`；manifest=`configs/releases/fin_ia_0_1_2_s0_current_active_test_suite_manifest_v2_3.json`；current projection=`configs/runtime/fin_ia_0_1_2_current_program_projection_v2_5.json`。

当时下一项（已由 S0-09 消费）：

`FIN-0.1.2-S0-FRESH-CLEAN-ENVIRONMENT-QUALIFICATION-EXECUTION-AND-CLOSEOUT`

### S0-09 正式资格运行与 S0 收口（通过）

唯一 R2 attempt 在 clean/synced HEAD=`6340aeef857ad3c48226a530ace6bb8204b8decd` 上执行一次，exit=0，未重试、未替换：

1. contract compile=`pass`，绑定五阶段、六类 dependency bundle 和冻结 execution-plan digest；
2. host preflight=`31 passed / 0 failed / 0 collection error`；
3. 两套 Git-free disposable 各=`58 passed / 0 failed / 0 collection error`，semantic/raw parity=true，未知宿主绝对路径各 0；
4. package=`789 tracked / 0 allowlist / 0 external dependency`，repository 在运行前后不变；per-test 和 process stdout/stderr 均内容寻址；
5. historical audit=`23 passed / 1 non-gating finding`。该 finding 是旧 R2.1 authority 的“尚未消费”历史断言在旧 attempt 已消费后失败，属于预期历史事实，不是 current gate 失败；
6. RC-P36-090/091/093/094/095/097 关闭，092/096 保持关闭，S0=`pass_closed`。

证据摘要：`configs/releases/fin_ia_0_1_2_s0_phase_aware_clean_environment_qualification_success_and_s0_closeout_v1_0.json`；current projection：`configs/runtime/fin_ia_0_1_2_current_program_projection_v2_6.json`。

当前下一项：

`FIN-0.1.2-S1-ENTRY-AND-HISTORICAL-ASSET-REUSE-SCOPE-DECISION`

S1 不从头重做，也不直接继承历史“已通过”声明。先对照当前 S0 package 已覆盖的三案例测试与历史 S1 资产，确认哪些可复用、哪些仍缺 current-baseline 验收，再冻结 S1 最小剩余工作。

## 4. 简化后的通过标准

S0 通过必须同时满足：

- 当前生产模块能导入，当前测试能收集；
- 所需资源均来自 Git tracked 或明确带 digest/type/reason 的受控入口；
- `.git`、`.codex_runtime`、未跟踪文件和宿主绝对路径不能成为隐藏依赖；
- DELL/MU/NVDA 零模型链保持基础回归，但不在 S0 声明产品质量；
- 失败仍先保存完整安全 capture 和 terminal result；
- 两个独立目录得到一致的业务语义结果；
- 历史 event、当前 projection 和运行 attempt 三类真值互不冒充；
- 当前 open RC-P36-090/091/093/094/095/097 关闭，或有经用户接受且不影响 S0 目标的明确外部边界；已关闭的 092/096 不重复重证。

## 5. 停止和反思规则

- 同一失败原因未修复前不重跑；
- 连续出现同一根因说明修复无效，回到最早责任代码；
- 连续出现新的不同 S0 缺陷时，先向用户报告 S0 设计可能仍不完整，再修改计划；
- 不因测试失败新建产品版本；
- 不为了测试全绿降低资源、身份、数字、日期、引用或原始证据标准；
- 执行过程中必须遵守 `docs/project_os/senior_assistant_collaboration_policy.zh-CN.md`，主动指出不合理需求和规划。

## 6. 本计划没有授权的动作

S0-04 本地集中修复、S0-05 失败终态、S0-06 项目级 disposition、S0-07 phase-aware/typed dependency 零调用工程实现和 S0-08 authority decision 均已完成。现在只授权下一项按冻结合同创建并执行一次 formal clean qualification attempt；没有授权读取凭据、调用 DeepSeek/OpenAI/Sub2API、访问业务网络、执行 exact-live 或 DELL/MU/NVDA 产品验收，也没有授权自动 retry/replacement、S1 entry、tag、release 或 production。formal run 成功也必须先做证据审查和 issue disposition，不能自动宣布 S0 通过。
