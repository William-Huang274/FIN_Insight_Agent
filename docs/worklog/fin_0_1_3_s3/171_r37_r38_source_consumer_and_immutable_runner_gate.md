# S3 工作记录 171：R37/R38 来源消费与历史 runner 不可变门

日期：2026-08-25

状态：`R38_zero_call_consumer_pass / historical_runner_compatibility_restored / natural_S3_open`

## 1. 历史 runner 与 current 语义必须分离

R34 修复了 current stop compiler：模型提出 `stop_sufficient` 但 coverage 未完成时，系统保留原
proposal，同时把 effective decision 编译为 `stop_no_progress`。复核发现该新断言曾直接写进
历史 `run_s3_current_dynamic_multi_agent.py`，但旧 authority manifests 按 SHA 绑定该 runner。

当前做法是恢复历史 runner 的既有 mutation contract，另建
`run_s3_current_dynamic_multi_agent_stop_successor.py` 检查 current 语义。successor 证明 proposal
不被改写、effective decision 安全降为 no-progress，并确认执行时没有永久替换历史 runner 的
`_mutation_checks`。这关闭历史可重放性缺陷，不授予新的 live authority。

## 2. R37/R38 zero-call consumer 事实

R37 R8 首次证明 reviewed `PUBLIC_PDF` 的 authority receipt 到达动态 workpaper；R38 R9 在网页
同步修复后重跑同一产品表面：

- 12/12 requests、7/7 proposition groups、两轮 current runtime；
- 15 reviewed Evidence、17 NumericFacts、9 gaps、18 FeedbackReceipt；
- 2 PlanDelta、2 graph hypotheses，终态 `stop_no_progress`；
- product bridge 到 workpaper，但 PVM／product profit 保持 null；
- CUDA FP16，0 Candidate promotion、network、model、Provider 或 paid call；
- public digest `f05731a7...`。

三案 R38 回执进一步证明 DELL 五个 cell 和 MU/NVDA 的 action/control projection 可复用，但没有
执行自然 Agent，也没有把未执行补源路线伪造成 public gap。

## 3. 工程门与内容边界

fresh 全库为 `1282 passed, 2 skipped, 2 warnings`；静态与仓库卫生门全部通过。R17 的 fresh
independent content pass 保持；本轮没有 material finding，所以没有 R18。

R38 canary 是 deterministic fixture 的 Harness/data-plane 证明，不是自然规划、反思、Writer 或
端到端产品验收。qualified human、S1／S2／S3、publication 和 release 均为 false。下一步仅为
clean push 后全新只读 subagent 对 immutable commit 做 P0–P3 审计；若发现 material finding，
在所属阶段开新 attempt，而不是改写 R37/R38。

## 4. 首轮整合审计的跨阶段处置

reviewer 对 `d63e7966...` 给出 FAIL，唯一 P2 属 S1 R35 promotion replay guard，不是 S3 canary、
R17 内容或自然 Agent finding；另一个 P3 是 context pack 顶部状态漂移。因此没有开 R18，也没有
改 R17。P2 已迁回 S1 所属层修复并保存独立 failure receipt；新的 full gate 与 fresh reviewer
通过前，S3／产品／publication／release 继续为 false。

## 5. fresh successor 审计结果

R35 guard successor 的作者 full gate 为 `1284 passed, 2 skipped, 2 warnings`；第二名 fresh
read-only reviewer 对 `e9d1bf1e...` 判定 `PASS，0/0/0/1`。唯一 P3 只是被审 commit 尚未记账，
当前文档 successor 已修正。没有 S3 或 R17 material finding，不开 R18；qualified human、S3、
产品、publication 和 release 仍为 false。
