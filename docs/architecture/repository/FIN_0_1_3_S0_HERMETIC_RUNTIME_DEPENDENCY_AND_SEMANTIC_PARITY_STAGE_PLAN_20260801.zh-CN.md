# FIN 0.1.3 S0 Hermetic Runtime 依赖与语义等价 StagePlan

日期：2026-08-01
状态：`G2 failed / T03 terminal immutable / exit_contract:v2 selected / implementation pending / zero external call`

## 1. 为什么 0.1.3 必须重新从 S0 开始

FIN 0.1.2 的失败发生在正式模型、金融判断和三案例 Runtime 之前：唯一 S0C 双-disposable package 在 pytest collection 阶段停止。直接原因是 Runtime 代码读取的静态合同没有进入包内资源闭包，同时 traceback 中的宿主 Python/site-packages 绝对路径没有进入语义投影类型系统。

因此，0.1.3 不是再给字段打补丁，也不是从零重写产品。它从 S0 重验共同 Runtime 基础，并且只复用 hash-compatible 资产。FIN 0.1.2 的失败包、预算和 honest-block 结论保持不可改写。

## 2. S0 的唯一目标

S0 关闭四个继承的工程 blocker，以及 T03 暴露的一个同源合同 blocker：

- RC-P36-090：host inventory 与 disposable current gate 的职责分离；
- RC-P36-091：递归依赖始终受 tracked-or-typed 边界控制；
- RC-P36-092：所有 active-suite 可达的 non-Python Runtime 读取进入单一 `RuntimeResourceRegistry`；
- RC-P36-093：interpreter、purelib、platlib 和 distribution roots 进入 typed environment projection。
- RC-P36-094：nested `ref/*_ref` 的 reference role 由版本化 registry/schema 编译，不再靠字段例外和字符串形状推断。

S0 不负责 DeepSeek Flash stable / Pro preview 对比，不负责 DELL/MU R2、post-transfer NVDA、NVDA R3，也不修改 FIN 0.2 Earnings Review Alpha 的产品定义。

## 3. 固定任务和预算

| 任务 | 内容 | 当前状态 | 预算 |
| --- | --- | --- | --- |
| T01 | StagePlan、G0、owner 与停止线 | 已通过 | 本文件与机器合同 |
| T02 | resource registry + typed environment 的单一零调用实现包 | engineering pass，已完成 | 1/1 implementation bundle 已消费 |
| T03 | host import/collect、resource/path mutation、三案例 full-fake | 唯一 run 已在 closure compiler 期终态失败 | 1/1 零调用 engineering proof 已消费 |
| T04 | 独立双-disposable formal proof 与 S0 closeout | blocked，未创建/未执行 | 0/1 formal package；当前未授权 |

T02 失败时不进入 T03；T03 失败时不进入 T04；T04 失败时 S0 终态 honest block。不得自动创建 T05、R/H、replacement family 或 FIN 0.1.4。

## 4. RuntimeResourceRegistry 合同

注册表是权威源，静态扫描只能发现候选，不能替代声明。每个资源必须至少声明：稳定 resource ID、repo-relative path、SHA-256、bytes、classification、consumer IDs、load phase、required 和 source owner。

所有 active-suite 可达的生产 non-Python 文件读取都必须注册。未注册直接读取、missing、unknown、duplicate、digest drift、permutation、cross-version、ignored/untracked、`.codex_runtime`、traversal 与 symlink escape 必须在 object storage 或 pytest 之前确定性 fail closed。

## 5. Typed environment semantic parity 合同

每次证明前冻结 disposable package/repository/temp roots，以及 `sys.prefix`、`sys.base_prefix`、purelib、platlib、installed distribution roots。只有 traceback、environment 和 process diagnostic 字段中位于这些精确 root 下的路径可以替换成稳定 role token。

业务数值、nodeid、failure code、repo-relative resource path 和原始内容寻址证据必须保留。未知绝对路径继续 fail closed，不能用全局正则删路径来换取 parity。Windows drive case、slash、site-packages、prefix/base-prefix 和“看起来像路径的业务值”必须有 mutation 覆盖。

## 6. Active-set 与正式证明入口

正式 T04 预算只有在以下条件全部成立后才可消费：

1. application module import sweep 通过；
2. active suite collect-only 通过；
3. resource 与 environment mutation 全绿；
4. DELL/MU/NVDA 各达到 `6 nodes / 12 interactions / 12 captures / 9 diagnostic Artifacts`；
5. 最终九件产物通过 numeric、identity、temporal、lineage mutation；
6. Lead/Writer/Verifier 下游失败仍保留 capture 与 terminal result；
7. package 中 `.git`、`.codex_runtime`、ignored/untracked path 均为 0；
8. raw stdout/stderr/detail/terminal/per-test evidence 内容寻址保留，宿主仓库 readback 不变。

T04 只能创建一个 package，并在两个 fresh disposable roots、两个独立 process 中执行。两侧必须全部 collect/import/execute、current release gate 全绿、semantic digest 一致、unknown absolute path 为 0。

T03 实际在上述第 1 项之前停止：中央 registry 让 DELL source-grounded pack 进入闭包后，compiler 发现合法业务 `followup_ref` 含 `/`，但当前 `ref/*_ref` 路径启发式没有 typed semantic-followup role，故以 `hermetic_repository_reference_classification_missing` fail closed。事后只读 collect-all 进一步发现完整 reachable closure 需要区分 47 种 reference field：业务 follow-up、`.codex_runtime` restricted audit lineage、tracked model-run report 与真实 repository resource 不能再靠字段后缀和字符串形状区分。该诊断不可晋升为 T03 pass，也不授权增加字段例外后重跑。

## 7. 当前真值

- `G0=pass`，T01 完成；`G1=engineering pass`，T02 完成；`G2=failed`，T03 唯一 run 已消费；
- RuntimeResourceRegistry 已覆盖 29 项/323,829 bytes；7 个应用/三案例默认 loader 模块改用 resource ID，16 个 prompt 则保留 FIN 0.1.2 冻结的 `SKILL_FILES` compatibility adapter 并与新注册表双向校验；missing、unknown、duplicate、drift、permutation、cross-version 与 traversal mutation 均 fail closed；
- typed environment projection 已覆盖八类 roots，并证明 Windows drive case、slash、purelib/platlib、prefix/base-prefix、未知路径、相对路径与字段边界；raw evidence 不改写；
- focused registry/environment contracts=`24 passed`，相关生产 consumer 与三案例 host 回归通过；
- T03 在 host dependency closure、application import/collect/pytest 之前终态失败；modules/tests/Artifacts=`0/0/0`，T04 package 未创建；
- implementation/formal proof package=`1/0`；
- credential/model/provider/network/admission/business Run/Artifact=`0`；
- RC-P36-090–093 仍 open/full-chain blocker；新增 RC-P36-094 typed reference-role taxonomy blocker；
- FIN 0.1 release qualified=false，S1/S2 尚未进入。

机器合同：`configs/releases/fin_ia_0_1_3_s0_hermetic_runtime_dependency_and_semantic_parity_stage_plan_v1_0.json`
SHA-256：`034c7714e5773fe48b0d69ed6ab373ba02074e497d803bcd73349932f2177000`

## 8. Owner disposition：S0 Exit Contract v2

Owner 选择保留 FIN 0.1.3 为当前唯一主线，不自动创建 FIN 0.1.4，不豁免 hermetic gate，也不对旧 T03 重新计数。旧 v1 StagePlan 和 T03 closeout 保持不可变历史证据；新的 `fin_0_1_3.S0.exit_contract:v2` 是同一 S0 下的显式合同修订。

v2 的 reference-role registry 至少覆盖 `repository_resource`、`package_relative_audit`、`external_content`、`restricted_runtime_audit`、`model_run_report` 与 `semantic_followup`。同一 registry/schema 必须生成字段规则、closure policy、collect-all validator 和 mutation fixture；未知角色 fail closed。实现应一次报告全部未分类角色，禁止增加 47 个字段例外。

v2 固定预算为一个零调用实现包、一个 host engineering proof 和一个独立双-disposable formal proof；每项最多一次，无自动 retry、replacement、T05/R/H 或版本跃迁。实现包只证明合同已落地；host proof 全绿后才可签发 formal proof；formal proof 全绿并关闭 RC-P36-090–094 后，S0 才可进入 S1。任一全新 L1/结构失败触发项目级计划变更说明，不在同一任务内无限修补。

完整 S0–S5 产品归属见 `docs/product/FIN_0_1_3_CANONICAL_S0_TO_S5_PRODUCT_PROGRESSION_PLAN_20260801.zh-CN.md`。

当前唯一下一项（零调用实现；不重跑旧 T03）：

`FIN-0.1.3-S0-REFERENCE-ROLE-TAXONOMY-REGISTRY-AND-COLLECT-ALL-COMPILER-MINIMUM-ZERO-CALL-IMPLEMENTATION`
