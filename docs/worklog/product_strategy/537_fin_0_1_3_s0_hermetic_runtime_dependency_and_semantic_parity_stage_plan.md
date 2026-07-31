# 537 FIN 0.1.3 S0 Hermetic Runtime 依赖与语义等价 StagePlan

日期：2026-08-01
状态：`T01 pass / G0 pass / T02 ready / zero call`

## 问题与授权

用户要求继续 FIN 0.1.3。上一项已经冻结 FIN 0.1.2 internal honest block，并把 RC-P36-090–093 原样转交新的 patch-line S0。本项只允许建立 StagePlan，不允许同轮实现 Runtime、创建证明包或调用模型。

## 判断与决策

0.1.2 的终态失败不是 DeepSeek 或金融判断失败，而是 formal proof 的资源闭包与宿主环境路径类型系统不完整。因此 0.1.3 S0 的 earliest owner 应当是：

- 一个显式、可编译的 RuntimeResourceRegistry；
- 一个只作用于 typed diagnostic fields 的 execution-environment semantic projection；
- 在正式证明前完成全 application import、active-suite collect 和三案例 deterministic behavior closure；
- 只允许一个 implementation bundle 和一个 formal two-disposable package。

为避免再次形成无限修复链，任务固定 T01–T04。T02、T03 或 T04 任一失败都按预定义边界停止，不能自动创建 T05、R/H、replacement family 或 FIN 0.1.4。

## 已完成

- 新增机器 StagePlan，并绑定 FIN 0.1.2 terminal disposition 与 S0C closeout 的不可变 SHA-256；
- 冻结四项 blocker 的独立 owner、resource row schema、typed environment roots、mutation matrix、active set 与 T04 pass 条件；
- 新增 FIN 0.1.3 S0 技术源文档；
- 更新产品版本谱系、program/S4 backlog、current projection、Project OS 台账与 master checklist；
- 新增 immutable StagePlan contract test，并把 current projection validator 迁到 T01 pass/T02 ready 状态。

其中 `hermetic_test_runner.py` 只新增两行 current-projection 状态 allowlist，用于让 host governance validator 识别 T01 pass/T02 ready；没有实现 registry、environment normalization、package materialization 或执行路径行为。

## 结果与证据

- StagePlan：`configs/releases/fin_ia_0_1_3_s0_hermetic_runtime_dependency_and_semantic_parity_stage_plan_v1_0.json`
- StagePlan SHA-256：`034c7714e5773fe48b0d69ed6ab373ba02074e497d803bcd73349932f2177000`
- 技术源文档：`docs/architecture/repository/FIN_0_1_3_S0_HERMETIC_RUNTIME_DEPENDENCY_AND_SEMANTIC_PARITY_STAGE_PLAN_20260801.zh-CN.md`
- 当前投影：`configs/runtime/fin_ia_0_1_3_current_program_projection_v1_1.json`
- Project OS 开工 preflight：pass，open blocker 对当前 StagePlan scope 的计数为 0；T02 next-scope preflight 同样 pass；
- focused StagePlan/current-projection/disposition contracts：`19 passed`；
- FIN 0.1.2/0.1.3 related contract matrix：`143 passed / 2251 deselected`；
- 初次 related matrix 曾出现 `142 passed / 1 failed`：旧 disposition 测试把两份明确标注为 living 的产品/架构源文档也要求永久保持旧 hash。修正后，机器 decision 与 terminal evidence 继续 exact-hash immutable；living 文档改为验证 supersession/current-next，不改写旧决策字节；
- Python compile、四份 touched JSON、三份完整 JSONL 与 `git diff --check` 均通过；敏感信息扫描确认本轮新增 secret-shaped candidate=`0`。历史台账已有候选形状不在本轮新增或改写范围内。

当前没有运行模型、Provider、网络源、admission、business Run 或 business Artifact，也没有创建 T03/T04 proof package。

## 下一项与安全边界

下一项唯一为：

`FIN-0.1.3-S0-RUNTIME-RESOURCE-REGISTRY-AND-TYPED-ENVIRONMENT-PROJECTION-MINIMUM-ZERO-CALL-IMPLEMENTATION`

它最多消费一个 T02 implementation bundle。Prospective registry、environment projection 与 active-suite manifest 在 T02 之前必须保持不存在；历史 failed packages 继续 restricted、不可删除、分享或业务晋升。
