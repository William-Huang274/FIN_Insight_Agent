# FIN 0.1.3 S0 Hermetic Runtime 依赖与语义等价 StagePlan

日期：2026-08-01
状态：`FIN 0.1.3 terminal honest block / version disposition complete / RC-P36-090–096 transferred to FIN 0.1.4 S0 StagePlan / zero external call`

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
- RC-P36-095：proof manifest、policy validator 与 shared repository compiler 必须使用同一 policy source，并在 host budget 消费前穿过 exact execution boundary。

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

v2 的 reference-role registry 已精确覆盖 `repository_resource`、`package_relative_audit`、`external_content`、`restricted_runtime_audit`、`model_run_report` 与 `semantic_followup`。同一 registry/schema 生成字段优先规则、有序值命名空间、closure policy、collect-all validator、mutation fixture 与 typed failure；未知角色 fail closed。`followup_ref` 的语义 owner 优先于字符串中的 `/`，v2 不接受 `non_repository_reference_fields`。

当前零调用实现已工程通过：正式 current-manifest 完整闭包得到 1,233 个全 tracked path、4,996 条 reference observation、0 unknown；repository/package/external/restricted/model-run/semantic 六类计数为 `1,640 / 6 / 54 / 219 / 16 / 3,061`。两未知项 mutation 会在同一个受限 typed failure envelope 中保留 document、JSON pointer、field、value、role/rule 空值与 observation digest，并明确 `business_promotable=false`；duplicate JSON key、cross-version、rule-order、untracked/traversal/symlink、未知 repository-like root filename 和历史 v1 兼容路径继续 fail closed。focused/current/legacy matrix=`83 passed`。该结果只消费 v2 implementation=`1/1`，没有消费 host/formal proof。

v2 固定预算为一个零调用实现包、一个 host engineering proof 和一个独立双-disposable formal proof；observed=`1/1/0`，失败与预算保持不可变，formal 预算不能转用为重跑。

完整 S0–S5 产品归属见 `docs/product/FIN_0_1_3_CANONICAL_S0_TO_S5_PRODUCT_PROGRESSION_PLAN_20260801.zh-CN.md`。

host proof 权限决策已消费：proof-specific active manifest 的 `unknown_reference_behavior=fail_closed_collect_all` 与共享 compiler 精确要求的 `fail_closed` 不一致，唯一 v2 host run 在 import、collect、pytest 与三案 full-fake 前触发 `hermetic_repository_reference_policy_boundary_invalid` 并终态停止。Project OS preflight、4316 文件启动 readback、内容寻址失败证据与失败后 clean/synced 仓库均已核验；这证明的是 packaging-to-compiler 合同漂移，不是 Runtime、reference-role 行为或金融 L1 失败。按固定预算没有 patch、retry、replacement 或第二次 host proof，formal proof 也未授权；v2 observed 已变为 `1 implementation / 1 host / 0 formal`，RC-P36-090–094 继续 open，并新增 RC-P36-095。

## 9. Owner disposition：S0 Exit Contract v3

项目级 decision 保留 FIN 0.1.3 为唯一主线，并把 v3 定义为同版本内最后一次 Exit Contract 修订；它不是 v2 retry，也不是 FIN 0.1.4。v2 六角色、29 项 Runtime resource、八类 environment root 与三案确定性合同原样继承，不重新实现或重新计数。

v3 只允许一个 proof-control-plane 实现包，建立版本化 repository-reference proof policy 单一来源；manifest compiler、validator 和 shared repository compiler 必须从该源取得精确值。`unknown_reference_behavior=fail_closed` 表示终止语义，`unknown_reference_reporting=collect_all_typed_envelope` 表示报告语义，两者不能再压进同一个 enum literal。

实现还必须加入 non-consuming exact-boundary eligibility：在 clean/synced committed HEAD 上绑定 execution/active manifest 与全部 source digest，执行 Project OS preflight、tracked snapshot、`compile_repository_inventory`、inventory policy/role/unknown/forbidden/allowlist/digest 校验和 content-addressed readback。host execution 必须立即重算并匹配 eligibility digest，之后才写入 consumed marker 并进入 import sweep。eligibility failure 在 host budget 消费前终止；匹配后的任何 host failure 都消费唯一 host run。

v3 maximum/observed `[implementation, eligibility, host, formal]=[1,1,1,1]/[1,0,0,0]`。唯一 implementation bundle 已工程通过：`fin_ia_0_1_3_repository_reference_proof_policy_v3_0.json` 成为唯一 policy source；被 v2 implementation 哈希绑定的 `hermetic_test_runner.py` 保持 byte-identical，新 `proof_control_plane.py` 先校验 v3 source，再确定性投影为 immutable v2 compiler surface，并把 policy source 本身纳入 closure。reference-role v1.0 也保持不变；新 v1.1 只增加完整 current compile 暴露的 `execution_started.json -> package_relative_audit` 兼容规则，六角色与闭包语义不变。`proof_control_plane.py` 同时建立 eligibility/attestation/host-authority typed contract，v3 runner 在 base execution 前重算 exact boundary。current active manifest v1.3 只保存 policy binding，并将 mutable current 验证归属新 v3 test。schema/digest/value/consumer-order/registry 与 attestation/authority drift mutation 全部 fail closed。

上述结果没有执行 clean/synced HEAD eligibility，也没有创建或消费 host/formal proof authority。implementation 不授权 eligibility 或 proof；eligibility 通过后仍需单独 host authority，host 通过后仍需单独 formal authority。eligibility、host 或 formal 任一出现新结构失败，FIN 0.1.3 冻结 internal honest block，不得在同版本创建 Exit Contract v4。S0 只有在 RC-P36-090–095 均可关闭后才进入 S1。

授权前 exact transition audit 已触发这条终态规则：冻结的 v3 runner 与 active manifest 仅允许 current projection 保持 `...implementation_pass_eligibility_authority_pending`，而一次诚实的 authority decision 必须把 current truth 推进为 `...eligibility_authorized_not_executed`；后一状态会在 eligibility 之前触发 `current_v3_projection_status_invalid`。保留旧状态会造成 Project OS 与权限事实不一致，修改 runner 属于第二个 v3 implementation patch，先运行后更新则超出权限并破坏证据顺序。因此 eligibility authority 未签发、execution manifest 未创建、eligibility/host/formal 均未执行，observed 保持 `[1,0,0,0]`。新增 RC-P36-096，RC-P36-090–095 继续 open；这不是 DS、Provider、金融 Runtime 或研究质量失败。

FIN 0.1.3 现为 `terminal honest block / version-scope disposition required`。eligibility 剩余预算不转移、不自动解释为新权限；不得建立同版本 v4，也不自动创建 FIN 0.1.4。FIN 0.2 的 Earnings Review Alpha 定义保持不变。

## 10. 终态版本处置：转交 FIN 0.1.4 S0

Owner 处置正式冻结 FIN 0.1.3，不重开 v3、不建立同版本 v4、不把未完成的共同 Runtime 债务转给 FIN 0.2。RC-P36-090–096 原样转交 `FIN-0.1.4-S0-PROOF-LIFECYCLE-STATE-MACHINE-AND-HERMETIC-QUALIFICATION`；0.1.3 的 v1/v2/v3 failures、budget 与 hash-bound implementation snapshots 均保持不可变。

FIN 0.1.4 不是再次逐字段修 proof runner。它首先把 proof lifecycle 变成单一版本化状态机，明确编译 pre-authority、authorized-not-executed、evidence-pass/fail、host/formal authority 与 terminal 状态；immutable event snapshot 不再验证 mutable backlog/current-next，current projection 也不再由历史 test suite 拥有。只有完整状态迁移 mutation、三案 deterministic closure 与 clean-head current projection 全部通过，未来 host/formal proof budget 才能消费。

本次 disposition 只创建版本和 S0 StagePlan 入口，未创建 StagePlan 本体、implementation、eligibility、host/formal proof、模型或业务 Artifact。FIN 0.1.4 无自动 T05/R/H/replacement 或 FIN 0.1.5；任何新结构失败仍进入项目级处置，不在同阶段循环修补。

当前唯一下一项（仅做 FIN 0.1.4 S0 StagePlan；不得自动实现、执行 proof 或修改金融 Runtime）：

`FIN-0.1.4-S0-PROOF-LIFECYCLE-STATE-MACHINE-AND-HERMETIC-QUALIFICATION-STAGE-PLAN`
