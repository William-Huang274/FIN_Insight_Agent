# S3/205：HPE 完整链路与跨用例根因审计

日期：2026-09-09。审计代码基线：f4a94e65。性质：历史实证、当前代码只读检查、成熟方案调研；不是修复完成报告。本轮付费模型调用为 0，未改变运行服务、原始失败、报告或产品版本。

## 结论与证据强度

目前最有证据支持的主因是：**长研究任务的增量交付与失败接续没有在专家、产物和父图之间形成完整闭环。** 专家要在不断增长的历史中完成研究、引用绑定、计算凭证和完整结构化提交；失败后的内容虽然保存，主流程却不能充分沿原任务、原候选和未决问题继续。结果既可能反复提交/重建任务，也可能在保留一份底稿后过早收缩研究范围。

这是对多项可观察机制的综合诊断，不是已经通过移除某因素的受控试验证明的唯一原因。财务语义错误仍是独立质量问题；不能声称只改运行框架就能保证判断正确。

必须纠正此前的重心：**HPE 前四次完整尝试还没有进入审查与写作，98.7% 的已知 tokens 已耗在研究专家阶段。** 因而“审查层太多”不是最初最大开销的解释。a5 的长审查、上下文重复与异常取消是后续第二层故障。

## 1. 按实际阶段还原 HPE

任务是 HPE（非 HP Inc.）FY2025/FY2024 收入、利润与现金转化，含 Juniper 并购、合并口径、融资、商誉减值、反证和边界；已有官方年报。不是寻找一个财务数值，也不是泛行业或 Dell 研究。

| 尝试 | 实际模型调用 | 已知 tokens | 实际卡点 |
|---|---:|---:|---|
| a1 | 48 | 2,194,134 | 研究专家失败，无完整报告 |
| a2 | 51 | 2,140,450 | 两个专家各 24 调用，引用/类型与提交未收敛 |
| a3 | 49 | 1,918,418 | 研究阶段失败；另确认新工具结果尚未被模型读到就被上下文处理清除 |
| a4 | 48 | 2,465,574 | 一份正式底稿、一份失败候选，其余研究未完成 |
| a5 同窗口接续 | 49 | 969,171 | 范围收缩后进入审查；counter 达上限异常取消另一审查，无完整报告 |

前四次合计 196 调用、8,718,576 tokens；其中专家 185 调用、8,607,649 tokens，占 98.7277%。五次合计 245 调用、9,687,747 已知 tokens；a5 含 1 次取消且用量未知。历史价格场景估算合计 ¥10.4609908，非账单，未包含后续局部作者/审查资格测试，不能与整个 205 计数混用。

### 研究阶段：已读资料、已有候选，仍不能稳定交付

- `dell_specialist_agentic_graph.py` 的提交需要上下文摘要、理由、状态、长篇叙述、多条 claim、类型、来源和计算关联。严格来源权限是必要的，但机械标识与完整对象构造让模型承担了额外协议工作。
- a2 出现 CHUNK/PASSAGE、numeric_fact 权威类型混用；a3 有新工具内容丢失；a4 有引文空白/非连续片段问题。这些不是同一种错误，但都在“读到资料→形成可接受产物”的边界反复消耗。
- 保存的失败候选已有实质财务内容，不能视为没有研究结果；也不能因为有文字就视为可靠底稿。
- 历史 a3 新工具丢失回放为 18 请求/21 条未读工具内容；修后回放 49 请求/113 条新工具内容、0 丢失。此修复已有离线证据，不应继续当作当前未修故障。
- a4 引文回放从 9 个错误降到 1 个；剩余非连续引文仍应拒绝。不能用放松证据检查换取“跑完”。

### 接续边界：保存失败与恢复失败不是一回事

当前 `research_session.py:60` 的 `can_continue_remaining_research` 只允许 needs_attention、已有 case_papers、没有 case_review/report 的状态继续。对实际函数做零模型四态探测：没有正式底稿不能继续；有底稿且没有审查能继续；已有不完整审查后同样不能走这个入口。此为入口函数证据，不是全部恢复路径的真实集成验收。

`run_research` 续跑仅传 `completed_workpapers`；失败专家的 agent_state 虽保存在父 checkpoint，却不随之进入恢复请求。Lead 的 initialize 重新建立任务状态。`dell_lead_research_graph.py:292` 又按宽泛 branch 阻止重用已提交方向，即使该方向下还有原问题未回答。

a5 的公开交接理由明确提到不能继续已提交 Q1，拟将注记补引交下游核验；其未决项却仍包括 Juniper 并购注记、减值所属业务、非 GAAP/FCF 定义等原题核心依据。这不是“用户不需要”，也不是已经证明的信息边界。把其他方向笼统说成无关，再交审查，暴露的是**分支提交状态与问题覆盖状态混淆**。

新增 question_coverage 可检查用户原句、任务绑定和显式 unresolved，但结构检查不能证明所有重要要求都列齐或财务覆盖充分。最近 scoped revision 入口也只在隔离资格中运行，不能当作主产品的 failed-worker/review 恢复已经接通。

### 审查与写作：第二层故障与未测边界

a5 才真正暴露长审查重复读取、到限不能形成可继续交接、异常取消同批另一结果的问题。已有保存发现、同批坏参数隔离、局部实际差异复核等修复，应保留这些成果；但当前不完整 case_review 仍没有完善的正常产品恢复路径。

已有 convergence/责任作者反馈与报告 diff，不能再造另一套收敛引擎。当前差异范围资格没有普遍代替完整复核输入，且新角色实例需要重新读回依据。需要补的是原生流程中的产物、任务和恢复连接。

HPE 尚未走到完整报告写作/导出，不能据此把 Writer 或 PDF/Word 当成 HPE 主故障。已有候选还包含费用总额/同比增量混淆和减值归因过强等语义问题，需独立验证，工程成功不等于金融通过。

## 2. 其他用例是否存在同类机制

| 用例 | 观察到的实际表现 | 与 HPE 的关系 |
|---|---|---|
| MSFT 指定双方向 | 原完整运行 94 调用、4,113,228 tokens，后续图表修订另 4 调用/59,874 tokens；Q1、Q1_R2 均失败，Q1_R3 才提交，最后生成待审报告 | 同一方向失败后新建替代任务，交付/恢复成本同类；最终有报告，不是与 HPE 同样终态 |
| NVDA 旧失败研究 | 一次 14 调用、512,472 tokens 均在专家，未正式交付 | 有候选但来源/提交契约阻塞；旧跨公司入口沿用旧案例来源约束也是已修历史因素，不能直接归咎模型 |
| NVDA/MU 小题 | 旧 41 调用/506,744 tokens；focused 同题 9 调用/108,491 tokens，均待人工审阅 | 小题固定多层编排过重已有直接证据与单样本改善；不同于 HPE 前四次尚未进入审查 |
| Dell integrated 大题 | 148 调用/8,282,356 tokens，报告待审；研究 80 调用、Writer 16、ReportVerifier 25 | 大任务重复来源/写作核验也出现，说明开销不只 HPE；不能用有报告证明同等质量 |
| 普通问答、MSFT SQL | 分别 2 轮/2 调用/5,169 tokens；3 轮/7 调用/45,862 tokens，SQL 原始数值可重启接续 | 负向对照：通用短循环与持久化并非完全失效，问题集中在复杂研究协议与父子交接 |

这里比较的是公开开发用例，不是隐藏测试。历史模型、提示、数据与 runtime 版本不同，因此只能识别相同机制，不能做严格模型排名或宣称通用节费比例。重复历史字符比例不等于可删信息比例，缓存命中也不等于无需携带的内容。

## 3. 可以参考的现成办法

| 成熟组件/工程经验 | 本项目可采用的具体做法 | 判断及边界 |
|---|---|---|
| LangGraph persistence / interrupts（当前栈） | 同一原生任务/checkpoint 保留执行进度；明确恢复失败专家、未完成审查和缺项补研；成功产物只引用，不重建任务来绕预算 | 优先补现有适配。interrupt 节点恢复会从节点开头重执行，必须验证付费/副作用幂等边界，不能简单套 resume |
| Anthropic 实际 multi-agent research 工程 | 委托明确目标、输出、边界；复杂度决定分工；产物外置并传引用；按最终任务覆盖而非活动数量验收 | 有生产工程依据，适合指导整改；不证明财务正确率，也不直接照抄其调用预算 |
| Deep Agents context engineering / subagents | 工具大结果外置，给模型短引用与按需回读工具；子任务上下文隔离 | 可在现有 LangChain/LangGraph 专家内做受限对照；本轮未安装/接入，须验证版本、未读内容、期间/单位/操作数回读。不默认开启有损摘要 |
| Anthropic 工具设计经验 | 模型使用可理解的任务级来源句柄，宿主绑定真实 ID/digest/权限；精简输出，必要时展开详情 | 降低协议错误，保留 canonical 财务证据校验；不手工替模型补财务结论 |
| Hermes context engine / session retrieval | 作为相同研究单元的上下文 challenger，比较恢复质量、原文可达性和总费用 | 默认摘要不能当财务原始依据；此前丢操作数的 FIN 结果仍有效。暂不整栈替换，它不能自行修复 FIN 的覆盖/恢复判定 |

直接来源（本轮读取官方文档/官方仓库）：

- https://docs.langchain.com/oss/python/langgraph/persistence
- https://docs.langchain.com/oss/python/langgraph/interrupts
- https://www.anthropic.com/engineering/multi-agent-research-system
- https://www.anthropic.com/engineering/writing-tools-for-agents
- https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- https://docs.langchain.com/oss/python/deepagents/context-engineering
- https://docs.langchain.com/oss/python/deepagents/subagents
- https://hermes-agent.nousresearch.com/docs/developer-guide/context-compression-and-caching

专门投研开源项目 [LangAlpha](https://github.com/ginlix-ai/LangAlpha) 也采用持久工作区、产物文件、快速/深研究入口和 sandbox 工具，可作产品与集成参考。其 README 不能充当企业采纳率或财务质量验收证据，不建议为借鉴而搬入整套编排。

## 4. 下一实质切片应验证什么

不再从 HPE 整题付费重跑起步。先复用 HPE/MSFT 已保存响应，在既有原生图中验证一段完整的**候选保存→同任务恢复→只补未决项→明确提交或明确停止→父图接收**，同时覆盖已提交方向内仍缺问题、审查半途停止、坏工具参数与有效兄弟结果共存。

验收重点是：恢复前后原始依据与计算操作数可达；已成功工作不重做；不能改任务 ID 获得新额度；未解决事项不能被省略或冒充信息缺口；用户能看见部分成果及可继续位置。金融总额/增量、期间/单位、减值归属另作语义验收，不能靠 schema pass 代替。

该切片应接正常产品路径，不能只新增一个 qualification CLI。随后才对固定同一研究单元比较现有上下文、Deep Agents 外置/回读和 Hermes。必须固定题目、资料、必要输出和验收条件，分别统计输入/输出/cache、重读、重做、未知请求、覆盖与语义错误；本轮未授权为审计新增任何付费尝试。

## 5. 可追溯证据与本轮交付分类

- 只读汇总：`D:/temp/fin205-full-chain-diagnosis-a1/audit.json`；一次性脚本 `D:/temp/fin205-full-chain-audit.py`。读取历史指标和保存状态，调用当前入口 guard，无外部模型请求。
- 历史指标：`D:/temp/fin205-all-thread-metrics-a1/`、`fin205-hpe-auto-a1/metrics-a1.json`、`fin205-hpe-auto-a2/metrics-a1.json`、`fin205-hpe-a3-cost-a2.json`、`fin205-hpe-a4-cost.json`、`fin205-hpe-a5-cost-delta.json`。
- 实际状态：`D:/temp/fin205-hpe-auto-ui-a3/current-code-public-state.json`、`fin205-hpe-auto-ui-a4/native-state.json`、`fin205-hpe-auto-ui-a5/final-state.json`、`fin205-msft-selected-a2/final-snapshot.json`（后四项均相对 `D:/temp/`）。
- 既有修复证据：`D:/temp/fin205-hpe-a3-unseen-tool-batch-loss.json`、`fin205-hpe-a3-unseen-tool-batch-fixed.json`、`fin205-hpe-a4-quote-replay.json`、`fin205-hpe-scoped-review-a2/result.json` 及 `completion-schema-replay.json`。
- 产品增量：无。工程增量：无源码/部署改动。研究/资格证据：跨用例历史阶段统计、当前恢复 guard 零模型探测、官方成熟方案核对。文档：本审计及上下文/根因记录更新。
- 阻塞仍在：复杂研究稳定交付、必要问题覆盖、失败专家/审查原生恢复、财务语义验收；第一步未完成。不得把本审计或前次隔离局部资格写成完整 HPE 成功。
