# FIN 0.1.2 pre-S2 hermetic fixture/resource rebaseline 最小零调用实现

日期：2026-07-31
任务：`PRE-S2-RB-T02`
结论：`pass_T02_minimum_zero_call_implementation_full_host_matrix_green_T03_replacement_proof_ready`

## 1. 本轮边界

本轮只消费父处置允许的一个 T02 implementation bundle，不重开 S1，不创建 S1-T05，不执行历史 T03/T04，也不提前消费新的 T03 replacement proof package。模型、Provider、业务网络、credential probe、admission、business Run、business Artifact 均为零。

T02 的目标不是宣布 hermetic proof 或产品通过，而是一次性关闭 S1 终态证据暴露的三个最早 repository owner：

1. ignored `.codex_runtime` 中的 MU realistic exact input；
2. Python-only package inventory 漏掉的 Runtime-read 非 Python 资源；
3. raw failure bytes 中 disposable root 导致的环境路径噪声与 semantic parity 混淆。

## 2. 受版本控制的 MU fixture

新增：

- materializer：`scripts/engineering/materialize_fin_0_1_2_pre_s2_mu_realistic_fixture_v1.py`，SHA-256=`c5a1eda089f70714cfd2cc1cb0a6ec8aea1a4739290365ca691cdd57a86cb4dc`；
- fixture：`tests/fixtures/fin_0_1_2/mu_realistic_three_cell_exact_input_v1.json`，`275275 bytes`，SHA-256=`84e2f2adf08423e6f7f7d2ab688656f2b1f47e83d5e62c24fb7fa25d82679909`；
- loader/fake support：`tests/contract/fin_0_1_2_realistic_fixture_support.py`，SHA-256=`c9886ecc688d6a37b5c367bd477f1388a8f296b9cbd440c1d13df40364d62d19`。

Fixture 绑定原始对象 SHA-256=`290e82aec53d6d3078eb0c8bac94e022bde7cc17a77b72d2315af118ced4958e`、input digest=`7887b5bb447fc6a844c410751f2038a04a1c0b04dbbe7e5bde41b040135a12e1`、`case_ec7da8015386e7bfeda92c61/v1`、ticker=`MU` 和三个 Cell。Loader duplicate-safe，并校验 digest、identity、版本与 non-promotion 边界。Active FIN0.1.2 三案路径改为读取该 fixture 与本地 support，不再从 `.codex_runtime` 读取，也不再把冻结的历史 S4 helper 当作当前 fixture owner。

Fixture 不包含 credential、Authorization/Cookie、Provider private reasoning 或可晋升 business output；它只能服务 deterministic proof。

## 3. 精确 Runtime 非 Python resource inventory

新增 generator：`scripts/engineering/generate_fin_0_1_2_runtime_nonpython_resource_inventory_v1.py`，SHA-256=`83a6cd7830af468a85bc45d52f4cb710182b5b66b1bf408affa041c6158d5b7a`。

生成 `configs/runtime/fin_ia_0_1_2_runtime_nonpython_resource_inventory_v1_0.json`：

- physical SHA-256=`986efbaf2ac5874e94c1756fd9219ea93b86bbcda7b4dc54569bc188a968c2c3`；
- source of truth=`src/sec_agent/research_skills.py::SKILL_FILES`；
- exact resources=`16`；
- total bytes=`53382`；
- canonical rows digest=`2b704b4c20dafad05097f59bb35740fc2f8a0479a2f55b6bb7d1a1bae15d1e9a`。

`src/sec_agent/hermetic_test_runner.py` 现在在启动 pytest 前校验 registry/source SHA、skill/path 唯一性、path/bytes/SHA、资源数与 canonical digest。自动 package 加入 inventory、registry 和 16 项资源；显式 inventory 也不得漏装。missing、duplicate、unknown、path/bytes/hash drift 和 explicit package omission 均 fail closed。目录 glob 不作为权威来源。

## 4. raw evidence 与 semantic parity 分离

新增 `configs/runtime/fin_ia_0_1_2_hermetic_semantic_parity_projection_v1_0.json`：physical SHA-256=`7b2fbbedf183ded583ffc96fee2df22f784ce9d582b3d3208e29f5b410143b47`，canonical digest=`922bcd08e9c42879f16262bd22cf94debecef6d1c5d550c4435c9f86cebdc7e7`。

Runner SHA-256=`53240479ebfe534098ac60c389dd2781e3459ac9f722ce5e9bb295e1e6855deb`。行为边界：

- raw terminal result、stdout/stderr refs、digest 和 content-addressed object 永不改写；
- 每个 disposable 另行持久化 `semantic_parity_projection.json`；
- 只允许 exact literal replacement：`exact_disposable_repository_root`、`exact_disposable_package_root`、`exact_hermetic_temporary_parent`；
- 业务值、nodeid、failure code、relative path 均保持比较显著；
- 非 allowlisted 绝对路径使 normalization 与 parity fail closed；
- final parity 同时要求两套 disposable 当前 gate green。

Mini full-run 已证明两套 disposable 的 raw path bytes/hash 不同、raw parity=false，但合法 exact-root projection 的 semantic parity=true；未知绝对路径会使 terminal status failed。

为避免把配置实现留到证明阶段，T02 同包新增 `configs/releases/fin_ia_0_1_2_pre_s2_t03_replacement_hermetic_proof_manifest_v1_0.json`，SHA-256=`5acee61ddf47abd479ca3257f8510cdef07da3ef7c5941ba3cef1a8ab956f4dc`。它显式绑定上述 resource inventory 与 semantic parity contract，选择 immutable disposition、current projection、three-case Runtime、historical S1 failure visibility 和 current dependency-closure gate，且没有隐式 external binding。该 manifest 只是 `ready_unexecuted`；本轮没有调用 runner 执行它。

## 5. 验证

实现记录：`configs/releases/fin_ia_0_1_2_pre_s2_hermetic_fixture_resource_rebaseline_minimum_zero_call_implementation_v1_0.json`，SHA-256=`629563185fcd075894fd0f998b330c8af047d7eb34e8d2b174537758e29fd8c4`。

已执行：

- fixture/resource/parity focused：`12 passed in 7.01s`；
- focused + existing runner：`14 passed in 8.72s`；
- 实现初验全体 `test_fin_0_1_2_*.py`：`95 passed in 14.24s`；补入独立 current-projection binding 后为 `96 passed`；补齐 T03 可执行 manifest 与最终 hash binding 后=`97 passed in 18.08s`；
- 新 T03 manifest-selected host preflight：`57 passed in 14.24s`；
- 既有 S0 manifest-selected current host suite：`24 passed in 1.16s`（实现记录还保留首次 `1.66s` 的真实运行回执）。

覆盖 DELL/MU/NVDA 每案 `6 nodes / 12 interactions / 12 captures / 9 Artifacts`，candidate counts=`0/1/3/6/7/22/76`，并覆盖 fixture mutation、跨案污染、数值/identity/lineage mutation、Lead/Writer/Verifier failure capture 和 resource/parity 负例。

历史 S4 文件中存在把 mutable current-next allowlist 冻结进 immutable implementation snapshot 的既有治理债务；它不属于 manifest-selected current suite，本轮没有为了变绿而改写历史语义或放宽断言。当前 projection 由独立 current-state tests 验证。

## 6. 产品真值与下一步

当前只可写：

- `PRE-S2-RB-T02=pass_full_host_matrix_green`；
- implementation bundles=`1/1`；
- replacement proof packages=`0/1`；
- `PRE-S2-RB-T03=ready_not_started`；
- S1 仍为 terminal honest block；
- S2 entry=false；
- DELL R2=false、MU R2=false、post-transfer NVDA=false、NVDA R3=false、FIN0.1 release qualified=false。

唯一当前下一项：

`FIN-0.1.2-PRE-S2-RB-T03-INDEPENDENT-TWO-DISPOSABLE-REPLACEMENT-HERMETIC-PROOF`

T03 必须是一个全新的 independent two-disposable package，消费 tracked MU fixture、exact non-Python resource inventory 与 raw-preserving semantic projection；不得伪装成历史 S1 T03/T04 rerun。它通过前不能进入 S2；若失败，pre-S2 honest block，不能自动生成第二个实现包或证明包。
