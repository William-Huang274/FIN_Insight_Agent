# FIN 0.1.3 S3 片段上下文与“分析／交卷”分离实验

日期：2026-08-16

状态：`zero_call_pass / single_thesis_live_contract_and_L1_pass / two_hypotheses_qualified / owner_review_complete / successor_continuation_authorized`

## 为什么做这一轮

R3 已把完整 Judgment 拆成 thesis、mechanism、counterargument 三段，但 thesis 调用仍携带整份单元 Evidence、全部 NumericFact、全部关系、三个 gap、Skill、Graph 与读工具历史。模型可见 prompt 仍为 8,448 tokens，DeepSeek 把 8,000 个输出 token 全部用于 reasoning，最后没有可见文字或 Tool Call。

这说明“缩小交卷表格”还不够。最早责任层是 S3 的模型可见上下文和节点职责：分析一个片段与把结论装进严格合同不应继续由同一个高推理 Tool Call 同时完成。

## 本轮只测试两个假设

1. **片段专属上下文**：系统从当前片段所有合法 ClaimRelation 自动求并集，只给模型这些关系可能使用的 Evidence、NumericRelation、NumericFact、定性事实与 gap。系统保留所有合法选项，不替模型选择答案。
2. **分析与交卷分离**：第一调用使用 `high / 8000` 形成可见、受控的分析草案；第二调用使用 `low / 2000`，只把草案中有当前权威支持的内容映射为唯一 thesis Tool Call。草案是模型数据，不能直接晋升为 Evidence、Judgment 或报告。

没有改协议，没有增加 token ceiling，没有进入动态检索，没有运行 mechanism／counterargument，也没有生成报告。

## 零调用结果

DELL thesis 当前只有两个合法方向：管理层产品盈利目标，以及不分配单一产品利润的多因素背景。因此投影后只保留：

- 2 个 ClaimRelation 选项；
- 2 份 reviewed Evidence；
- 1 条 source-bound qualitative fact；
- 0 个 NumericFact、0 个 NumericRelation、0 个 typed gap；
- 现有 6 条 value-capture 方法边界与 1 条被所选 Evidence 约束的 Graph edge。

旧 R3 thesis 的消息正文为 23,852 chars；新分析消息为 8,028 chars，减少 66.34%；带参考草案的新交卷消息为 8,146 chars，减少 65.85%。最终 thesis Tool Schema 仍为 3,570 chars，没有通过删字段来“作弊”。

定向测试 `47 passed`，全仓 `326 passed`；Python compileall、active baseline `127 Python / 8 frontend / 10 Runtime resources / 0 failure` 与 `6,612 files / 0 finding` secret scan 均通过。两个独立 Python 进程得到相同 research/context/messages/tool digest。DELL 自然合同、MU/NVDA 合成身份迁移、跨案例引用、缺失权威、错误前序片段、fake 分析→交卷均通过或按预期 fail closed。模型、网络、Provider、外源、embedding、retry、fallback 调用均为 0。

## 仍未证明

这轮只证明结构值得进行一次自然测试。它尚未证明：

- DeepSeek 能在高推理分析调用中交出可见草案；
- 低推理提交调用能形成唯一、合法的 thesis Tool Call；
- thesis 的金融 L1 与内容质量改善；
- 三片段完整 Judgment、fixed-Pack Layer One、动态 Agentic Research、五单元或 S3 通过。

下一门仅允许在 clean/synced 提交上签发一个 DELL value_capture thesis canary，预算为 `2 model calls / 1 accepted tool call / 0 retry / 0 fallback`。任何一步 length、空输出、合同失败或新的实质内容问题都立即停止，不自动进入第二次 live。

权威处置为 `configs/research/evals/fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_fragment_analysis_submission_disposition_v1_0.json`，零调用结果为 `configs/research/evals/fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_fragment_analysis_submission_zero_call_result_v1_0.json`。

## Single-thesis exact-live 结果

实现以 clean/synced commit `c5d303a5...` 推送。GitHub HTTPS 首次因本机 DNS 指向不可达边缘 IP 而失败；只对该次 Git 命令临时指定可达 GitHub 官方 IP 后成功，没有修改 remote、系统 DNS 或持久代理。fresh authority 的 18 份输入、输出 identity、HEAD/upstream、唯一未追踪 authority 和凭据存在性随后通过。

唯一 FAS-R1 自然运行完成：

1. 分析调用使用 `high / 8000`，prompt=`2,570`、completion=`6,995`、reasoning=`6,514`，`finish_reason=stop`，形成 940 字可见草案；
2. 提交调用使用 `low / 2000`，prompt=`4,309`、completion=`1,944`、reasoning=`1,434`，`finish_reason=tool_calls`，只返回 1 个 `submit_research_thesis`；
3. 本地 fragment contract 接受该 Tool Call，0 retry、0 fallback、0 EvidenceRequest、0 外源、0 embedding、0 protocol switch、0 publication；
4. 分析草案保留在私有 capture，只用于审计和后续提交输入，没有被提升为 Evidence、Judgment 或报告。

最终 thesis 选择 `CR::DELL::PRODUCT_TARGET`：只表述管理层称 AI 服务器产品盈利符合所选目标，明确该口径未经独立审计，也没有把产品增长归因成 ISG／公司利润。Evidence、QF、Method 与 Graph refs 均在当前单元范围内；最终 atom 没有自由精确数字，也没有把 gap 或 Graph 当成事实。因此单 thesis 的 L1 通过，并相对旧 R2 的 AI 利润归因有实质改善。

仍有两个非 L1 finding：`无产品级...桥` 最好收敛为“当前 Evidence Pack 尚未建立...”，避免读成普遍不存在；模型已经选择 QF，但又在 prose 中重复“中个位数”定性带，完整 renderer 后续应避免模型表面和确定性表面重复。它们不应触发自动重跑。

本轮只资格化了这两个结构假设在一个 thesis 上的效果，没有运行 mechanism、counterargument／WWC，也没有编译完整 Judgment。fixed-Pack Layer One、动态 Research Truth Spine、五单元和 S3 仍未通过。内容评估见 `configs/research/evals/fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_fragment_analysis_submission_chat_content_assessment_v1_0.json`。本段记录的是 FAS-R1 终止时的权限边界；Owner 已在后续审阅中授权先零调用扩展其余片段，再执行完整 fixed-Pack 新 attempt。后续权限以 `027_continuous_execution_and_heterogeneous_generalization_evaluation_governance.md` 为准。

事后治理复证为定向 `54 passed`、全仓 `326 passed`、Python compileall、active baseline `127 Python / 8 frontend / 10 Runtime resources / 0 failure` 与 secret scan `6,615 files / 0 finding`。公开 result、authority 和独立 assessment 可提交；包含完整模型草案的 private capture 继续留在受限本地目录，不进入 Git。
