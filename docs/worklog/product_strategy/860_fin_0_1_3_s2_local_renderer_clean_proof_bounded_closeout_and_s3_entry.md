# 860 — FIN 0.1.3 S2 local renderer clean proof、bounded closeout 与 S3 入口

日期：2026-08-11

状态：双 clean proof 通过；S2 bounded capability closeout；只放行 S3 零调用入口，不放行 formal live

## Clean proof 实际发生了什么

provider-neutral renderer 已在 clean/synced commit `3b5e584ffa6d948ec24102beb5dee5b87d658de5` 推送。两个独立 `git archive` 的 SHA-256 均为 `671e2282...46ea`，分别用 `PYTHONHASHSEED=101/202` 和 fresh Python process 运行。

第一份 archive 首次编译 material 时以 `changed_input_corrected_pack_artifact_drift` 停止。原因不是代码或模型漂移：Git archive 按设计不包含 `data/workbench_private`，而 canary material 需要 corrected／historical 两份 digest-bound Evidence Pack。处置没有放宽 hash gate，也没有修改源码；只把既有 `8210887f...9387`、`da86bdf8...2e4b` Pack 和 capture=`7cfd3c82...b9b6` 作为 proof input 注入两个 worker。随后各自 `12 passed`，共同 proof digest=`ba5e4ecf...004c1`，validation=`35a06db4...2036`，rendered delivery=`f75256e3...ebe5`，输出逐字节一致。临时 worker 已删除。

全过程新增 Provider／model／network／source／retry／fallback=`0/0/0/0/0/0`。历史 exact-live terminal 保持 failed，admission 保持 consumed，没有第二次 canary，也没有业务 Artifact 晋升。

## 为什么 S2 可以 bounded closeout

- changed-input DELL 13 节点已证明新资料转化成了更好的需求、利润、供给、竞争和反方判断，而不是只增加引用；
- selected-Evidence numeric co-compilation 已从同一 Evidence 事务产生 NumericFact／presentation program，并有先前双 clean proof；
- 最小自然 canary 正确选择 issuer Evidence、四个 NUM、HPE read-through 和 pull-forward 边界；唯一 formal failure 是无经济意义的英语词形 exact-match；
- 本地 renderer 保留模型全部非受保护分析文字，同时对 negation、反向关系、错实体、错期间、错单位、错数值和额外未绑定 count 继续 fail closed。

因此 RC-P36-170 的 S2 数字控制面可以关闭，不需要为了证明同一语义再花一次模型调用。但关闭只授予 `bounded_judgment_atom_and_evidence_selection`：模型可做判断、机制、反方、边界和 WWC 原子；Harness 继续拥有数字事实、公式、身份、期间、lineage、渲染和晋升。三案 raw Experiment A 的质量失败仍保留，unrestricted full-report autonomy=false。

## S3 接手什么

RC-P36-172 的弱 WWC、机制桥、重复表达、决策密度和完整研报质量全部留给 S3。下一项为 `S3_DYNAMIC_RESEARCH_PLANNER_EVIDENCE_REQUEST_LOOP_AND_RESEARCH_CONTENT_QUALITY_ENTRY_AUDIT_ZERO_CALL`，先设计动态 DecisionSurface、EvidenceRequest／targeted repair、工具预算、隐藏八维评分和 same-input comparison。当前不授权 DeepSeek 或工具 live；任何正式执行仍需 fresh proof、admission 与 exact-once authority。

决策后的 Project OS 复核进一步确认，正式 `FIN_0_1_3_S3_Experiment_B_end_to_end_agentic_research` 仍为 `blocked / 7`：RC-P36-151／152／154／155 看起来是后续 S1 成功后未关闭的历史投影，RC-P36-157／165 是仍真实存在的外源覆盖和残余资料边界，RC-P36-172 是 S3 本身的内容质量任务。下一项必须先注册只允许零调用入口审计的新 scope，逐条核对“已解决但账本陈旧”与“真实产品阻断”；不能为了进入 S3 而一次性把 7 条都改成 closed。

机器证明：

- `configs/releases/fin_ia_0_1_3_s2_provider_neutral_numeric_presentation_local_renderer_clean_independent_proof_v1_0.json`，digest=`df6552e8...41c8`；
- `configs/releases/fin_ia_0_1_3_s2_bounded_closeout_autonomy_grant_and_s3_entry_decision_v1_0.json`，digest=`2ef10602...e132`。

收尾回归覆盖 15 个 S2 numeric／canary／closeout 合同文件，共 `110 passed`；S2 scoped Project OS preflight=`pass / 0 blocker`，正式 S3 scope 的 `blocked / 7` 保持可见。
