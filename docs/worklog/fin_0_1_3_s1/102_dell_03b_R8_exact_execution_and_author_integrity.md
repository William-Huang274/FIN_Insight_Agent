# S1 工作记录 102：DELL 03B R8 唯一执行与作者完整性复证

日期：2026-08-27

状态：`exact execution success / raw capture preserved / author exact recompile and reprojection pass / fresh independent R8 engineering and R17 report-quality dual audit pending`

## 1. 冻结身份与执行前门

- implementation commit=`a9403e327e2de740015d63223ee6fbeace0f93a6`，tree=`3aa2cf8ee5102b81bdfb9151d35c14c68f8bb267`。
- authority commit=`f4c3c629c789fa8d61deda2f4375eb887f5f8ce4`，tree=`d55e3ac61a412e6aab184b5d6ca7b3e4442e9829`；唯一父提交精确为 implementation，唯一 changed path 为 v1.7 policy。
- 首次三次 push 因 github.com:443 connection reset/unreachable 失败；期间 authority 保持本地 ahead 1、canonical output/attempt 不存在，runner 未启动。间隔后同一 commit push 成功；执行前 `HEAD==upstream`、worktree clean。
- policy 绑定 `34` 个 immutable inputs 与 `21` 个 implementation files；policy digest=`ee6616d7c0db30608f91cea80c6412bb69dae19a0e9babc80576b9a2aa96ae63`，SHA=`7c3cbeb550531b6a8fe89e362d7f4c9687aeb6d4b057776778ac880b59e929f4`。
- canonical public 与 R8 attempt directory 均不存在；D 盘 free bytes=`1,303,891,968`，高于 `536,870,912` 下限。真实 policy validator 逐项复核 R7 failure chain、34 inputs、21 hashes、TokenBudgetBasis、identity、output contract 与 collision 后才进入 runner。

## 2. 唯一正式执行

- attempt=`dell-rsq-03b-internal-chain-r8`；recorded at=`2026-08-26T22:03:23+00:00`（本地 2026-08-27 06:03:23）。Receipt 在 runtime/model 初始化前 exclusive-create；同 attempt retry=false。
- request=`5`、compiled lane=`5`、local Qwen3-Embedding-0.6B query batch=`1`、request-level union=`338`、final=`80`、target-union occurrences=`794`。
- `network/provider/generation-model/external-capture/4B/reranker/retry/current-mutation/Candidate-promotion/Evidence-promotion/gap-closure` 全为 `0`。
- Runtime 的 `numeric_fact_count=11`、`typed_fact_resolved/gap/conflict=4/26/0` 是只读输入摘要，不是本次 NumericFact admission/promotion。
- 模型返回后，runner 在任何 private compilation/public projection 前独占保存 `raw_execution_capture.json`。本次后续全部成功，因此没有 `terminal_failure_receipt.json`。

| target | complete source/compiled/union/final | best final rank | frame-role coverage gap | route observation |
|---|---:|---:|---:|---|
| ASP | 1/1/1/1 | 2 | 0 | bounded hardware quote；company realized ASP/mix remains open |
| capacity release | 0/0/0/0 | — | 0 | external route required |
| capacity utilization/yield | 0/0/0/0 | — | 0 | external route required |
| HBM supply | 0/0/0/0 | — | 0 | external route required |
| supplier→Dell | 3/3/2/1 | 2 | 0 | relationship/sell-through present；capacity allocation remains open |
| units | 0/0/0/0 | — | 0 | external route required |

Formal 与冻结 preview 完全一致：local repair=`0`、external route required=`4`、target-specific 4B eligible=`0`、same-pool reranker eligible=`0`。R8 formal raw execution SHA 与 R7 相同，说明同一冻结请求/候选 ranking trace 未漂移；R8 的变化只在确定性 predicate-frame、anchor 和 public projection qualification 层。

## 3. Artifact 完整性与 exact replay

- attempt receipt digest/SHA=`695f50f516efb621fd27883d099d188026a04bf55430722caa4c830943bd21fa` / `cace31eca24984dcb927131876b3d449b406a7f5280cae2a6ce9f93e89248217`。
- raw capture digest/SHA=`6da7eed0dedfe854023b27088532293af1dea253733aab343c78c7352c75ba4c` / `d71cd93eedf7226b2e80d82ba53c6d43f7db2c79e19bee8df703e12910cfbd83`。
- raw execution SHA/validated execution digest=`0e9e4456ba75ecd07bc2e3bd6d5deddafc1972ba19700b029b2e6793e99f7458`。
- private digest/SHA=`290c8390f3b043409b79833b00ef9a3388c56368c19a1eb901bded7598b037b2` / `17041e294d89ed281f9c54bd666cd0a071a13056bffa6a91306fca136cface4f`。
- public digest/SHA=`1b6c04aadd61ec1253ab27062b3dd8a7b3251e6b7f3fb20ef3918e390aa5e83d` / `8a11168e9366462928d4741abb1e87cfabc2597d4e1a6603c66b3710835dd022`。
- policy/receipt/raw-capture/private/public 五份 self-digest、canonical file bytes、receipt/capture/private/public policy link、public→private digest/SHA link、raw SHA 与 exact-once 全为 true。
- 作者只读使用保存的 raw capture、正式 recorded_at/Git/input bindings 对 1,888 source／34,199 objects 重编，用时 `42.489s`；private dict 与 canonical bytes逐字节相等，public reprojection dict 与 canonical bytes逐字节相等。

## 4. 风险分层与未完成门

R8 production/test freeze 已在 implementation commit 前通过一次 T4：`1823 passed, 2 skipped, 2 existing SWIG warnings in 508.75s`。Policy-only、formal result、worklog、Project OS 与 audit manifest 不改 production/test/shared validator/active consumer，因此不重复全仓。Post-result 只跑 R8 targeted、Project OS、active baseline、JSON/JSONL、secret/static/diff 与上述 exact replay/reprojection。

当前仍只是 author-integrity pass，不是 independent 03B pass。Fresh fork-none reviewer 必须审：Git/input/output/exact-once/raw-failure seal、frame split/role span/scope、anchor locality/ambiguity/positive recall、public threat-first validator、actual route/counts，以及 R17 reader citations/source appendix、14/9/4/10 crosswalk、六 WWC、事实密度/重复、source passages/locators、02B `0/16` 与 formal 8D。

四个 external targets 尚未补源；Evidence admission、Pack/Readiness、S2、受影响动态单元、新报告和人工验收均未开始。Fresh audit 前不得启动 03C、4B、reranker、Evidence/NumericFact admission、S2 或报告 successor。

## 5. 提交与审计边界

结果提交只包含 public result、model-run、worklog 与 Project OS；private、receipt、raw capture 留在 canonical ignored path。结果 commit/push 后再建立 self-digest/hash-bound fixed audit manifest，明确绑定 T1/T2/T3/T4、static/secret、current-corpus crosswalk、raw capture/replay 和 R17 fixed report-quality bundle。Reviewer 只读固定包，缺材料直接 `NOT_ASSESSABLE`，不递归历史阅读、不重复 full pytest。

## 6. Post-result risk-tiered gate

- R8 targeted=`97 passed in 20.02s`；Project OS=`82 passed in 34.56s`。
- exact private recompile/public reprojection=`42.489s`；五份 self-digest 与全部 integrity links=true。
- active baseline=`213 Python / 8 frontend / 5 detectors / 28 resources / 0 failures`。
- config JSON=`1,154 parse pass`；Project OS JSONL=`8 files / 1,307 rows parse pass`；R8 private receipt/capture/result=`3 JSON parse pass`。
- 最终 changed-path secret scan 与 staged diff check 在提交前执行；全仓不重复，因为 production/test/shared validator/active consumer 未变，implementation-freeze T4 receipt 仍有效。
