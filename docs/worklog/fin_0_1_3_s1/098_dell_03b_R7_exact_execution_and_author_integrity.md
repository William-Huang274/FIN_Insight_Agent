# S1 工作记录 098：DELL 03B R7 唯一执行与作者完整性复证

日期：2026-08-27

状态：`exact execution success / author exact recompile and reprojection pass / fresh independent R7 engineering and R17 report-quality dual audit pending`

## 1. 冻结身份与执行前门

- implementation commit=`b2f8ce3ce393d593f0cb4964aeb11ba09aa3fb92`，tree=`f56c450e7a7fff379a9093efaa28adbdaf96cf7a`。
- authority commit=`b740270c2012cd936b87562ce47c3fb1886358b1`，唯一父提交为 implementation，唯一 changed path 为 v1.6 policy；执行前 `HEAD==upstream`、工作树 clean。
- policy 绑定 `29` 个 immutable inputs 与 `17` 个 implementation files；policy digest=`debc1cdde0e14e1b069374205af2a20860dde2e79ae7e49a317a4136165c54c0`，SHA=`2577d4a2a02295305ab3665a692b3b715d085da031985a3904468bd7f90132c4`。
- canonical private/public/receipt 与 attempt parent directory 均不存在；D 盘 free bytes=`1,336,659,968`，高于 `536,870,912` 下限。只读 preflight 完整验证 identity、parent、path、input、implementation、policy self-digest、disk 与 collision 后才进入 runner。

## 2. 唯一正式执行

- attempt=`dell-rsq-03b-internal-chain-r7`；recorded at=`2026-08-26T16:43:06+00:00`（本地 2026-08-27 00:43:06）；receipt 在 query batch 前 exclusive-create，同 attempt retry=false。
- request=`5`、compiled lane=`5`、local Qwen3-Embedding-0.6B query batch=`1`、request-level union=`338`、final=`80`、target-union occurrences=`794`。
- `network/provider/generation-model/external-capture/4B/reranker/retry/current-mutation/Candidate-promotion/Evidence-promotion/gap-closure` 全为 `0`。
- Runtime 的 `numeric_fact_count=11`、`typed_fact_resolved/gap/conflict=4/26/0` 是只读输入摘要，不是本次 NumericFact admission 或 promotion。

| target | complete source/compiled/union/final | best final rank | role-bound coverage gap | route observation |
|---|---:|---:|---:|---|
| ASP | 1/1/1/1 | 2 | 0 | bounded hardware quote present；company realized ASP/mix remains open |
| capacity release | 0/0/0/0 | — | 0 | external route required |
| capacity utilization/yield | 0/0/0/0 | — | 0 | external route required |
| HBM supply | 0/0/0/0 | — | 0 | external route required |
| supplier→Dell | 3/3/2/1 | 2 | 0 | relationship/sell-through present；supplier capacity allocation remains open |
| units | 0/0/0/0 | — | 0 | external route required |

正式结果与冻结 zero-call preview 完全一致。R6 的 CSpire/JSU 跨句、非 Dell 卖方 ASP 被撤回；Dell `$757,231` hardware quote 保留但不能升格为 company realized ASP。Supplier 多出 Dell earnings-call partner 单命题真阳性。External route required=`4`、local repair=`0`、target-specific 4B recall eligible=`0`、current same-pool reranker eligible=`0`。重排器没有删除：当前有效 ASP 已 rank 2，所以本池不制造运行资格；未来新增候选池或独立排序评测仍需单独 authority。

## 3. Artifact 完整性与 exact replay

- attempt receipt digest=`1f3bf45e9d3fc8df24f24140e15d98de07d9460c5cd72f48c8517c23554f7ab5`，SHA=`06614dc23b72745c72140d2cc65d701a0ae219819768175be0647a191ab30333`。
- private digest=`bda1eebc9a5766e4637ed0b86217bfe0b6c411bfabe7b601657a88a9ec81503d`，SHA=`b0f4392ef9dc2d44be380137c5ff1d52d6f64b27416117f3709dc7bb5bd8c897`。
- public digest=`94303de7e27194243e2fb7a442c0ba46dd73129736a8a7ad2f3dc3c637ce007f`，SHA=`2749abc80b6088724be98501a681e1f4cc040cdf9d3de2d1b35ee88937599357`。
- raw execution SHA 与 validated digest 均为 `0e9e4456ba75ecd07bc2e3bd6d5deddafc1972ba19700b029b2e6793e99f7458`。
- policy/receipt/private/public self-digest、canonical file bytes、private digest/SHA link、receipt-policy link、raw execution SHA 与 exact-once 均为 true。
- 作者仅使用保存的 raw execution、正式 recorded_at/Git identity/input bindings 对 1,888 source／34,199 objects 重编，用时 `34.222s`；`exact_private_recompile=true`、`exact_public_reprojection=true`。R7 targeted=`151 passed in 11.49s`。

## 4. 分层测试与尚未通过的门

R7 production/test freeze 已在 implementation commit 前通过一次全仓 `1726 passed, 2 skipped, 2 existing warnings`；result 阶段没有改 production、test、shared validator 或 active consumer。依照 `risk_tiered_test_evidence_policy.zh-CN.md`，本阶段以 R7 targeted、exact replay/reprojection、Project OS、active baseline、JSON/JSONL、secret/static/diff 为证据，不重复 22 分钟全仓。若 fresh audit 发现 material engineering finding，按 finding 所属面升级 targeted/mutation；影响面不明才升级全仓。

当前仍只是 author-integrity pass，不是 independent 03B pass。Fresh fork-none reviewer 必须攻击 one-proposition role binding、polarity/modality/status/report direction、positive recall、role-bound product/FY/currency/numeric anchors、field-typed public content、actual route 与 zero-authority seal；它不默认重跑全仓。

R17 研报质量是同一独立审计的第二部分：reader-visible citation/source appendix、14/9/4/10 gap crosswalk consumption、六项 WWC operationalization、事实密度与重复、02B qualified-human `0/16`、formal 8D validity 均继续 open。四个 external targets 尚未补源，Evidence admission、Pack/Readiness、S2、新报告和人工验收均未开始。Fresh audit 前不得启动 03C、4B、reranker、Evidence/NumericFact admission、S2 或报告 successor。

## 5. 提交边界

结果提交只包含 public result、model-run、worklog 与 Project OS；private 与 attempt receipt 留在 canonical ignored path。完成受影响 post-result gates、clean commit/push 后，才启动全新 fork-none、作者分离、只读 R7/R17 dual auditor。

## 6. Post-result risk-tiered gate

- R7 targeted=`151 passed in 11.49s`；Project OS=`82 passed in 28.91s`。
- exact private recompile/public reprojection=`34.222s`，全部 integrity links=true。
- active baseline=`213 Python / 8 frontend / 5 detectors / 28 resources / 0 failures`。
- config JSON=`1,151 parse pass`；Project OS JSONL=`8 files / 1,294 rows parse pass`；private/receipt JSON parse pass。
- changed-path secret scan、staged diff check 与 canonical public/private/receipt digest checks 在提交前执行；全仓不重复，原因与覆盖边界已在第 4 节记录。
