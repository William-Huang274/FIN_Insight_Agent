# 205 分区上下文、压缩后核对与有界接续资格

2026-09-10，FIN 0.1.3 / S3 / 205；分支 codex/fin013-conversation-and-retrieval。产品版本、历史报告和旧失败不变。本次仍应用 Project OS、全局质量、Git hygiene 和工作日志规范；不另建运行控制面。

## Owner 目标与本次范围

先让 Agent 知道何时核对已有上下文，再让它能分区发现和读取正确记录；长期用户记忆/长会话提炼需实测，不要求百分百无损，但应有明确失败出口。工作底稿继续是自然语言正文，不加金融章节合同。目录和摘要是派生视图，不得取代原始数字、用户意见或底稿版本。

本次先做一个可执行切片：原生通用对话的 checkpoint 分区目录与回读、共享请求摘要的用户纠正保留，以及有限模型接续对照。没有全面迁移 Hermes、开启其自动压缩或重跑 HPE。

## 已实现

- `context_navigation.py`：通过现有 LangChain ToolRuntime 读取宿主绑定的本窗口 checkpoint；`browse_context` 分 conversation / numbers / sources，最近优先、12条分页、元数据字面过滤。`read_context_turn` 精确读取公开消息；数字和原文通过已有 `read_saved_result` 原样分页回读。无 SQL/web/embedding 重发，无跨窗口参数，无新增数据库。
- 稳定键复制原 message/tool-call ID，不让模型从标题猜 ID。显示自然语言类别及原调用参数/预览。用户消息、历史助手候选与数字结果分开，失败调用标为 error，不把失败变成未披露。
- `ContextOrientationMiddleware` 给模型本窗口各区记录数量，不把非可信原文提升为系统指令。指引在接续、压缩、用户纠正、疑似缺失或重复取数前核对相关记录；眼前原文足够则直接使用，无须全库搜索。这是行为引导，不能保证模型每次遵守。
- `RequestSummaryMiddleware` 继续使用原生 LangChain 摘要/截断工具配对逻辑，完整消息保留于 checkpoint。最近一条被省略的用户消息额外原文置入请求。该额外投影不参与下次摘要的原始边界计数，避免连续压缩时误算前缀。
- 工作底稿沿用既有 SQLite 正文/版本及 Qwen + sqlite-vec 检索；补充公司/期间/主题的可读标题和按 opaque ID 回读的提示。本轮未新增语义索引、未调用 Qwen。普通 checkpoint 目录目前是字面过滤，不能冒称跨语义召回。

部署边界：新目录只接原生通用对话。共享摘要改动在启用该中间件的路径生效；未更改启用开关。Hermes 本轮只继承工作底稿指引，仍仅三项底稿工具，自动压缩关闭。没有更新运行中的 18795/18165/18806 服务或前端。

## 技术栈取舍与长期方案

采用已经安装的 LangChain middleware / ToolRuntime、LangGraph checkpoint 和既有正文检索；FIN 新增的是薄目录适配，不是第二个检索引擎或工作流。

参考 [Deep Agents context engineering](https://docs.langchain.com/oss/python/deepagents/context-engineering) 的原文卸载、按需载入和少量常驻记忆；不为了文件接口复制一份现有 SQLite 正文。参考 [Letta Context Repositories](https://www.letta.com/blog/context-repositories/) 的可读定位与可维护记忆，本轮用已有稳定 ID 和版本承接，不引入第二套 Git 权威库。

[ACE，2026-06](https://arxiv.org/abs/2606.31564) 的原文/抽象选择与 [ACM，2026-07](https://arxiv.org/abs/2607.23809) 的主动上下文管理作为下一步资格候选，不声称已安装、复现论文收益或属于企业生产验证。本轮没有训练选择器、没有每一步额外调用一个模型挑记忆。

后续长期记忆按三类增量推进：

1. 每次接续保留短背景：任务、当前范围、用户纠正、已完成/未完成、相关记录位置。原数字/来源/大段历史按需读取。背景缺字段不阻断自由底稿保存。
2. 长会话整理只形成可替换的派生摘要，记录它覆盖的原消息边界；可从原记录重新生成，避免永久“摘要再摘要”。用户改口要使旧摘要失效/重整，不能由历史助手结论压过用户原话。跨窗口继续走现有宿主授权交接。
3. 用户长期偏好与研究结论分开。只有明确表达、作用域合适的偏好才进入长期候选；模型推断要标注来源和待确认，不能把“本次不要分析原因”永久记成用户从不需要原因分析。先复用现有版本化自由正文/Store 接缝资格，是否引入新后台整理服务由实测决定。

下一组固定小样本应覆盖：同公司跨财年与多公司同名指标、用户推翻旧指令、底稿新旧版本冲突、别名检索失败、三轮以上压缩与窗口交接。分别统计原文恢复、引用/期间/单位保留、旧结论污染、无谓回读次数、重复外部查询、完成率与tokens。目录找不到先留空分区浏览/改短词/检查版本与作用域；仍缺失则明确请求具体记录或交接。工具失败不是公开信息缺口。当前没有自动长期用户画像功能，以上是有界下一步方案。

## 离线验证

48 项通过：`test_context_navigation`、`test_model_context`、`test_request_summary`、`test_conversation_agent`、`test_conversation_tools`、`test_conversation_handoff`、`test_working_memory`、`test_working_memory_search`、`test_hermes_working_memory_bridge`。

包括：区域混淆/字面零匹配回退、旧目录分页、不暴露 reasoning 字段、摘要遗漏时原文用户纠正保留、两次原生压缩边界、关闭重开实际 SQLite checkpoint 后浏览→精确回读、其他窗口不可读。脚本化模型验证工程行为，不作真实模型主动性的证据。

## 有界真实模型结果及失败归属

脚本 `scripts/qualification/context_navigation_roundtrip.py`。每个 attempt 两组：正常原文视图 / 故意遗漏数字且保留旧错误说法的摘要视图，各最多3次请求，合计6；每请求实际输入上限20000字符、输出1200tokens、90秒、thinking enabled / low、DeepSeek `deepseek-flash`，零传输重试。每次发送前写入任务专属 TokenBudgetBasis。数据是虚构 Acme CFO 100→80 百万美元，用户已纠正不得当作现金余额、不继续研究原因。

| Attempt | 结果 | 请求 / 已知tokens | 解释 |
| --- | --- | --- | --- |
| a1 | 两组都找到正确原记录，但未完成答复 | 6 / 18072 | 测试脚本误把 production factory 的计算器也开放。模型继续调用计算器，normal触发model limit、lossy触发tool limit。属于资格脚本范围错误，不算模型接续通过；原件保留。 |
| a2 | 两组都完成这个合成样本的接续 | 6 / 13570 | 限定最初预定的三项只读工具，并补充眼前信息足够无需回读的指引。正常7446tokens、摘要6124tokens；不是单变量消融或跨任务节费证据。 |

a2 两组均先浏览 numbers/conversation，再按 `receipt-73ab` 回读，得到正确100/80、FY2024/FY2025、百万美元、来源ID，并明确CFO不是现金余额、原因不判断、数据虚构。没有外部查询/SQL重发。正常组仍无谓回读眼前已有原文，说明“能发现并回读”有证据，但“知道何时无需检索”未通过效率验收。此次主动回读依然在明示接续的单个开发样本中验证，不能推广为自主识别所有压缩情境。

a2 产物已写入后，Windows GBK 控制台打印 Unicode 数学符号失败；改为 ASCII JSON 控制台输出，UTF-8 产物保留，不重跑模型。调用/结果已由独立审计文件核对，不能把打印错误记成未知调用。

私有证据：`D:/temp/fin205-context-recovery-a1` 与 `D:/temp/fin205-context-recovery-a2`。含 TokenBudgetBasis、事件、原始请求/推理字段/正文、SQLite checkpoint，不能提交Git。a1失败原件不改写；脚本新增失败时导出partial-state，原始checkpoint仍是权威。

合计新增12请求、31642已知tokens、新未知0；205累计610实际尝试、17872554已知tokens、历史未知3。本轮Qwen请求0。付费资格停止，不追加追绿。

## 当前交付判断

工程增量：分区导航、原文用户纠正投影、连续压缩边界保护、可复用有界资格脚本。产品增量：源码里的通用对话具备新工具，运行中的前端/服务未更新。资格证据：48离线通过及两组真实合成接续，含失败记录。文档增量：本记录、产品基线、Project OS。未完成：正常上下文避免无谓回读、真实多次摘要的累计保真、Hermes相同工具/上下文接缝、长期偏好提炼、多Agent任意节点依赖重排。未宣称完整问题已解决。

工程提交：`a1387b63`。定向编译、diff whitespace检查通过；14个候选文件凭据模式检查无独立密钥命中（首个宽匹配命中历史普通单词中的sk-子串，边界检查排除）。运行SQLite、原始响应和日志留在私有证据目录，不提交。
