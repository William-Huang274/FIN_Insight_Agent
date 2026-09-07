# S1 工作记录 085：DELL 03B R2 fresh audit failure 与 R3 要求

日期：2026-08-25

状态：`R2 immutable / fresh audit FAIL / 03B acceptance withdrawn / same-stage R3 required`

## 1. 结论先行

作者分离、无上下文继承、只读的 reviewer 审计 immutable commit
`2a604156777a027d06a15c3e379632d945c70703`，结论为 **FAIL**。本轮 03B 新增
`P0/P1/P2/P3=1/1/1/0`；连同仍未关闭的 R17 研报质量项，当前 open 合计为
`1/2/3/1`。Reviewer 不是 qualified human，02B decision 仍为 `0/16`。

R2 的文件、trace、身份等式和 exact public projection 保持不可变；但 `03B=True`、本地六项目标均缺、
`03C required=6`、`4B eligible=0`、`reranker eligible=0` 全部撤回。03C、4B、reranker、Evidence
promotion、gap closure、S2 和新报告继续暂停。

## 2. 工程 finding：execution seal 不 fail closed

编译器只要求 request count=5、embedding batch≤1、少数调用为 0；未强制 batch=1、原始 request list
恰为 5 且唯一、每 request 96/16、rank 精确排列，也未验证 provider、external、4B、reranker、retry、
mutation、promotion 和 gap closure。重复 request 会被 dict 静默覆盖，若干 public zero 还是硬编码值。

只读内存攻击实际接受了：每 request 一个 seed/零 final、零 fresh batch、多个越权字段非零、重复第六请求。
Runner 同时允许同一 attempt 改写到任意新 output path，未冻结 exact branch/commit/tree；private/public 同径
还会先留下 private 半成品。故保存 trace 的 96/16 是可复算事实，但不是 validator 的 fail-closed 保证。

## 3. 研究 finding：对象级 AND 造成真实假阴性

ASP 在 current R38 已有两组 reviewed、同源分片的 bounded configuration-price package：

1. Principled Technologies：quote `$757,231` 与两台 PowerEdge XE9680 配置分别位于 object 34170/34172；
2. Mississippi procurement：`$2,278,577.28`、四系统及 bundle 服务与 XE9680 配置分别位于
   object 34174/34189。

它们可支持“有限配置／bundle 价格观察”，不能无条件除以台数当 Dell company-wide hardware ASP。R2 因
所有语义组必须同处一个 object 且 ASP ticker 限于 DELL/MSFT，把两个 package 错写为 corpus absent；相关
对象已在 final rank 14/15/16，故 ASP 的 reranker usefulness 至少必须重算，不能继续写 0。

Supplier→Dell 也已有 Dell/NVIDIA official partnership、delivery 与 availability：objects 34180、34184、
34191、34197；34197 在 supplier request final rank=2。现合同漏掉 `partnering to deliver`、
`partnered for decades`、`shipping at scale`。完整 relationship/delivery 不应再补源；capacity/allocation
read-through 仍是 residual。

Capacity release 已有 product availability/shipping 候选，但 upstream capacity→Dell allocation 未证明；
yield、HBM→Dell bridge、Dell company-period physical server units 的 bounded absence 仍较可信，但都不是
public-information boundary。

## 4. 语义 precision 与 coverage finding

`_term_hit` 使用裸子串，TSM transcript 的 speaker `Wendell` 会命中 `Dell`，再与泛化
`collaboration` 合成 supplier→Dell complete。R3 不能靠整页或整份 filing 盲拼；必须使用 token/entity
boundary、关系主客体／方向、同一 canonical source 内的 bounded adjacent-slice package。

source ID 与 compiled lineage 集合相等也不等于 source text 完整进入对象。source record 1887 含 Dell 美国
工厂一周可 ship 数千 NVIDIA Blackwell GPU 的句子，但对应 compiled objects 34190–34198 不含该句。R3 必须
增加 material source→object semantic coverage 门，不能把 identity equality 当语义 coverage。

## 5. 六 target 的合法下一步

| target | R2 后审计状态 | 后续路线 |
|---|---|---|
| ASP | 本地 bounded packages 已存在；company-wide realized ASP 仍缺 | 先 R3 同源 package 重编与 reranker 重算；不做全量 03C |
| capacity release | availability/shipping 已存在；allocation/timetable 未闭合 | 只保留 residual 03C，4B/reranker 待重算 |
| capacity utilization/yield | 当前完整事实缺失较可信 | 可做 bounded 03C，不得声明公开信息边界 |
| HBM supply | HBM capacity/shortage 有上下文，无 Dell bridge | 可做 residual 03C，先修 ticker/role 语义 |
| supplier→Dell | official relationship/delivery 已存在 | 不为已证明部分补源；只查 allocation/capacity residual |
| units | Dell 仅定性 shipments；GPU 数／采购四系统都不是公司出货量 | 可做 bounded 03C，不得错升格 |

## 6. R17 研报质量仍未关闭

R17 仍只有内部 `EV::/GAP::/WPCLAIM::`，没有读者可核验的逐 claim 标题、issuer、日期／期间、
page/section、URL、角色和 source appendix。14 Pack／9 dynamic／4 Writer／10 refs 只是 crosswalk，Pack
仍为 55 Evidence／14 gaps／0 closed／3 narrowed，不能把路由数写成 gap closure。WWC 多数没有
metric/event/window/threshold/owner/source route，top-level 与 section 还有重复和事实密度问题。

未来新报告必须在 L1 financial truth 与 L2 evidence authority 后生成 reader-facing citation appendix，
明确 configuration bundle 的内容、单位和不可推断 company-wide ASP 的边界，并让 author-separated reviewer
按正式 8D 门复核；最后的 16 项 Evidence decision 和产品验收仍属于 qualified human。

## 7. R3 验收合同

R3 必须是非覆盖的新 policy/result/attempt，至少满足：

1. 冻结 exact branch、implementation commit/tree、attempt 和 canonical private/public pair；输出双文件原子、
   exclusive-create，并有 attempt consumption receipt；
2. 绑定 raw execution SHA/digest；五个唯一 request、一个 fresh batch、全部调用／mutation 权限字段精确为冻结值；
3. 每 request 精确 96 union、16 final、ID 唯一、rank 为完整无重复排列，所有 summary 从验证输入派生；
4. `Wendell != Dell`，关系有主体／客体／方向，识别 `partnering to deliver` 等 morphology；
5. 仅在同一 canonical source 的 bounded adjacent slices 内聚合 role package，禁止 whole-filing blind concat；
6. configuration bundle 与 company ASP 分离，availability 与 upstream allocation 分离；
7. A14 SRAM yield 不得冒充 Dell/HBM supply yield，100,000 GPUs 不得冒充 Dell server units；
8. source material text 未进入 compiled object 时 coverage gate fail closed；
9. 重算 corpus/union/final、useful@10、4B/reranker/03C 分流；另一名 fresh reviewer 通过前不进入下一阶段。

审计收据：`configs/audits/
fin_ia_0_1_3_commit_2a604156_dell_03b_r2_fresh_audit_fail_v1_0.json`。
