# DELL-RSQ-03B R39 本地 claim 修复与 R4 语义 successor

日期：2026-08-26
阶段：S1 / DELL-RSQ-03B same-stage R4
当前结论：R39 current runtime 已只追加修复一个真实本地对象损失；R4 完整工程门与唯一精确执行已通过作者完整性复验，fresh author-separated dual audit 尚未完成。

## 1. 为什么不是继续“补网页”

R3 fresh audit 证明 NVIDIA/Dell 页面已经在 R38 source store，真正缺失的是其中一句：

> One of Dell’s U.S. factories can ship thousands of NVIDIA Blackwell GPUs to customers in a week.

源记录 1887/1888 均有该句，但 compiled objects 34190–34198 没有。根因是历史句子切分把 `U.S.` 的句点误当成句末，两个短片段又低于 claim 最小长度，因此被静默丢弃。这是本地 source→object compiler failure，不是外源或 public-information gap。

## 2. R39 append-only 修复

- v1 segmentation 保持历史不变；新增 `sentence_with_wrapped_line_reflow_v2`，保护常见缩写并使用 exact offset locator。
- v2 claim identity 使用字符区间，不使用会随前置句变化的 ordinal。
- source store 保持 v5、1,888 条不变；v8 的 34,198 objects 保持精确前缀，只追加：
  - `COBJ::00d728a389f931920f8ff525`
  - char `1087:1183`
  - candidate-not-Evidence、numeric authority=false、evidence promoted=false。
- 只对新增 1 个对象使用本地 CUDA/FP16 Qwen3-Embedding-0.6B 补算向量；v9 cache 为 34,199×1,024 float16，CPU fallback=0，network/provider/generation=0。
- R39 current runtime registry、route v1.6、hybrid v1.9、binding v1.14、receipt v1.15 已校验；source=1,888、objects/embedding=34,199，S1 qualified 仍 false。

首次 promotion R1 在任何 current output 或 registry mutation 之前失败：registry helper 会重读尚未发布的 v1.9 policy。失败已保存为 `fin_ia_0_1_3_r39_abbreviation_runtime_promotion_R1_failure_assessment_v1_0.json`；修正顺序后 R2 成功，不追认 R1。

## 3. R4 语义与 coverage 合同

R4 继承 R3 已独立通过的 exact execution/attempt/integrity/privacy seal，不削弱 5 requests、1 query batch、每 request 96/16 ranks 及全部 zero-authority counters。

新增合同：

1. page parent 与 slices 归入一个 canonical source family，同时报告 canonical claim 数和 raw occurrence 数。
2. 对象按 slice index、char offset、frozen input order 排序；任何 package 最多覆盖 8 个绝对相邻单元。只选中的对象不会消除中间 300 个未选对象的距离。
3. supplier 必须是 Dell + 具名 supplier + 正向 relationship/delivery；否定合作或否定交付不得通过。
4. yield/utilization 必须是 observed measure；future/target/A14/SRAM qualifier 位于 measure 前后均排除。
5. units 必须有 Dell seller/shipper 角色、物理 server/system 数量及 company-period surface；大学/机构采购、客户收到 Dell 品牌设备、GPU 数量和美元 shipment 不得变成 Dell units。
6. coverage 只审 target-required material role，并要求材料性数字/时间 anchor 在 bounded compiled window 中真实存在；一般美元金额、Dell 全球 delivery、非具名 supply chain 和非 material tail 不创建 repair obligation。

## 4. 已通过的作者侧证据

- v2 compiler/route 与 R39 tests：聚焦 39 项通过。
- R4 adversarial/real-data tests：12 项通过，包括 fresh audit 的四个 bypass、真实 factory loss、parent/slice 2 occurrences→1 canonical gap、R39 repair 后归零、真实 ASP rank-16 package。
- 全 R39 corpus 第二轮只读扫描：六目标 canonical/occurrence coverage gaps 均为 0。
- R3 raw pool 对 R39 的只读 R4 预编译：
  - ASP source/compiled/union/final=`2/2/2/2`，best final rank=15，same-pool reranker challenger eligible=true；它仍只是 configuration/bundle observation。
  - supplier source/compiled/union/final=`2/2/2/1`，best final rank=2，reranker=false；capacity/allocation boundary 仍 open。
  - capacity release、observed yield、Dell-specific HBM bridge、Dell company-period physical units 均 complete=0；local repair=false，bounded 03C candidate=true。
  - target-specific 4B recall challenger eligible=0；这不撤销通用 mixed 4B program，只说明本轮六目标没有“对象已在 corpus 但 0.6B union 漏召”的 target。
  - 所有 Candidate/Evidence/promotion/gap closure/downstream authority 仍为 0/false。

## 5. 尚未完成与停止条件

- clean implementation commit/push 后，仅新增一个 policy authority commit；必须满足 authority parent=implementation、唯一 changed path=R4 policy、HEAD=upstream。
- 之后才能消费唯一 attempt `dell-rsq-03b-internal-chain-r4`，从 R39 current runtime 重新执行一个新 0.6B query batch；不能复用 R3 score 作为正式结果。
- 精确结果必须再交给新的 fork-none、作者分离、只读 reviewer；审计范围同时包含工程/语义路由与 R17 研报质量。fresh audit 通过前，不执行 03C、4B、reranker、Evidence admission、S2 重编、Pack/Readiness、新报告或产品验收。
- R17 仍为 55 Evidence、14 gaps、0 closure、02B human decisions 0/16；reader-visible citations/source appendix、crosswalk consumption、WWC operationality 和事实密度仍 OPEN/NOT_ASSESSABLE。

## 6. 全仓门与冻结边界纠偏

首轮全仓为 `1434 passed, 4 failed, 2 skipped, 2 existing warnings`。四个失败同源：作者最初把 v2 缩写逻辑放进了被 VS5 preregistration 逐字节冻结的 `object_view_compiler.py`，触发 qualification-bound SHA 漂移。不能通过改写冻结 preregistration 追认这次漂移；该方向在提交前撤回：

- v1 编译器已恢复预注册 SHA `043cbf8e...d8482`，历史资格边界保持原字节。
- 缩写感知 exact-offset 逻辑迁入 `object_view_compiler_v2.py`，只有 route 的显式 `sentence_with_wrapped_line_reflow_v2` 才启用；v1 输出不变。
- R39 的 factory 对象仍为 `COBJ::00d728a389f931920f8ff525`、`1087:1183`；append-only objects 与 embedding 结果不需要追认或改写。
- 历史 R1–R3 测试不再错误读取已推进到 R39 的 mutable current-registry bytes，而是按各自 policy 封存的 R38 id/digest 验证；生产 validator 未放宽。

纠偏后的最终作者门：focused `118 passed`，DELL/S1 adjacent `248 passed`，full repository `1439 passed, 2 skipped, 2 existing SWIG warnings`；compileall、pyflakes、active baseline `213/8/5/28/0`、1139 config JSON、8 份 Project OS JSONL／1237 行、Project OS `82 passed`、8117-file secret scan／0 和 diff check 全部通过。JSON/JSONL 校验工具 R1 因 PowerShell 冒号变量插值语法在读取前失败，R2 修正后完整通过；R1 不追认为数据门执行。

这些门只使 implementation snapshot 可以提交，不等于 R4 exact attempt、03B independent pass、信源缺口关闭或研报质量通过。

## 7. R4 唯一精确执行结果

- implementation commit=`14f11b8c...51789a`、tree=`e2d30481...0f2e1f` 已推送；authority commit=`aa61687f...43d74` 的唯一父提交为 implementation，唯一 changed path 为 R4 policy，执行时 `HEAD==upstream` 且工作树 clean。
- attempt `dell-rsq-03b-internal-chain-r4` 在 current R39 上只执行 1 个本地 Qwen3-Embedding-0.6B query batch；5 个唯一 request、每 request 精确 96 union／16 final，network/Provider/generation/external/4B/reranker/retry/mutation/promotion/closure 全为 0。
- 六 target 的 material coverage canonical/occurrence gaps 全为 `0/0`，local repair target=0。ASP=`2/2/2/2`、best rank 15、reranker challenger=1；supplier=`2/2/2/1`、best rank 2；capacity release、observed yield、Dell-HBM bridge、Dell company-period units 均=`0/0/0/0`，author route 仍为 bounded 03C candidate；target-specific 4B recall challenger=0。
- public digest=`cb72f7a5...2113ca6`、SHA=`9cf1b4f8...a3fd79`；private digest=`9f21a1f8...f412d65`、SHA=`85cab9d0...c54836b`；receipt SHA=`921d71b4...132cbe`。四份 self-digest、raw execution validator、private link 与 public exact reprojection 全部通过。
- post-result 门：R4/R39 定向 `76 passed`、Project OS `82 passed`、active baseline=`213/8/5/28/0`、config JSON=`1141/0 invalid`、Project OS JSONL=`8 files / 1246 lines / 0 invalid`、secret scan=`8120 files / 0 findings`、diff check 通过。
- 这是 author-integrity result，不是 03B independent pass。下一步只允许提交 immutable result 与 Project OS，然后启动全新的 fork-none、只读 reviewer，同时审 R4 工程/语义/route 和 R17 的 claim-source、citation/source appendix、14/9/4 crosswalk、WWC、密度/重复及八维质量。审计前所有下游 authority 继续 false。
