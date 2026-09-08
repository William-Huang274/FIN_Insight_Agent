# 196：三层研究图与目标修订入口

2026-09-08，FIN 0.1.3 / S3；实现提交41e680bc，本地codex/fin013-report-reader。Owner明确要求把三层前端跳转、真实产物绑定与针对判断的修订闭环合并实施，完成后再考虑几个小case。本轮没有发起研究模型调用，没有推送公开草稿分支，Hermes未开始。

## 产品增量

- 移除54条长引用下拉。默认报告总览，以已保存报告的章节为专题，点击进入专题判断图，再下钻到判断、来源、CALC和操作数。面包屑返回上级，原报告阅读与历史版本保留。真实Dell v4识别10个专题，同一引用可属于多个专题，计数不能相加当唯一引用总量。
- 来源详情增加宽幅原生dialog，支持主张/摘录与上下文对照、存档原文、加载后续分页、查找定位、外部文献入口及返回原图。读取固定checkpoint；完整存档对象可能只是一段文献，不能声称已取得外部全文。
- 当前报告的每条绑定引用可写修订意见，预览后确认进入既有研究修订流程；历史版只读。提交按钮说明真实模型费用。页面按原生run回显状态、目标、基线版本和相对基线的真实报告diff；运行完成仍需审阅，不自动称通过。
- 原始引用主张可能早于正文修订，保留身份提示。第一、二层边只表示正文归属，第三层仅投影保存的引用/计算依赖，没有生成或伪造模型内部思维。

## 工程增量与成熟栈取舍

导航采用已资格React Flow12.11.6；章节/引用投影采用已存在依赖unified11.0.5、remark-parse11.0.0、remark-gfm及现有绑定引用插件，本轮将前两者声明为直接依赖。保留原npm lock，不引入另一套解析平台、工作流、队列、锁或图数据库。

新增FIN领域RevisionTarget：request_id、citation_id、base_version、base_digest、base_checkpoint。章节位置ID只用于导航，不当持久研究ID；服务端从保存产物取得主张和来源，不相信前端任意图节点的描述。BFF验证当前产物及指定历史checkpoint；原生human_review在调用研究处理器前再次检查实际状态，防止预检后基线变化。意见作为用户反馈而非事实证据，目标上下文进入已有research_revision路由；浏览器无任意goto权限。

继续使用Agent Server的multitask_strategy=reject。相同request_id及负载从run metadata读回既有运行，负载变化409；原生checkpoint记录已接受请求ID阻止重复处理。SDK当前RunsClient.create不提供run_id入参，未虚构该参数。前端防双击，未知提交结果停止自动重发并提示读运行状态。它不是新幂等服务，也不承诺任何网络故障下的全局exactly-once。

没有新增模型节点或更改已有模型预算；现有责任修订的TokenBudgetBasis继续约束实际模型节点。本轮脚本替代模型，不产生新付费authority；后续小case应单独明确任务、预算依据、停止条件及金融内容验收。

## 资格证据与失败处理

- Python：原有28项先通过；首次合跑33通过/1失败，定位为ReviewAction.model_dump输出UUID对象不能JSON序列化。修复在BFF序列化边界使用mode=json/exclude_none，未削弱测试。新6项重验通过；最终两文件34项通过（17.60秒）。
- 原生LangGraph脚本覆盖：合法目标到既有修订处理器并产出v2、旧checkpoint可读；过期digest、未知引用、重复请求在处理器前拒绝。BFF覆盖浏览器写保护、相同请求回用run、不同负载409、目标JSON与原生reject策略。处理器为脚本，不能称真实模型语义通过。
- 浏览器A1：1440/1024/390三宽度研究图与原阅读历史共6通过（16.3秒），证据D:/temp/fin-hierarchical-graph-a1/results。覆盖三层跳转、来源503重试、现代/legacy计算及alias、宽幅模式/分页/查找/Escape、分引用草稿、mock提交唯一POST及目标基线、运行投影、报告diff、无横向溢出。仅测试服务接收模拟提交。
- 最后小修保证引用摘录按当前source_id选择，避免拿其他来源首条摘录；TypeScript noEmit及最终Vite构建通过。产物index-Cn3xSSMF.js/index-B82OjNUp.css，既有大包警告仍在，不称性能优化。
- CUA真实v4：总览→现金流专题→现金转化率判断→cfo_q2计算操作数→Dell FY2027 Q2 EX99.1；宽幅原文、cash查找、返回和修订预览可读。没有点击正式确认提交，草稿已清空并返回总览，页面error日志为空。工程入口可用不等于Owner认可易用性。
- 暂存增量四类credential模式扫描0命中，git diff --check通过；仅有界增量检查，不是全仓安全保证。

## 本地部署与停止点

部署前确认没有活动研究；固定settings仍为Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/report-workbench-20260906-a1，fresh-only/enable-research。原生18165重建API，保持原Postgres/Redis及历史卷；镜像config SHA164fd58dfabd489b48e046bcfd97b03cbf15ce3216b5aa2314c6f6801ff0ce1d。8766旧BFF进程按命令行核实后更换为PID4512（隐藏启动），日志D:/temp/fin-hierarchy-bff-20260908.*.log。

实际会话01a077d8-a47c-7280-98f5-3df94b219488仍28runs、报告v4、interrupted/can_respond，digest64字符。未清库、未新增研究运行或研究费用。页面已打开供Owner体验。

尚未完成：真实模型对目标修订的研究质量与费用实测、持久平行候选分支、精确到任意研究节点的增量执行、完整显式假设/反证关系。当前结果关联为目标引用＋实际报告diff，不能声称所有受影响判断已结构化定位。用户稍后决定小case；本轮停止在可体验实现，不自动启动这些工作。公开main和产品版本不变，原v4金融语义审阅意见及摘要disabled继续保留。
