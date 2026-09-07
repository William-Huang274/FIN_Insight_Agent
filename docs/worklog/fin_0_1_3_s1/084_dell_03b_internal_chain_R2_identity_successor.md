# S1 工作记录 084：DELL 03B R2 source identity successor

日期：2026-08-25

状态：`R2 executed and materialized / author review complete / fresh read-only audit pending`

## 1. 需求票与依赖

| 票据 | 输入 | 输出 | 工程验收 | 模型／研报质量验收 |
|---|---|---|---|---|
| 03B-R2-01 | R1 policy、terminal failure receipt | 非覆盖式 v1.1 successor authority | R1 identity／digest／SHA、R2 identity、自摘要、预算与权限 fail closed | 不改变 6/3 target 分区、语义规则或研报 claim 含义 |
| 03B-R2-02 | R38 source JSONL | canonical source identity set | 只接受非空、trimmed、唯一 `evidence_id`；拒绝 `source_record_id` alias | 不把字段错误归类为信源缺失或模型质量失败 |
| 03B-R2-03 | R38 compiled objects、binding receipt | exact source↔compiled lineage equality | 34,198 object 全有 lineage；1,888 source identity 与 lineage identity 集合精确相等 | 每个 candidate 的 source lineage 可追溯，不能出现幽灵引用 |
| 03B-R2-04 | clean/synced commit、5 frozen requests | 一次性 R2 private/public result | pre-model gate、1 query batch、0 network/provider/4B/reranker、new-file-only write | 精确区分 corpus absence、recall miss、post-union cut、useful@10 |
| 03B-R2-05 | R2 immutable result | 后续路线 decision | 先固化、再由 author-separated 只读审计 | 审计同时覆盖工程正确性、target 语义、信源充分性和最终研报可用性 |

依赖顺序为：`R1 failure preserved → identity contract → real-store regression → full repository gate → clean
commit/push → one R2 run → immutable result → fresh read-only audit → 03C/4B/reranker separate authority`。

## 2. 修复内容

1. source-store 身份从错误的 `source_record_id` 改为唯一合法字段 `evidence_id`；不做兼容 fallback。
2. source/object identity 门从 model 执行后移到 query embedding 前；失败不再浪费一次 batch。
3. receipt 必须声明 all-source-lineage-bound、outside=[]、missing=[]，并且 compiled lineage 集合必须与
   canonical source identity 集合完全相等；结果编译时再验一次。
4. R2 policy 绑定 immutable R1 policy 与 failure receipt；R1 的 query score、partial state 和 result 均不复用。
5. runner 默认只接受 canonical v1.1 successor，并要求 clean worktree、HEAD==upstream、实现 SHA 匹配和
   v1.1 output 不存在。

## 3. 输入输出和停止条件

- 输入：03A R2 residual program、DELL proposition execution program、R38 registry／binding receipt、
  readiness v1.7、1,888 source rows、34,198 compiled objects、既有 BM25／0.6B dense／typed graph runtime。
- private 输出：`data/workbench_private/fin_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling/
  dell-rsq-03b-internal-chain-r2/full_result.json`。
- public 输出：`configs/retrieval/
  fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_result_v1_1.json`。
- 任一 Git、SHA、digest、schema、identity、lineage、target、request、budget 或 output collision 异常立即停止；
  不自动生成 R3，不扩大到 held target、外源、4B 或 reranker。

## 4. 工程与质量测试

- focused 03B：`29 passed`；覆盖 successor lineage、R1 reuse、预算／权限 mutation、真实 1,888／34,198
  population、alias／缺失／重复 identity、source-lineage 集合错配、6 个 target positive control、ASP／units
  false-positive control、4B／reranker／03C 分流和 public text leak。
- adjacent DELL S1：`125 passed`；覆盖 02A、03A、gap crosswalk、internal proposition、external ladder 和
  direct capture 相邻合同。
- full repository：`1390 passed, 2 skipped, 2 warnings in 259.44s`；两条 warning 为既有 SWIG
  deprecation。compileall、精确 pyflakes、active baseline `213/8/5/28/0`、1127 config JSON、8 份
  Project OS JSONL／1220 行、Project OS `82 passed`、8091-file secret scan／0 和 diff check 全部通过。
  这些工程门支持随后的 exact stage／commit／push；push 未成功或 `HEAD!=upstream` 时 runner 会在模型前拒绝。

## 5. 研报质量接口

03B 不以“候选很多”或“12/12 material axis complete”代替研报信源充分性。每个 target 必须输出完整命题对象
在 corpus／union／useful@10／final 的位置；候选仍为 candidate-not-evidence。后续 admission 必须检查 ticker、
company/product owner、publication/measurement period、GAAP/non-GAAP basis、单位与分母、事实／关系角色、
read-through 方向和 forbidden inference。新的 author-separated 审计必须阅读最终 citation/source appendix 和
正文 claim-source use，不能只审代码或 schema。

## 6. 不变边界

当前仍无 02B human decision、真实补源、4B/reranker 运行、Evidence promotion、S2 bridge 重编、新研报或
产品验收。R2 的成功只决定下一步 eligibility；它本身不授予 03C、CandidateDecision、Evidence admission、
gap closure、S1/S2/S3、report/product/publication/release 权限。

## 7. R2 实际结果

implementation commit `53ea34a1...4f5` 推送成功后，runner 的 clean/synced、output collision、predecessor、
failure、implementation、source/object SHA 与 exact 1,888-source／34,198-object lineage preflight 全部通过。
唯一 R2 在 `2026-08-25T12:47:13+00:00` 完成：5 requests、1 local 0.6B query batch、339 union candidates、
80 final candidates；network/provider/generation/external/4B/reranker/promotion/gap closure 全为 0。

6 个 target 的 complete-corpus／complete-union／complete-final 都是 0。partial corpus 分别为 ASP 84、
capacity release 2、capacity utilization/yield 3、HBM supply 15、supplier read-through 7、units 3；partial
union/final 分别为 6/3、0/0、0/0、4/2、2/0、2/1。因此 4B embedding recall challenger eligible=0、
same-pool reranker eligible=0、03C external route required=6。

public result：`configs/retrieval/
fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_result_v1_1.json`，digest=`6c8159ed...132496`；
private digest=`eaa604ad...7d65df`。作者侧 top-partial 抽查没有看到完整 target 被错误降级，但这不是独立结论。
post-result validation 为 03B＋Project OS `111 passed`、1128 config JSON、8 Project OS JSONL／1222 行、
8092-file secret scan／0、public/private digest／SHA parity 和 diff check 全通过。
下一步先提交/push immutable result，再让无上下文继承的只读 reviewer 复核工程、语义假阴性、信源充分性、
上一版研报 gap crosswalk 和未来研报 claim-source/citation 质量；审计通过前不启动 03C。
