# P38 Point 01 M2-A1 Phase B0.6：trigger 合同与 v2.9 executable authority package

## 结论

状态仅为 `B0.6_repaired_refrozen_pending_independent_review`。本轮未创建 active human approval、admission、receipt、ledger namespace、runtime 或 baseline；没有进入 Step 2、其余场景、M3–M7、network/model/tool/provider、fixed/business store mutation 或 full-chain。

## 已修复

- event table 的 UPDATE/DELETE deny trigger 使用 SQLite `sqlite_master` stored DDL 的规范化精确比对；只处理 outer terminal semicolon 的 SQLite 存储差异。`WHEN 0`、错误 abort message、错误 action 与缺 trigger 都在 ledger 打开时 fail-closed。
- v2.9 将 default-deny JIT、registrar、stdlib parent 与 clean child 都纳入 package input hashes。future external `HumanJITWindowApproval` 通过全部 exact bindings 后，才可按照 approval → admission/receipt → register → consume → grant → materialize → child → actual → oracle → reviewer → terminal 的冻结顺序执行。
- v2.8 synthetic nonhuman proof 独立保留为历史测试能力，不能伪造或激活 human approval 路径。

## 冻结证据

- package / gate: `5a107d4b1b7f66a3028609f3d419106e6ba2c5664db9781f3b1e2243a391251b` / `0d9500bc69f5d80030933dc086b5cefc388613baabb625e4e9ccc6b2d07ea7b0`
- plan / gate: `98c618ee8c0fe6a3fe9ac2a7eeb760327911521f1bd0593e9ceecf9dffbdb5e7` / `5c73aab9b1287948251a9f3167cccc399eb16ff61584c6c62904947c34d77143`
- blueprint / gate: `d3a2b4e96aff1eb90384c72bd51a1ef441e27cbe316ccbb4bd405e15939e9655` / `1627507c6d9d42187899b681e7979be3f6a61c2f68b15a0f319f8f3076f074c9`

## 验证

- `python -m compileall -q`：通过（v2.9 runtime / scripts）。
- `python -m pytest -q tests/contract/test_point01_m2_a1_v2_7_approval_lineage.py tests/contract/test_point01_m2_a1_v2_8_operational_proof.py tests/contract/test_point01_m2_a1_v2_9_executable_authority.py`：`22 passed`。
- 生产 preflight 的 v2.9 exact test-only external-authority fixture 只到 read-only preflight boundary；没有 materialize runtime/output。缺/不可读 approval 和 v2.4 authority 都 fail-closed。
- fixed approval DB 未打开或写入；其既有 SHA-256 为 `ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4`。

## 剩余边界

SQLite enforcement 只面向 application-controlled database，而非可任意篡改数据库文件的恶意管理员。必须等待 total reviewer 独立审计 v2.9 package、exact DDL validator、entry hashes 和 no-side-effect proof；在此之前不得生成 active approval、baseline 或进入 Step 2。
