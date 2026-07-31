# FIN 0.1 S3-T09 Specialist-v7 r2 live validation

日期：2026-07-23

## 结论

r2 真实执行终止为可信的 `failed / failed / failed`，无 orphan、无 Artifact、无 retry/fallback/rerun。上一轮要修的两项问题均获得真实通过证据：

- 外层不再把 v7 错误压回 legacy 6000-byte 上限；三个 Specialist Cell、九个 Specialist segment 全部完成，Research Lead 也完成。
- 11 次 Provider 调用的 usage receipt 与 11 份 assistant final text 均在终止前持久化，且可受限回读。原始回答没有写进公开 runtime result，raw Provider response 与 private reasoning 均未保存。

因此这次失败不是上一轮 repair 无效。新的最早失败发生在 Memo Writer 的本地 canonical assembly validator。

## 真实执行事实

- admission digest：`006a280d8aa28dddbb285f36f1386fce5029c76743dd42b4b732d6271124b92a`
- WorkUnit：`wu_p02_5_a05e8d0eaa9ad8e6778fbb32`
- Attempt：`attempt_fin01_80490a8ad96e98a9a2685e04`
- Run：`research_run_fin01_8b42809cc1a8274a9b16fe37`
- calls：`11 / 11 / 11`
- tokens：input `42,583`、output `5,942`、total `48,525`
- latency：`77,283 ms`
- estimated cost：`USD 0.02275447`
- source network / external tool / live business head writes：`0 / 0 / 0`
- capture / restricted readback：`11 / 11`

## 新根因

Writer 的原始回答是合法的五条 `claim_renderings`，claim IDs 与上游精确一致。真正冲突来自 Specialist 的 WWC task IDs：

- Demand Cell：`wwc-001`、`wwc-002`、`wwc-003`
- Value/Profit Cell：`wwc-001`、`wwc-002`、`wwc-003`

当前 Specialist validator 只要求 task ID 在单个 Cell 内唯一，因此两个 Cell 都是合法输出；但 Writer validator 用一个全局 `task_id -> cell_id` map 绑定任务，后出现的 Cell 覆盖先出现的 Cell，最终把前一个 Cell 的 task refs 判断为错误。

这是项目自己的 identity-scope 合同不一致，不是 DeepSeek Writer 返回了错误 JSON。下一项应先做零调用合同决策：把 task/claim 的引用语义明确为 `(program_cell_id, local_id)` typed scoped identity，或在 canonical assembly 边界生成稳定 scoped ref；Prompt、Specialist validator、Lead、Writer、Verifier 必须共享同一合同。不得静默改写已经失败并持久化的历史答案。

## 边界

本轮不授权继续 patch、签发 replacement admission 或再跑模型。S3-T09 仍 blocked；没有完整九 Artifact 产品，不能做 paired comparison、owner acceptance、T10、S4、release 或 production。
