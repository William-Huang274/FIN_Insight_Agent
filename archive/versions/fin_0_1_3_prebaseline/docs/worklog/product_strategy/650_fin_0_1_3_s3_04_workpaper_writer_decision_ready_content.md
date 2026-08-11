# 650 — FIN 0.1.3 S3-04 Workpaper/Writer decision-ready 内容

日期：2026-08-06

## 问题与判断

S3-02/03 已有公司专属 Claim、可观测 WWC 和跨 Cell 综合，但旧交付仍容易退化成 Claim/atom 的排版投影。入口审计同时确认，上游自然选择仅为 `4/9`，另外 `5/9` 仍是 fixture，29 个动态 Cell 尚无 Claim。因此 S3-04 不能诚实生成“正式研究报告”，也不能用通用文案把未研究维度填满。

本轮采用两层边界：一是把已有判断编译成真正回答“结论、为什么、反方、缺什么、什么会改变”的 Workpaper/Writer 内容；二是把无 Claim 的研究维度明确显示为 coverage gap。fixture-mixed 内容只能作为工程预览和 deterministic baseline，不能晋升产品交付。

## 完成内容

- 新增 `s3_workpaper_writer_content_program.py`，消费 S3-02 Claim Card 和 S3-03 Lead synthesis，构建每案 8 个研究 lens。
- DELL/MU/NVDA 合计 `24` 个 lens：`21` 个 bounded judgment、`3` 个 explicit research gap。
- 每个 lens 均有 conclusion、why、opposing view、missing evidence、what-would-change；同时绑定 Claim、Numeric、dependency/conflict/gap 和 lineage。
- 12 个精确 Numeric 只由本地确定性 renderer 输出，保留披露日和口径边界。
- Writer packet 为 no-source：raw retrieval rows=`0`，Writer 只能消费审阅后的 Claim/Synthesis/section digest。
- 29 个 planned/no-claim Cell 只作为未完成研究问题，不得成为 finding。
- 三案 authority 均为 `fixture_mixed_engineering_only`，`display_ready=false`、`product_candidate=false`。
- 增加跨案 Claim、通用句、数字篡改、planned-cell 晋升和 fixture 晋升 mutation，全部 fail closed。

## 资产

- `src/sec_agent/s3_workpaper_writer_content_program.py`
- `configs/runtime/fin_ia_0_1_3_repair_closeout_s3_workpaper_writer_content_policy_v1_0.json`
- `scripts/releases/build_fin_ia_0_1_3_s3_04_workpaper_writer_decision_ready_content.py`
- `configs/releases/fin_ia_0_1_3_repair_closeout_s3_04_workpaper_writer_decision_ready_content_v1_0.json`
- `configs/releases/fin_ia_0_1_3_repair_closeout_s3_04_active_test_suite_successor_v1_0.json`
- `tests/contract/test_fin_0_1_3_repair_closeout_s3_04_workpaper_writer_decision_ready_content.py`

## 验证

- focused：`7 passed`。
- current canonical successor：`226 passed / 1 historical assertion deselected`。
- model/provider/network/source/business run：`0/0/0/0/0`。

## 边界与下一步

S3-04 达到 `engineering_pass`，不等于 Writer natural output、八维研究质量或产品通过。Provider-visible Writer input 还没有激活，因此本轮没有 canary；这也避免对 fixture-mixed 输入花费一次不能形成业务证明的模型调用。

下一项为 `013-S3-05`：把八维 Rubric 编译进 deterministic Verifier、paired packet 和 qualified-human decision contract。只有 S3-05 deterministic gate 通过后，才评估唯一正式 full-chain；正式 candidate 必须以 all-natural Claim/Lead/Writer 结果重建本合同并逐案评分。
