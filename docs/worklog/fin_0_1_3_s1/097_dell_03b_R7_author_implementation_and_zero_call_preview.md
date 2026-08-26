# S1 工作记录 097：DELL 03B R7 作者实现、性能纠偏与零调用全量预演

日期：2026-08-26

状态：`author implementation, zero-call preview and final repository gates pass / R7 policy, attempt, private and public result absent / fresh audit pending`

## 1. R7 owning-stage 实现

R7 不覆盖 R6，而是新增 v1.6 semantic kernel、candidate-chain compiler、exact-once runner 与 tests，针对 fresh R6 dual audit 的三个通用根因实施：

- `RC-S1-079`：引入 immutable `TypedProposition`。每个 proposition 保存 sentence/clause/span、actor、predicate、object、recipient、counterparty、polarity、modality、status、reported-speech、quantity/measure/currency/unit/qualifier、product/period/process、missing roles、limitations、digest 和 stable ID。`complete` 只允许一个 accepted proposition 同时满足 target contract；跨 clause、sentence、object 或 package 的 group union 不再是 completion authority。
- `RC-S1-080`：material coverage 改为 `accepted_proposition_role_bound_v3`。anchor 只从 accepted proposition 的 actor/counterparty/recipient/predicate/object/product/price/quantity/period/process/yield roles 生成；NVIDIA source 不能由 Micron object、`$15` 不能由 `$150` 或无关 support `$15` 覆盖。H/B/A/GB/MI/XE separator/plural、FY apostrophe/two/four digit、USD/dollars/magnitude/qualifier 语法统一。
- `RC-S0-105`：保留 recursive exact-key allowlist，并新增 field-typed content validator。repo ref、identifier、commit/digest、enum/status、narrative 分别校验；percent decode 后拒绝 scheme、裸 locator、drive/UNC/absolute path、`..`/backslash traversal、credential assignment、secret-like/high-entropy token，合法中文/英文金融叙述、货币、百分比与产品码不过度拦截。

R7 predecessor validator 精确绑定 immutable R6 policy/public/private/attempt receipt/fresh audit，复验 R6 `0/0/3/0`、R17 `0/1/2/1`、24 inputs、14 implementation bindings、5 requests、one local 0.6B batch、exact replay/reprojection、zero-authority counters 和 no-retry boundary。R7 runner 增加五份 R6 input binding；v1.6 policy 仍必须在 implementation identity 冻结后单独生成。

## 2. 冻结语义、anchor 与 privacy 回归

当前 R7 targeted=`151 passed`，包括：

- fresh R6 的 rumor/denial/suspension/capability/zero/revoked allocation、forecast/withdrawn/simulated yield、customer report/dispute、can/alleged/withdrawn quote、cross-sentence other-actor attacks；
- supplier、capacity、HBM、yield、units、ASP 的正向同义控制；
- 一个命题各缺一槽但 package 合并后仍 partial；raw occurrence 先定位且不同 sentence 不拼 complete；
- product/FY/currency/qualifier canonical grammar，以及 role-bound price/product/supplier-entity coverage；
- allowed public value 中 credential、high entropy、encoded locator、parent traversal、secret-like identifier/ref attacks 与合法金融 narrative controls；
- R6 fresh-audit predecessor、exact-output、disk、public projection 和 policy drift gates。

最终作者门同时通过：R1/R3/R4/R5/R6/R7 adjacent=`357 passed`；Project OS=`82 passed`；全仓=`1726 passed, 2 skipped, 2 existing SWIG warnings`，耗时 `1319.73s`。`compileall`、`pyflakes`、`git diff --check`、active baseline=`213 Python / 8 frontend / 5 detectors / 28 resources / 0 failures`、config JSON=`1,149`、Project OS JSONL=`8 files / 1,290 rows`、repository secret scan=`8,149 files / 0 findings` 全部通过。

实现过程中额外发现并修复两项作者问题：

1. `plan` 名词（maintenance and support services plan）曾被 modal regex 当成未来态；现只有 `plan/planned/plans + to/on/for` 才触发 modality。
2. `With NVIDIA hardware ..., only Dell delivers consistency` 曾因同句实体邻近被错判 supplier delivery；现 delivery predicate 必须绑定 supplier→Dell、Dell-with-supplier-product sell-through、relevant product object 或 explicit partnership。真实 `Dell servers with NVIDIA GB200 are shipping` 保留，actor=`Dell`、counterparty=`NVIDIA`、recipient=`customer_market`；Dell 财报中的 partners including NVIDIA 也保留。

## 3. 性能门失败与同阶段纠偏

首轮全量预演仍沿用最多八句重叠窗口，并在 coverage 中重复 proposition extraction。进程持续占用 CPU、内存稳定但超过 30 分钟门限；作者主动停止，零写、零模型、零网络、未创建 policy/result/receipt、未消费 R7 attempt。该次只证明 implementation performance gate 失败，不形成语义 verdict。

同阶段修复严格保持单命题质量门：R7 contract 明确 proposition 不跨 sentence，因此 source/object 直接按一个 raw sentence unit 分类，不再生成八句重叠窗口；coverage 复用 raw occurrence 单次遍历，并使用覆盖六 extractor 前置条件的 recall-only target hint。回归 `145/145` 后继续加入 supplier direction/entity 与 noun-modality controls，最终为 `151/151`。

最终复用 immutable R6 raw execution、1,888 source／34,199 objects 的零模型全量预演用时 `223.188s`。没有运行 embedding、Provider、generation、network、external、4B、reranker、CandidateDecision、Evidence/NumericFact promotion 或 gap closure，也没有写任何正式 R7 artifact。

## 4. R6→R7 current-corpus proposition crosswalk

最终 source/compiled/union/final：

- ASP=`1/1/1/1`，best final rank=`2`。保留 `PUBLIC::DELL-EXT::329F...`：`Dell quoted $757,231 as the purchase price for the hardware` 在同一 proposition 内绑定 Dell quoter、quote predicate、bounded hardware、price 与 2025 period。它仍只是 configuration/bundle price，不是 company realized ASP。
- R6 的 CSpire/JSU `PUBLIC::DELL-EXT::3F79...` 被正确撤回：合同价格的卖方/承包方是 CSpire，Dell 只在另一个 sentence 的 PowerEdge product description 中出现；R6 通过跨句 union 把它误当 Dell quote。该撤回不是信源丢失。
- supplier read-through=`3/3/2/1`，best final rank=`2`。三条 corpus proposition 分别为 Dell servers with NVIDIA GB200 的 downstream sell-through、official NVIDIA–Dell partnership、Dell earnings-call ecosystem partners including NVIDIA；最后一条是 R6 枚举 regex 漏掉的单命题真阳性。Final 仍是 GB200 sell-through family。
- capacity release、observed yield/utilization、Dell-HBM bridge、Dell company physical units 均=`0/0/0/0`；四项仍需要后续有回执的 external ladder，不能写成 public-information gap。
- 六 target role-bound material coverage canonical/occurrence gap=`0/0`，local source→object repair target=`0`；external target=`4`、4B recall eligibility=`0`。

R6 的 ASP rank 15 来自价格与 Dell product/quantity 跨对象 group union；R7 的真实同命题 Dell hardware quote 本身在 final rank 2，因此当前 same-pool reranker operational eligibility 从 1 变为 0。重排器没有从架构或后续规划中删除：它保留为未来 external/new-candidate pool 或独立排序评测的 challenger，但不得为了满足旧计划而在已无 rank miss 的当前 pool 上制造 eligibility。任何 reranker/4B 运行仍需 R7 fresh pass 后另行 authority 和 task-specific budget。

## 5. 尚未完成与下一门

当前仍没有 v1.6 policy、R7 attempt/private/public result。作者实现和 preview 不能等于 independent pass。继续顺序为：

1. clean implementation commit/push；
2. 以 implementation commit/tree 和 exact SHA 生成 policy-only authority commit/push；
3. clean `HEAD==upstream`、parent/path/input/output/disk 门通过后消费唯一 R7 attempt；
4. exact private replay/public reprojection、immutable result commit/push；
5. 启动全新 fork-none、作者分离、只读 reviewer，同时审 R7 engineering/semantics/anchors/privacy/route 与 R17 研报质量。

R17 reader-visible citations/source appendix、14/9/4/10 crosswalk、WWC `0/6` operationalization、density/repetition、02B decisions `0/16` 与 formal 8D 继续失败。R7 也没有解决上一版研报的全部信源缺失：四个 residual external targets 尚未补源，Evidence admission、Pack/Readiness、S2、非覆盖式新报告、工程与研报双审计、qualified-human/product/publication/release 均未开始且 authority=false。

## 6. Owner 对高频全仓回归的纠偏

Owner 指出单次全仓 pytest 已约 20 分钟，若在代码小修、账本追加、policy-only 和审计阶段反复运行，其等待成本会超过实现与审查本身。该异议成立：全仓应是高风险实现冻结/合并/release 门，不是每次文件变化的默认门。

`docs/project_os/risk_tiered_test_evidence_policy.zh-CN.md` 因此建立 T0 静态、T1 直接、T2 邻接、T3 子系统、T4 全仓五级证据与 fail-up 条件。当前 `pyproject.toml` 虽声明多类 marker，但关键 marker 尚未实际覆盖，不能用负向 `-m` 排除制造假安全；现阶段使用显式测试路径，下一次必要全仓附加 `--durations=50` 后再决定热点优化与 hermetic 并行。

R7 executable/test semantics 已被一次 targeted、adjacent 与全仓冻结证据覆盖。此后仅有 worklog/Project OS/测试策略变化，所以提交前只补跑 Project OS、JSON/JSONL、compile/static 与 diff 等受影响门；policy-only、immutable result 与 fresh audit 也不默认重复全仓。若 R7 production/test、共享 validator 或 active consumer 再发生语义变化，证据复用失效并按风险自动升级。
