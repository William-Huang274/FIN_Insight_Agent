# R10-bound protected Writer 零调用门

## 结论

R10 的六份 workpaper 与 Lead decision 已被编译为一份新的、只读的 protected Writer 输入。零调用 proof 已完整跑通真实编译器、Tool Schema、正向假提交、确定性渲染和负向变异；本阶段模型／Provider／网络／付费调用均为 0。它只建立 Writer live 的工程准入候选，不生成最终报告，也不代表 S3、产品、发布或 release 通过。

## R10 输入与报告权限

- R10 authority／public／private／独立 assessment 均按 SHA 和 canonical digest 绑定；六份最终 workpaper 逐 digest 复用。
- Demand 使用 R10 repair context；Operating、Value、Cash、Counterevidence 使用 R9 保留的 repair context。Supply 的 R5 authority view 与 R10 逐字节复用 workpaper 一致，但原完整 rebound context 未单独持久化，因此只形成显式的 report-compiler projection receipt，不冒充新的模型上下文。
- 基础报告目录为 56 条 Writer claim、38 条 presentation authority、10 个 typed gap。两个研究估算保留 lineage，但 `numeric_fact_authority=false`，不得进入确定性输出。
- 七个既有 source-bound numeric decision 和一个 temporal decision 只重新绑定到 R10 claim；没有新增 Evidence、来源 span、NumericFact 或检索。
- 当前动态 operand-only relation 由本地用同 ticker／metric／unit 的 typed operands 计算百分比或百分点变化；相同 NUM 在不同角色里的 formula input id 只合并内部 lineage，任何金融语义字段差异仍 fail closed。

## material 与 L3 保护

Writer 可见保护合同强制：

1. 同时使用订单与收入 authority 时，必须写成同季并列信号并保留 cohort 边界，不能写成同一批订单已转化；
2. Cash 的营运资金变化只能写成资产负债表 proxy，并保留 `GAP::EF4839B4BF55ADD0`；禁止精确 cash absorption 或 AI 归因；
3. 费用杠杆只能条件性表达或省略，禁止“算术必然／必然收窄”；
4. NVDA／MU 两个未归一化绝对库存 NUM 及对应 claim 已从 Writer Tool catalog 物理移除；
5. 所有 model-owned topic、heading 和 clause 均禁止数字或序数的英文／中文拼写绕过；精确数字和日期只能来自 typed deterministic presentation authority；
6. issuer ownership、公司／产品、pull-forward、typed gap 与 `not_inferable` 边界继续保留。

Harness 只做权限、保护和确定性渲染，不代替 Writer 写业务结论。任何本地 contract pass 的报告仍必须单独做 post-Writer L1／L2 与八维质量复评。

## 零调用证据

- source-bound review：`configs/research/fin_ia_0_1_3_s2_dell_current_dynamic_multi_agent_R10_source_bound_numeric_review_v1_0.json`；digest=`2b6a5608...50ff`。
- source-bound program：`configs/research/fin_ia_0_1_3_s2_dell_current_dynamic_multi_agent_R10_source_bound_numeric_program_v1_0.json`；digest=`b0a653cd...53f3`。
- Writer authority catalog：`configs/research/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_R10_protected_writer_authority_catalog_v1_0.json`；digest=`a65c63dd...e765`。
- protection contract：`configs/research/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_R10_writer_protection_contract_v1_0.json`；digest=`e81473c7...7b62`。
- zero-call result：`configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_R10_protected_writer_zero_call_result_v1_0.json`；SHA=`81dc5f5c...e1a1`，digest=`30be0605...e569`。
- scope decision：`configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_R10_protected_writer_scope_decision_v1_0.json`；SHA=`e24a4937...b3a2`，decision digest=`61bcaeef...7ecd`。

17 项零调用检查全部通过，包括 R10／R9／R5 lineage、Supply projection、estimate 不获输出权、既有 source span-only、库存 authority 移除、protection model-visible、正向假 Tool Call／render，以及 cohort、cash proxy、算术必然、数字字符和数字拼写五类负向变异。

## 未来 live 的严格上限

- 1 次 thinking=max Writer analysis，最大输出 16,000 tokens；length／空内容立即终止；
- 最多 2 次 non-thinking strict submission，每次最大 12,000 tokens；第二次只允许接收第一次本地合同的精确反馈；
- 合计最多 3 次模型／传输调用，0 retry／fallback；
- 0 upstream Agent、S1/S2、retrieval、外部来源、Candidate promotion 和产品指针变更；
- 任一失败都必须以全新 public／private terminal 证据保留，当前 authority 和输出 identity 立即消费；后继必须重新审计并使用新 proof／authority。

live runner 还要求：工程提交 clean／synced；repository-aware Project OS preflight；随后只允许一个仅包含 preflight＋authority 的提交。执行时同时验证工程提交是 authority 提交的唯一父前沿、实现 Git blob SHA、决策／输入摘要和 fresh outputs，避免把工程 commit 与 authority commit 误当成同一 SHA。

## 完整工程门

- protected Writer／Project OS／历史报告合同综合定向：`108 passed`；
- 全仓：`1169 passed, 2 warnings`，仅两条既有 SWIG deprecation warning；
- `compileall`、Git 精确变更集 `pyflakes` 与 `git diff --check` 通过；
- active baseline：`212 Python／8 frontend／5 detectors／28 Runtime／0 forbidden`；
- 957 份 configs JSON 与 8 份 Project OS JSONL／1,079 行全部可解析；
- repository secret scan：7,820 files／0 findings。

直接对整个历史仓库运行 pyflakes 仍会报告一批不属于本次变更的既有旧告警；本轮未静默扩大范围修理历史文件。当前 gate 使用与既有交付一致的 Git 精确变更集静态检查，结果为 0，并由全仓 pytest、compileall 和 active baseline 共同覆盖本次实现。

## 当前门

`RC-S3-088` 现可显式允许唯一 live scope `one_capture_bound_R10_protected_writer_analysis_and_submission`，但当前尚未签发或执行 Writer authority。下一步必须先做 exact-file staging、commit／push 与 clean／synced 复验；随后 repository-aware Project OS preflight 才能生成 fresh preflight＋authority。该二文件 authority-only 提交／推送并再次复验后，才允许一次 live。最终报告的独立 L1／L2、八维质量、S3、产品、publication 与 release 仍全部为 false。
