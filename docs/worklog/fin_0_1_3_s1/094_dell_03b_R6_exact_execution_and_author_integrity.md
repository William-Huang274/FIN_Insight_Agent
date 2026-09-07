# S1 工作记录 094：DELL 03B R6 唯一执行与作者完整性复证

日期：2026-08-26

状态：`exact execution success / author exact recompile and reprojection pass / fresh independent dual audit pending`

## 1. 执行身份与零写入启动事件

- implementation commit=`512aa32b0f312499b430c483ebfd3fbd9c520d38`，tree=`7715943022f376c82ede11b3e4bedad99c5ccb34`。
- authority commit=`b6410eb274601abc0913c90f6b4adcf08c91cd48`，其唯一父提交为 implementation，唯一 changed path 为 v1.5 policy；执行前 `HEAD==upstream`、工作树 clean。
- policy 绑定 `24` 个 immutable inputs 与 `14` 个 implementation files；policy digest=`6b0049f4a63b99983b2d0444a1dd123c325ad703d354bc70508a46b19ce50294`，SHA=`9ba4fb9be570ede9bc3c0f00ae1008afe6b3c2085195969311a6657d1f3dff65`。
- 第一次命令使用了非 canonical 的 `python -c` package import wrapper，在导入 `scripts.data_retrieval` 时立即 `ModuleNotFoundError`。当时 private/public/receipt 与 attempt parent directory 全部不存在、Git 仍 clean，故没有进入 runner、没有加载 policy、没有调用模型、没有消费 R6 attempt。随后仅改用仓库 canonical script 入口；该启动事件不伪装为模型执行成功或失败。
- canonical runner 前 private/public/receipt 均不存在；D 盘 free bytes=`1,370,591,232`，高于 `536,870,912` 下限。

## 2. 唯一正式执行

- attempt=`dell-rsq-03b-internal-chain-r6`；recorded at=`2026-08-26T09:26:11+00:00`；receipt 在 query batch 前 exclusive-create，同 attempt retry=false。
- request=`5`、compiled lane=`5`、local Qwen3-Embedding-0.6B query batch=`1`、request-level union=`338`、final=`80`、target-union occurrences=`794`。
- `network/provider/generation-model/external-capture/4B/reranker/retry/current-mutation/Candidate-promotion/Evidence-promotion/gap-closure` 全为 `0`。
- Runtime 的 `numeric_fact_count=11`、`typed_fact_resolved/gap/conflict=4/26/0` 是只读输入执行摘要，不是本次 NumericFact admission 或 promotion；全部 downstream authority 继续 false。

| target | complete source/compiled/union/final | best final rank | coverage gap | route observation |
|---|---:|---:|---:|---|
| ASP | 2/2/2/2 | 15 | 0 | same-pool reranker challenger eligible；未执行 |
| capacity release | 0/0/0/0 | — | 0 | external route required |
| capacity utilization/yield | 0/0/0/0 | — | 0 | external route required |
| HBM supply | 0/0/0/0 | — | 0 | external route required |
| supplier→Dell | 2/2/2/1 | 2 | 0 | local relationship/delivery present；capacity allocation remains open |
| units | 0/0/0/0 | — | 0 | external route required |

结果与最终 zero-call preview 及 immutable R5 current observations 完全一致：external target=`4`、reranker eligible=`1`、target-specific 4B recall eligible=`0`、local source-to-object repair=`0`。这不是补源，也没有运行用户要求保留的 reranker 或混合 4B challenger。

## 3. Artifact 完整性与 exact replay

- attempt receipt digest=`35e78361c64b81b7e6d4957a9d16374bc845939e1671308f89a3b7e89b4c0e94`，SHA=`89f110b919caaa76a3dcd5a331fc8bb7c4f90a97ef0c108c6fa078787fe1228b`。
- private digest=`5ec6e86d685c0dd323f316ee5367120d0f9baf0dc13d3ff4b2143c2cb4f1d169`，SHA=`41e35ba9114e1ac05558818af4bf7d8ecc4c349e2df6c3ee71888bb24df5e37a`。
- public digest=`396bdf25ee481e6a389d585950182c5c053cb95452bca36487d9b2f640a89c09`，SHA=`53114d2954aeb64b5d2329fe14d76a10943bfc102d9e56ecbc66e30002a8d00a`。
- raw execution SHA 与 validated digest 均为 `0e9e4456ba75ecd07bc2e3bd6d5deddafc1972ba19700b029b2e6793e99f7458`。
- policy/receipt/private/public self-digest、private digest/SHA link、raw execution SHA 均为 true。
- 作者仅使用保存的 raw execution、正式 recorded_at／Git identity／30 个 input bindings 对 1,888 source／34,199 objects 重编，用时 `218.543s`；`exact_private_recompile=true`、`exact_public_reprojection=true`。

## 4. 仍未通过的产品与研报门

R6 当前只是 author-integrity pass，不是 independent 03B pass。Fresh reviewer 必须重新攻击 clause polarity/modality/direction、positive recall、product/FY/proposition-slot anchors、recursive public schema、actual route counts 与 zero-authority seal。

R17 研报质量必须作为同一独立审计的第二部分：reader-visible citation/source appendix、14/9/4/10 gap crosswalk consumption、六项 WWC operationalization、事实密度与重复、02B qualified-human `0/16`、formal 8D validity 均继续 open。R6 不能让 R17、S2、产品、publication 或 release 自动通过。

下一顺序：完成 post-result repository gate；只提交 public result、model-run、worklog 与 Project OS（private/receipt 保持 canonical ignored path）；push 后启动全新 fork-none、作者分离、只读 auditor。Fresh audit 前不得启动 03C、4B、reranker、Evidence/NumericFact admission、S2 重编或新报告。

## 5. Post-result repository gate

R6 targeted=`95 passed`、Project OS=`82 passed`、active baseline=`213/8/5/28/0`、config JSON=`1,148`、Project OS JSONL=`8 files / 1,280 rows`、repository secret scan=`8,141 files / 0 findings`、compileall、四份 self-digest 与 diff check 全部通过。结果提交只包含 public result、model-run、worklog 与 Project OS；private 与 attempt receipt 留在 canonical ignored path。
