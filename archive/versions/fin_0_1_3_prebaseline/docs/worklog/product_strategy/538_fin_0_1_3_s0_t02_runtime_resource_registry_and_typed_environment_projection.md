# FIN 0.1.3 S0-T02 Runtime resource registry 与 typed environment projection

日期：2026-08-01
状态：`engineering pass / T02 complete / T03 ready / zero call`

## 本轮权限与边界

用户以“继续”授权执行 T01 已冻结的唯一 T02 零调用实现包。本轮只实现 Runtime resource authority、typed execution-environment projection、active-suite 合同及其本地 mutation；没有创建或执行 T03 engineering proof，也没有创建或执行 T04 双-disposable formal package。credential、model、Provider、network/source、admission、business Run、business Artifact、S1/S2 与 FIN 0.2 scope change 均为 0 或未授权。

## RuntimeResourceRegistry

新增：

- `src/sec_agent/runtime_resource_registry.py`
- `configs/runtime/fin_ia_0_1_3_runtime_resource_registry_v1_0.json`

注册表以 29 个稳定 resource ID 管理 323,829 bytes 生产 non-Python 资源。每行绑定 repo-relative path、SHA-256、bytes、classification、consumer IDs、load phase、required 与 source owner；registry 是 authority，AST static scan 只用于发现遗漏。

7 个应用/三案例默认 loader 模块改为按 resource ID 读取：Case/feature flags、Evidence、Integrity、Deliverable、Fact candidate profiles、FIN 0.1.2 compiled-contract source/binding、S4 DELL/MU Case Pack/method/source-grounded packs。16 个 prompt 没有直接修改旧 `research_skills.py`：FIN 0.1.2 inventory 已冻结该文件的物理哈希，因此新 registry 把旧 `SKILL_FILES` 作为 compatibility adapter 双向校验并纳入 package closure。这样既关闭当前依赖遗漏，又不改写历史证据。

确定性负例覆盖 missing、unknown ID、duplicate ID/path、bytes/SHA drift、row permutation、cross-version schema、duplicate JSON key、traversal、resolved symlink escape、unregistered literal 与 frozen `SKILL_FILES` adapter drift。

## Typed environment semantic parity

新增 `configs/runtime/fin_ia_0_1_3_typed_environment_semantic_parity_v1_0.json`，runner 在 disposable 执行前冻结八类 root：

1. disposable package root；
2. disposable repository root；
3. disposable temporary root；
4. `sys.prefix`；
5. `sys.base_prefix`；
6. purelib；
7. platlib；
8. installed distribution roots。

每个 runtime row 都带 root ID、role、absolute path、projection token、source 与 fingerprint。只有 stdout/stderr/detail、collection errors、process stdout/stderr 等 diagnostic fields 会做 exact-or-descendant 替换；Windows drive letter case 与 slash direction 被规范化，root 的后代相对段统一为 `/`。业务字段、nodeid、failure code、repo-relative path 和 raw content-addressed evidence 保持原样；未知绝对路径继续 fail closed。

实现中发现并修复一个本地语义投影细节：root token 后面的 `/tests/...` 一度被 POSIX unknown-path regex 误识别成新绝对路径。新合同明确排除 token 结束符 `>`，同时不放宽真实未知 POSIX/Windows 路径门禁。

## Active suite 与历史不可变性

新增 active manifest 与 current projection：

- `configs/releases/fin_ia_0_1_3_s0_active_test_suite_manifest_v1_0.json`
- `configs/runtime/fin_ia_0_1_3_current_program_projection_v1_2.json`

五类 proof owner 各一个：immutable event、current projection、current runtime、historical audit、release gate。T01 测试从“未来文件永远不存在”更正为只证明 T01 当时 implementation count 为 0，避免 immutable event 越权拥有当前文件系统状态；T01 JSON 与 SHA-256 `034c7714...7000` 未修改。FIN 0.1.2 inventory、failed packages 与 `research_skills.py` SHA-256 `d757747d...fdba` 也未修改。

## 验证结果

- registry + typed environment focused contracts：`24 passed`；
- old inventory、runner、S0C historical contract、production consumer、research skill 与 DELL/MU/NVDA three-case 相关矩阵：`100 passed`；
- T01/current projection 前置矩阵：`17 passed`；
- T02 record/active/current/event matrix：`19 passed`；
- 下一 T03 exact scope 的 Project OS preflight：`pass / open blocker count=0`；
- Python compile：pass；
- Git diff check：pass；
- model/Provider/network：`0/0/0`。

这些结果只构成 T02 engineering pass。application import sweep、active-suite collect-only、三案例 T03 proof、最终九件 mutation 与两套 independent disposable semantic parity 尚未执行，因此 RC-P36-090–093 继续 open/full-chain blocker，不能宣称 S0、S1、S2 或 FIN 0.1 release 通过。

## 下一项

唯一下一项：

`FIN-0.1.3-S0-HOST-IMPORT-COLLECT-RESOURCE-MUTATION-AND-THREE-CASE-FULL-FAKE-ZERO-CALL-PROOF`

该项最多执行一次 T03 零调用 engineering proof；通过后才允许另行进入 T04 的唯一双-disposable formal package。
