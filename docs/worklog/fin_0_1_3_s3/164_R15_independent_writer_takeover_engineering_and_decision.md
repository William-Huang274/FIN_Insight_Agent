# R15 独立 Writer 接管工程门与零 Provider 决策

更新时间：2026-08-24

## 结论

R14 已保持 immutable terminal，DeepSeek Writer successor 继续停止。依据用户在当前任务中的明确授权，R15 仅建立一个由当前 Codex 负责的本地 Writer 接管；它不是新模型节点，不调用 Provider，不新增证据，也不把 R14 改写为成功。

R15 接管器已在工程提交 `d93e4c8ff85129d4efefe665ac309754a671f11d` 实现并推送。报告正文编辑位于 Git 忽略的 private manifest，公开 decision 只绑定其 SHA／digest、允许变更路径、引用变更后的精确值和硬边界，避免把未验收报告正文当作产品发布。

## R14 语义与引用审计

R14 内层报告不能只做双层 JSON 拆包。接管前确认的四项硬引用问题及处置如下：

- `sections[3].clauses[0]`：Cash clause 错带 Operating claim `WPCLAIM::DA7641...` 及其 `EV::734A...`／`NUM::C0D6...`。Cash catalog 中 `WPCLAIM::E4FC...` 对同一“经营现金流高于净利润、公司级覆盖为正、不可归因 AI”判断有直接授权，因此执行同义 claim substitution，并移除跨域 Evidence／NUM；
- `sections[3].clauses[1]`：正文不需要渲染经营现金流金额，`NUM::D2AE...` 也不在所选营运资金 proxy claims 的 authority scope 中，因此移除；
- `what_would_change[0]`：Demand 的 `WPCLAIM::BD2D...` 已完整覆盖 cohort、取消、交付与 backlog aging，Operating claim `WPCLAIM::32A5...` 为冗余跨 Agent 引用，因此移除；
- `what_would_change[2]`：`WPCLAIM::0A332...` 在 catalog 不存在；catalog 中 `WPCLAIM::A332...` 的原文正是“AI server price／unit／mix 不可重建”，故登记为可证明的首字符误写并更正，而不是新增研究结论。

另有两条在普通 report audit 中不会出现、但会由 R10 protection 捕获的同季信号问题：`sections[0].clauses[0]` 和 `[2]` 选择了 cohort-protected claim，却未在本 clause 明示 `parallel／cohort` 边界。R15 显式补回“订单、收入和 backlog 是并列信号，无 cohort linkage”，没有添加业务事实。

## 质量处置

- 三处 spelled-numeric／ordinal surface 改写后 finding 为 0；
- executive thesis 从超建议密度压至建议上限以内，confidence 压至建议上限以内；
- confidence、executive、what-would-change 和重复 section 不再承担 gap inventory；
- 原 10 行 remaining-gap register 按“现金归因、需求与供给耐久性、产品经济分解、研究阈值”合并为 4 行；10 个 gap ref、对应 Agent／claim／Evidence／authority 集合逐项保持，未删除信息边界。

## 工程与 dry validation

- 新增 `scripts/research/run_s3_current_dynamic_writer_independent_takeover.py` 和 3 项专用测试；
- 接管器验证 R14 response／assessment／authority、R10 catalog／protection、private manifest 和实现 SHA；任何 binding、允许路径、引用、topology、surface、hard、quality 或条件保护漂移都会在写结果前 fail closed；
- dry validation：candidate draft digest=`dcb6e6d0...a49d`，contract finding receipt=`57971ee7...dc2b`，rendered report digest=`6d15b3d2...1a10`；surface／hard／quality=`0／0／0`，R10 两条 conditional protection 通过；
- 变更收据证明：0 新 Evidence／authority／gap ID，remaining-gap ref union 与 semantic-authority inventory 均保持；
- 专用＋Writer 定向 `19 passed`；全仓 `1177 passed, 2 existing SWIG warnings`；compileall、精确 pyflakes、active baseline=`212／8／5／28／0`、977 configs JSON、8 Project OS JSONL／1,106 行、secret scan=`7,846／0`、diff check 均通过。

## 决策与边界

公开 decision 为 `...R10_protected_writer_independent_takeover_scope_decision_v1_0.json`，SHA=`07647bdb...d08c`、decision digest=`66d71ebf...a803`；private manifest SHA=`74fe48b3...8fa1`、digest=`9bdebd27...3d12`。预算严格为 model／Provider／network／new Evidence／promotion=`0／0／0／0／0`。

下一步只能在该 decision 已提交、仓库 clean／synced 后物化一次 R15 private candidate 和 public receipt。即使物化成功，也只能说明本地合同和 R10 protection 通过；当前 Codex 既是作者，不能把后续自检称为独立 post-Writer 或 qualified-human。S3、产品验收、publication 和 release 继续为 false。
