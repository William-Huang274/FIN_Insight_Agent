# 205 两次真实摘要、原文回读与前端部署

2026-09-10，FIN0.1.3 / S3 / 205；继续 `codex/fin013-conversation-and-retrieval`。Owner要求按“真实摘要资格 → 原生/Hermes接入 → 前端部署体验”的顺序执行。没有启动新的产品版本，也没有重跑HPE或金融核验支线。

## 已交付的产品切片

普通对话启用已资格的可选摘要：LangChain选择摘要前缀，LangGraph保留原始消息与摘要状态。摘要仅是接续视图，目录和原始数字仍从完整checkpoint回读。每窗口至多两次自动摘要；摘要失败保留上一有效视图和原文，不自动付费重试。按Owner纠正，第一、第二次摘要请求均省略客户端输出token上限，保留thinking enabled/low、90秒超时和输入边界；普通回答节点原有限额不变。

前端新增“上下文与记忆”：会话原文、数字与计算、来源记录分区浏览/查找/原文分页；工作底稿沿用独立版本和Qwen检索。可查看摘要次数、当前摘要及原始记录/投影条数，明确条数不是tokens。目录是只读入口，不触发模型、SQL或外网查询。既有“保留进度并开新对话”保留。

Hermes增加原生会话目录与原文读取工具，使用SessionDB原始消息ID，宿主绑定会话，模型不能指定其他会话。只读公开user/assistant文本，不混入私有推理。共享纯读取函数只依赖langchain-core，未给Hermes另装LangGraph或创建第二套存储。**Hermes自身自动压缩仍关闭**；普通问答/底稿工具接入不等于所有研究角色迁移。

## 真实执行证据与开销

旧失败 `D:/temp/fin205-context-matrix-a1` 保留不改。新资格按case-id只执行失败的两次摘要情境，不重跑已通过四题；调用前冻结各节点TokenBudgetBasis。

| 实测 | 结果 | 新模型调用 / 已知tokens |
| --- | --- | --- |
| 两次真实摘要a2 | 两份摘要均有正文；随后浏览目录、读r-91c，恢复NOVA FY2024 CFO207百万美元/合成来源；保留取消ACME和原因分析的用户更正 | 5 / 22,755（2摘要＋3回答） |
| 已部署原生前端接续 | 通过LangGraph原生supersteps导入上述完整资格历史和两份摘要，明确标注合成资料；从前端另发新请求，一次回答正确，未新增查询/计算/底稿写入 | 1 / 7,305 |
| 已部署Hermes前端回读 | 在原底稿修订窗口提问；首次多词字面目录检索为空，随后留空浏览并读用户消息5；正确保留撤回结论、等待附注和停止检索，没有底稿写工具 | 4 / 28,872 |

本轮共10次DS请求、58,932已知tokens、新未知0；Qwen本轮0。205累计631次真实尝试、17,959,502已知tokens、历史未知3。Hermes独立审计确认用量，BFF当前尚未投影其调用用量，不能把BFF的空统计解释为零消耗。原生单次页面7165输入tokens是实际请求用量，不是原始存档或模型全部窗口的精确长度。

私有证据：`D:/temp/fin205-context-two-summaries-a2`、`D:/temp/fin205-context-deploy-a1`；包括原响应/推理、final-state、导入记录、产品TokenBudgetBasis、两个BFF结果和product-results.json。Hermes实际请求位于 `D:/temp/fin205-hermes-memory-service-a1/fin-audit/f80fa1f5716c1bd3ad4cad910f2e41b51e3db149e75ccdeb58a8ac57a4398761/35bc25b3b3c9481d90ead13d5dc8efad`。全部留在私有目录，不进Git。

原生线程 `01a08be8-6b0a-7492-a635-2fc3123e3d48`，新run `01a08bf0-6512-7173-af5b-8ba035b923f6`。Hermes线程 `01a08a8d-9705-76e0-860e-2a4ad9f8553a`，新run `01a08bf3-0469-7742-a290-c157a6fe08a7`。两者均success/idle。导入本身零模型调用；不能把这次导入后的接续冒称“前端从零积累历史触发两次摘要”。

## 工程检查与实际部署

- 47项定向Python检查通过；最后摘要schema/文字调整后19项相邻检查通过（有重叠，不相加）。TypeScript和Vite构建通过；现有大chunk/Zod注释警告保留。
- 14项浏览器检查通过。实际页面轮询发现ConversationMemory和WorkingNotes兄弟元素复用key，导致每次刷新新增面板；改为不同key。补上连续三次轮询仍只有一份面板的回归，桌面/移动两项通过；实际前端刷新验证为一份。
- 实际UI通过目录选择NOVA FY2024，原文显示207百万美元及fixture:r-91c；两次付费请求均由前端按钮发起。Hermes只调用browse_context两次及read_context_turn一次。
- 18795工作台/BFF、18165原生API、18806 Hermes已重载。原生镜像重新构建，部署包含RequestSummaryState及新配置；PG/Redis和旧数据卷恢复，原报告与窗口保留。配置目录仍为 `Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/report-workbench-20260906-a1`。
- Docker启动遇到已停止进程遗留AF_UNIX socket目录不可访问。核查后仅将 `%LOCALAPPDATA%/Docker/run` 与 `%LOCALAPPDATA%/docker-secrets-engine` 分别改名为同级 `run.fin205-recovery-20260910`、`docker-secrets-engine.fin205-recovery-20260910`，让Docker重建socket；未删目录、未清数据卷、未恢复出厂设置。原目录只含零字节socket/reparse项。Docker已重新启动。

## 明确未完成的部分

这是合成资料的上下文接续产品资格，不是金融研究结论质量、所有长会话的压缩保真率或节费对照。两个真实摘要现在已通过，但没有证明长期累计压缩无损。Hermes首次多词检索为空后恢复，说明字面目录检索仍有额外调用；工作底稿语义检索与此目录应保持分工。

Hermes自动压缩/实时上下文用量投影、长期用户偏好提炼、所有研究节点统一接入、任意节点中断后的依赖重排、生产身份隔离/sandbox、完整报告质量和公开仓库收口仍不计完成。本窗口两次摘要用完后原文继续保存，接近输入保护边界应明确交接，不无限自动摘要。本轮付费停止，交用户查看已部署效果。

产品增量是可操作记忆目录和真实接续；工程增量是共享只读层、摘要生产接入、Hermes原生回读及轮询修复；研究证据是上述三个有界样本；文档增量是本记录与Project OS状态，不另计实现。

工程提交 `2491860b`。24个候选文件凭据模式检查无命中，JSONL可解析，diff检查通过；文档与工程分开提交。生成的前端dist、原始请求、SQLite和私有资格产物不进入Git。继续开发分支，不更改公开main或release。
