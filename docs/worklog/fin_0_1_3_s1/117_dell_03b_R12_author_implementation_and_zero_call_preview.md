# S1 工作记录 117：DELL 03B R12 作者实现、连接重置闭环与零调用预演

日期：2026-08-28

状态：`R12-01～R12-07 author implementation and immutable-R11-raw zero-call preview pass / implementation commit and push pending / no R12 policy, attempt, private or public result / fresh dual audit pending`

## 1. 本轮边界与不可变前序

本轮只实现工作记录 116 定义的同阶段、non-overwriting R12：恒常 RouteContractIdentityRegistry、结构化 ClauseOwnershipDecision v3、GoverningPriceHeadProof v2、ConnectorProofIdentity／lossless transformation v4，以及隔离的 R12 compiler、zero-model runner 与 direct tests。R11 implementation、policy、attempt receipt、raw、private/public、reviewed result、fixed manifest 和 fresh audit failure 均保持不可变。

R12 尚未创建 v2.1 policy，尚未消费 `dell-rsq-03b-internal-chain-r12`，也尚未生成 R12 private/public result。所有 preview 都只读取 immutable R11 raw execution 和冻结的 source/object inventory；新增 generation、Provider、network、external capture、0.6B embedding、4B embedding、reranker、CandidateDecision、Evidence promotion、gap closure 与 current mutation 均为 0。

因此，本记录证明的是作者实现和零调用编译门，不是 R12 executed、independent 或 03B pass，更不是上一版研报信源已经补齐。

## 2. R11 四项材料性 finding 的同阶段修复

### 2.1 Route contract state erasure

R12 不再从 immediate predecessor 的 active disposition 恢复 route identity，而是精确绑定 immutable `FIN-0.1.3-S1-DELL-RSQ-03A-R2` residual program，program digest=`ed6f11a8fe091d84362d2df041d5ea0bffa50a5c781274f60eaf9e73d6919d50`。每个 target 的 constant registry row 保存全部 route contract digest、全部 external ID、mandatory external ID/digest、local ID 和 row digest；active/inactive 只改变当前 disposition，不删除恒常 identity。

当前五个 external-required target 的 exact mandatory external route 为：

| target | mandatory external route contract IDs |
| --- | --- |
| ASP | `DELL-RSQ-03A-TARGET-ASP::official_issuer_regulator`; `DELL-RSQ-03A-TARGET-ASP::product_procurement_deployment` |
| capacity release | `DELL-RSQ-03A-TARGET-CAPACITY-RELEASE::named_supplier`; `DELL-RSQ-03A-TARGET-CAPACITY-RELEASE::official_issuer_regulator` |
| capacity utilization/yield | `DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD::industry_primary`; `::named_supplier`; `::official_issuer_regulator` |
| HBM supply | `DELL-RSQ-03A-TARGET-HBM-SUPPLY::industry_primary`; `::named_supplier`; `::official_issuer_regulator` |
| units | `DELL-RSQ-03A-TARGET-UNITS::industry_primary`; `::official_issuer_regulator` |

ASP 的 route identity digest=`9f8b150c67813891fa6e498cd05207ff9f0e3dca820511d63cd62419f0a64cf2`。其 `true→false→true` 行为测试恢复完全相同的两个 exact ID；required=true+empty、伪 ID、伪 digest、local 混入 external 和 program drift 均 fail closed。supplier 当前已有完整 bounded package，故其恒常 registry 仍存在但 active external IDs 为空，不构成执行授权。

### 2.2 Case-independent structural clause ownership

R12 以 case-preserving surface alignment、全部 predicate candidates、owner NP、finite predicate／auxiliary、fronted functional adjunct 和 material-right-surface 证明决定 `shared_subject_proved`、`independent_owner_proved`、`ambiguous_material_boundary` 或 `non_clause_continuation`。大小写不再决定 owner；未知 verb 和 predicate/name collision 在无法证明 shared subject 时形成 typed barrier。

direct adversarial tests 覆盖 lower/mixed-case `eBay Systems wugged`、`vanadium labs zorps`、`rose systems offered`，以及未见 `following/next/subsequent quarter`、`under the framework/agreement/contract` 等 adjunct；合法 shared-subject auxiliary、compound subject、object list、offset-zero continuation 和显式右 owner controls 仍保持预期 verdict。新增 clause-decision diagnostics 在 source/compiled 两侧实际 materialize，而不是只存在于 schema。

### 2.3 Governing price head

R12 先证明 argument group 的 governing nominal head，再判断 product/object、price 与 connector。service、delivery、financing、lease、support、contract 和 nonce governing head 不能再被附近 `hardware at price` 覆盖；只有明确 purchase/config/list/recommended/quoted price 或直接 product↔price predicate path 才能进入 affirmative proof。

direct tests 同时冻结维护服务、交付服务、租赁融资、支持、合同和 nonce negatives，以及 direct product-for-price、price-for-product、priced-at 和 purchase-price positives。当前全语料 source/compiled governing-head partial diagnostic 均为 0；这表示当前被选择 package 未触发该新 barrier，不表示 ASP 外源事实已经出现。

### 2.4 Connector proof identity 与 transformation

R12 的 argument group 和 source→compiled binding 保存 connector lexical class、governing head、normalized proof identity、role span mapping 与 typed `loss/addition/ambiguity/proof_rebind` flags。`for→at` 会以 proof rebind 拒绝，price、product、predicate、owner、head 或 connector 改绑均不能无 flag accepted；只改变绝对 offset、但 surface、connector class 和 normalized proof 完全一致的 slice 仍可接受。

最终 full-corpus preview 的六 target `proof_rebind_failure_count=0`；failed-complete、unbound-complete、compiled-complete-without-source 均为 0。preview 还硬断言上述 diagnostics 非 null，防止实现后续退化成“字段存在但没有计算”。

## 3. Zero-model exact successor runner

R12 的 formal path 已删除 fresh `ResearchRetrievalService`／`execute_current_runtime_requests` 路径。唯一候选输入固定为 R11 raw execution SHA-256=`0e9e4456ba75ecd07bc2e3bd6d5deddafc1972ba19700b029b2e6793e99f7458`，且必须同时通过 R11 raw capture schema、attempt ID、self-digest、private equality、request population、5 requests、338 unique union、80 final 和上游一次本地 embedding batch验证。

后续唯一 R12 attempt 若获 policy authority，将先写 `fin_ia_dell_report_internal_chain_raw_reuse_capture_v1_0` successor capture。该 capture 显式保存 R11 raw ref/SHA/result digest/attempt、reuse reason、candidate-generation-equivalence proof、上游本地 embedding batch=`1` 与 R12 新增 batch=`0`。R12 新增 network/provider/model/generation/external/0.6B/4B/reranker/retry/promotion/closure counters 全部必须为 0；raw-first、exclusive receipt、same-ID no retry、clean identity recheck、private/public atomic pair 和 saved replay byte equality 均保留。

这不是为了成本而删掉必要研究，而是因为四项 R12 改动全部位于冻结 candidate generation 之后。若 query、inventory、vector、union 或 raw rank 任一可能改变，runner 必须停止，不得复用 R11 raw。

### 3.1 冻结前 staged-diff 自审新增的完整性门

作者在正式 authority 之前对完整 staged diff 做了第二轮逆向审查，发现四个尚未被原测试覆盖、但可能让错误持久化或公开投影静默通过的边界。它们均在 attempt 消费前修复并补直接攻击测试：

- saved transformation validator 过去没有把 `proof_rebind_flags` 纳入 material failure；现逐条验证 proof-rebind，mutation 必须 fail closed；
- zero-call policy 过去证明了 raw SHA，但没有逐项要求 `source_records`、`compiled_objects`、`execution_program`、`runtime_registry` 和 `runtime_binding_receipt` 与 R11 private input binding 精确一致；现五项任何 ref/SHA drift 都拒绝；
- formal path 过去先写 R12 raw-reuse capture 后直接使用内存对象编译；现必须从磁盘重读、复核 schema/self-digest/R11 lineage 后才允许 compile，避免“写出的证据”和“实际编译输入”分叉；
- public projection 过去会删除 private transformation rows 后只保留 summary，却未先证明 summary 是这些 rows 的真实聚合；现逐行验证 role mapping、binding self-digest、accepted/material flag 合同，再验证 ID 唯一性、数量、集合 digest、proof-rebind/unbound/failed diagnostics，任何篡改均拒绝公开投影。

真实全语料复证覆盖 1,601 条 binding（1,277 accepted／324 failed），六个 target 的逐行与汇总自校验全部通过，`proof_rebind_failure_count=0`。这些 324 个 failed binding 是保留的 partial/结构失败证据，不是 complete-family 失败；随后 preview 继续证明 complete coverage 6/6、failed-complete=0。

## 4. Preview 性能 hard-stop 与根因修复

第一次 full-corpus preview 用时 `284.729772s`，超过计划的 `>120s` hard stop。当时立即停止 formal 方向；该慢速结果没有被当作通过，也未消费 attempt。

profiling 证明主要开销不是 pytest、embedding、网络或外源，而是 ASP 等高提示密度 target 对相同文本反复执行 frame extraction、boundary parsing 和 R4 fallback。修正采用语义等价的确定性路径：

- 每个 unit 一次性生成 frame records 和 boundary decisions；
- 用 sound necessary-condition surface guard 跳过不可能形成 R12 frame 的文本；
- package selection 和 transformation 复用同一 runtime frame objects；
- 对未入选 package 延迟昂贵 diagnostics；
- R12 frame 已完整替代 R4 verdict 时不再重复调用旧 classifier。

优化阶段先以 canonical target digest证明输出不变；随后新增 route identity 和结构诊断字段属于有意 schema delta。首次优化后 preview 用时 `25.359961s`；完成 staged-diff 自审门后的最终冻结复跑为 `23.882675s`，低于 `<70s` warning，较初始下降约 91.6%，且没有通过缩小 source/object/target 或候选集换取速度。

## 5. 最终 immutable-R11-raw 零调用全语料 preview

命令：

`python scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r12.py --mode preview`

最终结果：source records=`1,888`；compiled objects=`34,199`；candidate union occurrences=`794`；request count=`5`；elapsed=`23.882675s`；preview digest=`ad4ef78ca6226ceb749d50649419ba25ca90b8d88d50060d55982cbc48297b4a`；model/provider/network/generation/external/embedding/4B/reranker/retry/promotion/closure/current mutation=`0`。

| target | R11 complete source/compiled/union/final | R12 complete source/compiled/union/final | best final rank | R11 partial source/compiled | R12 partial source/compiled |
| --- | ---: | ---: | ---: | ---: | ---: |
| ASP | 0/0/0/0 | 0/0/0/0 | null | 844/951 | 844/951 |
| capacity release | 0/0/0/0 | 0/0/0/0 | null | 388/353 | 381/347 |
| capacity utilization/yield | 0/0/0/0 | 0/0/0/0 | null | 5/8 | 5/8 |
| HBM supply | 0/0/0/0 | 0/0/0/0 | null | 17/19 | 16/18 |
| supplier readthrough | 3/3/2/1 | 3/3/2/1 | 2 | 80/73 | 76/69 |
| units | 0/0/0/0 | 0/0/0/0 | null | 332/295 | 332/295 |

六个 target 的 complete family population、四层 complete count、best final rank 和 non-route downstream disposition 均与 R11 完全相同；complete transformation coverage 6/6 pass。ASP 从 R11 错误的 active route IDs=`[]` 恢复为两个精确 contract IDs；其他 active route set保持不变。

## 6. Partial-only family delta 的逐来源解释

这些 delta 只描述 partial source→compiled transformation 的结构绑定，不是 Evidence 数量、gap closure 或 source ladder 完成度：

- ASP 新增 unbound：`DELL_2024...PART_03`、`DELL_2025...PART_02`。两者实际是 Price Waterhouse／PricewaterhouseCoopers 任职叙述，仍缺 Dell quoter、硬件对象和币价；R12 不再把 source/compiled 中不同的独立 owner 决策当作 lossless。它们没有变成 complete。
- ASP 移除 unbound：MSFT 2023/2024/2025 Item 8 三个会计履约义务／stand-alone selling price family。R12 对 source/compiled 的 shared-subject、actuality和 polarity结构取得一致绑定；它们仍缺 Dell、AI server 和真实 currency price，保持 partial。
- capacity 新增 unbound：`NVDA_2024...ITEM7...PART_01` 的标题与正文在 period／clause proof 上不等价；仍缺 Dell beneficiary 和 allocation period。capacity 移除 unbound：Dell 2026 Item 1A 债务偿还／现金分配文本被正确降为 non-target，不再伪装为生产 capacity。
- HBM 新增 unbound：`PUBLIC::DELL-EXT::AF72...` 的 NVIDIA／TSMC 先进制程紧张背景在 R12 中显式识别 named supplier，但 source/compiled 不能形成同一 bounded frame，且始终缺 Dell allocation/configuration bridge 和 period。
- supplier 新增 unbound：NVDA 2023 cloud-service partner 句在 R12 中选中真正 `NVIDIA has partnered...` frame，而 compiled window 未保存相同 frame，故 fail closed；它仍没有 Dell delivery direction。supplier 移除 unbound：Dell/VMware/Broadcom 董事履历叙述被正确降为 non-target，不再作为供应关系 partial。
- units 移除 unbound：三条 MSFT 履约义务文本、MU 2023 IP license 文本和 MU 2026 10b5-1 股票销售文本在 R12 中得到 source/compiled结构一致绑定；它们仍全部缺 Dell actual shipper、AI server product、physical quantity 和 shipment period，保持 partial。units complete count仍为0。

因此，R12 的当前结论仍是五个 target 的 local source corpus 缺少 complete bounded package；不得把 partial binding 的增减解释成外源补齐或 public non-disclosure。

## 7. 风险分层作者门与全仓 pytest 负担控制

- T1 R12 direct 最终复跑：`130 passed in 22.85s`，目标 `<90s`。
- T2 R11+R12 adjacent：`223 passed in 28.15s`，目标 `<150s`。
- T3 Project OS + base/R3 foundation seam：`140 passed in 41.66s`，目标 `<180s`。
- Project OS 在最终记录与 append-only ledger 写入后复跑：`82 passed in 11.32s`；8份 JSONL／1,363行全部解析。
- changed Python `py_compile` 和 `pyflakes` 通过；`ruff` 当前环境未安装，未伪报 ruff 通过。
- R11 fixed manifest=`34/34`；R12 active-import isolation通过；active baseline=`213 Python / 8 frontend / 5 detectors / 28 resources / 0 forbidden`；最终 repository secret scan=`8,227 files / 0 findings`；`git diff --check`通过。
- T4 未运行。R12 只新增隔离 successor modules、runner、tests 和记录，未修改 shared/active runtime、dependency、pytest config或 current consumer；T1～T3 没有暴露跨域失败。因此按照风险分层策略，不把约20分钟全仓 pytest当作频繁心跳。若后续 policy/result 提交只增加数据文件，仍以 T0/T1/Project OS 和 exact replay为主；只有共享运行时变化、影响范围无法证明或分层门出现跨域异常才触发 T4。

## 8. GitHub connection reset 的彻底归因与持久修复

多次 `git push` 的 `connection reset`／`github.com:443 timeout` 根因已确认：当前网络不能稳定直连 GitHub，而 Git 没有继承 Windows Internet Settings 中运行于 `127.0.0.1:6696` 的 OKZ/AtlasCore HTTP proxy，因此绕过了可用代理。

仓库级持久修复为：

`git config --local http.https://github.com.proxy http://127.0.0.1:6696`

显式代理 `ls-remote`、默认配置 `ls-remote` 和多次 non-force push 均已成功，HEAD/upstream 也已多次闭合。没有修改 system/global Git 或 Windows proxy。剩余外部依赖是本机 6696 listener：若代理进程未运行，Git 应 fail closed并明确报告 listener 不可用，不能静默退回当前已知不稳定的 direct path。

## 9. 研报质量边界与独立审计范围

R17 固定14文件仍为 `FAIL_GATE_OPEN_NOT_ASSESSABLE (P0/P1/P2/P3=0/1/2/1)`：reader-visible URL=`0`；18个 report EV 的 title/exact passage/locator/URL binding=`0/18`；14/9/4/10/4 crosswalk 未绑定；operational WWC=`0/6`；Facts=`72/36 unique`；02B qualified-human decisions=`0/16`；formal 8D=null。

R12 只阻止未来把错误语义候选写成证据，并恢复五条外源路线的精确合同身份；它不补任何 R17 citation，也不签研报质量。fresh reviewer 必须分别签发 R12 engineering/Evidence-pipeline verdict 和 R17 report-source/content-quality carry-forward verdict，审查 citation/source appendix、crosswalk、WWC、定量桥、因果边界、反方、去重/密度和八维质量；工程 finding=0不能替代研报或 qualified-human 验收。

## 10. 下一合法顺序

1. 更新 Project OS，复跑 T0/T1和账本解析，形成 clean implementation commit并通过仓库代理 non-force push。
2. 在 clean/synced implementation commit上创建只改一个 v2.1 policy文件的 authority commit；policy精确绑定15项 inputs、全部 implementation paths和 task-specific `TokenBudgetBasis`。
3. 执行唯一 `dell-rsq-03b-internal-chain-r12` zero-model formal：先写 raw-reuse successor，再生成 private/public；随后做 exact saved-formal replay。任一失败保留同 ID terminal evidence，不重试。
4. 冻结 reviewed result 和 fixed audit manifest，再交给作者分离、只读 reviewer同时审 R12工程与 R17研报质量。
5. 只有 fresh R12 engineering independent PASS 后才进入五条 residual external source ladders。随后在真实 changed candidate pool上运行0.6B/4B mixed embedding shadow；reranker保留，并仅在存在同池 eligible candidates时启用。
6. 完成 CandidateDecision、Evidence与 qualified-human admission，重编 Pack/Readiness和 S2 `units/share→ASP/mix→PVM→产品利润／营运资金`，再运行受影响 S3、生成不覆盖 R17 的新研报与 reader citation appendix，并分别完成工程审计、研报质量审计和 qualified-human验收。

在第4步工程独立通过前，03C、4B、reranker、Evidence、Readiness、S2、S3、新报告、formal 8D、product/publication/release authority均为 false。
