# S1 工作记录 090：DELL 03B R5 raw-position、typed-anchor 与语义 successor

日期：2026-08-26

状态：`R5 exact execution success / author exact recompile + reprojection pass / immutable result commit and fresh dual audit pending`

## 1. 为什么必须开 R5

Immutable R4 的 execution、integrity、privacy、R39 append-only repair 与真实 corpus 结果可重放，但 fresh dual audit 证明通用 route contract 仍有两组 material defect：

1. `RC-S1-077`：source sentence 在赋 position 前去重，20 条相同中间句会把真实 22-unit separation 压成 span 3；numeric/time anchor 又以 substring 比较，使 source `15` 被 compiled `150` 假覆盖，`H100` 等产品码可能贡献裸数字。
2. `RC-S1-078`：supplier、capacity、yield、HBM 与 units 仍可把 no/lack/denied、not/never/unavailable、will/forecast/planned、N2 pilot、negative shipment 和 reported counterparty shipment 判为 complete。

R4 policy/private/public/receipt/audit 均保持不变；R5 使用新 schema、policy、attempt 和 canonical output path，不重跑或覆盖 R4。

## 2. R4 audit digest 更正

实现 R5 policy validator 时发现 R4 fresh audit 的 `reviewed_artifacts.R4_public.result_digest` 手工多抄了一个字符：记录值长度 65，实际 public self-digest 长度 64。Public 文件 SHA=`9cf1b4f8...3fd79`、private digest、原 audit self-digest、P0/P1/P2/P3 与 route/report verdict 均未改变。

按 append-only 规则不改写原 audit；新增：

`configs/audits/fin_ia_0_1_3_dell_03b_r4_audit_public_digest_correction_v1_0.json`

correction digest=`0946e508573b7c8e6068aea6406baae7b0c3a3c2558ac8f16a69acd2b4362ea4`。R5 必须同时绑定原 audit 与 correction，不能通过放宽 digest 校验绕过。

## 3. R5 实现合同

- 每个 raw source sentence occurrence 先获得 immutable absolute position；canonical claim/display dedup 只能在 position 之后发生。
- 最多八个 absolute source/object units；selected candidate 只决定 visibility，不重新压缩相邻位置。
- currency、percent、number、number-word、fiscal year、calendar year、quarter、time unit 与 magnitude 使用 typed token-exact normalization；currency `15` 不等于 `150`，产品码中的数字不构成 numeric anchor。
- supplier 使用 scoped partnership/collaboration/delivery polarity；capacity/HBM 区分 affirmative allocation/configuration 与 denied/not/never/unavailable；yield 区分 observed measure 与 future/forecast/planned/pilot/wrong-process，同时保留同句 observed 80% 与 later target 90% 的正例；units 要求 Dell seller/shipper，排除 negative action 与 Dell reported counterparty action。
- Candidate 仍不是 Evidence；configuration price 仍不是 Dell company realized ASP；supplier relationship/delivery 仍不代表 capacity/allocation。
- 03C、4B embedding、reranker、Candidate/Evidence/NumericFact promotion、gap closure、public-information boundary、S1/S2/S3、report/product/publication/release authority 全部为 false。

## 4. 磁盘事故与执行前保护

首次写 R5 时 D 盘可用空间降到 0 bytes，`apply_patch` 留下 zero-byte untracked file。该文件已删除，tracked repository 与 R4 evidence 未受损。经 Owner 明确授权，只删除四个 `D:\temp` 临时目录：DingTalk updater、VS Code installer、Diagnostics 与 pip-unpack；它们不可从回收站恢复，共释放约 1.34 GiB。项目 data/index/model 与正在使用的 `_MEI` 目录未删除。

R5 runner 新增 pre-attempt capacity gate：canonical attempt receipt 之前必须至少有 `536,870,912` free bytes；不足则零写、零调用退出。正式 attempt 前还要重新检查磁盘，不依赖本次人工清理结果。

## 5. 作者回归与 full-corpus preview

- R5 targeted：`41 passed`；包括全部 R4 reproduced attacks、扩展 polarity/direction attacks、肯定 controls、raw occurrence 位置、`15 != 150`、产品码数字排除、policy/correction binding、correction 内部 SHA 与 policy input 的交叉绑定，以及 disk preflight。
- R1/R3/R4/R5/R39/query-object focused：`154 passed`。
- `compileall`、`pyflakes` 与 `git diff --check` 通过；Project OS=`82 passed`。
- 全仓=`1480 passed, 2 skipped, 2 existing SWIG warnings`；active baseline=`213 Python / 8 frontend / 5 detectors / 28 resources / 0 failures`。
- `1,143` 个 config JSON、`8` 个 Project OS JSONL／`1,258` 行均可解析；repository secret scan=`8,127 files / 0 findings`；correction self-digest 与内部 SHA cross-binding 精确通过。
- 使用 immutable R4 raw execution 做只读、零模型、零网络的全量 R5 single-pass preview；最终 scope-guard 版本对 1,888 source／34,199 objects 耗时 `94.953s`。未写 private/public/receipt，未消费 R5 attempt。
- Preview 结果：ASP=`2/2/2/2`、best final rank 15、reranker eligible；supplier=`2/2/2/1`、best rank 2；capacity release、observed yield、Dell-HBM bridge、Dell company-period physical units 均=`0/0/0/0`。六 target coverage gaps=`0`，external candidate=`4`、4B recall candidate=`0`，全部 authority=false。

## 6. 执行门状态

1. 最终 focused、Project OS、active baseline、JSON/JSONL、secret 与 full repository gate 已通过；
2. implementation commit=`9ed08c73...971d0`、tree=`241c22e5...436a` 已 clean push；
3. authority commit=`1e327656...51d6` 的唯一父提交为 implementation，唯一 changed path 为 R5 policy，且执行时 `HEAD==upstream`；
4. 执行前 free bytes=`1,419,427,840`，attempt/output 不存在；唯一 fresh local Qwen3-Embedding-0.6B batch 已成功，同 attempt 不重试；
5. immutable result 已通过作者 exact recompile/reprojection；下一门是提交结果，再交给另一个 fresh fork-none、作者分离、只读 reviewer，同时审 R5 工程/route 与 R17 研报质量；
6. fresh audit 前不运行 03C、4B 或 reranker，也不补源、晋升 Evidence、重编 S2 或新报告。

R17 仍为 55 Evidence／14 gaps／0 closure、02B qualified-human decisions=`0/16`；reader-visible citations/source appendix、14/9/4/10 crosswalk、六项 WWC operationalization 与事实密度仍未通过。

## 7. R5 唯一精确执行结果

- attempt=`dell-rsq-03b-internal-chain-r5`；recorded at=`2026-08-26T06:07:12+00:00`。5 个唯一 request、1 个本地 0.6B query-embedding batch、每 request 精确 96 union／16 final；network/provider/generation/external/4B/reranker/retry/mutation/promotion/closure 全为 0。
- ASP=`2/2/2/2`、best final rank 15；supplier=`2/2/2/1`、best rank 2；capacity release、observed yield、Dell-HBM bridge、Dell company-period units 均=`0/0/0/0`。六 target material coverage canonical/occurrence=`0/0`、external route candidate=4、reranker candidate=1、target-specific 4B recall candidate=0，全部 downstream authority=false。
- policy digest=`5477240d...a776c`；public digest=`bc916af9...0c3c1`、SHA=`1b8dc62c...36c9f`；private digest=`7949d84d...56df3`、SHA=`23b87124...b5c5d`；receipt digest=`5251a8d7...b4044`、SHA=`ea88579e...ade02`；raw execution SHA=`0e9e4456...9f7458`。
- 四份 self-digest、private link、raw execution SHA 均通过。作者只读全量 exact recompile 耗时 `144.925s`，private 逐字段相等，public exact reprojection 逐字段相等，且 public 不含 model text、material sentence 或 URL。
- 这是 author-integrity pass，不是 independent 03B pass，也没有改变 R17 的 14 gaps／0 closure 与研报质量失败。只有 immutable result commit/push 后才能启动全新的作者分离只读双审计。

## 8. post-result repository gate

R5 targeted=`41 passed`、Project OS=`82 passed`、active baseline=`213/8/5/28/0`、config JSON=`1,145`、Project OS JSONL=`8 files / 1,264 lines`、四份 self-digest 与 correction cross-binding、secret scan=`8,130 files / 0 findings`、diff check 全部通过。结果提交仍只允许 public result、model-run、worklog 与 Project OS；private 与 attempt receipt 保持在 ignored canonical private path。
