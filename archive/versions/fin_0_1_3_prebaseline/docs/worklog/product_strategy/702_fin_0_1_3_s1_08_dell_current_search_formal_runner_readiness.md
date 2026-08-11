# 702 — FIN 0.1.3 S1-08 DELL current-search 正式 runner 就绪

日期：2026-08-07
阶段：`013-S1-08`
状态：`formal runner engineering pass / clean commit preflight pending`

## 1. 发现与判断

Codex 重启后，当前进程已经能读取格式有效的 `FINSIGHT_SEC_CONTACT_EMAIL`，且没有回显或写入明文。恢复审计同时发现，worklog 701 所称的“exact-once runner”实际只有可调用的 Runtime 模块和测试，没有正式 CLI、clean/synced 检查和版本化结果物化。直接用临时 `python -c` 执行会削弱可复现性，因此该缺口留在 S1-08 原阶段修复，不新建版本，也不改 candidate-generation 合同。

## 2. 实现

- 新增 `scripts/releases/run_fin_ia_0_1_3_s1_08_dell_current_search_canary.py`：
  - live 前要求 Git clean/synced、输出不存在、runtime SEC contact 有效；
  - fresh admission 绑定 catalog、implementation commit、两小时有效期、24 次网络硬上限、每 query 最多 2 个文档、retry/model=`0/0`；
  - shared ledger 位于本次 runtime 外，fresh admission exact-once 消费；
  - 只执行 DELL，MU/NVDA、ranking/reranker、DeepSeek/S3 均不准入；
  - 受控识别 Codex `198.18.0.0/15` synthetic DNS，但继续拒绝非 synthetic 的 private/reserved 地址；
  - 没有把未绑定的 market snapshot 冒充 current 数据，市场角色允许形成 typed gap。
- `src/sec_agent/s1_08_live_canary.py` 现在用真实完成时刻 terminalize，并在异常后仍保留已发生的 network call count，避免失败 telemetry 误记为 0。

## 3. 零调用验证

- compileall：pass；
- focused：`19 passed`；
- related：`52 passed / 1 historical failure`；
- `git diff --check`：pass。

唯一扩大失败是 S0-02 历史 decision 对 `apps/workbench/backend/application/fin_0_1_2_s4_t03_executable_agentic_search.py` 的 mutable source SHA 绑定已经漂移（recorded `7d723a...`，current `782ce0...`）。这是已知 historical-proof/live-source-role 缺陷形状，不由本轮文件引入；不得重写旧 decision 换绿。正式 live 前仍需在 clean/synced commit 上运行 scoped Project OS preflight。

## 4. 下一步和边界

提交并推送本 runner slice；随后运行 `one_DELL_current_search_canary` scoped preflight。若通过，用户已有连续授权，可签发并 exact-once 执行一次 DELL canary。真实 target-in-pool 不足时留在 S1-08 修 candidate/source coverage；不得先调 BGE/Milvus 或进入 S3。

联系方式明文未进入 Git、普通 telemetry、admission、结果或本日志；它只允许存在于进程环境及受限 raw request capture。
