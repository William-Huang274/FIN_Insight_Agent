# 718 — FIN 0.1.3 S1-08 v3 DELL R3 successor preflight commit-lineage 修复

日期：2026-08-08
阶段：`013-S1-08-P2C`
状态：`zero-call repair pass / clean preflight pending`

## 1. 发现的问题

P2C 在真正生成 clean proof 前审计出一个提交自引用：R3 runner 把未来执行时的当前 `HEAD` 作为 `implementation_commit`，而 admission 又要求 clean preflight 的 `source_commit` 与它完全相等。clean proof artifact 必须在证明完成后才写入并提交，因此提交 proof 会天然推进 `HEAD`，使刚生成的 proof 在签发前立刻失效。

这是 R3 runner/preflight lineage 的项目内问题，不是 DeepSeek、Provider、网络或来源问题。不能靠手工把 proof JSON 中的 commit 改成新 HEAD，因为那会声称未被 archive/fresh process 证明的提交已经通过。

## 2. 有界修复

修复后区分两个身份：

- `proven_source_commit`：clean archive 实际证明的源码提交，继续作为 admission/terminal 的 `implementation_commit`；
- `execution_commit`：后续提交 proof artifact、Project OS 投影和文档后的 clean/synced HEAD。

runner 要求后者必须是前者的 Git 后代，同时 `src/`、`scripts/`、`configs/runtime/`、`pyproject.toml` 与 `requirements*.txt` 在两提交间零漂移。Runtime/Runner SHA、v3 implementation source map、authority/R2/catalog digest 仍逐项校验。因此 proof/账本文档可以在不制造自引用的情况下提交，但任何执行代码、依赖或运行时配置变化都会 fail closed，必须重新做 clean proof。

新增专用 preflight runner，复用既有 v3 proof 的 Git archive、受限 R1/R2 capture 注入与 credential-scrubbed fresh-process 机制，不再复制一套 capture materializer。它将在本修复提交并推送后执行完整 S1-08 `70` tests、compile、mutation、exact-once、R3-result absent 和零外部调用检查。

## 3. 当前验证与边界

- focused R3 contract：`7 passed`；
- same-lineage positive、Runtime-tree drift、non-ancestor mutation：均按预期通过或 fail closed；
- compileall：pass；
- formal admission/network/model/provider/retry/live=`0/0/0/0/0/0`。

机器证据：

`configs/releases/fin_ia_0_1_3_s1_08_v3_dell_r3_successor_preflight_commit_lineage_repair_v1_0.json`

当前仍不是 clean proof，也没有解锁 exact-live。下一步必须先把本修复提交并推送，再执行：

`S1_08_V3_DELL_R3_SUCCESSOR_CLEAN_ZERO_CALL_PREFLIGHT`

## 4. P2C-A1 proof-runner 失败与处置

clean `04e439bf...8f57` 上的第一份 proof 在结果物化前失败；同一错误诊断重放后确认：runner 使用 `pytest tests/contract -k s1_08`，而 pytest 会先导入整个 contract 目录再筛选，clean archive 因缺少与 S1-08 无关的历史生成资源出现 `144` 个 collection error。两次 observed formal admission/network/model/provider/retry/live 均为 `0`。

该失败归 proof-runner test selection，不归 R3 Runtime 或产品检索。修复没有把无关历史资源复制进 archive，也没有 skip/fallback；改为显式列出 `10` 个 S1-08 contract 文件，预期仍为完整 `70 passed / 0 failed / 0 skipped`。A1 保留在 v1.1 repair artifact 和未来 proof attempt history；下一步改为提交并推送 v1.1 后执行 A2。
