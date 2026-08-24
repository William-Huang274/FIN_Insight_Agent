# S1 工作记录 081：R35–R38 已审阅公共源同步与全库门禁

日期：2026-08-25

状态：`reviewed_public_source_runtime_sync_pass / broader_source_ladders_and_S1_qualification_open`

## 1. R35–R37 不是“多抓几页”，而是补完整消费链

DELL R4 Pack 已有 `55 Evidence / 14 gaps`，其中包含 6 份 `PUBLIC_PDF` 和 20 个
`PUBLIC_WEB`。最初这些 public document 已进入 Pack，却没有完整进入 current source、object、
index、material-policy 和动态 consumer。修复过程保留了每个失败 attempt：

- R3：Pack 中 PDF 不在 current object/index；
- R4：新对象已有，但 source route 未绑定；
- R5：retrieval facet 未进入 current policy；
- material promotion P1：ontology preflight 仍缺该 facet；
- R6：冻结 shortlist 不认识 successor facet；
- R7：compact Evidence card 丢失 PDF authority receipt；
- R8：R37 current canary 成功，public digest `20a180aa...`。

这些失败没有改写成成功，也没有通过降低断言、复制 relevance label 或把 Candidate 当 Evidence
来绕过。冻结的 `evidence_role_v2.py` 和 `financial_evidence_shortlist_v2.py` 保持字节语义，新的
bounded facets 只在兼容层解释。

## 2. R37 全库门发现的第二个真实缺口

R37 三案回执已能复用 current Pack/readiness/control context，但第一次完整 `pytest` 为
`1276 passed / 2 failed / 2 skipped`。一项是 25-lane 旧断言与 current 28-lane 合同漂移；另一项
是真缺陷：DELL R4 后加入的 NVIDIA 官方 `PUBLIC_WEB` 页面
`PUBLIC::DELL-EXT::2184F13EB685F627C757` 在 current corpus 中缺四次 reviewed-label occurrence。

失败回执
`configs/audits/fin_ia_0_1_3_r37_full_repository_gate_R1_failure_assessment_v1_0.json`，digest
`ad922332...`。本轮没有把 zero-missing 断言改成容忍缺失，而是开 R38 successor 修所属的 S1
同步层。

## 3. R38 append-only successor

R38 只追加该官方网页和精确 reviewed slice：

- source records：`1886 → 1888`；
- compiled objects：`34189 → 34198`，新增 9 个对象；
- 0.6B CUDA FP16 cache 只为 9 个新对象追加 embedding，CPU fallback、network、model call 均为 0；
- current reviewed-label missing occurrence：`4 → 0`；
- registry 为 R38，binding policy v1.13，receipt v1.14，snapshot v1.4；
- receipt digest `3c3ff77a...`，snapshot digest `2e52d235...`。

promotion P1 因引用不存在的 loader 在任何 current 输出生成前失败，digest `0d28d20b...`；P2
移除错误 import、保留 predecessor schema 的精确字段集合并以 fresh identity 成功。P1 仍是失败，
不能追认为 P2。

## 4. current 消费与三案泛化

DELL R38 R9 canary attempt
`dell-r38-reviewed-public-source-sync-zero-call-r9-20260824T211209Z`，public digest
`f05731a7...`：12/12 requests、两轮 runtime、15 Evidence、17 NumericFacts、9 gaps、18 feedback、
2 plan deltas、2 graph hypotheses；CUDA FP16，0 promotion/network/model/paid call。它证明 source
authority 可以进入 current consumer；该 bounded workpaper 未选择新增网页本身，不等于同步失败。

三案 R3 回执 digest `812b1a10...`：DELL `55/14`、MU `14/15`、NVDA `25/13`，每案 12/12
control gates。readiness 仍为 DELL `blocked_by_evidence_admission`、MU/NVDA
`blocked_by_candidate_coverage`；补源动作仍为 DELL `12+4`、MU `17+3`、NVDA `14+3`，三案
public-information-gap authority 都是 0。

## 5. 最终工程门与边界

fresh 全库测试 `1282 passed, 2 skipped, 2 warnings`；compileall、变更 Python pyflakes、active
baseline `213/8/5/28/0`、changed JSON 与 Project OS JSONL、8,041-file secret scan／0、diff check
全部通过。

这关闭的是 Pack→source/object/index/runtime 的已审阅公共源同步缺陷，不是完整外源梯子或 S1
资格。4-bit 4B 在 8GB 上 full-offload 已证明；因 NVDA embedding 和 reranker 质量回退未晋升，
不是 VRAM block。DELL 更广命题与 MU/NVDA 外源梯子仍须按 action ledger 执行，不能声明“能补的
源全补完”。
